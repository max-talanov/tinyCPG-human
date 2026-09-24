#!/usr/bin/env python3
"""
cpg_speed_stdp_figure.py
Paper Figure — Phase A: speed × STDP learning-rate matrix.

3 walking speeds (Courtine/Lavrov range):
    6 cm/s   = 1200 ms cycle (slow walk)
    13.5 cm/s = 520 ms cycle  (medium walk)
    21 cm/s   = 350 ms cycle  (fast walk)

× 3 STDP learning rates (bio-plausible cortical range):
    λ = 5e-4 (slow)
    λ = 1e-3 (baseline, Morrison 2007)
    λ = 2e-3 (fast)

Layout (12 × 14 in, portrait — paper figure):
  Rows 1-3:  Force E+F leg L, last 5 s zoom, 3 rows × 3 cols
              Rows = speed (slow / medium / fast)
              Cols = λ      (slow / baseline / fast)
  Row 4:     Three quantitative summary panels across the 3×3 matrix:
              (a) measured cycle period (ms) heat-tile
              (b) Force-E peak amplitude (a.u.) heat-tile
              (c) E↔F counter-phase Pearson r heat-tile

Usage:
  python3 cpg_speed_stdp_figure.py \\
      --indir results/2026-06-16 --outdir plots/paper \\
      --out plots/paper/fig5_speed_stdp.png
"""

import argparse
import glob
import os
import re
from typing import Dict, List, Tuple

import h5py
import matplotlib.pyplot as plt
import numpy as np


SPEED_ORDER = ["06cms", "13_5cms", "21cms"]
SPEED_LABEL = {
    "06cms":   "slow walk\n≈6 cm/s  (1200 ms)",
    "13_5cms": "medium walk\n≈13.5 cm/s  (520 ms)",
    "21cms":   "fast walk\n≈21 cm/s  (350 ms)",
}
SPEED_PERIOD_MS = {"06cms": 1200, "13_5cms": 520, "21cms": 350}

# Lambda tags are auto-discovered from filenames (see _resolve_files). The
# helpers below convert a tag such as "lam1em4" → value 1e-4 and a display
# label, so the figure adapts to whatever λ set was actually run.
_SUPERSCRIPT = {"-": "⁻", "0": "⁰", "1": "¹", "2": "²", "3": "³",
                "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"}


def _lambda_tag_to_value(tag: str) -> float:
    """'lam1em4' → 1e-4 ;  'lam5em4' → 5e-4 ;  'lam2em3' → 2e-3."""
    m = re.match(r"lam(\d+)em(\d+)", tag)
    if not m:
        return float("nan")
    return float(m.group(1)) * (10.0 ** (-int(m.group(2))))


def _lambda_label(tag: str, role: str = "") -> str:
    """Render 'lam1em4' → 'λ = 1·10⁻⁴\\n(role)'."""
    m = re.match(r"lam(\d+)em(\d+)", tag)
    if not m:
        return tag
    mant, exp = m.group(1), m.group(2)
    sup = "".join(_SUPERSCRIPT.get(ch, ch) for ch in f"-{exp}")
    base = f"λ = {mant}·10{sup}"
    return f"{base}\n({role})" if role else base


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
    return np.diff(t_ms[np.asarray(peaks, dtype=int)])


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 4 or b.size < 4:
        return np.nan
    a = a - a.mean(); b = b - b.mean()
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / d) if d > 1e-12 else np.nan


