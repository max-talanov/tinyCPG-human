#!/usr/bin/env python3
"""
p5_rge_gate_probe.py
PLAN.md P5 extensor load gate (MOD_RGE_LOAD_GATE): an isolated RG-E population (the
model's Izhikevich parameters, recurrent excitation and base drive; no inhibition)
driven by every subset of its four excitatory inputs -- brainstem (BS), cutaneous
(CUT), spindle Ia and tendon-organ Ib -- at the production in-degree (K = 50 each).

The gate: RG-E must stay subthreshold without ground contact (any subset lacking CUT,
at the Ia/Ib caps and worst-case rates) and fire with all four inputs at their initial
weights. Ib reinforces; it cannot drive the extensor on its own or with BS / Ia. CUT alone
must be subthreshold at its initial weight only: the learned CUT drive saturates RG-E, the
rate regime the RG-rate activation readout is calibrated for (PLAN.md P5).

Two weight states: `init` (the plastic Ia and CUT pathways at their initial lognormal
mean) and `cap` (both at Wmax, the worst case the learning can reach). BS is frozen and
Ib static, so they are the same in both. Rates: `stance` is the typical stance rate,
`high` the worst case (Ia, Ib) used for the no-contact checks.

Usage:
  python3 scripts/p5_rge_gate_probe.py                     # the human.yaml gate values
  python3 scripts/p5_rge_gate_probe.py --ie -10 --w-bs 1.0 --w-ib 1.2 \\
      --w-ia 0.6 1.5 --w-cut 1.0 2.0
"""
import argparse
import os
import sys

import numpy as np
import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
SUBSETS = [("bs",), ("ib",), ("ia",), ("cut",), ("bs", "ib"), ("bs", "ia"), ("bs", "ia", "ib"),
           ("bs", "cut"), ("bs", "cut", "ia"), ("bs", "cut", "ib"), ("bs", "cut", "ia", "ib")]
IZH = dict(a=0.02, b=0.2, c=-65.0, d=8.0, V_th=30.0, V_min=-120.0)  # izh_params in cpg_2legs_fast.py


def human_gate():
    groups = yaml.safe_load(open(os.path.join(HERE, "..", "config", "species", "human.yaml")))["constants"]
    c = {k: v for g in groups.values() for k, v in g.items()}
    mean = 3.5  # --sweep-pairs 3.5:0.30 (run_human_modes.sh), the lognormal init mean
    return dict(ie=c.get("I_E_RGE", 1.0), w_bs=mean * c.get("RGE_GATE_SCALE_BS", 1.0),
                w_ib=c.get("W_IB2RG", 4.5) * c.get("RGE_GATE_SCALE_IB", 1.0),
                w_ia=(mean * c.get("RGE_GATE_SCALE_IA", 1.0), c.get("WMAX_IA", 10.0) * c.get("RGE_GATE_SCALE_IA", 1.0)),
                w_cut=(mean * c.get("RGE_GATE_SCALE_CUT", 1.0), c.get("WMAX_CUT_RGE", c.get("WMAX", 120.0))))


