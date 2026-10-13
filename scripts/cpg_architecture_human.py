#!/usr/bin/env python3
"""
cpg_architecture_human.py
Figure 1 for the human model: the circuit as built by cpg_2legs_fast.py --species human (afferent model 'split';
plastic CUT->RG-E, BS->RG-E/F and Ia->RG-E/F; static Ib->RG; commissural inhibition between the rhythm generators).
Same palette as cpg_architecture_diagram.py (rat, one leg).
  (A) core circuit of both legs: descending drive, rhythm generators, reciprocal inhibition (6:1), motor pools, muscles,
      commissural inhibition between the legs.
  (B) afferent wiring of one leg (the other is a mirror): Ia, Ib, cutaneous and the external flexor swing afferent.
Not drawn: the tonic base drive (same targets as BS) and rules rather than wiring (RG-E load gate, force-triggered
stance/swing, ankle coupling of the muscle lengths, interlimb load transfer).
Usage: python3 scripts/cpg_architecture_human.py   ->  paper/figures/fig1_architecture_human.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Patch, RegularPolygon

ORANGE, ORANGE_D, ORANGE_L = "#F59331", "#C2570B", "#F2B66D"
BLUE, RED, GREY, INBOX = "#5BB0DA", "#D24726", "#8c8c8c", "#C15A1E"
FS = 11

fig = plt.figure(figsize=(18, 8.2))
axA = fig.add_axes([0.0, 0.08, 0.60, 0.88]); axB = fig.add_axes([0.61, 0.08, 0.38, 0.88])


def node(ax, kind, xy, label):
    if kind == "rg":
        ax.add_patch(Circle(xy, 0.62, fc=ORANGE, ec="#7a4a12", lw=1.4, zorder=4)); fs, c = FS + 1, "black"
    elif kind == "in":
        ax.add_patch(Circle(xy, 0.46, fc=BLUE, ec="#2b6f8f", lw=1.4, zorder=4)); fs, c = FS - 2.5, "black"
    elif kind == "mn":
        ax.add_patch(RegularPolygon(xy, 4, radius=0.62, orientation=0.0, fc=ORANGE, ec="#7a4a12", lw=1.4, zorder=4)); fs, c = FS - 2, "black"
    elif kind == "mus":
        ax.add_patch(FancyBboxPatch((xy[0] - 0.7, xy[1] - 0.31), 1.4, 0.62, boxstyle="round,pad=0.02", fc=RED, ec="#7a1f10", lw=1.4, zorder=4)); fs, c = FS, "white"
    else:  # afferent / drive box
        ax.add_patch(FancyBboxPatch((xy[0] - 0.62, xy[1] - 0.27), 1.24, 0.54, boxstyle="round,pad=0.02", fc=INBOX, ec="#7a3810", lw=1.3, zorder=4)); fs, c = FS - 1.5, "white"
    ax.text(*xy, label, ha="center", va="center", fontsize=fs, fontweight="bold", color=c, zorder=5)


def edge(ax, a, b, color, style="-", rad=0.0, lw=1.8, inhib=False, sa=14, sb=14, ra=0.55, rb=0.55):
    if inhib:  # inhibition: plain line ending in a dot just outside the target node
        import numpy as np
        a, b = np.array(a, float), np.array(b, float)
        u = (b - a) / np.hypot(*(b - a))
        a2, b2 = a + u * (ra + 0.05), b - u * (rb + 0.12)
        ax.add_patch(FancyArrowPatch(tuple(a2), tuple(b2), connectionstyle=f"arc3,rad={rad}", arrowstyle="-", lw=lw, color=color,
                                     linestyle=style, shrinkA=0, shrinkB=0, zorder=2))
        ax.plot(*b2, "o", ms=4 + 1.4 * lw, color=color, zorder=3)
        return
    ax.add_patch(FancyArrowPatch(a, b, connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>", mutation_scale=14,
                                 lw=lw, color=color, linestyle=style, shrinkA=sa, shrinkB=sb, zorder=2))


# ---------------- (A) core circuit, both legs ----------------
ax = axA; ax.set_xlim(-10.4, 10.4); ax.set_ylim(-1.0, 10.4); ax.set_aspect("equal"); ax.axis("off")
core = {}
for sgn, name in ((-1, "Left leg"), (+1, "Right leg")):
    X = lambda d: sgn * d
    P = dict(RGE=(X(2.7), 7.4), RGF=(X(2.7), 2.6), InF=(X(1.55), 5.0), InE=(X(3.85), 5.0),
             ME=(X(5.6), 7.4), MF=(X(5.6), 2.6), musE=(X(8.1), 7.4), musF=(X(8.1), 2.6))
    core[sgn] = P
    for k, kind in (("RGE", "rg"), ("RGF", "rg"), ("InE", "in"), ("InF", "in"), ("ME", "mn"), ("MF", "mn"), ("musE", "mus"), ("musF", "mus")):
        node(ax, kind, P[k], {"RGE": "RG-E", "RGF": "RG-F", "InE": "InE", "InF": "InF", "ME": "M-E", "MF": "M-F", "musE": "mus-E", "musF": "mus-F"}[k])
    edge(ax, P["RGE"], P["InE"], ORANGE_L, rad=-0.1 * sgn); edge(ax, P["InE"], P["RGF"], BLUE, inhib=True, rad=-0.1 * sgn, lw=1.4, ra=0.46, rb=0.62)
    edge(ax, P["RGF"], P["InF"], ORANGE_L, rad=-0.1 * sgn); edge(ax, P["InF"], P["RGE"], BLUE, inhib=True, rad=-0.1 * sgn, lw=3.0, ra=0.46, rb=0.62)
    for k, up in (("RGE", 1), ("RGF", -1)):  # recurrent excitation
        x, y = P[k]
        ax.add_patch(FancyArrowPatch((x - 0.32, y + up * 0.62), (x + 0.32, y + up * 0.62), connectionstyle=f"arc3,rad={-up * 1.6}",
                                     arrowstyle="-|>", mutation_scale=9, lw=1.2, color=ORANGE_L, zorder=2))
    edge(ax, P["RGE"], P["ME"], ORANGE_L); edge(ax, P["RGF"], P["MF"], ORANGE_L)
    edge(ax, P["ME"], P["musE"], ORANGE_L); edge(ax, P["MF"], P["musF"], ORANGE_L)
    edge(ax, P["ME"], P["MF"], BLUE, inhib=True, rad=0.3 * sgn, lw=1.4, ra=0.62, rb=0.62)
    edge(ax, P["MF"], P["ME"], BLUE, inhib=True, rad=0.3 * sgn, lw=1.4, ra=0.62, rb=0.62)
    ax.text(X(5.4), 9.7, name, ha="center", fontsize=15, color="#b0b0b0", fontweight="bold")
    ax.text(X(8.1), 6.55, "afferents:\nsee (B)", ha="center", fontsize=8.5, color=GREY, style="italic")
    ax.text(X(8.1), 1.6, "afferents:\nsee (B)", ha="center", fontsize=8.5, color=GREY, style="italic")
node(ax, "box", (0, 9.7), "BS to E"); node(ax, "box", (0, -0.5), "BS to F")
for sgn in (-1, 1):
    edge(ax, (0, 9.7), core[sgn]["RGE"], ORANGE_D, lw=2.6, rad=0.12 * sgn, sa=12, sb=18)
    edge(ax, (0, -0.5), core[sgn]["RGF"], ORANGE_D, lw=2.6, rad=-0.12 * sgn, sa=12, sb=18)
edge(ax, core[-1]["RGF"], core[1]["RGF"], BLUE, inhib=True, lw=2.6, rad=0.0, ra=0.62, rb=0.62)
edge(ax, core[1]["RGF"], core[-1]["RGF"], BLUE, inhib=True, lw=2.6, rad=0.0, ra=0.62, rb=0.62)
edge(ax, core[-1]["RGE"], core[1]["RGE"], BLUE, inhib=True, lw=1.3, rad=0.0, ra=0.62, rb=0.62)
edge(ax, core[1]["RGE"], core[-1]["RGE"], BLUE, inhib=True, lw=1.3, rad=0.0, ra=0.62, rb=0.62)
ax.text(0, 3.05, "commissural, F strong\n(V0-like, as direct RG→RG)", ha="center", fontsize=9.5, color="#2b6f8f", style="italic")
ax.text(0, 7.75, "commissural, E weak", ha="center", fontsize=9.5, color="#2b6f8f", style="italic")
ax.text(-10.3, 10.2, "A", fontsize=20, fontweight="bold")

# ---------------- (B) afferent wiring of one leg ----------------
ax = axB; ax.set_xlim(-1.4, 9.4); ax.set_ylim(-0.4, 10.4); ax.set_aspect("equal"); ax.axis("off")
mus = dict(musE=(0.2, 7.9), musF=(0.2, 2.1))
aff = dict(IaE=(3.1, 9.1), IbE=(3.1, 7.9), CUT=(3.1, 6.7), IaF=(3.1, 3.3), IbF=(3.1, 2.1), SW=(3.1, 0.9))
tgt = dict(RGE=(8.3, 9.4), InE=(8.3, 8.2), IaIntE=(6.1, 6.6), MF=(8.3, 5.9), ME=(8.3, 4.1), IaIntF=(6.1, 3.4), InF=(8.3, 1.8), RGF=(8.3, 0.6))
node(ax, "mus", mus["musE"], "mus-E"); node(ax, "mus", mus["musF"], "mus-F")
for k, lab in (("IaE", "Ia"), ("IbE", "Ib"), ("CUT", "cut"), ("IaF", "Ia"), ("IbF", "Ib"), ("SW", "swing")):
    node(ax, "box", aff[k], lab)
for k, kind, lab in (("RGE", "rg", "RG-E"), ("InE", "in", "InE"), ("IaIntE", "in", "Ia-E"), ("MF", "mn", "M-F"),
                     ("ME", "mn", "M-E"), ("IaIntF", "in", "Ia-F"), ("InF", "in", "InF"), ("RGF", "rg", "RG-F")):
    node(ax, kind, tgt[k], lab)
for k in ("IaE", "IbE", "CUT"):
    edge(ax, mus["musE"], aff[k], GREY, style="--", lw=1.1, sa=22, sb=12)
for k in ("IaF", "IbF"):
    edge(ax, mus["musF"], aff[k], GREY, style="--", lw=1.1, sa=22, sb=12)
O = dict(sa=12, sb=18)
edge(ax, aff["IaE"], tgt["RGE"], ORANGE_D, lw=2.4, **O); edge(ax, aff["IaE"], tgt["IaIntE"], ORANGE_L, **O)
edge(ax, aff["IbE"], tgt["RGE"], ORANGE_L, **O); edge(ax, aff["IbE"], tgt["InE"], ORANGE_L, **O)
edge(ax, aff["CUT"], tgt["RGE"], ORANGE_D, lw=3.0, **O); edge(ax, aff["CUT"], tgt["InE"], ORANGE_L, **O)
edge(ax, aff["IaF"], tgt["RGF"], ORANGE_D, lw=2.4, **O); edge(ax, aff["IaF"], tgt["IaIntF"], ORANGE_L, **O)
edge(ax, aff["IbF"], tgt["RGF"], ORANGE_L, **O); edge(ax, aff["IbF"], tgt["InF"], ORANGE_L, **O)
edge(ax, aff["SW"], tgt["RGF"], ORANGE_L, style=":", lw=1.6, **O); edge(ax, aff["SW"], tgt["InF"], ORANGE_L, style=":", lw=1.6, **O)
edge(ax, tgt["IaIntE"], tgt["MF"], BLUE, inhib=True, lw=1.6, ra=0.46, rb=0.62)
edge(ax, tgt["IaIntF"], tgt["ME"], BLUE, inhib=True, lw=1.6, ra=0.46, rb=0.62)
ax.text(3.1, 10.1, "afferents", ha="center", fontsize=10, color="#555"); ax.text(8.3, 10.35, "targets", ha="center", fontsize=10, color="#555")
ax.text(-1.3, 10.2, "B", fontsize=20, fontweight="bold")

handles = [Patch(fc=ORANGE, ec="#7a4a12", label="rhythm generator / motoneuron pool (excitatory)"),
           Patch(fc=BLUE, ec="#2b6f8f", label="inhibitory interneuron"), Patch(fc=RED, ec="#7a1f10", label="muscle"),
           Patch(fc=INBOX, ec="#7a3810", label="afferent / descending input"),
           Line2D([0], [0], color=ORANGE_D, lw=3, label="plastic excitatory (BS, CUT, Ia → RG)"),
           Line2D([0], [0], color=ORANGE_L, lw=2, label="static excitatory"),
           Line2D([0], [0], color=ORANGE_L, lw=2, ls=":", label="external swing afferent"),
           Line2D([0], [0], color=BLUE, lw=2, marker="o", markersize=7, label="inhibitory (dot end)"),
           Line2D([0], [0], color=GREY, lw=1.5, ls="--", label="rate-coded from muscle force / length")]
fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=9.5, frameon=True, bbox_to_anchor=(0.5, 0.0))
out = "paper/figures/fig1_architecture_human.png"
fig.savefig(out, dpi=150)
print("saved", out)
