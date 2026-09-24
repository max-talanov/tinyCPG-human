#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cpg_2legs_nest_to_hdf5.py
Run the 2-leg CPG NEST simulation headlessly (HPC-friendly) and save all time-series
(and basic network stats) into an HDF5 file for later plotting on a local machine.

Example:
  python3 cpg_2legs_nest_to_hdf5.py --out cpg_run.h5 --sim-ms 10000 --dt-ms 10 --threads 10

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

# ---------- CUT training ----------
N_PHASES = 6
CUT_RATE_ON_HZ = 200.0
CUT_RATE_OFF_HZ = 0.0

# ---------- brainstem ----------
BS_OSC_HZ = 1.0
BS_RATE_BASE_HZ = 0.0
BS_RATE_AMP_HZ = 300.0
BS_RATE_MIN_HZ = 0.0
BS_PHASE = {"L": 0.0, "R": np.pi}  # left-right alternation

# ---------- connectivity ----------
P_IN_STDP = 0.5
P_RG_REC = 0.12
DELAY_MS = 1.0

P_RG_RECIP = 0.20
W_RG_RECIP = -18.0
DELAY_RECIP_MS = 1.0

W_M2MUS = 1.0
P_M2MUS = 0.8

IA2RG_P = 0.4
IA2RG_W = 12.0

BASE_DRIVE_HZ = 10.0
BASE_DRIVE_W = 18.0
BASE_DRIVE_P = 0.08

USE_STATIC_PARALLEL = False
P_STATIC_IN = 0.03
P_STATIC_RM = 0.03
W_STATIC_IN = 22.0
W_STATIC_RM = 35.0

ENABLE_COMMISSURAL = True
P_COMM = 0.08
W_COMM_INH = -10.0
DELAY_COMM_MS = 1.0

# ---------- STDP ----------
TAU_PLUS = 20.0
LAMBDA = 0.002
ALPHA = 1.05
MU_PLUS = 0.0
MU_MINUS = 0.0
WMAX = 120.0

W0_IN = 22.0
W0_RM = 30.0

# ---------- Izhikevich ----------
izh_params = dict(a=0.02, b=0.2, c=-65.0, d=8.0, V_th=30.0, V_min=-120.0)
I_E_RG = 1.0
I_E_MOTOR = 1.0

# ---------- muscle proxies ----------
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

# ---------- Ia ----------
IA_BASE_HZ = 10.0
IA_K_FORCE = 6.0
IA_K_STRETCH = 250.0
IA_RATE_MAX_HZ = 500.0


