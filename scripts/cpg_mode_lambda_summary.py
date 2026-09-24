#!/usr/bin/env python3
"""
cpg_mode_lambda_summary.py
Extended comparison across the 5 locomotion modes x N STDP rates (lambda) of the
canonical sensory model. Auto-detects the lambda tags present (3 now, 5 after the
5x5 re-run). Produces three views of the same metrics:
  (a) metric heatmaps  -> <out>_heatmaps.png
  (b) line-plot trends -> <out>_trends.png
  (c) LaTeX + CSV table -> <out>_table.tex / .csv
Metrics per (mode, lambda) cell, last 20 s: corr(F_E,F_F), corr(RG-E,RG-F),
peak Force-E (95th pct), converged CUT->RG-E weight.
"""
import argparse, glob, os, re
import h5py, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

MODES = [
    ("slow walk\n6 cm/s",           "cpg_sensory_stdp_06cms"),
    ("medium / plantar\n13.5 cm/s", "cpg_sensory_stdp_13_5cms"),
    ("fast walk\n21 cm/s",          "cpg_sensory_stdp_21cms"),
    ("toe stepping",                "cpg_ablsens_toe"),
    ("air stepping",                "cpg_ablsens_air"),
]
LAM_VAL = {"lam1em2": 1e-2, "lam1em3": 1e-3, "lam1em4": 1e-4, "lam1em5": 1e-5, "lam1em6": 1e-6}
METRICS = [  # (key, label, cmap, vmin, vmax)
    ("corrF",  "corr($F_E,F_F$)",      "RdBu",     -1, 1),
    ("corrRG", "corr(RG-E,RG-F)",      "RdBu",     -1, 1),
    ("Fpk",    "peak Force-E (a.u.)",  "viridis",   0, 18),
    ("cut",    "converged CUT→RG-E (pA)", "magma",  0, 70),
]


def _find(indir, stem, lam):
    h = sorted(glob.glob(os.path.join(indir, f"{stem}_{lam}_*.h5")))
    return h[0] if h else None


