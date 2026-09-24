#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2_stdp_izhi_nest.py (v4)

New changes vs v3:
A) Ia phase fix:
   - Ia "almost sinusoidal" modulation is now COUNTER-PHASE (E uses +sin, F uses -sin).
   - This prevents the shared sinus term from synchronizing Ia-E and Ia-F.

B) Reciprocal inhibition between RG centers (single leg):
   - Added RG-E -> RG-F inhibitory coupling
   - Added RG-F -> RG-E inhibitory coupling
   This matches the reciprocal inhibition idea in your diagram (for ONE leg).

Everything else kept from v3:
- BS counter-phase drive
- Two muscle groups (E has CUT, F no CUT), both with Ia
- Force/activation/length proxies and plots
- Motor synapse means on separate plot
"""

import nest
import numpy as np
import matplotlib.pyplot as plt

# ============================
# Sizes (your constraints)
# ============================
N_CUT = 100
N_BS = 100

N_RG_TOTAL = 200
N_RG_E = N_RG_TOTAL // 2
N_RG_F = N_RG_TOTAL - N_RG_E

N_MOTOR_E = 100
N_MOTOR_F = 100

N_IA_E = 100
N_IA_F = 100

# ============================
# Simulation timing
# ============================
SIM_MS = 6000.0
SAMPLE_DT_MS = 10.0

# ============================
# CUT stimulation (extensor only)
# ============================
N_PHASES = 6
PHASE_MS = SIM_MS / N_PHASES
CUT_RATE_ON_HZ = 200.0
CUT_RATE_OFF_HZ = 0.0

# ============================
# Brainstem drive (counter-phase ~1 Hz)
# ============================
BS_OSC_HZ = 1.0
BS_RATE_BASE_HZ = 0.0     # keep inactive side quiet
BS_RATE_AMP_HZ = 300.0
BS_RATE_MIN_HZ = 0.0

# ============================
# Connectivity
# ============================
P_IN_STDP = 0.5
P_RG_REC = 0.12
DELAY_MS = 1.0

# NEW: reciprocal inhibition between RG-E and RG-F (one leg)
P_RG_RECIP = 0.20
W_RG_RECIP = -18.0        # negative weight => inhibitory current for izhikevich
DELAY_RECIP_MS = 1.0

# Small baseline RG drive (insurance)
BASE_DRIVE_HZ = 10.0
BASE_DRIVE_W = 18.0
BASE_DRIVE_P = 0.08

# Optional static parallel paths (insurance)
USE_STATIC_PARALLEL = True
P_STATIC_IN = 0.03
P_STATIC_RM = 0.03
W_STATIC_IN = 22.0
W_STATIC_RM = 35.0

# ============================
# STDP params (plain, no DA)
# ============================
TAU_PLUS = 20.0
LAMBDA = 0.002
ALPHA = 1.05
MU_PLUS = 0.0
MU_MINUS = 0.0
WMAX = 120.0

W0_IN = 22.0
W0_RM = 30.0

# ============================
# Izhikevich neurons
# ============================
izh_params = {
    "a": 0.02,
    "b": 0.2,
    "c": -65.0,
    "d": 8.0,
    "V_th": 30.0,
    "V_min": -120.0,
}

I_E_RG = 1.0
I_E_MOTOR = 1.0

# ============================
# Muscle proxy: activation/force/length
# ============================
TAU_ACT_MS = 80.0
ACT_GAIN = 0.03
ACT_MAX = 1.2

TAU_FORCE_RISE_MS = 140.0
TAU_FORCE_DECAY_MS = 60.0
FORCE_MAX = 25.0
FORCE_SAT_K = 2.5

TAU_LENGTH_MS = 260.0
L0 = 1.0
L_MIN, L_MAX = 0.5, 2.0
SHORTEN_GAIN = 0.010
STRETCH_GAIN = 0.35  # extensor-only stretch from CUT fraction

# ============================
# Ia generator model
# ============================
IA_BASE_HZ = 10.0
IA_K_FORCE = 6.0
IA_K_STRETCH = 250.0
IA_RATE_MAX_HZ = 500.0

IA_SIN_MOD_HZ = 1.0
IA_SIN_MAX_DEPTH = 0.6


def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def bs_rates_counterphase(t_ms: float) -> tuple[float, float]:
    """Counter-phase BS: E gets +sin half-wave, F gets -sin half-wave."""
    t_s = t_ms / 1000.0
    s = np.sin(2.0 * np.pi * BS_OSC_HZ * t_s)
    e = max(0.0, s)
    f = max(0.0, -s)
    r_e = BS_RATE_BASE_HZ + BS_RATE_AMP_HZ * e
    r_f = BS_RATE_BASE_HZ + BS_RATE_AMP_HZ * f
    r_e = clamp(r_e, BS_RATE_MIN_HZ, BS_RATE_BASE_HZ + BS_RATE_AMP_HZ)
    r_f = clamp(r_f, BS_RATE_MIN_HZ, BS_RATE_BASE_HZ + BS_RATE_AMP_HZ)
    return r_e, r_f


def main():
    nest.ResetKernel()
    nest.SetKernelStatus({"resolution": 0.1})

    # Inputs: Poisson -> parrot
    cut_pg = nest.Create("poisson_generator", N_CUT)
    cut_in = nest.Create("parrot_neuron", N_CUT)
    nest.Connect(cut_pg, cut_in, conn_spec={"rule": "one_to_one"})

    bs_pg_e = nest.Create("poisson_generator", N_BS)
    bs_in_e = nest.Create("parrot_neuron", N_BS)
    nest.Connect(bs_pg_e, bs_in_e, conn_spec={"rule": "one_to_one"})

    bs_pg_f = nest.Create("poisson_generator", N_BS)
    bs_in_f = nest.Create("parrot_neuron", N_BS)
    nest.Connect(bs_pg_f, bs_in_f, conn_spec={"rule": "one_to_one"})

    base_pg_e = nest.Create("poisson_generator", N_BS)
    base_in_e = nest.Create("parrot_neuron", N_BS)
    nest.Connect(base_pg_e, base_in_e, conn_spec={"rule": "one_to_one"})

    base_pg_f = nest.Create("poisson_generator", N_BS)
    base_in_f = nest.Create("parrot_neuron", N_BS)
    nest.Connect(base_pg_f, base_in_f, conn_spec={"rule": "one_to_one"})

    ia_pg_e = nest.Create("poisson_generator", N_IA_E)
    ia_in_e = nest.Create("parrot_neuron", N_IA_E)
    nest.Connect(ia_pg_e, ia_in_e, conn_spec={"rule": "one_to_one"})

    ia_pg_f = nest.Create("poisson_generator", N_IA_F)
    ia_in_f = nest.Create("parrot_neuron", N_IA_F)
    nest.Connect(ia_pg_f, ia_in_f, conn_spec={"rule": "one_to_one"})

    # init rates
    nest.SetStatus(cut_pg, {"rate": CUT_RATE_OFF_HZ})
    nest.SetStatus(bs_pg_e, {"rate": BS_RATE_BASE_HZ})
    nest.SetStatus(bs_pg_f, {"rate": BS_RATE_BASE_HZ})
    nest.SetStatus(base_pg_e, {"rate": BASE_DRIVE_HZ})
    nest.SetStatus(base_pg_f, {"rate": BASE_DRIVE_HZ})
    nest.SetStatus(ia_pg_e, {"rate": IA_BASE_HZ})
    nest.SetStatus(ia_pg_f, {"rate": IA_BASE_HZ})

    # Neurons
    rg_e = nest.Create("izhikevich", N_RG_E)
    rg_f = nest.Create("izhikevich", N_RG_F)
    m_e = nest.Create("izhikevich", N_MOTOR_E)
    m_f = nest.Create("izhikevich", N_MOTOR_F)

    for pop in (rg_e, rg_f, m_e, m_f):
        nest.SetStatus(pop, izh_params)

    nest.SetStatus(rg_e, {"V_m": -65.0, "U_m": 0.2 * (-65.0), "I_e": I_E_RG})
    nest.SetStatus(rg_f, {"V_m": -65.0, "U_m": 0.2 * (-65.0), "I_e": I_E_RG})
    nest.SetStatus(m_e,  {"V_m": -65.0, "U_m": 0.2 * (-65.0), "I_e": I_E_MOTOR})
    nest.SetStatus(m_f,  {"V_m": -65.0, "U_m": 0.2 * (-65.0), "I_e": I_E_MOTOR})

    # Spike recorders (motor only)
    rec_me = nest.Create("spike_recorder")
    rec_mf = nest.Create("spike_recorder")
    nest.Connect(m_e, rec_me)
    nest.Connect(m_f, rec_mf)

    # Weight recorders (optional)
    HAVE_WR = True
    try:
        wr_cut_rge = nest.Create("weight_recorder")
        wr_bs_rge = nest.Create("weight_recorder")
        wr_bs_rgf = nest.Create("weight_recorder")
        wr_rge_me = nest.Create("weight_recorder")
        wr_rgf_mf = nest.Create("weight_recorder")
    except Exception:
        HAVE_WR = False
        wr_cut_rge = wr_bs_rge = wr_bs_rgf = wr_rge_me = wr_rgf_mf = None

    stdp_defaults = {
        "tau_plus": TAU_PLUS,
        "lambda": LAMBDA,
        "alpha": ALPHA,
        "mu_plus": MU_PLUS,
        "mu_minus": MU_MINUS,
        "Wmax": WMAX,
    }

    def copy_stdp(name: str, wr):
        if HAVE_WR and wr is not None:
            nest.CopyModel("stdp_synapse", name, {**stdp_defaults, "weight_recorder": wr})
        else:
            nest.CopyModel("stdp_synapse", name, stdp_defaults)

    copy_stdp("stdp_cut_rge", wr_cut_rge)
    copy_stdp("stdp_bs_rge", wr_bs_rge)
    copy_stdp("stdp_bs_rgf", wr_bs_rgf)
    copy_stdp("stdp_rge_me", wr_rge_me)
    copy_stdp("stdp_rgf_mf", wr_rgf_mf)

    # Connections
    nest.Connect(
        cut_in, rg_e,
        conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
        syn_spec={"synapse_model": "stdp_cut_rge", "weight": W0_IN, "delay": DELAY_MS},
    )

    nest.Connect(
        bs_in_e, rg_e,
        conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
        syn_spec={"synapse_model": "stdp_bs_rge", "weight": W0_IN, "delay": DELAY_MS},
    )
    nest.Connect(
        bs_in_f, rg_f,
        conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
        syn_spec={"synapse_model": "stdp_bs_rgf", "weight": W0_IN, "delay": DELAY_MS},
    )

    # Baseline RG drive (static)
    nest.Connect(
        base_in_e, rg_e,
        conn_spec={"rule": "pairwise_bernoulli", "p": BASE_DRIVE_P},
        syn_spec={"synapse_model": "static_synapse", "weight": BASE_DRIVE_W, "delay": DELAY_MS},
    )
    nest.Connect(
        base_in_f, rg_f,
        conn_spec={"rule": "pairwise_bernoulli", "p": BASE_DRIVE_P},
        syn_spec={"synapse_model": "static_synapse", "weight": BASE_DRIVE_W, "delay": DELAY_MS},
    )

    # RG -> motor
    nest.Connect(
        rg_e, m_e,
        conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
        syn_spec={"synapse_model": "stdp_rge_me", "weight": W0_RM, "delay": DELAY_MS},
    )
    nest.Connect(
        rg_f, m_f,
        conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
        syn_spec={"synapse_model": "stdp_rgf_mf", "weight": W0_RM, "delay": DELAY_MS},
    )

    # Local RG recurrence (static; within-pop)
    nest.Connect(
        rg_e, rg_e,
        conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_REC},
        syn_spec={"synapse_model": "static_synapse", "weight": 8.0, "delay": DELAY_MS},
    )
    nest.Connect(
        rg_f, rg_f,
        conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_REC},
        syn_spec={"synapse_model": "static_synapse", "weight": 8.0, "delay": DELAY_MS},
    )

    # NEW: Reciprocal inhibition RG-E <-> RG-F (one leg)
    nest.Connect(
        rg_e, rg_f,
        conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_RECIP},
        syn_spec={"synapse_model": "static_synapse", "weight": W_RG_RECIP, "delay": DELAY_RECIP_MS},
    )
    nest.Connect(
        rg_f, rg_e,
        conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_RECIP},
        syn_spec={"synapse_model": "static_synapse", "weight": W_RG_RECIP, "delay": DELAY_RECIP_MS},
    )

    # Ia -> RG feedback (static excitatory)
    IA2RG_P = 0.4
    IA2RG_W = 12.0
    nest.Connect(
        ia_in_e, rg_e,
        conn_spec={"rule": "pairwise_bernoulli", "p": IA2RG_P},
        syn_spec={"synapse_model": "static_synapse", "weight": IA2RG_W, "delay": DELAY_MS},
    )
    nest.Connect(
        ia_in_f, rg_f,
        conn_spec={"rule": "pairwise_bernoulli", "p": IA2RG_P},
        syn_spec={"synapse_model": "static_synapse", "weight": IA2RG_W, "delay": DELAY_MS},
    )

    # Optional static parallel paths
    if USE_STATIC_PARALLEL:
        nest.Connect(
            bs_in_e, rg_e,
            conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
            syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": DELAY_MS},
        )
        nest.Connect(
            bs_in_f, rg_f,
            conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
            syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": DELAY_MS},
        )
        nest.Connect(
            cut_in, rg_e,
            conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
            syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": DELAY_MS},
        )
        nest.Connect(
            rg_e, m_e,
            conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_RM},
            syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_RM, "delay": DELAY_MS},
        )
        nest.Connect(
            rg_f, m_f,
            conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_RM},
            syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_RM, "delay": DELAY_MS},
        )

    # Weight sampling helper
    def sample_w(model_name: str) -> np.ndarray:
        conns = nest.GetConnections(synapse_model=model_name)
        if len(conns) == 0:
            return np.array([], dtype=float)
        return np.asarray(nest.GetStatus(conns, "weight"), dtype=float)

    # Closed-loop state
    act_e, act_f = 0.0, 0.0
    force_e, force_f = 0.0, 0.0
    len_e, len_f = L0, L0

    last_me_len = 0
    last_mf_len = 0

    times = []
    mean_std = {k: ([], []) for k in ["cut->rge", "bs->rge", "bs->rgf", "rge->me", "rgf->mf"]}

    bs_rate_e_trace, bs_rate_f_trace = [], []
    mot_rate_e, mot_rate_f = [], []
    act_trace_e, act_trace_f = [], []
    force_trace_e, force_trace_f = [], []
    len_trace_e, len_trace_f = [], []
    ia_rate_e, ia_rate_f = [], []

    def new_spikes(rec, last_len):
        ev = nest.GetStatus(rec, "events")[0]
        cur = len(ev["times"])
        return cur - last_len, cur

    def update_force_length_ia(t_ms: float, cut_active_frac: float):
        nonlocal act_e, act_f, force_e, force_f, len_e, len_f, last_me_len, last_mf_len
        dt_s = SAMPLE_DT_MS / 1000.0

        # Counter-phase BS update
        r_bs_e, r_bs_f = bs_rates_counterphase(t_ms)
        nest.SetStatus(bs_pg_e, {"rate": r_bs_e})
        nest.SetStatus(bs_pg_f, {"rate": r_bs_f})
        bs_rate_e_trace.append(r_bs_e)
        bs_rate_f_trace.append(r_bs_f)

        # Motor spikes -> rates
        sp_me, last_me_len2 = new_spikes(rec_me, last_me_len)
        sp_mf, last_mf_len2 = new_spikes(rec_mf, last_mf_len)
        last_me_len = last_me_len2
        last_mf_len = last_mf_len2
        r_me = (sp_me / max(1, N_MOTOR_E)) / dt_s
        r_mf = (sp_mf / max(1, N_MOTOR_F)) / dt_s

        # Activation LPF
        tauA_s = TAU_ACT_MS / 1000.0
        target_ae = clamp(ACT_GAIN * r_me, 0.0, ACT_MAX)
        target_af = clamp(ACT_GAIN * r_mf, 0.0, ACT_MAX)
        act_e += (dt_s / tauA_s) * (target_ae - act_e)
        act_f += (dt_s / tauA_s) * (target_af - act_f)

        # Force target: saturating
        target_fe = FORCE_MAX * (1.0 - np.exp(-FORCE_SAT_K * act_e))
        target_ff = FORCE_MAX * (1.0 - np.exp(-FORCE_SAT_K * act_f))

        tau_rise_s = TAU_FORCE_RISE_MS / 1000.0
        tau_decay_s = TAU_FORCE_DECAY_MS / 1000.0
        if target_fe > force_e:
            force_e += (dt_s / tau_rise_s) * (target_fe - force_e)
        else:
            force_e += (dt_s / tau_decay_s) * (target_fe - force_e)
        if target_ff > force_f:
            force_f += (dt_s / tau_rise_s) * (target_ff - force_f)
        else:
            force_f += (dt_s / tau_decay_s) * (target_ff - force_f)

        force_e = clamp(force_e, 0.0, FORCE_MAX)
        force_f = clamp(force_f, 0.0, FORCE_MAX)

        # Length dynamics
        tauL_s = TAU_LENGTH_MS / 1000.0
        len_e += (dt_s / tauL_s) * (L0 - len_e)
        len_f += (dt_s / tauL_s) * (L0 - len_f)
        len_e -= SHORTEN_GAIN * force_e * dt_s
        len_f -= SHORTEN_GAIN * force_f * dt_s
        if cut_active_frac > 0.0:
            len_e += STRETCH_GAIN * cut_active_frac * dt_s
        len_e = clamp(len_e, L_MIN, L_MAX)
        len_f = clamp(len_f, L_MIN, L_MAX)

        # Ia rates (counter-phase sinus modulation FIX)
        stretch_e = max(0.0, len_e - L0)
        stretch_f = max(0.0, len_f - L0)

        t_s = t_ms / 1000.0
        s = np.sin(2.0 * np.pi * IA_SIN_MOD_HZ * t_s)
        sin_mod_e = 0.5 * (1.0 + s)   # E in-phase
        sin_mod_f = 0.5 * (1.0 - s)   # F anti-phase

        depth_e = IA_SIN_MAX_DEPTH * (force_e / FORCE_MAX)
        depth_f = IA_SIN_MAX_DEPTH * (force_f / FORCE_MAX)
        amp_e = (1.0 - depth_e) + depth_e * sin_mod_e
        amp_f = (1.0 - depth_f) + depth_f * sin_mod_f

        rate_e = (IA_BASE_HZ + IA_K_FORCE * force_e + IA_K_STRETCH * stretch_e) * amp_e
        rate_f = (IA_BASE_HZ + IA_K_FORCE * force_f + IA_K_STRETCH * stretch_f) * amp_f
        rate_e = clamp(rate_e, 0.0, IA_RATE_MAX_HZ)
        rate_f = clamp(rate_f, 0.0, IA_RATE_MAX_HZ)

        nest.SetStatus(ia_pg_e, {"rate": rate_e})
        nest.SetStatus(ia_pg_f, {"rate": rate_f})

        # logs
        mot_rate_e.append(r_me)
        mot_rate_f.append(r_mf)
        act_trace_e.append(act_e)
        act_trace_f.append(act_f)
        force_trace_e.append(force_e)
        force_trace_f.append(force_f)
        len_trace_e.append(len_e)
        len_trace_f.append(len_f)
        ia_rate_e.append(rate_e)
        ia_rate_f.append(rate_f)

    def log_weights(t_ms: float):
        times.append(t_ms)

        def push(model, key):
            w = sample_w(model)
            if w.size == 0:
                mean_std[key][0].append(np.nan)
                mean_std[key][1].append(np.nan)
            else:
                mean_std[key][0].append(float(w.mean()))
                mean_std[key][1].append(float(w.std()))

        push("stdp_cut_rge", "cut->rge")
        push("stdp_bs_rge", "bs->rge")
        push("stdp_bs_rgf", "bs->rgf")
        push("stdp_rge_me", "rge->me")
        push("stdp_rgf_mf", "rgf->mf")

    # Run: chunked CUT phases
    chunk = max(1, int(N_CUT / N_PHASES))
    t = 0.0

    for phase in range(N_PHASES):
        nest.SetStatus(cut_pg, {"rate": CUT_RATE_OFF_HZ})
        start = phase * chunk
        end = min(N_CUT, (phase + 1) * chunk)
        nest.SetStatus(cut_pg[start:end], {"rate": CUT_RATE_ON_HZ})
        cut_active_frac = float(end - start) / float(N_CUT)

        n_steps = int(PHASE_MS / SAMPLE_DT_MS)
        for _ in range(n_steps):
            nest.Simulate(SAMPLE_DT_MS)
            t += SAMPLE_DT_MS
            update_force_length_ia(t, cut_active_frac)
            log_weights(t)

    times_arr = np.asarray(times)

    # Plots
    plt.figure(figsize=(14, 5))
    plt.plot(times_arr, bs_rate_e_trace, label="BS rate E (Hz)")
    plt.plot(times_arr, bs_rate_f_trace, label="BS rate F (Hz)")
    plt.xlabel("time (ms)")
    plt.ylabel("Hz")
    plt.title("Brainstem drive (counter-phase)")
    plt.legend()
    plt.tight_layout()
    plt.show()

    # Inputs learning
    plt.figure(figsize=(14, 7))
    for key, color in [
        ("cut->rge", "tab:blue"),
        ("bs->rge", "tab:orange"),
        ("bs->rgf", "tab:purple"),
    ]:
        m = np.asarray(mean_std[key][0])
        s = np.asarray(mean_std[key][1])
        plt.plot(times_arr, m, label=f"{key} mean", color=color)
        plt.fill_between(times_arr, m - s, m + s, color=color, alpha=0.15)
    plt.xlabel("time (ms)")
    plt.ylabel("weight (pA)")
    plt.title("STDP learning curves — inputs (mean ± std)")
    plt.legend()
    plt.tight_layout()
    plt.show()

    # Motor synapses means on separate plot
    plt.figure(figsize=(14, 6))
    plt.plot(times_arr, np.asarray(mean_std["rge->me"][0]), label="rge->me mean")
    plt.plot(times_arr, np.asarray(mean_std["rgf->mf"][0]), label="rgf->mf mean")
    plt.xlabel("time (ms)")
    plt.ylabel("weight (pA)")
    plt.title("STDP learning curves — motor synapses (means)")
    plt.legend()
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(14, 5))
    plt.plot(times_arr, mot_rate_e, label="M-E rate (Hz/neuron)")
    plt.plot(times_arr, mot_rate_f, label="M-F rate (Hz/neuron)")
    plt.xlabel("time (ms)")
    plt.ylabel("Hz/neuron")
    plt.title("Motor population rates (counter-phase expected)")
    plt.legend()
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(14, 5))
    plt.plot(times_arr, act_trace_e, label="Activation E")
    plt.plot(times_arr, act_trace_f, label="Activation F")
    plt.xlabel("time (ms)")
    plt.ylabel("a.u.")
    plt.title("Activation proxy (counter-phase expected)")
    plt.legend()
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(14, 5))
    plt.plot(times_arr, force_trace_e, label="Force E")
    plt.plot(times_arr, force_trace_f, label="Force F")
    plt.xlabel("time (ms)")
    plt.ylabel("force (a.u.)")
    plt.title("Force proxy (counter-phase expected)")
    plt.legend()
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(14, 5))
    plt.plot(times_arr, len_trace_e, label="Length E")
    plt.plot(times_arr, len_trace_f, label="Length F")
    plt.axhline(L0, linestyle="--", linewidth=1)
    plt.xlabel("time (ms)")
    plt.ylabel("length (a.u.)")
    plt.title("Length proxy (E has CUT stretch; both shorten with force)")
    plt.legend()
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(14, 5))
    plt.plot(times_arr, ia_rate_e, label="Ia-E rate (Hz)")
    plt.plot(times_arr, ia_rate_f, label="Ia-F rate (Hz)")
    plt.xlabel("time (ms)")
    plt.ylabel("Hz")
    plt.title("Ia generator rates (counter-phase modulation)")
    plt.legend()
    plt.tight_layout()
    plt.show()

    # Sanity
    ev_me = nest.GetStatus(rec_me, "events")[0]
    ev_mf = nest.GetStatus(rec_mf, "events")[0]
    print("ME spikes:", len(ev_me["times"]), "MF spikes:", len(ev_mf["times"]))
    if len(ev_me["times"]) == 0 and len(ev_mf["times"]) == 0:
        print("WARNING: motor pools are silent -> force will stay ~0.")
        print("Increase BS_RATE_AMP_HZ, W0_RM, BASE_DRIVE_W, or I_E_MOTOR.")


if __name__ == "__main__":
    main()
