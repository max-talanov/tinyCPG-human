#!/usr/bin/env python3
"""
cpg_gait_gallery.py
Paper Figure — gait gallery: clean force-profile comparison
(fig4-top-panel style) across the three walking speeds and the three
graded-ablation modes, at a single STDP learning rate (default baseline).

Two rows × three columns, each panel Force-E (solid) / Force-F (dashed),
last-window zoom on the converged steady-state gait:
  Row 1 (speeds, Phase A):    6 / 13.5 / 21 cm/s   (1200 / 520 / 350 ms)
  Row 2 (ablation, Phase B):  baseline / toe / air  (Ia gain 1.0 / 0.5 / 0.1)

Usage:
  python3 cpg_gait_gallery.py \\
      --indir results/2026-06-19 --outdir plots/paper \\
      --out plots/paper/fig7_gait_gallery.png --lambda-tag lam1em3
"""

import argparse
import glob
import os
import re
from typing import Dict, Optional

import h5py
import matplotlib.pyplot as plt
import numpy as np


# Speed conditions (Phase A) — file tag → (label, commanded period ms)
SPEED_PANELS = [
    ("06cms",   "slow walk · ≈6 cm/s\n(1200 ms)", 1200),
    ("13_5cms", "medium walk · ≈13.5 cm/s\n(520 ms)", 520),
    ("21cms",   "fast walk · ≈21 cm/s\n(350 ms)", 350),
]
# Ablation conditions (Phase B) — file tag → label
ABLATION_PANELS = [
    ("baseline", "baseline\nIa gain 1.0 (weight-bearing)"),
    ("toe",      "toe stepping\nIa gain 0.5 (partial weight)"),
    ("air",      "air stepping\nIa gain 0.1 (unloaded)"),
]


def _find(indir: str, pattern: str) -> Optional[str]:
    hits = sorted(glob.glob(os.path.join(indir, pattern)))
    return hits[0] if hits else None


def _zoom_force(ax, path: str, color: str, zoom_ms: float, title: str):
    with h5py.File(path, "r") as h:
        t = np.asarray(h["times_ms"])
        fe = np.asarray(h["leg_L/force_e"])
        ff = np.asarray(h["leg_L/force_f"])
        sim_ms = float(h.attrs.get("sim_ms", t.max() if t.size else 120000.0))
    z0 = max(0.0, sim_ms - zoom_ms)
    mask = t >= z0
    ax.plot(t[mask], fe[mask], color=color, linewidth=1.3, label="E")
    ax.plot(t[mask], ff[mask], color=color, linewidth=1.0, linestyle="--",
            alpha=0.7, label="F")
    ax.set_xlim(z0, sim_ms)
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", type=str, default="results/2026-06-19")
    ap.add_argument("--outdir", type=str, default="plots/paper")
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--lambda-tag", type=str, default="lam1em3",
                    help="Which STDP-λ tag to show (default lam1em3 = baseline).")
    ap.add_argument("--zoom-ms", type=float, default=10000.0,
                    help="Width of the converged-tail window shown (ms).")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    out_path = args.out or os.path.join(args.outdir, "fig7_gait_gallery.png")
    lam = args.lambda_tag

    # Resolve files
    speed_files = [(lbl, per, _find(args.indir, f"cpg_speed_stdp_{tag}_{lam}_*.h5"))
                   for tag, lbl, per in SPEED_PANELS]
    abl_files = [(lbl, _find(args.indir, f"cpg_ablgrad_{tag}_{lam}_*.h5"))
                 for tag, lbl in ABLATION_PANELS]

    n_missing = sum(1 for _, _, f in speed_files if f is None) + \
                sum(1 for _, f in abl_files if f is None)
    if n_missing:
        print(f"[gallery] WARNING: {n_missing} panel(s) missing for λ={lam}")

    plt.rcParams.update({
        "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 10,
        "legend.fontsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
    })

    # viridis for speeds (matches the earlier speed-sweep colour convention)
    speed_colors = [plt.get_cmap("viridis")(v) for v in (0.05, 0.5, 0.9)]
    # graded reds for ablation (intact → degraded)
    abl_colors = ["#1f3b73", "#b5651d", "#c1272d"]

    fig, axes = plt.subplots(2, 3, figsize=(16, 7))

    # Row 1 — speeds
    for c, (lbl, per, f) in enumerate(speed_files):
        ax = axes[0][c]
        if f is None:
            ax.set_facecolor("#f5f5f5")
            ax.text(0.5, 0.5, "missing", ha="center", va="center",
                    transform=ax.transAxes, color="grey")
            ax.set_xticks([]); ax.set_yticks([]); continue
        _zoom_force(ax, f, speed_colors[c], args.zoom_ms, lbl)
        if c == 0:
            ax.set_ylabel("Force E (solid)\n/ F (dashed)  (a.u.)")
            ax.legend(loc="upper right", ncol=2, fontsize=7)

    # Row 2 — ablation modes
    for c, (lbl, f) in enumerate(abl_files):
        ax = axes[1][c]
        if f is None:
            ax.set_facecolor("#f5f5f5")
            ax.text(0.5, 0.5, "missing", ha="center", va="center",
                    transform=ax.transAxes, color="grey")
            ax.set_xticks([]); ax.set_yticks([]); continue
        _zoom_force(ax, f, abl_colors[c], args.zoom_ms, lbl)
        ax.set_xlabel("time (ms)")
        if c == 0:
            ax.set_ylabel("Force E (solid)\n/ F (dashed)  (a.u.)")
            ax.legend(loc="upper right", ncol=2, fontsize=7)

    lam_pretty = re.sub(r"lam(\d+)em(\d+)", r"λ = \1·10⁻\2", lam)
    fig.suptitle(
        "Gait gallery — force profiles across speed (top) and graded sensory "
        f"ablation (bottom)\n(last {args.zoom_ms/1000:.0f} s; {lam_pretty}; "
        "μ=3.5, CV=0.30)",
        fontsize=12, y=1.00,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"[gallery] saved {out_path}")


if __name__ == "__main__":
    main()
