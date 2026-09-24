#!/usr/bin/env python3
"""
cpg_gallery_matrix.py
Gallery-style (converged-tail, E-solid / F-dashed) figures spanning the
full STDP-λ dimension:

  fig9  — speed × λ      force gallery   (3 speeds  × 3 λ)
  fig10 — ablation × λ   force gallery   (3 gains   × 3 λ)
  fig11 — weight profiles per λ          (CUT→RGE, BS→RGE, BS→RGF means)

All read the λ ∈ {1e-5, 1e-4, 1e-3} runs (120 s). The force galleries
show the converged tail (last `--zoom-ms`); the weight figure shows the
full-run mean-weight trajectories with the three λ overlaid.

Usage:
  python3 cpg_gallery_matrix.py --indir results/2026-06-20 --outdir plots/paper
"""

import argparse
import glob
import os
import re
from typing import Dict, List, Optional, Tuple

import h5py
import matplotlib.pyplot as plt
import numpy as np


LAMBDA_ORDER = ["lam1em5", "lam1em4", "lam1em3"]
_SUP = {"-": "⁻", "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
        "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"}


def _lam_label(tag: str) -> str:
    m = re.match(r"lam(\d+)em(\d+)", tag)
    if not m:
        return tag
    sup = "".join(_SUP.get(c, c) for c in f"-{m.group(2)}")
    return f"λ = {m.group(1)}·10{sup}"


# Speed conditions (Phase A) — file tag → (label, period ms)
SPEEDS = [
    ("06cms",   "slow walk\n≈6 cm/s (1200 ms)", 1200),
    ("13_5cms", "medium walk\n≈13.5 cm/s (520 ms)", 520),
    ("21cms",   "fast walk\n≈21 cm/s (350 ms)", 350),
]
# Ablation conditions (Phase B) — file tag → label
GAINS = [
    ("baseline", "baseline\nIa gain 1.0"),
    ("toe",      "toe stepping\nIa gain 0.5"),
    ("air",      "air stepping\nIa gain 0.1"),
]


def _find(indir: str, pattern: str) -> Optional[str]:
    hits = sorted(glob.glob(os.path.join(indir, pattern)))
    return hits[0] if hits else None


# Dark, high-contrast E/F colours for force-profile comparison.
DARK_E = "#0b2545"   # very dark navy (extensor, solid)
DARK_F = "#7a0010"   # dark crimson   (flexor, dashed)


def _force_panel(ax, path, color, zoom_ms, title=None, window="last", color_f=None):
    with h5py.File(path, "r") as h:
        t = np.asarray(h["times_ms"])
        fe = np.asarray(h["leg_L/force_e"]); ff = np.asarray(h["leg_L/force_f"])
        sim_ms = float(h.attrs.get("sim_ms", t.max() if t.size else 120000.0))
    if window == "first":
        z0, z1 = 0.0, min(zoom_ms, sim_ms)
    else:
        z0, z1 = max(0.0, sim_ms - zoom_ms), sim_ms
    m = (t >= z0) & (t <= z1)
    cf = color_f if color_f is not None else color
    f_alpha = 0.9 if color_f is not None else 0.7
    ax.plot(t[m], fe[m], color=color, linewidth=1.2, label="E")
    ax.plot(t[m], ff[m], color=cf, linewidth=1.0, linestyle="--", alpha=f_alpha, label="F")
    ax.set_xlim(z0, z1); ax.grid(alpha=0.2)
    if title:
        ax.set_title(title, fontsize=9)


