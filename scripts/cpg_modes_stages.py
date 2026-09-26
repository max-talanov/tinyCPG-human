#!/usr/bin/env python3
"""
cpg_modes_stages.py
Force and plastic weights at three stages (beginning / middle / end) for the
five locomotion modes of one species -- the overview counterpart of
scripts/cpg_force_weights_stages.py (one run, both legs in detail) and of the
paper's scripts/cpg_force_stages.py.

Layout: one row per mode (slow, medium, fast, toe, air), 4 columns:
  cols 1-3  force in the stage window, left leg: Force-E (extensor, ink) and
            Force-F (flexor, gray). Title: in-window r(E,F) for left and right
            leg.
  col 4     plastic weights (mean over synapses, full-weight snapshots inside
            each window): one bar group per pathway, three bars light -> dark =
            beginning -> middle -> end (left leg); a dot marks the right leg.
            Pathways without plasticity in the run (e.g. BS->RG under
            --freeze-bs-rg) are not recorded and so not shown.

Input: results/modes/<species>/<mode>.h5 from ./run_modes_local.sh.

Usage:
  python3 scripts/cpg_modes_stages.py --species human
  python3 scripts/cpg_modes_stages.py --species rat --stage beginning:4000:9000 \
      --stage middle:40000:45000 --stage end:115000:120000
"""
import argparse
import os

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
MODES = [("slow", "slow walk\nstride 1200 ms"), ("medium", "medium / plantar\nstride 520 ms"),
         ("fast", "fast walk\nstride 350 ms"), ("toe", "toe stepping\nloading 0.5"),
         ("air", "air stepping\nloading 0.1")]
# pathway key -> (label, 3 sequential steps light->dark of the pathway hue)
PATHWAYS = [("bs_to_rge", "BS→E", ["#b7d0f0", "#6fa3e3", "#2a78d6"]),
            ("cut_to_rge", "CUT→E", ["#f7c3ad", "#f09570", "#eb6834"]),
            ("ia_to_rge", "Ia→E", ["#a6e0c9", "#5fc7a0", "#1baf7a"]),
            ("bs_to_rgf", "BS→F", ["#b7d0f0", "#6fa3e3", "#2a78d6"]),
            ("ia_to_rgf", "Ia→F", ["#a6e0c9", "#5fc7a0", "#1baf7a"])]
DEFAULT_STAGES = [("beginning", 4000.0, 9000.0), ("middle", 40000.0, 45000.0), ("end", 115000.0, 120000.0)]


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK_2, labelsize=7.5, length=2.5)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def win_mean_w(wt, full, lo, hi):
    m = (wt >= lo) & (wt <= hi)
    idx = np.flatnonzero(m) if m.any() else [int(np.argmin(np.abs(wt - hi)))]
    return float(np.nanmean(np.nanmean(full[idx, :], axis=0)))


