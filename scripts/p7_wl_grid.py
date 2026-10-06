#!/usr/bin/env python3
"""
p7_wl_grid.py
PLAN.md P7b: grid of one-session runs over extensor weakness (--init-weights-scale W, pathway weights x W)
and loading (L = --ia-feedback-gain = --cut-feedback-gain; walker / body-weight support).
Reads results/human_modes/p7/7b_wl/w<W>_l<L>/bws50.h5 (run_p7_local.sh style) and prints one grid per metric:
  rEF     mean r(Force-E, Force-F)         E_force  95th percentile of Force-E (a.u., 17 = healthy full load)
  stance  mean stance fraction            stride   measured stride (ms)
  Eact    extensor-active fraction of stance
The first --from-ms of every run is skipped.
Usage: python3 scripts/p7_wl_grid.py [--root results/human_modes/p7/7b_wl] [--mode bws50]
"""
import argparse, glob, os, re, sys
import h5py
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpg_gait_phase_metrics import metrics

ap = argparse.ArgumentParser()
ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "human_modes", "p7", "7b_wl"))
ap.add_argument("--mode", default="bws50")
ap.add_argument("--from-ms", type=float, default=20000.0)
a = ap.parse_args()
cell = {}
for f in glob.glob(os.path.join(a.root, "w*_l*", a.mode + ".h5")):
    m = re.search(r"w([\d.]+)_l([\d.]+)", f)
    w, l = float(m.group(1)), float(m.group(2))
    r = metrics(f, a.from_ms)
    with h5py.File(f, "r") as h:
        t = h["times_ms"][()]
        k = t > a.from_ms
        fe = np.mean([np.percentile(h[f"leg_{s}/force_e"][()][k], 95) for s in "LR"])
    cell[(w, l)] = dict(rEF=np.nanmean([r["rEF_L"], r["rEF_R"]]), E_force=fe,
                        stance=np.nanmean([r.get("stance_L", np.nan), r.get("stance_R", np.nan)]),
                        stride=r.get("stride_meas", np.nan),
                        Eact=np.nanmean([r["E|stance_L"], r["E|stance_R"]]) if "E|stance_L" in r else np.nan)
Ws = sorted({k[0] for k in cell}, reverse=True)
Ls = sorted({k[1] for k in cell}, reverse=True)
for key, fmt in (("rEF", "{:7.2f}"), ("E_force", "{:7.1f}"), ("Eact", "{:7.2f}"), ("stance", "{:7.2f}"), ("stride", "{:7.0f}")):
    print(f"\n{key}   rows: weights W   columns: loading L")
    print("  W\\L  " + "".join(f"{l:7.2f}" for l in Ls))
    for w in Ws:
        print(f"  {w:4.2f} " + "".join(fmt.format(cell[(w, l)][key]) if (w, l) in cell else "      -" for l in Ls))
