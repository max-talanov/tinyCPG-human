#!/usr/bin/env python3
"""
cpg_frozen_figure.py
Paper Figure — frozen-weight control: does the descending-weight
distribution (mean + spread), held fixed with plasticity OFF, reproduce
the two-regime counter-phase result of Phase B?

Reads cpg_frozen_m<MEAN>_cv<CV3>_baseline_*.h5 files (STDP frozen, baseline
loading, 520 ms paced) and dissects the two hypothesised mechanisms:

  MEAN sweep (weakness; CV fixed 0.02):  corr & period-jitter vs mean
  CV   sweep (heterogeneity; mean = 63): corr & period-jitter vs CV

Layout (14 × 9 in):
  Row 1: (a) corr(F_E,F_F) vs CUT->RGE mean   [weakness mechanism]
         (b) corr(F_E,F_F) vs CUT->RGE CV     [heterogeneity mechanism]
  Row 2: (c, d) cycle-period s.d. for the same two sweeps
  Row 3: representative force traces (weak / tight / broad), last 8 s

Usage:
  python3 cpg_frozen_figure.py \\
      --indir results/<date> --outdir plots/paper \\
      --out plots/paper/fig8_frozen_control.png
"""

import argparse
import glob
import os
import re
from typing import Dict, List, Optional

import h5py
import matplotlib.pyplot as plt
import numpy as np


def _find_cycle_periods(t_ms, signal, min_peak_height=3.0, min_gap_ms=200.0):
    if signal.size < 5:
        return np.array([])
    dt_med = float(np.median(np.diff(t_ms))) if t_ms.size > 1 else 100.0
    gap = max(1, int(min_gap_ms / max(1e-9, dt_med)))
    above = signal > min_peak_height
    peaks: List[int] = []
    last = -10**9
    for i in range(1, signal.size - 1):
        if above[i] and signal[i] >= signal[i - 1] and signal[i] >= signal[i + 1]:
            if i - last >= gap:
                peaks.append(i); last = i
    if len(peaks) < 2:
        return np.array([])
    return np.diff(t_ms[np.asarray(peaks, dtype=int)])


def _safe_corr(a, b):
    if a.size < 4 or b.size < 4:
        return np.nan
    a = a - a.mean(); b = b - b.mean()
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / d) if d > 1e-12 else np.nan


def _load(path: str) -> Dict:
    m = re.search(r"cpg_frozen_m(\d+)_cv(\d+)_baseline", os.path.basename(path))
    mean = float(m.group(1)) if m else np.nan
    cv = float(m.group(2)) / 1000.0 if m else np.nan
    with h5py.File(path, "r") as h:
        t = np.asarray(h["times_ms"])
        sim_ms = float(h.attrs.get("sim_ms", 30000.0))
        period_ms = float(h.attrs.get("step_period_ms", 520.0))
        fe = np.asarray(h["leg_L/force_e"]); ff = np.asarray(h["leg_L/force_f"])
        wg = h["leg_L/weights"]
        cut_mean = float(np.asarray(wg["cut->rge_mean"])[-30:].mean()) if "cut->rge_mean" in wg else np.nan
        cut_std = float(np.asarray(wg["cut->rge_std"])[-30:].mean()) if "cut->rge_std" in wg else np.nan
    mask = t >= max(0.0, sim_ms - 20000.0)
    fe_w, ff_w, t_w = fe[mask], ff[mask], t[mask]
    per = _find_cycle_periods(t_w, fe_w, 3.0, max(120.0, period_ms * 0.4))
    return dict(path=path, mean=mean, cv=cv, t=t, fe=fe, ff=ff, sim_ms=sim_ms,
                cut_mean=cut_mean, cut_std=cut_std,
                corr=_safe_corr(fe_w, ff_w),
                per_sd=float(np.std(per)) if per.size else np.nan,
                peak_e=float(np.percentile(fe_w, 95)))


