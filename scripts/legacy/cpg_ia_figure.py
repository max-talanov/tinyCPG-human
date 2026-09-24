#!/usr/bin/env python3
"""
cpg_ia_figure.py
Ia (proprioceptive) afferent activity — both legs — across speed or
graded ablation. The Ia rate (leg_*/ia_e, ia_f) is the force/stretch-driven
closed-loop feedback, gated by limb loading (--ia-feedback-gain) in the
ablation runs.

Rows (4): L Ia-F, L Ia-E, R Ia-F, R Ia-E.
Columns: the 3 states of the mode (speeds, or loading conditions).
Each panel: Ia firing rate (Hz) over the last N cycles.

Usage:
  python3 cpg_ia_figure.py --mode speed   --indir results/<date> --out fig_ia_speed.png
  python3 cpg_ia_figure.py --mode ablstim --indir results/<date> --out fig_ia_ablstim.png
  python3 cpg_ia_figure.py --mode ablgrad --indir results/<date> --out fig_ia_natural.png
"""

import argparse
import glob
import os
from typing import Optional

import h5py
import matplotlib.pyplot as plt
import numpy as np

MODE_COLS = {
    "speed":   ([("06cms", "slow walk\n6 cm/s (1200 ms)", 1200),
                 ("13_5cms", "medium walk\n13.5 cm/s (520 ms)", 520),
                 ("21cms", "fast walk\n21 cm/s (350 ms)", 350)],
                "cpg_speed_stdp", "across speed (Ia intact)"),
    "sensory": ([("06cms", "slow walk\n6 cm/s (1200 ms)", 1200),
                 ("13_5cms", "medium walk\n13.5 cm/s (520 ms)", 520),
                 ("21cms", "fast walk\n21 cm/s (350 ms)", 350)],
                "cpg_sensory_stdp", "sensory learning (Ia→RG plastic), across speed"),
    "ablstim": ([("baseline", "baseline\nIa,CUT 1.0", 520), ("toe", "toe stepping\nIa,CUT 0.5", 520),
                 ("air", "air stepping\nIa,CUT 0.1", 520)], "cpg_ablstim", "stim arm, across loading"),
    "ablgrad": ([("baseline", "baseline\nIa,CUT 1.0", 520), ("toe", "toe stepping\nIa,CUT 0.5", 520),
                 ("air", "air stepping\nIa,CUT 0.1", 520)], "cpg_ablgrad", "natural arm, across loading"),
    "ablsens": ([("baseline", "baseline\nIa,CUT 1.0", 520), ("toe", "toe stepping\nIa,CUT 0.5", 520),
                 ("air", "air stepping\nIa,CUT 0.1", 520)], "cpg_ablsens",
                "sensory learning, across loading (Ia is the gated learning drive)"),
}

ROWS = [("leg_L/ia_f", "L Ia-F"), ("leg_L/ia_e", "L Ia-E"),
        ("leg_R/ia_f", "R Ia-F"), ("leg_R/ia_e", "R Ia-E")]


def _find(indir, pat) -> Optional[str]:
    h = sorted(glob.glob(os.path.join(indir, pat)))
    return h[0] if h else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=list(MODE_COLS), default="speed")
    ap.add_argument("--indir", required=True)
    ap.add_argument("--lambda-tag", default="lam1em3")
    ap.add_argument("--n-cycles", type=int, default=5)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    cols, prefix, desc = MODE_COLS[args.mode]
    lam = args.lambda_tag

    files = {tag: _find(args.indir, f"{prefix}_{tag}_{lam}_*.h5") for tag, _l, _p in cols}

    plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9})
    nr, nc = len(ROWS), len(cols)
    fig, axes = plt.subplots(nr, nc, figsize=(4.2 * nc, 1.9 * nr), squeeze=False, sharey="row")

    for r, (key, rlabel) in enumerate(ROWS):
        # shared y per row for comparability of the gating across conditions
        ymax = 1.0
        ser = {}
        for tag, _lbl, per in cols:
            f = files[tag]
            if f is None:
                continue
            with h5py.File(f, "r") as h:
                t = np.asarray(h["times_ms"]); y = np.asarray(h[key]); sim = float(h.attrs["sim_ms"])
            z = max(0.0, sim - args.n_cycles * per); m = t >= z
            ser[tag] = (t[m] - z, y[m], per)
            ymax = max(ymax, float(np.nanpercentile(y[m], 99)) * 1.1)
        for c, (tag, _lbl, per) in enumerate(cols):
            ax = axes[r][c]
            if tag in ser:
                tt, yy, per = ser[tag]
                ax.plot(tt, yy, color="#117733", linewidth=1.0)
                ax.set_xlim(0, args.n_cycles * per)
            ax.set_ylim(0, ymax); ax.grid(alpha=0.2)
            if rlabel.startswith("R "):
                ax.set_facecolor("#f3f6fb")
            if r == 0:
                ax.set_title(cols[c][1], fontsize=9)
            if c == 0:
                ax.set_ylabel(f"{rlabel}\nIa rate (Hz)", fontsize=9)
            if r == nr - 1:
                ax.set_xlabel("time (ms, last cycles)")

    fig.suptitle(
        f"Ia proprioceptive afferent activity — both legs — {desc}\n"
        f"force/stretch-driven, loading-gated; last {args.n_cycles} cycles; "
        f"λ={lam.replace('lam1em','1·10⁻')}, μ=3.5, CV=0.30",
        fontsize=12, y=0.998)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(args.out, dpi=185, bbox_inches="tight")
    plt.close(fig)
    print(f"[ia] saved {args.out}")


if __name__ == "__main__":
    main()
