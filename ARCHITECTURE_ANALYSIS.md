# Implemented architecture vs the feedback-loop diagram — analysis & justification

Companion to `paper/figures/fig1_schematic.png` (the conceptual diagram) and
`plots/paper/fig_architecture_implemented.png` (the as-built diagram, generated
from the verified projection list). Answers the connectivity questions.

## Q2/Q3 — Why do static projections have only a *delay* distribution, not a *weight* distribution?

**Yes — static projections have a single (delta) weight but a spread of delays.**
This is a deliberate modelling choice, not an omission:

- **Weights.** A static projection is created with one scalar weight applied to
  every connection (e.g. `InF→RG-E = −48 pA` for all 1514 connections). We did
  not draw per-connection weight jitter for the fixed circuit, so the weight
  "distribution" is a spike at the design value (s.d. = 0). The fixed circuit
  encodes a *designed* balance (the Zhang 6:1 asymmetry, the motor reciprocal
  inhibition, the commissural strengths); giving each its exact intended value
  keeps that balance interpretable and reproducible. Only the **plastic**
  projections (CUT→RG-E, BS→RG, Ia→RG) carry a weight distribution, because STDP
  (and the lognormal initialisation) generates per-connection spread there.

- **Delays.** Delays are drawn for *every* connection — static and plastic alike
  — from the rat `length_velocity` preset (a per-projection base conduction +
  synaptic delay) plus 0.2 ms Gaussian jitter. So delays vary per connection
  (s.d. ≈ 0.2 ms) because conduction distance and synaptic latency genuinely
  vary, whereas the *strength* of a designed fixed projection does not.

**RESOLVED (adopted).** Since biological weights *are* heterogeneous, the model
now applies per-connection lognormal heterogeneity to every static synapse by
default (`--static-weight-cv 0.5`, mean and sign preserved). So all projections
now carry a weight distribution, not just a delay distribution. This was
validated to slightly *improve* counter-phase (corr$(F_E,F_F)$ −0.978 → −0.989,
debug-small sensory), so bio-plausibility and performance agree. The legacy
delta behaviour remains available with `--static-weight-cv 0` (used by the
frozen-weight control, which isolates *learned* weight structure).

## Q4 — What are the "extra" projections (CUT→InE, Ia→IaInt, base→RG, Ia→InE)?

These are real model pathways that the high-level diagram folds into its afferent
arrows; they are the spinal-reflex microcircuitry:

| Projection | What it is | Biology |
|---|---|---|
| **base→RG-E / -F** | A small always-on tonic bias (+1 pA, p=0.1) to both RGs. | Numerical excitability floor (prevents silent death at low drive); stands in for diffuse background excitability. Not a labelled afferent. |
| **CUT→InE** | Cutaneous afferent → extensor-side reciprocal interneuron (+6 pA). | The **stance-phase cutaneous reflex** (Schomburg, Pearson, Rossignol): paw contact reinforces extensor *and* suppresses flexor via InE. The diagram's `cut` box only shows the afferent, not this reflex target. |
| **Ia-E→IaInt-E / Ia-F→IaInt-F** | Muscle Ia afferent → Ia *inhibitory* interneuron (+6 pA). | First leg of the **classical Ia reciprocal-inhibition reflex**. In the diagram the Ia-E/Ia-F blue circles *are* these IaInt cells. |
| **IaInt-E→M-F / IaInt-F→M-E** | Ia interneuron → *antagonist* motor pool (−10 pA). | Second leg: stretch of one muscle inhibits its antagonist's motoneurons. |
| **Ia-E→InE / Ia-F→InF** | Muscle Ia afferent → RG reciprocal interneuron (+6 pA). | The **closed-loop sensory drive** (`MOD_IA_LOOP`): proprioception feeds the rhythm-generator core so the rhythm is partly sustained by feedback, not BS alone. This is the knob the whole "reduced-BS-dependence" goal turns on. |

## Q6 — Why was CUT→RG-E bimodal (a spike at 14 pA)? — *fixed*

