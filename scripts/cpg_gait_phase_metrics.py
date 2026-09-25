#!/usr/bin/env python3
"""
cpg_gait_phase_metrics.py
Gait-phase metrics for PLAN.md Phase 3 (stance fraction, double support) from
one or more cpg_2legs_fast.py outputs.

Schedule (from the per-leg ground-truth `cut_on`, duration-weighted over the
chunks; needs --gait-scheduler phase or --cut-trigger force):
  stance     fraction of time each leg is in stance
  DS         double support: both legs in stance (total, and per L/R transition)
  flight     both legs in swing
  stride     mean interval between successive touch-downs of the left leg

Does the network follow the schedule (from force; any run):
  r(E,F)     extensor/flexor force correlation per leg
  r(EL,ER)   left/right extensor force correlation (anti-phase < 0)
  E-active   fraction of time the extensor is active (force_e above half of its
             95th percentile), per leg
  neural DS  both extensors active at the same time
  E|stance   fraction of each leg's stance during which its extensor is active

The first --from-ms of each run is skipped (settling).

Usage:
  python3 scripts/cpg_gait_phase_metrics.py results/p3/*.h5
"""
import argparse
import os

import h5py
import numpy as np


def active(x):
    ref = np.percentile(x, 95)
    return x > 0.5 * ref if ref > 1e-9 else np.zeros_like(x, dtype=bool)


def wmean(mask, w):
    return float(np.sum(w[mask]) / np.sum(w)) if np.sum(w) > 0 else float("nan")


def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1]) if a.std() > 1e-9 and b.std() > 1e-9 else float("nan")


def metrics(path, from_ms):
    with h5py.File(path, "r") as f:
        t = f["times_ms"][()]
        a = dict(f.attrs)
        L, R = f["leg_L"], f["leg_R"]
        fe = {s: f[f"leg_{s}/force_e"][()] for s in "LR"}
        ff = {s: f[f"leg_{s}/force_f"][()] for s in "LR"}
        on = {s: f[f"leg_{s}/cut_on"][()] for s in "LR"} if L["cut_on"].size and R["cut_on"].size else None
    dur = np.diff(np.concatenate([[0.0], t]))
    keep = t > from_ms
    w = dur[keep]
    m = {"file": os.path.basename(path), "species": a.get("species", "?"),
         "sched": a.get("gait_scheduler", "force" if a.get("cut_trigger") == "force" else "halfcycle"),
         "f_nominal": a.get("stance_fraction", float("nan")), "stride_ms": a.get("step_period_ms", float("nan"))}
    ea = {s: active(fe[s][keep]) for s in "LR"}
    m.update({f"rEF_{s}": corr(fe[s][keep], ff[s][keep]) for s in "LR"})
    m["rELER"] = corr(fe["L"][keep], fe["R"][keep])
    m.update({f"Eact_{s}": wmean(ea[s], w) for s in "LR"})
    m["neuralDS"] = wmean(ea["L"] & ea["R"], w)
    if on is not None:
        st = {s: on[s][keep] > 0.5 for s in "LR"}
        m.update({f"stance_{s}": wmean(st[s], w) for s in "LR"})
        m["DS"] = wmean(st["L"] & st["R"], w)
        m["flight"] = wmean(~st["L"] & ~st["R"], w)
        m.update({f"E|stance_{s}": (wmean(ea[s] & st[s], w) / max(1e-9, wmean(st[s], w))) for s in "LR"})
        td = t[keep][1:][np.diff(st["L"].astype(int)) == 1]
        m["stride_meas"] = float(np.mean(np.diff(td))) if td.size > 2 else float("nan")
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--from-ms", type=float, default=5000.0)
    args = ap.parse_args()
    rows = [metrics(p, args.from_ms) for p in args.files]
    cols = [("file", "{:<26}"), ("sched", "{:<9}"), ("stance_L", "{:>8.3f}"), ("stance_R", "{:>8.3f}"),
            ("DS", "{:>6.3f}"), ("flight", "{:>6.3f}"), ("stride_meas", "{:>7.0f}"),
            ("rEF_L", "{:>6.2f}"), ("rEF_R", "{:>6.2f}"), ("rELER", "{:>6.2f}"),
            ("Eact_L", "{:>6.2f}"), ("Eact_R", "{:>6.2f}"), ("neuralDS", "{:>8.3f}"),
            ("E|stance_L", "{:>10.2f}"), ("E|stance_R", "{:>10.2f}")]
    print("  ".join(f"{c:>{len(fmt.format(0)) if 'f' in fmt else len(c)}}" if c != "file" and c != "sched"
                    else f"{c:<{26 if c == 'file' else 9}}" for c, fmt in cols))
    for r in rows:
        cells = []
        for c, fmt in cols:
            v = r.get(c, float("nan"))
            try:
                cells.append(fmt.format(v))
            except (ValueError, TypeError):
                cells.append(f"{str(v):>8}")
        print("  ".join(cells))


if __name__ == "__main__":
    main()
