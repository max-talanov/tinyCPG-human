#!/usr/bin/env python3
"""
cpg_network_activity.py
Zhang-style combined network-activity figure: population firing rates of
the whole recorded circuit (rhythm generators, reciprocal-inhibition and
Ia interneurons, motor pools) for leg L plus the contralateral RG, across
either the three walking speeds or the graded-ablation conditions.

Rows (Zhang lf-F/lf-E ordering — F before E):
    L RG-F, L RG-E            rhythm generators
    L InF,  L InE             reciprocal-inhibition interneurons
    L IaIntF, L IaIntE        Ia inhibitory interneurons
    L M-F,  L M-E             motor pools (muscle relays)
    R RG-F, R RG-E            contralateral RG (shows L/R trot offset)

Columns:
    --mode speed     → slow / medium / fast walk (1200 / 520 / 350 ms)
    --mode ablation  → baseline / toe / air (set --ablation-prefix +
                       --indir to pick the stim or natural arm)

NOTE: requires the interneuron-rate signals (ine/inf/iaint_e/iaint_f),
added by MOD_NET_RECORD — re-run the model after that change.

Usage:
  python3 cpg_network_activity.py --mode speed --indir results/<date> \\
      --out plots/paper/fig_network_speed.png
  python3 cpg_network_activity.py --mode ablation --indir results/<date> \\
      --ablation-prefix cpg_ablstim --out plots/paper/fig_network_ablstim.png
"""

import argparse
import glob
import os
from typing import Optional

import h5py
import matplotlib.pyplot as plt
import numpy as np


SPEED_COLS = [("06cms", "slow walk\n6 cm/s (1200 ms)", 1200),
              ("13_5cms", "medium walk\n13.5 cm/s (520 ms)", 520),
              ("21cms", "fast walk\n21 cm/s (350 ms)", 350)]
ABL_COLS = [("baseline", "baseline\nIa,CUT 1.0", 520),
            ("toe", "toe stepping\nIa,CUT 0.5", 520),
            ("air", "air stepping\nIa,CUT 0.1", 520)]

# Full circuit for BOTH legs (Zhang-style, F before E within each population).
ROWS = [
    ("leg_L/rgf", "L RG-F"), ("leg_L/rge", "L RG-E"),
    ("leg_L/inf", "L InF"),  ("leg_L/ine", "L InE"),
    ("leg_L/iaint_f", "L IaInt-F"), ("leg_L/iaint_e", "L IaInt-E"),
    ("leg_L/mus_f", "L M-F"), ("leg_L/mus_e", "L M-E"),
    ("leg_R/rgf", "R RG-F"), ("leg_R/rge", "R RG-E"),
    ("leg_R/inf", "R InF"),  ("leg_R/ine", "R InE"),
    ("leg_R/iaint_f", "R IaInt-F"), ("leg_R/iaint_e", "R IaInt-E"),
    ("leg_R/mus_f", "R M-F"), ("leg_R/mus_e", "R M-E"),
]


def _find(indir, pat) -> Optional[str]:
    h = sorted(glob.glob(os.path.join(indir, pat)))
    return h[0] if h else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["speed", "ablation"], default="speed")
    ap.add_argument("--indir", required=True)
    ap.add_argument("--lambda-tag", default="lam1em3")
    ap.add_argument("--ablation-prefix", default="cpg_ablgrad",
                    help="For --mode ablation: cpg_ablgrad (natural), cpg_ablstim (stim), "
                         "or cpg_ablsens (sensory-learning arm).")
    ap.add_argument("--speed-prefix", default="cpg_speed_stdp",
                    help="For --mode speed: cpg_speed_stdp (descending arm) or "
                         "cpg_sensory_stdp (sensory-learning arm).")
    ap.add_argument("--n-cycles", type=int, default=5)
    ap.add_argument("--out", default="plots/paper/fig_network_activity.png")
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    cols = SPEED_COLS if args.mode == "speed" else ABL_COLS
    lam = args.lambda_tag

    def colfile(tag):
        if args.mode == "speed":
            return _find(args.indir, f"{args.speed_prefix}_{tag}_{lam}_*.h5")
        return _find(args.indir, f"{args.ablation_prefix}_{tag}_{lam}_*.h5")

    files = {tag: colfile(tag) for tag, _l, _p in cols}
    missing = [t for t, f in files.items() if f is None]
    if missing:
        print(f"[network] WARNING missing columns: {missing}")

    plt.rcParams.update({"font.size": 8, "axes.titlesize": 10, "axes.labelsize": 8})
    nr, nc = len(ROWS), len(cols)
    fig, axes = plt.subplots(nr, nc, figsize=(3.4 * nc, 0.95 * nr),
                             squeeze=False, sharex="col")

    for r, (key, rlabel) in enumerate(ROWS):
        ymax = 1.0
        series = {}
        for tag, _lbl, per in cols:
            f = files[tag]
            if f is None:
                continue
            with h5py.File(f, "r") as h:
                if key not in h:
                    continue
                t = np.asarray(h["times_ms"]); y = np.asarray(h[key])
                sim = float(h.attrs.get("sim_ms", t.max()))
            z = max(0.0, sim - args.n_cycles * per)
            m = t >= z
            series[tag] = (t[m] - z, y[m], per)
            ymax = max(ymax, float(np.nanpercentile(y[m], 99)) * 1.1)
        for c, (tag, _lbl, per) in enumerate(cols):
            ax = axes[r][c]
            if tag in series:
                tt, yy, per = series[tag]
                ax.plot(tt, yy, color="#27408b", linewidth=0.9)
                ax.set_xlim(0, args.n_cycles * per)
            ax.set_ylim(0, ymax); ax.set_yticks([0, round(ymax)])
            # faint background tint to separate the two legs (Zhang-style blocks)
            if rlabel.startswith("R "):
                ax.set_facecolor("#f3f6fb")
            if c == 0:
                ax.set_ylabel(rlabel, rotation=0, ha="right", va="center",
                              fontsize=9, labelpad=24)
            if r == 0:
                ax.set_title(cols[c][1], fontsize=9)
            if r == nr - 1:
                ax.set_xlabel("time (ms, last cycles)")
            ax.tick_params(labelsize=6)

    mode_desc = ("walking speed" if args.mode == "speed"
                 else f"graded ablation ({'stim' if 'stim' in args.ablation_prefix else 'natural'})")
    fig.tight_layout(rect=(0.02, 0, 1, 0.975))
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[network] saved {args.out}")


if __name__ == "__main__":
    main()
