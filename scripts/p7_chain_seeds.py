#!/usr/bin/env python3
"""
p7_chain_seeds.py
PLAN.md P7b: recovery curves of the MN5 production chains (run_chains_mn5.sh layout
<root>/chain/s<seed>/<condition>/s<k>/<mode>.h5) across seeds, with the P6 spinal chains as the
controls (healthy extensor, no EES; <control>/chain/s<seed>/<mode>/s<k>/<mode>.h5).
One row per support level (BWS 50%, BWS 90%), against session number:
  left    r(Force-E, Force-F), mean of the legs, last --last-ms of each session
  middle  captured CUT->RG-E weight at the end of the session (what the next session starts from)
  right   stride (ms), last --last-ms
Colour = extensor strength (1, 0.5, 0.25), solid = EES 10 Hz, dashed = no EES; mean over seeds,
shaded +/- sd. Prints the table (session 1, session 15, training change) and sessions to criterion.

Usage:
  python3 scripts/p7_chain_seeds.py results/2026-10-12/p7/p7 --control results/2026-10-07/p6/p6_spinal \
      --out plots/p7/mn5_recovery.png
"""
import argparse
import glob
import os
import re
import sys

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpg_gait_phase_metrics import metrics as phase_metrics  # noqa: E402

INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
STRENGTH_COL = {1.0: INK, 0.5: "#eb6834", 0.25: "#3b6fd6"}


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK_2, labelsize=8, length=2.5)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def session(path, last_ms):
    with h5py.File(path, "r") as f:
        t = f["times_ms"][()]
        k = t > t[-1] - last_ms
        r = []
        for s in "LR":
            e, fl = f[f"leg_{s}/force_e"][()][k], f[f"leg_{s}/force_f"][()][k]
            r.append(np.corrcoef(e, fl)[0, 1] if e.std() > 1e-9 and fl.std() > 1e-9 else np.nan)
        cut = np.mean([f[f"leg_{s}/full_weights/cut_to_rge/baseline"][()].mean() for s in "LR"])
    pm = phase_metrics(path, float(t[-1]) - last_ms)
    return float(np.nanmean(r)), float(cut), float(pm.get("stride_meas", np.nan))


def chain(d, mode, last_ms):
    fs = sorted(glob.glob(os.path.join(d, "s*", f"{mode}.h5")),
                key=lambda p: int(re.sub(r"\D", "", os.path.basename(os.path.dirname(p)))))
    return np.array([session(p, last_ms) for p in fs])


def parse(name):
    """condition name -> (mode, extensor strength, EES)"""
    mode = "bws50" if "bws50" in name else "bws90"
    m = re.match(r"s([0-9.]+)_", name)
    return mode, float(m.group(1)) if m else 1.0, "ees" in name


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--control", default=None, help="P6 chains root (controls: healthy extensor, no EES)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--last-ms", type=float, default=20000.0)
    ap.add_argument("--criterion", type=float, default=-0.5)
    args = ap.parse_args()
    seeds = sorted(os.path.basename(p) for p in glob.glob(os.path.join(args.root, "chain", "s*")))
    conds = sorted({os.path.basename(c) for s in seeds for c in glob.glob(os.path.join(args.root, "chain", s, "*"))
                    if os.path.isdir(c)})
    data = {}  # name -> array (seeds, sessions, 3)
    for c in conds:
        mode = parse(c)[0]
        runs = [chain(os.path.join(args.root, "chain", s, c), mode, args.last_ms) for s in seeds]
        data[c] = runs
    if args.control:
        for mode in ("bws50", "bws90"):
            runs = [chain(os.path.join(args.control, "chain", s, mode), mode, args.last_ms) for s in seeds]
            if all(len(r) for r in runs):
                data[mode] = runs

    fig, axes = plt.subplots(2, 3, figsize=(15, 8.2), facecolor=SURFACE)
    for ax in axes.flat:
        style(ax)
    print(f"{'condition':20s} {'r s1':>6s} {'r last':>7s} {'train':>12s} {'CUT s1':>7s} {'CUT last':>8s} "
          f"{'stride last':>12s}  to criterion")
    for row, mode in enumerate(("bws50", "bws90")):
        names = sorted((n for n in data if parse(n)[0] == mode), key=lambda n: (-parse(n)[1], parse(n)[2]))
        for n in names:
            _, s, ees = parse(n)
            n_s = min(len(r) for r in data[n])
            A = np.array([r[:n_s] for r in data[n]])  # seeds x sessions x 3
            x = np.arange(1, n_s + 1)
            col = STRENGTH_COL.get(s, MUTED)
            lab = f"strength {s:g}, {'EES 10 Hz' if ees else 'no EES'}" + ("  (P6 control)" if n == mode else "")
            for j, ax in enumerate(axes[row]):
                m = A[:, :, j].mean(0)
                sd = A[:, :, j].std(0, ddof=1) if len(A) > 1 else np.zeros(n_s)
                ax.fill_between(x, m - sd, m + sd, color=col, alpha=0.12, linewidth=0)
                ax.plot(x, m, "-" if ees else "--", color=col, linewidth=1.8, marker="o" if ees else None,
                        markersize=3, label=lab)
            r = A[:, :, 0]
            crit = [next((i + 1 for i, v in enumerate(rr) if v <= args.criterion), None) for rr in r]
            d = r[:, -1] - r[:, 0]
            print(f"{n:20s} {r[:, 0].mean():+6.2f} {r[:, -1].mean():+7.2f} {d.mean():+6.2f}±{d.std(ddof=1):.2f} "
                  f"{A[:, 0, 1].mean():7.1f} {A[:, -1, 1].mean():8.1f} {A[:, -1, 2].mean():7.0f}±{A[:, -1, 2].std(ddof=1):3.0f}"
                  f"  {crit}")
        axes[row, 0].axhline(args.criterion, color=MUTED, linestyle=":", linewidth=1.0)
        axes[row, 0].invert_yaxis()
        axes[row, 0].set_ylabel(f"{'BWS 50%' if mode == 'bws50' else 'BWS 90%'}\n\nr(E,F), end of session",
                                fontsize=9, color=INK_2)
        axes[row, 1].set_ylabel("captured CUT→RG-E (pA)", fontsize=9, color=INK_2)
        axes[row, 2].set_ylabel("stride (ms)", fontsize=9, color=INK_2)
        for ax in axes[row]:
            ax.set_xlabel("session", fontsize=9, color=INK_2)
    for j, t in enumerate(("Flexor–extensor alternation (criterion dotted)", "Consolidated CUT→RG-E weight",
                           "Stride")):
        axes[0, j].set_title(t, fontsize=10.5, color=INK, loc="left", fontweight="bold")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=3, frameon=False, fontsize=8.5, labelcolor=INK_2,
               bbox_to_anchor=(0.5, 0.955))
    fig.suptitle(f"P7b production chains (N = 100): extensor weakness × EES, mean ± sd over {len(seeds)} seeds",
                 x=0.06, ha="left", fontsize=12.5, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print(f"[p7-seeds] wrote {args.out}")


if __name__ == "__main__":
    main()
