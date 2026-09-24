#!/usr/bin/env python3
"""
cpg_consolidate_bout_timeline.py
Visualizes the finding that --consolidate's whole-run frac_at_cap regression
is an extended-but-resolving early recovery transient, not a persistent
steady-state problem: plots each stance bout's duration against its onset
time, one row per --consolidate condition, with a horizontal line at
--cut-max-stance-ms. Bouts sitting on the cap line are failsafe-terminated
(disguised clock); bouts below it are genuine force-threshold crossings.
"""
import argparse, os
import h5py, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt


def bouts_from_cut_on(t_ms, cut_on):
    stance = cut_on > 0.5
    trans = np.diff(stance.astype(int))
    onsets = t_ms[1:][trans == 1]
    offsets = t_ms[1:][trans == -1]
    on_list, dur_list = [], []
    for on in onsets:
        off = offsets[offsets > on]
        if len(off):
            on_list.append(float(on))
            dur_list.append(float(off[0] - on))
    return np.asarray(on_list), np.asarray(dur_list)


def _parse_run(s):
    label, path = s.split("=", 1)
    return label, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True, help="label=path.h5, repeatable")
    ap.add_argument("--leg", default="L")
    ap.add_argument("--steady-from-ms", type=float, default=30000.0)
    ap.add_argument("--out", default="plots/consolidate_bout_timeline.png")
    ap.add_argument("--dpi", type=int, default=170)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    runs = [_parse_run(s) for s in args.run]
    nr = len(runs)
    fig, axes = plt.subplots(nr, 1, figsize=(9, 2.1 * nr), squeeze=False, sharex=True)

    for r, (label, path) in enumerate(runs):
        ax = axes[r][0]
        with h5py.File(path, "r") as h:
            cap = float(h.attrs.get("cut_max_stance_ms", 450.0))
            c = np.asarray(h[f"leg_{args.leg}/cut_on"])
            t = np.asarray(h["times_ms"])
        onsets, durs = bouts_from_cut_on(t, c)
        at_cap = (durs >= cap) & (durs <= cap + 110.0)
        steady_s = args.steady_from_ms / 1000.0
        sim_end_s = float(t[-1]) / 1000.0 if len(t) else steady_s * 2
        ax.axhline(cap, color="#b0392f", linestyle="--", linewidth=1, label=f"cap ({cap:.0f}ms)")
        ax.axvspan(0, steady_s, color="#f0c419", alpha=0.15)
        ax.scatter(onsets[~at_cap] / 1000.0, durs[~at_cap], s=22, color="#2a7f3f",
                   label="genuine", zorder=3)
        ax.scatter(onsets[at_cap] / 1000.0, durs[at_cap], s=22, color="#b0392f",
                   marker="x", label="failsafe-capped", zorder=3)
        ax.set_xlim(0, sim_end_s)
        ax.set_ylim(0, cap * 1.25)
        ax.set_ylabel("stance\nduration (ms)", fontsize=9)
        ax.set_title(label, fontsize=11, fontweight="bold", loc="left")
        ax.grid(alpha=0.2)
        if r == 0:
            ax.text(steady_s / 2.0, cap * 1.15, "recovery\nwindow",
                    ha="center", va="top", fontsize=8, color="#8a6d00")
            ax.legend(loc="lower right", fontsize=8, ncol=3, framealpha=0.9)
    axes[-1][0].set_xlabel(f"bout onset time (s), leg {args.leg}", fontsize=10)
    fig.tight_layout()
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[bout-timeline] saved {args.out}")


if __name__ == "__main__":
    main()
