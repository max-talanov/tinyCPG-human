#!/usr/bin/env python3
"""
p5_seed_summary.py
PLAN.md Phase 5 acceptance across seeds: one directory per seed (each with <mode>.h5,
as written by run_human_modes.sh TAG=p5_seeds/s<seed>), one row per mode with the
mean +- sd over seeds of

  stride, stance fraction   vs the mode target (config/modes/human.yaml); OK = mean within 5%
  cap(st)                   fraction of stance bouts that ended on the failsafe cap
  r(E,F)                    Force-E vs Force-F, mean of the two legs
  r(EL,ER)                  left vs right Force-E
  R phase, sd               right touchdown in the left stride (0.5 = alternation), and its
                            within-run sd
  DS                        double-support fraction of time

Everything for t > --from-ms. Per-seed values are printed with --per-seed.

Usage:
  python3 scripts/p5_seed_summary.py results/human_modes/p5_seeds/s*  [--from-ms 30000]
"""
import argparse
import os

import h5py
import numpy as np
import yaml

from p5_force_summary import bouts, corr

HERE = os.path.dirname(os.path.realpath(__file__))


def run_metrics(path, cap_ms_default, t_from):
    with h5py.File(path, "r") as f:
        t = f["times_ms"][()]
        cap = float(f.attrs.get("cut_max_stance_ms", cap_ms_default))
        g = {s: {k: f[f"leg_{s}/{k}"][()] for k in ("force_e", "force_f", "cut_on")} for s in "LR"}
    keep = t > t_from
    dur = np.diff(np.concatenate([[0.0], t]))
    on = {s: g[s]["cut_on"] > 0.5 for s in "LR"}
    strides, frac, capst, td = [], [], [], {}
    for s in "LR":
        st, _ = bouts(on[s], t, t_from)
        td[s] = np.array([b[0] for b in st])
        strides += list(np.diff(td[s]))
        frac.append(np.sum(dur[keep & on[s]]) / np.sum(dur[keep]))
        capst += [(b[1] - b[0]) >= cap - 1e-6 for b in st]
    ph = []
    for a, b in zip(td["L"][:-1], td["L"][1:]):
        r = td["R"][(td["R"] >= a) & (td["R"] < b)]
        if r.size:
            ph.append((r[0] - a) / (b - a))
    ph = np.asarray(ph)
    return dict(
        stride=float(np.mean(strides)) if strides else np.nan,
        stance=float(np.mean(frac)),
        cap=float(np.mean(capst)) if capst else np.nan,
        ref=float(np.mean([corr(g[s]["force_e"][keep], g[s]["force_f"][keep]) for s in "LR"])),
        rlr=corr(g["L"]["force_e"][keep], g["R"]["force_e"][keep]),
        phase=float(ph.mean()) if ph.size else np.nan,
        phase_sd=float(ph.std()) if ph.size else np.nan,
        ds=float(np.sum(dur[keep & on["L"] & on["R"]]) / np.sum(dur[keep])),
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("seed_dirs", nargs="+")
    ap.add_argument("--modes-config", default=os.path.join(HERE, "..", "config", "modes", "human.yaml"))
    ap.add_argument("--from-ms", type=float, default=30000.0)
    ap.add_argument("--per-seed", action="store_true")
    args = ap.parse_args()
    modes = yaml.safe_load(open(args.modes_config))["modes"]
    dirs = sorted(args.seed_dirs)
    print(f"t > {args.from_ms / 1000:.0f} s, seeds: {', '.join(os.path.basename(d.rstrip('/')) for d in dirs)}. "
          f"mean +- sd over seeds; OK = mean within 5% of target")
    print(f"{'mode':12s} {'n':>2s} {'stride':>17s} {'stance frac':>18s} {'cap(st)':>11s} {'r(E,F)':>13s} "
          f"{'r(EL,ER)':>13s} {'R phase':>11s} {'sd':>5s} {'DS':>5s}")
    for name, m in modes.items():
        rows = []
        for d in dirs:
            p = os.path.join(d, f"{name}.h5")
            if os.path.isfile(p):
                rows.append(run_metrics(p, m["force"]["cap_ms"], args.from_ms))
        if not rows:
            continue
        a = {k: np.array([r[k] for r in rows]) for k in rows[0]}
        ms = lambda k, fmt: f"{np.nanmean(a[k]):{fmt}}+-{np.nanstd(a[k]):{fmt.lstrip('+')}}"
        ok_t = abs(np.nanmean(a["stride"]) / m["stride_ms"] - 1) <= 0.05
        ok_f = abs(np.nanmean(a["stance"]) / m["stance_fraction"] - 1) <= 0.05
        print(f"{name:12s} {len(rows):2d} {ms('stride', '5.0f')}/{m['stride_ms']:<4d}{'OK' if ok_t else '--':>2s} "
              f"{ms('stance', '4.2f')}/{m['stance_fraction']:.2f}{'OK' if ok_f else '--':>3s} "
              f"{ms('cap', '4.2f')} {ms('ref', '+5.2f')} {ms('rlr', '+5.2f')} {ms('phase', '4.2f')} "
              f"{np.nanmean(a['phase_sd']):5.2f} {np.nanmean(a['ds']):5.2f}")
        if args.per_seed:
            for d, r in zip(dirs, rows):
                print(f"    {os.path.basename(d.rstrip('/')):8s} stride {r['stride']:5.0f} stance {r['stance']:.2f} "
                      f"cap {r['cap']:.2f} r(E,F) {r['ref']:+.2f} r(EL,ER) {r['rlr']:+.2f} "
                      f"phase {r['phase']:.2f}+-{r['phase_sd']:.2f} DS {r['ds']:.2f}")


if __name__ == "__main__":
    main()
