#!/usr/bin/env python3
"""
cpg_force_weights_stages.py
Force and plastic weights at three stages of one run (beginning / middle /
end), both legs and both muscle groups -- to see how plasticity reshapes the
force profiles. Same idea as scripts/cpg_force_stages.py (paper Fig 5-8), but
for a single run, with both legs and the weights shown explicitly.

Layout (4 rows x 3 stage columns):
  rows 1-2  force in the stage window, left / right leg: Force-E (extensor,
            ink) and Force-F (flexor, gray); stance shaded when the run logged
            `cut_on` (--cut-trigger force). Title: in-window corr(E, F) and the
            extensor / flexor peak-to-trough swing.
  rows 3-4  plastic weights at that stage, left / right leg: mean +/- 1 SD
            across synapses (full-weight snapshots inside the window, averaged
            per synapse) for BS->RG-E, CUT->RG-E, Ia->RG-E | BS->RG-F, Ia->RG-F.
            From the middle stage on, a dark tick marks the beginning-stage
            mean, so the change is read directly off the bar.

Default windows are fractions of the run: beginning 5-25 %, middle 40-60 %,
end 80-100 %. Override with --stage name:lo_ms:hi_ms (repeatable, 3 times).

Usage:
  python3 scripts/cpg_force_weights_stages.py --in results/debug.h5 --out plots/debug_stages.png
"""
import argparse

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Same tokens as scripts/cpg_force_weights_panel.py (dataviz reference palette).
INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
STANCE = "#efeee8"
PATHWAY = {"bs": ("BS (brainstem)", "#2a78d6"),
           "cut": ("CUT (cutaneous)", "#eb6834"),
           "ia": ("Ia (proprioceptive)", "#1baf7a")}
# (bar label, pathway colour key, full_weights key); None = gap between E and F groups
BARS = [("BS→E", "bs", "bs_to_rge"), ("CUT→E", "cut", "cut_to_rge"), ("Ia→E", "ia", "ia_to_rge"),
        None,
        ("BS→F", "bs", "bs_to_rgf"), ("Ia→F", "ia", "ia_to_rgf")]
DEFAULT_FRACS = [("beginning", 0.05, 0.25), ("middle", 0.40, 0.60), ("end", 0.80, 1.00)]


def style(ax, ygrid=True):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK_2, labelsize=8, length=3)
    if ygrid:
        ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def stance_spans(t, cut_on):
    on = np.asarray(cut_on) > 0.5
    if on.size == 0 or not on.any():
        return []
    edges = np.flatnonzero(np.diff(on.astype(int)))
    starts = ([0] if on[0] else []) + [i + 1 for i in edges if not on[i]]
    ends = [i + 1 for i in edges if on[i]] + ([len(on) - 1] if on[-1] else [])
    return [(t[s], t[e]) for s, e in zip(starts, ends)]


