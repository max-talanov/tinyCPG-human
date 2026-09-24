#!/usr/bin/env python3
"""
cpg_speed_figure.py
Paper Figure — Speed sweep.

Varies --step-period-ms across rat locomotor range (600–1400 ms) at the same
(mu, CV) = (3.5, 0.30) and shows the model tracks the commanded gait period.

Layout (16 × 12 in, landscape):
  Row 1 (5 panels): Force-E leg L, last 10 s zoom, one per step period.
                    Visually shows different cycle lengths.
  Row 2 (5 panels): State-space limit cycle (Force-F vs Force-E),
                    one per step period. Closed loops = stable rhythm.
  Row 3 (3 panels): (a) Measured cycle period vs commanded step_period_ms
                    (b) Force-E peak height vs step period
                    (c) Counter-phase corr(E,F) vs step period

Usage:
  python3 cpg_speed_figure.py \\
      --indir . --outdir plots/paper \\
      --out plots/paper/fig_speed.png
"""

import argparse
import glob
import os
import re
from typing import Dict, List

import h5py
import matplotlib.pyplot as plt
import numpy as np


def _find_cycle_periods(t_ms: np.ndarray, signal: np.ndarray,
                        min_peak_height: float = 5.0,
                        min_gap_ms: float = 200.0) -> np.ndarray:
    if signal.size < 5:
        return np.array([])
    dt_med = float(np.median(np.diff(t_ms))) if t_ms.size > 1 else 100.0
    min_gap_samples = max(1, int(min_gap_ms / max(1e-9, dt_med)))
    above = signal > min_peak_height
    peaks: List[int] = []
    last = -10**9
    for i in range(1, signal.size - 1):
        if above[i] and signal[i] >= signal[i - 1] and signal[i] >= signal[i + 1]:
            if i - last >= min_gap_samples:
                peaks.append(i)
                last = i
    if len(peaks) < 2:
        return np.array([])
    peak_times = t_ms[np.asarray(peaks, dtype=int)]
    return np.diff(peak_times)


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 4 or b.size < 4:
        return np.nan
    a = a - a.mean(); b = b - b.mean()
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / d) if d > 1e-12 else np.nan


def _discover_speed_files(indir: str) -> List[Dict]:
    """Find cpg_speed_period<P>ms_*.h5 files, sorted by period."""
    pattern = os.path.join(indir, "cpg_speed_period*ms_*.h5")
    files = sorted(glob.glob(pattern))
    out = []
    for f in files:
        m = re.search(r"period(\d+)ms", os.path.basename(f))
        if not m:
            continue
        out.append({"period_ms": int(m.group(1)), "path": f})
    out.sort(key=lambda d: d["period_ms"])
    return out


