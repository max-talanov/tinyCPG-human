#!/usr/bin/env python3
"""
cpg_collapse_lr_figure.py
Two circuit-level findings from the interneuron-recording runs:
  (1) the EXTENSOR COLLAPSE under natural unloading (and its absence under
      epidural-stim pacing), graded across loading;
  (2) the ROBUSTNESS of L/R commissural (interlimb) coordination — the legs
      keep alternating at 180° even when the within-leg E/F pattern breaks.

Layout (13 × 9 in):
  (a) RG-E mean rate vs loading           (stim vs natural)  — extensor collapse
  (b) RG-F mean rate vs loading           (stim vs natural)  — flexor takeover
  (c) L/R RG-E coordination strength vs loading (stim vs natural)
  (d) L RG-E vs R RG-E traces at air stepping (natural) — 180° preserved

Usage:
  python3 cpg_collapse_lr_figure.py --indir results/2026-06-28 \\
      --lambda-tag lam1em3 --out plots/paper/network/fig_collapse_lr.png
"""

import argparse
import glob
import os

import h5py
import matplotlib.pyplot as plt
import numpy as np

GAINS = [("baseline", "baseline\n1.0"), ("toe", "toe\n0.5"), ("air", "air\n0.1")]


def _find(indir, pat):
    h = sorted(glob.glob(os.path.join(indir, pat)))
    return h[0] if h else None


def _load(f):
    h = h5py.File(f, "r")
    t = np.asarray(h["times_ms"]); sim = float(h.attrs["sim_ms"])
    per = float(h.attrs.get("step_period_ms", 520)); m = t >= sim - 20000
    d = dict(t=t[m] - (sim - 20000), per=per,
             le=np.asarray(h["leg_L/rge"])[m], lf=np.asarray(h["leg_L/rgf"])[m],
             re=np.asarray(h["leg_R/rge"])[m])
    h.close(); return d


def _mean(f, key):
    h = h5py.File(f, "r"); t = np.asarray(h["times_ms"]); sim = float(h.attrs["sim_ms"])
    m = t >= sim - 20000; v = float(np.mean(np.asarray(h["leg_L/" + key])[m])); h.close()
    return v


def _lr_strength(f):
    d = _load(f); a = d["le"] - d["le"].mean(); b = d["re"] - d["re"].mean()
    xc = np.correlate(b, a, "full")
    return float(np.max(xc) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", default="results/2026-06-28")
    ap.add_argument("--lambda-tag", default="lam1em3")
    ap.add_argument("--out", default="plots/paper/network/fig_collapse_lr.png")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    lam = args.lambda_tag

    def files(pref):
        return {g: _find(args.indir, f"{pref}_{g}_{lam}_*.h5") for g, _l in GAINS}
    stim = files("cpg_ablstim"); nat = files("cpg_ablgrad")
    x = np.arange(len(GAINS))

    plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10})
    fig = plt.figure(figsize=(13, 9))
    gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.27)

    def series(fdict, key):
        return [_mean(fdict[g[0]], key) if fdict[g[0]] else np.nan for g in GAINS]

    # (a) RG-E mean rate
    ax = fig.add_subplot(gs[0, 0])
    ax.plot(x, series(stim, "rge"), "o-", color="#1f77b4", ms=9, label="stim (CUT intact)")
    ax.plot(x, series(nat, "rge"), "s--", color="#d62728", ms=9, label="natural (CUT gated)")
    ax.set_xticks(x); ax.set_xticklabels([g[1] for g in GAINS])
    ax.set_ylabel("RG-E mean rate (Hz/neuron)"); ax.set_ylim(0, None)
    ax.set_title("(a) Extensor drive vs loading — the collapse")
    ax.legend(); ax.grid(alpha=0.2)

    # (b) RG-F mean rate
    ax = fig.add_subplot(gs[0, 1])
    ax.plot(x, series(stim, "rgf"), "o-", color="#1f77b4", ms=9, label="stim")
    ax.plot(x, series(nat, "rgf"), "s--", color="#d62728", ms=9, label="natural")
    ax.set_xticks(x); ax.set_xticklabels([g[1] for g in GAINS])
    ax.set_ylabel("RG-F mean rate (Hz/neuron)"); ax.set_ylim(0, None)
    ax.set_title("(b) Flexor drive vs loading — the takeover")
    ax.legend(); ax.grid(alpha=0.2)

    # (c) L/R coordination strength
    ax = fig.add_subplot(gs[1, 0])
    cs = [_lr_strength(stim[g[0]]) if stim[g[0]] else np.nan for g in GAINS]
    cn = [_lr_strength(nat[g[0]]) if nat[g[0]] else np.nan for g in GAINS]
    ax.plot(x, cs, "o-", color="#1f77b4", ms=9, label="stim")
    ax.plot(x, cn, "s--", color="#d62728", ms=9, label="natural")
    ax.set_xticks(x); ax.set_xticklabels([g[1] for g in GAINS])
    ax.set_ylabel("L/R RG-E coordination (peak x-corr)")
    ax.set_ylim(0.5, 1.02); ax.axhline(1.0, ls=":", color="grey", alpha=0.5)
    ax.set_title("(c) L/R commissural coordination — robust (stays ≈180°)")
    ax.legend(loc="lower left"); ax.grid(alpha=0.2)

    # (d) L RG-E vs R RG-E at natural air stepping
    ax = fig.add_subplot(gs[1, 1])
    fair = nat["air"]
    if fair:
        d = _load(fair); z = 4 * d["per"]; mm = d["t"] <= z
        ax.plot(d["t"][mm], d["le"][mm], color="#d62728", lw=1.3, label="L RG-E")
        ax.plot(d["t"][mm], d["re"][mm], color="#1f3b73", lw=1.3, ls="--", label="R RG-E")
        ax.set_xlim(0, z)
    ax.set_xlabel("time (ms)"); ax.set_ylabel("RG-E rate (Hz/neuron)")
    ax.set_title("(d) Natural air stepping: L/R still alternate (180°)\ndespite weak/irregular extensor")
    ax.legend(); ax.grid(alpha=0.2)

    fig.suptitle(
        "Circuit-level dissection — extensor collapse vs robust L/R commissural coordination\n"
        "(Phase B, λ=1·10⁻³, 520 ms, μ=3.5, CV=0.30)", fontsize=12, y=0.99)
    fig.savefig(args.out, dpi=190, bbox_inches="tight")
    plt.close(fig)
    print(f"[collapse_lr] saved {args.out}")


if __name__ == "__main__":
    main()
