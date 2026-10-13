# Figure 1 (human model): caption and notes

Figure: `fig1_architecture_human.png`, drawn by `scripts/cpg_architecture_human.py` from the projections that
`cpg_2legs_fast.py --species human` builds. It replaces the conceptual schematic `fig1_schematic.png` (rat-era) for the human paper.

## Caption

**Architecture of the two-leg human spinal CPG.** (A) Core circuit. Each leg has an extensor (E) and a flexor (F)
rhythm-generator half-centre (RG-E, RG-F) with recurrent excitation, coupled by reciprocal inhibition through the
interneurons InE and InF (strong F→E, weak E→F, 6:1; Zhang 2022). Each half-centre drives its motoneuron pool (M-E, M-F), which
drives a muscle proxy; the pools inhibit each other. The brainstem drive (BS to E, BS to F) reaches both legs through plastic
synapses. The legs are coupled by direct inhibition between the rhythm generators (flexors strong, extensors weak), which
abstracts the V0-type commissural pathway. (B) Afferent wiring of one leg (the other is a mirror image). Rate-coded Ia (spindle)
and Ib (tendon organ) afferents and cutaneous (cut) afferents follow muscle force and length. Ia, and the cutaneous input to
RG-E, project to the rhythm generators through plastic synapses; Ib projects to the rhythm generators and to InE/InF through
static synapses (group I load loop); cut also excites InE. Ia also drives the Ia interneurons, which inhibit the antagonist motoneuron
pool. An external flexor swing afferent excites RG-F and InF. Not drawn: the tonic base drive (same targets as BS) and the rules
that are not wiring (RG-E load gate, force-triggered stance and swing, ankle coupling of the muscle lengths, interlimb load transfer).

## What changed against the old Figure 1 (and the rat-era text)

| Item | Old figure / text | Model (human) |
|---|---|---|
| Commissural pathway | V2a, V0v, V0d, In1 populations | no such populations: direct RG-F→RG-F (strong) and RG-E→RG-E (weak) inhibition |
| Ia → motoneuron | direct arrow | none; Ia acts through RG and the Ia interneurons (reflex latency probe: 30 ms) |
| Ib afferents | absent | Ib→InE/InF (load loop), Ib→RG-E/F (static) |
| Ia → RG | not plastic (Methods 3.5, rat-era) | plastic, Wmax-capped, all modes |
| Afferents → InE/InF | "Ia and cutaneous feed InE/InF" (caption) | Ib (split afferent model) feeds InE/InF; Ia feeds the Ia interneurons and RG; cut feeds InE |
| Flexor swing afferent, base drive, RG recurrent excitation, motor-pool reciprocal inhibition | absent | present |
| Rat-era constants in the Methods text (weights, P) | rat values | human values differ (see `config/species/human.yaml`) |
