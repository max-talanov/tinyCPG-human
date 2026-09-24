#!/usr/bin/env python3
"""
cpg_ablation_figure.py
Paper Figure — Ablation study.

Shows necessity of each model component by comparing 5 conditions at the same
(mu, CV) = (3.5, 0.30):
  - baseline : all components ON
  - noIa     : Ia → InE/InF closed-loop removed (W_IA2IN = 0)
  - symInh   : reciprocal inhibition symmetric (W_INF2RGE = W_INE2RGF = -28)
  - noComm   : L↔R commissural inhibition removed
  - noPaced  : legacy rotating-CUT (no --paced-gait)

Layout (16 × 12 in, landscape, suitable for paper Figure 4-ish):
  Row 1 (5 panels): Force E+F leg L, last 5 s zoom, one panel per condition
  Row 2 (5 panels): same for leg R   (highlights L vs R 180° offset)
  Row 3 (3 panels): summary metrics across conditions
     (a) Mean cycle period ± std (from Force-E peaks)
     (b) Force-E peak height
     (c) Force-E ↔ Force-F counter-phase correlation

Usage:
  python3 cpg_ablation_figure.py \\
      --indir . --outdir plots/paper \\
      --out plots/paper/fig_ablation.png
"""

import argparse
import glob
import os
from typing import Dict, List, Tuple

import h5py
import matplotlib.pyplot as plt
import numpy as np


CONDITION_ORDER = ["baseline", "noIa", "symInh", "noComm", "noPaced"]
CONDITION_LABELS = {
    "baseline": "Baseline\n(all features)",
    "noIa": "No Ia loop\n(W_IA2IN = 0)",
    "symInh": "Symmetric inh.\n(InF↔E = InE↔F = -28)",
    "noComm": "No commissural\n(W_COMM = 0)",
    "noPaced": "No paced gait\n(legacy CUT rotation)",
}
CONDITION_COLOR = {
    "baseline": "#1f77b4",
    "noIa": "#d62728",
    "symInh": "#ff7f0e",
    "noComm": "#2ca02c",
    "noPaced": "#9467bd",
}


def _find_cycle_periods(t_ms: np.ndarray, signal: np.ndarray,
                        min_peak_height: float = 5.0,
                        min_gap_ms: float = 300.0) -> np.ndarray:
    """Detect peak-to-peak periods of `signal` over `t_ms` (ms).

    Pure numpy. Returns array of inter-peak intervals (ms).
    """
    if signal.size < 5:
        return np.array([])
    dt_med = float(np.median(np.diff(t_ms))) if t_ms.size > 1 else 100.0
    min_gap_samples = max(1, int(min_gap_ms / max(1e-9, dt_med)))

    above = signal > min_peak_height
    # Local maxima
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
    a = a - a.mean()
    b = b - b.mean()
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom < 1e-12:
        return np.nan
    return float(np.dot(a, b) / denom)


def _compute_metrics(h5_path: str) -> Dict:
    """Per-run summary stats used in the metrics panel."""
    with h5py.File(h5_path, "r") as h:
        t = np.asarray(h["times_ms"])
        L = h["leg_L"]
        force_e = np.asarray(L["force_e"])
        force_f = np.asarray(L["force_f"])
        # Use last 20 s (skip startup transients + STDP convergence)
        sim_ms = float(h.attrs.get("sim_ms", 30000.0))
        mask = t >= max(0.0, sim_ms - 20000.0)
        t_w = t[mask]; fe = force_e[mask]; ff = force_f[mask]
        periods = _find_cycle_periods(t_w, fe, min_peak_height=5.0, min_gap_ms=300.0)
        return dict(
            tag=str(h.attrs.get("ablation_tag", "?")),
            paced=bool(h.attrs.get("paced_gait", False)),
            cycle_mean_ms=float(np.mean(periods)) if periods.size else np.nan,
            cycle_std_ms=float(np.std(periods)) if periods.size else np.nan,
            n_cycles=int(periods.size),
            peak_force_e=float(np.percentile(fe, 95)),
            peak_force_f=float(np.percentile(ff, 95)),
            corr_ef=_safe_corr(fe, ff),
        )