def _trace(ax, d, color, title, zoom_ms=8000.0):
    z = max(0.0, d["sim_ms"] - zoom_ms)
    mask = d["t"] >= z
    ax.plot(d["t"][mask], d["fe"][mask], color=color, linewidth=1.1, label="E")
    ax.plot(d["t"][mask], d["ff"][mask], color=color, linewidth=0.9,
            linestyle="--", alpha=0.7, label="F")
    ax.set_xlim(z, d["sim_ms"]); ax.set_title(title, fontsize=9); ax.grid(alpha=0.2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", type=str, required=True)
    ap.add_argument("--outdir", type=str, default="plots/paper")
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    out_path = args.out or os.path.join(args.outdir, "fig8_frozen_control.png")

    files = sorted(glob.glob(os.path.join(args.indir, "cpg_frozen_m*_cv*_baseline_*.h5")))
    if not files:
        raise SystemExit(f"No cpg_frozen_*.h5 files in {args.indir}")
    runs = [_load(f) for f in files]
    print(f"[frozen] loaded {len(runs)} runs")

    # Split into the two controlled sweeps
    mean_sweep = sorted([r for r in runs if abs(r["cv"] - 0.02) < 1e-9], key=lambda r: r["mean"])
    cv_sweep = sorted([r for r in runs if abs(r["mean"] - 63) < 1e-9], key=lambda r: r["cv"])

    plt.rcParams.update({"font.size": 10, "axes.titlesize": 11,
                         "axes.labelsize": 10, "legend.fontsize": 8})
    fig = plt.figure(figsize=(14, 9))
    gs = fig.add_gridspec(3, 3, height_ratios=[1.1, 1.1, 1.0], hspace=0.5, wspace=0.3)

    # (a) corr vs mean (weakness)
    ax_a = fig.add_subplot(gs[0, :2])
    if mean_sweep:
        x = [r["mean"] for r in mean_sweep]; y = [r["corr"] for r in mean_sweep]
        ax_a.plot(x, y, "o-", color="#1f77b4", markersize=8)
    ax_a.axhline(-0.8, ls="--", color="grey", alpha=0.6, label="strong (−0.8)")
    ax_a.set_xlabel("frozen CUT→RG-E mean weight (pA)")
    ax_a.set_ylabel("corr$(F_E, F_F)$")
    ax_a.set_title("(a) Weakness mechanism: corr vs mean weight (CV=0.02 fixed)")
    ax_a.set_ylim(-1.05, 0.1); ax_a.legend(loc="lower left"); ax_a.grid(alpha=0.2)

    # (b) corr vs CV (heterogeneity)
    ax_b = fig.add_subplot(gs[1, :2])
    if cv_sweep:
        x = [r["cv"] for r in cv_sweep]; y = [r["corr"] for r in cv_sweep]
        ax_b.plot(x, y, "s-", color="#d62728", markersize=8)
    ax_b.axhline(-0.8, ls="--", color="grey", alpha=0.6, label="strong (−0.8)")
    ax_b.set_xlabel("frozen CUT→RG-E coefficient of variation (CV)")
    ax_b.set_ylabel("corr$(F_E, F_F)$")
    ax_b.set_title("(b) Heterogeneity mechanism: corr vs weight spread (mean=63 pA fixed)")
    ax_b.set_ylim(-1.05, 0.1); ax_b.legend(loc="lower left"); ax_b.grid(alpha=0.2)

    # (c) period s.d. vs mean ; (d) period s.d. vs CV
    ax_c = fig.add_subplot(gs[0, 2])
    if mean_sweep:
        ax_c.plot([r["mean"] for r in mean_sweep], [r["per_sd"] for r in mean_sweep],
                  "o-", color="#1f77b4", markersize=6)
    ax_c.set_xlabel("mean weight (pA)"); ax_c.set_ylabel("period s.d. (ms)")
    ax_c.set_title("(c) jitter vs mean"); ax_c.grid(alpha=0.2)

    ax_d = fig.add_subplot(gs[1, 2])
    if cv_sweep:
        ax_d.plot([r["cv"] for r in cv_sweep], [r["per_sd"] for r in cv_sweep],
                  "s-", color="#d62728", markersize=6)
    ax_d.set_xlabel("CV"); ax_d.set_ylabel("period s.d. (ms)")
    ax_d.set_title("(d) jitter vs CV"); ax_d.grid(alpha=0.2)

    # Row 3: representative force traces — weak / tight / broad
    def _pick(pred):
        cand = [r for r in runs if pred(r)]
        return cand[0] if cand else None
    reps = [
        (_pick(lambda r: abs(r["mean"] - 15) < 1e-9), "#2ca02c",
         "weak (mean=15, CV=0.02)"),
        (_pick(lambda r: abs(r["mean"] - 63) < 1e-9 and abs(r["cv"] - 0.02) < 1e-9), "#ff7f0e",
         "full + tight (mean=63, CV=0.02)"),
        (_pick(lambda r: abs(r["mean"] - 63) < 1e-9 and abs(r["cv"] - 0.10) < 1e-9), "#1f77b4",
         "full + broad (mean=63, CV=0.10)"),
    ]
    for c, (d, col, title) in enumerate(reps):
        ax = fig.add_subplot(gs[2, c])
        if d is None:
            ax.set_facecolor("#f5f5f5")
            ax.text(0.5, 0.5, "missing", ha="center", va="center", transform=ax.transAxes,
                    color="grey")
            ax.set_xticks([]); ax.set_yticks([]); continue
        _trace(ax, d, col, title + f"\ncorr={d['corr']:.2f}")
        ax.set_xlabel("time (ms)")
        if c == 0:
            ax.set_ylabel("Force E (solid) / F (dashed)")
            ax.legend(loc="upper right", ncol=2, fontsize=7)

    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"[frozen] saved {out_path}")

    # CSV
    csv = os.path.splitext(out_path)[0] + "_metrics.csv"
    with open(csv, "w") as fh:
        fh.write("sweep,mean_pA,CV,cut_mean_pA,cut_std_pA,corr_ef,period_sd_ms,peak_force_e\n")
        for r in runs:
            sweep = "mean" if abs(r["cv"] - 0.02) < 1e-9 else "cv"
            fh.write(f"{sweep},{r['mean']:.0f},{r['cv']:.3f},{r['cut_mean']:.2f},"
                     f"{r['cut_std']:.2f},{r['corr']:.3f},{r['per_sd']:.2f},{r['peak_e']:.3f}\n")
    print(f"[frozen] metrics CSV: {csv}")


if __name__ == "__main__":
    main()
