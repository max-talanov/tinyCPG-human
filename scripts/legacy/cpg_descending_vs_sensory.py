#!/usr/bin/env python3
"""
cpg_descending_vs_sensory.py  ->  fig_descending_vs_sensory.png  (paper Fig., sec 3.7)

Four-panel contrast of where the plasticity is sited, from the canonical set:
  (a) counter-phase corr(F_E,F_F) vs speed: descending vs sensory arm (lambda 1e-3)
  (b) counter-phase vs loading for the three arms (stim / sensory / natural)
  (c) extensor RG-E mean rate vs loading (the mechanism)
  (d) force-peak balance (F_E vs F_F) vs loading, sensory arm

All metrics are recomputed from the HDF5 files (last 20 s window), so the
figure and the Results tables/prose come from one source.

Usage:
  python3 cpg_descending_vs_sensory.py --indir results/2026-07-01 \
      --out plots/paper/fig_descending_vs_sensory.png
"""
import argparse, glob, os
import numpy as np, h5py
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

WIN_MS = 20000.0
SPEEDS = [("06cms", "6"), ("13_5cms", "13.5"), ("21cms", "21")]
LOADS  = [("baseline", "baseline\n(G=1.0)"), ("toe", "toe step\n(G=0.5)"), ("air", "air step\n(G=0.1)")]
C_DESC, C_SENS, C_STIM, C_NAT = "#1f77b4", "#2ca02c", "#1f77b4", "#d62728"


def _find(indir, pat):
    h = sorted(glob.glob(os.path.join(indir, pat)))
    return h[0] if h else None


def _win(h):
    t = np.asarray(h["times_ms"]); sim = float(h.attrs.get("sim_ms", 120000.0))
    return t >= max(0.0, sim - WIN_MS)


def _corr(f):
    if not f:
        return np.nan
    with h5py.File(f, "r") as h:
        m = _win(h)
        a = np.asarray(h["leg_L/force_e"])[m]; b = np.asarray(h["leg_L/force_f"])[m]
    a = a - a.mean(); b = b - b.mean()
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / d) if d > 1e-12 else np.nan


def _rate(f, key):
    if not f:
        return np.nan
    with h5py.File(f, "r") as h:
        m = _win(h)
        return float(np.mean(np.asarray(h["leg_L/" + key])[m]))


