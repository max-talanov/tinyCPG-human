#!/usr/bin/env python3
"""
cpg_stdp_matrix.py
STDP weight-trajectory matrices for BOTH legs and all three plastic
projections, across each experiment mode (speed / ablation-stim /
ablation-natural). Three λ overlaid per panel.

Rows (6): L CUT→RG-E, L BS→RG-E, L BS→RG-F, R CUT→RG-E, R BS→RG-E, R BS→RG-F
Columns: the three states of the mode (speeds, or loading conditions).

Usage:
  python3 cpg_stdp_matrix.py --mode speed    --indir results/<date> --out fig_stdp_speed.png
  python3 cpg_stdp_matrix.py --mode ablstim  --indir results/<date> --out fig_stdp_ablstim.png
  python3 cpg_stdp_matrix.py --mode ablgrad  --indir results/<date> --out fig_stdp_natural.png
"""

import argparse
import glob
import os
import re
from typing import Optional

import h5py
import matplotlib.pyplot as plt
import numpy as np


LAMBDA_ORDER = ["lam1em5", "lam1em4", "lam1em3"]
LAM_COLOR = {"lam1em5": "#1f77b4", "lam1em4": "#2ca02c", "lam1em3": "#d62728"}
_SUP = {"-": "⁻", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵"}

# Descending-learning projections (BS plastic). Sensory modes override this
# with the Ia->RG projections (BS is frozen there, so bs->* are not tracked).
PROJS = [("cut->rge_mean", "CUT→RG-E"), ("bs->rge_mean", "BS→RG-E"),
         ("bs->rgf_mean", "BS→RG-F")]
PROJS_SENSORY = [("cut->rge_mean", "CUT→RG-E"), ("ia->rge_mean", "Ia-E→RG-E"),
                 ("ia->rgf_mean", "Ia-F→RG-F")]

MODE_COLS = {
    "speed":   ([("06cms", "slow walk\n6 cm/s"), ("13_5cms", "medium walk\n13.5 cm/s"),
                 ("21cms", "fast walk\n21 cm/s")], "cpg_speed_stdp", "Ia intact, across speed"),
    "sensory": ([("06cms", "slow walk\n6 cm/s"), ("13_5cms", "medium walk\n13.5 cm/s"),
                 ("21cms", "fast walk\n21 cm/s")], "cpg_sensory_stdp",
                "sensory learning (frozen BS + plastic Ia→RG), across speed"),
    "ablstim": ([("baseline", "baseline"), ("toe", "toe stepping"), ("air", "air stepping")],
                "cpg_ablstim", "stim arm (CUT intact), across loading"),
    "ablgrad": ([("baseline", "baseline"), ("toe", "toe stepping"), ("air", "air stepping")],
                "cpg_ablgrad", "natural arm (CUT gated), across loading"),
    "ablsens": ([("baseline", "baseline"), ("toe", "toe stepping"), ("air", "air stepping")],
                "cpg_ablsens", "sensory learning, across loading (Ia is the gated learning drive)"),
}

# Modes whose plastic projections are the sensory (Ia->RG) set.
SENSORY_MODES = {"sensory", "ablsens"}


def _lam(tag):
    m = re.match(r"lam(\d+)em(\d+)", tag)
    return f"λ=1·10{''.join(_SUP.get(c, c) for c in '-' + m.group(2))}"


def _find(indir, pat) -> Optional[str]:
    h = sorted(glob.glob(os.path.join(indir, pat)))
    return h[0] if h else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=list(MODE_COLS), default="speed")
    ap.add_argument("--indir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--xlim-s", type=float, default=None,
                    help="Zoom x-axis to [0,X] s (e.g. 20 for early saturation).")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    cols, prefix, desc = MODE_COLS[args.mode]
    projs = PROJS_SENSORY if args.mode in SENSORY_MODES else PROJS

    def cfile(tag, lam):
        return _find(args.indir, f"{prefix}_{tag}_{lam}_*.h5")

    rows = [(leg, key, lbl) for leg in ("L", "R") for key, lbl in projs]
    nr, nc = len(rows), len(cols)
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9})
    fig, axes = plt.subplots(nr, nc, figsize=(4.4 * nc, 2.6 * nr),
                             squeeze=False, sharey="row")

    for r, (leg, key, plabel) in enumerate(rows):
        for c, (tag, clabel) in enumerate(cols):
            ax = axes[r][c]
            for lam in LAMBDA_ORDER:
                f = cfile(tag, lam)
                if f is None:
                    continue
                with h5py.File(f, "r") as h:
                    wg = h[f"leg_{leg}/weights"]
                    if key not in wg:
                        continue
                    w = np.asarray(wg[key]); t = np.asarray(h["times_ms"])[: w.size]
                ax.plot(t / 1000.0, w, color=LAM_COLOR[lam], linewidth=1.3, label=_lam(lam))
            if key == "bs->rge_mean":
                ax.axhline(30.0, ls="--", color="grey", alpha=0.5, label="W$_{max}$=30")
            if key in ("ia->rge_mean", "ia->rgf_mean"):
                ax.axhline(10.0, ls="--", color="grey", alpha=0.5, label="W$_{max}$=10")
            if args.xlim_s:
                ax.set_xlim(0, args.xlim_s)
            ax.grid(alpha=0.2)
            if leg == "R":
                ax.set_facecolor("#f3f6fb")
            if r == 0:
                ax.set_title(clabel, fontsize=10)
            if c == 0:
                ax.set_ylabel(f"{leg}  {plabel}\nweight (pA)", fontsize=9)
            if r == nr - 1:
                ax.set_xlabel("time (s)")
            if r == 0 and c == nc - 1:
                ax.legend(loc="lower right", fontsize=7)

    fig.suptitle(
        f"STDP weight trajectories — both legs × 3 projections × 3 λ\n"
        f"{desc}  (μ=3.5, CV=0.30; L rows white, R rows tinted)",
        fontsize=12, y=0.998)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(args.out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"[stdp] saved {args.out}")


if __name__ == "__main__":
    main()