def _force_matrix(indir, rows, file_fn, row_colors, outpath, suptitle, zoom_ms,
                  window="last", dark=False, dpi=170):
    """rows: list of (tag, label); file_fn(tag, lam) -> path; 3 λ columns.

    dark=True overrides the per-row colour with a uniform dark navy E /
    dark crimson F, so the force-PROFILE shape is what differs between
    panels (best for cross-condition comparison).
    """
    nr, nc = len(rows), len(LAMBDA_ORDER)
    fig, axes = plt.subplots(nr, nc, figsize=(4.6 * nc, 3.1 * nr), squeeze=False)
    for r, (tag, lbl) in enumerate(rows):
        for c, lam in enumerate(LAMBDA_ORDER):
            ax = axes[r][c]
            f = file_fn(tag, lam)
            if f is None:
                ax.set_facecolor("#f5f5f5")
                ax.text(0.5, 0.5, "missing", ha="center", va="center",
                        transform=ax.transAxes, color="grey")
                ax.set_xticks([]); ax.set_yticks([]); continue
            ce = DARK_E if dark else row_colors[r]
            cf = DARK_F if dark else None
            _force_panel(ax, f, ce, zoom_ms, window=window, color_f=cf,
                         title=(_lam_label(lam) if r == 0 else None))
            if c == 0:
                ax.set_ylabel(f"{lbl}\nForce E / F (a.u.)", fontsize=9)
                ax.legend(loc="upper right", ncol=2, fontsize=7)
            if r == nr - 1:
                ax.set_xlabel("time (ms)")
    fig.suptitle(suptitle, fontsize=12, y=1.00)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(outpath, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[gallery] saved {outpath}  (dpi={dpi}, dark={dark})")


def _weight_matrix(indir, cols, file_fn, outpath, suptitle, xlim_s=None):
    """Matrix of weight trajectories: rows = the 3 plastic projections,
    columns = states (speeds or ablation gains); 3 λ overlaid per panel.

    cols: list of (tag, label).  file_fn(tag, lam) -> path.
    xlim_s: if set, restrict the x-axis to [0, xlim_s] seconds (zoom on the
            early saturation dynamics).
    """
    palette = {"lam1em5": "#1f77b4", "lam1em4": "#2ca02c", "lam1em3": "#d62728"}
    projs = [("cut->rge_mean", "CUT→RG-E"), ("bs->rge_mean", "BS→RG-E"),
             ("bs->rgf_mean", "BS→RG-F")]
    nr, nc = len(projs), len(cols)
    fig, axes = plt.subplots(nr, nc, figsize=(4.6 * nc, 3.0 * nr),
                             squeeze=False, sharey="row")
    for r, (key, plabel) in enumerate(projs):
        for c, (tag, clabel) in enumerate(cols):
            ax = axes[r][c]
            for lam in LAMBDA_ORDER:
                f = file_fn(tag, lam)
                if f is None:
                    continue
                with h5py.File(f, "r") as h:
                    wg = h["leg_L/weights"]
                    if key not in wg:
                        continue
                    w = np.asarray(wg[key]); t = np.asarray(h["times_ms"])[: w.size]
                ax.plot(t / 1000.0, w, color=palette[lam], linewidth=1.3,
                        label=_lam_label(lam))
            if key == "bs->rge_mean":
                ax.axhline(30.0, ls="--", color="grey", alpha=0.5, label="W$_{max}$=30")
            ax.grid(alpha=0.2)
            if xlim_s is not None:
                ax.set_xlim(0, xlim_s)
            if r == 0:
                ax.set_title(clabel, fontsize=10)
            if c == 0:
                ax.set_ylabel(f"{plabel}\nmean weight (pA)", fontsize=10)
            if r == nr - 1:
                ax.set_xlabel("time (s)")
            if r == 0 and c == nc - 1:
                ax.legend(loc="lower right", fontsize=7)
    fig.suptitle(suptitle, fontsize=12, y=1.00)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(outpath, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(f"[gallery] saved {outpath}")


def _weight_profiles(indir, anchor_speed, anchor_gain, outpath):
    """CUT->RGE, BS->RGE, BS->RGF mean-weight trajectories, 3 λ overlaid,
    for a speed anchor (top row) and an ablation anchor (bottom row)."""
    palette = {"lam1em5": "#1f77b4", "lam1em4": "#2ca02c", "lam1em3": "#d62728"}
    proj05 = [("cut->rge_mean", "CUT→RG-E"), ("bs->rge_mean", "BS→RG-E"),
              ("bs->rgf_mean", "BS→RG-F")]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), squeeze=False)
    rows = [
        ("medium walk (Ia intact)",
         lambda lam: _find(indir, f"cpg_speed_stdp_{anchor_speed}_{lam}_*.h5")),
        ("air stepping (Ia gain 0.1)",
         lambda lam: _find(indir, f"cpg_ablgrad_{anchor_gain}_{lam}_*.h5")),
    ]
    for r, (rlabel, file_fn) in enumerate(rows):
        for c, (key, plabel) in enumerate(proj05):
            ax = axes[r][c]
            for lam in LAMBDA_ORDER:
                f = file_fn(lam)
                if f is None:
                    continue
                with h5py.File(f, "r") as h:
                    wg = h["leg_L/weights"]
                    if key not in wg:
                        continue
                    w = np.asarray(wg[key]); t = np.asarray(h["times_ms"])[: w.size]
                ax.plot(t / 1000.0, w, color=palette[lam], linewidth=1.3,
                        label=_lam_label(lam))
            if key == "bs->rge_mean":
                ax.axhline(30.0, ls="--", color="grey", alpha=0.5, label="W$_{max}$=30")
            ax.grid(alpha=0.2)
            if r == 0:
                ax.set_title(plabel, fontsize=11)
            if c == 0:
                ax.set_ylabel(f"{rlabel}\nmean weight (pA)", fontsize=9)
            if r == 1:
                ax.set_xlabel("time (s)")
            if r == 0 and c == 2:
                ax.legend(loc="lower right", fontsize=8)
    fig.suptitle("STDP weight profiles across λ — descending/cutaneous projections\n"
                 "(top: medium-walk, Ia intact; bottom: air stepping, Ia gain 0.1)",
                 fontsize=12, y=1.00)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(outpath, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(f"[gallery] saved {outpath}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", type=str, default="results/2026-06-20",
                    help="Default results dir (used when --speed-dir/--ablation-dir unset).")
    ap.add_argument("--speed-dir", type=str, default=None,
                    help="Results dir for the speed figures (defaults to --indir).")
    ap.add_argument("--ablation-dir", type=str, default=None,
                    help="Results dir for the ablation figures (defaults to --indir).")
    ap.add_argument("--outdir", type=str, default="plots/paper")
    ap.add_argument("--zoom-ms", type=float, default=10000.0)
    ap.add_argument("--window", choices=["first", "last"], default="last",
                    help="Force-gallery window: 'last' (converged tail, default) "
                         "or 'first' (self-organisation transient).")
    ap.add_argument("--dark", action="store_true",
                    help="Use uniform dark navy-E / crimson-F curves (best for "
                         "cross-condition force-profile comparison).")
    ap.add_argument("--dpi", type=int, default=170,
                    help="Output DPI for the force galleries (e.g. 300 for high-res).")
    ap.add_argument("--weight-xlim-s", type=float, default=None,
                    help="If set, zoom the weight-matrix x-axis to [0, X] seconds "
                         "to show the early saturation (e.g. 20).")
    args = ap.parse_args()
    win = args.window
    win_desc = (f"first {args.zoom_ms/1000:.0f} s" if win == "first"
                else f"last {args.zoom_ms/1000:.0f} s")
    os.makedirs(args.outdir, exist_ok=True)
    speed_dir = args.speed_dir or args.indir
    abl_dir = args.ablation_dir or args.indir

    speed_colors = [plt.get_cmap("viridis")(v) for v in (0.05, 0.5, 0.9)]
    gain_colors = ["#1f3b73", "#b5651d", "#c1272d"]

    sfx = ("_first" if win == "first" else "") + ("_dark" if args.dark else "")
    speed_rows = [(tag, lbl) for tag, lbl, _per in SPEEDS]
    _force_matrix(
        speed_dir, speed_rows,
        lambda tag, lam: _find(speed_dir, f"cpg_speed_stdp_{tag}_{lam}_*.h5"),
        speed_colors,
        os.path.join(args.outdir, f"fig9_speed_lambda_gallery{sfx}.png"),
        f"Speed × λ gait gallery — force profiles ({win_desc}; μ=3.5, CV=0.30)",
        args.zoom_ms, window=win, dark=args.dark, dpi=args.dpi)

    _force_matrix(
        abl_dir, GAINS,
        lambda tag, lam: _find(abl_dir, f"cpg_ablgrad_{tag}_{lam}_*.h5"),
        gain_colors,
        os.path.join(args.outdir, f"fig10_ablation_lambda_gallery{sfx}.png"),
        f"Graded ablation × λ gait gallery — force profiles "
        f"({win_desc}; 520 ms; μ=3.5, CV=0.30)", args.zoom_ms, window=win,
        dark=args.dark, dpi=args.dpi)

    _weight_profiles(abl_dir, "13_5cms", "air",
                     os.path.join(args.outdir, "fig11_weight_profiles.png"))

    # Full weight matrices: 3 projections × 3 states, 3 λ overlaid per panel.
    xlim = args.weight_xlim_s
    wsfx = f"_first{int(xlim)}s" if xlim is not None else ""
    wdesc = f"first {xlim:.0f} s" if xlim is not None else "full 120 s"
    speed_cols = [(tag, lbl.replace("\n", " ")) for tag, lbl, _per in SPEEDS]
    _weight_matrix(
        speed_dir, speed_cols,
        lambda tag, lam: _find(speed_dir, f"cpg_speed_stdp_{tag}_{lam}_*.h5"),
        os.path.join(args.outdir, f"fig12_weight_matrix_speed{wsfx}.png"),
        "Weight-profile matrix across speed — projections (rows) × speed "
        f"(cols), 3 λ overlaid  ({wdesc}; Ia intact, μ=3.5, CV=0.30)",
        xlim_s=xlim)

    gain_cols = [(tag, lbl.replace("\n", " ")) for tag, lbl in GAINS]
    _weight_matrix(
        abl_dir, gain_cols,
        lambda tag, lam: _find(abl_dir, f"cpg_ablgrad_{tag}_{lam}_*.h5"),
        os.path.join(args.outdir, f"fig13_weight_matrix_ablation{wsfx}.png"),
        "Weight-profile matrix across ablation — projections (rows) × Ia "
        f"gain (cols), 3 λ overlaid  ({wdesc}; 520 ms, μ=3.5, CV=0.30)",
        xlim_s=xlim)


if __name__ == "__main__":
    main()