def stage_weights(wt, full, lo, hi):
    """Per-synapse mean over the snapshots inside [lo, hi]; nearest snapshot if none."""
    m = (wt >= lo) & (wt <= hi)
    idx = np.flatnonzero(m) if m.any() else [int(np.argmin(np.abs(wt - hi)))]
    w = np.nanmean(full[idx, :], axis=0)
    return float(np.nanmean(w)), float(np.nanstd(w))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stage", action="append", help="name:lo_ms:hi_ms, give exactly 3")
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    with h5py.File(args.inp, "r") as f:
        t_ms = f["times_ms"][()]
        wt_ms = f["weights_times_ms"][()]
        attrs = dict(f.attrs)
        legs = {}
        for side in ("L", "R"):
            g = f[f"leg_{side}"]
            legs[side] = {"fe": g["force_e"][()], "ff": g["force_f"][()],
                          "cut_on": g["cut_on"][()] if "cut_on" in g else np.array([]),
                          "full": {b[2]: g[f"full_weights/{b[2]}/w"][()] for b in BARS
                                   if b and f"full_weights/{b[2]}/w" in g}}

    sim_ms = float(attrs.get("sim_ms", t_ms[-1]))
    if args.stage:
        if len(args.stage) != 3:
            ap.error("--stage must be given exactly 3 times")
        stages = [(n, float(lo), float(hi)) for n, lo, hi in (s.split(":") for s in args.stage)]
    else:
        stages = [(n, a * sim_ms, b * sim_ms) for n, a, b in DEFAULT_FRACS]

    # Pathways that were not plastic in this run (e.g. BS->RG under --freeze-bs-rg) have
    # no recorded weights; drop their bars, keeping the E | F grouping.
    avail = set(legs["L"]["full"])
    bars_used = [b for b in BARS if b is None or b[2] in avail]
    while bars_used and bars_used[0] is None:
        bars_used.pop(0)
    # weights per leg / stage / bar: (mean, sd)
    W = {s: [{b[2]: stage_weights(wt_ms, legs[s]["full"][b[2]], lo, hi) for b in bars_used if b}
             for _, lo, hi in stages] for s in legs}

    fig, axes = plt.subplots(4, 3, figsize=(13, 10.5), facecolor=SURFACE,
                             gridspec_kw={"height_ratios": [1, 1, 1.05, 1.05], "hspace": 0.55, "wspace": 0.12})
    fmax = max(max(d["fe"].max(), d["ff"].max()) for d in legs.values()) * 1.08
    wtop = max(m + sd for s in W for st in W[s] for m, sd in st.values()) * 1.12
    xs, labels, pos = [], [], 0.0
    for b in bars_used:
        if b is None:
            pos += 0.6
            continue
        xs.append(pos); labels.append(b[0]); pos += 1.0

    for c, (sname, lo, hi) in enumerate(stages):
        for r, side in enumerate(("L", "R")):
            d = legs[side]
            ax = axes[r, c]
            style(ax)
            m = (t_ms >= lo) & (t_ms <= hi)
            tt = t_ms[m] / 1000.0
            for a, b in stance_spans(t_ms / 1000.0, d["cut_on"]):
                if b >= tt[0] and a <= tt[-1]:
                    ax.axvspan(max(a, tt[0]), min(b, tt[-1]), color=STANCE, linewidth=0, zorder=0)
            fe, ff = d["fe"][m], d["ff"][m]
            ax.plot(tt, fe, color=INK, linewidth=1.6, label="Extensor (Force-E)")
            ax.plot(tt, ff, color=MUTED, linewidth=1.6, label="Flexor (Force-F)")
            ax.set_xlim(tt[0], tt[-1]); ax.set_ylim(0, fmax)
            corr = np.corrcoef(fe, ff)[0, 1] if fe.std() > 1e-9 and ff.std() > 1e-9 else np.nan
            ax.set_title(f"{'Left' if side == 'L' else 'Right'} leg   r(E,F) = {corr:+.2f}   "
                         f"E {fe.min():.1f}–{fe.max():.1f}   F {ff.min():.1f}–{ff.max():.1f}",
                         fontsize=8.5, color=INK, loc="left")
            if c == 0:
                ax.set_ylabel("Force (a.u.)", fontsize=9, color=INK_2)
            if r == 1:
                ax.set_xlabel("Time (s)", fontsize=8.5, color=INK_2)

            ax = axes[2 + r, c]
            style(ax)
            bars = [b for b in bars_used if b]
            for x, b in zip(xs, bars):
                mean, sd = W[side][c][b[2]]
                colour = PATHWAY[b[1]][1]
                ax.bar(x, mean, width=0.72, color=colour, edgecolor=SURFACE, linewidth=2, zorder=2)
                ax.errorbar(x, mean, yerr=sd, color=INK_2, linewidth=1, capsize=3, zorder=3)
                m0 = W[side][0][b[2]][0]
                top = max(mean + sd, m0) if c > 0 else mean + sd
                ax.annotate(f"{mean:.1f}", (x, top), xytext=(0, 3), textcoords="offset points",
                            ha="center", fontsize=7.5, color=INK_2)
                if c > 0:
                    ax.plot([x - 0.36, x + 0.36], [m0, m0], color=INK, linewidth=1.8, zorder=4,
                            solid_capstyle="butt")
            ax.set_xticks(xs, labels, fontsize=8, color=INK_2)
            ax.set_ylim(0, wtop)
            ax.set_title(f"{'Left' if side == 'L' else 'Right'} leg — weights (mean ± 1 SD)",
                         fontsize=8.5, color=INK, loc="left")
            if c == 0:
                ax.set_ylabel("Weight (pA)", fontsize=9, color=INK_2)
            for grp, txt in (("rge", "onto extensor RG-E"), ("rgf", "onto flexor RG-F")):
                gx = [x for x, b in zip(xs, bars) if b[2].endswith(grp)]
                if gx:
                    ax.text((gx[0] + gx[-1]) / 2, -0.2, txt, transform=ax.get_xaxis_transform(),
                            ha="center", va="top", fontsize=7.5, color=MUTED)

        axes[0, c].text(0.0, 1.32, f"{sname.upper()}   {lo / 1000:.1f}–{hi / 1000:.1f} s",
                        transform=axes[0, c].transAxes, fontsize=11, fontweight="bold", color=INK)

    h, l = axes[0, 0].get_legend_handles_labels()
    if legs["L"]["cut_on"].size:
        h.append(plt.Rectangle((0, 0), 1, 1, color=STANCE)); l.append("Stance (CUT on)")
    shown = [k for k in PATHWAY if any(b and b[1] == k for b in bars_used)]
    h += [plt.Rectangle((0, 0), 1, 1, color=PATHWAY[k][1]) for k in shown]
    l += [PATHWAY[k][0] for k in shown]
    h.append(plt.Line2D([], [], color=INK, linewidth=1.8)); l.append("Beginning-stage mean")
    fig.legend(h, l, loc="upper center", ncol=len(h), frameon=False, fontsize=8.5,
               labelcolor=INK_2, bbox_to_anchor=(0.5, 0.965))

    trig = "force-triggered stance/swing" if legs["L"]["cut_on"].size else "timer-paced gait"
    title = args.title or f"{args.inp.split('/')[-1]} — {trig}: force and weights at three stages"
    sub = (f"species={attrs.get('species', '?')}  seed={attrs.get('seed', '?')}  "
           f"nest_rng_seed={attrs.get('nest_rng_seed', '?')}  sim={sim_ms / 1000:.0f} s")
    fig.text(0.06, 1.0, title, ha="left", va="bottom", fontsize=12, color=INK, fontweight="bold")
    fig.text(0.06, 0.995, sub, ha="left", va="top", fontsize=8.5, color=INK_2)
    fig.savefig(args.out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print(f"[stages] wrote {args.out}")


if __name__ == "__main__":
    main()
