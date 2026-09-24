#!/usr/bin/env python3
"""Generate Fig. 1a / Fig. 1b for spinal_plasticity_as_learning_spec.md.

Style follows tinyHippo's timescale_axis.png: a muted fast->slow hue ramp,
capsule (round-capped) bars, and row labels coloured to match their bar.

Run from the repo root:  python3 scripts/make_spinal_timescale_figs.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

OUT = "."

# Palette sampled pixel-by-pixel from tinyHippo's timescale_axis.png: a muted
# fast->slow hue ramp. Seven values are exact; "cote" is the one added tone
# (dusty mauve), matched to the same saturation/lightness band because this
# figure carries one more mechanism family than the reference had rows.
# One colour per family, shared across Fig 1a and Fig 1b -- the reference does
# the same thing (its rows 5 and 6 share #C1642F).
colors = {
    "induction":    "#2E6FA7",  # blue   - NMDAR/AMPAR induction + STP
    "serotonergic": "#1E8FA0",  # teal   - serotonergic CPG gating
    "grau":         "#4C8C3B",  # green  - spinal instrumental learning
    "ltp":          "#AD8A2E",  # olive  - two-phase LTP, motor circuits
    "wolpaw":       "#C1642F",  # orange - H-reflex conditioning
    "homeostatic":  "#A6433F",  # brick  - homeostatic scaling
    "cote":         "#9C5A76",  # mauve  - activity-dependent step-training
    "tasklearn":    "#6B4A8A",  # purple - task-specific locomotor learning
}

MS, SEC = 1, 1000
MIN = 60 * SEC
HOUR = 60 * MIN
DAY = 24 * HOUR
WEEK = 7 * DAY

TICKS = [1, 10, 100, SEC, 10 * SEC, MIN, HOUR, DAY, WEEK, 4 * WEEK, 12 * WEEK]
TICK_LABELS = ["1ms", "10ms", "100ms", "1s", "10s", "1min", "1hr", "1day",
               "1wk", "4wk", "12wk"]
# Geometry is fixed in ABSOLUTE units so Fig 1a and Fig 1b are a true matched
# pair: identical row pitch, identical bar thickness and identical axis width,
# regardless of how many rows each one has.
ROW_PITCH_IN = 0.495     # vertical distance between rows
BAR_H = 0.5              # bar thickness as a share of row pitch
TOP_MARGIN_IN = 0.75     # room for the title
BOT_MARGIN_IN = 1.55     # room for rotated tick labels + xlabel
FIG_W_IN = 16.0
AXES_LEFT_FRAC = 0.335   # label gutter
AXES_W_FRAC = 0.315


def capsule(ax, fig, x0, x1, y, lw_pt, color, zorder=2):
    """Draw a round-capped bar from x0 to x1.

    A round cap extends half a linewidth *in display space* past each
    endpoint, which on a log axis would silently lengthen the bar by a
    position-dependent amount. So shrink the segment by the cap radius at
    both ends first: the capsule's outer extent then equals the true data
    range. Degenerates to a dot when the bar is shorter than one cap.
    """
    t, inv = ax.transData, ax.transData.inverted()
    p0, p1 = t.transform((x0, y)), t.transform((x1, y))
    r = lw_pt / 2.0 * fig.dpi / 72.0
    avail = p1[0] - p0[0]
    if avail > 2 * r + 1.0:
        xa = inv.transform((p0[0] + r, p0[1]))[0]
        xb = inv.transform((p1[0] - r, p1[1]))[0]
    else:
        # Shorter than one cap diameter. Centre a minimal (non-zero) segment:
        # a zero-length path is not rendered at all, so keep half a pixel on
        # each side. The drawn capsule is then cap-width regardless, i.e. such
        # a bar is at the figure's resolution floor and slightly overstated.
        mid = (p0[0] + p1[0]) / 2.0
        xa = inv.transform((mid - 0.5, p0[1]))[0]
        xb = inv.transform((mid + 0.5, p0[1]))[0]
    ax.plot([xa, xb], [y, y], lw=lw_pt, color=color, solid_capstyle="round",
            zorder=zorder, clip_on=False)
    return xa, xb


def render(rows, legend_keys, title, outfile, hatch=None, xmax=12 * WEEK):
    y_span = len(rows) + 0.5
    axes_h_in = y_span * ROW_PITCH_IN
    fig_h_in = axes_h_in + TOP_MARGIN_IN + BOT_MARGIN_IN
    fig = plt.figure(figsize=(FIG_W_IN, fig_h_in), dpi=150)
    ax = fig.add_axes([AXES_LEFT_FRAC, BOT_MARGIN_IN / fig_h_in,
                       AXES_W_FRAC, axes_h_in / fig_h_in])

    y_positions = list(range(len(rows)))[::-1]
    ax.set_yticks(y_positions)
    ax.set_yticklabels([r[0] for r in rows], fontsize=10.5)
    ax.set_ylim(-0.75, len(rows) - 0.25)
    ax.set_xscale("log")
    ax.set_xticks(TICKS)
    ax.set_xticklabels(TICK_LABELS, rotation=40, ha="right", fontsize=10.5)
    ax.set_xlim(1, xmax * 1.5)

    # absolute bar thickness -> identical in both figures
    lw_pt = BAR_H * ROW_PITCH_IN * 72.0

    for (label, start, end, key), y in zip(rows, y_positions):
        xa, xb = capsule(ax, fig, start, end, y, lw_pt, colors[key], zorder=3)
        if hatch and xb > xa:
            # hatch only the span between the cap centres, so the rounded ends
            # stay solid and nothing spills past the capsule outline
            ax.barh(y, width=(xb - xa), left=xa, height=BAR_H,
                    facecolor="none", edgecolor="white", hatch=hatch,
                    linewidth=0, zorder=4)

    # colour each row label to match its bar, as the reference figure does
    for lbl, row in zip(ax.get_yticklabels(), rows):
        lbl.set_color(colors[row[3]])

    ax.set_xlabel("Time since induction (log scale)", fontsize=13)
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.grid(axis="x", which="major", color="lightgray", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)

    handles = [mpatches.Patch(facecolor=colors[k], label=lbl, hatch=hatch,
                              edgecolor=("white" if hatch else "none"))
               for k, lbl in legend_keys]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.03, 1.02),
              fontsize=10, frameon=False)
    plt.savefig(f"{OUT}/{outfile}")
    plt.close(fig)
    print("wrote", outfile)


healthy_rows = [
    ("NMDAR/AMPAR-dependent induction", 1, 15, "induction"),
    ("Short-term plasticity (facilitation/depression)", 15, SEC, "induction"),
    ("Serotonergic gating -- acute (state-dependent)  [22,23]", SEC, 40 * SEC, "serotonergic"),
    ("Spinal instrumental learning -- contingent (adaptive)  [1,2]", MIN, HOUR, "grau"),
    ("Early-phase LTP, motor circuits (E-LTP)  [1,4,6]", 2 * MIN, 3 * HOUR, "ltp"),
    ("Late-phase LTP, motor circuits (L-LTP)  [1,4,7]", 3 * HOUR, 3 * DAY, "ltp"),
    ("H-reflex conditioning, Phase I (fast, small)  [8]", HOUR, 2 * DAY, "wolpaw"),
    ("Homeostatic AMPAR upscaling (deafferentation)  [24,27]", DAY, 5 * DAY, "homeostatic"),
    ("Step-training neurotrophin upregulation  [14,15]", 5 * DAY, 14 * DAY, "cote"),
    ("Serotonergic gating -- chronic, training-restored  [22,23]", 5 * DAY, 28 * DAY, "serotonergic"),
    ("H-reflex conditioning, Phase II (slow, multi-site)  [8,9]", WEEK, 49 * DAY, "wolpaw"),
    ("Task-specific spinal locomotor learning\n(de Leon/Roy/Edgerton, contested)  [11,12,13]", 14 * DAY, 84 * DAY, "tasklearn"),
]

# Legend follows the fast->slow ramp, i.e. order of first appearance.
healthy_legend = [
    ("induction", "NMDAR/AMPAR induction / short-term plasticity"),
    ("serotonergic", "Serotonergic CPG gating"),
    ("grau", "Spinal instrumental learning (Grau)"),
    ("ltp", "Two-phase LTP, motor circuits (Grau; corticospinal)"),
    ("wolpaw", "H-reflex conditioning (Wolpaw)"),
    ("homeostatic", "Homeostatic scaling"),
    ("cote", "Activity-dependent step-training (Cote et al.)"),
    ("tasklearn", "Task-specific locomotor learning (de Leon/Roy/Edgerton)"),
]

pathological_rows = [
    ("Spinal instrumental learning -- non-contingent (maladaptive)  [1,3,5]", MIN, HOUR, "grau"),
    ("Homeostatic downscaling failure / KCC2 loss (spasticity)  [25,26]", HOUR, 28 * DAY, "homeostatic"),
    ("Serotonergic gating -- chronic, untreated (persists)  [22,23]", 5 * DAY, 28 * DAY, "serotonergic"),
]

pathological_legend = [
    ("serotonergic", "Serotonergic CPG gating"),
    ("grau", "Spinal instrumental learning (Grau)"),
    ("homeostatic", "Homeostatic scaling"),
]

render(healthy_rows, healthy_legend,
       "Healthy / adaptive spinal plasticity timescales",
       "spinal_timescale_healthy.png", hatch=None)

render(pathological_rows, pathological_legend,
       "Pathological motor-circuit plasticity timescales (after SCI)",
       "spinal_timescale_pathological.png", hatch="//")
