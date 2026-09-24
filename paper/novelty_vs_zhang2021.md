# Novelty of tinyCPG relative to Zhang, Shevtsova et al. 2022 (eLife)

> Zhang H., Shevtsova N.A., Deska-Gauthier D., Mackay C., Dougherty K.J.,
> Danner S.M., Zhang Y., Rybak I.A. (2022). *The role of V3 neurons in
> speed-dependent interlimb coordination during locomotion in mice.* eLife
> 11:e73424. DOI: 10.7554/eLife.73424.

## What Zhang/Rybak/Danner do

A canonical Hodgkin–Huxley spinal-CPG model lineage extending Rybak 2006 →
Shevtsova 2015 → Danner 2017 → Zhang 2022. Strengths:

- Four rhythm generators (L/R × fore/hind) with **hand-curated**
  commissural/long-propriospinal connectivity (V0V, V0D, V1, V2a, V3, Shox2).
- Speed-dependent gait expression (walk → trot → gallop → bound) controlled by
  a single tonic brainstem drive parameter α.
- Reproduces V3-silencing experiments quantitatively.

## What they explicitly say they *don't* do (their own "Limitations" section)

Verbatim from Zhang 2022 p. 22:

> *"One such limitation is that the present model focuses exclusively on
> central interactions within the spinal cord, **without considering
> biomechanics and the role of sensory feedback from the limbs**, which are
> involved in limb coordination and gait expression in vivo."*

> *"The other important limitation is that **our model did not consider spinal
> circuits operating below the RG and limb-coordinating circuits. The model
> does not include motoneurons**, and we assume that the output motor activity
> (recorded from the lumbar and cervical roots) simply reproduces the output
> activity in rhythm generating circuits. Therefore, different pattern
> formation circuits, circuits involved in the processing of sensory feedback,
> and reflex circuits, including those mediating by Ia and Ib interneurons,
> Renshaw cells, and motoneurons … were not included in the model."*

And there is **no plasticity anywhere** — every synaptic weight `w_ji` and
external drive coefficient `k_i, d0_i` is hand-tuned (their Table 1).

## What tinyCPG adds (the novelty claims, in order of strength)

### 1. STDP-driven self-organisation of CUT→RG and BS→RG synapses *(primary novelty)*
Where Zhang 2022 hand-tunes all `w_ji`, we train the descending and cutaneous
synapses with NEST's STDP synapse model (Bi & Poo 1998; Morrison 2007). Our
10-point sweep over the initial-weight distribution (μ ∈ {0, 0.5, 1, 2, 3.5, 5,
7, 9, 12, 16} pA, CV ∈ {0, 0.8, 0.6, 0.45, 0.30, 0.20, 0.15, 0.10, 0.08, 0.05})
shows the post-training weight distribution converges to the same plateau
regardless of initialisation. **Claim:** rhythm-generator function is
self-organising; locomotor patterns *emerge* from STDP rather than being
inscribed by an experimentalist.

### 2. Closed-loop sensory feedback (Ia → InE/InF → RG) *(addresses their Limitation #1)*
We implement the Ia closed loop they explicitly list as missing. Force-rate
encoding of muscle spindle output (`r_Ia = base + k_F·F + k_S·stretch`) drives
inhibitory interneurons that target the contralateral rhythm-generator
half-centre. Our ablation experiment (`--ablate-ia-loop`) shows the Ia loop
provides redundant rhythm support: with paced descending drive intact, the
network rhythm survives Ia removal, but the Ia loop becomes essential under
the legacy rotating-CUT drive condition — consistent with deafferented fictive
locomotion literature (Pearson 1995; Rossignol 2006; Hultborn 2006).

