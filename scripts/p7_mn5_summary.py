#!/usr/bin/env python3
"""
p7_mn5_summary.py
PLAN.md P7b at production size on the architecture-round wiring (run_p7_chain_mn5.sh, MN5, 3 seeds x 20 conditions x 15 sessions).
Per condition and session (first / last), mean +- sd over seeds of Force-E p95, r(E,F), stride, captured CUT->RG-E weight and s_eff;
then paired per-seed effects on the last session: EES (with - without) and REC (recovering - fixed weakness), plus fixed weakness vs control.
Usage: python3 scripts/p7_mn5_summary.py [--root results/2026-10-15/p7/human_modes/p7_arch] [--sessions 1 15]
"""
import argparse
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p7_arch_seed_summary import row  # noqa: E402

LV = ("bws50", "bws90")
CONDS = []
for b in LV:
    CONDS += [(f"{b} control", b), (f"{b} EES", f"{b}_ees10")]
    for s in ("0.5", "0.25"):
        CONDS += [(f"{b} s{s} fixed", f"s{s}_{b}"), (f"{b} s{s} fixed+EES", f"s{s}_{b}_ees10"),
                  (f"{b} s{s} REC", f"r{s}_{b}"), (f"{b} s{s} REC+EES", f"r{s}_{b}_ees10")]
PAIRS_EES, PAIRS_REC, PAIRS_FIX = [], [], []
for b in LV:
    PAIRS_EES.append((b, f"{b}_ees10"))
    for s in ("0.5", "0.25"):
        PAIRS_EES += [(f"s{s}_{b}", f"s{s}_{b}_ees10"), (f"r{s}_{b}", f"r{s}_{b}_ees10")]
        PAIRS_REC += [(f"s{s}_{b}", f"r{s}_{b}"), (f"s{s}_{b}_ees10", f"r{s}_{b}_ees10")]
        PAIRS_FIX.append((b, f"s{s}_{b}"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="results/2026-10-15/p7/human_modes/p7_arch")
    ap.add_argument("--seeds", type=int, nargs="+", default=[12345, 54321, 777])
    ap.add_argument("--sessions", type=int, nargs="+", default=[1, 15])
    ap.add_argument("--from-ms", type=float, default=10000.0)
    a = ap.parse_args()
    data = {}
    for _, d in CONDS:
        for sd in a.seeds:
            for k in a.sessions:
                p = glob.glob(f"{a.root}/chain/s{sd}/{d}/s{k}/bws*.h5")
                if p:
                    data[(d, sd, k)] = row(p[0], a.from_ms)
    print(f"{'condition':22s} {'sess':>4s} {'n':>2s} {'ForceE p95':>12s} {'r(E,F)':>13s} {'stride ms':>14s} {'CUT pA':>12s} {'s_eff':>10s}")
    for name, d in CONDS:
        for k in a.sessions:
            rows = [data[(d, sd, k)] for sd in a.seeds if (d, sd, k) in data]
            if not rows:
                continue

            def ms(key, w, dec=2):
                v = np.array([r[key] for r in rows], float)
                return f"{np.nanmean(v):{w}.{dec}f} ±{np.nanstd(v):4.2f}" if not np.all(np.isnan(v)) else "     -"
            print(f"{name:22s} {k:>4d} {len(rows):>2d} {ms('fe', 5, 1)} {ms('r', 6)} {ms('stride', 6, 0)} {ms('w', 5, 1)} {ms('seff', 4)}")
    k = a.sessions[-1]
    for title, pairs in (("EES effect, last session (with - without), per seed", PAIRS_EES),
                         ("REC effect, last session (recovering - fixed), per seed", PAIRS_REC),
                         ("Fixed weakness vs control, last session (fixed - control), per seed", PAIRS_FIX)):
        print(f"\n{title}:")
        for x, y in pairs:
            for key, nm in (("r", "r(E,F)"), ("fe", "Force-E"), ("w", "CUT pA"), ("seff", "s_eff")):
                dd = [data[(y, sd, k)][key] - data[(x, sd, k)][key] for sd in a.seeds if (y, sd, k) in data and (x, sd, k) in data]
                if dd and not np.all(np.isnan(dd)):
                    print(f"  {y:16s} - {x:14s} {nm:8s} " + "  ".join(f"{v:+7.2f}" for v in dd) + f"   mean {np.nanmean(dd):+.2f}")


if __name__ == "__main__":
    main()