def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def bs_rates_counterphase(t_ms: float, leg: str) -> tuple[float, float]:
    t_s = t_ms / 1000.0
    s = np.sin(2.0 * np.pi * BS_OSC_HZ * t_s + BS_PHASE[leg])
    e = max(0.0, s)
    f = max(0.0, -s)
    r_e = BS_RATE_BASE_HZ + BS_RATE_AMP_HZ * e
    r_f = BS_RATE_BASE_HZ + BS_RATE_AMP_HZ * f
    r_e = clamp(r_e, BS_RATE_MIN_HZ, BS_RATE_BASE_HZ + BS_RATE_AMP_HZ)
    r_f = clamp(r_f, BS_RATE_MIN_HZ, BS_RATE_BASE_HZ + BS_RATE_AMP_HZ)
    return r_e, r_f


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default="cpg_run.h5")
    ap.add_argument("--sim-ms", type=float, default=10000.0)
    ap.add_argument("--dt-ms", type=float, default=10.0)
    ap.add_argument("--threads", type=int, default=10)
    ap.add_argument("--print-every", type=int, default=50, help="progress cadence in steps")
    ap.add_argument("--weight-sample-ms", type=float, default=100.0, help="How often to sample STDP weights (ms). Larger = faster.")
    ap.add_argument("--rate-update-ms", type=float, default=20.0, help="How often to push updated rates to poisson_generators (ms). Larger = faster.")
    args = ap.parse_args()

    SIM_MS = float(args.sim_ms)
    DT_MS = float(args.dt_ms)
    PHASE_MS = SIM_MS / int(N_PHASES)

    weight_every = max(1, int(round(float(args.weight_sample_ms) / DT_MS)))
    rate_every = max(1, int(round(float(args.rate_update_ms) / DT_MS)))

    nest.ResetKernel()
    nest.SetKernelStatus({"resolution": 0.1, "local_num_threads": int(args.threads), "print_time": False})

    # Robust rank/proc detection:
    # - under Slurm, SLURM_PROCID/SLURM_NTASKS are the most reliable
    # - otherwise, fall back to NEST helpers if present
    if "SLURM_PROCID" in os.environ:
        rank = int(os.environ.get("SLURM_PROCID", "0"))
        nproc = int(os.environ.get("SLURM_NTASKS", "1"))
    else:
        rank = getattr(nest, "Rank", lambda: 0)()
        nproc = getattr(nest, "NumProcesses", lambda: 1)()

    if rank == 0:
        print(f"[NEST] processes={nproc} | local_threads={nest.GetKernelStatus('local_num_threads')}")
        print(f"[Run] sim_ms={SIM_MS} dt_ms={DT_MS} phases={N_PHASES} phase_ms={PHASE_MS:.2f}")

    # ---- build per-leg ----
    leg = {}
    for side in LEGS:
        cut_pg = nest.Create("poisson_generator", N_CUT)
        cut_in = nest.Create("parrot_neuron", N_CUT)
        nest.Connect(cut_pg, cut_in, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(cut_pg, {"rate": CUT_RATE_OFF_HZ})

        bs_pg_e = nest.Create("poisson_generator", N_BS)
        bs_in_e = nest.Create("parrot_neuron", N_BS)
        nest.Connect(bs_pg_e, bs_in_e, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(bs_pg_e, {"rate": BS_RATE_BASE_HZ})

        bs_pg_f = nest.Create("poisson_generator", N_BS)
        bs_in_f = nest.Create("parrot_neuron", N_BS)
        nest.Connect(bs_pg_f, bs_in_f, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(bs_pg_f, {"rate": BS_RATE_BASE_HZ})

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

        rg_e = nest.Create("izhikevich", N_RG_E)
        rg_f = nest.Create("izhikevich", N_RG_F)
        m_e = nest.Create("izhikevich", N_MOTOR_E)
        m_f = nest.Create("izhikevich", N_MOTOR_F)
        for pop in (rg_e, rg_f, m_e, m_f):
            nest.SetStatus(pop, izh_params)
        nest.SetStatus(rg_e, {"V_m": -65.0, "U_m": 0.2 * (-65.0), "I_e": I_E_RG})
        nest.SetStatus(rg_f, {"V_m": -65.0, "U_m": 0.2 * (-65.0), "I_e": I_E_RG})
        nest.SetStatus(m_e, {"V_m": -65.0, "U_m": 0.2 * (-65.0), "I_e": I_E_MOTOR})
        nest.SetStatus(m_f, {"V_m": -65.0, "U_m": 0.2 * (-65.0), "I_e": I_E_MOTOR})

        mus_e = nest.Create("parrot_neuron", N_MUS_E)
        mus_f = nest.Create("parrot_neuron", N_MUS_F)
        rec_muse = nest.Create("spike_recorder", params={"record_to": "memory"})
        rec_musf = nest.Create("spike_recorder", params={"record_to": "memory"})
        nest.Connect(mus_e, rec_muse)
        nest.Connect(mus_f, rec_musf)

        leg[side] = dict(
            cut_pg=cut_pg, cut_in=cut_in,
            bs_pg_e=bs_pg_e, bs_in_e=bs_in_e,
            bs_pg_f=bs_pg_f, bs_in_f=bs_in_f,
            base_pg=base_pg, base_in=base_in,
            ia_pg_e=ia_pg_e, ia_in_e=ia_in_e,
            ia_pg_f=ia_pg_f, ia_in_f=ia_in_f,
            rg_e=rg_e, rg_f=rg_f, m_e=m_e, m_f=m_f,
            mus_e=mus_e, mus_f=mus_f,
            rec_muse=rec_muse, rec_musf=rec_musf
        )

    # ---- STDP models ----
    stdp_defaults = {
        "tau_plus": TAU_PLUS,
        "lambda": LAMBDA,  # <-- key is a string, so it's fine
        "alpha": ALPHA,
        "mu_plus": MU_PLUS,
        "mu_minus": MU_MINUS,
        "Wmax": WMAX,
    }

    for side in LEGS:
        def copy(name, wr):
            if wr is not None:
                nest.CopyModel("stdp_synapse", name, {**stdp_defaults, "weight_recorder": wr})
            else:
                nest.CopyModel("stdp_synapse", name, stdp_defaults)

        copy(f"stdp_cut_rge_{side}", make_weight_recorder_safe())
        copy(f"stdp_bs_rge_{side}", make_weight_recorder_safe())
        copy(f"stdp_bs_rgf_{side}", make_weight_recorder_safe())
        copy(f"stdp_rge_me_{side}", make_weight_recorder_safe())
        copy(f"stdp_rgf_mf_{side}", make_weight_recorder_safe())

    # ---- connect per leg ----
    for side in LEGS:
        L = leg[side]

        nest.Connect(L["cut_in"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": f"stdp_cut_rge_{side}", "weight": W0_IN, "delay": DELAY_MS})

        nest.Connect(L["bs_in_e"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": f"stdp_bs_rge_{side}", "weight": W0_IN, "delay": DELAY_MS})
        nest.Connect(L["bs_in_f"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": f"stdp_bs_rgf_{side}", "weight": W0_IN, "delay": DELAY_MS})

        nest.Connect(L["base_in"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": BASE_DRIVE_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": BASE_DRIVE_W, "delay": DELAY_MS})
        nest.Connect(L["base_in"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": BASE_DRIVE_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": BASE_DRIVE_W, "delay": DELAY_MS})

        nest.Connect(L["rg_e"], L["m_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": f"stdp_rge_me_{side}", "weight": W0_RM, "delay": DELAY_MS})
        nest.Connect(L["rg_f"], L["m_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": f"stdp_rgf_mf_{side}", "weight": W0_RM, "delay": DELAY_MS})

        nest.Connect(L["m_e"], L["mus_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_M2MUS},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_M2MUS, "delay": DELAY_MS})
        nest.Connect(L["m_f"], L["mus_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_M2MUS},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_M2MUS, "delay": DELAY_MS})

        nest.Connect(L["rg_e"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_REC},
                     syn_spec={"synapse_model": "static_synapse", "weight": 8.0, "delay": DELAY_MS})
        nest.Connect(L["rg_f"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_REC},
                     syn_spec={"synapse_model": "static_synapse", "weight": 8.0, "delay": DELAY_MS})

        nest.Connect(L["rg_e"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_RECIP},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_RG_RECIP, "delay": DELAY_RECIP_MS})
        nest.Connect(L["rg_f"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_RECIP},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_RG_RECIP, "delay": DELAY_RECIP_MS})

        nest.Connect(L["ia_in_e"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": IA2RG_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": IA2RG_W, "delay": DELAY_MS})
        nest.Connect(L["ia_in_f"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": IA2RG_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": IA2RG_W, "delay": DELAY_MS})

        if USE_STATIC_PARALLEL:
            nest.Connect(L["bs_in_e"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": DELAY_MS})
            nest.Connect(L["bs_in_f"], L["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": DELAY_MS})
            nest.Connect(L["cut_in"], L["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": DELAY_MS})
            nest.Connect(L["rg_e"], L["m_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_RM},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_RM, "delay": DELAY_MS})
            nest.Connect(L["rg_f"], L["m_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_RM},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_RM, "delay": DELAY_MS})

    # ---- commissural ----
    if ENABLE_COMMISSURAL:
        LL = leg["L"]; RR = leg["R"]
        nest.Connect(LL["rg_e"], RR["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_INH, "delay": DELAY_COMM_MS})
        nest.Connect(RR["rg_e"], LL["rg_f"], conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_INH, "delay": DELAY_COMM_MS})
        nest.Connect(LL["rg_f"], RR["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_INH, "delay": DELAY_COMM_MS})
        nest.Connect(RR["rg_f"], LL["rg_e"], conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_INH, "delay": DELAY_COMM_MS})

    # ---- stats (pre-sim) ----
    stats_nodes = node_model_counts(["izhikevich", "parrot_neuron", "poisson_generator", "spike_recorder", "weight_recorder"])
    stats_syn_sign = synapse_sign_stats()
    stats_syn_models = {
        "L_stdp_cut_rge": safe_len_connections(synapse_model="stdp_cut_rge_L"),
        "L_stdp_bs_rge": safe_len_connections(synapse_model="stdp_bs_rge_L"),
        "L_stdp_bs_rgf": safe_len_connections(synapse_model="stdp_bs_rgf_L"),
        "L_stdp_rge_me": safe_len_connections(synapse_model="stdp_rge_me_L"),
        "L_stdp_rgf_mf": safe_len_connections(synapse_model="stdp_rgf_mf_L"),
        "R_stdp_cut_rge": safe_len_connections(synapse_model="stdp_cut_rge_R"),
        "R_stdp_bs_rge": safe_len_connections(synapse_model="stdp_bs_rge_R"),
        "R_stdp_bs_rgf": safe_len_connections(synapse_model="stdp_bs_rgf_R"),
        "R_stdp_rge_me": safe_len_connections(synapse_model="stdp_rge_me_R"),
        "R_stdp_rgf_mf": safe_len_connections(synapse_model="stdp_rgf_mf_R"),
        "static_total": safe_len_connections(synapse_model="static_synapse"),
    }
    if rank == 0:
        print("[Stats] node_models:", stats_nodes)
        print("[Stats] syn_sign:", stats_syn_sign)
    print("[Stats] syn_models:", stats_syn_models)

    # ---- cache connection collections for faster weight sampling ----
    # NOTE: in MPI runs, each rank sees (and caches) its local connections.
    conns_cache = {side: {} for side in LEGS}
    for side in LEGS:
        conns_cache[side]["cut->rge"] = nest.GetConnections(synapse_model=f"stdp_cut_rge_{side}")
        conns_cache[side]["bs->rge"]  = nest.GetConnections(synapse_model=f"stdp_bs_rge_{side}")
        conns_cache[side]["bs->rgf"]  = nest.GetConnections(synapse_model=f"stdp_bs_rgf_{side}")
        conns_cache[side]["rge->me"]  = nest.GetConnections(synapse_model=f"stdp_rge_me_{side}")
        conns_cache[side]["rgf->mf"]  = nest.GetConnections(synapse_model=f"stdp_rgf_mf_{side}")

    # ---- storage ----
    times = []
    wstats = {side: {k: ([], []) for k in ["cut->rge", "bs->rge", "bs->rgf", "rge->me", "rgf->mf"]} for side in LEGS}
    logs = {side: dict(bs_e=[], bs_f=[], mus_e=[], mus_f=[],
                       act_e=[], act_f=[], force_e=[], force_f=[],
                       len_e=[], len_f=[], ia_e=[], ia_f=[]) for side in LEGS}
    state = {side: dict(act_e=0.0, act_f=0.0, force_e=0.0, force_f=0.0,
                        len_e=L0, len_f=L0, last_muse=0, last_musf=0) for side in LEGS}

    def new_spikes(rec, last_n):
        # Fast, constant-memory spike counting
        cur = int(nest.GetStatus(rec, "n_events")[0])
        return cur - last_n, cur

    def update_leg(side: str, t_ms: float, cut_active_frac: float, do_rate_update: bool):
        dt_s = DT_MS / 1000.0
        L = leg[side]
        S = state[side]
        P = logs[side]

        r_e, r_f = bs_rates_counterphase(t_ms, side)
        if do_rate_update:
            nest.SetStatus(L["bs_pg_e"], {"rate": r_e})
            nest.SetStatus(L["bs_pg_f"], {"rate": r_f})
        P["bs_e"].append(r_e); P["bs_f"].append(r_f)

        sp_e, cur_e = new_spikes(L["rec_muse"], S["last_muse"])
        sp_f, cur_f = new_spikes(L["rec_musf"], S["last_musf"])
        S["last_muse"] = cur_e; S["last_musf"] = cur_f

        r_muse = (sp_e / max(1, N_MUS_E)) / dt_s
        r_musf = (sp_f / max(1, N_MUS_F)) / dt_s
        P["mus_e"].append(r_muse); P["mus_f"].append(r_musf)

        tauA_s = TAU_ACT_MS / 1000.0
        target_ae = clamp(ACT_GAIN * r_muse, 0.0, ACT_MAX)
        target_af = clamp(ACT_GAIN * r_musf, 0.0, ACT_MAX)
        S["act_e"] += (dt_s / tauA_s) * (target_ae - S["act_e"])
        S["act_f"] += (dt_s / tauA_s) * (target_af - S["act_f"])

        target_fe = FORCE_MAX * (1.0 - np.exp(-FORCE_SAT_K * S["act_e"]))
        target_ff = FORCE_MAX * (1.0 - np.exp(-FORCE_SAT_K * S["act_f"]))
        tau_rise_s = TAU_FORCE_RISE_MS / 1000.0
        tau_decay_s = TAU_FORCE_DECAY_MS / 1000.0

        if target_fe > S["force_e"]:
            S["force_e"] += (dt_s / tau_rise_s) * (target_fe - S["force_e"])
        else:
            S["force_e"] += (dt_s / tau_decay_s) * (target_fe - S["force_e"])

        if target_ff > S["force_f"]:
            S["force_f"] += (dt_s / tau_rise_s) * (target_ff - S["force_f"])
        else:
            S["force_f"] += (dt_s / tau_decay_s) * (target_ff - S["force_f"])

        S["force_e"] = clamp(S["force_e"], 0.0, FORCE_MAX)
        S["force_f"] = clamp(S["force_f"], 0.0, FORCE_MAX)

        tauL_s = TAU_LENGTH_MS / 1000.0
        S["len_e"] += (dt_s / tauL_s) * (L0 - S["len_e"])
        S["len_f"] += (dt_s / tauL_s) * (L0 - S["len_f"])
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
        ia_e = clamp(ia_e, 0.0, IA_RATE_MAX_HZ)
        ia_f = clamp(ia_f, 0.0, IA_RATE_MAX_HZ)
        if do_rate_update:
            nest.SetStatus(L["ia_pg_e"], {"rate": ia_e})
            nest.SetStatus(L["ia_pg_f"], {"rate": ia_f})

        P["act_e"].append(S["act_e"]); P["act_f"].append(S["act_f"])
        P["force_e"].append(S["force_e"]); P["force_f"].append(S["force_f"])
        P["len_e"].append(S["len_e"]); P["len_f"].append(S["len_f"])
        P["ia_e"].append(ia_e); P["ia_f"].append(ia_f)

    # Keep last sampled mean/std so we can append smoothly without resampling every step
    last_wstats = {side: {k: (np.nan, np.nan) for k in ["cut->rge", "bs->rge", "bs->rgf", "rge->me", "rgf->mf"]} for side in LEGS}

    def log_weights(t_ms: float, step_idx: int):
        """Append weight mean/std time series.
        To accelerate, only sample actual weights every `weight_every` steps, and reuse last values otherwise.
        """
        times.append(t_ms)
        do_sample = (step_idx % weight_every == 0)

        for side in LEGS:
            for key in ["cut->rge", "bs->rge", "bs->rgf", "rge->me", "rgf->mf"]:
                if do_sample:
                    conns = conns_cache[side][key]
                    if len(conns) == 0:
                        last_wstats[side][key] = (np.nan, np.nan)
                    else:
                        w = np.asarray(nest.GetStatus(conns, "weight"), dtype=float)
                        last_wstats[side][key] = (float(w.mean()), float(w.std()))
                mval, sval = last_wstats[side][key]
                wstats[side][key][0].append(mval)
                wstats[side][key][1].append(sval)

    total_steps = int(SIM_MS / DT_MS)
    done_steps = 0
    chunk = max(1, int(N_CUT / N_PHASES))
    t_ms = 0.0

    t0 = time.time()
    for phase in range(N_PHASES):
        for side in LEGS:
            nest.SetStatus(leg[side]["cut_pg"], {"rate": CUT_RATE_OFF_HZ})

        start = phase * chunk
        end = min(N_CUT, (phase + 1) * chunk)
        for side in LEGS:
            nest.SetStatus(leg[side]["cut_pg"][start:end], {"rate": CUT_RATE_ON_HZ})
        cut_active_frac = float(end - start) / float(N_CUT)

        n_steps = int(PHASE_MS / DT_MS)
        for local_step in range(n_steps):
            nest.Simulate(DT_MS)
            t_ms += DT_MS
            done_steps += 1

            for side in LEGS:
                do_rate_update = (done_steps % rate_every == 0)
                update_leg(side, t_ms, cut_active_frac, do_rate_update)
            log_weights(t_ms, done_steps)

            if rank == 0 and ((done_steps % int(args.print_every) == 0) or (done_steps == total_steps) or (local_step == 0)):
                print(f"[Sim] Phase {phase+1}/{N_PHASES} | step {done_steps}/{total_steps} | "
                      f"phase_step {local_step+1}/{n_steps} | t={t_ms:.1f} ms")

    if rank == 0:
        print(f"[Done] wall={time.time()-t0:.1f}s, out={args.out}")

    # ---- write HDF5 (rank 0 only) ----
    if rank != 0:
        return

    times_arr = np.asarray(times, dtype=np.float32)

    with h5py.File(args.out, "w") as h5:
        h5.attrs["created_utc"] = datetime.utcnow().isoformat() + "Z"
        h5.attrs["nest_version"] = str(nest.__version__)
        h5.attrs["sim_ms"] = SIM_MS
        h5.attrs["dt_ms"] = DT_MS
        h5.attrs["phases"] = int(N_PHASES)
        h5.attrs["bs_osc_hz"] = float(BS_OSC_HZ)
        h5.attrs["local_threads"] = int(args.threads)
        h5.attrs["mpi_processes"] = int(nproc)

        gstats = h5.create_group("stats")
        for k, v in stats_nodes.items():
            gstats.attrs[f"nodes_{k}"] = int(v)
        for k, v in stats_syn_sign.items():
            gstats.attrs[f"syn_{k}"] = int(v)
        for k, v in stats_syn_models.items():
            gstats.attrs[k] = int(v)

        h5.create_dataset("times_ms", data=times_arr, compression="gzip")

        for side in LEGS:
            g = h5.create_group(f"leg_{side}")
            for key, arr in logs[side].items():
                g.create_dataset(key, data=np.asarray(arr, dtype=np.float32), compression="gzip")

            gw = g.create_group("weights")
            for key in ["cut->rge", "bs->rge", "bs->rgf", "rge->me", "rgf->mf"]:
                gw.create_dataset(f"{key}_mean", data=np.asarray(wstats[side][key][0], dtype=np.float32), compression="gzip")
                gw.create_dataset(f"{key}_std", data=np.asarray(wstats[side][key][1], dtype=np.float32), compression="gzip")

    print(f"[HDF5] saved {args.out}")


if __name__ == "__main__":
    main()