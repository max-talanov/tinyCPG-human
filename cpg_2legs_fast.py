#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cpg_2legs_nest_to_hdf5.py
Run the 2-leg CPG NEST simulation headlessly (HPC-friendly) and save all time-series
(and basic network stats) into an HDF5 file for later plotting on a local machine.

Example:
  python3 cpg_2legs_nest_to_hdf5.py --out cpg_run.h5 --sim-ms 60000 --dt-ms 10 --threads 10 --long-run

If your NEST build supports MPI, launch with mpirun/srun externally.
Only rank 0 writes the .h5 file.
"""

import argparse
import os
import time
from datetime import datetime

import numpy as np
import h5py
import nest

# PLAN.md P1: species YAML configs live next to the real model file (resolve
# symlinks, e.g. regress.sh runs the model through one from a scratch dir).
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from species_config import ConfigError, load_species, to_yaml  # noqa: E402


def get_kernel_parallel_status(nest_mod):
    """Return (mpi_procs, local_threads) without assuming specific kernel keys."""
    ks = nest_mod.GetKernelStatus()
    mpi_procs = ks.get("mpi_num_processes", ks.get("num_processes", ks.get("total_num_processes", 1)))
    local_threads = ks.get("local_num_threads", ks.get("num_threads", ks.get("threads", 1)))
    return int(mpi_procs), int(local_threads)


LEGS = ("L", "R")

# ---------- sizes ----------
N_CUT = 100
N_BS = 100

N_RG_TOTAL = 200
N_RG_E = N_RG_TOTAL // 2
N_RG_F = N_RG_TOTAL - N_RG_E

N_MOTOR_E = 100
N_MOTOR_F = 100

N_MUS_E = 100
N_MUS_F = 100

N_IA_E = 100
N_IA_F = 100

# Interneurons (per leg) to match physiological motifs in the schematic
N_IA_INT = 50  # inhibitory interneurons driven by Ia afferents
N_INE = 50  # inhibitory interneurons mediating RG-E -> RG-F inhibition
N_INF = 50  # inhibitory interneurons mediating RG-F -> RG-E inhibition

# Synaptic weights (tune as needed)
W_IA_IN2INT = 6.0  # Ia parrot -> Ia inhibitory interneuron (excitatory synapse)
W_IA_INT2ANT = -10.0  # Ia inhibitory interneuron -> antagonist motor pool (inhibitory synapse)

# MOD_IA_LOOP: Ia afferents also drive the RG reciprocal interneurons (InE, InF).
# Ia-E (driven by extensor force/stretch) → InE → inhibits RG-F.
# Ia-F (driven by flexor  force/stretch) → InF → inhibits RG-E.
# This is closed-loop sensory feedback INTO the CPG core. It reduces the model's
# dependence on tonic BS drive: at low BS (~20 Hz in --debug-small), the
# Ia → In → RG loop is what keeps the rhythm self-sustaining, approximating the
# role that intrinsic INaP bursting plays in the Hodgkin-Huxley Zhang 2022 model
# (we don't have INaP in Izhikevich neurons).
W_IA2IN = 6.0  # moderate increase: reinforces Ia→In feedback without over-speeding cycle (was 5; 8 makes cycles too fast)
P_IA2IN = 0.25
# MOD_FLEXOR_AFFERENT: direct excitatory weight, swing flexor-afferent → RG-F.
# Clocks the flexor burst during swing (Grillner & Rossignol 1978 hip afferent).
W_FLEX_AFF2RGF = 6.0

# MOD_ZHANG_ASYM: Asymmetric reciprocal inhibition between RG-F and RG-E half-centres.
# Zhang/Shevtsova/Rybak (eLife 2022) Table 2 shows the F→InF→E inhibition is ~13× stronger
# than E→InE→F (effective gains 0.18 vs 0.014). This asymmetry is what gives clean alternation:
# F drives the rhythm and forcibly silences E during the flexor burst, while E only weakly
# nudges F so F's intrinsic burst pattern survives. Symmetric weights here gave shallow
# counter-phase (RG correlation only ~−0.65 instead of ~−0.95).
W_RG2INE     = 12.0    # RG-E → InE   (excites flexor-suppressing interneuron)
W_RG2INF     = 18.0    # RG-F → InF   (excites extensor-suppressing interneuron, stronger)
W_INE2RGF    =  -8.0   # InE → RG-F   (WEAK suppression — preserve F's intrinsic rhythm)
W_INF2RGE    = -48.0   # InF → RG-E   (STRONG suppression — ratio 48:8=6:1, Zhang 2022)
P_RG_RECIP_F = 0.30    # F→InF→E pathway density (higher for strong inhibition)
P_RG_RECIP_E = 0.15    # E→InE→F pathway density (lower for weak inhibition)

# Legacy symmetric constants (kept for any external scripts still importing them)
W_RG2IN = 8.0
W_IN2RG = -18.0

# ---------- CUT training ----------
N_PHASES = 6
CUT_RATE_ON_HZ = 100.0   # MOD_COACT: bio-plausible rat cutaneous/Group-II afferent peak rate
                          # (SAI 10-50 Hz, RA/Aβ up to 100 Hz during active paw contact;
                          #  Loeb & Duysens; Pearson rat locomotion data). 400 Hz was not realistic.
CUT_RATE_OFF_HZ = 0.0

# ---------- brainstem ----------
BS_OSC_HZ = 2.0  # MOD_FIG10: increase RG drive oscillation freq to ~2 Hz baseline (paper-like α≈0.1)
BS_RATE_BASE_HZ = 0.0  # keep near-zero baseline; learning should shape effective drive via STDP weights
BS_NOISE_STD_HZ = 0.0  # Gaussian noise std on BS rate (Hz); overridden by --bs-noise-std-hz
 # Further reduced BS drive amplitude to avoid dominating RG dynamics and to amplify BS->RG STDP learning trajectories
BS_RATE_AMP_HZ = 30.0  # MOD_FIG10: reduce BS modulation amplitude (was 80) to avoid overdriving RG and inflating population rates
BS_RATE_MIN_HZ = 0.0
BS_PHASE = {"L": 0.0, "R": np.pi}  # left-right alternation

BS_REGULAR_HZ = 60.0   # MOD_COACT: reticulospinal tonic drive 20-80 Hz in rat (bio-plausible).
                       # At 60 Hz even fully potentiated STDP weights (capped at WMAX_BS=30)
                       # keep BS alone subthreshold for RGE; CUT co-activation is required.
BS_REGULAR_DESYNC = "linspace"  # MOD_BS_REGULAR200: desynchronize neurons deterministically to avoid synchrony artifacts
BS_REGULAR_JITTER_MS = 0.3  # MOD_BS_REGULAR200: add small spike-time jitter (ms) for quasi-regular cortical-like drive; set 0.0 to disable
BS_DRIVE_NORM_HZ = BS_REGULAR_HZ  # MOD_BS_REGULAR200: normalization constant for activation gating

# ---------- connectivity ----------
P_IN_STDP = 0.5
P_RG_REC = 0.12
W_RG_REC_E = 4.0  # MOD_FIG10: reduced RG-E self-excitation (was 8.0) to bring rates closer to paper
W_RG_REC_F = 5.5  # MOD_FLEXBOOST: slightly stronger RG-F recurrence to lift flexor activity

# Flexor-phase brainstem gain can be species-dependent (human delays often damp oscillations slightly).
# MOD_FLEXBOOST: set per species in config/species/<name>.yaml (constants.drive); 1.0 for rat and human.
FLEXOR_BS_GAIN = 1.00
DELAY_MS = 1.0

P_RG_RECIP = 0.20
W_RG_RECIP = -18.0
DELAY_RECIP_MS = 1.0

# Motor-pool reciprocal inhibition (extra safeguard against E/F co-activation)
P_MOTOR_RECIP = 0.25
W_MOTOR_RECIP = -22.0
DELAY_MOTOR_RECIP_E2F_MS = 1.5
DELAY_MOTOR_RECIP_F2E_MS = 1.0

W_M2MUS = 1.0
P_M2MUS = 0.8

IA2RG_P = 0.4
IA2RG_W = 12.0

BASE_DRIVE_HZ = 2.0
BASE_DRIVE_W = 1.0
BASE_DRIVE_P = 0.10

USE_STATIC_PARALLEL = False # it should be always false if we want STDP working
P_STATIC_IN = 0.03
P_STATIC_RM = 0.03
W_STATIC_IN = 22.0
W_STATIC_RM = 35.0

ENABLE_COMMISSURAL = True
P_COMM_F = 0.22
W_COMM_F_INH = -20.0
P_COMM_E = 0.10
W_COMM_E_INH = -8.0
DELAY_COMM_MS = 1.0
LEFT_RIGHT_BIAS_IE = 0.12

# ---------- conduction + synaptic delay presets ----------
# Delay model: delay_ms = syn_delay_ms + (length_m / velocity_mps)*1000 + jitter
# Notes:
#  - `fixed` preserves legacy behavior using DELAY_MS/DELAY_RECIP_MS/etc.
#  - `length_velocity` uses coarse, tunable presets.
#  - Delays are clipped to at least the kernel resolution.
# PLAN.md P1 / decision D2: the per-path presets (syn_delay_ms, length_m, velocity_mps)
# now live in the `delays:` section of config/species/<name>.yaml, so they can never be
# combined with another species. `fixed` still falls back to DELAY_MS / DELAY_RECIP_MS / ... below.


def _delay_ms_from_preset(preset: dict, delay_scale: float) -> float:
    syn_ms = float(preset.get("syn_delay_ms", 1.0))
    length_m = float(preset.get("length_m", 0.0))
    vel = float(preset.get("velocity_mps", 1.0))
    vel = max(1e-9, vel)
    base_ms = syn_ms + (length_m / vel) * 1000.0
    return float(delay_scale) * float(base_ms)


def make_delay_param(delay_model: str, paths: dict, key: str, *,
                     fallback_ms: float, res_ms: float, jitter_ms: float, delay_scale: float):
    """Return a scalar or a NEST Parameter for synaptic delays.

    - fixed: returns fallback_ms
    - length_velocity: returns base_ms (+ optional Gaussian jitter), clipped to >= res_ms

    IMPORTANT: Call this only after nest.SetKernelStatus().
    """
    delay_model = str(delay_model).lower().strip()

    if delay_model == "fixed":
        return float(fallback_ms)

    preset = (paths or {}).get(key, None)
    base_ms = float(fallback_ms) if preset is None else _delay_ms_from_preset(preset, delay_scale)

    p = float(base_ms)
    jm = float(max(0.0, jitter_ms))
    if jm > 0.0:
        p = p + nest.random.normal(mean=0.0, std=jm)

    # Clip to at least the kernel resolution
    try:
        p = nest.math.max(p, float(max(1e-9, res_ms)))
    except Exception:
        p = float(max(float(p), float(max(1e-9, res_ms))))

    return p


# ---------- STDP ----------
TAU_PLUS = 20.0
# Lower learning rate and mild LTP/LTD balance + multiplicative STDP to reduce hard-boundary pileups at 0/Wmax
LAMBDA = 0.001
ALPHA = 0.95
MU_PLUS = 0.4
MU_MINUS = 0.4
WMAX = 120.0

# MOD_COACT: BS STDP weights capped so tonic BS alone stays subthreshold even after
# full STDP potentiation. CUT STDP keeps the full WMAX.
WMAX_BS = 30.0

# MOD_IA_RG_STDP: plastic homonymous Ia->RG-E/F projection (matches the reference
# architecture's direct excitatory Ia->RG arrow, distinct from the Ia->InE/InF
# reciprocal-inhibition loop). Always wired now -- a third standing plastic pathway
# alongside BS->RG and CUT->RG, present in every mode (BS->RG->RG-E and BS->RG-F still
# drop out under --freeze-bs-rg; Ia->RG and CUT->RG keep training either way).
# WMAX_IA TUNING (debug-small, 25 s, frozen BS, --stdp-ia-rg): the homonymous Ia->RG loop
# is in-phase positive feedback, so a *low* cap is essential — a light phased boost
# reinforces each burst without filling the inter-burst trough, but a high cap saturates
# into quasi-tonic co-excitation of BOTH half-centres and destroys counter-phase.
# WMAX_IA sweep on corr(Force-E,Force-F): 10->-0.98, 20->-0.71, 30->-0.50, 60->-0.26,
# 120->+0.12. WMAX_IA=10 BEATS the BS-plastic control (-0.98 vs -0.96) AND fixes the weak
# flexor (Force-F peak 11->17). Override with --wmax-ia.
# CAVEAT: this tuning was done with BS frozen weak. Now that Ia->RG is always wired
# (including alongside a fully plastic, much stronger BS->RG in the descending arm),
# WMAX_IA=10 as a universal default is NOT yet re-validated there -- smoke-test before
# trusting it (see CLAUDE.md "core architecture fix" notes).
WMAX_IA = 10.0
P_IA2RG_STDP = 0.5  # density of the new Ia->RG plastic projection (matches CUT/BS P_IN_STDP)

# MOD_IA_RG_LOADING_GAIN: WMAX_IA above is validated for FULL loading (--cut-feedback-gain
# 1.0), where Ia is meant to stay a light supplementary boost alongside a full-strength
# CUT->RG-E. Under simulated unloading (air/toe stepping, --cut-feedback-gain low), CUT
# can't provide its usual excitation (that's the definition of unloading), and Ia can't
# substitute for it while capped at 10 -- confirmed by direct test: boosting
# --ia-feedback-gain up to 8x at --cut-feedback-gain=0.1 left force_e maxing out ~1.6
# (vs. the normal ~17 ceiling) because ia->rge_mean itself stays capped near WMAX_IA
# regardless of gain (gain scales Ia's input RATE, not its weight ceiling). WMAX_IA_UNLOADED
# raises that ceiling specifically as loading drops, so Ia can only take over more
# excitatory drive when cutaneous input is genuinely reduced -- bio-plausible framing:
# post-SCI/deafferentation upregulation of spinal sensory gain (central sensitization),
# not an arbitrary knob, and it leaves the already-validated full-loading behaviour
# (WMAX_IA=10 at cut_feedback_gain=1.0) exactly as before. NOT YET validated whether 60
# is the right unloaded ceiling -- smoke-test before trusting it.
WMAX_IA_UNLOADED = 60.0

# MOD_COACT: static CUT → RGE pathway — immediate cutaneous drive present from t=0,
# before STDP bootstraps. Weight and density chosen so that CUT alone (100 Hz × W=14
# × ~35 conns) is still subthreshold, but CUT + BS (60 Hz × ~25) together are supra-
# threshold. This enforces the co-activation gate from the first simulation step.
W_CUT2RGE_STATIC = 14.0
P_CUT2RGE_STATIC = 0.35

# MOD_CUT_REFLEX: CUT also excites the flexor-suppressing interneuron (InE).
# This is the canonical *stance-phase cutaneous reflex* (Schomburg, Pearson, Rossignol):
# paw contact → cutaneous afferents → reinforce extensor activity AND suppress flexor.
# Effect on the model: CUT now does double duty — direct excitation of RG-E *plus* indirect
# inhibition of RG-F via InE. This dramatically deepens the counter-phase during stance
# without altering BS or the central CPG balance.
W_CUT2INE = 6.0
P_CUT2INE = 0.30

W0_IN = 22.0
W0_RM = 30.0

# ---------- Izhikevich ----------
izh_params = dict(a=0.02, b=0.2, c=-65.0, d=8.0, V_th=30.0, V_min=-120.0)
izh_inh_params = dict(a=0.1, b=0.2, c=-65.0, d=2.0, V_th=30.0, V_min=-120.0)  # UPDATED_v7
I_E_RGE = 1.0  # MOD_REBALANCE: extensor tonic drive baseline
I_E_RGF = 0.9  # MOD_REBALANCE: flexor tonic drive slightly lower to shorten RG-F bursts; 1.1 makes IB too fast

# Izhikevich "chattering" (bursting-like) parameters for RG-F excitatory neurons
# (Izhikevich 2003/2004 canonical set)
RGF_A = 0.02
RGF_B = 0.2
RGF_C = -55.0  # MOD_FIG10: intrinsic-bursting-ish RG-F
RGF_D = 4.0    # MOD_FIG10: intrinsic-bursting-ish RG-F
I_E_MOTOR = 1.0

# ---------- muscle proxies ----------
# Activation proxy: saturating nonlinearity + brainstem gating to avoid saturation & enforce timing
TAU_ACT_RISE_MS = 20.0   # fast rise: activation tracks burst onset in ~20ms (was 60ms, too slow for 150ms cycles)
TAU_ACT_DECAY_MS = 20.0  # fast decay: activation drops in ~20ms so force clears baseline in 75ms off-phase (was 35ms)
ACT_MAX = 1.2
ACT_SAT_K = 0.02          # slope for activation from muscle relay rate; saturates at ~100-150 Hz (was 5e-4, ~40× too small)
ACT_GATE_POWER = 2.0      # (legacy) squared clamp gate — superseded by the logistic gate
# MOD_LOGISTIC_GATE: smooth (bio-plausible) sigmoidal activation gate replacing the
# hard clamp(x,0,1)^p. d = sigma(ACT_GATE_K * (r_RG/rg_ref - ACT_GATE_X0)). The
# steepness/mid-point are tuned to preserve the burst/trough discrimination of the
# old clamp^2 gate (trough r/ref~0.25 -> d~0.06; burst ~0.8 -> d~0.83; saturates at 1).
ACT_GATE_K = 8.0          # logistic steepness
ACT_GATE_X0 = 0.6         # logistic mid-point (fraction of rg_ref)

TAU_FORCE_RISE_MS = 30.0   # rat fast-twitch twitch rise ~15-30ms; shorter allows force to track 150ms bursts
TAU_FORCE_DECAY_MS = 30.0  # fast relaxation: force drops below 2 in 75ms off-phase (was 60ms)
FORCE_MAX = 25.0
# MOD_FORCE_LINEAR: previously FORCE_SAT_K=2.5 made force saturate near 17.8 at activation 0.5,
# so the force trace flat-topped and never came back to 0 between bursts. With K=1.0, force
# is roughly linear in activation across the working range (0.1–0.6), so counter-phase from
# the activation envelope passes through to force cleanly.
FORCE_SAT_K = 1.0
# --paced-gait replaces the activation/force τ above with these (smooth plateaus for the
# ~500 ms stance windows; were literals in main() before PLAN.md P1).
PACED_TAU_ACT_RISE_MS = 40.0
PACED_TAU_ACT_DECAY_MS = 40.0
PACED_TAU_FORCE_RISE_MS = 80.0
PACED_TAU_FORCE_DECAY_MS = 80.0

# MOD_CUT_FORCE_TRIGGER: initial seed for the per-leg adaptive peak-force tracker
# (fraction of FORCE_MAX), before any real burst has been observed. 0.4*FORCE_MAX=10
# sits inside the empirically observed debug-mode force_e peak range (~11-17), so the
# first real burst crosses the on-threshold and the tracker starts adapting immediately.
# This assumes full loading. Under reduced --cut-feedback-gain the achievable force
# ceiling drops well below this fixed seed (confirmed by direct test: at gain=0.1 with
# the loading-dependent Ia->RG cap rescuing force to ~8, a seed of 10 stayed permanently
# above the real peak, so peak_e_est never adapted and on/off thresholds were meaningless
# relative to the leg's actual force scale) -- MOD_IA_RG_LOADING_GAIN's cap fix alone
# isn't sufficient, the seed has to scale down with loading too, see
# CUT_FORCE_PEAK_SEED_MIN_FRAC below.
CUT_FORCE_PEAK_SEED_FRAC = 0.4
# Floor on how far the seed scales down as --cut-feedback-gain drops to 0 (as a
# fraction of CUT_FORCE_PEAK_SEED_FRAC) -- avoids a degenerate near-zero seed that
# would make the Schmitt trigger pathologically sensitive to noise. NOT YET validated;
# picked as a starting point, smoke-test before trusting it for any real sweep.
CUT_FORCE_PEAK_SEED_MIN_FRAC = 0.5

TAU_LENGTH_MS = 260.0
L0 = 1.0
L_MIN, L_MAX = 0.5, 2.0
SHORTEN_GAIN = 0.010
STRETCH_GAIN = 0.35  # extensor-only stretch from CUT fraction

# ---------- Ia ----------
IA_BASE_HZ = 10.0
IA_K_FORCE = 6.0
IA_K_STRETCH = 250.0
IA_RATE_MAX_HZ = 500.0


def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def bs_rates_tonic(t_ms: float, leg: str) -> tuple[float, float]:
    # MOD_TONIC_BS: BS is constant, equal drive to both E and F on both legs.
    # L/R and E/F alternation must emerge entirely from spinal CPG circuitry.
    r = clamp(BS_REGULAR_HZ, BS_RATE_MIN_HZ, BS_REGULAR_HZ)
    return r, r


def bs_rates_counterphase(t_ms: float, leg: str) -> tuple[float, float]:
    # Kept for backward-compatible references; delegates to tonic version.
    return bs_rates_tonic(t_ms, leg)


def make_weight_recorder_safe():
    try:
        return nest.Create("weight_recorder")
    except Exception:
        return None


def safe_len_connections(**kwargs) -> int:
    try:
        return len(nest.GetConnections(**kwargs))
    except Exception:
        return -1


def synapse_sign_stats():
    conns = nest.GetConnections()
    if len(conns) == 0:
        return dict(total=0, exc=0, inh=0)
    w = np.array(nest.GetStatus(conns, "weight"), dtype=float)
    return dict(total=int(w.size), exc=int(np.sum(w >= 0.0)), inh=int(np.sum(w < 0.0)))


def node_model_counts(models):
    out = {}
    for m in models:
        try:
            out[m] = int(len(nest.GetNodes(properties={"model": m})[0]))
        except Exception:
            out[m] = -1
    return out


def sample_w(model_name: str) -> np.ndarray:
    conns = nest.GetConnections(synapse_model=model_name)
    if len(conns) == 0:
        return np.array([], dtype=float)
    return np.asarray(nest.GetStatus(conns, "weight"), dtype=float)


def sorted_connections(conns):
    """Return `conns` in a deterministic order: by (source, target, synapse_id, delay, weight).

    With more than one NEST thread, GetConnections returns the same connections in a
    run-to-run varying order (PLAN.md §7, B11). Anything that pairs connections with
    positional numpy arrays -- per-connection random factors, the --max-weight-conns
    subset, consolidation baselines -- must use a collection from here, or the same
    seed wires a different network on every multi-thread run.
    """
    if conns is None or len(conns) < 2:
        return conns
    try:
        src = np.asarray(nest.GetStatus(conns, "source"), dtype=np.int64)
        tgt = np.asarray(nest.GetStatus(conns, "target"), dtype=np.int64)
        sid = np.asarray(nest.GetStatus(conns, "synapse_id"), dtype=np.int64)
        dly = np.asarray(nest.GetStatus(conns, "delay"), dtype=float)
        wgt = np.asarray(nest.GetStatus(conns, "weight"), dtype=float)
        perm = np.lexsort((wgt, dly, sid, tgt, src))
        return nest.SynapseCollection([conns._datum[int(i)] for i in perm])
    except Exception as e:
        print(f"[WARN] sorted_connections failed ({e}); connection order is NOT deterministic "
              f"with >1 thread -- results will not be reproducible (PLAN.md §7, B11).")
        return conns


def apply_species_constants(constants: dict):
    """Set module-level model constants from a species config (PLAN.md P1).

    Only existing numeric constants can be set, so a typo in the YAML fails loudly
    instead of silently doing nothing."""
    g = globals()
    for name, value in constants.items():
        if name not in g:
            raise ConfigError(f"unknown model constant `{name}`")
        cur = g[name]
        if isinstance(cur, bool) or not isinstance(cur, (int, float)):
            raise ConfigError(f"`{name}` is not a numeric model constant")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"`{name}` must be a number, got {value!r}")
        g[name] = float(value) if isinstance(cur, float) else value


def write_species_provenance(h5obj, cfg: dict, out_path: str = None):
    """Record the resolved species config (PLAN.md P1). HDF5 attrs are all prefixed
    `config_` (scripts/regression_compare.py treats them as provenance, not model
    output); a sidecar <out>.config.yaml holds the same text for humans."""
    text = to_yaml(cfg)
    h5obj.attrs["config_species_yaml"] = text
    h5obj.attrs["config_species_file"] = os.path.relpath(cfg["files"]["species"], os.path.dirname(os.path.realpath(__file__)))
    h5obj.attrs["config_neuron_profile"] = str(cfg["neuron_profile"])
    if "height_m" in cfg["body"]:
        h5obj.attrs["config_body_height_m"] = float(cfg["body"]["height_m"])
    if out_path:
        with open(out_path + ".config.yaml", "w") as fh:
            fh.write(text)


def main():
    global BS_RATE_BASE_HZ, BS_NOISE_STD_HZ, BS_DRIVE_NORM_HZ, ENFORCE_TONIC_BS
    global TAU_ACT_RISE_MS, TAU_ACT_DECAY_MS, TAU_FORCE_RISE_MS, TAU_FORCE_DECAY_MS
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default="cpg_run.h5")
    ap.add_argument("--outdir", type=str, default=".",
                    help="Output directory for HDF5 when using sweep mode. Ignored unless --sweep-pairs is set.")
    ap.add_argument("--tag", type=str, default="cpg",
                    help="Tag used in auto-generated filenames when using sweep mode.")
    ap.add_argument("--run-name", type=str, default="",
                    help="Optional explicit output base name (without .h5). Overrides auto-naming in sweep mode.")
    ap.add_argument("--seed", type=int, default=12345,
                    help="Base RNG seed used for sweep runs (each sweep index gets a deterministic offset).")
    ap.add_argument("--sweep-pairs", type=str, default="",
                    help="Comma-separated list of mu:cv pairs, e.g. '0:0,1:0.8,2:0.4'. When set, runs exactly one pair selected by --sweep-run-idx or SLURM_ARRAY_TASK_ID.")
    ap.add_argument("--sweep-run-idx", type=int, default=-1,
                    help="Index into --sweep-pairs (0-based). If -1, uses SLURM_ARRAY_TASK_ID when available.")
    ap.add_argument("--sweep-dist", type=str, default="lognormal_cv",
                    choices=["const", "normal", "lognormal", "lognormal_cv"],
                    help="Distribution used for initial STDP weights in sweep mode. lognormal_cv interprets CV directly (CV=std/mean).")
    ap.add_argument("--sim-ms", type=float, default=10000.0)
    ap.add_argument("--dt-ms", type=float, default=10.0)
    ap.add_argument("--threads", type=int, default=10)
    ap.add_argument("--print-every", type=int, default=50, help="progress cadence in steps")
    ap.add_argument("--weight-sample-ms", type=float, default=100.0,
                    help="How often to sample STDP weights (ms). Larger = faster.")
    ap.add_argument("--rate-update-ms", type=float, default=20.0,
                    help="How often to push updated rates to poisson_generators (ms). Larger = faster.")
    ap.add_argument("--resolution-ms", type=float, default=0.2,
                    help="NEST kernel resolution (ms). Larger = faster, but less precise. Try 0.2, 0.5, 1.0.")
    ap.add_argument("--simulate-chunk-ms", type=float, default=50.0,
                    help="Simulate in larger chunks to reduce Python<->NEST call overhead (ms). Must be >= dt-ms. Try 50 or 100.")
    ap.add_argument("--long-run", action="store_true",
                    help="Enable long-run defaults (aimed at >=30s sims): coarser chunking, less frequent sampling, and weight downsampling for trend plots.")
    # ---- species configuration (PLAN.md P1: YAML, decisions D1/D2) ----
    ap.add_argument("--species", type=str, default="rat",
                    help="Species configuration: loads config/species/<name>.yaml (constants, CLI defaults "
                         "and delays). Default rat = the tinyCPG baseline. See species_config.py.")
    ap.add_argument("--species-config", type=str, default=None,
                    help="Explicit species YAML path (overrides --species).")
    ap.add_argument("--delay-model", type=str, default=None, choices=["fixed", "length_velocity"],
                    help="DEPRECATED (PLAN.md D2): the delay model is part of the species config. Accepted "
                         "only if it matches the species' `delays: model`; otherwise the run stops.")
    ap.add_argument("--delay-jitter-ms", type=float, default=0.2,
                    help="Std-dev (ms) for per-connection delay jitter when using length_velocity. Set 0 to "
                         "disable. Default comes from the species' `delays: jitter_ms`.")
    ap.add_argument("--delay-scale", type=float, default=1.0,
                    help="Global multiplier on computed delays (useful for quick calibration).")

    ap.add_argument("--max-weight-conns", type=int, default=0,
                    help="If >0, downsample each projection's connection list to at most this many connections when computing weight mean/std (trend mode speed-up).")
    ap.add_argument("--save-weights", type=str, default="snapshots", choices=["none", "final", "snapshots"],
                    help="Save full weight vectors for plastic projections: none=only mean/std; final=store initial+final full vectors; snapshots=store full vectors at each weight sample tick (can be large).")
    ap.add_argument("--probe-reflex-at-ms", type=float, default=None,
                    help="PLAN.md P2 reflex-latency probe: at this time (ms) deliver one synchronous "
                         "volley to every left-leg Ia-E afferent and record raw spike times of left "
                         "RG-E, M-E and mus-E into the HDF5 group `probe`. A negative value builds the "
                         "same probe structure without the volley (the control run). Compare the two "
                         "with scripts/probe_reflex_latency.py.")
    ap.add_argument("--dump-connectivity", type=str, default="",
                    help="If set, after building the network dump per-connection WEIGHT and "
                         "DELAY distributions for every named projection to this HDF5 path, "
                         "then exit (no simulation). For the connectivity-statistics figure.")
    ap.add_argument("--freeze-bs-rg", action="store_true",
                    help="MOD_FREEZE_BS: connect BS->RG-E and BS->RG-F with STATIC synapses "
                         "(no STDP), held at the weak lognormal init (W_INIT_BS ~3.5 pA). BS "
                         "becomes a fixed tonic drive; the sensory-learning arm. Ia->RG and "
                         "CUT->RG stay plastic (both are always-on, see --stdp-ia-rg).")
    ap.add_argument("--stdp-ia-rg", action="store_true",
                    help="DEPRECATED / no-op: plastic homonymous Ia->RG (Ia-E->RG-E, "
                         "Ia-F->RG-F, matching the reference architecture diagram's direct "
                         "excitatory Ia->RG projection) is now always wired and always "
                         "plastic (Wmax=WMAX_IA), alongside BS->RG and CUT->RG -- three "
                         "simultaneously plastic pathways is the standing architecture, not "
                         "an opt-in ablation. This flag is kept only so existing scripts that "
                         "pass it don't break; it no longer changes behaviour.")
    ap.add_argument("--wmax-ia", type=float, default=WMAX_IA,
                    help="MOD_IA_RG_STDP: weight cap for the plastic Ia->RG projection AT FULL "
                         "LOADING (--cut-feedback-gain 1.0). Lower values limit symmetric "
                         "over-excitation of both half-centres (preserves counter-phase); "
                         "higher lets the sensory loop carry more drive. See --wmax-ia-unloaded "
                         "for how this scales up as loading drops.")
    ap.add_argument("--wmax-ia-unloaded", type=float, default=WMAX_IA_UNLOADED,
                    help="MOD_IA_RG_LOADING_GAIN: weight cap for the plastic Ia->RG projection "
                         "at FULL unloading (--cut-feedback-gain 0.0) -- e.g. air-stepping, "
                         "where cutaneous drive can't provide its usual excitation. The "
                         "effective cap is linearly interpolated between --wmax-ia (at gain=1) "
                         "and this value (at gain=0) by --cut-feedback-gain, so Ia can only "
                         "take over more excitatory drive when cutaneous input is genuinely "
                         "reduced. Bio-plausible framing: post-SCI/deafferentation upregulation "
                         "of spinal sensory gain, not an arbitrary knob.")
    ap.add_argument("--p-ia2rg", type=float, default=P_IA2RG_STDP,
                    help="MOD_IA_RG_STDP: connection probability of the Ia->RG projection.")
    ap.add_argument("--static-weight-cv", type=float, default=0.5,
                    help="BIO-PLAUSIBILITY (default 0.5): give every static-synapse weight per-connection "
                         "lognormal heterogeneity with this coefficient of variation (mean and sign "
                         "preserved). 0 = delta weights (legacy). Cortical/spinal weights are lognormal "
                         "(Song 2005; Buzsaki & Mizuseki 2014); CV~0.5-1.0 is typical.")
    ap.add_argument("--cut-static-w", type=float, default=0.0,
                    help="BIO-PLAUSIBILITY (default 0 = dropped): weight of the fixed cutaneous "
                         "co-activation pathway parallel to the plastic CUT->RG-E. 0 leaves a single "
                         "plastic cutaneous projection (bio-plausible). Set 14 to restore the legacy "
                         "co-activation bootstrap pathway.")
    ap.add_argument("--stdp-winit-dist", type=str, default="lognormal",
                    choices=["const", "normal", "lognormal", "lognormal_cv"],
                    help="Initial weight distribution for STDP synapses. const=all weights=W0_IN; normal/lognormal draw per-connection weights.")
    ap.add_argument("--stdp-winit-mean", type=float, default=W0_IN,
                    help="Target mean (approx.) for initial STDP weights.")
    ap.add_argument("--stdp-winit-std", type=float, default=0.5,
                    help="Std parameter for initial STDP weights. For normal: std in weight units. For lognormal: sigma of underlying normal.")
    ap.add_argument("--stdp-winit-min", type=float, default=0.0,
                    help="Lower bound for initial STDP weights (used via redraw/clipping).")
    ap.add_argument("--stdp-winit-max", type=float, default=WMAX,
                    help="Upper bound for initial STDP weights (used via redraw/clipping).")
    ap.add_argument("--stdp-winit-bs-mean-mul", type=float, default=1.0,
                    help="Multiplier applied to --stdp-winit-mean for BS->RG STDP projections only.")
    ap.add_argument("--stdp-winit-bs-std-mul", type=float, default=2.0,
                    help="Multiplier applied to --stdp-winit-std for BS->RG STDP projections only (widens BS init distribution).")
    ap.add_argument("--nest-verbosity", type=str, default="M_ERROR",
                    help="NEST verbosity level to reduce slurmout I/O. Try M_ERROR or M_WARNING.")
    ap.add_argument("--bs-base-hz", type=float, default=BS_RATE_BASE_HZ,
                    help="Override tonic brainstem base rate (Hz).")
    ap.add_argument("--bs-noise-std-hz", type=float, default=BS_NOISE_STD_HZ,
                    help="Override Gaussian BS noise std (Hz).")
    ap.add_argument("--enforce-tonic-bs", action="store_true",
                    help="Force BS E/F and L/R rates to remain identical; abort otherwise.")
    ap.add_argument("--debug-small", action="store_true",
                    help="MOD_DEBUG_SMALL: reduce neuron counts and BS drive for fast local "
                         "iteration. Overrides N_RG/N_CUT/N_BS/N_MOTOR/N_MUS/N_IA/N_IA_INT/N_IN "
                         "to ~30-40 and BS_REGULAR_HZ to 20 Hz. Use with --sim-ms 5000 to "
                         "iterate in seconds instead of minutes.")
    ap.add_argument("--paced-gait", action="store_true",
                    help="MOD_PACED_GAIT: replace rotating CUT phase with explicit 1-s gait cycle. "
                         "L and R legs alternate 180° (trot). Stance leg gets CUT ON + sequential "
                         "Ia-E groups (heel→toe). Swing leg gets CUT OFF, RGF bursts freely. "
                         "Use with --sim-ms 10000 and --step-period-ms 1000.")
    ap.add_argument("--step-period-ms", type=float, default=1000.0,
                    help="Full stride period (ms) for --paced-gait: one stance+swing cycle per "
                         "leg, L and R offset by half a stride. Default from the species config.")
    ap.add_argument("--gait-scheduler", type=str, default="halfcycle", choices=["halfcycle", "phase"],
                    help="Timer (--paced-gait) stance/swing scheduler. halfcycle = the original rat "
                         "scheduler: legs take turns, one half-stride each, so stance <= 0.5 (no double "
                         "support). phase = PLAN.md P3 per-leg phase schedule: each leg is in stance for "
                         "stance_fraction x stride, the right leg offset by half a stride; >0.5 gives "
                         "double support. Default from the species config (rat: halfcycle, human: phase).")
    ap.add_argument("--stance-fraction", type=float, default=0.5,
                    help="Fraction of the FULL stride (--step-period-ms) each leg spends in "
                         "stance (CUT on, sequential Ia-E groups active): stance_ms = step_period "
                         "x fraction. The current paced scheduler gives each leg one half-stride, "
                         "so values above 0.5 are refused until PLAN.md Phase 3 (double support).")
    ap.add_argument("--n-ia-groups", type=int, default=3,
                    help="Number of sequential Ia-E sub-groups (heel→mid→toe) for --paced-gait.")
    ap.add_argument("--ia-ext-hz", type=float, nargs="+", default=[60.0, 80.0, 100.0],
                    help="Peak Ia rate (Hz) for each sequential extensor sub-group. "
                         "Mimics heel→mid→toe pressure ramp. Must have --n-ia-groups values.")
    ap.add_argument("--ia-ext-f-hz", type=float, default=0.0,
                    help="MOD_FLEXOR_AFFERENT: rate (Hz) of the external flexor "
                         "swing-afferent driven during the swing phase (hip/flexor-"
                         "stretch signal; Grillner & Rossignol 1978; Pearson 1995). "
                         "Mirrors the stance Ia-E ramp to clock the flexor. 0 = off "
                         "(legacy intrinsic-only flexor); 80 is a typical on value.")
    # ---- MOD_CUT_FORCE_TRIGGER: closed-loop stance detection ----
    ap.add_argument("--cut-trigger", choices=["timer", "force"], default="timer",
                    help="MOD_CUT_FORCE_TRIGGER: 'timer' (default) keeps the existing "
                         "clock-scheduled stance/swing windows. 'force' replaces the "
                         "clock with a per-leg Schmitt-trigger on that leg's own "
                         "extensor force_e (paw-contact proxy): CUT turns ON when "
                         "force_e crosses --cut-force-on-frac of the leg's running peak "
                         "('foot touches down'), OFF when it falls below "
                         "--cut-force-off-frac ('foot lifts off'). Requires --paced-gait "
                         "(reuses its per-leg CUT/Ia-E-group/flexor-afferent wiring).")
    ap.add_argument("--cut-force-on-frac", type=float, default=0.80,
                    help="MOD_CUT_FORCE_TRIGGER: stance-ON threshold as a fraction of the "
                         "leg's adaptive running peak force_e. Close to 1.0 = only near "
                         "the very peak of the burst.")
    ap.add_argument("--cut-force-off-frac", type=float, default=0.20,
                    help="MOD_CUT_FORCE_TRIGGER: stance-OFF threshold as a fraction of "
                         "the leg's adaptive running peak force_e. Must be < "
                         "--cut-force-on-frac (hysteresis band prevents chatter).")
    ap.add_argument("--cut-force-filter-tau-ms", type=float, default=0.0,
                    help="MOD_CUT_FORCE_TRIGGER: time constant (ms) for an exponential "
                         "low-pass filter applied to force_e before it feeds peak_e_est "
                         "and the on/off threshold comparisons. Default 0 = off (raw "
                         "force_e, original behaviour, unaffected regardless of "
                         "--rate-update-ms). Exists because the gate's threshold "
                         "comparisons were previously only ever run at --rate-update-ms "
                         "50ms, which incidentally low-pass-filtered force_e's own "
                         "tick-to-tick noise; naively shortening --rate-update-ms to "
                         "resolve shorter (faster-gait) bouts removes that incidental "
                         "filtering and the trigger chatters (confirmed by direct test: "
                         "50->20ms alone collapsed bout duration to 40-84ms, i.e. rapid "
                         "spurious on/off flips, not a shorter genuine rhythm). This "
                         "flag reintroduces the noise rejection explicitly, decoupled "
                         "from tick rate, so --rate-update-ms can be shortened for fast "
                         "operating points without reintroducing chatter. Try a value "
                         "comparable to or a little above the new --rate-update-ms.")
    ap.add_argument("--leading-leg", choices=["L", "R"], default="R",
                    help="MOD_CUT_FORCE_TRIGGER: which leg starts in stance at t=0 "
                         "(bio motivation: gait initiation from one already-planted "
                         "leg, not perfectly symmetric initial conditions). The other "
                         "leg starts in swing and is held there for --lead-offset-ms.")
    ap.add_argument("--lead-offset-ms", type=float, default=150.0,
                    help="MOD_CUT_FORCE_TRIGGER: duration (ms) the non-leading leg's "
                         "CUT is forced OFF at simulation start, regardless of its own "
                         "force_e, to deterministically break L/R symmetry before the "
                         "commissural circuit and force feedback take over.")
    ap.add_argument("--cut-max-stance-ms", type=float, default=600.0,
                    help="MOD_CUT_FORCE_TRIGGER: failsafe ceiling (ms) on stance "
                         "duration -- forces CUT OFF even if force_e never decays back "
                         "through --cut-force-off-frac. Without INaP-style adaptation, "
                         "the CUT->RG-E->force_e loop is a stable positive-feedback "
                         "plateau (force saturates, never decays on its own), so a pure "
                         "force threshold can lock permanently in stance. This timeout "
                         "is the endogenous-rhythm backstop (bio: hip-extension/limb-"
                         "position limit triggers swing even under continued loading; "
                         "Grillner & Rossignol 1978) -- matches the two-level "
                         "sensory-gated + endogenous-timer phase-transition picture "
                         "(Rybak/McCrea unit-burst-generator model).")
    ap.add_argument("--cut-max-swing-ms", type=float, default=600.0,
                    help="MOD_CUT_FORCE_TRIGGER: failsafe ceiling (ms) on swing "
                         "duration -- forces CUT ON even if force_e never rises through "
                         "--cut-force-on-frac (mirror of --cut-max-stance-ms; prevents a "
                         "leg from locking permanently in swing).")
    # ---- MOD_MUSCLE_FATIGUE: makes the stance->swing force transition genuinely
    # force-driven instead of failsafe-timer-driven (see --cut-max-stance-ms help:
    # confirmed by direct test that without it, force_e saturates and sits flat
    # indefinitely -- RG-E has no INaP-style self-terminating burst mechanism the
    # way RG-F does (RGF_C/RGF_D intrinsic bursting), so nothing makes force decay
    # on its own during sustained stance). Opt-in and OFF by default so existing
    # timer-based paced-gait runs (rat-sh/debug.sh, rat-sh/run.sh, rat-sh/run_*_stdp.sh) are unaffected.
    ap.add_argument("--muscle-fatigue", action="store_true",
                    help="MOD_MUSCLE_FATIGUE: add slow activity-dependent fatigue to "
                         "the force proxy (both E and F) so force genuinely decays "
                         "during sustained high activation and recovers at rest, "
                         "instead of relying on --cut-max-stance-ms/--cut-max-swing-ms "
                         "to force the transition. OFF by default (opt-in) -- only "
                         "affects the force computation, not the neural circuit.")
    ap.add_argument("--fatigue-tau-onset-ms", type=float, default=400.0,
                    help="MOD_MUSCLE_FATIGUE: time constant (ms) for fatigue to build "
                         "up under sustained full activation. Shorter = force decays "
                         "faster during a long stance/swing bout.")
    ap.add_argument("--fatigue-tau-recovery-ms", type=float, default=600.0,
                    help="MOD_MUSCLE_FATIGUE: time constant (ms) for fatigue to clear "
                         "once activation drops. Needs to be fast enough that a leg "
                         "substantially recovers within one swing/stance bout, or "
                         "fatigue creeps up cycle-over-cycle.")
    ap.add_argument("--fatigue-max-frac", type=float, default=0.95,
                    help="MOD_MUSCLE_FATIGUE: maximum fraction (0-1) by which force "
                         "can be attenuated under sustained full activation. Must "
                         "leave the fatigued force floor comfortably below "
                         "--cut-force-off-frac x (this bout's peak), or the leg locks "
                         "at a permanently-fatigued-but-still-'on' plateau instead of "
                         "actually releasing -- confirmed by direct test at 0.85: R "
                         "settled at a stable force_e~2.6 floor (from residual "
                         "activation ~1.2) against an off-threshold of ~1.9 and never "
                         "crossed it. 0.95 leaves a floor of ~0.9, safely below a "
                         "typical off-threshold even for a modest bout peak.")
    ap.add_argument("--leg-fatigue-asym-frac", type=float, default=0.0,
                    help="MOD_LEG_ASYM: persistent (not just at-priming) L/R asymmetry "
                         "in --fatigue-tau-onset-ms, as a fraction of the base value -- "
                         "the leading leg (--leading-leg) gets tau*(1-frac) (fatigues "
                         "faster), the other leg tau*(1+frac). 0 (default) = symmetric, "
                         "matches every prior run exactly. Motivation: several "
                         "force-trigger operating points with short/weak bouts (fast "
                         "speed, reduced loading) reach genuine (non-cap-dominated) "
                         "timing but the L/R phase relationship becomes seed-dependent "
                         "(bistable) -- --leading-leg/--lead-offset-ms only break "
                         "symmetry at t=0, and by steady state nothing distinguishes "
                         "the legs anymore. A small persistent asymmetry (real limbs "
                         "are not identical either) is confirmed (2 seeds) to fix this "
                         "at both a fast-speed and a toe-loading operating point -- see "
                         "CLAUDE.md 'Persistent leg asymmetry breaks the fast/toe "
                         "bistability'. Working magnitude is config-dependent (0.04-0.12 "
                         "tested); too small still flips sign, too large cap-dominates "
                         "the slower-fatiguing leg.")
    # ---- MOD_CONSOLIDATE: tag-and-capture consolidation (replaces vanilla STDP's
    # "every potentiation is kept forever, up to Wmax" retention with a genuine
    # retention gate -- see spinal_plasticity_as_learning_spec.md secs 1-2 and the
    # implementation plan for the literature basis (Sandkuhler spinal E-LTP/L-LTP +
    # BDNF/D1-D5 gating; Grau contingency-gated spinal instrumental learning;
    # Wolpaw two-phase H-reflex conditioning on Ia->motor). Opt-in, OFF by default,
    # and requires --cut-trigger force (the only mode with a genuine-vs-failsafe-
    # forced bout-boundary signal to gate captures on).
    ap.add_argument("--consolidate", action="store_true",
                    help="MOD_CONSOLIDATE: replace vanilla unconditional STDP "
                         "retention with tag-and-capture consolidation on "
                         "CUT->RG-E, Ia->RG-E/F, and BS->RG-E/F (when not "
                         "frozen -- applied uniformly across all plastic "
                         "pathways as of 2026-09-17, previously BS->RG only "
                         "got measurement-only bookkeeping with no actual "
                         "write-back). A per-connection 'tag' (weight above "
                         "its captured baseline) decays with "
                         "--consolidate-tau-tag-ms unless a shared per-leg "
                         "PRP-pool-like accumulator crosses "
                         "--consolidate-prp-threshold first, in which case the "
                         "baseline is frozen at the current weight. Genuine "
                         "(real force-threshold) bout endings push the pool up; "
                         "failsafe-forced ones push it down. WMAX_BS's "
                         "documented anti-runaway role is unaffected -- Wmax "
                         "itself is never touched by consolidation on any "
                         "pathway, only retention within the existing ceiling. "
                         "Requires --cut-trigger force. OFF by default.")
    ap.add_argument("--consolidate-tau-tag-ms", type=float, default=2000.0,
                    help="MOD_CONSOLIDATE: time constant (ms) for a synapse's "
                         "uncaptured tag (weight above its baseline) to decay "
                         "back toward that baseline. A few bout-cycles by "
                         "default; needs its own local tuning round like every "
                         "other timing constant in this project.")
    ap.add_argument("--consolidate-prp-threshold", type=float, default=1.0,
                    help="MOD_CONSOLIDATE: PRP-pool threshold (arbitrary units) "
                         "that triggers a capture event, freezing the current "
                         "weight as the new baseline. The gain flags below are "
                         "defined relative to this.")
    ap.add_argument("--consolidate-prp-gain-genuine", type=float, default=0.20,
                    help="MOD_CONSOLIDATE: PRP-pool increment per genuine "
                         "(real force-threshold) bout ending. Default (0.20, "
                         "vs. --consolidate-prp-gain-forced's 0.15) is a mildly "
                         "genuine-favoring ratio confirmed across two seeds at "
                         "the round-5 operating point (Round 1+2 tuning, "
                         "CLAUDE.md): a 1:1 ratio never captures at all, and "
                         "more aggressive genuine-favoring ratios (0.25+) do "
                         "reach capture but their L/R desynchronization outcome "
                         "was seed-sensitive enough to flip sign between seeds "
                         "-- 0.20/0.15 was the only point that stayed robustly "
                         "good (corr(F-E_L,F-E_R) approx -0.7) in both.")
    ap.add_argument("--consolidate-prp-gain-forced", type=float, default=0.15,
                    help="MOD_CONSOLIDATE: PRP-pool decrement (floored at 0) "
                         "per failsafe-forced bout ending. See "
                         "--consolidate-prp-gain-genuine for how this default "
                         "was chosen -- forced bouts still suppress capture "
                         "(Grau: non-contingent outcomes actively suppress "
                         "spinal learning) but the shipped ratio is only "
                         "mildly asymmetric (~1.3:1), not the originally-"
                         "guessed 2:1, which was confirmed to never capture "
                         "at all at this operating point.")
    # ---- MOD_WMAX_GROWTH: structural consolidation of the Ia->RG ceiling itself ----
    # spinal_plasticity_as_learning_spec.md Sec 4's Ia->RG mapping flags a real gap:
    # WMAX_IA is a fixed, hand-tuned cap; a genuine consolidation mechanism (Wolpaw's
    # Phase I -> Phase II) would let the ceiling itself rise only after demonstrated,
    # repeated stable capture, not stay static forever. --consolidate's baseline/tag
    # split above governs retention *within* Wmax; this governs Wmax itself, and is
    # a separate opt-in on top of --consolidate (requires it -- growth is driven by
    # the same capture events).
    ap.add_argument("--consolidate-wmax-ia-growth-per-capture", type=float, default=0.0,
                    help="MOD_WMAX_GROWTH: opt-in (0.0 default = exact no-op, every "
                         "existing --consolidate run is unaffected). Amount added to "
                         "a connection's own Wmax on Ia->RG-E/F ONLY (not CUT->RG-E, "
                         "not BS->RG-E/F -- this flag never touches their Wmax, "
                         "regardless of whether their weight retention is itself "
                         "consolidated) each time a capture event fires on "
                         "that pathway/leg. Capped at "
                         "--consolidate-wmax-ia-ceiling. Requires --consolidate.")
    ap.add_argument("--consolidate-wmax-ia-ceiling", type=float, default=60.0,
                    help="MOD_WMAX_GROWTH: hard ceiling for the per-capture Wmax "
                         "growth above, applied per-connection on top of whatever "
                         "the loading-dependent --wmax-ia/--wmax-ia-unloaded "
                         "interpolation already set as the starting point. Default "
                         "60 matches --wmax-ia-unloaded's own default so it is a "
                         "familiar number, not a new regime -- not yet validated "
                         "for correctness at this value, this is a first local test.")
    # ---- ablation flags (paper Figure: necessity of each component) ----
    ap.add_argument("--ablate-ia-loop", action="store_true",
                    help="ABLATION: zero Ia→InE/InF closed-loop (W_IA2IN=0). Tests "
                         "whether closed-loop sensory feedback is required.")
    ap.add_argument("--ablate-asym", action="store_true",
                    help="ABLATION: symmetric reciprocal inhibition "
                         "(W_INF2RGE = W_INE2RGF = -28). Tests whether Zhang 2022 "
                         "6:1 asymmetry is required.")
    ap.add_argument("--ablate-comm", action="store_true",
                    help="ABLATION: zero L↔R commissural inhibition "
                         "(W_COMM_F_INH = W_COMM_E_INH = 0). Tests L/R desync mechanism.")
    # ---- graded sensory feedback (Courtine/Lavrov SCI paradigm) ----
    ap.add_argument("--ia-feedback-gain", type=float, default=1.0,
                    help="Multiplicative gain on the closed-loop Ia rate "
                         "(force/stretch → spindle Hz). Default 1.0 = full weight-bearing; "
                         "0.5 = toe stepping (partial weight); 0.1 = air stepping "
                         "(near-deafferented). Bio reference: Lavrov 2008; Edgerton 2008.")
    ap.add_argument("--cut-feedback-gain", type=float, default=1.0,
                    help="Multiplicative gain on the cutaneous (CUT) stance drive, "
                         "scaling the loading-dependent paw-contact feedback. 1.0 = full "
                         "weight-bearing; 0.5 = toe stepping; 0.1 = air stepping (no paw "
                         "contact). The external Ia-E heel→toe ramp (the epidural-stim "
                         "pacing) is NOT scaled, only the cutaneous feedback that drives "
                         "CUT→RG-E learning.")
    # ---- STDP learning rate override ----
    ap.add_argument("--stdp-lambda", type=float, default=None,
                    help="Override the STDP learning-rate constant LAMBDA. Default None "
                         "uses the global LAMBDA = 0.001. Bio-plausible range 5e-4 to 5e-3.")
    # PLAN.md P1: resolve the species config first, so its cli_defaults become argparse
    # defaults (explicit flags still win) and its constants are applied before any use.
    pre, _ = ap.parse_known_args()
    try:
        SPECIES_CFG = load_species(name=pre.species, path=pre.species_config)
    except ConfigError as e:
        ap.error(str(e))
    known_dests = {a.dest for a in ap._actions}
    unknown = sorted(set(SPECIES_CFG["cli_defaults"]) - known_dests)
    if unknown:
        ap.error(f"{SPECIES_CFG['files']['species']}: cli_defaults has unknown options {unknown}")
    ap.set_defaults(**SPECIES_CFG["cli_defaults"], delay_jitter_ms=SPECIES_CFG["delays"]["jitter_ms"])
    args = ap.parse_args()
    args.species = SPECIES_CFG["species"]
    _cfg_model = SPECIES_CFG["delays"]["model"]
    if args.delay_model is not None and args.delay_model != _cfg_model:
        ap.error(f"--delay-model {args.delay_model} contradicts species `{args.species}` "
                 f"({SPECIES_CFG['files']['species']}), whose delays use `{_cfg_model}` (PLAN.md D2). "
                 f"Drop the flag or use a species config with that delay model.")
    args.delay_model = _cfg_model
    # PLAN.md §7 B1/B2: the sequential half-cycle scheduler computes swing as
    # half_stride - stance, which goes negative above 0.5. Refuse instead of running
    # a broken schedule; the P3 phase scheduler (--gait-scheduler phase) allows it.
    if not 0.0 < float(args.stance_fraction) < 1.0:
        ap.error(f"--stance-fraction must be in (0, 1), got {args.stance_fraction}")
    if (getattr(args, "paced_gait", False) and args.gait_scheduler == "halfcycle"
            and float(args.stance_fraction) > 0.5):
        ap.error(f"--stance-fraction {args.stance_fraction} > 0.5 needs --gait-scheduler phase "
                 f"(the halfcycle scheduler has no double support; PLAN.md Phase 3)")
    try:
        apply_species_constants(SPECIES_CFG["constants"])
    except ConfigError as e:
        ap.error(f"{SPECIES_CFG['files']['species']}: {e}")
    # ---- apply ablation overrides (must happen before connect-time uses these constants) ----
    global W_IA2IN, W_INF2RGE, W_INE2RGF, W_COMM_F_INH, W_COMM_E_INH, LAMBDA
    ablation_tag = []
    if args.ablate_ia_loop:
        W_IA2IN = 0.0
        ablation_tag.append("noIa")
    if args.ablate_asym:
        W_INF2RGE = -28.0   # mean of -48 and -8
        W_INE2RGF = -28.0
        ablation_tag.append("symInh")
    if args.ablate_comm:
        W_COMM_F_INH = 0.0
        W_COMM_E_INH = 0.0
        ablation_tag.append("noComm")
    # STDP learning-rate override (kept distinct from ablation tags)
    if args.stdp_lambda is not None:
        LAMBDA = float(args.stdp_lambda)
    # Graded sensory feedback gain (Courtine/Lavrov toe/air stepping)
    IA_FEEDBACK_GAIN = float(args.ia_feedback_gain)
    # Loading-dependent cutaneous (paw-contact) gain. Scales CUT stance drive;
    # the external Ia-E pacing (stim analogue) is left at full amplitude.
    CUT_FEEDBACK_GAIN = float(args.cut_feedback_gain)
    # MOD_IA_RG_LOADING_GAIN: Ia->RG-E/F weight cap relaxes as cutaneous loading drops,
    # so Ia can only take over more excitatory drive when CUT genuinely can't provide it
    # (see WMAX_IA_UNLOADED above). At full loading (gain=1) this equals --wmax-ia exactly,
    # unchanged from the validated baseline.
    _cut_gain_for_ia_cap = clamp(CUT_FEEDBACK_GAIN, 0.0, 1.0)
    WMAX_IA_BASE = float(getattr(args, "wmax_ia", WMAX_IA))
    WMAX_IA_UNLOADED_EFF = float(getattr(args, "wmax_ia_unloaded", WMAX_IA_UNLOADED))
    EFFECTIVE_WMAX_IA = WMAX_IA_BASE + (WMAX_IA_UNLOADED_EFF - WMAX_IA_BASE) * (1.0 - _cut_gain_for_ia_cap)
    BS_RATE_BASE_HZ = float(args.bs_base_hz)
    BS_NOISE_STD_HZ = float(args.bs_noise_std_hz)
    BS_DRIVE_NORM_HZ = max(BS_RATE_BASE_HZ, 1e-9)
    ENFORCE_TONIC_BS = bool(args.enforce_tonic_bs)
    PACED_GAIT = bool(getattr(args, "paced_gait", False))
    GAIT_SCHEDULER = str(getattr(args, "gait_scheduler", "halfcycle"))  # PLAN.md P3
    # MOD_CUT_FORCE_TRIGGER: closed-loop force-threshold stance detection, replacing
    # the paced-gait clock. Reuses paced-gait's per-leg CUT/Ia-E-group/flexor-afferent
    # wiring, so it can only run on top of --paced-gait.
    CUT_TRIGGER = str(getattr(args, "cut_trigger", "timer"))
    if CUT_TRIGGER == "force" and not PACED_GAIT:
        raise ValueError("--cut-trigger force requires --paced-gait (it reuses its "
                          "per-leg CUT/Ia-E/flexor-afferent wiring).")
    CUT_FORCE_ON_FRAC = float(args.cut_force_on_frac)
    CUT_FORCE_OFF_FRAC = float(args.cut_force_off_frac)
    if not (0.0 < CUT_FORCE_OFF_FRAC < CUT_FORCE_ON_FRAC <= 1.0):
        raise ValueError(f"--cut-force-off-frac ({CUT_FORCE_OFF_FRAC}) must be < "
                          f"--cut-force-on-frac ({CUT_FORCE_ON_FRAC}), both in (0,1].")
    CUT_FORCE_FILTER_TAU_MS = float(getattr(args, "cut_force_filter_tau_ms", 0.0))
    LEADING_LEG = str(getattr(args, "leading_leg", "R"))
    LEAD_OFFSET_MS = float(args.lead_offset_ms)
    CUT_MAX_STANCE_MS = float(args.cut_max_stance_ms)
    CUT_MAX_SWING_MS = float(args.cut_max_swing_ms)
    MUSCLE_FATIGUE = bool(args.muscle_fatigue)
    FATIGUE_TAU_ONSET_MS = float(args.fatigue_tau_onset_ms)
    FATIGUE_TAU_RECOVERY_MS = float(args.fatigue_tau_recovery_ms)
    FATIGUE_MAX_FRAC = float(args.fatigue_max_frac)
    if not (0.0 <= FATIGUE_MAX_FRAC <= 1.0):
        raise ValueError(f"--fatigue-max-frac ({FATIGUE_MAX_FRAC}) must be in [0,1].")
    # MOD_LEG_ASYM: persistent per-leg fatigue-onset asymmetry (0 = symmetric, exact
    # no-op match to every prior run). Leading leg fatigues faster (shorter tau).
    LEG_FATIGUE_ASYM_FRAC = float(getattr(args, "leg_fatigue_asym_frac", 0.0))
    FATIGUE_TAU_ONSET_MS_BY_SIDE = {
        side: FATIGUE_TAU_ONSET_MS * (1.0 - LEG_FATIGUE_ASYM_FRAC if side == LEADING_LEG
                                       else 1.0 + LEG_FATIGUE_ASYM_FRAC)
        for side in LEGS
    }
    # MOD_CONSOLIDATE: tag-and-capture consolidation, scoped to --cut-trigger force
    # (the only mode with a genuine-vs-failsafe-forced bout-boundary signal).
    CONSOLIDATE = bool(getattr(args, "consolidate", False))
    if CONSOLIDATE and CUT_TRIGGER != "force":
        raise ValueError("--consolidate requires --cut-trigger force (it gates "
                          "capture on that mode's genuine-vs-failsafe-forced "
                          "bout-boundary classification, which does not exist "
                          "in timer/paced-gait mode).")
    CONSOLIDATE_TAU_TAG_MS = float(getattr(args, "consolidate_tau_tag_ms", 2000.0))
    CONSOLIDATE_PRP_THRESHOLD = float(getattr(args, "consolidate_prp_threshold", 1.0))
    CONSOLIDATE_PRP_GAIN_GENUINE = float(getattr(args, "consolidate_prp_gain_genuine", 0.20))
    CONSOLIDATE_PRP_GAIN_FORCED = float(getattr(args, "consolidate_prp_gain_forced", 0.15))
    # MOD_WMAX_GROWTH: 0.0 default = exact no-op (Wmax never changes after init, same
    # as every prior --consolidate run).
    CONSOLIDATE_WMAX_IA_GROWTH = float(getattr(args, "consolidate_wmax_ia_growth_per_capture", 0.0))
    CONSOLIDATE_WMAX_IA_CEILING = float(getattr(args, "consolidate_wmax_ia_ceiling", 60.0))
    # ---- sweep mode (Option C): run one (mu, CV) pair per Slurm array task ----
    def _parse_pairs(s: str):
        s = (s or "").strip()
        if not s:
            return []
        out = []
        for item in s.split(","):
            item = item.strip()
            if not item:
                continue
            if ":" not in item:
                raise ValueError(f"Bad --sweep-pairs item '{item}'. Expected mu:cv.")
            mu_s, cv_s = item.split(":", 1)
            out.append((float(mu_s), float(cv_s)))
        return out

    sweep_pairs = _parse_pairs(getattr(args, "sweep_pairs", ""))
    sweep_active = len(sweep_pairs) > 0

    sweep_idx = int(getattr(args, "sweep_run_idx", -1))
    if sweep_active and sweep_idx < 0:
        if "SLURM_ARRAY_TASK_ID" in os.environ:
            sweep_idx = int(os.environ.get("SLURM_ARRAY_TASK_ID", "0"))
        else:
            sweep_idx = 0

    sweep_mu = None
    sweep_cv = None
    sweep_sigma = None
    run_seed = int(getattr(args, "seed", 12345))

    if sweep_active:
        if sweep_idx < 0 or sweep_idx >= len(sweep_pairs):
            raise ValueError(f"--sweep-run-idx={sweep_idx} out of range for {len(sweep_pairs)} pairs")
        sweep_mu, sweep_cv = sweep_pairs[sweep_idx]
        sweep_sigma = float(sweep_cv) * float(sweep_mu)

        # Deterministic per-index seed offset (reduces accidental correlations across tasks)
        run_seed = int(getattr(args, "seed", 12345)) + int(sweep_idx) * 10007

        # Auto-name output unless user explicitly set --out to something other than the default
        outdir = str(getattr(args, "outdir", "."))
        tag = str(getattr(args, "tag", "cpg"))
        run_name = str(getattr(args, "run_name", "")).strip()

        if run_name:
            base = run_name
        else:
            base = f"cpg_{tag}_idx{sweep_idx:02d}_mu{sweep_mu:05.2f}_cv{sweep_cv:05.2f}_seed{run_seed}"

        if not base.endswith(".h5"):
            base += ".h5"

        if str(getattr(args, "out", "")).strip() in ("", "cpg_run.h5"):
            args.out = os.path.join(outdir, base)

        # In sweep mode, override STDP init params to match (mu, CV)
        sweep_dist = str(getattr(args, "sweep_dist", "lognormal_cv")).lower().strip()
        if sweep_dist == "const":
            args.stdp_winit_dist = "const"
            args.stdp_winit_mean = float(sweep_mu)
            args.stdp_winit_std = 0.0
        elif sweep_dist == "normal":
            args.stdp_winit_dist = "normal"
            args.stdp_winit_mean = float(sweep_mu)
            args.stdp_winit_std = float(sweep_sigma)  # std in weight units
        elif sweep_dist == "lognormal":
            # Legacy: args.stdp_winit_std is interpreted as underlying-normal sigma
            args.stdp_winit_dist = "lognormal"
            args.stdp_winit_mean = float(sweep_mu)
        else:
            # lognormal_cv: args.stdp_winit_std is interpreted as CV (std/mean)
            args.stdp_winit_dist = "lognormal_cv"
            args.stdp_winit_mean = float(sweep_mu)
            args.stdp_winit_std = float(sweep_cv)

    # B12 (PLAN.md §7): seed numpy in every mode. Previously only sweep mode seeded it,
    # so non-sweep runs (e.g. rat-sh/run_frozen.sh) drew BS spike offsets/jitter unseeded.
    # Sweep mode is unchanged: same seed value, same point in the RNG stream.
    np.random.seed(run_seed)
    # --- STDP randomized initial weights helper ---
    def make_stdp_init_weight_param(dist: str, mean_w: float, std_w: float, wmin: float, wmax: float):
        """Return either a scalar or a NEST Parameter for per-connection initial weights.

        Bio-plausible default: lognormal (positive, heavy-tailed). We enforce bounds using
        clipping (not redraw) for speed and reliability during Connect.

        Notes:
          - For `normal`: std_w is in weight units.
          - For `lognormal`: std_w is sigma of the underlying normal distribution.
            We choose mu so that E[w] ~= mean_w (before redraw/clipping): mu = ln(mean_w) - 0.5*sigma^2.
          - For `lognormal_cv`: std_w is interpreted as CV in weight space (std/mean). We convert CV->sigma via sigma = sqrt(log(1+CV^2)) and choose mu so E[w] ~= mean_w.
        """
        dist = str(dist).lower().strip()
        mean_w = float(mean_w)
        std_w = float(std_w)
        wmin = float(wmin)
        wmax = float(wmax)

        if dist == "const":
            return float(mean_w)

        if dist == "normal":
            p = nest.random.normal(mean=mean_w, std=max(1e-12, std_w))

        elif dist == "lognormal_cv":
            # std_w is CV in weight space; convert to underlying-normal sigma
            if mean_w <= 0.0:
                return float(wmin)
            cv = max(0.0, std_w)
            sigma = float(np.sqrt(np.log(1.0 + cv * cv)))
            mu = float(np.log(max(1e-12, mean_w)) - 0.5 * sigma * sigma)

            p = None
            try:
                p = nest.random.lognormal(mu=mu, sigma=max(1e-12, sigma))
            except Exception:
                try:
                    p = nest.random.lognormal(mean=mu, std=max(1e-12, sigma))
                except Exception:
                    try:
                        p = nest.random.lognormal(mean=mean_w, std=max(1e-12, sigma))
                    except Exception:
                        return float(mean_w)

        elif dist == "lognormal":
            # IMPORTANT: NEST's lognormal parameterization can vary by version.
            # We try the underlying-normal (mu/sigma) form first, then fall back.
            if mean_w <= 0.0:
                return float(wmin)

            sigma = max(1e-12, std_w)
            mu = float(np.log(max(1e-12, mean_w)) - 0.5 * sigma * sigma)

            p = None
            try:
                # Newer-style / explicit parameterization
                p = nest.random.lognormal(mu=mu, sigma=sigma)
            except Exception:
                try:
                    # Older-style signature might still accept mean/std keywords
                    p = nest.random.lognormal(mean=mu, std=sigma)
                except Exception:
                    try:
                        # Last resort: interpret args as mean/std of the *lognormal* itself
                        p = nest.random.lognormal(mean=mean_w, std=sigma)
                    except Exception:
                        return float(mean_w)

        else:
            # Safe fallback
            return float(mean_w)

        # Enforce biologically sensible bounds without redraw (redraw can crash during Connect)
        # We prefer hard clipping via NEST math combinators so weight sampling never retries.
        if wmin > -np.inf or wmax < np.inf:
            try:
                # Try a dedicated clip if available (version-dependent)
                if hasattr(nest.math, "clip"):
                    p = nest.math.clip(p, min=wmin, max=wmax)
                else:
                    # Generic: p <- min(max(p, wmin), wmax)
                    if wmin > -np.inf:
                        p = nest.math.max(p, wmin)
                    if wmax < np.inf:
                        p = nest.math.min(p, wmax)
            except Exception:
                # As a last resort, skip bounding rather than failing the run
                pass

        return p

    # --- NEST verbosity (reduce log spam / slurmout I/O) ---
    try:
        nest.set_verbosity(str(args.nest_verbosity))
    except Exception:
        # Fall back silently if verbosity string is not supported
        pass

    # --- Long-run mode: reduce Python<->NEST overhead and weight sampling cost ---
    # For long simulations, the dominant cost is often weight sampling (GetStatus on many connections).
    # Long-run mode shifts toward "trend" logging rather than high-frequency snapshots.
    if args.long_run:
        # Coarser outer chunking reduces the number of nest.Simulate() calls.
        if args.simulate_chunk_ms < 100.0:
            args.simulate_chunk_ms = 100.0
        # Coarser rate updates reduce frequent SetStatus calls.
        if args.rate_update_ms < 100.0:
            args.rate_update_ms = 100.0
        # Coarser weight sampling for trend plots.
        if args.weight_sample_ms < 1000.0:
            args.weight_sample_ms = 1000.0
        # Default weight downsampling (if not explicitly set)
        if int(args.max_weight_conns) <= 0:
            args.max_weight_conns = 2000
        # Reduce progress print cadence (in steps) so output doesn't grow too much.
        if args.print_every < 200:
            args.print_every = 200

    SIM_MS = float(args.sim_ms)
    DT_MS = float(args.dt_ms)
    PHASE_MS = SIM_MS / int(N_PHASES)

    # We will call nest.Simulate() in larger chunks to reduce overhead.
    CHUNK_MS = float(args.simulate_chunk_ms)
    RES_MS = float(args.resolution_ms)

    def q_ms(x: float) -> float:
        """Quantize time to an integer multiple of the NEST resolution."""
        if RES_MS <= 0.0:
            return float(x)
        steps = int(round(float(x) / RES_MS))
        return steps * RES_MS

    # Ensure chunk is a clean multiple of resolution
    CHUNK_MS = q_ms(CHUNK_MS)
    if CHUNK_MS <= 0.0:
        raise ValueError(f"--simulate-chunk-ms quantized to {CHUNK_MS}, choose a larger value.")

    if CHUNK_MS < DT_MS:
        raise ValueError(f"--simulate-chunk-ms ({CHUNK_MS}) must be >= --dt-ms ({DT_MS}).")

    # Convert sampling cadences (ms) into "chunk steps"
    weight_every = max(1, int(round(float(args.weight_sample_ms) / CHUNK_MS)))
    rate_every = max(1, int(round(float(args.rate_update_ms) / CHUNK_MS)))

    # ---- MOD_PACED_GAIT: explicit 1-s trot cycle constants ----
    if PACED_GAIT:
        STEP_PERIOD_MS = q_ms(float(args.step_period_ms))   # full stride (both legs)
        STANCE_FRAC    = float(args.stance_fraction)         # fraction of full stride in stance
        HALF_MS        = q_ms(STEP_PERIOD_MS / 2.0)         # per half-cycle (one leg's turn = 500ms)
        STANCE_MS      = q_ms(STEP_PERIOD_MS * STANCE_FRAC) # stance duration per leg (= 500ms @ FRAC=0.5)
        SWING_MS       = q_ms(HALF_MS - STANCE_MS)          # residual swing window within half-cycle
        N_IA_GROUPS_PACED = int(args.n_ia_groups)
        IA_EXT_HZ      = list(args.ia_ext_hz)
        while len(IA_EXT_HZ) < N_IA_GROUPS_PACED:
            IA_EXT_HZ.append(float(IA_EXT_HZ[-1]))
        IA_EXT_F_HZ    = float(args.ia_ext_f_hz)   # MOD_FLEXOR_AFFERENT swing drive
        # Each Ia sub-group window = stance duration / n_groups (e.g. 500/3 ≈ 167ms)
        SUB_STANCE_MS  = q_ms(STANCE_MS / max(1, N_IA_GROUPS_PACED))
        n_half_cycles  = max(2, int(np.ceil(SIM_MS / HALF_MS)))
        # Longer time constants for smooth 500ms force plateaus (was tuned for ~150ms cycles)
        TAU_ACT_RISE_MS   = PACED_TAU_ACT_RISE_MS
        TAU_ACT_DECAY_MS  = PACED_TAU_ACT_DECAY_MS
        TAU_FORCE_RISE_MS = PACED_TAU_FORCE_RISE_MS
        TAU_FORCE_DECAY_MS = PACED_TAU_FORCE_DECAY_MS

    nest.ResetKernel()
    # B12 (PLAN.md §7): --seed must reach NEST. Before this, rng_seed was never set,
    # so every run used NEST's default (143202461) and "different seeds" shared the
    # same Poisson noise, NEST-drawn weight init and delay jitter. NEST's valid range
    # is [1, 2**32 - 1].
    NEST_RNG_SEED = int(run_seed) % (2**32 - 1) or 1
    nest.SetKernelStatus(
        {"resolution": float(args.resolution_ms), "local_num_threads": int(args.threads), "print_time": False,
         "rng_seed": NEST_RNG_SEED})

    # ---- delay parameters (must be created AFTER kernel config) ----
    # Delay model and per-path table come from the species config (PLAN.md P1, D2);
    # FLEXOR_BS_GAIN (MOD_FLEXBOOST) was already set from it by apply_species_constants().
    delay_model = str(args.delay_model)
    delay_paths = SPECIES_CFG["delays"]["paths"]
    delay_jitter_ms = float(getattr(args, "delay_jitter_ms", 0.0))
    delay_scale = float(getattr(args, "delay_scale", 1.0))

    delay = {
        "cut_to_rg": make_delay_param(delay_model, delay_paths, "cut_to_rg",
                                      fallback_ms=DELAY_MS, res_ms=RES_MS,
                                      jitter_ms=delay_jitter_ms, delay_scale=delay_scale),
        "bs_to_rg": make_delay_param(delay_model, delay_paths, "bs_to_rg",
                                     fallback_ms=DELAY_MS, res_ms=RES_MS,
                                     jitter_ms=delay_jitter_ms, delay_scale=delay_scale),
        "base_to_rg": make_delay_param(delay_model, delay_paths, "base_to_rg",
                                       fallback_ms=DELAY_MS, res_ms=RES_MS,
                                       jitter_ms=delay_jitter_ms, delay_scale=delay_scale),
        "rg_to_m": make_delay_param(delay_model, delay_paths, "rg_to_m",
                                    fallback_ms=DELAY_MS, res_ms=RES_MS,
                                    jitter_ms=delay_jitter_ms, delay_scale=delay_scale),
        "m_to_mus": make_delay_param(delay_model, delay_paths, "m_to_mus",
                                     fallback_ms=DELAY_MS, res_ms=RES_MS,
                                     jitter_ms=delay_jitter_ms, delay_scale=delay_scale),
        "ia_path": make_delay_param(delay_model, delay_paths, "ia_path",
                                    fallback_ms=DELAY_MS, res_ms=RES_MS,
                                    jitter_ms=delay_jitter_ms, delay_scale=delay_scale),
        "rg_rec": make_delay_param(delay_model, delay_paths, "rg_rec",
                                   fallback_ms=DELAY_MS, res_ms=RES_MS,
                                   jitter_ms=delay_jitter_ms, delay_scale=delay_scale),
        "rg_recip": make_delay_param(delay_model, delay_paths, "rg_recip",
                                     fallback_ms=DELAY_RECIP_MS, res_ms=RES_MS,
                                     jitter_ms=delay_jitter_ms, delay_scale=delay_scale),
        "motor_e2f": make_delay_param(delay_model, delay_paths, "motor_e2f",
                                      fallback_ms=DELAY_MOTOR_RECIP_E2F_MS, res_ms=RES_MS,
                                      jitter_ms=delay_jitter_ms, delay_scale=delay_scale),
        "motor_f2e": make_delay_param(delay_model, delay_paths, "motor_f2e",
                                      fallback_ms=DELAY_MOTOR_RECIP_F2E_MS, res_ms=RES_MS,
                                      jitter_ms=delay_jitter_ms, delay_scale=delay_scale),
        "commissural": make_delay_param(delay_model, delay_paths, "commissural",
                                        fallback_ms=DELAY_COMM_MS, res_ms=RES_MS,
                                        jitter_ms=delay_jitter_ms, delay_scale=delay_scale),
    }
    # PLAN.md P2: intraspinal Ia-interneuron -> antagonist motoneuron hop. It used
    # delay["ia_path"] (the afferent conduction delay) before; split so human-scale
    # afferent delays do not also slow one-segment reciprocal inhibition.
    # NEST quirk (verified): two *separate* but identical random-delay Parameter objects
    # draw differently from one shared object -- even connection counts change. So when
    # the species gives ia_int_to_m exactly the ia_path values (rat), reuse that object;
    # this keeps rat output byte-identical (./regress.sh).
    _pk = lambda k: tuple(sorted((delay_paths.get(k) or {}).items()))
    if delay_model == "fixed" or _pk("ia_int_to_m") == _pk("ia_path"):
        delay["ia_int_to_m"] = delay["ia_path"]
    else:
        delay["ia_int_to_m"] = make_delay_param(delay_model, delay_paths, "ia_int_to_m",
                                                fallback_ms=DELAY_MS, res_ms=RES_MS,
                                                jitter_ms=delay_jitter_ms, delay_scale=delay_scale)

    # Ensure output directory exists (especially for sweep auto-naming)
    try:
        out_dirname = os.path.dirname(str(args.out))
        if out_dirname:
            os.makedirs(out_dirname, exist_ok=True)
    except Exception:
        pass

    # IMPORTANT (NEST safety): Create random Parameter objects only after the kernel is configured.
    # Creating Parameters before setting threads/virtual processes can cause incorrect behavior or segfaults.
    W_INIT_CUT = make_stdp_init_weight_param(
        args.stdp_winit_dist,
        args.stdp_winit_mean,
        args.stdp_winit_std,
        args.stdp_winit_min,
        min(float(args.stdp_winit_max), float(WMAX)),
    )

    W_INIT_BS = make_stdp_init_weight_param(
        args.stdp_winit_dist,
        float(args.stdp_winit_mean) * float(getattr(args, "stdp_winit_bs_mean_mul", 1.0)),
        float(args.stdp_winit_std) * float(getattr(args, "stdp_winit_bs_std_mul", 1.0)),
        args.stdp_winit_min,
        min(float(args.stdp_winit_max), float(WMAX)),
    )

    # MOD_IA_RG_STDP: initial weight for the plastic Ia->RG projection. Starts at the
    # base lognormal init (like CUT) and potentiates up under STDP. Clamped against the
    # loading-adjusted EFFECTIVE_WMAX_IA (MOD_IA_RG_LOADING_GAIN), not the raw --wmax-ia.
    W_INIT_IA = make_stdp_init_weight_param(
        args.stdp_winit_dist,
        args.stdp_winit_mean,
        args.stdp_winit_std,
        args.stdp_winit_min,
        min(float(args.stdp_winit_max), EFFECTIVE_WMAX_IA),
    )

    # Robust rank/proc detection:
    # - under Slurm, SLURM_PROCID/SLURM_NTASKS are the most reliable
    # - otherwise, fall back to NEST helpers if present
    if "SLURM_PROCID" in os.environ:
        rank = int(os.environ.get("SLURM_PROCID", "0"))
        nproc = int(os.environ.get("SLURM_NTASKS", "1"))
    else:
        rank = getattr(nest, "Rank", lambda: 0)()
        nproc = getattr(nest, "NumProcesses", lambda: 1)()

    if rank == 0 and ("sweep_active" in locals()) and sweep_active:
        print(f"[Sweep] active=True idx={sweep_idx} mu={sweep_mu} cv={sweep_cv} sigma={sweep_sigma} dist={args.stdp_winit_dist} seed={run_seed}")
        print(f"[Sweep] out={args.out}")

    if rank == 0:
        print(f"[NEST] processes={nproc} | local_threads={nest.GetKernelStatus('local_num_threads')}")
        print(
            f"[Run] sim_ms={SIM_MS} dt_ms={DT_MS} chunk_ms={CHUNK_MS} resolution_ms={float(args.resolution_ms)} phases={N_PHASES} phase_ms={PHASE_MS:.2f}")
        print(
            f"[STDP init] dist={args.stdp_winit_dist} "
            f"CUT(mean={args.stdp_winit_mean}, std={args.stdp_winit_std}) "
            f"BS(mean={float(args.stdp_winit_mean)*float(getattr(args,'stdp_winit_bs_mean_mul',1.0))}, "
            f"std={float(args.stdp_winit_std)*float(getattr(args,'stdp_winit_bs_std_mul',1.0))}) "
            f"min={args.stdp_winit_min} max={min(float(args.stdp_winit_max), float(WMAX))}"
        )
        if PACED_GAIT and GAIT_SCHEDULER == "phase" and CUT_TRIGGER != "force":
            print(f"[PHASE-GAIT] stride={STEP_PERIOD_MS:.0f}ms  stance={STEP_PERIOD_MS * STANCE_FRAC:.0f}ms "
                  f"({STANCE_FRAC:.2f})  double support={max(0.0, 2.0 * STANCE_FRAC - 1.0) * 100:.0f}% of stride  "
                  f"n_ia_groups={N_IA_GROUPS_PACED}  ia_ext_hz={IA_EXT_HZ}")
        elif PACED_GAIT:
            print(f"[PACED-GAIT] step_period={STEP_PERIOD_MS:.0f}ms  half={HALF_MS:.0f}ms  "
                  f"stance={STANCE_MS:.0f}ms  swing={SWING_MS:.0f}ms  "
                  f"n_ia_groups={N_IA_GROUPS_PACED}  sub_stance={SUB_STANCE_MS:.1f}ms  "
                  f"ia_ext_hz={IA_EXT_HZ}  n_half_cycles={n_half_cycles}")
            print(f"[PACED-GAIT] TAU_ACT={TAU_ACT_RISE_MS}/{TAU_ACT_DECAY_MS}ms  "
                  f"TAU_FORCE={TAU_FORCE_RISE_MS}/{TAU_FORCE_DECAY_MS}ms")

    # ---- MOD_DEBUG_SMALL: small-N + low-BS debug mode for fast local iteration ----
    if args.debug_small:
        global N_CUT, N_BS, N_RG_E, N_RG_F, N_MOTOR_E, N_MOTOR_F
        global N_MUS_E, N_MUS_F, N_IA_E, N_IA_F, N_IA_INT, N_INE, N_INF
        global BS_REGULAR_HZ
        N_CUT = 30
        N_BS  = 30
        N_RG_E = 40
        N_RG_F = 40
        N_MOTOR_E = 30
        N_MOTOR_F = 30
        N_MUS_E = 30
        N_MUS_F = 30
        N_IA_E = 30
        N_IA_F = 30
        N_IA_INT = 20
        N_INE = 20  # E→F pathway: keep sparse (preserves F's rhythm-leading role; doubling hurt correlation)
        N_INF = 40  # F→E pathway: doubled for adequate RGE silencing during F burst at small N
        BS_REGULAR_HZ = 20.0
        if rank == 0:
            print("=" * 64)
            print("[DEBUG-SMALL] Local fast-iteration mode active")
            print(f"  N_RG=({N_RG_E},{N_RG_F})  N_CUT={N_CUT}  N_BS={N_BS}")
            print(f"  N_MOTOR=({N_MOTOR_E},{N_MOTOR_F})  N_MUS=({N_MUS_E},{N_MUS_F})")
            print(f"  N_IA=({N_IA_E},{N_IA_F})  N_IA_INT={N_IA_INT}  N_IN=({N_INE},{N_INF})")
            print(f"  BS_REGULAR_HZ={BS_REGULAR_HZ} Hz (was 60)")
            print("  Rhythm now relies on Ia → In → RG closed-loop instead of BS drive.")
            print("=" * 64)

    # ---- build per-leg ----
    leg = {}
    for side in LEGS:
        cut_pg = nest.Create("poisson_generator", N_CUT)
        cut_in = nest.Create("parrot_neuron", N_CUT)
        nest.Connect(cut_pg, cut_in, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(cut_pg, {"rate": CUT_RATE_OFF_HZ})

        bs_pg_e = nest.Create("spike_generator", N_BS)  # MOD_BS_REGULAR200: replace Poisson with regular spike generators
        bs_in_e = nest.Create("parrot_neuron", N_BS)
        nest.Connect(bs_pg_e, bs_in_e, conn_spec={"rule": "one_to_one"})

        bs_pg_f = nest.Create("spike_generator", N_BS)  # MOD_BS_REGULAR200
        bs_in_f = nest.Create("parrot_neuron", N_BS)
        nest.Connect(bs_pg_f, bs_in_f, conn_spec={"rule": "one_to_one"})

        # MOD_TONIC_BS: constant tonic drive throughout simulation — no sinusoidal gating.
        # Both bs_pg_e and bs_pg_f fire identically on both legs at BS_REGULAR_HZ.
        # L/R and E/F alternation must emerge from spinal CPG (commissural + reciprocal inh).
        period_ms = 1000.0 / float(BS_REGULAR_HZ)
        base_times = np.arange(RES_MS, SIM_MS + 1e-9, period_ms)  # avoid t=0 (NEST forbids)

        if BS_REGULAR_DESYNC == "random":
            offsets = np.random.uniform(0.0, period_ms, size=int(N_BS))
        else:
            offsets = np.linspace(0.0, period_ms, int(N_BS), endpoint=False)

        times_e = []
        times_f = []
        for off in offsets:
            t_arr = base_times + float(off)  # all spikes; no phase filter
            if BS_REGULAR_JITTER_MS > 0.0:
                j = float(BS_REGULAR_JITTER_MS)
                t_arr = np.clip(t_arr + np.random.uniform(-j, j, size=t_arr.shape), RES_MS, SIM_MS)
                t_arr = np.round(t_arr / RES_MS) * RES_MS  # snap to NEST resolution
                t_arr = t_arr[t_arr >= RES_MS]             # NEST forbids t=0
                t_arr = np.unique(np.sort(t_arr))
            times_e.append(t_arr.tolist())
            times_f.append(t_arr.tolist())  # E and F are identical: tonic

        nest.SetStatus(bs_pg_e, [{"spike_times": st} for st in times_e])  # MOD_BS_REGULAR200
        nest.SetStatus(bs_pg_f, [{"spike_times": st} for st in times_f])  # MOD_BS_REGULAR200

        base_pg = nest.Create("poisson_generator", N_BS)
        base_in = nest.Create("parrot_neuron", N_BS)
        nest.Connect(base_pg, base_in, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(base_pg, {"rate": BASE_DRIVE_HZ})

        ia_pg_e = nest.Create("poisson_generator", N_IA_E)
        ia_in_e = nest.Create("parrot_neuron", N_IA_E)
        nest.Connect(ia_pg_e, ia_in_e, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(ia_pg_e, {"rate": IA_BASE_HZ})

        ia_pg_f = nest.Create("poisson_generator", N_IA_F)
        ia_in_f = nest.Create("parrot_neuron", N_IA_F)
        nest.Connect(ia_pg_f, ia_in_f, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(ia_pg_f, {"rate": IA_BASE_HZ})

        # MOD_PACED_GAIT: external sequential Ia-E groups (heel→mid→toe)
        ia_ext_pg_e_groups = []
        ia_ext_in_e_groups = []
        if PACED_GAIT:
            n_per = max(1, N_IA_E // N_IA_GROUPS_PACED)
            for _ in range(N_IA_GROUPS_PACED):
                pg = nest.Create("poisson_generator", n_per)
                pn = nest.Create("parrot_neuron", n_per)
                nest.Connect(pg, pn, conn_spec={"rule": "one_to_one"})
                nest.SetStatus(pg, {"rate": 0.0})
                ia_ext_pg_e_groups.append(pg)
                ia_ext_in_e_groups.append(pn)

        # MOD_FLEXOR_AFFERENT: external flexor swing-afferent (hip/flexor-stretch
        # signal that drives the swing-phase flexor burst; Grillner & Rossignol
        # 1978; Pearson 1995). A single phasic group active during swing,
        # mirroring the stance Ia-E ramp; drives InF → reinforces the flexor.
        ia_ext_pg_f = None
        if PACED_GAIT and IA_EXT_F_HZ > 0.0:
            ia_ext_pg_f = nest.Create("poisson_generator", N_IA_F)
            nest.SetStatus(ia_ext_pg_f, {"rate": 0.0})

        rg_e = nest.Create("izhikevich", N_RG_E)
        rg_f = nest.Create("izhikevich", N_RG_F)
        m_e = nest.Create("izhikevich", N_MOTOR_E)
        m_f = nest.Create("izhikevich", N_MOTOR_F)
        # Record RG population spiking to compute population rates (like muscle relay rates)
        rec_rge = nest.Create("spike_recorder")
        rec_rgf = nest.Create("spike_recorder")
        nest.Connect(rg_e, rec_rge)
        nest.Connect(rg_f, rec_rgf)
        # Interneurons
        ia_int_e = nest.Create("izhikevich", N_IA_INT)  # inhibitory
        ia_int_f = nest.Create("izhikevich", N_IA_INT)  # inhibitory
        in_e = nest.Create("izhikevich", N_INE)  # inhibitory
        in_f = nest.Create("izhikevich", N_INF)  # inhibitory
        # MOD_NET_RECORD: spike recorders for the interneuron populations so the
        # combined network-activity figure can show the whole circuit (Zhang-style).
        rec_ine = nest.Create("spike_recorder");  nest.Connect(in_e, rec_ine)
        rec_inf = nest.Create("spike_recorder");  nest.Connect(in_f, rec_inf)
        rec_iainte = nest.Create("spike_recorder"); nest.Connect(ia_int_e, rec_iainte)
        rec_iaintf = nest.Create("spike_recorder"); nest.Connect(ia_int_f, rec_iaintf)
        for pop in (rg_e, rg_f, m_e, m_f):
            nest.SetStatus(pop, izh_params)
        for pop in (ia_int_e, ia_int_f, in_e, in_f):
            nest.SetStatus(pop, izh_inh_params)
        bias = (+LEFT_RIGHT_BIAS_IE if side == "L" else -LEFT_RIGHT_BIAS_IE)
        nest.SetStatus(rg_e, {"V_m": -65.0, "U_m": 0.2 * (-65.0), "I_e": I_E_RGE})  # MOD_FIG10
        nest.SetStatus(rg_f, {"a": RGF_A, "b": RGF_B, "c": RGF_C, "d": RGF_D,
                              "V_m": -65.0, "U_m": RGF_B * (-65.0), "I_e": I_E_RGF + bias})  # slight L/R bias breaks perfect synchrony
        nest.SetStatus(m_e, {"V_m": -65.0, "U_m": 0.2 * (-65.0), "I_e": I_E_MOTOR})
        nest.SetStatus(m_f, {"V_m": -65.0, "U_m": 0.2 * (-65.0), "I_e": I_E_MOTOR})

        mus_e = nest.Create("parrot_neuron", N_MUS_E)
        mus_f = nest.Create("parrot_neuron", N_MUS_F)
        rec_muse = nest.Create("spike_recorder")
        rec_musf = nest.Create("spike_recorder")
        nest.Connect(mus_e, rec_muse)
        nest.Connect(mus_f, rec_musf)

        leg[side] = dict(
            cut_pg=cut_pg, cut_in=cut_in,
            bs_pg_e=bs_pg_e, bs_in_e=bs_in_e,
            bs_pg_f=bs_pg_f, bs_in_f=bs_in_f,
            base_pg=base_pg, base_in=base_in,
            ia_pg_e=ia_pg_e, ia_in_e=ia_in_e,
            ia_pg_f=ia_pg_f, ia_in_f=ia_in_f,
            ia_ext_pg_e=ia_ext_pg_e_groups,   # MOD_PACED_GAIT: list of sequential Ia-E groups
            ia_ext_pg_f=ia_ext_pg_f,          # MOD_FLEXOR_AFFERENT: swing flexor afferent (or None)
            rg_e=rg_e, rg_f=rg_f, m_e=m_e, m_f=m_f,
            ia_int_e=ia_int_e, ia_int_f=ia_int_f, in_e=in_e, in_f=in_f,
            mus_e=mus_e, mus_f=mus_f,
            rec_muse=rec_muse, rec_musf=rec_musf,
            rec_rge=rec_rge, rec_rgf=rec_rgf,
            rec_ine=rec_ine, rec_inf=rec_inf,
            rec_iainte=rec_iainte, rec_iaintf=rec_iaintf
        )

    # ---- STDP models ----
    stdp_defaults = {
        "tau_plus": TAU_PLUS,
        "lambda": LAMBDA,
        "alpha": ALPHA,
        "mu_plus": MU_PLUS,
        "mu_minus": MU_MINUS,
        "Wmax": WMAX,
    }
    # MOD_COACT: BS STDP models use WMAX_BS so tonic BS weights cannot potentiate high
    # enough to drive RGE alone even after extended training.
    stdp_bs_defaults = {**stdp_defaults, "Wmax": WMAX_BS}

    for side in LEGS:
        def copy(name, params, wr):
            if wr is not None:
                nest.CopyModel("stdp_synapse", name, {**params, "weight_recorder": wr})
            else:
                nest.CopyModel("stdp_synapse", name, params)

        copy(f"stdp_cut_rge_{side}", stdp_defaults, make_weight_recorder_safe())
        copy(f"stdp_bs_rge_{side}", stdp_bs_defaults, make_weight_recorder_safe())   # MOD_COACT: capped Wmax
        copy(f"stdp_bs_rgf_{side}", stdp_bs_defaults, make_weight_recorder_safe())   # MOD_COACT: capped Wmax
        # MOD_IA_RG_STDP: plastic homonymous Ia->RG models, always created -- the third
        # standing plastic pathway alongside BS->RG and CUT->RG, matching the reference
        # architecture's direct Ia->RG-E/F excitatory projection. Wmax is the
        # loading-adjusted EFFECTIVE_WMAX_IA (MOD_IA_RG_LOADING_GAIN), not the raw
        # --wmax-ia -- relaxes as --cut-feedback-gain drops.
        stdp_ia_defaults = {**stdp_defaults, "Wmax": float(EFFECTIVE_WMAX_IA)}
        copy(f"stdp_ia_rge_{side}", stdp_ia_defaults, make_weight_recorder_safe())
        copy(f"stdp_ia_rgf_{side}", stdp_ia_defaults, make_weight_recorder_safe())

    # ---- connect per leg ----
    for side in LEGS:
        L = leg[side]

        nest.Connect(L["cut_in"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": f"stdp_cut_rge_{side}", "weight": W_INIT_CUT, "delay": delay["cut_to_rg"]})

        # MOD_COACT: static CUT → RGE pathway — present from t=0 before STDP bootstraps.
        # CUT 100 Hz × W=14 × ~35 conns alone is subthreshold; combined with BS 60 Hz it
        # crosses threshold (bio-plausible co-activation gate for rat CPG).
        # --cut-static-w sets the weight; default 0 drops the pathway (single plastic CUT).
        _cut_static_w = float(getattr(args, "cut_static_w", 0.0))
        if _cut_static_w != 0.0:
            nest.Connect(L["cut_in"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_CUT2RGE_STATIC},
                         syn_spec={"synapse_model": "static_synapse", "weight": _cut_static_w, "delay": delay["cut_to_rg"]})

        # MOD_FREEZE_BS: with --freeze-bs-rg these are static (no STDP), held at the weak
        # lognormal init so BS is a fixed tonic drive and the learning shifts to Ia->RG.
        _bs_rge_model = "static_synapse" if getattr(args, "freeze_bs_rg", False) else f"stdp_bs_rge_{side}"
        _bs_rgf_model = "static_synapse" if getattr(args, "freeze_bs_rg", False) else f"stdp_bs_rgf_{side}"
        nest.Connect(L["bs_in_e"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": _bs_rge_model, "weight": W_INIT_BS, "delay": delay["bs_to_rg"]})
        nest.Connect(L["bs_in_f"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": _bs_rgf_model, "weight": W_INIT_BS, "delay": delay["bs_to_rg"]})

        nest.Connect(L["base_in"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": BASE_DRIVE_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": BASE_DRIVE_W, "delay": delay["base_to_rg"]})
        nest.Connect(L["base_in"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": BASE_DRIVE_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": BASE_DRIVE_W, "delay": delay["base_to_rg"]})

        nest.Connect(L["rg_e"], L["m_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": "static_synapse", "weight": W0_RM, "delay": delay["rg_to_m"]})
        nest.Connect(L["rg_f"], L["m_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": "static_synapse", "weight": W0_RM, "delay": delay["rg_to_m"]})

        # Motor-pool reciprocal inhibition (helps enforce E/F alternation)
        nest.Connect(L["m_e"], L["m_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_MOTOR_RECIP},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_MOTOR_RECIP,
                               "delay": delay["motor_e2f"]})
        nest.Connect(L["m_f"], L["m_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_MOTOR_RECIP},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_MOTOR_RECIP,
                               "delay": delay["motor_f2e"]})

        nest.Connect(L["m_e"], L["mus_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_M2MUS},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_M2MUS, "delay": delay["m_to_mus"]})
        nest.Connect(L["m_f"], L["mus_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_M2MUS},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_M2MUS, "delay": delay["m_to_mus"]})

        # Ia afferent pathways via inhibitory interneurons:
        # - Ia from extensor inhibits flexor motor pool
        # - Ia from flexor inhibits extensor motor pool
        nest.Connect(L["ia_in_e"], L["ia_int_e"], conn_spec={"rule": "pairwise_bernoulli", "p": IA2RG_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_IA_IN2INT, "delay": delay["ia_path"]})
        nest.Connect(L["ia_int_e"], L["m_f"], conn_spec={"rule": "pairwise_bernoulli", "p": IA2RG_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_IA_INT2ANT, "delay": delay["ia_int_to_m"]})

        nest.Connect(L["ia_in_f"], L["ia_int_f"], conn_spec={"rule": "pairwise_bernoulli", "p": IA2RG_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_IA_IN2INT, "delay": delay["ia_path"]})
        nest.Connect(L["ia_int_f"], L["m_e"], conn_spec={"rule": "pairwise_bernoulli", "p": IA2RG_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_IA_INT2ANT, "delay": delay["ia_int_to_m"]})

        # MOD_IA_LOOP: Ia afferents drive the RG reciprocal-inhibition interneurons too.
        # Ia-E (peaks with extensor force/stretch) → InE → inhibits RG-F → reinforces
        # extensor phase. Ia-F (peaks with flexor force/stretch) → InF → inhibits RG-E
        # → reinforces flexor phase. Closed-loop sensory drive sustains the rhythm
        # when BS is low (essential for --debug-small at BS=20 Hz).
        nest.Connect(L["ia_in_e"], L["in_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IA2IN},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_IA2IN, "delay": delay["ia_path"]})
        nest.Connect(L["ia_in_f"], L["in_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IA2IN},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_IA2IN, "delay": delay["ia_path"]})

        # MOD_IA_RG_STDP: plastic homonymous Ia->RG excitation, always wired (matches the
        # reference architecture diagram's direct Ia->RG-E/F projection, distinct from the
        # Ia->InE/InF reciprocal-inhibition loop above). Ia-E (extensor stretch/force)
        # potentiates onto RG-E, Ia-F onto RG-F — a third standing plastic pathway
        # alongside BS->RG and CUT->RG (BS drops out under --freeze-bs-rg; Ia->RG and
        # CUT->RG keep training either way). A fixed weight here couldn't represent
        # training/rehabilitation, so this must stay plastic, not a static baseline.
        _p_ia2rg = float(getattr(args, "p_ia2rg", P_IA2RG_STDP))
        nest.Connect(L["ia_in_e"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": _p_ia2rg},
                     syn_spec={"synapse_model": f"stdp_ia_rge_{side}", "weight": W_INIT_IA, "delay": delay["ia_path"]})
        nest.Connect(L["ia_in_f"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": _p_ia2rg},
                     syn_spec={"synapse_model": f"stdp_ia_rgf_{side}", "weight": W_INIT_IA, "delay": delay["ia_path"]})

        # MOD_PACED_GAIT: external sequential Ia-E groups → InE → inhibits RGF during stance.
        # Reinforces extensor phase while preserving F→E asymmetry (InF→RGE still 6× stronger).
        if PACED_GAIT:
            for pn in L["ia_ext_pg_e"]:
                nest.Connect(pn, L["in_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IA2IN},
                             syn_spec={"synapse_model": "static_synapse", "weight": W_IA2IN,
                                       "delay": delay["ia_path"]})
        # MOD_FLEXOR_AFFERENT: swing flexor afferent reinforces the flexor phase
        # symmetrically to the stance extensor drive. Two pathways, mirroring the
        # extensor's (CUT→RG-E direct + Ia-E→InE antagonist suppression):
        #   (i)  ia_ext_pg_f → RG-F  (direct excitation, clocks the flexor burst)
        #   (ii) ia_ext_pg_f → InF   (suppresses RG-E, the antagonist, during swing)
        if PACED_GAIT and L["ia_ext_pg_f"] is not None:
            nest.Connect(L["ia_ext_pg_f"], L["rg_f"],
                         conn_spec={"rule": "pairwise_bernoulli", "p": P_IA2IN},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_FLEX_AFF2RGF,
                                   "delay": delay["ia_path"]})
            nest.Connect(L["ia_ext_pg_f"], L["in_f"],
                         conn_spec={"rule": "pairwise_bernoulli", "p": P_IA2IN},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_IA2IN,
                                   "delay": delay["ia_path"]})

        nest.Connect(L["rg_e"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_REC},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_RG_REC_E, "delay": delay["rg_rec"]})  # MOD_FIG10
        nest.Connect(L["rg_f"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_REC},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_RG_REC_F, "delay": delay["rg_rec"]})  # MOD_FIG10
        # MOD_ZHANG_ASYM: asymmetric reciprocal inhibition via inhibitory interneurons (InE, InF).
        # F→InF→E pathway is strong (clean extensor silencing during flexor burst);
        # E→InE→F pathway is weak (preserves flexor's rhythm-leading role).
        # F → InF (strong drive of the extensor-suppressing interneuron)
        nest.Connect(L["rg_f"], L["in_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_RECIP_F},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_RG2INF, "delay": delay["rg_recip"]})
        # InF → RG-E (STRONG inhibition: F dominates and silences E)
        nest.Connect(L["in_f"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_RECIP_F},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_INF2RGE, "delay": delay["rg_recip"]})

        # E → InE (drives the flexor-suppressing interneuron)
        nest.Connect(L["rg_e"], L["in_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_RECIP_E},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_RG2INE, "delay": delay["rg_recip"]})
        # InE → RG-F (WEAK inhibition: preserves F's intrinsic rhythm)
        nest.Connect(L["in_e"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_RECIP_E},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_INE2RGF, "delay": delay["rg_recip"]})

        # MOD_CUT_REFLEX: CUT → InE — cutaneous afferents reinforce the stance-phase
        # extensor reflex by exciting the flexor-suppressing interneuron.
        nest.Connect(L["cut_in"], L["in_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_CUT2INE},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_CUT2INE, "delay": delay["cut_to_rg"]})

        if USE_STATIC_PARALLEL:
            nest.Connect(L["bs_in_e"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": delay["base_to_rg"]})
            nest.Connect(L["bs_in_f"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": delay["base_to_rg"]})
            nest.Connect(L["cut_in"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": delay["base_to_rg"]})
            nest.Connect(L["rg_e"], L["m_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_RM},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_RM, "delay": delay["base_to_rg"]})
            nest.Connect(L["rg_f"], L["m_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_RM},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_RM, "delay": delay["base_to_rg"]})

        # ---- commissural ----
    if ENABLE_COMMISSURAL:
        LL = leg["L"]; RR = leg["R"]
        # Main left-right symmetry-breaking mechanism should be spinal, not brainstem.
        # Strengthen mutual inhibition between homologous flexor half-centers and add a weaker
        # extensor-side cross inhibition to suppress mirror-symmetric locking.
        nest.Connect(LL["rg_f"], RR["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM_F},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_F_INH, "delay": delay["commissural"]})
        nest.Connect(RR["rg_f"], LL["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM_F},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_F_INH, "delay": delay["commissural"]})

        nest.Connect(LL["rg_e"], RR["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM_E},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_E_INH, "delay": delay["commissural"]})
        nest.Connect(RR["rg_e"], LL["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM_E},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_E_INH, "delay": delay["commissural"]})

    # ---- BIO-PLAUSIBILITY: lognormal weight heterogeneity on static synapses ----
    # Biological synaptic weights are heterogeneous (lognormal: Song 2005; Buzsaki &
    # Mizuseki 2014), not delta-valued. With --static-weight-cv>0 we multiply every
    # static-synapse weight by a per-connection lognormal factor (mean 1, given CV),
    # preserving each projection's mean and sign. Applied before the dump and sim.
    static_cv = float(getattr(args, "static_weight_cv", 0.0) or 0.0)
    if static_cv > 0.0:
        try:
            # Sorted so the seeded factors land on the same synapses every run (B11).
            sconns = sorted_connections(nest.GetConnections(synapse_model="static_synapse"))
            if sconns is not None and len(sconns) > 0:
                w = np.asarray(nest.GetStatus(sconns, "weight"), dtype=float)
                sigma = float(np.sqrt(np.log(1.0 + static_cv * static_cv)))
                mu = -0.5 * sigma * sigma  # so E[factor]=1
                factor = np.random.default_rng(int(args.seed) + 777).lognormal(mu, sigma, size=w.size)
                nest.SetStatus(sconns, [{"weight": float(wi * fi)} for wi, fi in zip(w, factor)])
                if rank == 0:
                    print(f"[BioPlaus] static-weight heterogeneity CV={static_cv} applied to {w.size} static synapses")
        except Exception as e:
            if rank == 0:
                print(f"[BioPlaus] static heterogeneity skipped: {e}")

    # ---- PLAN.md P2: reflex-latency probe (opt-in) ----
    # Runs are deterministic for a fixed seed and thread count (B11/B12), so a probe run
    # and a control run with the SAME extra nodes differ only by the volley: the first
    # spike that differs after the volley gives the shortest causal Ia -> RG/M/muscle
    # latency. Nothing here is created unless --probe-reflex-at-ms is given.
    PROBE_RECS = {}
    PROBE_VOLLEY_MS = None
    if getattr(args, "probe_reflex_at_ms", None) is not None:
        _t = float(args.probe_reflex_at_ms)
        PROBE_VOLLEY_MS = round(_t / RES_MS) * RES_MS if _t >= 0 else -1.0
        _sg = nest.Create("spike_generator", len(leg["L"]["ia_in_e"]),
                          params={"spike_times": [PROBE_VOLLEY_MS] if PROBE_VOLLEY_MS > 0 else []})
        nest.Connect(_sg, leg["L"]["ia_in_e"], "one_to_one",
                     syn_spec={"synapse_model": "static_synapse", "weight": 1.0, "delay": RES_MS})
        for _name in ("rg_e", "m_e", "mus_e"):
            PROBE_RECS[_name] = nest.Create("spike_recorder")
            nest.Connect(leg["L"][_name], PROBE_RECS[_name])
        if rank == 0:
            print(f"[Probe] Ia-E volley at {PROBE_VOLLEY_MS} ms (negative = control, no volley); "
                  f"recording left RG-E, M-E, mus-E")

    # ---- optional: dump per-connection weight & delay distributions, then exit ----
    if str(getattr(args, "dump_connectivity", "")).strip():
        L = leg["L"]
        # (name, source population, target population [, synapse_model]) for every
        # named projection. The optional 4th element disambiguates parallel pathways
        # that share a (source, target) pair (CUT->RG-E has BOTH a plastic STDP
        # pathway and a static co-activation pathway).
        side0 = LEGS[0]
        projset = [
            # --- descending / supraspinal drive ---
            ("BS->RG-E",   L["bs_in_e"],  L["rg_e"]),
            ("BS->RG-F",   L["bs_in_f"],  L["rg_f"]),
            ("CUT->RG-E (plastic)", L["cut_in"], L["rg_e"], f"stdp_cut_rge_{side0}"),
            ("CUT->RG-E (static coact)", L["cut_in"], L["rg_e"], "static_synapse"),
            ("CUT->InE",   L["cut_in"],   L["in_e"]),
            ("base->RG-E", L["base_in"],  L["rg_e"]),
            ("base->RG-F", L["base_in"],  L["rg_f"]),
            # --- rhythm-generator reciprocal core ---
            ("RG-E->InE",  L["rg_e"],     L["in_e"]),
            ("RG-F->InF",  L["rg_f"],     L["in_f"]),
            ("InE->RG-F",  L["in_e"],     L["rg_f"]),
            ("InF->RG-E",  L["in_f"],     L["rg_e"]),
            # --- motor output ---
            ("RG-E->M-E",  L["rg_e"],     L["m_e"]),
            ("RG-F->M-F",  L["rg_f"],     L["m_f"]),
            ("M-E->M-F",   L["m_e"],      L["m_f"]),
            ("M-F->M-E",   L["m_f"],      L["m_e"]),
            ("M-E->mus-E", L["m_e"],      L["mus_e"]),
            ("M-F->mus-F", L["m_f"],      L["mus_f"]),
            # --- Ia proprioceptive interneuron pathway ---
            ("Ia-E->IaInt-E", L["ia_in_e"], L["ia_int_e"]),
            ("Ia-F->IaInt-F", L["ia_in_f"], L["ia_int_f"]),
            ("IaInt-E->M-F", L["ia_int_e"], L["m_f"]),
            ("IaInt-F->M-E", L["ia_int_f"], L["m_e"]),
            ("Ia-E->InE",  L["ia_in_e"],  L["in_e"]),
            ("Ia-F->InF",  L["ia_in_f"],  L["in_f"]),
            # --- commissural (interlimb; abstracts V0v/V0d/V2a/In1 classes) ---
            ("commiss F (L->R)", leg["L"]["rg_f"], leg["R"]["rg_f"]),
            ("commiss E (L->R)", leg["L"]["rg_e"], leg["R"]["rg_e"]),
        ]
        if L["ia_ext_pg_f"] is not None:
            projset.append(("flexAff->RG-F", L["ia_ext_pg_f"], L["rg_f"]))
            projset.append(("flexAff->InF",  L["ia_ext_pg_f"], L["in_f"]))
        projset.append(("Ia-E->RG-E", L["ia_in_e"], L["rg_e"]))
        projset.append(("Ia-F->RG-F", L["ia_in_f"], L["rg_f"]))
        if rank == 0:
            with h5py.File(args.dump_connectivity, "w") as hc:
                hc.attrs["species"] = str(getattr(args, "species", "rat"))
                hc.attrs["delay_model"] = str(getattr(args, "delay_model", "fixed"))
                hc.attrs["delay_jitter_ms"] = float(getattr(args, "delay_jitter_ms", 0.0))
                write_species_provenance(hc, SPECIES_CFG)
                for entry in projset:
                    name, src, tgt = entry[0], entry[1], entry[2]
                    syn_model = entry[3] if len(entry) > 3 else None
                    try:
                        if syn_model is not None:
                            conns = nest.GetConnections(source=src, target=tgt, synapse_model=syn_model)
                        else:
                            conns = nest.GetConnections(source=src, target=tgt)
                        conns = sorted_connections(conns)  # deterministic dump order (B11)
                        if conns is None or len(conns) == 0:
                            continue
                        w = np.asarray(nest.GetStatus(conns, "weight"), dtype=np.float32)
                        d = np.asarray(nest.GetStatus(conns, "delay"), dtype=np.float32)
                    except Exception:
                        continue
                    g = hc.create_group(name.replace("/", "_").replace(" ", "_"))
                    g.attrs["projection"] = name
                    g.create_dataset("weight", data=w, compression="gzip")
                    g.create_dataset("delay", data=d, compression="gzip")
                    g.attrs["n"] = int(w.size)
                    g.attrs["w_mean"] = float(w.mean()); g.attrs["w_std"] = float(w.std())
                    g.attrs["d_mean"] = float(d.mean()); g.attrs["d_std"] = float(d.std())
            print(f"[Connectivity] dumped {len(projset)} projections -> {args.dump_connectivity}")
        return

    # ---- stats (pre-sim) ----

    stats_nodes = node_model_counts(
        ["izhikevich", "parrot_neuron", "poisson_generator", "spike_recorder", "weight_recorder"])
    stats_syn_sign = synapse_sign_stats()
    stats_syn_models = {
        "L_stdp_cut_rge": safe_len_connections(synapse_model="stdp_cut_rge_L"),
        "L_stdp_bs_rge": safe_len_connections(synapse_model="stdp_bs_rge_L"),
        "L_stdp_bs_rgf": safe_len_connections(synapse_model="stdp_bs_rgf_L"),
        "R_stdp_cut_rge": safe_len_connections(synapse_model="stdp_cut_rge_R"),
        "R_stdp_bs_rge": safe_len_connections(synapse_model="stdp_bs_rge_R"),
        "R_stdp_bs_rgf": safe_len_connections(synapse_model="stdp_bs_rgf_R"),
        "static_total": safe_len_connections(synapse_model="static_synapse"),
    }
    if rank == 0:
        print("[Stats] node_models:", stats_nodes)
        print("[Stats] syn_sign:", stats_syn_sign)
        print("[Stats] syn_models:", stats_syn_models)
    # ---- cache connection collections for faster weight sampling ----
    # NOTE: in MPI runs, each rank sees (and caches) its local connections.
    # Plastic projections to track: CUT->RG and Ia->RG are always plastic (three-pathway
    # standing architecture); BS->RG drops out only when frozen (--freeze-bs-rg).
    # (MOD_FREEZE_BS / MOD_IA_RG_STDP)
    plastic_keys = ["cut->rge", "ia->rge", "ia->rgf"]
    if not getattr(args, "freeze_bs_rg", False):
        plastic_keys += ["bs->rge", "bs->rgf"]

    def _stdp_model(key, side):
        return {"cut->rge": f"stdp_cut_rge_{side}", "bs->rge": f"stdp_bs_rge_{side}",
                "bs->rgf": f"stdp_bs_rgf_{side}", "ia->rge": f"stdp_ia_rge_{side}",
                "ia->rgf": f"stdp_ia_rgf_{side}"}[key]

    conns_cache = {side: {} for side in LEGS}
    for side in LEGS:
        L = leg[side]
        # Plastic (STDP) connections cached by synapse model. Sorted (B11): the
        # --max-weight-conns subset below and the consolidation baselines are
        # positional, so the order must be the same on every run.
        for key in plastic_keys:
            try:
                conns_cache[side][key] = sorted_connections(
                    nest.GetConnections(synapse_model=_stdp_model(key, side)))
            except Exception:
                conns_cache[side][key] = []

    # Keep an unmodified cache for full-weight saving (not downsampled)
    conns_full_cache = {side: {k: conns_cache[side][k] for k in conns_cache[side].keys()} for side in LEGS}

    # Cache endpoints once for full-weight saving
    conns_endpoints = {side: {} for side in LEGS}
    for side in LEGS:
        for key, conns in conns_full_cache[side].items():
            try:
                if conns is None or len(conns) == 0:
                    conns_endpoints[side][key] = (np.array([], dtype=np.int64), np.array([], dtype=np.int64))
                else:
                    src = np.asarray(nest.GetStatus(conns, "source"), dtype=np.int64)
                    tgt = np.asarray(nest.GetStatus(conns, "target"), dtype=np.int64)
                    conns_endpoints[side][key] = (src, tgt)
            except Exception:
                conns_endpoints[side][key] = (np.array([], dtype=np.int64), np.array([], dtype=np.int64))

    # Optional connection downsampling for faster weight trend stats (mean/std)
    # This reduces the size of the weight arrays pulled via nest.GetStatus(conns, "weight")
    # without changing the simulated network.
    max_w_conns = int(getattr(args, "max_weight_conns", 0) or 0)
    if max_w_conns > 0:
        for side in LEGS:
            for key, conns in conns_cache[side].items():
                try:
                    if conns is not None and len(conns) > max_w_conns:
                        # ConnectionCollection supports slicing in NEST 3.x
                        conns_cache[side][key] = conns[:max_w_conns]
                except Exception:
                    # If slicing is not supported, keep original
                    pass

    # ---- MOD_CONSOLIDATE: tag-and-capture consolidation state (opt-in) ----
    # Two components per synapse, replacing "whatever stdp_synapse says is
    # permanent" with "only what gets captured is permanent": `weight` (native
    # STDP induction, unchanged -- the fast, local, per-synapse tag-setting
    # process) and `baseline` (new, persistent per-connection captured/stable
    # component; the live tag = weight - baseline is not stored separately).
    # A single shared "cell-wide" prp_pool per pathway/leg is the capture
    # gate -- PRP synthesis is cell-wide in the biology while the tag is
    # synapse-local, so this mirrors that split rather than tracking a pool
    # per synapse. Initialized post-downsampling so array lengths always match
    # conns_cache[side][key] exactly. All three pathways (cut->rge, ia->rge,
    # ia->rgf, and bs->rge/bs->rgf when not frozen) get real weight writes --
    # BS->RG previously got identical bookkeeping but was never written back
    # (weak literature support for touching WMAX_BS's anti-runaway role was
    # the original reasoning); fixed 2026-09-17 at explicit user request to
    # apply consolidation uniformly across every plastic pathway rather than
    # leaving BS->RG as vanilla-STDP-only. Wmax itself remains untouched for
    # BS (WMAX_BS's anti-runaway cap still applies) -- only retention within
    # that ceiling is now gated the same way as the other two pathways.
    consolidate_keys = list(plastic_keys)
    consolidate_behavioral_keys = set(consolidate_keys)
    baseline = {side: {} for side in LEGS}
    prp_pool = {side: {k: 0.0 for k in consolidate_keys} for side in LEGS}
    pending_consolidation_event = {side: 0 for side in LEGS}
    # MOD_WMAX_GROWTH: current per-connection Wmax for ia->rge/ia->rgf only (the
    # pathway the spec's own mapping section names as the candidate for a rising
    # ceiling -- not cut->rge/bs->rge/bs->rgf). Starts at the already-loading-
    # adjusted EFFECTIVE_WMAX_IA and only ever moves if
    # --consolidate-wmax-ia-growth-per-capture > 0 (default 0.0 = no-op).
    wmax_ia_growth_keys = tuple(k for k in ("ia->rge", "ia->rgf") if k in consolidate_keys)
    wmax_ia_current = {side: {k: float(EFFECTIVE_WMAX_IA) for k in wmax_ia_growth_keys} for side in LEGS}
    if CONSOLIDATE:
        for side in LEGS:
            for key in consolidate_keys:
                conns = conns_cache[side][key]
                if conns is None or len(conns) == 0:
                    baseline[side][key] = np.array([], dtype=float)
                else:
                    baseline[side][key] = np.asarray(nest.GetStatus(conns, "weight"), dtype=float)

    def consolidation_bout_event(side: str, genuine: bool) -> bool:
        """MOD_CONSOLIDATE: called once per real (non-priming) stance/swing
        bout boundary. Genuine (real force-threshold) endings push the
        shared prp_pool up toward capture; forced (failsafe-timeout) endings
        push it down (Grau: non-contingent outcomes actively suppress rather
        than merely fail to reinforce). On capture, every connection's
        baseline is frozen at wherever weight currently sits (the hippocampal
        doc's Fig. 2 staircase step). Returns True if any key captured this
        event."""
        captured_any = False
        for key in consolidate_keys:
            if genuine:
                prp_pool[side][key] += CONSOLIDATE_PRP_GAIN_GENUINE
            else:
                prp_pool[side][key] = max(0.0, prp_pool[side][key] - CONSOLIDATE_PRP_GAIN_FORCED)
            if prp_pool[side][key] >= CONSOLIDATE_PRP_THRESHOLD:
                conns = conns_cache[side][key]
                if conns is not None and len(conns) > 0:
                    baseline[side][key] = np.asarray(nest.GetStatus(conns, "weight"), dtype=float)
                prp_pool[side][key] -= CONSOLIDATE_PRP_THRESHOLD
                captured_any = True
                # MOD_WMAX_GROWTH: structural consolidation -- a genuine, repeated
                # capture raises the ceiling itself (Wolpaw Phase I -> Phase II),
                # not just what's retained beneath it. No-op unless the growth
                # flag is set (default 0.0).
                if (CONSOLIDATE_WMAX_IA_GROWTH > 0.0) and (key in wmax_ia_current[side]):
                    new_wmax = min(CONSOLIDATE_WMAX_IA_CEILING,
                                   wmax_ia_current[side][key] + CONSOLIDATE_WMAX_IA_GROWTH)
                    if new_wmax != wmax_ia_current[side][key]:
                        wmax_ia_current[side][key] = new_wmax
                        if conns is not None and len(conns) > 0:
                            nest.SetStatus(conns, [{"Wmax": float(new_wmax)}] * len(conns))
        return captured_any

    def consolidation_leak(side: str):
        """MOD_CONSOLIDATE: spontaneous per-synapse tag decay toward the
        captured baseline, applied every gate tick (~args.rate_update_ms).
        This is the actual behavioral difference from vanilla STDP: an
        unreinforced potentiation now relaxes back toward the last captured
        baseline instead of being kept forever (Wmax is unaffected -- it
        still bounds `weight` exactly as before; this governs retention
        within that ceiling)."""
        decay = float(np.exp(-float(args.rate_update_ms) / CONSOLIDATE_TAU_TAG_MS))
        for key in consolidate_behavioral_keys:
            conns = conns_cache[side][key]
            if conns is None or len(conns) == 0:
                continue
            w = np.asarray(nest.GetStatus(conns, "weight"), dtype=float)
            new_w = baseline[side][key] + (w - baseline[side][key]) * decay
            nest.SetStatus(conns, [{"weight": float(wv)} for wv in new_w])

    # ---- storage ----
    times = []
    wstats = {side: {k: ([], []) for k in plastic_keys} for side in LEGS}
    # MOD_CONSOLIDATE: baseline (captured/stable component) mean/std time series
    # and the shared prp_pool trace, alongside the existing weight stats.
    consolidate_stats = {side: {k: ([], []) for k in consolidate_keys} for side in LEGS}
    prp_log = {side: {k: [] for k in consolidate_keys} for side in LEGS}
    # MOD_WMAX_GROWTH: current-Wmax trace for ia->rge/ia->rgf, flat at
    # EFFECTIVE_WMAX_IA unless --consolidate-wmax-ia-growth-per-capture > 0.
    wmax_ia_log = {side: {k: [] for k in wmax_ia_growth_keys} for side in LEGS}
    logs = {side: dict(bs_e=[], bs_f=[], mus_e=[], mus_f=[],
                       rge=[], rgf=[],
                       ine=[], inf=[], iaint_e=[], iaint_f=[],  # MOD_NET_RECORD
                       act_e=[], act_f=[], force_e=[], force_f=[],
                       fatigue_e=[], fatigue_f=[], cut_on=[],
                       len_e=[], len_f=[], ia_e=[], ia_f=[]) for side in LEGS}
    if CONSOLIDATE:  # MOD_CONSOLIDATE: +1 genuine / -1 forced / +-2 same-with-capture / 0 no-event
        for side in LEGS:
            logs[side]["consolidation_event"] = []
    state = {side: dict(act_e=0.0, act_f=0.0, force_e=0.0, force_f=0.0,
                        fatigue_e=0.0, fatigue_f=0.0,
                        len_e=L0, len_f=L0,
                        last_muse=0, last_musf=0,
                        last_rge=0, last_rgf=0,
                        last_ine=0, last_inf=0, last_iainte=0, last_iaintf=0) for side in LEGS}

    # Optional full-weight storage (final or snapshots)
    wfull_times = []
    wfull = {side: {k: [] for k in plastic_keys} for side in LEGS}

    # If only "final" weights are requested, also capture the INITIAL full weight vectors at t=0.
    # This prevents downstream plotting code (e.g., quantile bands over time) from seeing only a
    # single timepoint and producing empty/degenerate plots.
    if rank == 0 and args.save_weights == "final":
        wfull_times.append(0.0)
        for side in LEGS:
            for key in plastic_keys:
                conns = conns_full_cache[side][key]
                if conns is None or len(conns) == 0:
                    wfull[side][key].append(np.array([], dtype=np.float32))
                else:
                    w = np.asarray(nest.GetStatus(conns, "weight"), dtype=np.float32)
                    wfull[side][key].append(w)

    def new_spikes(rec, last_n):
        # Fast, constant-memory spike counting
        cur = int(nest.GetStatus(rec, "n_events")[0])
        return cur - last_n, cur

    def update_leg(side: str, t_ms: float, dt_ms_actual: float, cut_active_frac: float, do_rate_update: bool):
        dt_s = float(dt_ms_actual) / 1000.0
        L = leg[side]
        S = state[side]
        P = logs[side]

        r_e, r_f = bs_rates_counterphase(t_ms, side)
        # MOD_BS_REGULAR200: BS spike_generators are pre-programmed; no per-step rate updates.
        P["bs_e"].append(r_e);
        P["bs_f"].append(r_f)

        sp_e, cur_e = new_spikes(L["rec_muse"], S["last_muse"])
        sp_f, cur_f = new_spikes(L["rec_musf"], S["last_musf"])
        S["last_muse"] = cur_e;
        S["last_musf"] = cur_f

        # RG population spike rates (Hz per neuron) for plotting
        sp_rge, cur_rge = new_spikes(L["rec_rge"], S["last_rge"])
        sp_rgf, cur_rgf = new_spikes(L["rec_rgf"], S["last_rgf"])
        S["last_rge"] = cur_rge
        S["last_rgf"] = cur_rgf

        # NOTE: muscle parrot neurons amplify spikes because each muscle cell can receive many motor spikes.
        # Normalize by expected motor->muscle fan-in so proxy activation doesn't saturate in both phases.
        dt_s_safe = max(1e-9, dt_s)
        fanin_e = max(1.0, float(N_MOTOR_E) * float(P_M2MUS))
        fanin_f = max(1.0, float(N_MOTOR_F) * float(P_M2MUS))

        r_muse = ((sp_e / max(1, N_MUS_E)) / dt_s_safe) / fanin_e
        r_musf = ((sp_f / max(1, N_MUS_F)) / dt_s_safe) / fanin_f
        P["mus_e"].append(r_muse)
        P["mus_f"].append(r_musf)

        r_rge = (sp_rge / max(1, N_RG_E)) / dt_s_safe
        r_rgf = (sp_rgf / max(1, N_RG_F)) / dt_s_safe
        P["rge"].append(r_rge)
        P["rgf"].append(r_rgf)

        # MOD_NET_RECORD: interneuron population rates (Hz/neuron) for the
        # combined network-activity figure.
        sp_ine, cur_ine = new_spikes(L["rec_ine"], S["last_ine"]); S["last_ine"] = cur_ine
        sp_inf, cur_inf = new_spikes(L["rec_inf"], S["last_inf"]); S["last_inf"] = cur_inf
        sp_iae, cur_iae = new_spikes(L["rec_iainte"], S["last_iainte"]); S["last_iainte"] = cur_iae
        sp_iaf, cur_iaf = new_spikes(L["rec_iaintf"], S["last_iaintf"]); S["last_iaintf"] = cur_iaf
        P["ine"].append((sp_ine / max(1, N_INE)) / dt_s_safe)
        P["inf"].append((sp_inf / max(1, N_INF)) / dt_s_safe)
        P["iaint_e"].append((sp_iae / max(1, N_IA_INT)) / dt_s_safe)
        P["iaint_f"].append((sp_iaf / max(1, N_IA_INT)) / dt_s_safe)

        # MOD_ACT_GATE: gate by RG population rate. rg_ref=100 Hz matches typical burst peaks
        # in both debug (BS=20 Hz, N_RG=40) and production after convergence (d_e clamped to 1
        # when bursting at 300+ Hz). ACT_GATE_POWER=2 sharpens discrimination: at trough
        # (~25 Hz) d_e=(25/100)^2=0.063 → force<2; at burst peak (~80 Hz) d_e=0.64 → force>12.
        rg_ref = 100.0
        # MOD_LOGISTIC_GATE: smooth sigmoidal gate (replaces the hard clamp^power).
        d_e = 1.0 / (1.0 + np.exp(-ACT_GATE_K * (float(r_rge) / rg_ref - ACT_GATE_X0)))
        d_f = 1.0 / (1.0 + np.exp(-ACT_GATE_K * (float(r_rgf) / rg_ref - ACT_GATE_X0)))

        # Saturating mapping from muscle relay rate to activation
        a_raw_e = ACT_MAX * (1.0 - np.exp(-ACT_SAT_K * float(r_muse)))
        a_raw_f = ACT_MAX * (1.0 - np.exp(-ACT_SAT_K * float(r_musf)))

        # Gated activation target. a_raw already saturates at ACT_MAX and d in (0,1),
        # so the product is bounded in [0, ACT_MAX) without a hard clamp.
        target_ae = a_raw_e * d_e
        target_af = a_raw_f * d_f

        tau_rise_s = TAU_ACT_RISE_MS / 1000.0
        tau_decay_s = TAU_ACT_DECAY_MS / 1000.0
        tau_e = tau_rise_s if target_ae > S["act_e"] else tau_decay_s
        tau_f = tau_rise_s if target_af > S["act_f"] else tau_decay_s

        kAe = 1.0 - np.exp(-dt_s_safe / max(1e-9, tau_e))
        kAf = 1.0 - np.exp(-dt_s_safe / max(1e-9, tau_f))

        S["act_e"] += kAe * (target_ae - S["act_e"])
        S["act_f"] += kAf * (target_af - S["act_f"])
        S["act_e"] = clamp(S["act_e"], 0.0, ACT_MAX)
        S["act_f"] = clamp(S["act_f"], 0.0, ACT_MAX)

        # MOD_MUSCLE_FATIGUE: slow activity-dependent fatigue so force can decay on
        # its own during sustained stance/swing (RG-E has no INaP-style intrinsic
        # burst termination the way RG-F does, so without this the force plateau
        # never decays -- see --muscle-fatigue help). No-op (fatigue stays 0) unless
        # --muscle-fatigue is set, so timer-based paced-gait runs are unaffected.
        if MUSCLE_FATIGUE:
            drive_e = S["act_e"] / max(1e-9, ACT_MAX)
            drive_f = S["act_f"] / max(1e-9, ACT_MAX)
            tau_on_s = FATIGUE_TAU_ONSET_MS_BY_SIDE[side] / 1000.0
            tau_rec_s = FATIGUE_TAU_RECOVERY_MS / 1000.0
            S["fatigue_e"] += dt_s * (drive_e * (FATIGUE_MAX_FRAC - S["fatigue_e"]) / tau_on_s
                                       - (1.0 - drive_e) * S["fatigue_e"] / tau_rec_s)
            S["fatigue_f"] += dt_s * (drive_f * (FATIGUE_MAX_FRAC - S["fatigue_f"]) / tau_on_s
                                       - (1.0 - drive_f) * S["fatigue_f"] / tau_rec_s)
            S["fatigue_e"] = clamp(S["fatigue_e"], 0.0, FATIGUE_MAX_FRAC)
            S["fatigue_f"] = clamp(S["fatigue_f"], 0.0, FATIGUE_MAX_FRAC)

        target_fe = FORCE_MAX * (1.0 - S["fatigue_e"]) * (1.0 - np.exp(-FORCE_SAT_K * S["act_e"]))
        target_ff = FORCE_MAX * (1.0 - S["fatigue_f"]) * (1.0 - np.exp(-FORCE_SAT_K * S["act_f"]))
        tau_rise_s = TAU_FORCE_RISE_MS / 1000.0
        tau_decay_s = TAU_FORCE_DECAY_MS / 1000.0

        # Stable force dynamics (rise/decay) for large dt
        kFe = 1.0 - np.exp(-dt_s_safe / max(1e-9, (tau_rise_s if target_fe > S["force_e"] else tau_decay_s)))
        kFf = 1.0 - np.exp(-dt_s_safe / max(1e-9, (tau_rise_s if target_ff > S["force_f"] else tau_decay_s)))
        S["force_e"] += kFe * (target_fe - S["force_e"])
        S["force_f"] += kFf * (target_ff - S["force_f"])

        S["force_e"] = clamp(S["force_e"], 0.0, FORCE_MAX)
        S["force_f"] = clamp(S["force_f"], 0.0, FORCE_MAX)

        tauL_s = TAU_LENGTH_MS / 1000.0
        kL = 1.0 - np.exp(-dt_s_safe / max(1e-9, tauL_s))
        S["len_e"] += kL * (L0 - S["len_e"])
        S["len_f"] += kL * (L0 - S["len_f"])
        S["len_e"] -= SHORTEN_GAIN * S["force_e"] * dt_s
        S["len_f"] -= SHORTEN_GAIN * S["force_f"] * dt_s
        if cut_active_frac > 0.0:
            S["len_e"] += STRETCH_GAIN * cut_active_frac * dt_s
        S["len_e"] = clamp(S["len_e"], L_MIN, L_MAX)
        S["len_f"] = clamp(S["len_f"], L_MIN, L_MAX)

        stretch_e = max(0.0, S["len_e"] - L0)
        stretch_f = max(0.0, S["len_f"] - L0)
        ia_e = IA_BASE_HZ + IA_K_FORCE * S["force_e"] + IA_K_STRETCH * stretch_e
        ia_f = IA_BASE_HZ + IA_K_FORCE * S["force_f"] + IA_K_STRETCH * stretch_f
        # Graded sensory feedback: scale by Ia gain (1.0 baseline / 0.5 toe / 0.1 air).
        # Mimics partial loading after SCI rehab (Lavrov 2008; Edgerton 2008).
        ia_e = IA_FEEDBACK_GAIN * ia_e
        ia_f = IA_FEEDBACK_GAIN * ia_f
        ia_e = clamp(ia_e, 0.0, IA_RATE_MAX_HZ)
        ia_f = clamp(ia_f, 0.0, IA_RATE_MAX_HZ)
        if do_rate_update:
            nest.SetStatus(L["ia_pg_e"], {"rate": ia_e})
            nest.SetStatus(L["ia_pg_f"], {"rate": ia_f})

        P["act_e"].append(S["act_e"]);
        P["act_f"].append(S["act_f"])
        P["force_e"].append(S["force_e"]);
        P["force_f"].append(S["force_f"])
        P["fatigue_e"].append(S["fatigue_e"]);
        P["fatigue_f"].append(S["fatigue_f"])
        P["len_e"].append(S["len_e"]);
        P["len_f"].append(S["len_f"])
        P["ia_e"].append(ia_e);
        P["ia_f"].append(ia_f)

    # Keep last sampled mean/std so we can append smoothly without resampling every step
    last_wstats = {side: {k: (np.nan, np.nan) for k in plastic_keys} for side in LEGS}
    last_cstats = {side: {k: (np.nan, np.nan) for k in consolidate_keys} for side in LEGS}  # MOD_CONSOLIDATE

    def log_weights(t_ms: float, step_idx: int):
        """Append weight mean/std time series.
        Optionally store full weight vectors for plastic projections.

        - mean/std are appended every step (reusing last sampled values)
        - full vectors are stored only when sampling happens (snapshots)
        """
        times.append(t_ms)
        do_sample = (step_idx % weight_every == 0)

        for side in LEGS:
            for key in plastic_keys:
                if do_sample:
                    conns = conns_cache[side][key]
                    if conns is None or len(conns) == 0:
                        last_wstats[side][key] = (np.nan, np.nan)
                    else:
                        w = np.asarray(nest.GetStatus(conns, "weight"), dtype=float)
                        last_wstats[side][key] = (float(w.mean()), float(w.std()))
                mval, sval = last_wstats[side][key]
                wstats[side][key][0].append(mval)
                wstats[side][key][1].append(sval)

            if CONSOLIDATE:  # MOD_CONSOLIDATE: baseline mean/std + prp_pool trace
                for key in consolidate_keys:
                    if do_sample:
                        b = baseline[side].get(key)
                        if b is None or b.size == 0:
                            last_cstats[side][key] = (np.nan, np.nan)
                        else:
                            last_cstats[side][key] = (float(b.mean()), float(b.std()))
                    bmval, bsval = last_cstats[side][key]
                    consolidate_stats[side][key][0].append(bmval)
                    consolidate_stats[side][key][1].append(bsval)
                    prp_log[side][key].append(float(prp_pool[side][key]))
                for key in wmax_ia_growth_keys:  # MOD_WMAX_GROWTH
                    wmax_ia_log[side][key].append(float(wmax_ia_current[side][key]))

        # Full weight storage (snapshots at sampling ticks)
        if args.save_weights == "snapshots" and do_sample:
            wfull_times.append(float(t_ms))
            for side in LEGS:
                for key in plastic_keys:
                    conns = conns_full_cache[side][key]
                    if conns is None or len(conns) == 0:
                        wfull[side][key].append(np.array([], dtype=np.float32))
                    else:
                        w = np.asarray(nest.GetStatus(conns, "weight"), dtype=np.float32)
                        wfull[side][key].append(w)

    total_steps = int(np.ceil(SIM_MS / CHUNK_MS))
    if rank == 0 and (SIM_MS >= 30000.0) and (not args.long_run):
        print("[Hint] Long simulation detected. Consider adding --long-run "
              "(sets chunk>=200ms, weight_sample>=1000ms, rate_update>=100ms, and downsamples weight reads).")
    done_steps = 0
    t_ms = 0.0

    t0 = time.time()
    sim_accum = 0.0
    book_accum = 0.0

    def run_window(window_ms: float, cut_active_frac, log_cut_on=None):
        """Simulate window_ms of NEST time in CHUNK_MS steps, updating logs and rates.

        cut_active_frac: one value for both legs (halfcycle scheduler, unchanged) or a
        per-leg dict (P3 phase scheduler). log_cut_on: optional per-leg 0/1 stance
        state appended to logs[side]["cut_on"] for every chunk."""
        nonlocal done_steps, t_ms, sim_accum, book_accum
        n_c = int(window_ms // CHUNK_MS)
        tail = q_ms(window_ms - n_c * CHUNK_MS)
        n_c_total = n_c + (1 if tail > 1e-9 else 0)
        for ci in range(n_c_total):
            cur = q_ms(CHUNK_MS if ci < n_c else tail)
            if cur <= 0.0:
                continue
            t_sim0 = time.perf_counter()
            nest.Simulate(cur)
            sim_accum += (time.perf_counter() - t_sim0)
            t_ms += cur
            done_steps += 1
            t_book0 = time.perf_counter()
            do_rate_update = (done_steps % rate_every == 0)
            for side in LEGS:
                _frac = cut_active_frac[side] if isinstance(cut_active_frac, dict) else cut_active_frac
                update_leg(side, t_ms, cur, _frac, do_rate_update)
                if log_cut_on is not None:
                    logs[side]["cut_on"].append(float(log_cut_on[side]))
            if ENFORCE_TONIC_BS:
                l_be = float(logs["L"]["bs_e"][-1]); r_be = float(logs["R"]["bs_e"][-1])
                l_bf = float(logs["L"]["bs_f"][-1]); r_bf = float(logs["R"]["bs_f"][-1])
                if abs(l_be - r_be) > 1e-9 or abs(l_bf - r_bf) > 1e-9:
                    raise RuntimeError(
                        f"Tonic BS violated across legs at t_ms={t_ms}: L=({l_be},{l_bf}), R=({r_be},{r_bf})")
            log_weights(t_ms, done_steps)
            book_accum += (time.perf_counter() - t_book0)

    if PACED_GAIT and CUT_TRIGGER == "force":
        # MOD_CUT_FORCE_TRIGGER: continuous loop, no external clock. Each leg's own
        # CUT (paw-contact) state is a Schmitt trigger on its own force_e: ON once
        # force_e crosses --cut-force-on-frac of that leg's adaptive running peak
        # ("foot touches down"), OFF once it falls below --cut-force-off-frac
        # ("foot lifts off"). Only --leading-leg starts in stance at t=0; the other
        # leg starts in swing and is held there for --lead-offset-ms to deterministically
        # break L/R symmetry (bio motivation: gait initiation from one planted leg,
        # not identical initial conditions) before the commissural circuit + force
        # feedback take over autonomously.
        # MOD_CUT_FORCE_TRIGGER: --lead-offset-ms is also a *symmetric priming
        # window* (both legs' CUT ON) so both sides' plastic CUT->RG-E synapse gets
        # co-activation training before the leading/lagging split. Without this,
        # only the leading leg's CUT ever fires early on (CUT is now a *consequence*
        # of stance, not an external announcement of it), so at low initial STDP
        # weight (production sweeps start as low as mean=0-3.5) the lagging leg's
        # CUT->RG-E synapse never gets its first potentiation and that leg struggles
        # to ever mount a real stance -- confirmed by direct test (production N,
        # BS=60Hz, sweep-pairs 3.5:0.30, no priming): leading leg reached
        # corr(Force-E,Force-F) -0.92, lagging leg only -0.20 (mostly stuck
        # flexor-dominant). With symmetric priming both legs train equally; the
        # leading/lagging split still happens because only the lagging leg is cut
        # back to swing the instant priming ends.
        lag_side = "L" if LEADING_LEG == "R" else "R"
        cut_state = {side: True for side in LEGS}
        # MOD_IA_RG_LOADING_GAIN: scale the peak-force seed down with loading too, not
        # just the Ia->RG weight cap -- otherwise a fixed full-loading seed stays
        # permanently above the achievable force ceiling under reduced
        # --cut-feedback-gain and peak_e_est never adapts (confirmed by direct test).
        _seed_loading_scale = CUT_FORCE_PEAK_SEED_MIN_FRAC + (1.0 - CUT_FORCE_PEAK_SEED_MIN_FRAC) * _cut_gain_for_ia_cap
        peak_e_seed = FORCE_MAX * CUT_FORCE_PEAK_SEED_FRAC * _seed_loading_scale
        peak_e_est = {side: peak_e_seed for side in LEGS}
        stance_onset_ms = {side: 0.0 for side in LEGS}
        phase_onset_ms = {side: 0.0 for side in LEGS}
        # MOD_CUT_FORCE_TRIGGER: optional EMA low-pass on force_e, decoupled from
        # --rate-update-ms, so the tick can be shortened for fast operating points
        # without losing the noise rejection the coarse tick used to provide
        # incidentally (see --cut-force-filter-tau-ms help). None = not yet seeded.
        force_e_filt = {side: None for side in LEGS}

        def cut_force_apply(side, is_on, t_now):
            nest.SetStatus(leg[side]["cut_pg"],
                           {"rate": CUT_FEEDBACK_GAIN * CUT_RATE_ON_HZ if is_on else CUT_RATE_OFF_HZ})
            if is_on:
                # Stance: Ia-E heel->mid->toe sub-group sequenced by elapsed time
                # since this leg's own stance onset (self-timed, not clock-scheduled).
                if leg[side]["ia_ext_pg_f"] is not None:
                    nest.SetStatus(leg[side]["ia_ext_pg_f"], {"rate": 0.0})
                elapsed = max(0.0, t_now - stance_onset_ms[side])
                g_idx = min(N_IA_GROUPS_PACED - 1, int(elapsed // max(1e-9, SUB_STANCE_MS)))
                for gi, g in enumerate(leg[side]["ia_ext_pg_e"]):
                    nest.SetStatus(g, {"rate": IA_EXT_HZ[gi] if gi == g_idx else 0.0})
            else:
                for g in leg[side]["ia_ext_pg_e"]:
                    nest.SetStatus(g, {"rate": 0.0})
                if leg[side]["ia_ext_pg_f"] is not None:
                    nest.SetStatus(leg[side]["ia_ext_pg_f"], {"rate": IA_EXT_F_HZ})

        def cut_force_gate(side, t_now):
            # Reads force_e computed by THIS chunk's update_leg() call, which itself
            # reflects spikes generated under the CUT/Ia rates set at the *previous*
            # gate tick -- the same one-tick sensor delay already used for Ia (natural
            # consequence of simulate-then-update-then-set-next-rate ordering).
            fe_raw = float(state[side]["force_e"])
            # MOD_CUT_FORCE_TRIGGER: optional explicit noise filter, decoupled from
            # --rate-update-ms (see --cut-force-filter-tau-ms help). At tau=0 this is
            # `fe = fe_raw`, byte-for-byte the original behaviour.
            if CUT_FORCE_FILTER_TAU_MS > 0.0:
                if force_e_filt[side] is None:
                    force_e_filt[side] = fe_raw
                alpha = 1.0 - np.exp(-float(args.rate_update_ms) / CUT_FORCE_FILTER_TAU_MS)
                force_e_filt[side] += alpha * (fe_raw - force_e_filt[side])
                fe = force_e_filt[side]
            else:
                fe = fe_raw
            # Per-bout running max, not a time-decaying one: grows monotonically
            # through the current stance bout, then holds exactly at that value
            # through the following swing (used as the ON reference), and is reset
            # fresh at the next stance onset. A time-decaying peak would chase a
            # slowly-fatiguing force down and the relative OFF threshold would then
            # never actually be crossed (confirmed by direct test: with fatigue
            # active, force and a decaying peak converged together and the leg
            # locked at a permanently reduced plateau instead of releasing).
            peak_e_est[side] = max(fe, peak_e_est[side])
            on_thr = CUT_FORCE_ON_FRAC * peak_e_est[side]
            off_thr = CUT_FORCE_OFF_FRAC * peak_e_est[side]
            was_on = cut_state[side]
            elapsed_phase = t_now - phase_onset_ms[side]
            priming = t_now < LEAD_OFFSET_MS
            # First gate tick after the priming window has elapsed (rate_every
            # granularity, so check against the previous tick's time too).
            just_ended_priming = (not priming) and (t_now - float(args.rate_update_ms) < LEAD_OFFSET_MS)

            forced = False  # MOD_CONSOLIDATE: was this bout ending a genuine threshold
                             # crossing, or only the failsafe timeout forcing it?
            if priming:
                is_on = True
            else:
                is_on = was_on
                if not was_on and fe >= on_thr:
                    is_on = True
                elif was_on and fe <= off_thr:
                    is_on = False
                is_on_pre_failsafe = is_on  # MOD_CONSOLIDATE: classification point

                # Failsafe timeout: without adaptation/fatigue, CUT->RG-E->force_e is
                # a stable positive-feedback plateau that a pure force threshold can
                # never escape (force saturates near its ceiling and just sits
                # there). This bounds each phase so the rhythm can't lock
                # permanently in stance or swing -- the endogenous-timer backstop
                # for when peripheral gating alone stalls (see --cut-max-stance-ms /
                # --cut-max-swing-ms help).
                if was_on and is_on and elapsed_phase >= CUT_MAX_STANCE_MS:
                    is_on = False
                elif not was_on and not is_on and elapsed_phase >= CUT_MAX_SWING_MS:
                    is_on = True
                forced = (is_on != is_on_pre_failsafe)  # MOD_CONSOLIDATE

                # Priming just ended: hand the lagging leg to swing immediately so
                # the leading/lagging phase offset actually takes hold, rather than
                # letting residual priming-driven force keep it "on" a while longer
                # under the normal hysteresis.
                if side == lag_side and just_ended_priming:
                    is_on = False

            if is_on != was_on:
                phase_onset_ms[side] = t_now
                # MOD_CUT_FORCE_TRIGGER: re-seed the noise filter at every phase
                # transition, not just stance onset -- otherwise it carries a stale,
                # lagging estimate from the just-ended phase into a new bout that may
                # be much shorter than the filter's own settling time.
                force_e_filt[side] = None
                if is_on:
                    stance_onset_ms[side] = t_now
                    # Fresh bout: forget the previous bout's peak (which may already
                    # be fatigue-depressed) and re-discover this bout's own peak from
                    # the (loading-scaled) seed, so its OFF threshold isn't biased by
                    # history.
                    peak_e_est[side] = peak_e_seed
                # MOD_CONSOLIDATE: gate on real bout-boundary events only --
                # priming and the lag-side's artificial priming-end reset are
                # experimental symmetry-breaking, not trained outcomes.
                if CONSOLIDATE and not priming and not (side == lag_side and just_ended_priming):
                    captured = consolidation_bout_event(side, genuine=not forced)
                    code = (1 if not forced else -1) * (2 if captured else 1)
                    pending_consolidation_event[side] = code

            cut_state[side] = is_on
            cut_force_apply(side, is_on, t_now)
            if CONSOLIDATE:
                consolidation_leak(side)

        for side in LEGS:
            cut_force_apply(side, cut_state[side], 0.0)

        n_chunks = int(SIM_MS // CHUNK_MS)
        tail_ms = q_ms(SIM_MS - n_chunks * CHUNK_MS)
        n_chunks_total = n_chunks + (1 if tail_ms > 1e-9 else 0)

        for ci in range(n_chunks_total):
            cur_chunk_ms = q_ms(CHUNK_MS if ci < n_chunks else tail_ms)
            if cur_chunk_ms <= 0.0:
                continue

            t_sim0 = time.perf_counter()
            nest.Simulate(cur_chunk_ms)
            sim_accum += (time.perf_counter() - t_sim0)

            t_ms += cur_chunk_ms
            done_steps += 1

            t_book0 = time.perf_counter()
            do_rate_update = (done_steps % rate_every == 0)
            for side in LEGS:
                is_on_now = 1.0 if cut_state[side] else 0.0
                update_leg(side, t_ms, cur_chunk_ms, is_on_now, do_rate_update)
                # Ground-truth CUT on/off per chunk -- avoids reconstructing bout
                # boundaries from a force threshold after the fact (which is
                # threshold-sensitive and was confirmed to give inconsistent
                # cap-vs-genuine-crossing verdicts on the same file depending on
                # the reconstruction threshold chosen). Exact bout durations from
                # this array can be compared to cut_max_stance/swing_ms exactly.
                logs[side]["cut_on"].append(is_on_now)
                if CONSOLIDATE:  # MOD_CONSOLIDATE: default no-event; overwritten below if one fired
                    logs[side]["consolidation_event"].append(0.0)
            if ENFORCE_TONIC_BS:
                l_be = float(logs["L"]["bs_e"][-1]); r_be = float(logs["R"]["bs_e"][-1])
                l_bf = float(logs["L"]["bs_f"][-1]); r_bf = float(logs["R"]["bs_f"][-1])
                if abs(l_be - r_be) > 1e-9 or abs(l_bf - r_bf) > 1e-9:
                    raise RuntimeError(
                        f"Tonic BS violated across legs at t_ms={t_ms}: L=({l_be},{l_bf}), R=({r_be},{r_bf})")
            log_weights(t_ms, done_steps)
            if do_rate_update:
                for side in LEGS:
                    cut_force_gate(side, t_ms)
                    if CONSOLIDATE and pending_consolidation_event[side] != 0:
                        # Overwrite this chunk's just-appended 0 with the event code
                        # detected by the gate call above (one-tick-late, same as
                        # the existing Ia sensor delay -- see cut_force_gate).
                        logs[side]["consolidation_event"][-1] = float(pending_consolidation_event[side])
                        pending_consolidation_event[side] = 0
            book_accum += (time.perf_counter() - t_book0)

            if rank == 0 and (
                    (done_steps % int(args.print_every) == 0) or (done_steps == total_steps)):
                print(f"[ForceCUT] chunk {done_steps}/{total_steps} | t={t_ms:.1f} ms | "
                      f"L={'stance' if cut_state['L'] else 'swing'} "
                      f"R={'stance' if cut_state['R'] else 'swing'} "
                      f"peak_e=({peak_e_est['L']:.1f},{peak_e_est['R']:.1f})")

    elif PACED_GAIT and GAIT_SCHEDULER == "phase":
        # PLAN.md P3 (MOD_PHASE_GAIT): per-leg phase schedule. Each leg is in stance for
        # PH_STANCE_MS = stance_fraction x stride, starting at its own touch-down phase
        # (L at 0, R at half a stride). stance_fraction > 0.5 overlaps the two stance
        # windows = double support (human walking ~0.60 -> ~10% of the stride at each
        # L/R transition); < 0.5 leaves a flight phase. Stance leg: CUT on (loading-
        # scaled) and the heel->mid->toe Ia-E groups stepping through ITS stance; swing
        # leg: CUT off, flexor swing afferent on. Unlike the halfcycle scheduler, the
        # CUT-driven extensor stretch is applied per leg, and cut_on is logged per leg.
        PH_T = STEP_PERIOD_MS
        PH_STANCE_MS = q_ms(PH_T * STANCE_FRAC)
        PH_SUB_MS = PH_STANCE_MS / max(1, N_IA_GROUPS_PACED)
        PH_OFFSET = {"L": 0.0, "R": q_ms(PH_T / 2.0)}

        def _phase_state(side, t):
            ph = (t - PH_OFFSET[side]) % PH_T
            if ph < PH_STANCE_MS - 1e-9:
                return (True, min(N_IA_GROUPS_PACED - 1, int(ph // PH_SUB_MS)))
            return (False, -1)

        _per_stride = {0.0}
        for side in LEGS:
            for k in range(N_IA_GROUPS_PACED + 1):
                _per_stride.add((PH_OFFSET[side] + k * PH_SUB_MS) % PH_T)
        _events = sorted({min(SIM_MS, q_ms(k * PH_T + e))
                          for k in range(int(np.ceil(SIM_MS / PH_T)) + 1) for e in _per_stride} | {SIM_MS})
        _applied = {side: None for side in LEGS}
        _stride_printed = -1
        for a, b in zip(_events[:-1], _events[1:]):
            if b - a <= 1e-9 or t_ms >= SIM_MS:
                continue
            ph_state = {side: _phase_state(side, 0.5 * (a + b)) for side in LEGS}
            for side in LEGS:
                if ph_state[side] == _applied[side]:
                    continue
                in_stance, g_idx = ph_state[side]
                nest.SetStatus(leg[side]["cut_pg"],
                               {"rate": CUT_FEEDBACK_GAIN * CUT_RATE_ON_HZ if in_stance else CUT_RATE_OFF_HZ})
                for gi, g in enumerate(leg[side]["ia_ext_pg_e"]):
                    nest.SetStatus(g, {"rate": IA_EXT_HZ[gi] if gi == g_idx else 0.0})
                if leg[side]["ia_ext_pg_f"] is not None:
                    nest.SetStatus(leg[side]["ia_ext_pg_f"], {"rate": 0.0 if in_stance else IA_EXT_F_HZ})
                _applied[side] = ph_state[side]
            on = {side: 1.0 if ph_state[side][0] else 0.0 for side in LEGS}
            run_window(min(b - a, SIM_MS - t_ms), cut_active_frac=on, log_cut_on=on)
            _stride = int(t_ms // PH_T)
            if rank == 0 and _stride != _stride_printed and (_stride % max(1, int(args.print_every)) == 0):
                _stride_printed = _stride
                print(f"[Phase] stride {_stride} t={t_ms:.0f}/{SIM_MS:.0f} ms "
                      f"L={'stance' if on['L'] else 'swing'} R={'stance' if on['R'] else 'swing'}")

    elif PACED_GAIT:
        # MOD_PACED_GAIT: explicit trot-pattern gait cycle.
        # Each half-cycle = HALF_MS (500 ms). L and R legs alternate 180°.
        # Stance leg: CUT ON + sequential Ia-E heel→toe activation.
        # Swing leg: CUT OFF, no ext-Ia → RGF bursts freely via IB + strong InF→RGE suppression.
        for hc in range(n_half_cycles):
            if t_ms >= SIM_MS:
                break
            stance = "L" if hc % 2 == 0 else "R"
            swing  = "R" if hc % 2 == 0 else "L"

            # Swing leg: clear extensor stance drive; engage the flexor swing-
            # afferent (MOD_FLEXOR_AFFERENT) to clock the swing-phase flexor.
            nest.SetStatus(leg[swing]["cut_pg"], {"rate": CUT_RATE_OFF_HZ})
            for g in leg[swing]["ia_ext_pg_e"]:
                nest.SetStatus(g, {"rate": 0.0})
            if leg[swing]["ia_ext_pg_f"] is not None:
                nest.SetStatus(leg[swing]["ia_ext_pg_f"], {"rate": IA_EXT_F_HZ})

            # Stance leg: CUT ON, scaled by loading-dependent cutaneous gain
            # (full at weight-bearing, attenuated at toe/air stepping); flexor
            # swing-afferent OFF (this leg is in stance).
            nest.SetStatus(leg[stance]["cut_pg"],
                           {"rate": CUT_FEEDBACK_GAIN * CUT_RATE_ON_HZ})
            if leg[stance]["ia_ext_pg_f"] is not None:
                nest.SetStatus(leg[stance]["ia_ext_pg_f"], {"rate": 0.0})

            # Sequential Ia-E sub-groups: heel (60 Hz) → mid (80 Hz) → toe (100 Hz)
            for g_idx in range(N_IA_GROUPS_PACED):
                ia_hz = IA_EXT_HZ[g_idx]
                nest.SetStatus(leg[stance]["ia_ext_pg_e"][g_idx], {"rate": ia_hz})
                if g_idx > 0:
                    nest.SetStatus(leg[stance]["ia_ext_pg_e"][g_idx - 1], {"rate": 0.0})
                sub_rem = min(SUB_STANCE_MS, SIM_MS - t_ms)
                if sub_rem <= 0.0:
                    break
                run_window(sub_rem, cut_active_frac=1.0)

            # Turn off all ext-Ia on stance leg (it becomes swing next half-cycle)
            for g in leg[stance]["ia_ext_pg_e"]:
                nest.SetStatus(g, {"rate": 0.0})

            # Residual swing window within this half-cycle (non-zero only when STANCE_FRAC < 0.5)
            if SWING_MS > 0.0:
                nest.SetStatus(leg[stance]["cut_pg"], {"rate": CUT_RATE_OFF_HZ})
                swing_rem = min(SWING_MS, SIM_MS - t_ms)
                if swing_rem > 0.0:
                    run_window(swing_rem, cut_active_frac=0.0)

            if rank == 0 and (hc % max(1, int(args.print_every)) == 0 or hc == n_half_cycles - 1):
                print(f"[Paced] hc {hc + 1}/{n_half_cycles} stance={stance} "
                      f"t={t_ms:.0f}/{SIM_MS:.0f} ms step={done_steps}/{total_steps}")
    else:
        # Original N_PHASES rotating CUT loop
        chunk_cut = max(1, int(N_CUT / N_PHASES))
        for phase in range(N_PHASES):
            for side in LEGS:
                nest.SetStatus(leg[side]["cut_pg"], {"rate": CUT_RATE_OFF_HZ})

            start = phase * chunk_cut
            end = min(N_CUT, (phase + 1) * chunk_cut)
            for side in LEGS:
                nest.SetStatus(leg[side]["cut_pg"][start:end],
                               {"rate": CUT_FEEDBACK_GAIN * CUT_RATE_ON_HZ})
            cut_active_frac = float(end - start) / float(N_CUT)

            n_chunks = int(PHASE_MS // CHUNK_MS)
            tail_ms = q_ms(PHASE_MS - n_chunks * CHUNK_MS)
            n_chunks_total = n_chunks + (1 if tail_ms > 1e-9 else 0)

            for local_chunk in range(n_chunks_total):
                cur_chunk_ms = q_ms(CHUNK_MS if local_chunk < n_chunks else tail_ms)
                if cur_chunk_ms <= 0.0:
                    continue

                t_sim0 = time.perf_counter()
                nest.Simulate(cur_chunk_ms)
                sim_accum += (time.perf_counter() - t_sim0)

                t_ms += cur_chunk_ms
                done_steps += 1

                t_book0 = time.perf_counter()
                do_rate_update = (done_steps % rate_every == 0)
                for side in LEGS:
                    update_leg(side, t_ms, cur_chunk_ms, cut_active_frac, do_rate_update)
                if ENFORCE_TONIC_BS:
                    l_be = float(logs["L"]["bs_e"][-1]); r_be = float(logs["R"]["bs_e"][-1])
                    l_bf = float(logs["L"]["bs_f"][-1]); r_bf = float(logs["R"]["bs_f"][-1])
                    if abs(l_be - r_be) > 1e-9 or abs(l_bf - r_bf) > 1e-9:
                        raise RuntimeError(
                            f"Tonic BS violated across legs at t_ms={t_ms}: L=({l_be},{l_bf}), R=({r_be},{r_bf})")
                log_weights(t_ms, done_steps)
                book_accum += (time.perf_counter() - t_book0)

                if rank == 0 and (
                        (done_steps % int(args.print_every) == 0) or (done_steps == total_steps) or (local_chunk == 0)):
                    print(f"[Sim] Phase {phase + 1}/{N_PHASES} | chunk {done_steps}/{total_steps} | "
                          f"phase_chunk {local_chunk + 1}/{n_chunks_total} | t={t_ms:.1f} ms | chunk_ms={cur_chunk_ms:.1f}")

    if rank == 0:
        wall = time.time() - t0
        print(f"[Done] wall={wall:.1f}s, out={args.out}")
        tot = max(1e-9, (sim_accum + book_accum))
        print(
            f"[Timing] nest.Simulate: {sim_accum:.1f}s ({100.0 * sim_accum / tot:.1f}%) | bookkeeping: {book_accum:.1f}s ({100.0 * book_accum / tot:.1f}%)")

    # Capture final full weight vectors once (after simulation) if requested.
    # Note: in "final" mode we store both initial (t=0) and final (t=end) snapshots.
    if rank == 0 and args.save_weights == "final":
        wfull_times.append(float(t_ms))
        for side in LEGS:
            for key in plastic_keys:
                conns = conns_full_cache[side][key]
                if conns is None or len(conns) == 0:
                    wfull[side][key].append(np.array([], dtype=np.float32))
                else:
                    w = np.asarray(nest.GetStatus(conns, "weight"), dtype=np.float32)
                    wfull[side][key].append(w)

    # ---- write HDF5 (rank 0 only) ----
    if rank != 0:
        return

    times_arr = np.asarray(times, dtype=np.float32)

    with h5py.File(args.out, "w") as h5:
        h5.attrs["created_utc"] = datetime.utcnow().isoformat() + "Z"
        h5.attrs["nest_version"] = str(nest.__version__)
        h5.attrs["nest_rng_seed"] = int(NEST_RNG_SEED)  # B12: always recorded
        h5.attrs["sim_ms"] = SIM_MS
        h5.attrs["dt_ms"] = CHUNK_MS
        h5.attrs["inner_dt_ms"] = DT_MS
        h5.attrs["resolution_ms"] = float(args.resolution_ms)
        h5.attrs["phases"] = int(N_PHASES)
        h5.attrs["bs_osc_hz"] = float(BS_OSC_HZ)
        h5.attrs["bs_rate_base_hz"] = float(BS_RATE_BASE_HZ)
        h5.attrs["bs_noise_std_hz"] = float(BS_NOISE_STD_HZ)
        h5.attrs["enforce_tonic_bs"] = bool(ENFORCE_TONIC_BS)
        h5.attrs["paced_gait"] = bool(PACED_GAIT)
        if PACED_GAIT:
            h5.attrs["step_period_ms"] = float(STEP_PERIOD_MS)
            h5.attrs["half_ms"] = float(HALF_MS)
            h5.attrs["n_ia_groups"] = int(N_IA_GROUPS_PACED)
            h5.attrs["ia_ext_f_hz"] = float(IA_EXT_F_HZ)
            if GAIT_SCHEDULER == "phase" and CUT_TRIGGER != "force":  # PLAN.md P3; halfcycle keeps old attrs
                h5.attrs["gait_scheduler"] = "phase"
                h5.attrs["stance_fraction"] = float(STANCE_FRAC)
                h5.attrs["stance_ms"] = float(PH_STANCE_MS)
                h5.attrs["double_support_frac_nominal"] = float(max(0.0, 2.0 * STANCE_FRAC - 1.0))
        h5.attrs["cut_trigger"] = str(CUT_TRIGGER)
        if CUT_TRIGGER == "force":
            h5.attrs["cut_force_on_frac"] = float(CUT_FORCE_ON_FRAC)
            h5.attrs["cut_force_off_frac"] = float(CUT_FORCE_OFF_FRAC)
            h5.attrs["cut_force_filter_tau_ms"] = float(CUT_FORCE_FILTER_TAU_MS)
            h5.attrs["leading_leg"] = str(LEADING_LEG)
            h5.attrs["lead_offset_ms"] = float(LEAD_OFFSET_MS)
            h5.attrs["cut_max_stance_ms"] = float(CUT_MAX_STANCE_MS)
            h5.attrs["cut_max_swing_ms"] = float(CUT_MAX_SWING_MS)
        h5.attrs["consolidate"] = bool(CONSOLIDATE)  # MOD_CONSOLIDATE
        if CONSOLIDATE:
            h5.attrs["consolidate_tau_tag_ms"] = float(CONSOLIDATE_TAU_TAG_MS)
            h5.attrs["consolidate_prp_threshold"] = float(CONSOLIDATE_PRP_THRESHOLD)
            h5.attrs["consolidate_prp_gain_genuine"] = float(CONSOLIDATE_PRP_GAIN_GENUINE)
            h5.attrs["consolidate_prp_gain_forced"] = float(CONSOLIDATE_PRP_GAIN_FORCED)
            h5.attrs["consolidate_wmax_ia_growth_per_capture"] = float(CONSOLIDATE_WMAX_IA_GROWTH)  # MOD_WMAX_GROWTH
            h5.attrs["consolidate_wmax_ia_ceiling"] = float(CONSOLIDATE_WMAX_IA_CEILING)
        h5.attrs["muscle_fatigue"] = bool(MUSCLE_FATIGUE)
        if MUSCLE_FATIGUE:
            h5.attrs["fatigue_tau_onset_ms"] = float(FATIGUE_TAU_ONSET_MS)
            h5.attrs["leg_fatigue_asym_frac"] = float(LEG_FATIGUE_ASYM_FRAC)
            h5.attrs["fatigue_tau_recovery_ms"] = float(FATIGUE_TAU_RECOVERY_MS)
            h5.attrs["fatigue_max_frac"] = float(FATIGUE_MAX_FRAC)
        h5.attrs["ablate_ia_loop"] = bool(args.ablate_ia_loop)
        h5.attrs["ablate_asym"] = bool(args.ablate_asym)
        h5.attrs["ablate_comm"] = bool(args.ablate_comm)
        h5.attrs["ablation_tag"] = ",".join(ablation_tag) if ablation_tag else "baseline"
        h5.attrs["ia_feedback_gain"] = float(IA_FEEDBACK_GAIN)
        h5.attrs["cut_feedback_gain"] = float(CUT_FEEDBACK_GAIN)
        h5.attrs["stdp_lambda"] = float(LAMBDA)
        h5.attrs["freeze_bs_rg"] = bool(getattr(args, "freeze_bs_rg", False))   # MOD_FREEZE_BS
        h5.attrs["ia_rg_stdp_always_on"] = True                                 # MOD_IA_RG_STDP: Ia->RG-E/F now a standing plastic pathway, not opt-in
        h5.attrs["wmax_ia"] = float(WMAX_IA_BASE)
        h5.attrs["wmax_ia_unloaded"] = float(WMAX_IA_UNLOADED_EFF)
        h5.attrs["wmax_ia_effective"] = float(EFFECTIVE_WMAX_IA)               # MOD_IA_RG_LOADING_GAIN
        h5.attrs["p_ia2rg"] = float(getattr(args, "p_ia2rg", P_IA2RG_STDP))
        h5.attrs["static_weight_cv"] = float(getattr(args, "static_weight_cv", 0.0) or 0.0)
        h5.attrs["cut_static_w"] = float(getattr(args, "cut_static_w", 0.0))
        h5.attrs["local_threads"] = int(args.threads)
        h5.attrs["mpi_processes"] = int(nproc)
        h5.attrs["save_weights_mode"] = str(args.save_weights)
        h5.attrs["delay_model"] = str(getattr(args, "delay_model", "fixed"))
        h5.attrs["species"] = str(getattr(args, "species", "rat"))
        h5.attrs["delay_jitter_ms"] = float(getattr(args, "delay_jitter_ms", 0.0))
        h5.attrs["delay_scale"] = float(getattr(args, "delay_scale", 1.0))
        write_species_provenance(h5, SPECIES_CFG, out_path=args.out)
        if PROBE_RECS:  # PLAN.md P2 reflex-latency probe
            gp = h5.create_group("probe")
            gp.attrs["volley_ms"] = float(PROBE_VOLLEY_MS)
            gp.attrs["resolution_ms"] = float(RES_MS)
            for _name, _rec in PROBE_RECS.items():
                _ev = nest.GetStatus(_rec, "events")[0]
                _order = np.lexsort((np.asarray(_ev["senders"]), np.asarray(_ev["times"])))
                gp.create_dataset(f"{_name}_times", data=np.asarray(_ev["times"], dtype=np.float64)[_order])
                gp.create_dataset(f"{_name}_senders", data=np.asarray(_ev["senders"], dtype=np.int64)[_order])
        # Sweep metadata (if active)
        if ("sweep_active" in locals()) and sweep_active:
            h5.attrs["sweep_active"] = True
            h5.attrs["sweep_idx"] = int(sweep_idx)
            h5.attrs["winit_mu"] = float(sweep_mu)
            h5.attrs["winit_cv"] = float(sweep_cv)
            h5.attrs["winit_sigma"] = float(sweep_sigma)
            h5.attrs["winit_dist"] = str(args.stdp_winit_dist)
            h5.attrs["seed"] = int(run_seed)
            if "SLURM_JOB_ID" in os.environ:
                h5.attrs["slurm_job_id"] = str(os.environ.get("SLURM_JOB_ID"))
            if "SLURM_ARRAY_TASK_ID" in os.environ:
                h5.attrs["slurm_array_task_id"] = str(os.environ.get("SLURM_ARRAY_TASK_ID"))
        else:
            h5.attrs["sweep_active"] = False

        gstats = h5.create_group("stats")
        for k, v in stats_nodes.items():
            gstats.attrs[f"nodes_{k}"] = int(v)
        for k, v in stats_syn_sign.items():
            gstats.attrs[f"syn_{k}"] = int(v)
        for k, v in stats_syn_models.items():
            gstats.attrs[k] = int(v)

        h5.create_dataset("times_ms", data=times_arr, compression="gzip")
        if len(wfull_times) > 0:
            h5.create_dataset("weights_times_ms", data=np.asarray(wfull_times, dtype=np.float32), compression="gzip")

        for side in LEGS:
            g = h5.create_group(f"leg_{side}")
            for key, arr in logs[side].items():
                g.create_dataset(key, data=np.asarray(arr, dtype=np.float32), compression="gzip")

            gw = g.create_group("weights")
            for key in plastic_keys:
                gw.create_dataset(f"{key}_mean", data=np.asarray(wstats[side][key][0], dtype=np.float32),
                                  compression="gzip")
                gw.create_dataset(f"{key}_std", data=np.asarray(wstats[side][key][1], dtype=np.float32),
                                  compression="gzip")

            # MOD_CONSOLIDATE: captured-baseline mean/std + shared prp_pool trace,
            # one group per leg alongside "weights" (only written when enabled).
            if CONSOLIDATE:
                gc = g.create_group("consolidation")
                for key in consolidate_keys:
                    gc.create_dataset(f"{key}_baseline_mean",
                                      data=np.asarray(consolidate_stats[side][key][0], dtype=np.float32),
                                      compression="gzip")
                    gc.create_dataset(f"{key}_baseline_std",
                                      data=np.asarray(consolidate_stats[side][key][1], dtype=np.float32),
                                      compression="gzip")
                    gc.create_dataset(f"{key}_prp_pool",
                                      data=np.asarray(prp_log[side][key], dtype=np.float32),
                                      compression="gzip")
                for key in wmax_ia_growth_keys:  # MOD_WMAX_GROWTH
                    gc.create_dataset(f"{key}_wmax",
                                      data=np.asarray(wmax_ia_log[side][key], dtype=np.float32),
                                      compression="gzip")

            # Optional: full weight vectors (shape: [T_samples, N_connections])
            if len(wfull_times) > 0:
                gfw = g.create_group("full_weights")
                for key in plastic_keys:
                    src, tgt = conns_endpoints[side].get(key, (np.array([], dtype=np.int64), np.array([], dtype=np.int64)))
                    gk = gfw.create_group(key.replace("->", "_to_"))
                    gk.create_dataset("source", data=src, compression="gzip")
                    gk.create_dataset("target", data=tgt, compression="gzip")

                    if len(wfull[side][key]) > 0:
                        if wfull[side][key][0].size == 0:
                            wmat = np.zeros((len(wfull[side][key]), 0), dtype=np.float32)
                        else:
                            wmat = np.stack(wfull[side][key], axis=0).astype(np.float32, copy=False)
                        gk.create_dataset("w", data=wmat, compression="gzip")

    print(f"[HDF5] saved {args.out}")


if __name__ == "__main__":
    main()