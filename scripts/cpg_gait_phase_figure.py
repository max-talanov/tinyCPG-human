#!/usr/bin/env python3
"""
cpg_gait_phase_figure.py
PLAN.md Phase 3 figure: the per-leg stance schedule (with double support) and
the extensor forces of both legs, for one or more runs with the phase
scheduler (they need the per-leg `cut_on` log).

One row per run: the last --strides strides. Top of each panel: stance bars
for the left (ink) and right (gray) leg; double support (both legs in stance)
is shaded across the panel. Traces: Force-E of the left (ink) and right (gray)
leg. The title gives the scheduled stance fraction and double support, and the
in-window left/right extensor correlation.

Usage:
  python3 scripts/cpg_gait_phase_figure.py label=run.h5 [label=run.h5 ...] --out fig.png
"""
import argparse

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
DS_FILL = "#f3e3c3"


def spans(t, mask):
    """[(start, end)] of runs where mask is True; t are chunk END times."""
    out, start = [], None
    t0 = np.concatenate([[t[0] - (t[1] - t[0])], t[:-1]])  # chunk start times
    for i, m in enumerate(mask):
        if m and start is None:
            start = t0[i]
        if not m and start is not None:
            out.append((start, t0[i])); start = None
    if start is not None:
        out.append((start, t[-1]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", help="label=path.h5")
    ap.add_argument("--out", required=True)
    ap.add_argument("--strides", type=int, default=3)
    args = ap.parse_args()

    rows = []
    for spec in args.runs:
        label, path = spec.split("=", 1)
        with h5py.File(path, "r") as f:
            a = dict(f.attrs)
            rows.append((label, a, f["times_ms"][()] / 1000.0,
                         {s: f[f"leg_{s}/force_e"][()] for s in "LR"},
                         {s: f[f"leg_{s}/cut_on"][()] > 0.5 for s in "LR"}))
    fmax = max(max(fe["L"].max(), fe["R"].max()) for _, _, _, fe, _ in rows)

    fig, axes = plt.subplots(len(rows), 1, figsize=(12, 2.6 * len(rows)), facecolor=SURFACE,
                             gridspec_kw={"hspace": 0.55}, squeeze=False)
    for ax, (label, a, t, fe, on) in zip(axes[:, 0], rows):
        T = float(a["step_period_ms"]) / 1000.0
        lo, hi = t[-1] - args.strides * T, t[-1]
        m = (t > lo) & (t <= hi)
        ax.set_facecolor(SURFACE)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(MUTED)
        ax.tick_params(colors=INK_2, labelsize=8)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for x0, x1 in spans(t[m], on["L"][m] & on["R"][m]):
            ax.axvspan(x0, x1, color=DS_FILL, linewidth=0, zorder=0)
        for side, col, y in (("L", INK, 1.16), ("R", MUTED, 1.06)):
            for x0, x1 in spans(t[m], on[side][m]):
                ax.plot([x0, x1], [y * fmax, y * fmax], color=col, linewidth=5, solid_capstyle="butt")
            ax.text(lo - 0.01 * (hi - lo), y * fmax, f"{side} stance", ha="right", va="center",
                    fontsize=7.5, color=INK_2)
        ax.plot(t[m], fe["L"][m], color=INK, linewidth=1.6, label="Force-E left")
        ax.plot(t[m], fe["R"][m], color=MUTED, linewidth=1.6, label="Force-E right")
        ax.set_xlim(lo, hi); ax.set_ylim(0, 1.24 * fmax)
        ax.set_yticks([v for v in range(0, int(fmax) + 1, 5)])  # keep tick labels clear of the stance bars
        r = np.corrcoef(fe["L"][m], fe["R"][m])[0, 1]
        f_st = float(a.get("stance_fraction", 0.5))
        ax.set_title(f"{label}:  stance {f_st:.2f} × {T * 1000:.0f} ms stride,  scheduled double support "
                     f"{max(0.0, 2 * f_st - 1) * 50:.0f}% per transition   r(E_L, E_R) = {r:+.2f}",
                     fontsize=9.5, color=INK, loc="left")
        ax.set_ylabel("Force-E (a.u.)", fontsize=8.5, color=INK_2)
    axes[-1, 0].set_xlabel("time (s)", fontsize=9, color=INK_2)
    h, l = axes[0, 0].get_legend_handles_labels()
    h.append(plt.Rectangle((0, 0), 1, 1, color=DS_FILL)); l.append("double support (both legs in stance)")
    fig.legend(h, l, loc="upper center", ncol=3, frameon=False, fontsize=8.5, labelcolor=INK_2,
               bbox_to_anchor=(0.5, 0.965 if len(rows) > 2 else 1.0))
    sp = rows[0][1].get("species", "?")
    fig.text(0.06, 1.0, f"{sp}: P3 phase scheduler — stance schedule and extensor forces, both legs",
             ha="left", va="bottom", fontsize=12, fontweight="bold", color=INK)
    fig.savefig(args.out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print(f"[gait-phase] wrote {args.out}")


if __name__ == "__main__":
    main()
