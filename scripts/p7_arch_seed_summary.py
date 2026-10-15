#!/usr/bin/env python3
"""
p7_arch_seed_summary.py
PLAN.md P7 on the architecture-round wiring: the EES, fixed-weakness and recovering-strength (REC) chains across seeds
(run_chains_local.sh). Per condition and session (first / last), mean +- sd over seeds of Force-E p95, r(E,F) (t > --from-ms),
stride, captured CUT->RG-E weight and s_eff; then paired effects per seed on the last session: EES (ees10 - noees) and
REC (recovering - fixed).

Layout: seed 12345 -> results/human_modes/arch2/chain/<cond>/s<k>/<mode>.h5;
        other seeds -> results/human_modes/arch2_seeds/s<seed>/chain/<cond>/s<k>/<mode>.h5
Usage: python3 scripts/p7_arch_seed_summary.py [--seeds 12345 54321 777] [--sessions 1 10]
"""
import argparse
import glob
import os
import sys

import h5py
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpg_gait_phase_metrics import metrics  # noqa: E402

CONDS = [("BWS 50% control", "bws50"), ("BWS 50% EES", "ees10_bws50"), ("BWS 90% control", "bws90"), ("BWS 90% EES", "ees10_bws90"),
         ("s 0.5 fixed", "f0.5_noees"), ("s 0.5 fixed + EES", "f0.5_ees10"), ("s 0.25 fixed", "f0.25_noees"), ("s 0.25 fixed + EES", "f0.25_ees10"),
         ("s 0.5 REC", "r0.5_noees"), ("s 0.5 REC + EES", "r0.5_ees10"), ("s 0.25 REC", "r0.25_noees"), ("s 0.25 REC + EES", "r0.25_ees10")]
PAIRS_EES = [("bws50", "ees10_bws50"), ("bws90", "ees10_bws90"), ("f0.5_noees", "f0.5_ees10"), ("f0.25_noees", "f0.25_ees10"),
             ("r0.5_noees", "r0.5_ees10"), ("r0.25_noees", "r0.25_ees10")]
PAIRS_REC = [("f0.5_noees", "r0.5_noees"), ("f0.5_ees10", "r0.5_ees10"), ("f0.25_noees", "r0.25_noees"), ("f0.25_ees10", "r0.25_ees10")]


def cdir(seed, d):
    base = "results/human_modes/arch2/chain" if seed == 12345 else f"results/human_modes/arch2_seeds/s{seed}/chain"
    return f"{base}/{d}"


def row(path, from_ms):
    with h5py.File(path, "r") as f:
        a = dict(f.attrs)
        fp = np.mean([np.percentile(f[f"leg_{s}/force_e"][()], 95) for s in "LR"])
        w = np.mean([f[f"leg_{s}/consolidation/cut->rge_baseline_mean"][()][-1] for s in "LR"])
    m = metrics(path, from_ms)
    seff = [a[k] for k in (f"ext_strength_eff_end_{s}" for s in "LR") if k in a]
    return {"fe": fp, "r": (m["rEF_L"] + m["rEF_R"]) / 2, "stride": m.get("stride_meas", np.nan),
            "w": w, "seff": float(np.mean(seff)) if seff else np.nan}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=[12345, 54321, 777])
    ap.add_argument("--sessions", type=int, nargs="+", default=[1, 10])
    ap.add_argument("--from-ms", type=float, default=10000.0)
    a = ap.parse_args()
    data = {}
    for _, d in CONDS:
        for sd in a.seeds:
            for k in a.sessions:
                p = glob.glob(f"{cdir(sd, d)}/s{k}/bws*.h5")
                if p:
                    data[(d, sd, k)] = row(p[0], a.from_ms)
    print(f"{'condition':20s} {'sess':>4s} {'n':>2s} {'ForceE p95':>12s} {'r(E,F)':>13s} {'stride ms':>14s} {'CUT pA':>12s} {'s_eff':>10s}")
    for name, d in CONDS:
        for k in a.sessions:
            rows = [data[(d, sd, k)] for sd in a.seeds if (d, sd, k) in data]
            if not rows:
                continue
            def ms(key, w, dec=2):
                v = np.array([r[key] for r in rows], float)
                return f"{np.nanmean(v):{w}.{dec}f} ±{np.nanstd(v):4.2f}" if not np.all(np.isnan(v)) else "     -"
            print(f"{name:20s} {k:>4d} {len(rows):>2d} {ms('fe', 5, 1)} {ms('r', 6)} {ms('stride', 6, 0)} {ms('w', 5, 1)} {ms('seff', 4)}")
    k = a.sessions[-1]
    for title, pairs in (("EES effect, last session (ees10 - noees), per seed", PAIRS_EES), ("REC effect, last session (recovering - fixed), per seed", PAIRS_REC)):
        print(f"\n{title}:")
        for x, y in pairs:
            for key, nm in (("r", "r(E,F)"), ("fe", "Force-E"), ("w", "CUT pA"), ("seff", "s_eff")):
                dd = [data[(y, sd, k)][key] - data[(x, sd, k)][key] for sd in a.seeds if (y, sd, k) in data and (x, sd, k) in data]
                if dd and not np.all(np.isnan(dd)):
                    print(f"  {y:12s} - {x:12s} {nm:8s} " + "  ".join(f"{v:+7.2f}" for v in dd) + f"   mean {np.nanmean(dd):+.2f}")


if __name__ == "__main__":
    main()