def metrics(f):
    with h5py.File(f, "r") as h:
        t = np.asarray(h["times_ms"]); sim = float(h.attrs["sim_ms"]); m = t >= sim - 20000
        g = lambda k: np.asarray(h["leg_L/" + k])[m]
        fe, ff, rge, rgf = g("force_e"), g("force_f"), g("rge"), g("rgf")
        cc = lambda x, y: (float(np.corrcoef(x, y)[0, 1]) if x.std() > 1e-9 and y.std() > 1e-9 else np.nan)
        wg = h["leg_L/weights"]
        cutv = np.asarray(wg["cut->rge_mean"]); cutv = cutv[np.isfinite(cutv)]
        return dict(corrF=cc(fe, ff), corrRG=cc(rge, rgf),
                    Fpk=float(np.nanpercentile(fe, 95)),
                    cut=float(cutv[-1]) if cutv.size else np.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", required=True)
    ap.add_argument("--out", default="plots/paper/fig_mode_lambda_summary")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    # detect lambda tags actually present, order high->low rate
    lams = sorted({re.search(r"(lam1em\d)", os.path.basename(p)).group(1)
                   for p in glob.glob(os.path.join(args.indir, "cpg_sensory_stdp_*_lam1em*_*.h5"))},
                  key=lambda L: -LAM_VAL[L])
    if not lams:
        raise SystemExit(f"no cpg_sensory_stdp_*.h5 in {args.indir}")
    lam_lbl = [f"$10^{{{int(np.log10(LAM_VAL[L]))}}}$" for L in lams]
    nM, nL = len(MODES), len(lams)

    # gather metric matrices
    data = {mk: np.full((nM, nL), np.nan) for mk, *_ in METRICS}
    for r, (mlabel, stem) in enumerate(MODES):
        for c, lam in enumerate(lams):
            f = _find(args.indir, stem, lam)
            if f is None:
                continue
            mt = metrics(f)
            for mk, *_ in METRICS:
                data[mk][r, c] = mt[mk]

    mode_short = [m[0].split("\n")[0] for m in MODES]

    # (a) heatmaps
    fig, axes = plt.subplots(2, 2, figsize=(4.6 * 2, 3.6 * 2))
    for ax, (mk, mlab, cmap, vmin, vmax) in zip(axes.flat, METRICS):
        M = data[mk]
        im = ax.imshow(M, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
        ax.set_xticks(range(nL)); ax.set_xticklabels([f"λ={l}" for l in lam_lbl], fontsize=9)
        ax.set_yticks(range(nM)); ax.set_yticklabels(mode_short, fontsize=9)
        ax.set_title(mlab, fontsize=12, fontweight="bold")
        for i in range(nM):
            for j in range(nL):
                if np.isfinite(M[i, j]):
                    val = f"{M[i,j]:.2f}" if mk.startswith("corr") else f"{M[i,j]:.0f}"
                    # white text on the diverging (corr) panels and on dark
                    # viridis/magma cells; black otherwise.
                    tcol = "white" if (cmap == "RdBu" or (cmap in ("viridis", "magma") and M[i, j] < vmax * 0.55)) else "black"
                    ax.text(j, i, val, ha="center", va="center", fontsize=9, color=tcol)
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(args.out + "_heatmaps.png", dpi=170, bbox_inches="tight"); plt.close(fig)

    # (b) line-plot trends: metric vs mode, one line per lambda
    fig, axes = plt.subplots(2, 2, figsize=(4.8 * 2, 3.4 * 2))
    x = np.arange(nM)
    colors = plt.cm.plasma(np.linspace(0.1, 0.85, nL))
    for ax, (mk, mlab, *_r) in zip(axes.flat, METRICS):
        for c, (lam, col) in enumerate(zip(lams, colors)):
            ax.plot(x, data[mk][:, c], "o-", color=col, lw=1.8, label=f"λ={lam_lbl[c]}")
        ax.set_xticks(x); ax.set_xticklabels(mode_short, fontsize=8, rotation=20, ha="right")
        ax.set_ylabel(mlab, fontsize=11); ax.grid(alpha=0.25)
    axes[0][0].legend(fontsize=8, ncol=2, title="STDP rate")
    fig.suptitle("Metric trends across locomotion modes, one line per STDP rate λ",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(args.out + "_trends.png", dpi=170, bbox_inches="tight"); plt.close(fig)

    # (c) table (CSV + LaTeX)
    with open(args.out + "_table.csv", "w") as fh:
        fh.write("mode,lambda,corr_FE_FF,corr_RGE_RGF,peak_force_e,cut_rge_pA\n")
        for r, (ml, _s) in enumerate(MODES):
            for c, lam in enumerate(lams):
                fh.write(f"{ml.split(chr(10))[0]},{LAM_VAL[lam]:.0e},{data['corrF'][r,c]:.3f},"
                         f"{data['corrRG'][r,c]:.3f},{data['Fpk'][r,c]:.2f},{data['cut'][r,c]:.1f}\n")
    L = [r"\begin{table}[t]", r"  \centering", r"  \footnotesize",
         r"  \caption{Comparison across the 5 locomotion modes $\times$ "
         + f"{nL}" + r" STDP rates $\lambda$ (canonical sensory model, last 20\,s, leg L).}",
         r"  \label{tab:mode_lambda}", r"  \begin{tabular}{ll rrrr}", r"    \toprule",
         r"    Mode & $\lambda$ & corr$(F_E,F_F)$ & corr(RG) & peak $F_E$ & CUT$\to$RG-E \\",
         r"    \midrule"]
    for r, (ml, _s) in enumerate(MODES):
        for c, lam in enumerate(lams):
            L.append(f"    {ml.split(chr(10))[0]} & {lam_lbl[c]} & ${data['corrF'][r,c]:.2f}$ & "
                     f"${data['corrRG'][r,c]:.2f}$ & ${data['Fpk'][r,c]:.1f}$ & ${data['cut'][r,c]:.0f}$ \\\\")
        L.append(r"    \addlinespace[2pt]")
    L += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    open(args.out + "_table.tex", "w").write("\n".join(L) + "\n")
    print(f"[summary] {nM} modes x {nL} lambda -> {args.out}_heatmaps.png / _trends.png / _table.{{tex,csv}}")


if __name__ == "__main__":
    main()
