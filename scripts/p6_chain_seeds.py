#!/usr/bin/env python3
"""
p6_chain_seeds.py
PLAN.md Phase 6: recovery curves of session chains across seeds (run_p6_chain_mn5.sh
layout <root>/chain/s<seed>/<mode>/s<k>/<mode>.h5). Per mode, against session number:
  left   r(E,F) at the end of each session (last --late-ms), mean +/- sd over seeds,
         thin lines per seed; the healthy source level (<root>/src) as a dashed line
  right  captured CUT->RG-E baseline at the end of each session (what the next session
         starts from), same layout
Prints the table (mean +/- sd) and the sessions to criterion (r(E,F) <= --criterion).

Usage:
  python3 scripts/p6_chain_seeds.py results/2026-10-01/p6_prod --out plots/p6/prod_recovery.png
"""
import argparse
import glob
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p6_session_metrics import metrics  # noqa: E402

INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
MODE_COL = {"bws50": "#eb6834", "bws90": "#3b6fd6"}
MODE_LABEL = {"bws50": "BWS 50%", "bws90": "BWS 90%"}


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK_2, labelsize=8, length=2.5)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def num(p):
    return int(re.sub(r"\D", "", os.path.basename(p)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", required=True)
    ap.add_argument("--late-ms", type=float, default=10000.0)
    ap.add_argument("--criterion", type=float, default=-0.5)
    args = ap.parse_args()
    late = (-args.late_ms, 0.0)
    seeds = sorted(glob.glob(os.path.join(args.root, "chain", "s*")), key=num)
    modes = sorted({os.path.basename(m) for s in seeds for m in glob.glob(os.path.join(s, "*")) if os.path.isdir(m)})
    data = {}
    for mode in modes:
        for sd in seeds:
            runs = sorted(glob.glob(os.path.join(sd, mode, "s*", f"{mode}.h5")), key=lambda p: num(os.path.dirname(p)))
            if runs:
                data[(mode, os.path.basename(sd))] = [metrics(p, (2000.0, 12000.0), late) for p in runs]
    healthy = [metrics(p, (2000.0, 12000.0), late)["r_late"]
               for p in glob.glob(os.path.join(args.root, "src", "s*", "comfortable.h5"))]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), facecolor=SURFACE)
    for ax in axes:
        style(ax)
    for mode in modes:
        keys = [k for k in data if k[0] == mode]
        n = min(len(data[k]) for k in keys)
        x = np.arange(1, n + 1)
        print(f"\n{MODE_LABEL.get(mode, mode)}  ({len(keys)} seeds)")
        for ax, field, fmt in ((axes[0], "r_late", "{:+.2f}"), (axes[1], "base_end", "{:.1f}")):
            A = np.array([[r[field] for r in data[k][:n]] for k in keys])
            for row in A:
                ax.plot(x, row, color=MODE_COL.get(mode, INK), linewidth=0.6, alpha=0.45)
            m, s = A.mean(0), A.std(0, ddof=1) if len(A) > 1 else np.zeros(n)
            ax.fill_between(x, m - s, m + s, color=MODE_COL.get(mode, INK), alpha=0.18, linewidth=0)
            ax.plot(x, m, "o-", color=MODE_COL.get(mode, INK), markersize=3.5, linewidth=1.8,
                    label=MODE_LABEL.get(mode, mode))
            print(f"  {field:8s} " + " ".join((fmt.format(a) + "±" + f"{b:.2f}") for a, b in zip(m, s)))
        for k in keys:
            hit = next((i + 1 for i, r in enumerate(data[k]) if r["r_late"] <= args.criterion), None)
            print(f"  {k[1]}: sessions to criterion (r(E,F) <= {args.criterion}) = {hit}")
    if healthy:
        axes[0].axhline(np.mean(healthy), color=INK_2, linestyle="--", linewidth=1.0,
                        label=f"healthy, full loading ({np.mean(healthy):+.2f})")
    axes[0].axhline(args.criterion, color=MUTED, linestyle=":", linewidth=1.0, label=f"criterion {args.criterion:+.1f}")
    axes[0].set_ylabel("r(E,F), end of session", fontsize=9, color=INK_2)
    axes[0].set_title("Flexor–extensor alternation", fontsize=10.5, color=INK, loc="left", fontweight="bold")
    axes[0].invert_yaxis()
    axes[1].set_ylabel("captured CUT→RG-E (pA), end of session", fontsize=9, color=INK_2)
    axes[1].set_title("Consolidated weight carried to the next session", fontsize=10.5, color=INK, loc="left",
                      fontweight="bold")
    for ax in axes:
        ax.set_xlabel("session", fontsize=9, color=INK_2)
        ax.legend(fontsize=8, frameon=False, labelcolor=INK_2)
    fig.suptitle(f"P6 session chains, production size: mean ± sd over {len(seeds)} seeds (thin: single seeds)",
                 x=0.06, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.tight_layout()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print(f"\n[p6-seeds] wrote {args.out}")


if __name__ == "__main__":
    main()
