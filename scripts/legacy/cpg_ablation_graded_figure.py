#!/usr/bin/env python3
"""
cpg_ablation_graded_figure.py
Paper Figure — Phase B: graded sensory ablation × STDP learning-rate matrix
(Courtine/Lavrov SCI rehabilitation paradigm).

3 Ia feedback gains:
    1.0  = baseline (full weight-bearing, intact afferent)
    0.5  = toe stepping (partial weight-bearing; Edgerton 2008; Cha 2007)
    0.1  = air stepping (limb unloaded, ≈deafferented; Lavrov 2008;
                         Hägglund 2013)

× 3 STDP learning rates:
    λ = 5e-4 (slow)
    λ = 1e-3 (baseline)
    λ = 2e-3 (fast)

Layout (13 × 14 in, portrait):
  Rows 1-3:  Force E+F leg L, last 5 s zoom, rows = Ia gain, cols = λ
  Row 4:     Three quantitative summary heat-tiles across the 3×3 matrix:
              (a) cycle period (ms)
              (b) Peak Force-E amplitude
              (c) E↔F counter-phase Pearson r

Usage:
  python3 cpg_ablation_graded_figure.py \\
      --indir results/2026-06-16 --outdir plots/paper \\
      --out plots/paper/fig6_ablation_graded.png
"""

import argparse
import glob
import os
import re
from typing import Dict, List, Tuple

import h5py
import matplotlib.pyplot as plt
import numpy as np


GAIN_ORDER = ["baseline", "toe", "air"]
GAIN_LABEL = {
    "baseline": "baseline\nIa gain 1.0\n(intact, weight-bearing)",
    "toe":      "toe stepping\nIa gain 0.5\n(partial weight)",
    "air":      "air stepping\nIa gain 0.1\n(unloaded ≈deaff.)",
}
GAIN_VAL = {"baseline": 1.0, "toe": 0.5, "air": 0.1}

# Lambda tags are auto-discovered from filenames (see _resolve_files) so the
# figure adapts to whatever λ set was actually run.
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
                        min_peak_height: float = 3.0,
                        min_gap_ms: float = 150.0) -> np.ndarray:
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


