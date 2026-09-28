#!/usr/bin/env python3
"""
p5_force_summary.py
PLAN.md Phase 5 acceptance table for force-triggered human modes
(./run_human_modes.sh with TRIGGER=force), one row per mode:

  stride / stance   measured (mean touch-down interval -- a mean, because bouts are
                    quantised to the 100 ms update window and a median just
                    picks one tick value; duration-weighted
                    stance fraction) vs the mode's target from
                    config/modes/human.yaml; OK if within +-5%
  cap(st) cap(sw)   fraction of stance / swing bouts that ended on the failsafe
                    cap. Bouts are quantised to the update window, so a capped
                    bout ends at the first window end at or after the cap:
                    duration >= cap. Must be ~0: a bout ending on the cap is
                    the timer, not the force threshold. (The rat medium
                    operating point has genuine stance but every swing capped.)
  r(E,F) r(EL,ER)   force correlations (target band -0.6 .. -0.8, no L/R sync)
  captures          consolidation capture events per leg (0 if off)

Everything is computed for t > --from-ms (settling excluded).

Usage:
  python3 scripts/p5_force_summary.py results/human_modes/force_r1_debug [--from-ms 20000]
"""
import argparse
import os

import h5py
import numpy as np
import yaml

HERE = os.path.dirname(os.path.realpath(__file__))


def bouts(on, t, t_from):
    start_t = np.concatenate([[0.0], t[:-1]])
    e = np.diff(on.astype(int))
    ups, downs = np.flatnonzero(e == 1) + 1, np.flatnonzero(e == -1) + 1
    st = [(start_t[u], start_t[downs[downs > u][0]]) for u in ups if (downs > u).any() and start_t[u] >= t_from]
    sw = [(start_t[d], start_t[ups[ups > d][0]]) for d in downs if (ups > d).any() and start_t[d] >= t_from]
    return st, sw


def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1]) if a.std() > 1e-9 and b.std() > 1e-9 else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("indir")
    ap.add_argument("--modes-config", default=os.path.join(HERE, "..", "config", "modes", "human.yaml"))
    ap.add_argument("--from-ms", type=float, default=20000.0)
    args = ap.parse_args()
    modes = yaml.safe_load(open(args.modes_config))["modes"]
    print(f"t > {args.from_ms / 1000:.0f} s.  target = mode stride / stance fraction; OK = within 5%")
    print(f"{'mode':12s} {'stride':>14s} {'stance frac':>15s} {'stance ms':>9s} {'swing ms':>8s} "
          f"{'cap(st)':>7s} {'cap(sw)':>7s} {'r(E,F) L/R':>12s} {'r(EL,ER)':>8s} {'capt L/R':>9s}")
    for name, m in modes.items():
        p = os.path.join(args.indir, f"{name}.h5")
        if not os.path.isfile(p):
            continue
        with h5py.File(p, "r") as f:
            a = dict(f.attrs)
            t = f["times_ms"][()]
            g = {s: {k: f[f"leg_{s}/{k}"][()] for k in ("force_e", "force_f", "cut_on")} for s in "LR"}
            ev = {s: (f[f"leg_{s}/consolidation_event"][()] if f"leg_{s}/consolidation_event" in f else None)
                  for s in "LR"}
        cap = float(a.get("cut_max_stance_ms", np.nan))
        keep = t > args.from_ms
        dur = np.diff(np.concatenate([[0.0], t]))
        strides, frac, st_d, sw_d, capst, capsw = [], [], [], [], [], []
        for s in "LR":
            on = g[s]["cut_on"] > 0.5
            st, sw = bouts(on, t, args.from_ms)
            strides += list(np.diff([b[0] for b in st]))
            frac.append(np.sum(dur[keep & on]) / np.sum(dur[keep]))
            st_d += [b[1] - b[0] for b in st]
            sw_d += [b[1] - b[0] for b in sw]
            capst += [(b[1] - b[0]) >= cap - 1e-6 for b in st]
            capsw += [(b[1] - b[0]) >= cap - 1e-6 for b in sw]
        stride = float(np.mean(strides)) if strides else np.nan
        sf = float(np.mean(frac))
        ok_t = abs(stride / m["stride_ms"] - 1) <= 0.05
        ok_f = abs(sf / m["stance_fraction"] - 1) <= 0.05
        r = [corr(g[s]["force_e"][keep], g[s]["force_f"][keep]) for s in "LR"]
        rlr = corr(g["L"]["force_e"][keep], g["R"]["force_e"][keep])
        capt = "/".join(str(int(np.sum(ev[s][keep] > 0))) if ev[s] is not None else "-" for s in "LR")
        print(f"{name:12s} {stride:6.0f}/{m['stride_ms']:<4d}{'OK' if ok_t else '--':>3s} "
              f"{sf:5.2f}/{m['stance_fraction']:.2f}{'OK' if ok_f else '--':>4s} "
              f"{np.median(st_d) if st_d else np.nan:9.0f} {np.median(sw_d) if sw_d else np.nan:8.0f} "
              f"{np.mean(capst) if capst else np.nan:7.2f} {np.mean(capsw) if capsw else np.nan:7.2f} "
              f"{r[0]:+.2f}/{r[1]:+.2f} {rlr:+8.2f} {capt:>9s}")


if __name__ == "__main__":
    main()
