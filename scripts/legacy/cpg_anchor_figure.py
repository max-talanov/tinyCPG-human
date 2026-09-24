#!/usr/bin/env python3
"""
cpg_anchor_figure.py  ->  fig2_main.png  (paper Fig., sec 3.2)

Anchor overview of self-organisation + long-term stability, from a single
representative production run (descending arm, medium walk, baseline STDP
rate -- the arm that carries the BS->RG plastic trajectories).

Panels:
  top-left    Force-E/F leg L, last 5 s zoom (clean counter-phase)
  top-right   RG-E/F population rate, same window
  centre-left Force leg L, full run (no drift)
  centre-right Force leg R, full run (180 deg offset)
  bottom      STDP weight trajectories: CUT->RG-E, BS->RG-E, BS->RG-F

Usage:
  python3 cpg_anchor_figure.py --indir results/2026-07-01 --out plots/paper/fig2_main.png
"""
import argparse, glob, os
import numpy as np, h5py
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

CE, CF = "#1f77b4", "#ff7f0e"


def _find(indir, pat):
    h = sorted(glob.glob(os.path.join(indir, pat)))
    if not h:
        raise SystemExit(f"[anchor] no file matches {pat} in {indir}")
    return h[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", default="results/2026-07-01")
    ap.add_argument("--anchor", default="cpg_speed_stdp_13_5cms_lam1em3_*.h5")
    ap.add_argument("--out", default="plots/paper/fig2_main.png")
    a = ap.parse_args()
    f = _find(a.indir, a.anchor)

    with h5py.File(f, "r") as h:
        t = np.asarray(h["times_ms"]); sim = float(h.attrs.get("sim_ms", 120000.0))
        feL = np.asarray(h["leg_L/force_e"]); ffL = np.asarray(h["leg_L/force_f"])
        feR = np.asarray(h["leg_R/force_e"]); ffR = np.asarray(h["leg_R/force_f"])
        rge = np.asarray(h["leg_L/rge"]); rgf = np.asarray(h["leg_L/rgf"])
        wg = h["leg_L/weights"]
        W = {k: np.asarray(wg[f"{k}_mean"]) for k in ("cut->rge", "bs->rge", "bs->rgf") if f"{k}_mean" in wg}
        wt_raw = np.asarray(h["weights_times_ms"]) / 1000.0

    ts = t / 1000.0
    # weight-mean series are sampled either at the weight-snapshot times or at
    # the main resolution; pick whichever axis matches their length.
    def _waxis(w):
        if wt_raw.shape[0] == w.shape[0]:
            return wt_raw
        return np.linspace(0.0, sim / 1000.0, w.shape[0])
    z = t >= (sim - 5000.0)

    fig = plt.figure(figsize=(13, 11))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 1.0], hspace=0.38, wspace=0.2)

    # top-left: force zoom
    ax = fig.add_subplot(gs[0, 0])
    ax.plot(ts[z], feL[z], color=CE, lw=1.3, label="Force-E")
    ax.plot(ts[z], ffL[z], color=CF, lw=1.1, ls="--", label="Force-F")
    ax.set_title("Force leg L (last 5 s) — counter-phase"); ax.set_xlabel("time (s)")
    ax.set_ylabel("force (a.u.)"); ax.grid(alpha=0.2); ax.legend(fontsize=8, ncol=2)

    # top-right: RG rate zoom
    ax = fig.add_subplot(gs[0, 1])
    ax.plot(ts[z], rge[z], color=CE, lw=1.2, label="RG-E")
    ax.plot(ts[z], rgf[z], color=CF, lw=1.0, ls="--", label="RG-F")
    ax.set_title("RG-E/F population rate (last 5 s)"); ax.set_xlabel("time (s)")
    ax.set_ylabel("rate (Hz)"); ax.grid(alpha=0.2); ax.legend(fontsize=8, ncol=2)

    # centre-left / right: full-run force, leg L and R
    for col, (fe, ff, lab) in enumerate([(feL, ffL, "L"), (feR, ffR, "R")]):
        ax = fig.add_subplot(gs[1, col])
        ax.plot(ts, fe, color=CE, lw=0.5)
        ax.plot(ts, ff, color=CF, lw=0.4, ls="--", alpha=0.8)
        ax.set_title(f"Force leg {lab} — full {sim/1000:.0f} s (no drift)")
        ax.set_xlabel("time (s)"); ax.set_ylabel("force (a.u.)"); ax.grid(alpha=0.2)

    # bottom: weight trajectories (span both columns)
    ax = fig.add_subplot(gs[2, :])
    cols = {"cut->rge": "#d62728", "bs->rge": "#2ca02c", "bs->rgf": "#9467bd"}
    labs = {"cut->rge": "CUT→RG-E", "bs->rge": "BS→RG-E", "bs->rgf": "BS→RG-F"}
    for k, w in W.items():
        ax.plot(_waxis(w), w, color=cols[k], lw=1.8, label=f"{labs[k]} (→{w[-1]:.0f} pA)")
    ax.set_title("STDP weight self-organisation — plateau within ~5–10 s")
    ax.set_xlabel("time (s)"); ax.set_ylabel("mean weight (pA)")
    ax.grid(alpha=0.2); ax.legend(fontsize=9, loc="center right")

    fig.suptitle("Self-organisation and long-term stability of paced locomotion "
                 "(descending arm, medium walk, λ=1·10⁻³, production N)", fontsize=13, y=0.995)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    fig.savefig(a.out, dpi=160, bbox_inches="tight")
    print(f"[anchor] saved {a.out}  (source {os.path.basename(f)})")
    print(f"  converged: " + ", ".join(f"{labs[k]}={w[-1]:.1f}" for k, w in W.items()))
    lastw = t >= (sim - 20000.0)
    c = np.corrcoef(feL[lastw], ffL[lastw])[0, 1]
    print(f"  corr(F_E,F_F) last 20 s = {c:.3f}; F_E peak = {np.nanpercentile(feL[lastw],95):.1f}")


if __name__ == "__main__":
    main()
