# Figure 1 (human model): caption and notes

Figure: `fig1_architecture_human.png`, drawn by `scripts/cpg_architecture_human.py` from the projections that
`cpg_2legs_fast.py --species human` builds (architecture round of 2026-10-13). It replaces the conceptual schematic
`fig1_schematic.png` (rat-era) for the human paper.

## Caption

**Architecture of the two-leg human spinal CPG.** (A) Core circuit. Each leg has an extensor (E) and a flexor (F)
rhythm-generator half-centre (RG-E, RG-F) with recurrent excitation, coupled by reciprocal inhibition through the
interneurons InE and InF (strong F→E, weak E→F, 6:1; Zhang 2022). Each half-centre drives its motoneuron pool (M-E, M-F), which
drives a muscle proxy; the pools inhibit each other. The brainstem drive (BS to E, BS to F) reaches both legs through static
synapses (the human runs freeze BS→RG). The legs are coupled by direct inhibition between the rhythm generators (flexors strong,
extensors weak), which abstracts the V0-type commissural pathway. (B) Afferent wiring of one leg (the other is a mirror image).
Rate-coded Ia (spindle) and Ib (tendon organ) afferents and cutaneous (cut) afferents follow muscle force and length. Ia projects to
the rhythm generator through plastic synapses, to the homonymous motoneuron pool through static synapses, and to the Ia interneuron,
which inhibits the antagonist pool. Ib projects to its rhythm generator and to InE/InF through static synapses (group I load
loop). The cutaneous afferent excites RG-E through plastic synapses and reaches InE only through RG-E. The flexor Ia also
carries the hip-flexor stretch signal at swing onset. Not drawn: the tonic base drive (same targets as BS) and the rules that are not
wiring (RG-E load gate, force-triggered stance and swing, ankle coupling of the muscle lengths, interlimb load transfer).

## What changed against the old Figure 1 (and the rat-era text)

| Item | Old figure / text | Model (human) |
|---|---|---|
| Commissural pathway | V2a, V0v, V0d, In1 populations | no such populations: direct RG-F→RG-F (strong) and RG-E→RG-E (weak) inhibition; no V3 excitatory pathway, no Renshaw cells |
| Ia → motoneuron | direct arrow in the old figure; none in the model until 2026-10-13 | homonymous static Ia→M (6 pA, p 0.5, not calibrated) |
| Ib afferents | absent | Ib→InE/InF (load loop), Ib→RG-E/F (static) |
| Ia → RG | not plastic (Methods 3.5, rat-era) | plastic, Wmax-capped, all modes |
| Afferents → InE/InF | "Ia and cutaneous feed InE/InF" (caption) | Ib feeds InE/InF; Ia feeds RG, the Ia interneurons and the motoneurons; cut feeds RG-E only |
| CUT → InE | in the rat model | removed in the human model (`W_CUT2INE` 0) |
| Flexor swing afferent | separate group onto RG-F and InF (rat, and the human model before 2026-10-13) | a term of the flexor Ia (80 Hz at swing onset, τ 150 ms) |
| BS → RG | plastic (first version of this figure) | static: the human runs freeze BS→RG |
| Base drive, RG recurrent excitation, motor-pool reciprocal inhibition | absent | present |
| Rat-era constants in the Methods text (weights, P) | rat values | human values differ (see `config/species/human.yaml`) |
