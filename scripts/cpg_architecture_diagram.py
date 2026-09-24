#!/usr/bin/env python3
"""
cpg_architecture_diagram.py
As-implemented architecture of one leg (contralateral = mirror), drawn in the
visual style of the conceptual schematic (Fig. 1): orange circles = excitatory
rhythm-generator nuclei, orange diamonds = motoneuron pools, red rounded boxes =
muscles, light-blue circles = inhibitory interneurons, dark-orange boxes =
afferent / descending inputs. Excitatory projections orange (dark = STDP-plastic),
inhibitory projections light blue, rate-coded muscle->Ia transduction dashed grey.
Vertical (rotated) layout: descending drive at top, flowing down through the RG
core and motor pools to the muscles, with the proprioceptive loop closing on the
right. No in-figure title (info -> caption).
"""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle, RegularPolygon
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# Fig-1 palette
ORANGE   = "#F59331"   # excitatory neuron (RG, MN)
ORANGE_D = "#C2570B"   # STDP / plastic excitatory projection (dark orange)
ORANGE_L = "#F2B66D"   # static excitatory projection (light orange)
BLUE     = "#5BB0DA"   # inhibitory neuron + projection (light blue)
RED      = "#D24726"   # muscle
GREY     = "#9e9e9e"   # rate-coded transduction
INBOX    = "#C15A1E"   # afferent / drive input box

FS = 12.5              # node label font size


def rg(ax, xy, label):        # big excitatory nucleus
    ax.add_patch(Circle(xy, 0.62, fc=ORANGE, ec="#7a4a12", lw=1.6, zorder=4))
    ax.text(*xy, label, ha="center", va="center", fontsize=FS, fontweight="bold", zorder=5)

def mn(ax, xy, label):        # motoneuron pool (diamond)
    ax.add_patch(RegularPolygon(xy, 4, radius=0.62, orientation=0.0,
                                fc=ORANGE, ec="#7a4a12", lw=1.6, zorder=4))
    ax.text(*xy, label, ha="center", va="center", fontsize=FS - 1.5, fontweight="bold", zorder=5)

def inh(ax, xy, label, r=0.42):   # inhibitory interneuron (light-blue circle)
    ax.add_patch(Circle(xy, r, fc=BLUE, ec="#2b6f8f", lw=1.4, zorder=4))
    ax.text(*xy, label, ha="center", va="center", fontsize=FS - 3, fontweight="bold", zorder=5)

def muscle(ax, xy, label):    # muscle (red rounded rectangle)
    ax.add_patch(FancyBboxPatch((xy[0] - 0.7, xy[1] - 0.33), 1.4, 0.66,
                 boxstyle="round,pad=0.02", fc=RED, ec="#7a1f10", lw=1.6, zorder=4))
    ax.text(*xy, label, ha="center", va="center", fontsize=FS, fontweight="bold",
            color="white", zorder=5)

def inp(ax, xy, label, w=1.2):    # afferent / drive input box (dark-orange)
    ax.add_patch(FancyBboxPatch((xy[0] - w / 2, xy[1] - 0.3), w, 0.6,
                 boxstyle="round,pad=0.02", fc=INBOX, ec="#7a3810", lw=1.4, zorder=4))
    ax.text(*xy, label, ha="center", va="center", fontsize=FS - 1.5, fontweight="bold",
            color="white", zorder=5)

def edge(ax, a, b, color, style="-", rad=0.0, lw=2.0, label=None, lx=0.5, ly=0.16):
    ax.add_patch(FancyArrowPatch(a, b, connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>",
                 mutation_scale=16, lw=lw, color=color, linestyle=style,
                 shrinkA=17, shrinkB=17, zorder=2))
    if label:
        mx = a[0] + (b[0] - a[0]) * lx - rad * 1.1
        my = a[1] + (b[1] - a[1]) * lx + ly
        ax.text(mx, my, label, fontsize=9, color=color, ha="center", style="italic", zorder=6)


fig, ax = plt.subplots(figsize=(16, 9))
ax.set_xlim(0, 16.2); ax.set_ylim(0.4, 8.7); ax.axis("off")

# Horizontal left->right flow (like Fig. 1): drives -> RG core -> Ia interneurons
# -> motoneurons -> muscles, with the proprioceptive loop closing along the bottom.
P = dict(
    BS=(1.3, 7.6), CUT=(1.3, 6.2), base=(1.3, 4.8),
    IaEramp=(1.3, 3.1), flexAff=(1.3, 1.7),
    RGE=(4.7, 6.3), RGF=(4.7, 2.5),
    InE=(6.1, 5.2), InF=(6.1, 3.6),
    IaIntE=(8.0, 7.0), IaIntF=(8.0, 1.8),
    ME=(9.9, 6.3), MF=(9.9, 2.5),
    musE=(12.4, 6.3), musF=(12.4, 2.5),
    IaE=(15.0, 5.4), IaF=(15.0, 3.4),
)
# nodes
for k in ("BS", "CUT", "base"): inp(ax, P[k], k)
inp(ax, P["IaEramp"], "Ia-E\nramp", w=1.3); inp(ax, P["flexAff"], "flex\nAff", w=1.3)
rg(ax, P["RGE"], "RG-E"); rg(ax, P["RGF"], "RG-F")
inh(ax, P["InE"], "InE"); inh(ax, P["InF"], "InF")
inh(ax, P["IaIntE"], "IaInt-E", r=0.46); inh(ax, P["IaIntF"], "IaInt-F", r=0.46)
mn(ax, P["ME"], "M-E"); mn(ax, P["MF"], "M-F")
muscle(ax, P["musE"], "mus-E"); muscle(ax, P["musF"], "mus-F")
inp(ax, P["IaE"], "Ia-E"); inp(ax, P["IaF"], "Ia-F")