def _resolve_files(indir: str):
    """Discover (gain_tag, lambda_tag) → path, plus ordered λ tag list.
    Files are named: cpg_ablgrad_<gain>_<lambda>_idx00_*.h5
    Returns (files_dict, lambda_order_list) with λ sorted ascending by value.
    """
    files = sorted(glob.glob(os.path.join(indir, "cpg_ablgrad_*.h5")))
    out: Dict[Tuple[str, str], str] = {}
    rgx = re.compile(r"cpg_ablgrad_(baseline|toe|air)_(lam\d+em\d+)_")
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
    period_ms = float(h.attrs.get("step_period_ms", 520.0))
    fe = np.asarray(h["leg_L/force_e"])
    ff = np.asarray(h["leg_L/force_f"])
    mask = t >= max(0.0, sim_ms - 20000.0)
    fe_w = fe[mask]; ff_w = ff[mask]; t_w = t[mask]
    periods = _find_cycle_periods(t_w, fe_w, min_peak_height=3.0,
                                  min_gap_ms=max(120.0, period_ms * 0.4))
    # STDP weight trajectories (dense per-chunk mean & std)
    weights = {}
    try:
        wg = h["leg_L/weights"]
        for key in ("cut->rge_mean", "cut->rge_std",
                    "bs->rge_mean", "bs->rge_std", "bs->rgf_mean"):
            if key in wg:
                weights[key] = np.asarray(wg[key])
    except Exception:
        pass
    return {
        "h5": h, "t": t, "fe": fe, "ff": ff, "sim_ms": sim_ms,
        "period_ms": period_ms,
        "weights": weights,
        "ia_gain": float(h.attrs.get("ia_feedback_gain", 1.0)),
        "stdp_lambda": float(h.attrs.get("stdp_lambda", 1e-3)),
        "measured_period_mean": float(np.mean(periods)) if periods.size else np.nan,
        "measured_period_std":  float(np.std(periods))  if periods.size else np.nan,
        "peak_e":  float(np.percentile(fe_w, 95)),
        "peak_f":  float(np.percentile(ff_w, 95)),
        "corr_ef": _safe_corr(fe_w, ff_w),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", type=str, default="results/2026-06-16")
    ap.add_argument("--outdir", type=str, default="plots/paper")
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--trace-window", choices=["first", "last"], default="first",
                    help="Show force traces from the FIRST window (default; reveals "
                         "STDP-rate-dependent self-organisation) or the LAST window "
                         "(converged steady state).")
    ap.add_argument("--trace-window-ms", type=float, default=20000.0,
                    help="Width of the force-trace window in ms (default 20000 = 20 s, "
                         "covering the STDP convergence transient).")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    out_path = args.out or os.path.join(args.outdir, "fig6_ablation_graded.png")

    files, LAMBDA_ORDER = _resolve_files(args.indir)
    if not LAMBDA_ORDER:
        raise SystemExit(f"No cpg_ablgrad_*.h5 files found in {args.indir}")

    # Build display label dict; assign roles by position (slowest=slow, fastest=fast).
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

    missing = [(g, l) for g in GAIN_ORDER for l in LAMBDA_ORDER if (g, l) not in files]
    if missing:
        print(f"[ablgrad] WARNING: missing cells: {missing}")
    print(f"[ablgrad] resolved {len(files)} files; λ tags = {LAMBDA_ORDER}")

    data: Dict[Tuple[str, str], Dict] = {}
    for g in GAIN_ORDER:
        for l in LAMBDA_ORDER:
            if (g, l) in files:
                data[(g, l)] = _load(files[(g, l)])

    plt.rcParams.update({
        "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
        "legend.fontsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
    })

    n_rows, n_cols = len(GAIN_ORDER), len(LAMBDA_ORDER)
    fig = plt.figure(figsize=(4.3 * n_cols, 18))
    # 5 rows: 3 force-trace rows, 1 metric-heat-tile row, 1 STDP
    # weight-trajectory row (the rescue mechanism: how fast the descending /
    # cutaneous weights re-equilibrate under air stepping at each λ).
    gs = fig.add_gridspec(5, n_cols, height_ratios=[1.0, 1.0, 1.0, 1.25, 1.20],
                          hspace=0.55, wspace=0.28)

    # Rows 1-3: Force traces, rows = gain, cols = lambda.
    # Default window = FIRST 20 s, where the STDP-rate-dependent
    # self-organisation of the gait is visible (weights saturate quickly,
    # so a converged-tail window shows no λ effect).
    win_ms = float(args.trace_window_ms)

    def _panel_tag(r, c):
        return f"B{r * n_cols + c + 1}"
    for r, g in enumerate(GAIN_ORDER):
        for c, l in enumerate(LAMBDA_ORDER):
            ax = fig.add_subplot(gs[r, c])
            if (g, l) not in data:
                ax.set_facecolor("#f5f5f5")
                ax.text(0.5, 0.5, "missing", ha="center", va="center",
                        transform=ax.transAxes, color="grey", fontsize=10)
                ax.set_xticks([]); ax.set_yticks([])
                continue
            d = data[(g, l)]
            if args.trace_window == "first":
                z0, z1 = 0.0, min(win_ms, d["sim_ms"])
            else:
                z0, z1 = max(0.0, d["sim_ms"] - win_ms), d["sim_ms"]
            mask = (d["t"] >= z0) & (d["t"] <= z1)
            ax.plot(d["t"][mask], d["fe"][mask], color="#1f77b4", linewidth=0.9, label="E")
            ax.plot(d["t"][mask], d["ff"][mask], color="#ff7f0e", linewidth=0.9, label="F")
            ax.set_xlim(z0, z1)
            ax.grid(alpha=0.2)
            ax.text(0.015, 0.97, _panel_tag(r, c), transform=ax.transAxes,
                    fontsize=10, fontweight="bold", va="top", ha="left",
                    bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="grey",
                              alpha=0.85, lw=0.6))
            if r == 0:
                ax.set_title(LAMBDA_LABEL[l], fontsize=9)
            if c == 0:
                ax.set_ylabel(f"{GAIN_LABEL[g]}\nforce (a.u.)", fontsize=9)
                ax.legend(loc="upper right", fontsize=7, ncol=2)
            if r == n_rows - 1:
                ax.set_xlabel("time (ms)")

    # Row 4: three summary heat-tiles
    metric_keys = ["measured_period_mean", "peak_e", "corr_ef"]
    metric_titles = [
        "(a) Cycle period (ms) — last 20 s",
        "(b) Peak Force-E (95th pct., a.u.)",
        "(c) E↔F counter-phase r",
    ]
    metric_cmaps = ["viridis", "plasma", "RdBu"]
    metric_vlim = [None, None, (-1.0, 0.4)]

    for m_idx, (mk, mtitle, cmap_name, vlim) in enumerate(
            zip(metric_keys, metric_titles, metric_cmaps, metric_vlim)):
        ax = fig.add_subplot(gs[3, m_idx])
        M = np.full((n_rows, n_cols), np.nan)
        for r, g in enumerate(GAIN_ORDER):
            for c, l in enumerate(LAMBDA_ORDER):
                if (g, l) in data:
                    M[r, c] = data[(g, l)][mk]
        if vlim is not None:
            im = ax.imshow(M, aspect="auto", cmap=cmap_name, vmin=vlim[0], vmax=vlim[1])
        else:
            im = ax.imshow(M, aspect="auto", cmap=cmap_name)
        ax.set_xticks(range(n_cols))
        ax.set_xticklabels([LAMBDA_LABEL[l].split("\n")[0] for l in LAMBDA_ORDER],
                           rotation=0, fontsize=8)
        ax.set_yticks(range(n_rows))
        ax.set_yticklabels([GAIN_LABEL[g].split("\n")[0] for g in GAIN_ORDER], fontsize=8)
        ax.set_title(mtitle, fontsize=10)
        for r in range(n_rows):
            for c in range(n_cols):
                if np.isfinite(M[r, c]):
                    val_str = f"{M[r, c]:.2f}" if mk == "corr_ef" else f"{M[r, c]:.1f}"
                    ax.text(c, r, val_str, ha="center", va="center",
                            color="white" if (cmap_name in ("viridis", "plasma") and r >= 1) else "black",
                            fontsize=9)
        plt.colorbar(im, ax=ax, fraction=0.05, pad=0.04)

    # ----- Row 5: STDP weight trajectories (the rescue mechanism) -----
    # (d) CUT->RG-E weight vs time at AIR stepping, 3 λ overlaid — faster λ
    #     re-equilibrates the cutaneous weight sooner, explaining the rescue.
    # (e) BS->RG-E weight vs time at AIR stepping, 3 λ overlaid (saturating).
    # (f) CUT->RG-E weight vs time at BASELINE λ, 3 Ia gains overlaid —
    #     compensation check: does reduced sensory feedback drive the
    #     descending weight to a different plateau?
    _traj_palette = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd", "#ff7f0e"]
    lam_color = {l: _traj_palette[i % len(_traj_palette)]
                 for i, l in enumerate(LAMBDA_ORDER)}
    anchor_gain = "air"            # degraded condition where λ matters most

    ax_d = fig.add_subplot(gs[4, 0])
    for l in LAMBDA_ORDER:
        d = data.get((anchor_gain, l))
        if d is None or "cut->rge_mean" not in d["weights"]:
            continue
        w = d["weights"]["cut->rge_mean"]
        tt = d["t"][: w.size]
        ax_d.plot(tt / 1000.0, w, color=lam_color[l], linewidth=1.2,
                  label=LAMBDA_LABEL[l].split("\n")[0])
    ax_d.set_xlabel("time (s)"); ax_d.set_ylabel("mean weight (pA)")
    ax_d.set_title("(d) CUT→RG-E weight trajectory\n(air stepping; λ-dependent transient)")
    ax_d.legend(loc="lower right", fontsize=7)
    ax_d.grid(alpha=0.2)

    # (BS->RG-E panel removed: BS is frozen in the canonical sensory model.)
    if n_cols > 1:
        # (e) CUT->RG-E mean ± std band at air stepping, λ overlaid. Reveals
        # the rescue mechanism: faster λ settles at a LOWER mean with a much
        # BROADER weight distribution (heterogeneous), which supports cleaner
        # counter-phase under degraded sensory feedback — the opposite of a
        # simple "stronger descending weight" account.
        ax_f = fig.add_subplot(gs[4, 1:])
        for l in LAMBDA_ORDER:
            d = data.get((anchor_gain, l))
            if d is None or "cut->rge_mean" not in d["weights"]:
                continue
            w = d["weights"]["cut->rge_mean"]
            tt = d["t"][: w.size]
            ax_f.plot(tt / 1000.0, w, color=lam_color[l], linewidth=1.2,
                      label=LAMBDA_LABEL[l].split("\n")[0])
            if "cut->rge_std" in d["weights"]:
                sd = d["weights"]["cut->rge_std"][: w.size]
                ax_f.fill_between(tt / 1000.0, w - sd, w + sd,
                                  color=lam_color[l], alpha=0.15)
        ax_f.set_xlabel("time (s)"); ax_f.set_ylabel("weight (pA)")
        ax_f.set_title("(e) CUT→RG-E mean ± std — air stepping (fast λ: lower mean, broader distribution)")
        ax_f.legend(loc="lower right", fontsize=7)
        ax_f.grid(alpha=0.2)

    win_desc = (f"first {win_ms/1000:.0f} s" if args.trace_window == "first"
                else f"last {win_ms/1000:.0f} s")
    sim_s = max((d["sim_ms"] for d in data.values()), default=120000.0) / 1000.0
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"[ablgrad] saved {out_path}")

    csv_path = os.path.splitext(out_path)[0] + "_metrics.csv"
    with open(csv_path, "w") as fh:
        fh.write("ia_gain_tag,ia_gain_val,lambda_tag,lambda_val,"
                 "measured_period_ms,period_std_ms,peak_force_e,peak_force_f,corr_ef\n")
        for g in GAIN_ORDER:
            for l in LAMBDA_ORDER:
                if (g, l) not in data:
                    continue
                d = data[(g, l)]
                fh.write(f"{g},{GAIN_VAL[g]},{l},{LAMBDA_VAL[l]},"
                         f"{d['measured_period_mean']:.2f},{d['measured_period_std']:.2f},"
                         f"{d['peak_e']:.3f},{d['peak_f']:.3f},{d['corr_ef']:.3f}\n")
    print(f"[ablgrad] metrics CSV: {csv_path}")

    for d in data.values():
        d["h5"].close()


if __name__ == "__main__":
    main()
