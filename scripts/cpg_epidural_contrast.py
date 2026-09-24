#!/usr/bin/env python3
"""
cpg_epidural_contrast.py
Paper Figure — epidural-stimulation rescue: paired contrast between
natural unloading (cutaneous CUT drive gated by limb loading) and
epidural-stim-assisted stepping (CUT pacing intact).

Reads two Phase B result sets at matched (μ, CV, λ):
  --stim-dir     CUT intact (loading-independent pacing)  → epidural stim
  --natural-dir  CUT gated by loading                     → unassisted

For each loading condition (baseline / toe / air) it compares the
counter-phase quality, demonstrating that the paced cutaneous drive
(the stim analogue) is what preserves stepping under unloading.

Layout (13 × 9 in):
  (a) corr(F_E,F_F) vs loading — stim vs natural
  (b) cycle-period s.d. vs loading — stim vs natural
  (c) air-stepping force trace — epidural stim (CUT intact)
  (d) air-stepping force trace — natural (CUT gated)

Usage:
  python3 cpg_epidural_contrast.py \\
      --stim-dir results/2026-06-20 --natural-dir results/2026-06-23 \\
      --lambda-tag lam1em3 --out plots/paper/fig14_epidural_contrast.png
"""

import argparse
import glob
import os
from typing import Dict, List, Optional

import h5py
import matplotlib.pyplot as plt
import numpy as np


GAINS = [("baseline", "baseline\nIa,CUT 1.0", 1.0),
         ("toe", "toe stepping\nIa,CUT 0.5", 0.5),
         ("air", "air stepping\nIa,CUT 0.1", 0.1)]


def _find(indir, pattern):
    hits = sorted(glob.glob(os.path.join(indir, pattern)))
    return hits[0] if hits else None


def _cycle_sd(t_ms, sig, period_ms):
    if sig.size < 5:
        return np.nan
    dt = float(np.median(np.diff(t_ms))) if t_ms.size > 1 else 100.0
    gap = max(1, int(max(120.0, period_ms * 0.4) / max(1e-9, dt)))
    above = sig > 3.0
    peaks, last = [], -10**9
    for i in range(1, sig.size - 1):
        if above[i] and sig[i] >= sig[i-1] and sig[i] >= sig[i+1] and i - last >= gap:
            peaks.append(i); last = i
    if len(peaks) < 2:
        return np.nan
    return float(np.std(np.diff(t_ms[np.asarray(peaks)])))


def _corr(a, b):
    if a.size < 4:
        return np.nan
    a = a - a.mean(); b = b - b.mean()
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / d) if d > 1e-12 else np.nan


def _metrics(path):
    with h5py.File(path, "r") as h:
        t = np.asarray(h["times_ms"]); sim = float(h.attrs.get("sim_ms", 120000.0))
        period = float(h.attrs.get("step_period_ms", 520.0))
        fe = np.asarray(h["leg_L/force_e"]); ff = np.asarray(h["leg_L/force_f"])
    m = t >= max(0.0, sim - 20000.0)
    return dict(corr=_corr(fe[m], ff[m]), sd=_cycle_sd(t[m], fe[m], period),
                t=t, fe=fe, ff=ff, sim=sim)