# --- descending drive ---
edge(ax, P["BS"], P["RGE"], ORANGE_L, label="BS→E (frozen)", lx=0.55, rad=0.05)
edge(ax, P["BS"], P["RGF"], ORANGE_L, label="BS→F (frozen)", lx=0.55, rad=-0.05)
edge(ax, P["CUT"], P["RGE"], ORANGE_D, label="plastic →63", lx=0.5)
edge(ax, P["CUT"], P["InE"], ORANGE_L, rad=-0.2, lw=1.4)
edge(ax, P["base"], P["RGF"], ORANGE_L, lw=1.3, label="tonic", lx=0.55)
# external pacing afferents
edge(ax, P["IaEramp"], P["RGE"], ORANGE_L, style=":", label="heel→toe", lx=0.5)
edge(ax, P["flexAff"], P["RGF"], ORANGE_L, style=":", rad=-0.1, label="swing aff", lx=0.5)
# --- reciprocal core (Zhang 6:1) ---
edge(ax, P["RGE"], P["InE"], ORANGE_L, lw=1.4)
edge(ax, P["RGF"], P["InF"], ORANGE_L, lw=1.4)
edge(ax, P["InE"], P["RGF"], BLUE, label="−8", lx=0.62, ly=0.28)
edge(ax, P["InF"], P["RGE"], BLUE, label="−48 (6:1)", lx=0.32, ly=-0.42)
# --- motor output ---
edge(ax, P["RGE"], P["ME"], ORANGE_L, label="+30", lx=0.5)
edge(ax, P["RGF"], P["MF"], ORANGE_L, label="+30", lx=0.5)
edge(ax, P["ME"], P["MF"], BLUE, rad=0.35, lw=1.4, label="motor recip −22", lx=0.5, ly=-0.3)
edge(ax, P["MF"], P["ME"], BLUE, rad=0.35, lw=1.4)
edge(ax, P["ME"], P["musE"], ORANGE_L)
edge(ax, P["MF"], P["musF"], ORANGE_L)
# --- proprioceptive loop (right side) ---
edge(ax, P["musE"], P["IaE"], GREY, style="--", rad=-0.3, label="force/len→Hz", lx=0.55)
edge(ax, P["musF"], P["IaF"], GREY, style="--", rad=-0.3)
edge(ax, P["IaE"], P["IaIntE"], ORANGE_L, lw=1.4)
edge(ax, P["IaIntE"], P["MF"], BLUE, lw=1.4, rad=0.15, label="Ia recip −10", lx=0.6, ly=-0.25)
edge(ax, P["IaF"], P["IaIntF"], ORANGE_L, lw=1.4)
edge(ax, P["IaIntF"], P["ME"], BLUE, lw=1.4, rad=0.15)
edge(ax, P["IaE"], P["InF"], ORANGE_L, rad=0.25, lw=1.3, label="Ia→In loop", lx=0.6, ly=0.34)
edge(ax, P["IaE"], P["RGE"], ORANGE_D, rad=0.4, lw=2.4, label="plastic Ia→RG", lx=0.12, ly=0.28)
edge(ax, P["IaF"], P["RGF"], ORANGE_D, rad=-0.3, lw=2.4)
# commissural stub (informational note in the empty top-left band)
ax.annotate("commissural → contralateral leg\nRG-E↔RG-E −8,  RG-F↔RG-F −20",
            (3.2, 8.2), fontsize=10, color=BLUE, ha="center",
            bbox=dict(boxstyle="round", fc="#eef7fb", ec=BLUE, lw=1.2))

# legend
leg = [Patch(fc=ORANGE, ec="#7a4a12", label="excitatory nucleus (RG)"),
       Line2D([0], [0], marker="D", color="w", markerfacecolor=ORANGE, markersize=13,
              markeredgecolor="#7a4a12", label="motoneuron pool"),
       Patch(fc=BLUE, ec="#2b6f8f", label="inhibitory interneuron"),
       Patch(fc=RED, ec="#7a1f10", label="muscle"),
       Patch(fc=INBOX, ec="#7a3810", label="afferent / drive input"),
       Line2D([0], [0], color=ORANGE_D, lw=3, label="plastic excitatory (STDP)"),
       Line2D([0], [0], color=ORANGE_L, lw=3, label="static excitatory"),
       Line2D([0], [0], color=BLUE, lw=3, label="inhibitory projection"),
       Line2D([0], [0], color=GREY, lw=3, ls="--", label="rate-coded transduction")]
ax.legend(handles=leg, loc="lower center", ncol=3, fontsize=10.5, frameon=True,
          bbox_to_anchor=(0.5, -0.02))
fig.savefig("paper/figures/fig_architecture_implemented.png", dpi=170, bbox_inches="tight")
print("saved paper/figures/fig_architecture_implemented.png")
