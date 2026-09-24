#!/usr/bin/env python3
"""
cpg_compare_idxes.py
Generate combined comparison plots across multiple sweep-idx HDF5 files
for force, length, RG activation (rates), and STDP learning weights.

Example:
  python3 cpg_compare_idxes.py \
    --files cpg_bursting_paced_idx00_*.h5 cpg_bursting_paced_idx04_*.h5 cpg_bursting_paced_idx09_*.h5 \
    --outdir plots/mn5_paced_compare
"""

import argparse
import glob
import os
import re
from typing import List

import h5py
import matplotlib.pyplot as plt
import numpy as np


def _label_from_filename(path: str) -> str:
    """Extract a compact 'idx04 mu=3.5 cv=0.30' label from a filename."""
    base = os.path.basename(path)
    m_idx = re.search(r"idx(\d+)", base)
    m_mu = re.search(r"mu([\d.]+)", base)
    m_cv = re.search(r"cv([\d.]+)", base)
    parts = []
    if m_idx:
        parts.append(f"idx{m_idx.group(1)}")
    if m_mu:
        parts.append(f"μ={float(m_mu.group(1)):.2f}")
    if m_cv:
        parts.append(f"CV={float(m_cv.group(1)):.2f}")
    return " ".join(parts) if parts else base


