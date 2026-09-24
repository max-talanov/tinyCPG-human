#!/usr/bin/env python3
"""
cpg_consolidate_force_stages.py
Force profiles at three stages of a run (beginning / middle / end), one row
per --consolidate condition, in the same layout/annotation style as the
paper's Figure 5-8 (scripts/cpg_force_stages.py) but comparing consolidation
configs on leg L at a single (fixed) operating point instead of comparing
locomotion modes at a fixed learning rate.

Each panel is annotated with the mean CUT->RG-E weight in the window and the
in-window corr(F_E,F_F), exactly like the paper figures.
"""
import argparse, os
import h5py, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _win(t, y, lo, hi):
    m = (t >= lo) & (t <= hi)
    return t[m], y[m], m


def _parse_run(s):
    # "label=path.h5"
    label, path = s.split("=", 1)
    return label, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True,
                     help="label=path.h5, repeatable -- one row per condition")
    ap.add_argument("--leg", default="L")
    ap.add_argument("--stage", action="append",
                     help="name:lo_ms:hi_ms, repeatable. Default: 60s-run windows "
                          "(beginning 2-7s, middle 27-32s, end 55-60s).")
    ap.add_argument("--out", default="plots/consolidate_force_stages.png")
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    runs = [_parse_run(s) for s in args.run]
    if args.stage:
        stages = []
        for s in args.stage:
            name, lo, hi = s.split(":")
            stages.append((name, (float(lo), float(hi))))
    else:
        stages = [("beginning", (2000, 7000)), ("middle", (27000, 32000)), ("end", (55000, 60000))]
    win_label = {"beginning": "early", "middle": "converging", "end": "converged"}

    nr, nc = len(runs), len(stages)
    fig, axes = plt.subplots(nr, nc, figsize=(3.9 * nc, 1.9 * nr), squeeze=False, sharey=True)

    for r, (label, path) in enumerate(runs):
        with h5py.File(path, "r") as h:
            t = np.asarray(h["times_ms"])
            fe = np.asarray(h[f"leg_{args.leg}/force_e"])
            ff = np.asarray(h[f"leg_{args.leg}/force_f"])
            wkey = f"leg_{args.leg}/weights/cut->rge_mean"
            w = np.asarray(h[wkey]) if wkey in h else None
        for c, (sname, (lo, hi)) in enumerate(stages):
            ax = axes[r][c]
            tt, ee, m = _win(t, fe, lo, hi)
            _, fftt, _ = _win(t, ff, lo, hi)
            ax.plot((tt - lo) / 1000.0, ee, color="#c1440e", lw=1.1, label="F-E")
            ax.plot((tt - lo) / 1000.0, fftt, color="#1f6feb", lw=1.1, ls="--", label="F-F")
            corr = (np.corrcoef(ee, fftt)[0, 1]
                    if np.std(ee) > 1e-9 and np.std(fftt) > 1e-9 else float("nan"))
            wtxt = ""
            if w is not None:
                v = w[m]; v = v[np.isfinite(v)]
                if v.size:
                    wtxt = f"CUT {np.mean(v):.0f} pA   "
            ax.set_title(f"{wtxt}r={corr:+.2f}", fontsize=10)
            ax.set_xlim(0, (hi - lo) / 1000.0)
            ax.grid(alpha=0.2); ax.tick_params(labelsize=9)
            if r == 0:
                ax.text(0.5, 1.30, f"{sname.upper()}  ({win_label.get(sname, sname)})", ha="center",
                        va="bottom", fontsize=13, fontweight="bold", transform=ax.transAxes)
            if c == 0:
                ax.set_ylabel(f"{label}\nForce (a.u.)", fontsize=10)
            if r == nr - 1:
                ax.set_xlabel("time in window (s)", fontsize=11)
    _L = [chr(97 + i) if i < 26 else chr(96 + i // 26) + chr(97 + i % 26) for i in range(nr * nc)]
    for i, ax in enumerate(axes.flat):
        ax.text(0.02, 0.95, f"({_L[i]})", transform=ax.transAxes, fontsize=10,
                fontweight="bold", va="top", ha="left")
    axes[-1][-1].legend(loc="lower right", fontsize=9, ncol=1, framealpha=0.9)
    fig.tight_layout(rect=(0.04, 0, 1, 0.96))
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[consolidate-force-stages] saved {args.out}")


if __name__ == "__main__":
    main()
