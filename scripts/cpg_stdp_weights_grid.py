#!/usr/bin/env python3
"""
cpg_stdp_weights_grid.py  (Results figure #2)
Combined STDP weight trajectories of all three plastic projections
(CUT->RG-E, Ia-E->RG-E, Ia-F->RG-F) across the 15 rehabilitation modes:
5 locomotion modes (rows) x 3 STDP rates lambda (columns). Leg L, canonical
sensory model. CUT on the left axis (pA), the two Ia projections on the right
axis (pA, low set-point). Large fonts; every axis labelled with units.
"""
import argparse, glob, os
import h5py, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

MODES = [
    ("slow walk\n6 cm/s",                     "cpg_sensory_stdp_06cms"),
    ("medium / plantar\n13.5 cm/s (baseline)", "cpg_sensory_stdp_13_5cms"),
    ("fast walk\n21 cm/s",                    "cpg_sensory_stdp_21cms"),
    ("toe stepping\npartial unloading",       "cpg_ablsens_toe"),
    ("air stepping\nfull unloading",          "cpg_ablsens_air"),
]
LAMBDAS = [("lam1em2", "λ = 10⁻²"), ("lam1em3", "λ = 10⁻³"), ("lam1em4", "λ = 10⁻⁴"),
           ("lam1em5", "λ = 10⁻⁵"), ("lam1em6", "λ = 10⁻⁶")]
CUT = ("cut->rge_mean", "CUT→RG-E", "#c1440e")
IAS = [("ia->rge_mean", "Ia-E→RG-E", "#1f77b4"), ("ia->rgf_mean", "Ia-F→RG-F", "#2ca02c")]


def _find(indir, stem, lam):
    h = sorted(glob.glob(os.path.join(indir, f"{stem}_{lam}_*.h5")))
    return h[0] if h else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", required=True)
    ap.add_argument("--out", default="paper/figures/fig_stdp_weights_grid.png")
    ap.add_argument("--dpi", type=int, default=170)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    plt.rcParams.update({"font.size": 12, "axes.titlesize": 13, "axes.labelsize": 12})

    nr, nc = len(MODES), len(LAMBDAS)
    fig, axes = plt.subplots(nr, nc, figsize=(4.6 * nc, 2.5 * nr), squeeze=False, sharex=True)

    for r, (mlabel, stem) in enumerate(MODES):
        for c, (lam, llab) in enumerate(LAMBDAS):
            ax = axes[r][c]; axr = ax.twinx()
            f = _find(args.indir, stem, lam)
            if f is not None:
                with h5py.File(f, "r") as h:
                    t = np.asarray(h["times_ms"]) / 1000.0
                    if f"leg_L/weights/{CUT[0]}" in h:
                        ax.plot(t, np.asarray(h[f"leg_L/weights/{CUT[0]}"]),
                                color=CUT[2], lw=2.0, label=CUT[1])
                    for key, name, col in IAS:
                        if f"leg_L/weights/{key}" in h:
                            axr.plot(t, np.asarray(h[f"leg_L/weights/{key}"]),
                                     color=col, lw=1.6, ls="--", label=name)
            ax.set_xlim(0, 120); ax.set_ylim(0, 72); axr.set_ylim(0, 12)
            ax.grid(alpha=0.2); ax.tick_params(labelsize=9); axr.tick_params(labelsize=9)
            if r == 0:
                ax.set_title(llab, fontsize=14, fontweight="bold")
            if c == 0:
                ax.set_ylabel(mlabel + "\n\nCUT→RG-E weight (pA)", fontsize=11)
            else:
                ax.set_ylabel("CUT→RG-E weight (pA)", fontsize=10)
            if c == nc - 1:
                axr.set_ylabel("Ia→RG weight (pA)", fontsize=11, color="0.35")
            axr.tick_params(axis="y", labelcolor="0.35")
            if r == nr - 1:
                ax.set_xlabel("time (s)", fontsize=12)
    # panel index letters (row-major)
    _L = [chr(97 + i) if i < 26 else chr(96 + i // 26) + chr(97 + i % 26) for i in range(nr * nc)]
    for i, ax in enumerate(axes.flat):
        ax.text(0.03, 0.96, f"({_L[i]})", transform=ax.transAxes, fontsize=12,
                fontweight="bold", va="top", ha="left")

    # single combined legend
    h1 = [plt.Line2D([0], [0], color=CUT[2], lw=2.0, label=CUT[1] + " (left axis)")]
    h2 = [plt.Line2D([0], [0], color=c, lw=1.6, ls="--", label=n + " (right axis)")
          for _, n, c in IAS]
    axes[-1][-1].legend(handles=h1 + h2, loc="lower right", ncol=1, fontsize=10,
                        frameon=True, framealpha=0.95)
    fig.tight_layout()
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[stdp-weights-grid] saved {args.out}")


if __name__ == "__main__":
    main()
