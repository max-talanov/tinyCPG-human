# Bio-plausibility analysis — final model (flexor swing-afferent on)

Data: `results/2026-06-27` (speed×λ, ablation-stim) + `results/2026-06-25`
(ablation-natural, frozen). Figures: `plots/paper/final/`.

## Quantitative summary (speed × λ=1e-3, leg L)

| speed | cmd (ms) | measured (ms) | peak E | peak F | E duty | corr(E,F) |
|---|---|---|---|---|---|---|
| 6 cm/s  | 1200 | 1200.0 | 17.5 | 17.5 | 50 % | −0.97 |
| 13.5 cm/s | 520 | 519.6 | 16.7 | 16.8 | 62 % | −0.92 |
| 21 cm/s | 350 | 350.4 | 15.5 | 15.5 | 70 % | −0.94 |

## ✅ What is bio-plausible (correct behaviour)

1. **Flexor–extensor counter-phase.** Strong anti-phase (corr −0.92 to
   −0.97) at every speed and learning rate. This is the defining feature
   of the spinal half-centre oscillator (Graham Brown 1911; Brown's
   half-centre).
2. **Balanced E/F amplitudes.** With the flexor swing-afferent, peak E ≈
   peak F (≈ 1.0 ratio) — both half-centres are now equally driven, as in
   normal stepping. (Before the afferent, the flexor was weak and jittery.)
3. **Cycle period across the rat locomotor range.** 350–1200 ms spans rat
   slow-walk → trot (400–700 ms typical; Bellardita & Kiehn 2015; Lemieux
   2016), tracked to < 1 ms.
4. **L/R trot coordination.** The two legs run 180° out of phase
   (Fig. network-activity), the canonical alternating-gait pattern.
5. **Stance-extensor / swing-flexor afferent organisation.** The extensor
   is reinforced by stance cutaneous (load/paw-contact) and the flexor by
   the swing hip-afferent (joint position) — matching the known division
   that stance is load/contact-driven and swing is hip-position-triggered
   (Pearson 1995; Grillner & Rossignol 1978; Rossignol 2006).
6. **Epidural-stimulation rescue (Fig 9).** Natural unloading (cutaneous
   gated) collapses the rhythm (corr −0.92 → −0.34); with the paced
   cutaneous drive intact (stim analogue) the rhythm is preserved and even
   sharpened (−0.92 → −0.96). This reproduces the Courtine/Lavrov/Harkema
   finding that epidural stimulation restores stepping in spinal animals.
7. **Self-organisation of descending weights via STDP** to a stable
   attractor independent of initialisation (Phase A / earlier sweep).

## ⚠️ What is not (yet) bio-plausible — simplifications & artefacts

1. **Fixed 50/50 stance/swing duty.** `stance_fraction = 0.5` imposes a
   constant duty cycle. In real rats the **stance fraction decreases with
   speed** (slow walk ≈ 65 % stance, trot ≈ 50 %). Our duty is correct for
   trot but too short-stance for slow walk. *Fix:* make `stance_fraction`
   speed-dependent (longer stance at slow speeds).
2. **Force does not fully relax at fast gait.** At 21 cm/s (175 ms swing)
   the force decay constant (τ_F = 80 ms) is too slow to return the
   extensor to baseline before the next stance, so apparent E "duty" rises
   to 70 % (a filtering artefact, not a real duty change). *Fix:* shorten
   τ_F, or scale it with cadence.
3. **Single imposed gait.** The model paces one trot-like gait; it does
   **not** produce emergent speed-dependent gait transitions
   (walk→trot→gallop→bound) the way Zhang 2022 does via a single brainstem
   drive α. Our "speed" is an externally set step period, not an emergent
   property of descending drive.
4. **Two legs only.** No fore–hind limbs, no long-propriospinal / V3-aLPN
   interlimb coordination (the core of Zhang 2022). Diagonal/homolateral
   coordination is out of scope.
5. **Reduced neuron biophysics.** Izhikevich units, not Hodgkin–Huxley
   with persistent-sodium (INaP) bursting. Network-level rhythm is faithful;
   INaP pharmacology is not addressed.
6. **Burst rates are high in absolute terms.** RG peak rates reach
   ~500–1300 Hz/neuron during bursts (Fig. network-activity) — higher than
   biological single-unit rates; the population *pattern* is meaningful but
   absolute rates should be read qualitatively.
7. **Air-stepping failure is flexor-dominant.** Under natural unloading the
   extensor cutaneous is lost but the (un-gated) hip-afferent keeps the
   flexor clocked, so the failure mode is a tonic-flexor imbalance rather
   than a silent limb. This is a reasonable but untested prediction.

## Network-level analysis (interneuron-recording runs, results/2026-06-28)

### Circuit phase logic (medium walk, λ=1e-3, lag vs RG-E)
| population | phase | reading |
|---|---|---|
| RG-F, mus-F | 180° | flexor/extensor alternation |
| InF | 180° (with RG-F) | driven by RG-F, suppresses RG-E |
| InE | 0° (with RG-E)  | driven by RG-E, suppresses RG-F |
| IaInt-F/E | ~+60° after muscle | force-driven Ia lags motor onset |
| contralateral RG-E | 180° | L/R trot alternation |

The reciprocal-inhibition interneurons fire in exactly the phase that
suppresses the antagonist; the half-centre logic propagates RG→In→motor
correctly. Bio-plausible.

### Epidural-stim rescue dissected at the population level
Mean firing rate (Hz·neuron⁻¹), baseline → air stepping:

| population | STIM (CUT intact) | NATURAL (CUT gated) |
|---|---|---|
| RG-E | 470 → 533 (maintained) | 470 → **132** (collapses) |
| RG-F | 195 → 213 (stable) | 195 → **272** (takes over) |
| mus-E | 1213 → 1344 | 1213 → **555** |
| mus-F | 602 → 668 | 602 → **943** |
| IaInt-E/F | 287 → 20 (collapses) | 287 → 22 (collapses) |

Two conclusions: (i) the Ia interneurons collapse in *both* arms
(proprioception gated identically), so they are not what differs;
(ii) the entire difference is the **extensor** — cutaneous-intact (stim)
holds RG-E (470→533) and keeps E/F balanced, while cutaneous-gated
(natural) lets RG-E collapse (470→132) and the un-gated hip-afferent lets
the flexor take over. The cutaneous CUT→RG-E drive is the single quantity
that maintains the extensor under unloading; epidural stimulation rescues
stepping by substituting for it. The flexor-takeover under natural air
stepping is a testable prediction (unloaded unstimulated stepping should
show extensor weakening with relative flexor dominance).

## Bottom line
The model reproduces the core spinal-CPG phenomenology — flexor/extensor
alternation, L/R trot coordination, speed tracking across the rat range,
the correct stance/swing afferent split, and the epidural-stimulation
rescue — at the network-pattern level. The main departures from biology
are the **imposed (not emergent) gait and duty cycle** and the
**single-gait, two-leg scope**, all of which are deliberate simplifications
rather than errors.
