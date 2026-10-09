#!/usr/bin/env python3
"""
p7_seed_summary.py
PLAN.md P7 step 1: the recovering-strength chains across seeds (run_p7_seeds_local.sh). Per condition
(strength s x EES) and session (first / middle / last), mean +- sd over seeds of Force-E p95, r(E,F) (mean of the
legs, t > --from-ms), stride, captured CUT->RG-E weight and the effective strength s_eff. Also the paired EES effect
(ees10 - noees) per seed on the last session, to separate it from the seed spread.

Layout: results/human_modes/p7_seeds/s<seed>/chain/r<s>_<noees|ees10>/s<k>/bws50.h5; seed 12345 is read from
results/human_modes/p7/chain/r<s>_<cond> (run before the seed driver existed).
Usage: python3 scripts/p7_seed_summary.py [--seeds 12345 54321 777] [--sessions 1 5 10]
"""
import argparse
import glob
import os
import sys

import h5py
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpg_gait_phase_metrics import metrics  # noqa: E402


def chain_dir(seed, s, cond):
    if seed == 12345:
        return f"results/human_modes/p7/chain/r{s}_{cond}"
    return f"results/human_modes/p7_seeds/s{seed}/chain/r{s}_{cond}"


def row(path, from_ms):
    with h5py.File(path, "r") as f:
        a = dict(f.attrs)
        fp = np.mean([np.percentile(f[f"leg_{s}/force_e"][()], 95) for s in "LR"])
        w = np.mean([f[f"leg_{s}/consolidation/cut->rge_baseline_mean"][()][-1] for s in "LR"])
    m = metrics(path, from_ms)
    return {"fe": fp, "r": (m["rEF_L"] + m["rEF_R"]) / 2, "stride": m.get("stride_meas", np.nan),
            "w": w, "seff": np.mean([a.get(f"ext_strength_eff_end_{s}", np.nan) for s in "LR"])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=[12345, 54321, 777])
    ap.add_argument("--sessions", type=int, nargs="+", default=[1, 5, 10])
    ap.add_argument("--from-ms", type=float, default=10000.0)
    a = ap.parse_args()
    data = {}
    for s in ("0.5", "0.25"):
        for cond in ("noees", "ees10"):
            for sd in a.seeds:
                for k in a.sessions:
                    p = glob.glob(f"{chain_dir(sd, s, cond)}/s{k}/bws50.h5")
                    if p:
                        data[(s, cond, sd, k)] = row(p[0], a.from_ms)
    print(f"{'s':>5s} {'EES':>6s} {'sess':>4s} {'n':>2s} {'ForceE p95':>13s} {'r(E,F)':>13s} {'stride ms':>13s} {'CUT pA':>13s} {'s_eff':>11s}")
    for s in ("0.5", "0.25"):
        for cond in ("noees", "ees10"):
            for k in a.sessions:
                rows = [data[(s, cond, sd, k)] for sd in a.seeds if (s, cond, sd, k) in data]
                if not rows:
                    continue
                def ms(key, w):
                    v = np.array([r[key] for r in rows], float)
                    return f"{np.nanmean(v):{w}.2f} ±{np.nanstd(v):4.2f}"
                print(f"{s:>5s} {cond:>6s} {k:>4d} {len(rows):>2d} {ms('fe', 6)} {ms('r', 6)} {ms('stride', 6)} {ms('w', 6)} {ms('seff', 4)}")
    k = a.sessions[-1]
    print(f"\nPaired EES effect on the last session (session {k}), ees10 - noees, per seed:")
    for s in ("0.5", "0.25"):
        for key, name in (("r", "r(E,F)"), ("fe", "Force-E"), ("w", "CUT pA"), ("seff", "s_eff")):
            d = [data[(s, "ees10", sd, k)][key] - data[(s, "noees", sd, k)][key] for sd in a.seeds
                 if (s, "ees10", sd, k) in data and (s, "noees", sd, k) in data]
            if d:
                print(f"  s {s:>4s} {name:8s} " + "  ".join(f"{x:+7.2f}" for x in d) + f"   mean {np.mean(d):+.2f}")


if __name__ == "__main__":
    main()