def _spectral_concentration(t_ms: np.ndarray, signal: np.ndarray,
                            period_ms: float, band_frac: float = 0.15) -> float:
    """Fraction of total PSD power concentrated within ±band_frac around the
    fundamental cycle frequency f0 = 1000/period_ms.

    Higher = sharper rhythm peak = cleaner pacing. Less saturated than
    period s.d. (which is ≈0 for paced gait), so detects subtle STDP
    differences invisible in time-domain metrics.
    """
    if signal.size < 16 or period_ms <= 0:
        return np.nan
    # Mean-detrend, regular-grid resample assumed (already at chunk rate).
    x = signal - signal.mean()
    if t_ms.size > 1:
        dt_s = float(np.median(np.diff(t_ms))) / 1000.0
    else:
        dt_s = 0.1
    if dt_s <= 0:
        return np.nan
    n = x.size
    freqs = np.fft.rfftfreq(n, d=dt_s)         # Hz
    psd = np.abs(np.fft.rfft(x)) ** 2
    total = float(psd.sum())
    if total <= 0:
        return np.nan
    f0 = 1000.0 / period_ms                    # fundamental Hz
    lo, hi = f0 * (1.0 - band_frac), f0 * (1.0 + band_frac)
    band_mask = (freqs >= lo) & (freqs <= hi)
    return float(psd[band_mask].sum() / total)


def _resolve_files(indir: str, prefix: str = "cpg_speed_stdp"):
    """Discover (speed_tag, lambda_tag) → path, plus the ordered λ tag list.

    The λ tags are read from the filenames and sorted ascending by value, so
    the figure adapts to whatever λ set was actually run (3, 4, 5, ... values).
    Returns (files_dict, lambda_order_list).
    """
    files = sorted(glob.glob(os.path.join(indir, f"{prefix}_*.h5")))
    out: Dict[Tuple[str, str], str] = {}
    # Match any of the known speed tags (06cms, 13_5cms, 21cms) explicitly.
    # Using "[^_]+" fails for "13_5cms" because of the underscore inside.
    speed_re = "|".join(re.escape(s) for s in SPEED_ORDER)
    rgx = re.compile(rf"{re.escape(prefix)}_({speed_re})_(lam\d+em\d+)_")
    lam_tags = set()
    for f in files:
        m = rgx.search(os.path.basename(f))
        if m:
            out[(m.group(1), m.group(2))] = f
            lam_tags.add(m.group(2))
    lam_order = sorted(lam_tags, key=_lambda_tag_to_value)
    return out, lam_order


