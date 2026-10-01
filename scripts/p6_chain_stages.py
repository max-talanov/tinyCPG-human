#!/usr/bin/env python3
"""
p6_chain_stages.py
PLAN.md Phase 6: force and plastic weights of session chains (run_p6_sessions.sh) at
three states -- the first, a middle and the last session.

Layout: one row per chain (e.g. BWS 50%, BWS 90%), 4 columns:
  cols 1-3  force in the last --window-ms of session 1, the middle session and the last
            session, left leg: Force-E (ink) and Force-F (gray); title: r(E,F) L and R
  col 4     weights over the whole chain (sessions back to back): live mean CUT->RG-E
            (orange), its captured baseline (orange dotted), Ia->RG-E / Ia->RG-F on the right
            axis; left leg; session boundaries as thin lines, the three shown sessions shaded

Usage:
  python3 scripts/p6_chain_stages.py results/human_modes/p6_chain15/bws50 \
      results/human_modes/p6_chain15/bws90 --out plots/p6/chain15_stages.png
"""
import argparse
import glob
import os
import re

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
COL = {"cut->rge": "#eb6834", "ia->rge": "#1baf7a", "ia->rgf": "#8e6bd6"}
LABEL = {"cut->rge": "CUT→E", "ia->rge": "Ia→E", "ia->rgf": "Ia→F"}


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK_2, labelsize=7.5, length=2.5)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def corr(a, b):
    return np.corrcoef(a, b)[0, 1] if a.std() > 1e-9 and b.std() > 1e-9 else np.nan


