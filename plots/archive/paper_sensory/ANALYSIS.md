# Descending vs sensory learning — production results (2026-06-30)

Full 5-arm × 3-condition × 3-λ matrix at production N, 120 s/run. Metrics over
the last 20 s, leg L. corr = Pearson; rates Hz/neuron; weights pA.

## Headline findings

**1. Relocating the learning from descending (BS→RG) to sensory (Ia→RG) is free
at normal loading.** Across all three walking speeds the sensory arm matches the
descending control on counter-phase:

| speed | descending corr(F) | sensory corr(F) |
|---|---|---|
| 6 cm/s | −0.951 | −0.990 |
| 13.5 cm/s | −0.915 | −0.983 |
| 21 cm/s | −0.935 | −0.946 |

(λ=1e-3.) In the descending arm BS→RG only reaches ~15 pA (capped at 30) while
CUT→RG-E carries ~63; the sensory arm freezes BS weak and replaces that small
plastic BS contribution with an even lighter **~4.5 pA phased Ia→RG** loop — and
counter-phase is unchanged or better. The learning *trajectory* is identical
(CUT→63, slow λ=1e-5 transient still climbing at 120 s).

**2. Under unloading, sensory learning is partially self-rescuing — a regime the
natural (descending) arm cannot reach.** Three-way loading contrast (corr(F),
λ=1e-3):

| loading | stim (CUT intact) | **sensory (Ia→RG)** | natural (CUT gated) |
|---|---|---|---|
| baseline (1.0) | −0.915 | **−0.983** | −0.915 |
| toe (0.5) | −0.941 | **−0.988** | −0.703 |
| air (0.1) | −0.981 | **−0.541** | −0.359 |

- **Toe stepping (partial load):** the sensory arm nearly fully preserves the
  pattern (−0.99) where the natural arm has already degraded (−0.70). The plastic
  Ia→RG loop reinforces the rhythm from the proprioception that *is* still present.
- **Air stepping (no load):** the sensory arm degrades to −0.54 — better than
  natural (−0.36) but well short of stim (−0.98). This is the key limit: under
  total unloading the Ia feedback (gain 0.1) is the very input the sensory pathway
  learns from, so it cannot bootstrap a pattern from proprioception it no longer
  receives. Epidural-stim (CUT) bypasses this because its drive is load-independent.

**3. Mechanism — extensor maintenance.** RG-E mean rate vs loading (Hz/neuron):
stim 470→503→533 (rises, fully held), natural 470→286→132 (collapses), sensory
468→291→94. The natural arm shows the extensor collapse + flexor takeover
(RG-F 195→228→272); the sensory arm keeps Force-E/Force-F balanced (both ~17 a.u.)
down to toe, and recovers extensor force at air only for fast learning (λ=1e-3:
F-E peak 16.8 vs λ=1e-5: 11.5).

## Bio-plausibility reading

This reproduces the clinical/animal hierarchy:
- **Epidural stimulation (CUT)** restores load-independent stepping in SCI — robust
  across deafferentation (Lavrov 2008, Courtine 2009, Harkema 2011).
- **Proprioceptive training (Ia→RG)** improves weight-supported (toe) stepping but
  cannot substitute for load feedback during full unloading (air ≈ deafferentation)
  — Edgerton 2008, Takeoka 2014 (Ia afferents required for locomotor recovery).
- **Passive descending drive without either (natural, gated)** loses the pattern as
  load is withdrawn — the extensor collapse of fictive/unloaded preparations.

The novel model statement: *where the learning lives determines which rehab regime
it survives.* Sensory-sited plasticity self-rescues partial unloading but is
hostage to its own (gated) input under total unloading; descending/stim drive is
robust because it is exogenous to the sensory loss.

## Figures (this folder)

| File | Content |
|---|---|
| `fig_descending_vs_sensory.png` | Headline: (a) speed equivalence, (b) 3-way loading robustness, (c) extensor mechanism, (d) E/F balance. |
| `fig_stdp_sensory.png` | Sensory STDP weight matrix (CUT + Ia→RG, both legs × 3 speeds × 3 λ). |
| `fig_stdp_ablsens.png` | Sensory STDP weights across loading. |
| `fig_net_sensory_speed.png` | Full-circuit network activity, sensory arm, across speed. |
| `fig_net_ablsens.png` | Full-circuit network activity, sensory arm, across loading. |
| `fig_ia_sensory.png` / `fig_ia_ablsens.png` | Ia afferent activity, both legs. |