def _color_for_period(p_ms: int) -> str:
    # Sequential colormap: faster = blue, slower = red
    cmap = plt.get_cmap("viridis")
    # Range 600-1400 → 0-1
    val = (p_ms - 600.0) / max(1.0, 1400.0 - 600.0)
    return cmap(np.clip(val, 0.0, 1.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", type=str, default=".")
    ap.add_argument("--outdir", type=str, default="plots/paper")
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--zoom-sec", type=float, default=10.0,
                    help="Zoom window for force trace panels (seconds).")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    out_path = args.out or os.path.join(args.outdir, "fig_speed.png")

    files = _discover_speed_files(args.indir)
    if not files:
        raise SystemExit("No cpg_speed_period*ms files found.")
    print(f"[speed] found {len(files)} step-periods: "
          f"{[f['period_ms'] for f in files]} ms")

    # Pre-load + metrics
    runs: List[Dict] = []
    for f in files:
        h = h5py.File(f["path"], "r")
        t = np.asarray(h["times_ms"])
        sim_ms = float(h.attrs.get("sim_ms", 30000.0))
        fe_l = np.asarray(h["leg_L/force_e"])
        ff_l = np.asarray(h["leg_L/force_f"])
        # Metrics on last 20s
        mask = t >= max(0.0, sim_ms - 20000.0)
        t_w = t[mask]; fe_w = fe_l[mask]; ff_w = ff_l[mask]
        periods = _find_cycle_periods(t_w, fe_w, min_peak_height=5.0,
                                      min_gap_ms=max(150.0, f["period_ms"] * 0.4))
        runs.append({
            "period_ms": f["period_ms"],
            "h5": h,
            "t": t,
            "fe_l": fe_l,
            "ff_l": ff_l,
            "sim_ms": sim_ms,
            "measured_period_mean": float(np.mean(periods)) if periods.size else np.nan,
            "measured_period_std": float(np.std(periods)) if periods.size else np.nan,
            "n_cycles": int(periods.size),
            "peak_e": float(np.percentile(fe_w, 95)),
            "peak_f": float(np.percentile(ff_w, 95)),
            "corr_ef": _safe_corr(fe_w, ff_w),
            "color": _color_for_period(f["period_ms"]),
        })

    plt.rcParams.update({
        "font.size": 10, "axes.titlesize": 10, "axes.labelsize": 9,
        "legend.fontsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
    })

    n = len(runs)
    fig = plt.figure(figsize=(3.2 * n, 12))
    gs = fig.add_gridspec(3, n, height_ratios=[1.0, 1.0, 1.2],
                          hspace=0.55, wspace=0.30)

    zoom_ms = args.zoom_sec * 1000.0

    # Row 1: Force-E traces (last zoom_sec)
    for i, r in enumerate(runs):
        ax = fig.add_subplot(gs[0, i])
        z = max(0.0, r["sim_ms"] - zoom_ms)
        mask = r["t"] >= z
        ax.plot(r["t"][mask], r["fe_l"][mask], color=r["color"], linewidth=1.0,
                label=f"step={r['period_ms']}ms")
        ax.plot(r["t"][mask], r["ff_l"][mask], color=r["color"], linewidth=0.7,
                linestyle="--", alpha=0.6)
        ax.set_xlim(z, r["sim_ms"])
        ax.set_title(f"step = {r['period_ms']} ms")
        ax.grid(alpha=0.2)
        if i == 0:
            ax.set_ylabel("Force E (solid) / F (dashed)\n(a.u.)")

    # Row 2: state-space limit-cycle plots (Force-F vs Force-E).
    # Use ONLY the last 3 cycles of stable rhythm — cleaner closed loops than
    # showing the full zoom window (which would also include onset transients).
    for i, r in enumerate(runs):
        ax = fig.add_subplot(gs[1, i])
        three_cycles_ms = 3.0 * r["period_ms"]
        z = max(0.0, r["sim_ms"] - three_cycles_ms)
        mask = r["t"] >= z
        ax.plot(r["fe_l"][mask], r["ff_l"][mask], color=r["color"],
                linewidth=1.0, alpha=0.85)
        ax.set_xlabel("Force-E (a.u.)")
        if i == 0:
            ax.set_ylabel("Force-F (a.u.)")
        ax.set_title(f"limit cycle (last 3 cycles)")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=0.2)

    # Row 3: 3 quantitative panels (bottom row)
    gs_bottom = fig.add_gridspec(1, 3, left=0.07, right=0.97,
                                 bottom=0.04, top=0.32, wspace=0.32)
    ax_a = fig.add_subplot(gs_bottom[0, 0])
    ax_b = fig.add_subplot(gs_bottom[0, 1])
    ax_c = fig.add_subplot(gs_bottom[0, 2])

    cmd = np.array([r["period_ms"] for r in runs], dtype=float)
    meas = np.array([r["measured_period_mean"] for r in runs])
    meas_sd = np.array([r["measured_period_std"] for r in runs])
    peaks_e = np.array([r["peak_e"] for r in runs])
    peaks_f = np.array([r["peak_f"] for r in runs])
    corrs = np.array([r["corr_ef"] for r in runs])
    bar_colors = [r["color"] for r in runs]

    # (a) measured vs commanded period — identity line + scatter
    lo = min(cmd.min(), np.nanmin(meas)) - 50
    hi = max(cmd.max(), np.nanmax(meas)) + 50
    ax_a.plot([lo, hi], [lo, hi], linestyle="--", color="grey", alpha=0.7,
              label="identity (commanded = measured)")
    ax_a.errorbar(cmd, meas, yerr=meas_sd, fmt="o", markersize=8,
                  capsize=4, color="#1f77b4", label="data")
    ax_a.set_xlabel("commanded step period (ms)")
    ax_a.set_ylabel("measured Force-E peak-to-peak period (ms)")
    ax_a.set_title("(a) Commanded vs measured cycle period")
    ax_a.legend(loc="lower right", fontsize=8)
    ax_a.grid(alpha=0.2)

    # (b) Peak force vs step period
    ax_b.plot(cmd, peaks_e, "o-", color="#1f77b4", label="Force-E", markersize=8)
    ax_b.plot(cmd, peaks_f, "s--", color="#ff7f0e", label="Force-F", markersize=7)
    ax_b.set_xlabel("commanded step period (ms)")
    ax_b.set_ylabel("force peak (95th pct., a.u.)")
    ax_b.set_title("(b) Peak force amplitude vs speed")
    ax_b.legend(loc="best", fontsize=8)
    ax_b.grid(alpha=0.2)

    # (c) Counter-phase correlation vs step period
    ax_c.plot(cmd, corrs, "o-", color="#2ca02c", markersize=8)
    ax_c.axhline(-0.8, linestyle="--", color="grey", alpha=0.6, label="target ≤ −0.8")
    ax_c.axhline(0.0, color="black", linewidth=0.5)
    ax_c.set_xlabel("commanded step period (ms)")
    ax_c.set_ylabel("corr(Force-E, Force-F)")
    ax_c.set_title("(c) E↔F counter-phase vs speed")
    ax_c.set_ylim(-1.05, 0.4)
    ax_c.legend(loc="lower right", fontsize=8)
    ax_c.grid(alpha=0.2)

    fig.suptitle(
        "Speed sweep — gait tracks commanded step period across rat locomotor range "
        "(μ = 3.5, CV = 0.30, 30 s)",
        fontsize=12, y=0.995,
    )
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"[speed] saved {out_path}  ({3.2 * n:.1f} × 12 in)")

    # Dump metrics CSV
    csv_path = os.path.splitext(out_path)[0] + "_metrics.csv"
    with open(csv_path, "w") as fh:
        fh.write("step_period_ms,measured_period_mean,measured_period_std,n_cycles,"
                 "peak_force_e,peak_force_f,corr_ef\n")
        for r in runs:
            fh.write(f"{r['period_ms']},{r['measured_period_mean']:.2f},"
                     f"{r['measured_period_std']:.2f},{r['n_cycles']},"
                     f"{r['peak_e']:.3f},{r['peak_f']:.3f},{r['corr_ef']:.3f}\n")
    print(f"[speed] metrics CSV: {csv_path}")

    for r in runs:
        r["h5"].close()


if __name__ == "__main__":
    main()
