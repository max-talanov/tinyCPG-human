#!/usr/bin/env python3
"""
cpg_force_weights_panel.py
One-figure overview of a cpg_2legs_fast.py run: muscle force and plastic
weights for both legs and both muscle groups.

Layout (3 rows x 2 columns, columns = left / right leg, shared time axis):
  row 1  Force-E (extensor) and Force-F (flexor); stance periods shaded when
         the run logged the ground-truth `cut_on` array (--cut-trigger force)
  row 2  extensor-side plastic weights: BS->RG-E, CUT->RG-E, Ia->RG-E
  row 3  flexor-side plastic weights:   BS->RG-F, Ia->RG-F
Weights are mean +/- 1 SD over the tracked synapses (the --max-weight-conns
subset); the mean is re-sampled every --weight-sample-ms, so it is a step
trace. Each pathway keeps one colour in both weight rows.

Usage:
  python3 scripts/cpg_force_weights_panel.py --in results/debug.h5 --out plots/debug_force_weights.png
"""
import argparse

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Reference palette (dataviz skill): categorical slots 1-3 validate all-pairs,
# light mode. Force uses ink/gray so no hue means two different things.
INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
STANCE = "#efeee8"
PATHWAY = {  # key -> (label, colour)
    "bs": ("BS (brainstem)", "#2a78d6"),
    "cut": ("CUT (cutaneous)", "#eb6834"),
    "ia": ("Ia (proprioceptive)", "#1baf7a"),
}
ROWS_W = {
    "E": [("bs", "bs->rge"), ("cut", "cut->rge"), ("ia", "ia->rge")],
    "F": [("bs", "bs->rgf"), ("ia", "ia->rgf")],
}


def stance_spans(t, cut_on):
    on = np.asarray(cut_on) > 0.5
    if on.size == 0 or not on.any():
        return []
    edges = np.flatnonzero(np.diff(on.astype(int)))
    starts = [0] if on[0] else []
    starts += [i + 1 for i in edges if not on[i]]
    ends = [i + 1 for i in edges if on[i]]
    if on[-1]:
        ends.append(len(on) - 1)
    return [(t[s], t[e]) for s, e in zip(starts, ends)]


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK_2, labelsize=8, length=3)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    with h5py.File(args.inp, "r") as f:
        t = f["times_ms"][()] / 1000.0
        attrs = dict(f.attrs)
        legs = {}
        for side in ("L", "R"):
            g = f[f"leg_{side}"]
            legs[side] = {
                "fe": g["force_e"][()], "ff": g["force_f"][()],
                "cut_on": g["cut_on"][()] if "cut_on" in g else np.array([]),
                "w": {k[:-5]: (g["weights"][k][()], g["weights"][k[:-5] + "_std"][()])
                      for k in g["weights"] if k.endswith("_mean")},
            }

    fig, axes = plt.subplots(3, 2, figsize=(12, 8.2), sharex=True, facecolor=SURFACE,
                             gridspec_kw={"height_ratios": [1.1, 1, 1], "hspace": 0.28, "wspace": 0.12})
    fmax = max(max(d["fe"].max(), d["ff"].max()) for d in legs.values()) * 1.08
    wmax = {r: max(np.nanmax(legs[s]["w"][k][0] + legs[s]["w"][k][1])
                   for s in legs for _, k in ROWS_W[r]) * 1.1 for r in ROWS_W}

    for col, side in enumerate(("L", "R")):
        d = legs[side]
        name = "Left leg" if side == "L" else "Right leg"

        ax = axes[0, col]
        style(ax)
        for a, b in stance_spans(t, d["cut_on"]):
            ax.axvspan(a, b, color=STANCE, linewidth=0, zorder=0)
        ax.plot(t, d["fe"], color=INK, linewidth=1.6, label="Extensor (Force-E)")
        ax.plot(t, d["ff"], color=MUTED, linewidth=1.6, label="Flexor (Force-F)")
        ax.set_ylim(0, fmax)
        r = np.corrcoef(d["fe"], d["ff"])[0, 1]
        ax.set_title(f"{name} — muscle force   corr(E, F) = {r:+.2f}", fontsize=10, color=INK, loc="left")
        if col == 0:
            ax.set_ylabel("Force (a.u.)", fontsize=9, color=INK_2)

        for row, grp in ((1, "E"), (2, "F")):
            ax = axes[row, col]
            style(ax)
            for pkey, wkey in ROWS_W[grp]:
                label, colour = PATHWAY[pkey]
                m, sd = d["w"][wkey]
                ax.fill_between(t, m - sd, m + sd, color=colour, alpha=0.14, linewidth=0, step="post")
                ax.step(t, m, where="post", color=colour, linewidth=2.0, label=label)
                ax.annotate(f"{m[-1]:.1f}", (t[-1], m[-1]), xytext=(4, 0), textcoords="offset points",
                            va="center", fontsize=8, color=INK_2, annotation_clip=False)
            ax.set_ylim(0, wmax[grp])
            muscle = "extensor half-centre (→ RG-E)" if grp == "E" else "flexor half-centre (→ RG-F)"
            ax.set_title(f"{name} — plastic weights onto {muscle}", fontsize=10, color=INK, loc="left")
            if col == 0:
                ax.set_ylabel("Weight (pA)\nmean ± 1 SD", fontsize=9, color=INK_2)
        axes[2, col].set_xlabel("Time (s)", fontsize=9, color=INK_2)

    h0, l0 = axes[0, 0].get_legend_handles_labels()
    if legs["L"]["cut_on"].size:
        h0.append(plt.Rectangle((0, 0), 1, 1, color=STANCE)); l0.append("Stance (CUT on)")
    hw = [plt.Line2D([], [], color=c, linewidth=2.0) for _, c in PATHWAY.values()]
    lw = [lab for lab, _ in PATHWAY.values()]
    fig.legend(h0 + hw, l0 + lw, loc="upper center", ncol=len(h0) + len(hw), frameon=False,
               fontsize=9, labelcolor=INK_2, bbox_to_anchor=(0.5, 0.975))

    trig = "force-triggered stance/swing" if legs["L"]["cut_on"].size else "timer-paced gait"
    title = args.title or f"{args.inp.split('/')[-1]} — {trig}"
    sub = (f"species={attrs.get('species', '?')}  seed={attrs.get('seed', '?')}  "
           f"nest_rng_seed={attrs.get('nest_rng_seed', '?')}  sim={attrs.get('sim_ms', 0) / 1000:.0f} s")
    fig.text(0.06, 1.035, title, ha="left", va="bottom", fontsize=12, color=INK, fontweight="bold")
    fig.text(0.06, 1.030, sub, ha="left", va="top", fontsize=8.5, color=INK_2)
    fig.savefig(args.out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print(f"[panel] wrote {args.out}")


if __name__ == "__main__":
    main()
