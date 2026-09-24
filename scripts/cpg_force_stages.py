#!/usr/bin/env python3
"""
cpg_force_stages.py
Force profiles at three stages of STDP learning (beginning / middle / end),
one row per locomotion mode (canonical sensory model). Shows how the
counter-phase force pattern sharpens as the plastic weights converge over the
120 s run. Each panel is annotated with the mean CUT->RG-E weight in the window
and the in-window corr(F_E,F_F).

Modes: slow / medium=plantar=baseline / fast walk, toe / air stepping.
"""
import argparse, glob, os
import h5py, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

# (row label, filename glob stem, [(weight-key, short-name), ...] to annotate)
# The five locomotion modes of the canonical sensory model.
MODES = [
    ("slow walk\n6 cm/s",            "cpg_sensory_stdp_06cms",   [("cut->rge_mean", "CUT")]),
    ("medium / plantar\n13.5 cm/s",  "cpg_sensory_stdp_13_5cms", [("cut->rge_mean", "CUT")]),
    ("fast walk\n21 cm/s",           "cpg_sensory_stdp_21cms",   [("cut->rge_mean", "CUT")]),
    ("toe stepping\npartial unload", "cpg_ablsens_toe",          [("cut->rge_mean", "CUT")]),
    ("air stepping\nfull unload",    "cpg_ablsens_air",          [("cut->rge_mean", "CUT")]),
]
STAGES = [("beginning", (4000, 9000)), ("middle", (40000, 45000)), ("end", (115000, 120000))]
WIN_LABEL = {"beginning": "early learning", "middle": "converging", "end": "converged"}


def _find(indir, stem, lam):
    h = sorted(glob.glob(os.path.join(indir, f"{stem}_{lam}_*.h5")))
    return h[0] if h else None


def _win(t, y, lo, hi):
    m = (t >= lo) & (t <= hi)
    return t[m], y[m], m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", required=True)
    ap.add_argument("--lambda-tag", default="lam1em4",
                    help="Use a slow-enough rate that convergence spans the 120 s run so the "
                         "three stages are distinct (at lam1em3 CUT->RG-E converges by ~8 s).")
    ap.add_argument("--out", default="plots/paper/fig_force_stages.png")
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    nr, nc = len(MODES), len(STAGES)
    fig, axes = plt.subplots(nr, nc, figsize=(3.9 * nc, 1.6 * nr), squeeze=False, sharey=True)

    for r, (mlabel, stem, wkeys) in enumerate(MODES):
        f = _find(args.indir, stem, args.lambda_tag)
        if f is None:
            for c in range(nc):
                axes[r][c].text(0.5, 0.5, f"missing:\n{stem}", ha="center", va="center",
                                fontsize=8, transform=axes[r][c].transAxes)
            continue
        with h5py.File(f, "r") as h:
            t = np.asarray(h["times_ms"])
            fe = np.asarray(h["leg_L/force_e"]); ff = np.asarray(h["leg_L/force_f"])
            ws = {kn[0]: np.asarray(h[f"leg_L/weights/{kn[0]}"])
                  for kn in wkeys if f"leg_L/weights/{kn[0]}" in h}
        for c, (sname, (lo, hi)) in enumerate(STAGES):
            ax = axes[r][c]
            tt, ee, m = _win(t, fe, lo, hi)
            _, fftt, _ = _win(t, ff, lo, hi)
            ax.plot((tt - lo) / 1000.0, ee, color="#c1440e", lw=1.1, label="F-E")
            ax.plot((tt - lo) / 1000.0, fftt, color="#1f6feb", lw=1.1, ls="--", label="F-F")
            corr = (np.corrcoef(ee, fftt)[0, 1]
                    if np.std(ee) > 1e-9 and np.std(fftt) > 1e-9 else float("nan"))
            # mean of each annotated learned weight over the window (nan-safe)
            parts = []
            for key, name in wkeys:
                if key in ws:
                    v = ws[key][m]; v = v[np.isfinite(v)]
                    if v.size:
                        parts.append(f"{name} {np.mean(v):.0f}")
            wtxt = "  ".join(parts)
            ax.set_title(f"{wtxt} pA   r={corr:+.2f}", fontsize=10)
            ax.set_xlim(0, (hi - lo) / 1000.0)
            ax.grid(alpha=0.2); ax.tick_params(labelsize=9)
            if r == 0:
                ax.text(0.5, 1.30, f"{sname.upper()}  ({WIN_LABEL[sname]})", ha="center",
                        va="bottom", fontsize=14, fontweight="bold", transform=ax.transAxes)
            if c == 0:
                ax.set_ylabel(f"{mlabel}\nForce (a.u.)", fontsize=11)
            if r == nr - 1:
                ax.set_xlabel("time in window (s)", fontsize=12)
    _L = [chr(97 + i) if i < 26 else chr(96 + i // 26) + chr(97 + i % 26) for i in range(nr * nc)]
    for i, ax in enumerate(axes.flat):
        ax.text(0.02, 0.95, f"({_L[i]})", transform=ax.transAxes, fontsize=11,
                fontweight="bold", va="top", ha="left")
    axes[-1][-1].legend(loc="lower right", fontsize=9, ncol=1, framealpha=0.9)
    lamtxt = args.lambda_tag.replace("lam1em", "1·10⁻")
    fig.tight_layout(rect=(0.04, 0, 1, 0.975))
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[force-stages] saved {args.out}")


if __name__ == "__main__":
    main()