def _peak(f, key):
    if not f:
        return np.nan
    with h5py.File(f, "r") as h:
        m = _win(h)
        return float(np.nanpercentile(np.asarray(h["leg_L/" + key])[m], 95))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", default="results/2026-07-01")
    ap.add_argument("--out", default="plots/paper/fig_descending_vs_sensory.png")
    ap.add_argument("--lam", default="lam1em3")
    a = ap.parse_args()
    D, lam = a.indir, a.lam

    # (a) corr vs speed
    desc = [_corr(_find(D, f"cpg_speed_stdp_{s}_{lam}_*.h5")) for s, _ in SPEEDS]
    sens = [_corr(_find(D, f"cpg_sensory_stdp_{s}_{lam}_*.h5")) for s, _ in SPEEDS]
    # (b) corr vs loading, three arms
    arms = {"stim": "cpg_ablstim", "sensory": "cpg_ablsens", "natural": "cpg_ablgrad"}
    corrL = {k: [_corr(_find(D, f"{p}_{t}_{lam}_*.h5")) for t, _ in LOADS] for k, p in arms.items()}
    # (c) RG-E rate vs loading
    rgeL = {k: [_rate(_find(D, f"{p}_{t}_{lam}_*.h5"), "rge") for t, _ in LOADS] for k, p in arms.items()}
    # (d) sensory-arm force balance
    fe = [_peak(_find(D, f"cpg_ablsens_{t}_{lam}_*.h5"), "force_e") for t, _ in LOADS]
    ff = [_peak(_find(D, f"cpg_ablsens_{t}_{lam}_*.h5"), "force_f") for t, _ in LOADS]

    plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10})
    fig, ax = plt.subplots(2, 2, figsize=(12, 9))
    xs = np.arange(len(SPEEDS)); xl = np.arange(len(LOADS))

    # (a)
    ax[0, 0].plot(xs, desc, "o-", color=C_DESC, ms=9, label="descending (BS→RG plastic)")
    ax[0, 0].plot(xs, sens, "s-", color=C_SENS, ms=9, label="sensory (Ia→RG plastic)")
    ax[0, 0].axhline(-0.8, ls=":", color="grey", alpha=0.6)
    ax[0, 0].set_xticks(xs); ax[0, 0].set_xticklabels([l for _, l in SPEEDS])
    ax[0, 0].set_xlabel("speed (cm/s)"); ax[0, 0].set_ylabel("corr$(F_E,F_F)$")
    ax[0, 0].set_ylim(-1.05, -0.4); ax[0, 0].grid(alpha=0.2)
    ax[0, 0].legend(loc="lower left", fontsize=8)
    ax[0, 0].set_title("(a) Relocation is cost-free at normal loading")

    # (b)
    for k, c, mk, lb in [("stim", C_STIM, "o-", "epidural stim (CUT intact)"),
                         ("sensory", C_SENS, "s-", "sensory (Ia→RG plastic)"),
                         ("natural", C_NAT, "^--", "natural (CUT+Ia gated)")]:
        ax[0, 1].plot(xl, corrL[k], mk, color=c, ms=9, label=lb)
    ax[0, 1].axhline(-0.8, ls=":", color="grey", alpha=0.6)
    ax[0, 1].set_xticks(xl); ax[0, 1].set_xticklabels([l for _, l in LOADS], fontsize=8)
    ax[0, 1].set_ylabel("corr$(F_E,F_F)$"); ax[0, 1].set_ylim(-1.05, 0.05); ax[0, 1].grid(alpha=0.2)
    ax[0, 1].legend(loc="lower left", fontsize=8)
    ax[0, 1].set_title("(b) Under unloading: toe-rescue, air-limit")

    # (c)
    for k, c, mk in [("stim", C_STIM, "o-"), ("sensory", C_SENS, "s-"), ("natural", C_NAT, "^--")]:
        ax[1, 0].plot(xl, rgeL[k], mk, color=c, ms=9, label=k)
    ax[1, 0].set_xticks(xl); ax[1, 0].set_xticklabels([l for _, l in LOADS], fontsize=8)
    ax[1, 0].set_ylabel("RG-E mean rate (Hz)"); ax[1, 0].grid(alpha=0.2)
    ax[1, 0].legend(loc="upper right", fontsize=8)
    ax[1, 0].set_title("(c) Mechanism: extensor drive vs loading")

    # (d)
    w = 0.36
    ax[1, 1].bar(xl - w / 2, fe, w, color="#1f77b4", label="peak $F_E$")
    ax[1, 1].bar(xl + w / 2, ff, w, color="#ff7f0e", label="peak $F_F$")
    ax[1, 1].set_xticks(xl); ax[1, 1].set_xticklabels([l for _, l in LOADS], fontsize=8)
    ax[1, 1].set_ylabel("force peak (a.u.)"); ax[1, 1].grid(alpha=0.2, axis="y")
    ax[1, 1].legend(loc="lower left", fontsize=8)
    ax[1, 1].set_title("(d) Sensory arm keeps E/F force balanced")

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    fig.savefig(a.out, dpi=170, bbox_inches="tight")
    print(f"[desc_vs_sens] saved {a.out}")
    print(f"  (a) desc={np.round(desc,3)}  sens={np.round(sens,3)}")
    for k in arms:
        print(f"  (b) {k:8s} corr={np.round(corrL[k],3)}  (c) RG-E={np.round(rgeL[k],0)}")
    print(f"  (d) sensory F_E={np.round(fe,1)}  F_F={np.round(ff,1)}")


if __name__ == "__main__":
    main()