def rge_rate(active, w, rates, ie, seed=1, n=100, k=50, sim_ms=2000.0):
    import nest
    nest.ResetKernel()
    nest.set_verbosity("M_ERROR")
    nest.SetKernelStatus({"resolution": 0.1, "rng_seed": seed})
    rng = np.random.default_rng(seed)
    rg = nest.Create("izhikevich", n, IZH)
    nest.SetStatus(rg, {"V_m": -65.0, "U_m": -13.0, "I_e": ie})

    def source(rate, kk, weights):
        pg = nest.Create("poisson_generator", 100, {"rate": rate})
        par = nest.Create("parrot_neuron", 100)
        nest.Connect(pg, par, "one_to_one")
        for tgt in rg:
            idx = sorted(rng.choice(100, kk, replace=False).tolist())
            nest.Connect(par[idx], tgt, "all_to_all", {"weight": weights(kk).reshape(1, -1), "delay": 1.0})

    lognorm = lambda mean: (lambda kk: rng.lognormal(np.log(mean / np.sqrt(1.09)), np.sqrt(np.log(1.09)), kk))
    const = lambda v: (lambda kk: np.full(kk, float(v)))
    source(2.0, 10, const(1.0))                                                    # base_in -> rg_e
    nest.Connect(rg, rg, {"rule": "fixed_indegree", "indegree": 12}, {"weight": 4.0, "delay": 2.0})  # rg_e -> rg_e
    for name in active:
        source(rates[name], k, lognorm(w[name]) if name in ("bs", "ia", "cut") else const(w[name]))
    sr = nest.Create("spike_recorder")
    nest.Connect(rg, sr)
    nest.Simulate(500.0)
    nest.SetStatus(sr, {"n_events": 0})
    nest.Simulate(sim_ms)
    return nest.GetStatus(sr, "n_events")[0] / n / (sim_ms / 1000.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ie", type=float)
    ap.add_argument("--w-bs", type=float, help="BS -> RG-E mean weight (mV)")
    ap.add_argument("--w-ib", type=float, help="Ib -> RG-E weight (mV)")
    ap.add_argument("--w-ia", type=float, nargs=2, metavar=("INIT", "CAP"))
    ap.add_argument("--w-cut", type=float, nargs=2, metavar=("INIT", "CAP"))
    ap.add_argument("--rates", type=float, nargs=4, default=[60.0, 100.0, 35.0, 37.0], metavar=("BS", "CUT", "IA", "IB"),
                    help="stance rates (Hz); default: production force runs, t > 30 s, stance p90")
    ap.add_argument("--high", type=float, nargs=2, default=[45.0, 45.0], metavar=("IA", "IB"),
                    help="worst-case Ia / Ib rates for the no-contact checks")
    ap.add_argument("--sub-hz", type=float, default=1.0, help="subthreshold criterion (Hz/neuron)")
    args = ap.parse_args()
    g = human_gate()
    ie = g["ie"] if args.ie is None else args.ie
    w_bs = g["w_bs"] if args.w_bs is None else args.w_bs
    w_ib = g["w_ib"] if args.w_ib is None else args.w_ib
    w_ia = g["w_ia"] if args.w_ia is None else args.w_ia
    w_cut = g["w_cut"] if args.w_cut is None else args.w_cut
    bs, cut, ia, ib = args.rates
    print(f"I_e {ie}  w: BS {w_bs:.2f}  Ib {w_ib:.2f}  Ia {w_ia[0]:.2f}/{w_ia[1]:.2f}  CUT {w_cut[0]:.2f}/{w_cut[1]:.2f} (init/cap)")
    print(f"rates: BS {bs:.0f}  CUT {cut:.0f}  Ia {ia:.0f} (high {args.high[0]:.0f})  Ib {ib:.0f} (high {args.high[1]:.0f}) Hz")
    print(f"{'inputs':18s} {'init':>7s} {'cap':>7s} {'cap,high':>8s}  must")
    ok_all = True
    for sub in SUBSETS:
        contact = "cut" in sub
        must = "fire" if sub == ("bs", "cut", "ia", "ib") else ("sub" if not contact else "-")
        if sub == ("cut",):
            must = "init"  # CUT alone: subthreshold before learning; the learned CUT drive may fire it
        row = []
        for state, hi in (("init", False), ("cap", False), ("cap", True)):
            j = 0 if state == "init" else 1
            w = dict(bs=w_bs, ib=w_ib, ia=w_ia[j], cut=w_cut[j])
            r = dict(bs=bs, cut=cut, ia=args.high[0] if hi else ia, ib=args.high[1] if hi else ib)
            row.append(rge_rate(sub, w, r, ie) if (not hi or not contact) else np.nan)
        if must == "sub":
            ok = max(x for x in row if not np.isnan(x)) < args.sub_hz
        elif must == "init":
            ok = row[0] < args.sub_hz
        elif must == "fire":
            ok = row[0] > args.sub_hz
        else:
            ok = True
        ok_all &= ok
        cells = " ".join(f"{x:7.1f}" if not np.isnan(x) else f"{'':>7s}" for x in row)
        print(f"{'+'.join(sub):18s} {cells}   {must:4s} {'OK' if ok else 'FAIL'}")
    print("gate", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
