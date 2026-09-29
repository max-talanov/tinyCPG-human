#!/usr/bin/env python3
"""
p6_session_metrics.py
PLAN.md Phase 6: how much one session changes the gait and what it keeps. Per run
(one .h5 per session): r(E,F) (mean of the legs) and CUT->RG-E mean weight at the
session start and end windows, the captured baseline at the end (what the next session
starts from with --init-weights-state baseline), and the capture count per leg.

Usage:
  python3 scripts/p6_session_metrics.py RUN.h5 [RUN2.h5 ...] [--early 2000 12000] [--late -10000 0]
  (--late is relative to the run end)
"""
import argparse

import h5py
import numpy as np

from p5_force_summary import corr


def metrics(path, early, late):
    with h5py.File(path, "r") as f:
        t = f["times_ms"][()]
        end = t[-1]
        out = {}
        for tag, (lo, hi) in (("early", early), ("late", (end + late[0], end + late[1]))):
            k = (t >= lo) & (t <= hi)
            out[f"r_{tag}"] = float(np.mean([corr(f[f"leg_{s}/force_e"][()][k], f[f"leg_{s}/force_f"][()][k])
                                             for s in "LR"]))
            out[f"cut_{tag}"] = float(np.nanmean([f[f"leg_{s}/weights/cut->rge_mean"][()][k] for s in "LR"]))
        out["base_end"] = float(np.mean([f[f"leg_{s}/consolidation/cut->rge_baseline_mean"][()][-1] for s in "LR"])) \
            if "leg_L/consolidation" in f else np.nan
        out["captures"] = "/".join(str(int(np.sum(np.abs(f[f"leg_{s}/consolidation_event"][()]) >= 2)))
                                   if f"leg_{s}/consolidation_event" in f else "-" for s in "LR")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--early", type=float, nargs=2, default=[2000.0, 12000.0])
    ap.add_argument("--late", type=float, nargs=2, default=[-10000.0, 0.0])
    args = ap.parse_args()
    print(f"{'run':40s} {'r(E,F) early':>12s} {'late':>6s} {'CUT early':>10s} {'late':>6s} {'base end':>9s} {'capt L/R':>9s}")
    for p in args.runs:
        m = metrics(p, args.early, args.late)
        print(f"{p[-40:]:40s} {m['r_early']:+12.2f} {m['r_late']:+6.2f} {m['cut_early']:10.1f} {m['cut_late']:6.1f} "
              f"{m['base_end']:9.1f} {m['captures']:>9s}")


if __name__ == "__main__":
    main()