def load_chain(d):
    sess = sorted(glob.glob(os.path.join(d, "s*")), key=lambda p: int(re.sub(r"\D", "", os.path.basename(p))))
    runs = []
    for sd in sess:
        # session 1 also holds the source run (a symlink, or a copy after rsync -L): take <mode>.h5
        h5 = [p for p in glob.glob(os.path.join(sd, f"{os.path.basename(os.path.normpath(d))}.h5"))] or \
            [p for p in glob.glob(os.path.join(sd, "*.h5")) if not os.path.islink(p)]
        if not h5:
            continue
        with h5py.File(h5[0], "r") as f:
            r = {"t": f["times_ms"][()], "mode": os.path.splitext(os.path.basename(h5[0]))[0],
                 "loading": float(f.attrs.get("cut_feedback_gain", 1.0)),
                 "seed": int(f.attrs.get("seed", 0))}
            for s in "LR":
                g = f[f"leg_{s}"]
                r[s] = {"fe": g["force_e"][()], "ff": g["force_f"][()],
                        "w": {k: g[f"weights/{k}_mean"][()] for k in COL if f"weights/{k}_mean" in g},
                        "b": {k: g[f"consolidation/{k}_baseline_mean"][()] for k in COL
                              if f"consolidation/{k}_baseline_mean" in g}}
        runs.append(r)
    return runs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chains", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--window-ms", type=float, default=5000.0)
    args = ap.parse_args()
    chains = [(c, load_chain(c)) for c in args.chains]
    chains = [(c, r) for c, r in chains if r]
    fmax = max(max(r["L"]["fe"].max(), r["L"]["ff"].max()) for _, rs in chains for r in rs) * 1.08
    H = 2.6 * len(chains) + 1.4  # figure height (in); the top 1.4 in hold title, legend and column headers
    fig, axes = plt.subplots(len(chains), 4, figsize=(15, H), facecolor=SURFACE, squeeze=False,
                             gridspec_kw={"width_ratios": [1, 1, 1, 1.3], "hspace": 0.62, "wspace": 0.18})
    fig.subplots_adjust(top=1 - 1.4 / H, bottom=0.5 / H)
    for row, (cdir, runs) in enumerate(chains):
        n = len(runs)
        shown = [0, (n - 1) // 2, n - 1]
        for c in range(4):
            style(axes[row, c])
        for c, si in enumerate(shown):
            ax = axes[row, c]
            r = runs[si]
            m = r["t"] > r["t"][-1] - args.window_ms
            tt = (r["t"][m] - r["t"][m][0]) / 1000.0
            ax.plot(tt, r["L"]["fe"][m], color=INK, linewidth=1.3, label="Extensor (Force-E)")
            ax.plot(tt, r["L"]["ff"][m], color=MUTED, linewidth=1.3, label="Flexor (Force-F)")
            ax.set_ylim(0, fmax); ax.set_xlim(0, args.window_ms / 1000.0)
            rl = corr(r["L"]["fe"][m], r["L"]["ff"][m]); rr = corr(r["R"]["fe"][m], r["R"]["ff"][m])
            ax.set_title(f"session {si + 1}/{n}   r(E,F)  L {rl:+.2f}  R {rr:+.2f}", fontsize=8.5, color=INK,
                         loc="left")
            if row == 0:
                name = ["FIRST", "MIDDLE", "LAST"][c]
                ax.text(0.0, 1.2, f"{name} SESSION (last {args.window_ms / 1000:.0f} s)", transform=ax.transAxes,
                        fontsize=10.5, fontweight="bold", color=INK)
            if c == 0:
                ax.set_ylabel(f"{runs[0]['mode']}  seed {runs[0]['seed']}\n(loading {runs[0]['loading']:g}, {n} sessions)\n\n"
                              "Force (a.u.)",
                              fontsize=8.5, color=INK_2)
            if row == len(chains) - 1:
                ax.set_xlabel("time in window (s)", fontsize=8, color=INK_2)
        ax = axes[row, 3]
        ax2 = ax.twinx()
        ax2.spines["top"].set_visible(False); ax2.spines["right"].set_color(MUTED)
        ax2.tick_params(colors=INK_2, labelsize=7.5, length=2.5)
        t0 = 0.0
        ia_max = 1.0
        cut_max = 1.0
        for si, r in enumerate(runs):
            tt = (r["t"] / 1000.0) + t0
            if si in shown:
                ax.axvspan(tt[0], tt[-1], color=GRID, alpha=0.7, zorder=0)
            ax.axvline(t0, color=GRID, linewidth=0.6, zorder=0)
            for k, w in r["L"]["w"].items():
                tgt = ax2 if k.startswith("ia") else ax
                tgt.plot(tt, w, color=COL[k], linewidth=1.2, label=LABEL[k] if si == 0 else None)
                (cut_max, ia_max) = (cut_max, max(ia_max, np.nanmax(w))) if k.startswith("ia") else \
                    (max(cut_max, np.nanmax(w)), ia_max)
            if "cut->rge" in r["L"]["b"]:
                ax.plot(tt, r["L"]["b"]["cut->rge"], ":", color=COL["cut->rge"], linewidth=1.2,
                        label="CUT→E captured" if si == 0 else None)
            t0 = tt[-1]
        ax.set_xlim(0, t0); ax.set_ylim(0, cut_max * 1.15); ax2.set_ylim(0, ia_max * 1.8)
        ax.set_ylabel("CUT (pA)", fontsize=7.5, color=INK_2); ax2.set_ylabel("Ia (pA)", fontsize=7.5, color=INK_2)
        h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, fontsize=6.5, frameon=False, loc="lower right", labelcolor=INK_2)
        ax.set_title("weights over the chain (left leg)", fontsize=8.5, color=INK, loc="left")
        if row == 0:
            ax.text(0.0, 1.2, "PLASTIC WEIGHTS (pA)", transform=ax.transAxes, fontsize=10.5, fontweight="bold",
                    color=INK)
        if row == len(chains) - 1:
            ax.set_xlabel("simulated training time, sessions back to back (s)", fontsize=8, color=INK_2)
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=2, frameon=False, fontsize=8.5, labelcolor=INK_2,
               bbox_to_anchor=(0.5, 1 - 0.62 / H))
    fig.text(0.06, 1 - 0.12 / H, "P6 session chains: force and plastic weights, first / middle / last session",
             ha="left", va="top", fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.06, 1 - 0.42 / H, "each session starts from the previous session's captured baselines "
             "(--init-weights-state baseline); session 1 = injured start (trained comfortable weights x init_scale)",
             ha="left", va="top", fontsize=8.5, color=INK_2)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print(f"[p6-chain] wrote {args.out}")


if __name__ == "__main__":
    main()
