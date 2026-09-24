#!/usr/bin/env python3
"""
cpg_stdp_weight_matrix.py
STDP weight trajectories for the canonical (sensory) model: both legs x the
three plastic projections (CUT->RG-E, Ia-E->RG-E, Ia-F->RG-F) x the five
locomotion modes (slow / medium=plantar=baseline / fast walk, toe / air
stepping), with the three learning rates overlaid in each panel.

Left-leg rows white, right-leg rows tinted. No in-figure title (moves to the
LaTeX caption).
"""
import argparse, glob, os
import h5py, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

# rows: (leg group, weight key, row label, y-max)
ROWS = [
    ("leg_L", "cut->rge_mean", "L  CUT→RG-E", 72),
    ("leg_L", "ia->rge_mean",  "L  Ia-E→RG-E", 12),
    ("leg_L", "ia->rgf_mean",  "L  Ia-F→RG-F", 12),
    ("leg_R", "cut->rge_mean", "R  CUT→RG-E", 72),
    ("leg_R", "ia->rge_mean",  "R  Ia-E→RG-E", 12),
    ("leg_R", "ia->rgf_mean",  "R  Ia-F→RG-F", 12),
]
# columns: (label, filename stem) — the five locomotion modes (sensory arm)
COLS = [
    ("slow walk\n6 cm/s",                  "cpg_sensory_stdp_06cms"),
    ("medium walk / plantar\n13.5 cm/s (baseline)", "cpg_sensory_stdp_13_5cms"),
    ("fast walk\n21 cm/s",                 "cpg_sensory_stdp_21cms"),
    ("toe stepping\npartial unloading",    "cpg_ablsens_toe"),
    ("air stepping\nfull unloading",       "cpg_ablsens_air"),
]
LAMBDAS = [("lam1em2", "λ=10⁻²", "#7f1d1d"),
           ("lam1em3", "λ=10⁻³", "#d62728"),
           ("lam1em4", "λ=10⁻⁴", "#2ca02c"),
           ("lam1em5", "λ=10⁻⁵", "#1f77b4"),
           ("lam1em6", "λ=10⁻⁶", "#9467bd")]


def _find(indir, stem, lam):
    h = sorted(glob.glob(os.path.join(indir, f"{stem}_{lam}_*.h5")))
    return h[0] if h else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", required=True)
    ap.add_argument("--out", default="paper/figures/fig_stdp_weight_matrix.png")
    ap.add_argument("--dpi", type=int, default=170)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    nr, nc = len(ROWS), len(COLS)
    fig, axes = plt.subplots(nr, nc, figsize=(3.3 * nc, 1.7 * nr),
                             squeeze=False, sharex=True)

    for r, (leg, wkey, rlabel, ymax) in enumerate(ROWS):
        for c, (clabel, stem) in enumerate(COLS):
            ax = axes[r][c]
            if leg == "leg_R":
                ax.set_facecolor("#f3f6fb")
            for lam, llab, col in LAMBDAS:
                f = _find(args.indir, stem, lam)
                if f is None:
                    continue
                with h5py.File(f, "r") as h:
                    key = f"{leg}/weights/{wkey}"
                    if key not in h:
                        continue
                    t = np.asarray(h["times_ms"]) / 1000.0
                    w = np.asarray(h[key])
                ax.plot(t, w, color=col, lw=1.4, label=llab)
            ax.set_ylim(0, ymax); ax.set_xlim(0, 120)
            ax.set_yticks([0, ymax // 2, ymax] if ymax == 12 else [0, 30, 60])
            ax.grid(alpha=0.2)
            ax.tick_params(labelsize=9)
            if r == 0:
                ax.set_title(clabel, fontsize=11, fontweight="bold")
            if c == 0:
                ax.set_ylabel(rlabel + "\nweight (pA)", fontsize=10)
            if r == nr - 1:
                ax.set_xlabel("time (s)", fontsize=10)
    _L = [chr(97 + i) if i < 26 else chr(96 + i // 26) + chr(97 + i % 26) for i in range(nr * nc)]
    for i, ax in enumerate(axes.flat):
        ax.text(0.03, 0.94, f"({_L[i]})", transform=ax.transAxes, fontsize=9,
                fontweight="bold", va="top", ha="left")
    axes[-1][-1].legend(fontsize=9, loc="lower right", framealpha=0.92)
    fig.tight_layout()
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[stdp-weight-matrix] saved {args.out}")


if __name__ == "__main__":
    main()