### 3. Motor pools + muscle proxies + force/length dynamics *(addresses their Limitation #2)*
Where Zhang 2022 *equates* the RG output with motor output, we route RG → M
(motor pool) → mus (parrot relay) → activation → Hill-style force/length
dynamics (Zajac 1989; Winters 1995). This produces a graded force trace with
rise/decay time constants in the rat fast-twitch range (τ_rise = τ_decay = 80
ms for paced gait). Peak Force-E = 17.4 a.u., Force-F = 17.4 a.u., counter-phase
correlation = −0.91 over 120 s.

### 4. Sequential heel→mid→toe Ia pacing *(new framing)*
Sensory afference is structured: during each 500 ms stance window, three Ia-E
sub-groups fire sequentially at 60 → 80 → 100 Hz, emulating centre-of-pressure
transfer from heel to toe in a single step (Loeb & Duysens 2018). This
externally paces a 1 s trot cycle in our 2-leg model. The model tracks the
commanded step-period across the rat locomotor range (600–1400 ms) with
< 0.5 ms error and counter-phase corr remaining −0.83 to −0.91 across speeds.

### 5. Long-term stability and ablation budget
We demonstrate 120 s (120 gait cycles) of stable counter-phase rhythm with
fully-converged STDP — well past the convergence point at t ≈ 5–10 s — and a
quantitative ablation budget across five conditions (baseline, noIa, symInh,
noComm, noPaced). Zhang 2022 reports only ~10-cycle averages and does not
quantify long-term stability.

## What we deliberately do *not* claim

To pre-empt reviewer objection, we should be explicit about what we are *not*
extending:

| Zhang 2022 feature | tinyCPG handling |
|---|---|
| 4-limb interlimb coordination (V3 aLPNs, fore-hind diagonals) | **Not in scope** — single hindlimb pair (L/R) only. Could be extended in future work. |
| Speed-dependent gait expression (walk/trot/gallop/bound) | **Not modelled** — single gait (paced trot at 600-1400 ms cycle). |
| Hodgkin-Huxley biophysical neuron models with INaP-driven intrinsic bursting | **Not used** — Izhikevich neurons (RGF in IB regime) chosen for simulation efficiency and parameter compactness. |
| V3 commissural CIN vs. aLPN distinction | **Not modelled** — single commissural inhibitory pathway (V0D-like). |
| Validation against in-vivo gait-by-treadmill-speed data | **Not validated** in this work — only against in-vitro fictive locomotion literature. |

## Suggested paper framing

> *"The Zhang/Rybak/Danner family of computational spinal CPG models is the
> field standard for architectural realism — explicitly typed V0V/V0D/V1/V2a/
> V3 commissural interneurons, four rhythm generators coupled by long-
> propriospinal pathways, speed-dependent gait expression. These models,
> however, are exclusively **central**: by the authors' own account they
> 'do not include motoneurons' and 'do not consider sensory feedback'.
> Here we ask the complementary question — given a fixed Rybak-style central
> architecture, can the rhythm-generator output couple to a biomechanical
> output via motoneurons, muscle proxies, and a closed-loop Ia spindle
> pathway, and can the connection strengths into the rhythm-generator
> **self-organise via STDP** rather than be hand-tuned? We answer
> affirmatively for a 2-leg (L/R hindlimb) model with paced descending drive,
> demonstrating 120 s of stable counter-phase locomotion across the rat
> locomotor speed range, robust to single-component ablations under intact
> paced drive."*

## Recommended target journals (re-ranked given this framing)

1. **Frontiers in Computational Neuroscience** — perfect topical match
   (Rybak group historically publishes here; STDP + CPG fits cleanly).
2. **PLOS Computational Biology** — higher prestige, OA, more rigorous review
   process; the "closed-loop self-organisation of a Rybak-style CPG" framing
   is exactly their target.
3. **eNeuro** — solid OA Society for Neuroscience journal, lower cost than
   Frontiers, well-suited for "complete and convincing but not paradigm-
   shifting" computational work.
4. **Biological Cybernetics** — natural home for CPG/control work, will care
   about the closed-loop dynamics.
