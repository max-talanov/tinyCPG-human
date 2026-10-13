#!/usr/bin/env python3
"""
p8_model_vs_patients.py
PLAN.md P8, SCI arm: model gait timing against the four patients (validation/human_sci_metrics.json).

Patients (per condition, both legs averaged): stride, stance fraction, double support, plus per-leg stance.
Model (debug-small, seed 12345; metrics from cut_on via cpg_gait_phase_metrics), results root --root (default arch2 = the
architecture-round wiring; p7 = the earlier wiring, with grid dir 7b_wl):
  grid   results/human_modes/<root>/7b/w<s>_l<L>/bws50.h5   one 60 s session, trained start, extensor strength s x loading L
  chains results/human_modes/<root>/chain/r<s>_<noees|ees10>/s10/bws50.h5   recovered state after 10 sessions
Healthy references: model five modes (<root>/7a) and the controls (validation/human_gait_reference.json).

Both the patient and the control stance / double support are IMU estimates (biased 3-6 points high, see
validation/human_data_sources.md), so the offset between patient and model is read together with the control offset
(model comfortable vs controls). Writes validation/p8_model_vs_patients.json and plots/p8/model_vs_patients.png.
Usage: python3 scripts/p8_model_vs_patients.py [--root arch2] [--tag arch2]
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from cpg_gait_phase_metrics import metrics  # noqa: E402


def mrow(path, from_ms=10000.0):
    m = metrics(path, from_ms)
    return {"stride": m["stride_meas"] / 1000.0, "stance": (m["stance_L"] + m["stance_R"]) / 2,
            "ds": m["DS"], "flight": m["flight"], "rEF": (m["rEF_L"] + m["rEF_R"]) / 2}


def patients():
    d = json.load(open(os.path.join(ROOT, "validation/human_sci_metrics.json")))
    out = []
    for exp, e in d.items():
        for cond, c in e["conditions"].items():
            out.append({"id": exp, "cond": cond, "worse": e["worse_side"],
                        "stride": np.mean([c["stride_s_Sx"], c["stride_s_Dx"]]),
                        "stance": np.mean([c["stance_Sx"], c["stance_Dx"]]), "ds": c["ds"],
                        "stance_Sx": c["stance_Sx"], "stance_Dx": c["stance_Dx"]})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="arch2")
    ap.add_argument("--tag", default="", help="suffix of the output files (default: none)")
    args = ap.parse_args()
    grid_dir = "7b_wl" if args.root == "p7" else "7b"
    pats = patients()
    grid = {}
    for p in sorted(glob.glob(os.path.join(ROOT, f"results/human_modes/{args.root}/{grid_dir}/w*_l*/bws50.h5"))):
        tag = os.path.basename(os.path.dirname(p))
        s, L = (float(x[1:]) for x in tag.split("_"))
        grid[(s, L)] = mrow(p)
    chains = {}
    for p in sorted(glob.glob(os.path.join(ROOT, f"results/human_modes/{args.root}/chain/r*_*/s10/bws50.h5"))):
        tag = os.path.basename(os.path.dirname(os.path.dirname(p)))
        chains[tag] = mrow(p)
    modes = {os.path.basename(p)[:-3]: mrow(p) for p in sorted(glob.glob(os.path.join(ROOT, f"results/human_modes/{args.root}/7a/*.h5")))}
    ref = json.load(open(os.path.join(ROOT, "validation/human_gait_reference.json")))

    print("Patients (both legs averaged)")
    print(f"  {'id':5s} {'condition':10s} {'stride s':>8s} {'stance':>7s} {'DS':>5s}")
    for r in pats:
        print(f"  {r['id']:5s} {r['cond']:10s} {r['stride']:8.2f} {r['stance']:7.2f} {r['ds']:5.2f}")
    print("\nModel healthy modes (7a): " + "; ".join(f"{k} {v['stride']:.2f}s stance {v['stance']:.2f} DS {v['ds']:.2f}" for k, v in modes.items()))
    print("\nModel grid, one session (stride s / stance / DS / r(E,F)); rows: strength s, columns: loading L")
    Ls = sorted({k[1] for k in grid}, reverse=True)
    print(f"  {'s':>5s} " + " ".join(f"{'L ' + str(l):>24s}" for l in Ls))
    for s in sorted({k[0] for k in grid}, reverse=True):
        print(f"  {s:5.2f} " + " ".join(
            (f"{grid[(s, l)]['stride']:5.2f} {grid[(s, l)]['stance']:5.2f} {grid[(s, l)]['ds']:5.2f} {grid[(s, l)]['rEF']:6.2f}" if (s, l) in grid else " " * 23) + " "
            for l in Ls))
    print("\nModel chains, session 10: " + "; ".join(f"{k} {v['stride']:.2f}s stance {v['stance']:.2f} DS {v['ds']:.2f}" for k, v in chains.items()))

    # nearest model cell per patient condition in (stride, stance), normalised by the patient spread
    sd_stride = np.std([r["stride"] for r in pats]) or 1.0
    sd_stance = np.std([r["stance"] for r in pats]) or 1.0
    cells = [(f"grid s{s} L{l}", v) for (s, l), v in grid.items()] + [(f"chain {k}", v) for k, v in chains.items()]
    print("\nNearest model cell in (stride, stance) per patient condition")
    near = {}
    for r in pats:
        best = min(cells, key=lambda c: ((c[1]["stride"] - r["stride"]) / sd_stride) ** 2 + ((c[1]["stance"] - r["stance"]) / sd_stance) ** 2)
        near[f"{r['id']} {r['cond']}"] = {"cell": best[0], **best[1]}
        print(f"  {r['id']} {r['cond']:10s} patient {r['stride']:.2f}s / {r['stance']:.2f}  ->  {best[0]:24s} {best[1]['stride']:.2f}s / {best[1]['stance']:.2f}")

    os.makedirs(os.path.join(ROOT, "plots/p8"), exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
    for a, key, lab in ((ax[0], "stance", "stance fraction"), (ax[1], "ds", "double support")):
        a.scatter([v["stride"] for v in grid.values()], [v[key] for v in grid.values()], c="#9aa6b2", s=28, label="model grid (s × L)")
        a.scatter([v["stride"] for v in chains.values()], [v[key] for v in chains.values()], c="#2a7fbb", marker="s", s=44, label="model chains, session 10")
        a.scatter([v["stride"] for v in modes.values()], [v[key] for v in modes.values()], c="#222", marker="^", s=50, label="model healthy modes")
        for r in pats:
            a.scatter(r["stride"], r[key], c="#d1495b", marker="D", s=50)
            a.annotate(f"{r['id'][-2:]}{r['cond'][:2]}", (r["stride"], r[key]), fontsize=7, xytext=(3, 3), textcoords="offset points")
        a.scatter([], [], c="#d1495b", marker="D", label="patients (IMU)")
        a.set_xlabel("stride (s)"); a.set_ylabel(lab); a.grid(alpha=.25)
    ax[0].legend(fontsize=7, loc="lower right")
    fig.suptitle(f"Model ({args.root}) vs the four SCI patients: gait timing (debug-small, seed 12345; patient stance and DS are IMU estimates)", fontsize=9)
    fig.tight_layout()
    out = os.path.join(ROOT, f"plots/p8/model_vs_patients{args.tag}.png")
    fig.savefig(out, dpi=140)
    json.dump({"patients": pats, "grid": {f"s{k[0]}_L{k[1]}": v for k, v in grid.items()}, "chains": chains, "modes": modes,
               "nearest": near}, open(os.path.join(ROOT, f"validation/p8_model_vs_patients{args.tag}.json"), "w"), indent=1, default=float)
    print("wrote", out)


if __name__ == "__main__":
    main()