def _load(path: str) -> Dict:
    h = h5py.File(path, "r")
    t = np.asarray(h["times_ms"])
    sim_ms = float(h.attrs.get("sim_ms", 30000.0))
    period_ms = float(h.attrs.get("step_period_ms", 1000.0))
    fe = np.asarray(h["leg_L/force_e"])
    ff = np.asarray(h["leg_L/force_f"])
    # Metrics on last 20 s
    mask = t >= max(0.0, sim_ms - 20000.0)
    fe_w = fe[mask]; ff_w = ff[mask]; t_w = t[mask]
    periods = _find_cycle_periods(t_w, fe_w, min_peak_height=5.0,
                                  min_gap_ms=max(150.0, period_ms * 0.4))
    spec_conc = _spectral_concentration(t_w, fe_w, period_ms, band_frac=0.10)
    # Weight trajectories — dense (per-chunk) means
    weights = {}
    try:
        wg = h["leg_L/weights"]
        for key in ("cut->rge_mean", "bs->rge_mean", "bs->rgf_mean"):
            if key in wg:
                weights[key] = np.asarray(wg[key])
    except Exception:
        pass
    return {
        "h5": h, "t": t, "fe": fe, "ff": ff, "sim_ms": sim_ms,
        "period_ms": period_ms,
        "stdp_lambda": float(h.attrs.get("stdp_lambda", 1e-3)),
        "weights": weights,
        "measured_period_mean": float(np.mean(periods)) if periods.size else np.nan,
        "measured_period_std":  float(np.std(periods))  if periods.size else np.nan,
        "peak_e":  float(np.percentile(fe_w, 95)),
        "peak_f":  float(np.percentile(ff_w, 95)),
        "corr_ef": _safe_corr(fe_w, ff_w),
        "spec_conc": spec_conc,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", type=str, default="results/2026-06-16")
    ap.add_argument("--prefix", type=str, default="cpg_speed_stdp",
                    help="Filename prefix / arm, e.g. cpg_sensory_stdp for the canonical sensory arm.")
    ap.add_argument("--outdir", type=str, default="plots/paper")
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--trace-window", choices=["first", "last"], default="first",
                    help="Show the force traces from the FIRST window (default; "
                         "reveals the STDP-rate-dependent self-organisation of the "
                         "gait) or the LAST window (converged steady state).")
    ap.add_argument("--trace-window-ms", type=float, default=20000.0,
                    help="Width of the force-trace window in ms (default 20000 = "
                         "20 s, matching the STDP convergence transient).")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    out_path = args.out or os.path.join(args.outdir, "fig5_speed_stdp.png")

    files, LAMBDA_ORDER = _resolve_files(args.indir, args.prefix)
    if not LAMBDA_ORDER:
        raise SystemExit(f"No {args.prefix}_*.h5 files found in {args.indir}")

    # Build display label dict; assign roles by position (slowest=slow STDP,
    # fastest=fast STDP, the rest baseline/intermediate).
    LAMBDA_LABEL: Dict[str, str] = {}
    for i, l in enumerate(LAMBDA_ORDER):
        if len(LAMBDA_ORDER) == 1:
            role = ""
        elif _lambda_tag_to_value(l) == 1e-3:
            role = "baseline"            # literature reference, any position
        elif i == 0:
            role = "slow STDP"
        elif i == len(LAMBDA_ORDER) - 1:
            role = "fast STDP"
        else:
            role = "intermediate"
        LAMBDA_LABEL[l] = _lambda_label(l, role)
    LAMBDA_VAL = {l: _lambda_tag_to_value(l) for l in LAMBDA_ORDER}

    missing = [(s, l) for s in SPEED_ORDER for l in LAMBDA_ORDER if (s, l) not in files]
    if missing:
        print(f"[speed_stdp] WARNING: missing cells: {missing}")
    print(f"[speed_stdp] resolved {len(files)} files; λ tags = {LAMBDA_ORDER}")

    # Pre-load matrix
    data: Dict[Tuple[str, str], Dict] = {}
    for s in SPEED_ORDER:
        for l in LAMBDA_ORDER:
            if (s, l) in files:
                data[(s, l)] = _load(files[(s, l)])

    plt.rcParams.update({
        "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
        "legend.fontsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
    })

    n_rows, n_cols = len(SPEED_ORDER), len(LAMBDA_ORDER)
    fig = plt.figure(figsize=(4.3 * n_cols, 18))
    # 5 rows: 3 for traces, 1 for time-domain metric heat-tiles, 1 for STDP
    # convergence trajectories + spectral-concentration heat-tile (addresses
    # Q1: STDP-rate effect is in the *transient*, not the asymptote).
    gs = fig.add_gridspec(5, n_cols, height_ratios=[1.0, 1.0, 1.0, 1.25, 1.20],
                          hspace=0.55, wspace=0.28)

    # Rows 1-3: Force traces, rows = speed, cols = lambda.
    # Default window = FIRST 20 s, which is where the STDP-rate-dependent
    # self-organisation of the gait is visible (weights saturate by ~20 s,
    # so the converged last-5 s window shows no λ effect).
    win_ms = float(args.trace_window_ms)

    def _panel_tag(r, c):
        return f"A{r * n_cols + c + 1}"
    for r, s in enumerate(SPEED_ORDER):
        for c, l in enumerate(LAMBDA_ORDER):
            ax = fig.add_subplot(gs[r, c])
            if (s, l) not in data:
                ax.set_facecolor("#f5f5f5")
                ax.text(0.5, 0.5, "missing", ha="center", va="center",
                        transform=ax.transAxes, color="grey", fontsize=10)
                ax.set_xticks([]); ax.set_yticks([])
                continue
            d = data[(s, l)]
            if args.trace_window == "first":
                z0, z1 = 0.0, min(win_ms, d["sim_ms"])
            else:
                z0, z1 = max(0.0, d["sim_ms"] - win_ms), d["sim_ms"]
            mask = (d["t"] >= z0) & (d["t"] <= z1)
            ax.plot(d["t"][mask], d["fe"][mask], color="#1f77b4", linewidth=0.9, label="E")
            ax.plot(d["t"][mask], d["ff"][mask], color="#ff7f0e", linewidth=0.9, label="F")
            ax.set_xlim(z0, z1)
            ax.grid(alpha=0.2)
            # Panel index tag, top-left corner inside the axes
            ax.text(0.015, 0.97, _panel_tag(r, c), transform=ax.transAxes,
                    fontsize=10, fontweight="bold", va="top", ha="left",
                    bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="grey",
                              alpha=0.85, lw=0.6))
            # Column headers on row 0
            if r == 0:
                ax.set_title(LAMBDA_LABEL[l], fontsize=9)
            # Row labels on col 0
            if c == 0:
                ax.set_ylabel(f"{SPEED_LABEL[s]}\nforce (a.u.)", fontsize=9)
                ax.legend(loc="upper right", fontsize=7, ncol=2)
            if r == n_rows - 1:
                ax.set_xlabel("time (ms)")

    # Row 4: three summary heat-tiles across the 3×3 matrix
    metric_keys = ["measured_period_mean", "peak_e", "corr_ef"]
    metric_titles = [
        "(a) Measured cycle period (ms)\nvs. commanded",
        "(b) Peak Force-E (95th pct., a.u.)",
        "(c) E↔F counter-phase r",
    ]
    metric_cmaps = ["viridis", "plasma", "RdBu"]
    metric_vlim = [None, None, (-1.0, 0.4)]

    for m_idx, (mk, mtitle, cmap_name, vlim) in enumerate(
            zip(metric_keys, metric_titles, metric_cmaps, metric_vlim)):
        ax = fig.add_subplot(gs[3, m_idx])
        M = np.full((n_rows, n_cols), np.nan)
        for r, s in enumerate(SPEED_ORDER):
            for c, l in enumerate(LAMBDA_ORDER):
                if (s, l) in data:
                    M[r, c] = data[(s, l)][mk]
        if vlim is not None:
            im = ax.imshow(M, aspect="auto", cmap=cmap_name, vmin=vlim[0], vmax=vlim[1])
        else:
            im = ax.imshow(M, aspect="auto", cmap=cmap_name)
        ax.set_xticks(range(n_cols))
        ax.set_xticklabels([LAMBDA_LABEL[l].split("\n")[0] for l in LAMBDA_ORDER],
                           rotation=0, fontsize=8)
        ax.set_yticks(range(n_rows))
        ax.set_yticklabels([SPEED_LABEL[s].split("\n")[0] for s in SPEED_ORDER], fontsize=8)
        ax.set_title(mtitle, fontsize=10)
        # Cell-value annotations
        for r in range(n_rows):
            for c in range(n_cols):
                if np.isfinite(M[r, c]):
                    val_str = f"{M[r, c]:.2f}" if mk == "corr_ef" else f"{M[r, c]:.1f}"
                    ax.text(c, r, val_str, ha="center", va="center",
                            color="white" if (cmap_name in ("viridis", "plasma") and r >= 1) else "black",
                            fontsize=9)
        # For cycle period (a) draw commanded value as a small marker on diagonal labels
        if mk == "measured_period_mean":
            # Annotate commanded period in row labels
            ax.set_yticklabels(
                [f"{SPEED_LABEL[s].split(chr(10))[0]}\n(cmd={SPEED_PERIOD_MS[s]} ms)"
                 for s in SPEED_ORDER],
                fontsize=7,
            )
        plt.colorbar(im, ax=ax, fraction=0.05, pad=0.04)

    # ----- Row 5: STDP convergence trajectories + spectral concentration -----
    # Panel (d): CUT->RG-E mean weight vs time for medium-walk speed,
    #            3 λ overlaid. Shows the learning transient that the
    #            steady-state force trace hides.
    # Panel (e): BS->RG-E mean weight vs time (saturating projection).
    # Panel (f): Spectral concentration heat-tile across the 3×3 matrix
    #            (alternative irregularity metric; not saturated by paced clock).
    # Colour each λ by position: slowest = blue, middle = green, fastest = red.
    _traj_palette = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#ff7f0e"]
    lam_color = {l: _traj_palette[i % len(_traj_palette)]
                 for i, l in enumerate(LAMBDA_ORDER)}
    anchor_speed = "13_5cms"   # medium walk — show transient clearly

    ax_d = fig.add_subplot(gs[4, 0])
    for l in LAMBDA_ORDER:
        d = data.get((anchor_speed, l))
        if d is None or "cut->rge_mean" not in d["weights"]:
            continue
        w = d["weights"]["cut->rge_mean"]
        tt = d["t"][: w.size]
        ax_d.plot(tt / 1000.0, w, color=lam_color[l], linewidth=1.2,
                  label=LAMBDA_LABEL[l].split("\n")[0])
    ax_d.set_xlabel("time (s)"); ax_d.set_ylabel("mean weight (pA)")
    ax_d.set_title("(d) CUT→RG-E weight trajectory\n(medium walk; λ-dependent transient)")
    ax_d.legend(loc="lower right", fontsize=7)
    ax_d.grid(alpha=0.2)

    # (BS->RG-E panel removed: BS is frozen in the canonical sensory model, and the
    #  full weight trajectories are shown per projection in the STDP weight-matrix figure.)

    ax_f = fig.add_subplot(gs[4, 1:])
    M = np.full((n_rows, n_cols), np.nan)
    for r, s in enumerate(SPEED_ORDER):
        for c, l in enumerate(LAMBDA_ORDER):
            if (s, l) in data:
                M[r, c] = data[(s, l)]["spec_conc"]
    im = ax_f.imshow(M, aspect="auto", cmap="cividis", vmin=0.0, vmax=1.0)
    ax_f.set_xticks(range(n_cols))
    ax_f.set_xticklabels([LAMBDA_LABEL[l].split("\n")[0] for l in LAMBDA_ORDER],
                         fontsize=8)
    ax_f.set_yticks(range(n_rows))
    ax_f.set_yticklabels([SPEED_LABEL[s].split("\n")[0] for s in SPEED_ORDER],
                         fontsize=8)
    ax_f.set_title("(e) Spectral concentration in ±10% band around f₀ (higher = sharper)")
    for r in range(n_rows):
        for c in range(n_cols):
            if np.isfinite(M[r, c]):
                ax_f.text(c, r, f"{M[r, c]:.2f}", ha="center", va="center",
                          color="white" if M[r, c] < 0.6 else "black",
                          fontsize=9)
    plt.colorbar(im, ax=ax_f, fraction=0.05, pad=0.04)

    win_desc = (f"first {win_ms/1000:.0f} s" if args.trace_window == "first"
                else f"last {win_ms/1000:.0f} s")
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"[speed_stdp] saved {out_path}")

    # Metrics CSV
    csv_path = os.path.splitext(out_path)[0] + "_metrics.csv"
    with open(csv_path, "w") as fh:
        fh.write("speed,lambda,commanded_period_ms,measured_period_ms,period_std_ms,"
                 "peak_force_e,peak_force_f,corr_ef,spec_conc\n")
        for s in SPEED_ORDER:
            for l in LAMBDA_ORDER:
                if (s, l) not in data:
                    continue
                d = data[(s, l)]
                fh.write(f"{s},{l},{SPEED_PERIOD_MS[s]},"
                         f"{d['measured_period_mean']:.2f},{d['measured_period_std']:.2f},"
                         f"{d['peak_e']:.3f},{d['peak_f']:.3f},"
                         f"{d['corr_ef']:.3f},{d['spec_conc']:.4f}\n")
    print(f"[speed_stdp] metrics CSV: {csv_path}")

    for d in data.values():
        d["h5"].close()


if __name__ == "__main__":
    main()
