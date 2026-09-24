#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2_stdp_izhi_nest.py (v6) — two legs, Ia driven by muscles, per-leg plots, progress + counts, 10 threads.

Changes vs v5:
1) Separate graphs for each leg (L and R) — no mixed-leg plots.
2) Add simulation progress logging: "Step X / Total_steps" (prints every N steps).
3) Increase simulation duration to 10_000 ms.
4) Log number of neurons and synapses (per leg + totals).
5) Start using MPI / 10 threads:
   - Script sets NEST local threads to 10 via KernelStatus.
   - For MPI, run with mpirun/mpiexec (NEST must be built with MPI):
       mpirun -np 2 python 2_stdp_izhi_nest.py
     Each MPI process will use local_num_threads=10.

NEST: 3.9.0
"""

import nest
import numpy as np
import matplotlib.pyplot as plt




def _fill_nans_forward(x: np.ndarray) -> np.ndarray:
    """Cheap NaN handling for trend plots: forward-fill, then back-fill ends."""
    x = np.asarray(x, dtype=float).copy()
    if not np.isnan(x).any():
        return x
    idx = np.where(~np.isnan(x))[0]
    if idx.size == 0:
        return x
    # back-fill start
    x[:idx[0]] = x[idx[0]]
    # forward-fill gaps
    for i in range(idx.size - 1):
        a, b = idx[i], idx[i + 1]
        if b > a + 1:
            x[a + 1:b] = x[a]
    # forward-fill end
    x[idx[-1] + 1:] = x[idx[-1]]
    return x

def moving_average(x, win: int):
    """Centered moving average for smooth 1s trends."""
    x = _fill_nans_forward(np.asarray(x, dtype=float))
    win = int(max(1, win))
    if win <= 1:
        return x
    kernel = np.ones(win, dtype=float) / win
    return np.convolve(x, kernel, mode="same")


def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def bs_rates_counterphase(t_ms: float, leg: str) -> tuple[float, float]:
    """
    Counter-phase BS within a leg, phase-shift between legs.
      E gets +sin half-wave
      F gets -sin half-wave
    """
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


def count_conns(**kwargs) -> int:
    """Safe connection counter."""
    try:
        return len(nest.GetConnections(**kwargs))
    except Exception:
        return -1


def main():
    # ---- Kernel setup: 10 threads
    nest.ResetKernel()
    nest.SetKernelStatus({
        "resolution": 0.1,
        "local_num_threads": 10,
        "print_time": False,
    })

    rank = getattr(nest, "Rank", lambda: 0)()
    nproc = getattr(nest, "NumProcesses", lambda: 1)()
    if rank == 0:
        print(f"[NEST] MPI processes: {nproc} | local_num_threads: {nest.GetKernelStatus('local_num_threads')}")

    # ----------------------------
    # Build per-leg structures
    # ----------------------------
    leg = {}
    for side in LEGS:
        # CUT
        cut_pg = nest.Create("poisson_generator", N_CUT)
        cut_in = nest.Create("parrot_neuron", N_CUT)
        nest.Connect(cut_pg, cut_in, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(cut_pg, {"rate": CUT_RATE_OFF_HZ})

        # BS inputs
        bs_pg_e = nest.Create("poisson_generator", N_BS)
        bs_in_e = nest.Create("parrot_neuron", N_BS)
        nest.Connect(bs_pg_e, bs_in_e, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(bs_pg_e, {"rate": BS_RATE_BASE_HZ})

        bs_pg_f = nest.Create("poisson_generator", N_BS)
        bs_in_f = nest.Create("parrot_neuron", N_BS)
        nest.Connect(bs_pg_f, bs_in_f, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(bs_pg_f, {"rate": BS_RATE_BASE_HZ})

        # Baseline drive
        base_pg = nest.Create("poisson_generator", N_BS)
        base_in = nest.Create("parrot_neuron", N_BS)
        nest.Connect(base_pg, base_in, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(base_pg, {"rate": BASE_DRIVE_HZ})

        # Ia devices
        ia_pg_e = nest.Create("poisson_generator", N_IA_E)
        ia_in_e = nest.Create("parrot_neuron", N_IA_E)
        nest.Connect(ia_pg_e, ia_in_e, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(ia_pg_e, {"rate": IA_BASE_HZ})

        ia_pg_f = nest.Create("poisson_generator", N_IA_F)
        ia_in_f = nest.Create("parrot_neuron", N_IA_F)
        nest.Connect(ia_pg_f, ia_in_f, conn_spec={"rule": "one_to_one"})
        nest.SetStatus(ia_pg_f, {"rate": IA_BASE_HZ})

        # Neuron populations
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

        # Muscle relays
        mus_e = nest.Create("parrot_neuron", N_MUS_E)
        mus_f = nest.Create("parrot_neuron", N_MUS_F)

        # Recorders: muscle only
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
            rg_e=rg_e, rg_f=rg_f,
            m_e=m_e, m_f=m_f,
            mus_e=mus_e, mus_f=mus_f,
            rec_muse=rec_muse, rec_musf=rec_musf,
        )

    # ----------------------------
    # STDP synapse models (+ optional weight recorders)
    # ----------------------------
    stdp_defaults = {
        "tau_plus": TAU_PLUS,
        "lambda": LAMBDA,
        "alpha": ALPHA,
        "mu_plus": MU_PLUS,
        "mu_minus": MU_MINUS,
        "Wmax": WMAX,
    }

    for side in LEGS:
        wr_cut = make_weight_recorder_safe()
        wr_bse = make_weight_recorder_safe()
        wr_bsf = make_weight_recorder_safe()
        wr_rge_me = make_weight_recorder_safe()
        wr_rgf_mf = make_weight_recorder_safe()

        def copy(name, wr):
            if wr is not None:
                nest.CopyModel("stdp_synapse", name, {**stdp_defaults, "weight_recorder": wr})
            else:
                nest.CopyModel("stdp_synapse", name, stdp_defaults)

        copy(f"stdp_cut_rge_{side}", wr_cut)
        copy(f"stdp_bs_rge_{side}", wr_bse)
        copy(f"stdp_bs_rgf_{side}", wr_bsf)
        copy(f"stdp_rge_me_{side}", wr_rge_me)
        copy(f"stdp_rgf_mf_{side}", wr_rgf_mf)

    # ----------------------------
    # Connect per-leg
    # ----------------------------
    for side in LEGS:
        L = leg[side]

        # CUT -> RG-E
        nest.Connect(L["cut_in"], L["rg_e"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": f"stdp_cut_rge_{side}", "weight": W0_IN, "delay": DELAY_MS})

        # BS -> RG-E / RG-F
        nest.Connect(L["bs_in_e"], L["rg_e"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": f"stdp_bs_rge_{side}", "weight": W0_IN, "delay": DELAY_MS})
        nest.Connect(L["bs_in_f"], L["rg_f"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": f"stdp_bs_rgf_{side}", "weight": W0_IN, "delay": DELAY_MS})

        # Baseline drive -> RG
        nest.Connect(L["base_in"], L["rg_e"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": BASE_DRIVE_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": BASE_DRIVE_W, "delay": DELAY_MS})
        nest.Connect(L["base_in"], L["rg_f"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": BASE_DRIVE_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": BASE_DRIVE_W, "delay": DELAY_MS})

        # RG -> motor (STDP)
        nest.Connect(L["rg_e"], L["m_e"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": f"stdp_rge_me_{side}", "weight": W0_RM, "delay": DELAY_MS})
        nest.Connect(L["rg_f"], L["m_f"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_IN_STDP},
                     syn_spec={"synapse_model": f"stdp_rgf_mf_{side}", "weight": W0_RM, "delay": DELAY_MS})

        # Motor -> muscle relay (static)
        nest.Connect(L["m_e"], L["mus_e"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_M2MUS},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_M2MUS, "delay": DELAY_MS})
        nest.Connect(L["m_f"], L["mus_f"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_M2MUS},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_M2MUS, "delay": DELAY_MS})

        # Local RG recurrence
        nest.Connect(L["rg_e"], L["rg_e"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_REC},
                     syn_spec={"synapse_model": "static_synapse", "weight": 8.0, "delay": DELAY_MS})
        nest.Connect(L["rg_f"], L["rg_f"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_REC},
                     syn_spec={"synapse_model": "static_synapse", "weight": 8.0, "delay": DELAY_MS})

        # Reciprocal inhibition inside leg
        nest.Connect(L["rg_e"], L["rg_f"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_RECIP},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_RG_RECIP, "delay": DELAY_RECIP_MS})
        nest.Connect(L["rg_f"], L["rg_e"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_RG_RECIP},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_RG_RECIP, "delay": DELAY_RECIP_MS})

        # Ia -> RG feedback
        nest.Connect(L["ia_in_e"], L["rg_e"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": IA2RG_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": IA2RG_W, "delay": DELAY_MS})
        nest.Connect(L["ia_in_f"], L["rg_f"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": IA2RG_P},
                     syn_spec={"synapse_model": "static_synapse", "weight": IA2RG_W, "delay": DELAY_MS})

        # Optional static parallel paths
        if USE_STATIC_PARALLEL:
            nest.Connect(L["bs_in_e"], L["rg_e"],
                         conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": DELAY_MS})
            nest.Connect(L["bs_in_f"], L["rg_f"],
                         conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": DELAY_MS})
            nest.Connect(L["cut_in"], L["rg_e"],
                         conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_IN},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_IN, "delay": DELAY_MS})
            nest.Connect(L["rg_e"], L["m_e"],
                         conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_RM},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_RM, "delay": DELAY_MS})
            nest.Connect(L["rg_f"], L["m_f"],
                         conn_spec={"rule": "pairwise_bernoulli", "p": P_STATIC_RM},
                         syn_spec={"synapse_model": "static_synapse", "weight": W_STATIC_RM, "delay": DELAY_MS})

    # ----------------------------
    # Commissural coupling (between legs)
    # ----------------------------
    if ENABLE_COMMISSURAL:
        L = leg["L"]
        R = leg["R"]
        nest.Connect(L["rg_e"], R["rg_f"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_INH, "delay": DELAY_COMM_MS})
        nest.Connect(R["rg_e"], L["rg_f"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_INH, "delay": DELAY_COMM_MS})
        nest.Connect(L["rg_f"], R["rg_e"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_INH, "delay": DELAY_COMM_MS})
        nest.Connect(R["rg_f"], L["rg_e"],
                     conn_spec={"rule": "pairwise_bernoulli", "p": P_COMM},
                     syn_spec={"synapse_model": "static_synapse", "weight": W_COMM_INH, "delay": DELAY_COMM_MS})

    # ----------------------------
    # Log neurons & synapses
    # ----------------------------
    if rank == 0:
        per_leg_neurons = (N_CUT + N_BS * 2 + N_BS + N_IA_E + N_IA_F +
                           N_RG_E + N_RG_F + N_MOTOR_E + N_MOTOR_F + N_MUS_E + N_MUS_F)
        total_neurons = per_leg_neurons * len(LEGS)
        print(f"[Counts] Neurons per leg ≈ {per_leg_neurons} | Total ≈ {total_neurons}")

        for side in LEGS:
            print(f"[Counts] Synapses leg {side}: "
                  f"stdp_cut_rge={count_conns(synapse_model=f'stdp_cut_rge_{side}')}, "
                  f"stdp_bs_rge={count_conns(synapse_model=f'stdp_bs_rge_{side}')}, "
                  f"stdp_bs_rgf={count_conns(synapse_model=f'stdp_bs_rgf_{side}')}, "
                  f"stdp_rge_me={count_conns(synapse_model=f'stdp_rge_me_{side}')}, "
                  f"stdp_rgf_mf={count_conns(synapse_model=f'stdp_rgf_mf_{side}')}"
                  )

        print(f"[Counts] Total static_synapse connections (all legs + commissural): "
              f"{count_conns(synapse_model='static_synapse')}")

    # ----------------------------
    # Weight sampling helper
    # ----------------------------
    def sample_w(model_name: str) -> np.ndarray:
        conns = nest.GetConnections(synapse_model=model_name)
        if len(conns) == 0:
            return np.array([], dtype=float)
        return np.asarray(nest.GetStatus(conns, "weight"), dtype=float)

    # ----------------------------
    # Closed-loop state + logs
    # ----------------------------
    state = {side: dict(
        act_e=0.0, act_f=0.0,
        force_e=0.0, force_f=0.0,
        len_e=L0, len_f=L0,
        last_muse=0, last_musf=0,
    ) for side in LEGS}

    times = []
    wstats = {side: {k: ([], []) for k in ["cut->rge", "bs->rge", "bs->rgf", "rge->me", "rgf->mf"]} for side in LEGS}
    logs = {side: dict(bs_e=[], bs_f=[], mus_e=[], mus_f=[],
                      act_e=[], act_f=[], force_e=[], force_f=[],
                      len_e=[], len_f=[], ia_e=[], ia_f=[]) for side in LEGS}

    def new_spikes(rec, last_len):
        ev = nest.GetStatus(rec, "events")[0]
        cur = len(ev["times"])
        return cur - last_len, cur

    def update_leg(side: str, t_ms: float, cut_active_frac: float):
        dt_s = SAMPLE_DT_MS / 1000.0
        L = leg[side]
        S = state[side]
        P = logs[side]

        # BS rates
        r_e, r_f = bs_rates_counterphase(t_ms, side)
        nest.SetStatus(L["bs_pg_e"], {"rate": r_e})
        nest.SetStatus(L["bs_pg_f"], {"rate": r_f})
        P["bs_e"].append(r_e)
        P["bs_f"].append(r_f)

        # muscle spikes -> rates
        sp_e, cur_e = new_spikes(L["rec_muse"], S["last_muse"])
        sp_f, cur_f = new_spikes(L["rec_musf"], S["last_musf"])
        S["last_muse"] = cur_e
        S["last_musf"] = cur_f
        r_muse = (sp_e / max(1, N_MUS_E)) / dt_s
        r_musf = (sp_f / max(1, N_MUS_F)) / dt_s
        P["mus_e"].append(r_muse)
        P["mus_f"].append(r_musf)

        # activation
        tauA_s = TAU_ACT_MS / 1000.0
        target_ae = clamp(ACT_GAIN * r_muse, 0.0, ACT_MAX)
        target_af = clamp(ACT_GAIN * r_musf, 0.0, ACT_MAX)
        S["act_e"] += (dt_s / tauA_s) * (target_ae - S["act_e"])
        S["act_f"] += (dt_s / tauA_s) * (target_af - S["act_f"])

        # force
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

        # length
        tauL_s = TAU_LENGTH_MS / 1000.0
        S["len_e"] += (dt_s / tauL_s) * (L0 - S["len_e"])
        S["len_f"] += (dt_s / tauL_s) * (L0 - S["len_f"])
        S["len_e"] -= SHORTEN_GAIN * S["force_e"] * dt_s
        S["len_f"] -= SHORTEN_GAIN * S["force_f"] * dt_s
        if cut_active_frac > 0.0:
            S["len_e"] += STRETCH_GAIN * cut_active_frac * dt_s
        S["len_e"] = clamp(S["len_e"], L_MIN, L_MAX)
        S["len_f"] = clamp(S["len_f"], L_MIN, L_MAX)

        # Ia rates: force + stretch only
        stretch_e = max(0.0, S["len_e"] - L0)
        stretch_f = max(0.0, S["len_f"] - L0)
        ia_e = IA_BASE_HZ + IA_K_FORCE * S["force_e"] + IA_K_STRETCH * stretch_e
        ia_f = IA_BASE_HZ + IA_K_FORCE * S["force_f"] + IA_K_STRETCH * stretch_f
        ia_e = clamp(ia_e, 0.0, IA_RATE_MAX_HZ)
        ia_f = clamp(ia_f, 0.0, IA_RATE_MAX_HZ)
        nest.SetStatus(L["ia_pg_e"], {"rate": ia_e})
        nest.SetStatus(L["ia_pg_f"], {"rate": ia_f})

        # store logs
        P["act_e"].append(S["act_e"])
        P["act_f"].append(S["act_f"])
        P["force_e"].append(S["force_e"])
        P["force_f"].append(S["force_f"])
        P["len_e"].append(S["len_e"])
        P["len_f"].append(S["len_f"])
        P["ia_e"].append(ia_e)
        P["ia_f"].append(ia_f)

    def log_weights(t_ms: float):
        times.append(t_ms)
        for side in LEGS:
            def push(model, key):
                w = sample_w(model)
                if w.size == 0:
                    wstats[side][key][0].append(np.nan)
                    wstats[side][key][1].append(np.nan)
                else:
                    wstats[side][key][0].append(float(w.mean()))
                    wstats[side][key][1].append(float(w.std()))
            push(f"stdp_cut_rge_{side}", "cut->rge")
            push(f"stdp_bs_rge_{side}", "bs->rge")
            push(f"stdp_bs_rgf_{side}", "bs->rgf")
            push(f"stdp_rge_me_{side}", "rge->me")
            push(f"stdp_rgf_mf_{side}", "rgf->mf")

    # ----------------------------
    # Run loop with progress logging
    # ----------------------------
    total_steps = int(SIM_MS / SAMPLE_DT_MS)
    done_steps = 0

    chunk = max(1, int(N_CUT / N_PHASES))
    t = 0.0

    if rank == 0:
        print(f"[Sim] dt={SAMPLE_DT_MS} ms | total_steps={total_steps} | phases={N_PHASES} | phase_ms={PHASE_MS:.2f}")

    for phase in range(N_PHASES):
        for side in LEGS:
            nest.SetStatus(leg[side]["cut_pg"], {"rate": CUT_RATE_OFF_HZ})

        start = phase * chunk
        end = min(N_CUT, (phase + 1) * chunk)
        for side in LEGS:
            nest.SetStatus(leg[side]["cut_pg"][start:end], {"rate": CUT_RATE_ON_HZ})

        cut_active_frac = float(end - start) / float(N_CUT)

        n_steps = int(PHASE_MS / SAMPLE_DT_MS)
        for _ in range(n_steps):
            nest.Simulate(SAMPLE_DT_MS)
            t += SAMPLE_DT_MS
            done_steps += 1

            for side in LEGS:
                update_leg(side, t, cut_active_frac)
            log_weights(t)

            if (done_steps % PRINT_EVERY == 0) or (done_steps == total_steps):
                print(
                    f"[Sim] Phase {phase + 1}/{N_PHASES} | "
                    f"step {done_steps}/{total_steps} | "
                    f"t={t:.1f} ms"
                )

            if rank == 0 and (done_steps % PROGRESS_EVERY_STEPS == 0 or done_steps == total_steps):
                print(f"[Sim] Step {done_steps} / {total_steps}  (t={t:.1f} ms)")

    times_arr = np.asarray(times)

    # ----------------------------
    # Plots (SEPARATE per leg)
    # ----------------------------
    for side in LEGS:
        P = logs[side]

        # BS
        plt.figure(figsize=(14, 5))
        plt.plot(times_arr, P["bs_e"], label=f"BS E ({side})")
        plt.plot(times_arr, P["bs_f"], label=f"BS F ({side})")
        plt.xlabel("time (ms)")
        plt.ylabel("Hz")
        plt.title(f"Brainstem drive — leg {side}")
        plt.legend()
        plt.tight_layout()
        plt.show()

        # Input synapses learning
        plt.figure(figsize=(14, 7))
        for key in ["cut->rge", "bs->rge", "bs->rgf"]:
            m = np.asarray(wstats[side][key][0])
            s = np.asarray(wstats[side][key][1])
            plt.plot(times_arr, m, label=f"{key} mean")
            plt.fill_between(times_arr, m - s, m + s, alpha=0.15)
        plt.xlabel("time (ms)")
        plt.ylabel("weight (pA)")
        plt.title(f"STDP learning — inputs (leg {side}) mean ± std")
        plt.legend()
        plt.tight_layout()
        plt.show()

        # Motor synapses means
        plt.figure(figsize=(14, 6))
        m1 = moving_average(np.asarray(wstats[side]["rge->me"][0]), WIN_1S)
        m2 = moving_average(np.asarray(wstats[side]["rgf->mf"][0]), WIN_1S)

        plt.plot(times_arr, m1, label="rge->me mean (1s MA)")
        plt.plot(times_arr, m2, label="rgf->mf mean (1s MA)")

        plt.xlabel("time (ms)")
        plt.ylabel("weight (pA)")
        plt.title(f"STDP learning — motor synapses trend (leg {side}, 1s moving average)")
        plt.legend()
        plt.tight_layout()
        plt.show()

        # Muscle rates
        plt.figure(figsize=(14, 5))
        plt.plot(times_arr, P["mus_e"], label="mus-E rate")
        plt.plot(times_arr, P["mus_f"], label="mus-F rate")
        plt.xlabel("time (ms)")
        plt.ylabel("Hz/neuron")
        plt.title(f"Muscle relay rates — leg {side}")
        plt.legend()
        plt.tight_layout()
        plt.show()

        # Activation
        plt.figure(figsize=(14, 5))
        plt.plot(times_arr, P["act_e"], label="Activation E")
        plt.plot(times_arr, P["act_f"], label="Activation F")
        plt.xlabel("time (ms)")
        plt.ylabel("a.u.")
        plt.title(f"Activation proxy — leg {side}")
        plt.legend()
        plt.tight_layout()
        plt.show()

        # Force
        plt.figure(figsize=(14, 5))
        plt.plot(times_arr, P["force_e"], label="Force E")
        plt.plot(times_arr, P["force_f"], label="Force F")
        plt.xlabel("time (ms)")
        plt.ylabel("force (a.u.)")
        plt.title(f"Force proxy — leg {side}")
        plt.legend()
        plt.tight_layout()
        plt.show()

        # Length
        plt.figure(figsize=(14, 5))
        plt.plot(times_arr, P["len_e"], label="Length E")
        plt.plot(times_arr, P["len_f"], label="Length F")
        plt.axhline(L0, linestyle="--", linewidth=1)
        plt.xlabel("time (ms)")
        plt.ylabel("length (a.u.)")
        plt.title(f"Length proxy — leg {side} (E also stretched by CUT)")
        plt.legend()
        plt.tight_layout()
        plt.show()

        # Ia
        plt.figure(figsize=(14, 5))
        plt.plot(times_arr, P["ia_e"], label="Ia-E rate")
        plt.plot(times_arr, P["ia_f"], label="Ia-F rate")
        plt.xlabel("time (ms)")
        plt.ylabel("Hz")
        plt.title(f"Ia generator rates — leg {side} (force + stretch)")
        plt.legend()
        plt.tight_layout()
        plt.show()



# ============================
# Sizes
# ============================
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

LEGS = ("L", "R")


# ============================
# Simulation timing
# ============================
SIM_MS = 10_000.0
SAMPLE_DT_MS = 10.0

# Progress print cadence (avoid terminal spam)
PROGRESS_EVERY_STEPS = 50  # prints every 50 steps => every 500 ms with dt=10 ms


# ============================
# CUT stimulation (extensor only)
# ============================
N_PHASES = 6
PHASE_MS = SIM_MS / N_PHASES
CUT_RATE_ON_HZ = 200.0
CUT_RATE_OFF_HZ = 0.0


# ============================
# Brainstem drive
# ============================
BS_OSC_HZ = 1.0
BS_RATE_BASE_HZ = 0.0
BS_RATE_AMP_HZ = 300.0
BS_RATE_MIN_HZ = 0.0

# Left/right phase shift (diagonal alternation)
BS_PHASE = {"L": 0.0, "R": np.pi}


# ============================
# Connectivity
# ============================
P_IN_STDP = 0.5
P_RG_REC = 0.12
DELAY_MS = 1.0

# Reciprocal inhibition inside leg (RG-E <-> RG-F)
P_RG_RECIP = 0.20
W_RG_RECIP = -18.0
DELAY_RECIP_MS = 1.0

# Motor -> muscle relay synapses (static)
W_M2MUS = 1.0
P_M2MUS = 0.8

# Ia -> RG feedback synapses (static excitatory)
IA2RG_P = 0.4
IA2RG_W = 12.0

# Baseline RG drive (insurance)
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
# Commissural (between legs) — optional stabilizer
# ============================
ENABLE_COMMISSURAL = True
P_COMM = 0.08
W_COMM_INH = -10.0
DELAY_COMM_MS = 1.0


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
# Ia generator model (NO sinus modulation)
# ============================
IA_BASE_HZ = 10.0
IA_K_FORCE = 6.0
IA_K_STRETCH = 250.0
IA_RATE_MAX_HZ = 500.0

total_steps = int(SIM_MS / SAMPLE_DT_MS)
done_steps = 0
PRINT_EVERY = 50  # every 50 steps = every 500 ms for dt=10 ms
WIN_1S = max(1, int(1000.0 / SAMPLE_DT_MS))  # e.g. 100 samples if dt=10 ms


if __name__ == "__main__":
    main()