def _moving_average(x: np.ndarray, win: int) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if win <= 1 or x.size == 0:
        return x
    # Fill NaNs forward then smooth
    if np.isnan(x).any():
        idx = np.where(~np.isnan(x))[0]
        if idx.size:
            x = x.copy()
            x[: idx[0]] = x[idx[0]]
            for i in range(idx.size - 1):
                a, b = idx[i], idx[i + 1]
                if b > a + 1:
                    x[a + 1 : b] = x[a]
            x[idx[-1] + 1 :] = x[idx[-1]]
    kernel = np.ones(win, dtype=float) / win
    return np.convolve(x, kernel, mode="same")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="+", required=True,
                    help="HDF5 files to compare (glob patterns accepted).")
    ap.add_argument("--outdir", type=str, default="plots/mn5_paced_compare")
    ap.add_argument("--leg", type=str, default="L", choices=["L", "R"])
    ap.add_argument("--smooth-sec", type=float, default=1.0)
    args = ap.parse_args()

    # Expand glob patterns
    files: List[str] = []
    for pat in args.files:
        matches = sorted(glob.glob(pat))
        files.extend(matches if matches else [pat])
    files = sorted(set(files))
    if not files:
        raise SystemExit("No files matched.")

    os.makedirs(args.outdir, exist_ok=True)
    print(f"[compare] {len(files)} files → {args.outdir}")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    # Pre-load
    runs = []
    for f in files:
        h5 = h5py.File(f, "r")
        runs.append({
            "h5": h5,
            "label": _label_from_filename(f),
            "times_ms": np.asarray(h5["times_ms"]),
            "wtimes_ms": np.asarray(h5["weights_times_ms"]) if "weights_times_ms" in h5 else None,
            "g": h5[f"leg_{args.leg}"],
            "dt_ms": float(h5.attrs.get("dt_ms", 100.0)),
        })

    colors = [f"C{i}" for i in range(len(runs))]

    # 1) FORCE — E (top) and F (bottom), one panel each, all idxes overlaid
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    for r, c in zip(runs, colors):
        axes[0].plot(r["times_ms"], r["g"]["force_e"][:], color=c, label=r["label"], linewidth=1.0)
        axes[1].plot(r["times_ms"], r["g"]["force_f"][:], color=c, label=r["label"], linewidth=1.0)
    axes[0].set_title(f"Force-E — leg {args.leg} (paced gait, MN5 production sweep)")
    axes[1].set_title(f"Force-F — leg {args.leg}")
    axes[0].set_ylabel("force E (a.u.)")
    axes[1].set_ylabel("force F (a.u.)")
    axes[1].set_xlabel("time (ms)")
    axes[0].legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(args.outdir, f"compare_force_leg{args.leg}.png"), dpi=150)
    plt.close(fig)

    # 2) LENGTH — E and F panels, all idxes overlaid
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    for r, c in zip(runs, colors):
        axes[0].plot(r["times_ms"], r["g"]["len_e"][:], color=c, label=r["label"], linewidth=1.0)
        axes[1].plot(r["times_ms"], r["g"]["len_f"][:], color=c, label=r["label"], linewidth=1.0)
    axes[0].axhline(1.0, linestyle="--", linewidth=0.8, color="grey", alpha=0.5)
    axes[1].axhline(1.0, linestyle="--", linewidth=0.8, color="grey", alpha=0.5)
    axes[0].set_title(f"Length-E — leg {args.leg} (paced gait, MN5 production sweep)")
    axes[1].set_title(f"Length-F — leg {args.leg}")
    axes[0].set_ylabel("length E (a.u.)")
    axes[1].set_ylabel("length F (a.u.)")
    axes[1].set_xlabel("time (ms)")
    axes[0].legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(args.outdir, f"compare_length_leg{args.leg}.png"), dpi=150)
    plt.close(fig)

    # 3) RG ACTIVATION (population rates RG-E and RG-F)
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    for r, c in zip(runs, colors):
        axes[0].plot(r["times_ms"], r["g"]["rge"][:], color=c, label=r["label"], linewidth=0.9, alpha=0.85)
        axes[1].plot(r["times_ms"], r["g"]["rgf"][:], color=c, label=r["label"], linewidth=0.9, alpha=0.85)
    axes[0].set_title(f"RG-E population rate — leg {args.leg} (paced gait, MN5 production sweep)")
    axes[1].set_title(f"RG-F population rate — leg {args.leg}")
    axes[0].set_ylabel("RG-E rate (Hz/neuron)")
    axes[1].set_ylabel("RG-F rate (Hz/neuron)")
    axes[1].set_xlabel("time (ms)")
    axes[0].legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(args.outdir, f"compare_rg_rate_leg{args.leg}.png"), dpi=150)
    plt.close(fig)

    # 4) STDP LEARNING — 3 panels: cut->rge, bs->rge, bs->rgf — overlay each idx mean
    win = max(1, int(args.smooth_sec * 1000.0 / max(1.0, runs[0]["dt_ms"])))
    proj_keys = ["cut->rge", "bs->rge", "bs->rgf"]
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    for ax, proj in zip(axes, proj_keys):
        for r, col in zip(runs, colors):
            w = r["g"]["weights"]
            mk = f"{proj}_mean"
            sk = f"{proj}_std"
            if mk not in w:
                continue
            m = _moving_average(np.asarray(w[mk][:]), win)
            ax.plot(r["times_ms"], m, color=col, label=r["label"], linewidth=1.2)
            if sk in w:
                s = _moving_average(np.asarray(w[sk][:]), win)
                ax.fill_between(r["times_ms"], m - s, m + s, color=col, alpha=0.12)
        ax.set_title(f"STDP — {proj} mean ± std ({args.smooth_sec:.1f}s MA)")
        ax.set_ylabel("weight (pA)")
        ax.legend(loc="lower right", fontsize=9)
    axes[-1].set_xlabel("time (ms)")
    fig.tight_layout()
    fig.savefig(os.path.join(args.outdir, f"compare_stdp_leg{args.leg}.png"), dpi=150)
    plt.close(fig)

    # 5) Bonus: muscle activation envelopes
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    for r, c in zip(runs, colors):
        axes[0].plot(r["times_ms"], r["g"]["act_e"][:], color=c, label=r["label"], linewidth=0.9, alpha=0.9)
        axes[1].plot(r["times_ms"], r["g"]["act_f"][:], color=c, label=r["label"], linewidth=0.9, alpha=0.9)
    axes[0].set_title(f"Activation-E proxy — leg {args.leg} (paced gait)")
    axes[1].set_title(f"Activation-F proxy — leg {args.leg}")
    axes[0].set_ylabel("act E (a.u.)")
    axes[1].set_ylabel("act F (a.u.)")
    axes[1].set_xlabel("time (ms)")
    axes[0].legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(args.outdir, f"compare_activation_leg{args.leg}.png"), dpi=150)
    plt.close(fig)

    for r in runs:
        r["h5"].close()

    print(f"[compare] wrote {len(os.listdir(args.outdir))} PNGs in {args.outdir}")


if __name__ == "__main__":
    main()