The cutaneous input to RG-E is **two parallel pathways** sharing the same
(source, target):
1. a **plastic STDP** pathway (`stdp_cut_rge`, lognormal init ≈ 3.5 pA → learns to
   ≈ 63 pA), and
2. a **static co-activation** pathway (`MOD_COACT`, fixed `W_CUT2RGE_STATIC = 14`
   pA, p = 0.35) — present from t = 0 so cutaneous + brainstem can cross threshold
   together before STDP bootstraps.

The original dump queried *all* cut→rge connections and so superimposed a clean
lognormal (≈ 5000 plastic synapses) on a delta spike at 14 pA (≈ 3500 static
synapses) → the bimodal histogram. **It was correct data with a conflated label.**

**RESOLVED (adopted).** The static co-activation pathway was a numerical bootstrap
(ensure CUT+BS cross threshold at t=0 before STDP grows the plastic weight) — a
modeling scaffold, not biology: a real cutaneous→RG input is a single projection.
It is now **dropped by default** (`--cut-static-w 0`), leaving one plastic
cutaneous→RG-E projection. Validated to work in both arms (CUT still learns to
≈ 65 pA; counter-phase preserved/improved) — the paced gait and Ia loop supply
the early drive the bootstrap used to provide. The plastic CUT histogram is the
clean lognormal expected. (`--cut-static-w 14` restores the legacy pathway.)

## Q5 — Discrepancies: diagram vs implemented architecture

### In the diagram, abstracted/not separately implemented
| Diagram element | Implementation | Justification |
|---|---|---|
| **V2a, V0v, V0d, In1** commissural interneuron classes | Collapsed into two direct commissural **inhibitory** projections RG-E↔RG-E (−8) and RG-F↔RG-F (−20). | The model targets the *learning* question on a 2-leg CPG, not the genetically-identified commissural microcircuit. The functional output that matters here — robust left–right alternation — is captured by reciprocal RG inhibition (Kiehn 2016; Talpalar 2013). Resolving each V0/V2a/V3 class is the subject of Zhang 2021/2022 and is out of scope. |
| Numbered sub-nuclei (1–4) inside E and F | Homogeneous Izhikevich populations per half-centre (the 3-group Ia-E pacing ramp is the only sub-structure). | The sub-nuclei denote functional compartments; the phenomenological half-centre does not need them to produce the rhythm. |
| Homonymous monosynaptic Ia→motoneuron stretch reflex | Not implemented as Ia→M; Ia acts via IaInt (reciprocal), via InE/InF (closed loop), and (sensory arm) via plastic Ia→RG. | The model's locomotor question concerns rhythm generation and its sensory entrainment, not the segmental stretch-reflex gain. |

### Implemented, but not shown on the diagram
- **base→RG** tonic bias; **CUT→InE** stance reflex; **Ia→InE/InF** closed loop;
  **flexor swing afferent** (`flexAff→RG-F/InF`) and the **Ia-E heel→toe pacing
  ramp** (the paced-gait clock); and crucially the **plastic Ia→RG** projection
  (the sensory-learning arm). These are listed in Table~\ref{tab:delays}.
- **muscle→Ia** is drawn in the diagram as a loop arrow but is implemented as a
  **rate-coded transduction** (force & length → Ia firing rate), not a synapse —
  the standard spindle/GTO simplification — so it has no weight/delay.

### Faithful where it counts
Both legs; E/F half-centres with the Zhang 6:1 reciprocal asymmetry; InE/InF;
M-E/M-F with reciprocal inhibition; mus-E/mus-F; Ia and cutaneous afferents; the
BS→E/F descending projections; and the closed sensorimotor loop
(RG→M→muscle→Ia→back into the spinal core) are all present and match the diagram.

**Bottom line:** the implementation is a *functional reduction* of the diagram —
faithful to the half-centre core, the reciprocal-inhibition asymmetry, and the
closed proprioceptive loop, while abstracting the commissural interneuron taxonomy
and the segmental stretch reflex that are not under test. The as-built diagram
(`fig_architecture_implemented.png`) and Table~\ref{tab:delays} are the ground
truth, generated from the network NEST actually constructs.
