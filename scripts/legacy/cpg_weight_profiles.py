#!/usr/bin/env python3
"""
cpg_weight_profiles.py
STDP weight profiles (learning curves) for all five modes. One panel per mode
showing the plastic weight trajectory over the 120 s run at the three learning
rates. CUT->RG-E (solid, left axis) for every mode; the sensory arms additionally
show the plastic Ia->RG-E (dashed, right axis, low set-point).
"""
import argparse, glob, os
import h5py, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

# (mode label, filename stem, has plastic Ia->RG)
MODES = [
    ("descending (BS+CUT plastic)",   "cpg_speed_stdp_13_5cms",  False),
    ("sensory (Ia→RG plastic, BS frozen)", "cpg_sensory_stdp_13_5cms", True),
    ("epidural-stim (CUT intact)",     "cpg_ablstim_baseline",    False),
    ("natural (CUT,Ia gated)",         "cpg_ablgrad_baseline",    False),
    ("sensory-abl (Ia gated)",         "cpg_ablsens_baseline",    True),
]
LAMBDAS = [("lam1em3", "λ=10⁻³", "#c1440e"),
           ("lam1em4", "λ=10⁻⁴", "#2e7d32"),
           ("lam1em5", "λ=10⁻⁵", "#1f6feb")]


def _find(indir, stem, lam):
    h = sorted(glob.glob(os.path.join(indir, f"{stem}_{lam}_*.h5")))
    return h[0] if h else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", required=True)
    ap.add_argument("--out", default="paper/figures/fig_weight_profiles.png")
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axflat = axes.flat

    for ax, (mlabel, stem, has_ia) in zip(axflat, MODES):
        axr = ax.twinx() if has_ia else None
        for lam, llab, col in LAMBDAS:
            f = _find(args.indir, stem, lam)
            if f is None:
                continue
            with h5py.File(f, "r") as h:
                t = np.asarray(h["times_ms"]) / 1000.0
                cut = np.asarray(h["leg_L/weights/cut->rge_mean"])
                ia = (np.asarray(h["leg_L/weights/ia->rge_mean"])
                      if has_ia and "leg_L/weights/ia->rge_mean" in h else None)
            ax.plot(t, cut, color=col, lw=1.5, label=llab)
            if ia is not None:
                axr.plot(t, ia, color=col, lw=1.2, ls="--", alpha=0.8)
        ax.set_title(mlabel, fontsize=10, fontweight="bold")
        ax.set_xlim(0, 120); ax.set_ylim(0, 72); ax.grid(alpha=0.2)
        ax.set_xlabel("time (s)")
        ax.set_ylabel("CUT→RG-E weight (pA)")
        if axr is not None:
            axr.set_ylim(0, 12)
            axr.set_ylabel("Ia→RG-E weight (pA, dashed)", color="0.35")
            axr.tick_params(axis="y", labelcolor="0.35")
        ax.legend(fontsize=7.5, loc="center right", title="CUT→RG-E", title_fontsize=7.5)

    # last cell: legend / notes
    axn = axflat[5]; axn.axis("off")
    axn.text(0.02, 0.9, "STDP weight profiles — all modes", fontsize=11, fontweight="bold",
             transform=axn.transAxes)
    axn.text(0.02, 0.72,
             "Solid = CUT→RG-E (left axis, plastic in every mode).\n"
             "Dashed = Ia→RG-E (right axis, sensory arms only;\n"
             "self-stabilises at a low ≈4–5 pA set-point).\n\n"
             "Colour = STDP learning rate λ.\n\n"
             "CUT→RG-E converges to ≈63 pA in every mode; the\n"
             "rate sets only the time-to-plateau (~7 s / ~75 s /\n"
             ">120 s for 10⁻³ / 10⁻⁴ / 10⁻⁵). Medium walk (520 ms),\n"
             "baseline loading, μ=3.5, CV=0.30, bio-plausible defaults.",
             fontsize=8.5, transform=axn.transAxes, va="top")

    fig.suptitle("STDP weight profiles across all five learning modes",
                 fontsize=13, fontweight="bold", y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[weight-profiles] saved {args.out}")


if __name__ == "__main__":
    main()