def _trace(ax, path, title, zoom=10000.0):
    d = _metrics(path)
    z = max(0.0, d["sim"] - zoom); m = d["t"] >= z
    ax.plot(d["t"][m], d["fe"][m], color="#1f77b4", lw=1.2, label="E")
    ax.plot(d["t"][m], d["ff"][m], color="#ff7f0e", lw=1.0, ls="--", alpha=0.75, label="F")
    ax.set_xlim(z, d["sim"]); ax.grid(alpha=0.2)
    ax.set_title(f"{title}\ncorr={d['corr']:.2f}", fontsize=10)
    ax.set_xlabel("time (ms)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stim-dir", required=True, help="CUT-intact (epidural-stim) results")
    ap.add_argument("--natural-dir", required=True, help="CUT-gated (natural) results")
    ap.add_argument("--lambda-tag", default="lam1em3")
    ap.add_argument("--stim-prefix", default="cpg_ablstim",
                    help="Filename prefix for the stim arm (CUT intact). "
                         "Auto-falls back to cpg_ablgrad if not found.")
    ap.add_argument("--natural-prefix", default="cpg_ablgrad",
                    help="Filename prefix for the natural arm (CUT gated).")
    ap.add_argument("--out", default="plots/paper/fig14_epidural_contrast.png")
    args = ap.parse_args()
    lam = args.lambda_tag

    def collect(indir, prefix):
        out = {}
        for tag, _lbl, _g in GAINS:
            f = _find(indir, f"{prefix}_{tag}_{lam}_*.h5")
            if f is None and prefix != "cpg_ablgrad":
                f = _find(indir, f"cpg_ablgrad_{tag}_{lam}_*.h5")  # fallback
            out[tag] = _metrics(f) if f else None
        return out
    stim = collect(args.stim_dir, args.stim_prefix)
    nat = collect(args.natural_dir, args.natural_prefix)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10})
    fig = plt.figure(figsize=(13, 9))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1.0], hspace=0.42, wspace=0.25)

    x = np.arange(len(GAINS)); xlabels = [g[1] for g in GAINS]

    # (a) corr vs loading
    ax_a = fig.add_subplot(gs[0, 0])
    ax_a.plot(x, [stim[g[0]]["corr"] if stim[g[0]] else np.nan for g in GAINS],
              "o-", color="#1f77b4", markersize=9, label="epidural stim (CUT intact)")
    ax_a.plot(x, [nat[g[0]]["corr"] if nat[g[0]] else np.nan for g in GAINS],
              "s--", color="#d62728", markersize=9, label="natural (CUT gated)")
    ax_a.axhline(-0.8, ls=":", color="grey", alpha=0.6, label="strong (−0.8)")
    ax_a.axhline(0.0, color="black", lw=0.5)
    ax_a.set_xticks(x); ax_a.set_xticklabels([g[1] for g in GAINS], fontsize=8)
    ax_a.set_ylabel("corr$(F_E, F_F)$"); ax_a.set_ylim(-1.05, 0.25)
    ax_a.set_title("(a) Counter-phase vs loading")
    ax_a.legend(loc="upper right", fontsize=8); ax_a.grid(alpha=0.2)

    # (b) period s.d. vs loading
    ax_b = fig.add_subplot(gs[0, 1])
    ax_b.plot(x, [stim[g[0]]["sd"] if stim[g[0]] else np.nan for g in GAINS],
              "o-", color="#1f77b4", markersize=9, label="epidural stim (CUT intact)")
    ax_b.plot(x, [nat[g[0]]["sd"] if nat[g[0]] else np.nan for g in GAINS],
              "s--", color="#d62728", markersize=9, label="natural (CUT gated)")
    ax_b.set_xticks(x); ax_b.set_xticklabels([g[1] for g in GAINS], fontsize=8)
    ax_b.set_ylabel("cycle-period s.d. (ms)")
    ax_b.set_title("(b) Cycle irregularity vs loading")
    ax_b.legend(loc="upper left", fontsize=8); ax_b.grid(alpha=0.2)

    # (c, d) air-stepping traces
    fa = (_find(args.stim_dir, f"{args.stim_prefix}_air_{lam}_*.h5")
          or _find(args.stim_dir, f"cpg_ablgrad_air_{lam}_*.h5"))
    fn = (_find(args.natural_dir, f"{args.natural_prefix}_air_{lam}_*.h5")
          or _find(args.natural_dir, f"cpg_ablgrad_air_{lam}_*.h5"))
    ax_c = fig.add_subplot(gs[1, 0])
    if fa:
        _trace(ax_c, fa, "(c) Air stepping — epidural stim (CUT intact)")
        ax_c.set_ylabel("Force E (solid) / F (dashed)"); ax_c.legend(loc="upper right", ncol=2, fontsize=7)
    ax_d = fig.add_subplot(gs[1, 1])
    if fn:
        _trace(ax_d, fn, "(d) Air stepping — natural (CUT gated)")

    lam_pretty = lam.replace("lam1em", "λ = 1·10⁻")
    fig.savefig(args.out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"[epidural] saved {args.out}")

    # CSV
    csv = os.path.splitext(args.out)[0] + "_metrics.csv"
    with open(csv, "w") as fh:
        fh.write("loading,condition,corr_ef,period_sd_ms\n")
        for tag, _lbl, _g in GAINS:
            for cond, dset in [("stim", stim), ("natural", nat)]:
                d = dset[tag]
                if d:
                    fh.write(f"{tag},{cond},{d['corr']:.3f},{d['sd']:.2f}\n")
    print(f"[epidural] metrics CSV: {csv}")


if __name__ == "__main__":
    main()
