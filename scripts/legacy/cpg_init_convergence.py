#!/usr/bin/env python3
"""
cpg_init_convergence.py
Initialisation-robustness of STDP self-organisation: the 10-point mu:CV sweep
(run.sh) shows that the plastic CUT->RG-E weight converges to the same
attractor regardless of the initial weight, spanning four orders of magnitude.
Bio-plausible defaults, medium walk (520 ms), lambda=1e-3, 120 s.
"""
import argparse, glob, os, re
import h5py, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", required=True)
    ap.add_argument("--out", default="paper/figures/fig_init_convergence.png")
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    runs = []
    for f in sorted(glob.glob(os.path.join(args.indir, "cpg_bursting_paced_120s_idx*.h5"))):
        with h5py.File(f, "r") as h:
            t = np.asarray(h["times_ms"]) / 1000.0
            cut = np.asarray(h["leg_L/weights/cut->rge_mean"])
            mu = float(h.attrs["winit_mu"])
            cv = float(re.search(r"cv(\d+\.\d+)", f).group(1))
            sim = float(h.attrs["sim_ms"])
            m = (t >= (sim / 1000.0 - 20.0))
            conv = float(np.nanmean(cut[m]))
        runs.append(dict(mu=mu, cv=cv, t=t, cut=cut, conv=conv))
    runs.sort(key=lambda r: r["mu"])
    mus = np.array([r["mu"] for r in runs])
    conv = np.array([r["conv"] for r in runs])
    colors = cm.viridis(np.linspace(0, 0.92, len(runs)))

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13, 4.6),
                                   gridspec_kw={"width_ratios": [1.7, 1]})

    # (a) CUT->RG-E trajectories, one per init
    for r, c in zip(runs, colors):
        axA.plot(r["t"], r["cut"], color=c, lw=1.3,
                 label=f"μ={r['mu']:.1f}, CV={r['cv']:.2f}")
    axA.axhline(conv.mean(), color="k", ls="--", lw=0.8, alpha=0.6)
    axA.set_xlabel("time (s)"); axA.set_ylabel("mean CUT→RG-E weight (pA)")
    axA.set_title("(a) STDP convergence from 10 initialisations\n"
                  "(μ, CV spanning 4 orders of magnitude in initial weight)")
    axA.set_xlim(0, 120); axA.grid(alpha=0.2)
    axA.legend(fontsize=6.5, ncol=2, loc="lower right", framealpha=0.9)

    # (b) converged weight vs init mu -> flat = attractor independent of init
    axB.plot(mus, conv, "o-", color="#c1440e", lw=1.4, ms=7)
    axB.axhline(conv.mean(), color="k", ls="--", lw=0.8)
    axB.fill_between([mus.min() - 1, mus.max() + 1],
                     conv.mean() - conv.std(), conv.mean() + conv.std(),
                     color="0.8", alpha=0.5, zorder=0)
    axB.set_xlabel("initial-weight mean μ (pA)")
    axB.set_ylabel("converged CUT→RG-E (pA)")
    axB.set_title(f"(b) Attractor is init-independent\n"
                  f"{conv.mean():.1f} ± {conv.std():.1f} pA "
                  f"(CV {100*conv.std()/conv.mean():.1f}%)")
    axB.set_ylim(conv.mean() - 5, conv.mean() + 5)
    axB.set_xlim(mus.min() - 1, mus.max() + 1); axB.grid(alpha=0.2)

    fig.tight_layout()
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[init-convergence] saved {args.out}  "
          f"(converged {conv.mean():.1f}±{conv.std():.1f} pA, n={len(runs)})")


if __name__ == "__main__":
    main()