def corr(a, b):
    return np.corrcoef(a, b)[0, 1] if a.std() > 1e-9 and b.std() > 1e-9 else np.nan


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--species", default="human")
    ap.add_argument("--indir", default=None, help="default results/modes/<species>")
    ap.add_argument("--out", default=None, help="default plots/modes/<species>_modes_stages.png")
    ap.add_argument("--stage", action="append", help="name:lo_ms:hi_ms, exactly 3")
    args = ap.parse_args()
    indir = args.indir or os.path.join("results", "modes", args.species)
    out = args.out or os.path.join("plots", "modes", f"{args.species}_modes_stages.png")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    stages = ([(n, float(a), float(b)) for n, a, b in (s.split(":") for s in args.stage)]
              if args.stage else DEFAULT_STAGES)
    if len(stages) != 3:
        ap.error("--stage must be given exactly 3 times")

    data, attrs, scale = {}, {}, "size ?"
    for mode, _ in MODES:
        path = os.path.join(indir, f"{mode}.h5")
        if not os.path.isfile(path):
            continue
        with h5py.File(path, "r") as f:
            attrs = dict(f.attrs)
            # The model does not record --debug-small; infer the scale from the CUT->RG-E
            # synapse count (~5000 per leg at production N=100, a few hundred at debug-small).
            n_cut = int(dict(f["stats"].attrs).get("L_stdp_cut_rge", 0)) if "stats" in f else 0
            scale = "production N=100" if n_cut >= 2500 else ("debug-small" if n_cut else "size ?")
            d = {"t": f["times_ms"][()], "wt": f["weights_times_ms"][()]}
            for side in ("L", "R"):
                g = f[f"leg_{side}"]
                d[side] = {"fe": g["force_e"][()], "ff": g["force_f"][()],
                           "full": {k: g[f"full_weights/{k}/w"][()] for k, _, _ in PATHWAYS
                                    if f"full_weights/{k}/w" in g}}
            data[mode] = d
    if not data:
        raise SystemExit(f"no runs found in {indir} -- run ./run_modes_local.sh {args.species} first")
    present = [p for p in PATHWAYS if any(p[0] in d["L"]["full"] for d in data.values())]

    fmax = max(max(d["L"]["fe"].max(), d["L"]["ff"].max()) for d in data.values()) * 1.08
    W = {}
    for mode, d in data.items():
        W[mode] = {side: [{k: win_mean_w(d["wt"], d[side]["full"][k], lo, hi)
                           for k, _, _ in present if k in d[side]["full"]}
                          for _, lo, hi in stages] for side in ("L", "R")}
    wtop = max(v for m in W.values() for side in m.values() for st in side for v in st.values()) * 1.18

    fig, axes = plt.subplots(len(MODES), 4, figsize=(15, 2.35 * len(MODES)), facecolor=SURFACE,
                             gridspec_kw={"width_ratios": [1, 1, 1, 1.15], "hspace": 0.62, "wspace": 0.16})
    for r, (mode, label) in enumerate(MODES):
        for c in range(4):
            style(axes[r, c])
        if mode not in data:
            axes[r, 0].text(0.5, 0.5, f"missing: {mode}.h5", transform=axes[r, 0].transAxes,
                            ha="center", color=MUTED)
            continue
        d = data[mode]
        for c, (sname, lo, hi) in enumerate(stages):
            ax = axes[r, c]
            m = (d["t"] >= lo) & (d["t"] <= hi)
            tt = (d["t"][m] - lo) / 1000.0
            ax.plot(tt, d["L"]["fe"][m], color=INK, linewidth=1.3, label="Extensor (Force-E)")
            ax.plot(tt, d["L"]["ff"][m], color=MUTED, linewidth=1.3, label="Flexor (Force-F)")
            ax.set_xlim(0, (hi - lo) / 1000.0); ax.set_ylim(0, fmax)
            rl = corr(d["L"]["fe"][m], d["L"]["ff"][m]); rr = corr(d["R"]["fe"][m], d["R"]["ff"][m])
            ax.set_title(f"r(E,F)  L {rl:+.2f}   R {rr:+.2f}", fontsize=8.5, color=INK, loc="left")
            if r == 0:
                ax.text(0.0, 1.38, f"{sname.upper()}  {lo / 1000:.0f}–{hi / 1000:.0f} s",
                        transform=ax.transAxes, fontsize=10.5, fontweight="bold", color=INK)
            if c == 0:
                ax.set_ylabel(f"{label}\n\nForce (a.u.)", fontsize=8.5, color=INK_2)
            if r == len(MODES) - 1:
                ax.set_xlabel("time in window (s)", fontsize=8, color=INK_2)

        ax = axes[r, 3]
        xs = []
        for gi, (k, lab, steps) in enumerate(present):
            for si in range(3):
                x = gi * 4 + si
                v = W[mode]["L"][si].get(k)
                if v is None:
                    continue
                ax.bar(x, v, width=0.9, color=steps[si], edgecolor=SURFACE, linewidth=1.5, zorder=2)
                vr = W[mode]["R"][si].get(k)
                if vr is not None:
                    ax.plot(x, vr, "o", color=INK, markersize=3, zorder=3)
            end = W[mode]["L"][2].get(k)
            if end is not None:
                ax.annotate(f"{end:.1f}", (gi * 4 + 2, end), xytext=(0, 3), textcoords="offset points",
                            ha="center", fontsize=7, color=INK_2)
            xs.append((gi * 4 + 1, lab))
        ax.set_xticks([x for x, _ in xs], [lab for _, lab in xs], fontsize=7.5, color=INK_2)
        ax.set_ylim(0, wtop)
        ax.set_title("weights: beginning → middle → end", fontsize=8.5, color=INK, loc="left")
        if r == 0:
            ax.text(0.0, 1.38, "PLASTIC WEIGHTS (pA)", transform=ax.transAxes, fontsize=10.5,
                    fontweight="bold", color=INK)

    h, l = axes[0, 0].get_legend_handles_labels()
    h += [plt.Rectangle((0, 0), 1, 1, color=c) for c in ("#dcdad3", "#a9a79f", "#52514e")]
    l += ["beginning", "middle", "end (bar = left leg; light→dark)"]
    h.append(plt.Line2D([], [], marker="o", linestyle="", color=INK, markersize=4)); l.append("right leg")
    fig.legend(h, l, loc="upper center", ncol=len(h), frameon=False, fontsize=8.5, labelcolor=INK_2,
               bbox_to_anchor=(0.5, 0.955))
    note = ("frozen BS→RG (sensory-learning model): BS weights not plastic, not shown. "
            if not any(p[0].startswith("bs") for p in present) else "")
    fig.text(0.06, 1.0, f"{args.species}: force and plastic weights at three stages, five locomotion modes",
             ha="left", va="bottom", fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.06, 0.995,
             f"species={attrs.get('species', '?')}  {scale}  wiring={attrs.get('conn_rule', 'bernoulli')}  sim={attrs.get('sim_ms', 0) / 1000:.0f} s  "
             f"λ={attrs.get('stdp_lambda', attrs.get('lambda', '?'))}  seed={attrs.get('seed', '?')}   {note}"
             f"Force panels: left leg; r(E,F) for both legs.",
             ha="left", va="top", fontsize=8.5, color=INK_2)
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print(f"[modes-stages] wrote {out}")


if __name__ == "__main__":
    main()