def _resolve_files(indir: str) -> Dict[str, str]:
    """Map condition tag → file path. Handles either 'baseline' or
    files named *ablate_baseline*, *ablate_noPaced*, etc."""
    out: Dict[str, str] = {}
    for tag in CONDITION_ORDER:
        pat = os.path.join(indir, f"cpg_ablate_{tag}_*.h5")
        matches = sorted(glob.glob(pat))
        if matches:
            out[tag] = matches[0]
    return out


def _plot_trace_panel(ax, t_ms, force_e, force_f, sim_ms, title, color_e="#1f77b4", color_f="#ff7f0e"):
    zoom = max(0.0, sim_ms - 5000.0)
    mask = t_ms >= zoom
    ax.plot(t_ms[mask], force_e[mask], color=color_e, linewidth=1.0, label="E")
    ax.plot(t_ms[mask], force_f[mask], color=color_f, linewidth=1.0, label="F")
    ax.set_xlim(zoom, sim_ms)
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", type=str, default=".")
    ap.add_argument("--outdir", type=str, default="plots/paper")
    ap.add_argument("--out", type=str, default=None,
                    help="Output PNG path. Defaults to <outdir>/fig_ablation.png")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    out_path = args.out or os.path.join(args.outdir, "fig_ablation.png")

    files = _resolve_files(args.indir)
    missing = [c for c in CONDITION_ORDER if c not in files]
    if missing:
        print(f"[ablation] WARNING: missing conditions: {missing}")
    conds = [c for c in CONDITION_ORDER if c in files]
    if not conds:
        raise SystemExit("No ablation HDF5 files found.")

    print(f"[ablation] found {len(conds)} conditions: {conds}")

    # Pre-load all data + metrics
    data: List[Dict] = []
    metrics: List[Dict] = []
    for tag in conds:
        h = h5py.File(files[tag], "r")
        sim_ms = float(h.attrs.get("sim_ms", 30000.0))
        data.append(dict(
            tag=tag,
            h5=h,
            t=np.asarray(h["times_ms"]),
            fe_l=np.asarray(h["leg_L/force_e"]),
            ff_l=np.asarray(h["leg_L/force_f"]),
            fe_r=np.asarray(h["leg_R/force_e"]),
            ff_r=np.asarray(h["leg_R/force_f"]),
            sim_ms=sim_ms,
        ))
        m = _compute_metrics(files[tag])
        # Trust the filename-derived tag (`tag`) over the in-file ablation_tag,
        # which is "baseline" for noPaced runs (we didn't set --ablate-* there).
        m["tag"] = tag
        metrics.append(m)

    # ---- Build figure ----
    plt.rcParams.update({
        "font.size": 10, "axes.titlesize": 10, "axes.labelsize": 9,
        "legend.fontsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
    })

    n = len(conds)
    fig = plt.figure(figsize=(3.2 * n, 12))
    gs = fig.add_gridspec(3, n, height_ratios=[1.0, 1.0, 1.2],
                          hspace=0.55, wspace=0.30)

    # Row 1: Force E+F leg L per condition
    axes_l = []
    for i, d in enumerate(data):
        ax = fig.add_subplot(gs[0, i])
        title = f"{CONDITION_LABELS.get(d['tag'], d['tag'])}\nleg L"
        _plot_trace_panel(ax, d["t"], d["fe_l"], d["ff_l"], d["sim_ms"], title)
        if i == 0:
            ax.set_ylabel("force leg L (a.u.)")
            ax.legend(loc="upper right", ncol=2)
        axes_l.append(ax)

    # Row 2: Force E+F leg R per condition
    axes_r = []
    for i, d in enumerate(data):
        ax = fig.add_subplot(gs[1, i])
        _plot_trace_panel(ax, d["t"], d["fe_r"], d["ff_r"], d["sim_ms"],
                          title="leg R", color_e="#2ca02c", color_f="#d62728")
        if i == 0:
            ax.set_ylabel("force leg R (a.u.)")
            ax.legend(loc="upper right", ncol=2)
        ax.set_xlabel("time (ms)")
        axes_r.append(ax)

    # Row 3: 3 summary metric panels spanning bottom
    n_metric = 3
    metric_axes = []
    # Re-grid the bottom row into 3 equal cells
    gs_bottom = fig.add_gridspec(1, n_metric, left=0.06, right=0.98,
                                 bottom=0.04, top=0.32, wspace=0.32)
    for k in range(n_metric):
        metric_axes.append(fig.add_subplot(gs_bottom[0, k]))

    tags = [m["tag"] for m in metrics]
    colors = [CONDITION_COLOR.get(t, "grey") for t in tags]
    x = np.arange(len(tags))

    # (a) cycle period (mean ± std)
    means = np.array([m["cycle_mean_ms"] for m in metrics])
    stds = np.array([m["cycle_std_ms"] for m in metrics])
    metric_axes[0].bar(x, means, yerr=stds, color=colors, capsize=4, alpha=0.85)
    metric_axes[0].axhline(1000.0, linestyle="--", color="grey", alpha=0.6, label="paced target (1 s)")
    metric_axes[0].set_xticks(x); metric_axes[0].set_xticklabels(tags, rotation=20)
    metric_axes[0].set_ylabel("Force-E peak-to-peak period (ms)")
    metric_axes[0].set_title("(a) Cycle period (mean ± std, last 20 s)")
    metric_axes[0].legend(loc="upper right", fontsize=8)
    metric_axes[0].grid(alpha=0.2, axis="y")

    # (b) peak Force-E (95th pct)
    peaks_e = np.array([m["peak_force_e"] for m in metrics])
    peaks_f = np.array([m["peak_force_f"] for m in metrics])
    w = 0.36
    metric_axes[1].bar(x - w / 2, peaks_e, width=w, color="#1f77b4", alpha=0.85, label="Force-E")
    metric_axes[1].bar(x + w / 2, peaks_f, width=w, color="#ff7f0e", alpha=0.85, label="Force-F")
    metric_axes[1].set_xticks(x); metric_axes[1].set_xticklabels(tags, rotation=20)
    metric_axes[1].set_ylabel("force peak (95th pct., a.u.)")
    metric_axes[1].set_title("(b) Peak force amplitude")
    metric_axes[1].legend(loc="upper right", fontsize=8)
    metric_axes[1].grid(alpha=0.2, axis="y")

    # (c) corr(Force-E, Force-F) — counter-phase strength
    corrs = np.array([m["corr_ef"] for m in metrics])
    metric_axes[2].bar(x, corrs, color=colors, alpha=0.85)
    metric_axes[2].axhline(-0.8, linestyle="--", color="grey", alpha=0.6,
                            label="target (corr ≤ −0.8)")
    metric_axes[2].axhline(0.0, color="black", linewidth=0.5)
    metric_axes[2].set_xticks(x); metric_axes[2].set_xticklabels(tags, rotation=20)
    metric_axes[2].set_ylabel("corr(Force-E, Force-F)")
    metric_axes[2].set_title("(c) E↔F counter-phase strength")
    metric_axes[2].set_ylim(-1.05, 0.4)
    metric_axes[2].legend(loc="lower right", fontsize=8)
    metric_axes[2].grid(alpha=0.2, axis="y")

    # Make top half a bit narrower so bottom 3 panels fit
    fig.suptitle(
        "Ablation study — necessity of each component (μ = 3.5, CV = 0.30, 30 s)",
        fontsize=12, y=0.995,
    )
    # Use bbox_inches="tight" since we manually positioned bottom row
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"[ablation] saved {out_path}  ({3.2 * n:.1f} × 12 in)")

    # Also dump metrics as CSV for paper text
    csv_path = os.path.splitext(out_path)[0] + "_metrics.csv"
    with open(csv_path, "w") as f:
        f.write("condition,cycle_mean_ms,cycle_std_ms,n_cycles,peak_force_e,peak_force_f,corr_ef\n")
        for m in metrics:
            f.write(f"{m['tag']},{m['cycle_mean_ms']:.2f},{m['cycle_std_ms']:.2f},"
                    f"{m['n_cycles']},{m['peak_force_e']:.3f},{m['peak_force_f']:.3f},"
                    f"{m['corr_ef']:.3f}\n")
    print(f"[ablation] metrics CSV: {csv_path}")

    for d in data:
        d["h5"].close()


if __name__ == "__main__":
    main()
