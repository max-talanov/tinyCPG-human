#!/usr/bin/env python3
"""
cpg_connectivity_figure.py
Connectivity-statistics figure from a --dump-connectivity HDF5:
distribution of synaptic WEIGHTS and DELAYS along every projection.

  (a) weight histograms for the plastic projections (lognormal init)
  (b) static synaptic weight per projection (signed bar — E/I structure)
  (c) conduction delay per projection (mean ± jitter), sorted

Also writes a CSV table (n, weight mean±std, delay mean±std) for the
Methods/Supplementary.

Usage:
  python3 cpg_connectivity_figure.py --in results/connectivity/conn_dump.h5 \\
      --out plots/paper/fig_connectivity.png
"""

import argparse
import os

import h5py
import matplotlib.pyplot as plt
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", default="plots/paper/fig_connectivity.png")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    rows = []
    with h5py.File(args.inp, "r") as h:
        for k in h:
            g = h[k]
            rows.append(dict(name=g.attrs["projection"], n=int(g.attrs["n"]),
                             w=np.asarray(g["weight"]), d=np.asarray(g["delay"]),
                             wm=float(g.attrs["w_mean"]), ws=float(g.attrs["w_std"]),
                             dm=float(g.attrs["d_mean"]), ds=float(g.attrs["d_std"])))
    rows.sort(key=lambda r: r["dm"])
    # STDP/plastic projections identified by name (all projections now carry a weight
    # distribution since static synapses get lognormal heterogeneity; panel (a) shows
    # only the *learned* projections).
    def _is_plastic(nm):
        return ("plastic" in nm) or nm.startswith("BS->") or nm in ("Ia-E->RG-E", "Ia-F->RG-F")
    plastic = [r for r in rows if _is_plastic(r["name"])]

    plt.rcParams.update({"font.size": 12, "axes.titlesize": 13, "axes.labelsize": 12})
    fig = plt.figure(figsize=(15, 13))
    gs = fig.add_gridspec(3, 1, height_ratios=[0.9, 1.25, 1.25], hspace=0.45)

    # (a) weight histograms for plastic projections
    ga = gs[0].subgridspec(1, max(1, len(plastic)), wspace=0.3)
    for i, r in enumerate(plastic):
        ax = fig.add_subplot(ga[0, i])
        ax.hist(r["w"], bins=40, color="#4477aa", alpha=0.85)
        ax.set_title(f"{r['name']}\n(n={r['n']}, μ={r['wm']:.1f}, σ={r['ws']:.1f} pA)", fontsize=11)
        ax.set_xlabel("weight (pA)");
        if i == 0:
            ax.set_ylabel("count")
            ax.text(-0.28, 1.12, "(a)", transform=ax.transAxes, fontsize=15,
                    fontweight="bold", va="bottom", ha="left")
        ax.grid(alpha=0.2)

    # (b) weight per projection — signed bar with the per-connection spread (s.d.)
    ax = fig.add_subplot(gs[1])
    sr = sorted(rows, key=lambda r: r["wm"])
    names = [r["name"] for r in sr]; wm = [r["wm"] for r in sr]; ws = [r["ws"] for r in sr]
    colors = ["#cc3311" if w < 0 else "#228833" for w in wm]
    y = np.arange(len(sr))
    ax.barh(y, wm, xerr=ws, color=colors, alpha=0.85,
            error_kw=dict(ecolor="#555", elinewidth=0.8, capsize=2))
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=10)
    ax.axvline(0, color="black", lw=0.6)
    ax.set_xlabel("synaptic weight (pA): mean ± per-connection s.d.  —  green = excitatory, red = inhibitory")
    ax.set_title("(b) Weight by projection — all projections heterogeneous (lognormal CV≈0.5); "
                 "the 6:1 InF→RG-E (−48) vs InE→RG-F (−8) Zhang asymmetry preserved")
    ax.grid(alpha=0.2, axis="x")

    # (c) delay per projection (mean ± std), sorted by delay
    ax = fig.add_subplot(gs[2])
    dm = [r["dm"] for r in rows]; ds = [r["ds"] for r in rows]
    nm = [r["name"] for r in rows]
    y = np.arange(len(rows))
    ax.errorbar(dm, y, xerr=ds, fmt="o", color="#9933aa", capsize=3, markersize=6)
    ax.set_yticks(y); ax.set_yticklabels(nm, fontsize=10)
    ax.set_xlabel("conduction + synaptic delay (ms; mean ± across-connection s.d.)")
    ax.set_title("(c) Delay by projection (length_velocity rat preset + 0.2 ms jitter)")
    ax.grid(alpha=0.2, axis="x")

    fig.savefig(args.out, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(f"[connectivity] saved {args.out}")

    # CSV table
    csv = os.path.splitext(args.out)[0] + "_table.csv"
    with open(csv, "w") as fh:
        fh.write("projection,n_connections,weight_mean_pA,weight_std_pA,delay_mean_ms,delay_std_ms\n")
        for r in sorted(rows, key=lambda r: r["name"]):
            fh.write(f"{r['name']},{r['n']},{r['wm']:.3f},{r['ws']:.3f},{r['dm']:.3f},{r['ds']:.3f}\n")
    print(f"[connectivity] table {csv}")


if __name__ == "__main__":
    main()
