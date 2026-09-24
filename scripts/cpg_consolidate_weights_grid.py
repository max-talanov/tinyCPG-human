#!/usr/bin/env python3
"""
cpg_consolidate_weights_grid.py
Weight ("learning") trajectories of the three plastic projections, one panel
per --consolidate condition, in the same dual-axis layout/style as the
paper's Figure 3/4 (scripts/cpg_stdp_weights_grid.py): CUT->RG-E on the left
axis (solid), Ia-E->RG-E / Ia-F->RG-F on the right axis (dashed).

For runs with --consolidate enabled, also overlays each pathway's captured
baseline (dotted, same color) when the HDF5 carries a `consolidation` group
-- this is the actual tag/capture dynamic (live weight vs. the frozen,
non-decaying baseline) from real simulation output, not an illustrative
curve.
"""
import argparse, os
import h5py, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

CUT = ("cut->rge_mean", "CUT→RG-E", "#c1440e")
IAS = [("ia->rge_mean", "Ia-E→RG-E", "#1f77b4"), ("ia->rgf_mean", "Ia-F→RG-F", "#2ca02c")]


def _parse_run(s):
    label, path = s.split("=", 1)
    return label, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True,
                     help="label=path.h5, repeatable -- one panel per condition")
    ap.add_argument("--leg", default="L")
    ap.add_argument("--sim-s", type=float, default=60.0)
    ap.add_argument("--ncols", type=int, default=3)
    ap.add_argument("--out", default="plots/consolidate_weights_grid.png")
    ap.add_argument("--dpi", type=int, default=170)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    plt.rcParams.update({"font.size": 12, "axes.titlesize": 12, "axes.labelsize": 11})

    runs = [_parse_run(s) for s in args.run]
    nc = min(args.ncols, len(runs))
    nr = int(np.ceil(len(runs) / nc))
    fig, axes = plt.subplots(nr, nc, figsize=(4.8 * nc, 3.4 * nr), squeeze=False)

    for i, (label, path) in enumerate(runs):
        r, c = divmod(i, nc)
        ax = axes[r][c]; axr = ax.twinx()
        with h5py.File(path, "r") as h:
            t = np.asarray(h["times_ms"]) / 1000.0
            consolidate_on = bool(h.attrs.get("consolidate", False))
            wkey = f"leg_{args.leg}/weights/{CUT[0]}"
            if wkey in h:
                ax.plot(t, np.asarray(h[wkey]), color=CUT[2], lw=2.0, label=CUT[1] + " weight")
            if consolidate_on:
                bkey = f"leg_{args.leg}/consolidation/{CUT[0].replace('_mean', '')}_baseline_mean"
                if bkey in h:
                    ax.plot(t, np.asarray(h[bkey]), color=CUT[2], lw=1.6, ls=":",
                            label=CUT[1] + " baseline (captured)")
            ia_max = 12.0  # default axis ceiling; expanded below if data exceeds it
            for key, name, col in IAS:
                ikey = f"leg_{args.leg}/weights/{key}"
                if ikey in h:
                    ia_vals = np.asarray(h[ikey])
                    axr.plot(t, ia_vals, color=col, lw=1.4, ls="--", label=name + " weight")
                    finite = ia_vals[np.isfinite(ia_vals)]
                    if finite.size:
                        ia_max = max(ia_max, float(finite.max()))
                if consolidate_on:
                    bkey = f"leg_{args.leg}/consolidation/{key.replace('_mean', '')}_baseline_mean"
                    if bkey in h:
                        axr.plot(t, np.asarray(h[bkey]), color=col, lw=1.2, ls=":",
                                 label=name + " baseline (captured)")
        ax.set_xlim(0, args.sim_s); ax.set_ylim(0, 72); axr.set_ylim(0, ia_max * 1.1)
        ax.grid(alpha=0.2); ax.tick_params(labelsize=9); axr.tick_params(labelsize=9)
        ax.set_title(label, fontsize=13, fontweight="bold")
        ax.set_ylabel("CUT→RG-E weight (pA)", fontsize=10)
        axr.set_ylabel("Ia→RG weight (pA)", fontsize=10, color="0.35")
        axr.tick_params(axis="y", labelcolor="0.35")
        ax.set_xlabel("time (s)", fontsize=10)
        ax.legend(loc="upper left", fontsize=7.5, framealpha=0.9)
        axr.legend(loc="lower right", fontsize=7.5, framealpha=0.9)
    for i in range(len(runs), nr * nc):
        r, c = divmod(i, nc)
        axes[r][c].axis("off")

    _L = [chr(97 + i) if i < 26 else chr(96 + i // 26) + chr(97 + i % 26) for i in range(len(runs))]
    for i, (label, path) in enumerate(runs):
        r, c = divmod(i, nc)
        axes[r][c].text(0.02, 0.97, f"({_L[i]})", transform=axes[r][c].transAxes, fontsize=11,
                        fontweight="bold", va="top", ha="left")

    fig.tight_layout()
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[consolidate-weights-grid] saved {args.out}")


if __name__ == "__main__":
    main()
