# tinyCPG-human — Two-Leg Human Spinal CPG (Debug Workspace)

NEST-based spinal central pattern generator, being adapted from rat to **human**
locomotion. Two legs (left/right), each with extensor + flexor half-centers, motor pools,
muscle proxies, Ia afferents, cutaneous afferents, and tonic brainstem drive. Trained with
STDP on BS→RG, CUT→RG and Ia→RG synapses, with optional tag-and-capture consolidation.
Production runs on the MN5 supercomputer; this workspace is for fast local iteration
before submitting array jobs.

This repo was forked on 2026-09-24 from tinyCPG
(`feature/spinal-tag-capture-consolidation`, remote `tinycpg`). **Everything from "Frozen-weight
control" down to "Sensory-driven mode" is inherited rat-model tuning history.** Its
numbers (periods, caps, fatigue τ, `tau_tag_ms`, correlations, MN5 result dates) are
rat-scale. They are a reference for how the mechanisms behave, not human operating
points. Read "Human adaptation" below first.

## Project goal

**Build and demonstrate a bio-plausible human spinal CPG model, both intact and after
spinal cord injury (SCI), whose gradual rehabilitation dynamics come from bio-plausible
spinal plasticity, and validate it against human data.**

Three parts of that claim, and what each one means here:

1. **Bio-plausible human spinal CPG.** Parameters stay within human physiological ranges
   (see "Bio-plausibility constraints (human)" below): human stride and stance/swing
   timing, human-scale conduction delays, human muscle contraction times. The circuit
   keeps the established spinal architecture: asymmetric reciprocal inhibition (Zhang
   2022), tonic reticulospinal drive, Ia/cutaneous closed-loop feedback, and L/R
   commissural coupling. Evidence for a human lumbar locomotor CPG comes from
   stimulation-evoked stepping-like EMG in complete SCI (Dimitrijevic et al. 1998). It
   should produce clean E/F counter-phase and L/R alternation across human walking
   speeds (slow, comfortable, fast).
2. **Healthy vs. SCI.** Reduced loading/afferent input (body-weight-supported stepping via
   `--ia-feedback-gain`/`--cut-feedback-gain`) and reduced or frozen descending drive
   (`--freeze-bs-rg`, the sensory-learning arm) stand in for the injured cord. Epidural
   electrical stimulation (EES), the main human SCI neuromodulation, is still to be
   added (see "Human adaptation"). The intact and injured conditions must be compared
   under the same circuit.
3. **Gradual rehabilitation through bio-plausible spinal plasticity.** Recovery has to
   emerge from spinal learning over a realistic time course. It should not snap back
   instantly. Human locomotor recovery with EES + training takes weeks to months
   (Harkema et al. 2011; Angeli et al. 2018; Gill et al. 2018; Wagner et al. 2018). Three
   pathways are plastic: BS→RG, CUT→RG-E and Ia→RG-E/F. Tag-and-capture consolidation
   (`--consolidate`, grounded in
   [`spinal_plasticity_as_learning_spec.md`](spinal_plasticity_as_learning_spec.md))
   adds a retention gate and a settling-in period on top of vanilla STDP. Closed-loop
   force-triggered stance/swing (`--cut-trigger force`) makes the gait itself emergent,
   so the learning signal comes from real behavior, not a clock.

Every mechanism, sweep and figure in this workspace should serve one of those three
parts. Current phase (as of 2026-09-24): the rat model is imported unchanged. No
human-parameter run has been done yet. Next is the human parameter pass described below.

Rat-model state at fork time (2026-09-23): the force-trigger + consolidation story was
being confirmed at production scale on MN5. Air stepping and medium+consolidate at
production N were still open.

## Human adaptation (tinyCPG-human)

### What `--species human` does today

**Since PLAN.md P1 (2026-09-24):** `--species <name>` loads `config/species/<name>.yaml`
(loader: `species_config.py`). The species file sets model constants, CLI defaults and,
**mandatorily, its own `delays:` section** (delay model, jitter, per-path table) in
the same file, so a species cannot run without its delays or with another
species' delays (D2); duplicate YAML keys are refused, and `--delay-model` is deprecated (accepted only if it
matches). Every output records the resolved config (`config_*` HDF5 attrs and a
`<out>.config.yaml` sidecar). Check a config with `python3 species_config.py human`
or validate all with `python3 species_config.py --check`.

What the human config contains is still mostly rat. Read this before assuming a
run is "human":

- Apart from the `delays:` section and `body.height_m: 1.74`, every value in
  `config/species/human.yaml` is still the rat value. Each block names the phase
  that replaces it.
- `FLEXOR_BS_GAIN` is `1.00`, the same as rat.
- **Human delays (PLAN.md P2, 2026-09-25).** Peripheral paths scale with body height
  (`length_frac_height` × `body.height_m`, 1.74 m); intraspinal paths stay ~1–2 ms.
  Estimates to verify (anthropometry, nerve-conduction norms):

  | Key | rat (ms) | human (ms) | human path |
  |---|---|---|---|
  | `ia_path` | 2.00 | 13.6 | soleus spindle → L5/S1, 0.47 H at 65 m/s |
  | `m_to_mus` | 2.00 | 15.9 | motoneuron → soleus/TA, 0.47 H at 55 m/s (+ NMJ) |
  | `cut_to_rg` | 2.00 | 23.6 | plantar sole → lumbar cord, 0.65 H at 50 m/s |
  | `bs_to_rg` / `base_to_rg` | 3.00 | 8.3 | medulla → lumbar cord, 0.25 H at 60 m/s |
  | `ia_int_to_m` (new in P2) | 2.00 | 1.5 | Ia interneuron → antagonist motoneuron (intraspinal) |
  | `rg_to_m`, `rg_rec`, `rg_recip`, `motor_*`, `commissural` | 1.2–2.2 | 1.2–2.3 | intraspinal |

  `ia_int_to_m` was split off `ia_path` in P2: the Ia-interneuron → antagonist
  motoneuron synapse used the afferent conduction delay before. Rat keeps the
  identical value and **reuses the `ia_path` NEST Parameter object** when the two
  entries are equal — two separate but identical random-delay Parameters draw
  differently in NEST (verified; even connection counts change).
- **Size-invariant wiring (PLAN.md P3b, 2026-09-26).** Human runs use `--conn-rule indegree`
  (fixed in-degree K = p × production source size, see `MOD_CONN_INDEGREE`); rat keeps the
  original `pairwise_bernoulli`. At production N both give the same behaviour (switch check
  11/11 metrics). Human `--debug-small` now keeps BS at 60 Hz, so human debug-small numbers
  from before 2026-09-26 are not comparable with new ones. `--n-scale s` scales every
  population for size checks (`run_p3b_local.sh`, `run_p3b_mn5.sh`).
- **Reflex-latency probe:** `python3 scripts/probe_reflex_latency.py --species human`.
  The model has no monosynaptic Ia → motoneuron connection (Ia reaches M-E through
  RG-E), so it measures the shortest causal Ia → muscle latency. It uses
  `--probe-reflex-at-ms` and determinism (identical control vs. volley runs; the first
  diverging spike). Result, rat-sh/debug.sh configuration: **human 30.2 ms** (median 30.9;
  RG-E 13.4 ms, M-E 14.8 ms), inside the 28–35 ms soleus reflex target; rat 5.0 ms.
- The Ia/CUT rates are recomputed from force/length in Python every `--rate-update-ms`
  (50 ms in `rat-sh/debug.sh`). That update lag is already larger than any synaptic delay.
  Account for it when matching the ~30 ms reflex latency.

### Rat → human parameter map

Human values are **starting targets, none tested yet**. Rat values are the current
inherited defaults (production script `rat-sh/run_consolidate_all_modes_production.sh` for
per-mode timing).

| Parameter | Where | Rat (current) | Human starting target | Basis |
|---|---|---|---|---|
| Stride period | `--step-period-ms` | medium 1000, fast 600, slow 1200, toe 730 | comfortable ~1000–1200; fast ~900; slow ~1300–1500 | Perry & Burnfield 2010; cadence ~100–120 steps/min |
| Stance fraction | `--stance-fraction` | 0.5 | ~0.6 at comfortable speed, falling toward 0.5 as speed rises | Perry & Burnfield 2010 |
| Walking speed (for reporting) | — | rat trot ~30 cm/s | comfortable ~1.2–1.4 m/s | Bohannon & Andrews 2011 |
| Failsafe stance/swing cap | `--cut-max-stance-ms` / `--cut-max-swing-ms` | medium 450 | rescale with the new stance/swing durations; must stay above genuine bout length or `frac_at_cap` → 1 | model constraint (see "Force-triggered CUT") |
| Fatigue onset / recovery τ | `--fatigue-tau-onset-ms` / `--fatigue-tau-recovery-ms` | medium 260 / 600 | rescale with bout duration, then re-sweep; the rat rounds 1–5 showed the τ/off-frac/cap window is narrow | rat history below |
| Force rise/decay τ | `TAU_FORCE_RISE/DECAY_MS` (80/80 under `--paced-gait`) | rat fast-twitch | slower: human soleus twitch time-to-peak is on the order of 100 ms (verify source) | to verify |
| Peripheral delays | `config/species/human.yaml` `delays.paths`: `ia_path`, `m_to_mus`, `cut_to_rg` | ~2 ms | ~10–20 ms each, so the full Ia reflex loop lands near ~30 ms | H-reflex latency, Palmieri et al. 2004 |
| Descending delay | `config/species/human.yaml` `delays.paths.bs_to_rg` | 3 ms | brainstem-to-lumbar is ~0.5 m in an adult; tens of ms at reticulospinal velocities (verify) | to verify |
| Tag decay τ | `--consolidate-tau-tag-ms` | 2000 / 5000 / 20000 (medium/fast/toe) | keep the rat rule (scale with bout length and loading), re-confirm per human mode | rat history below |
| BS tonic rate | `BS_REGULAR_HZ` | 60 (20 in debug-small) | keep 20–80 Hz; there are no direct human reticulospinal recordings, so this is a cat/rat proxy | flag if changed |
| CUT peak rate | `CUT_RATE_ON_HZ` | 100 | keep ≤100 Hz until checked against human plantar microneurography (Kennedy & Inglis 2002) | to verify |
| Reduced loading | `--ia-feedback-gain` / `--cut-feedback-gain` | 1.0 / 0.5 toe / 0.1 air | map onto body-weight-support levels used in human locomotor training | to define |
| STDP λ | `--stdp-lambda` | 1e-3 | unchanged; 5e-4 to 5e-3 (Bi & Poo 1998; Morrison 2007) are not species-specific | — |

### Work plan (in order)

1. **Human delays.** Rewrite the `delays:` section of `config/species/human.yaml` with real peripheral path lengths
   and conduction velocities. Check the resulting Ia loop latency against the ~30 ms
   H-reflex. Run `--dump-connectivity` to confirm the delay arrays.
2. **Human gait timing.** Add human mode presets (slow / comfortable / fast, plus
   body-weight-supported stepping) with stride period, stance fraction, caps, fatigue τ
   and `tau_tag_ms` rescaled together. Put them in a new `run_*_human.sh`, not in the
   rat scripts.
3. **Re-confirm the force-trigger operating point** at human timing. Run
   `scripts/cpg_cutforce_diagnostics.py` on every output; `frac_at_cap` near 1.0 means a
   disguised clock, exactly as in the rat history.
4. **Muscle model.** Slow the force τ toward human contraction times and re-check that
   force still reaches the CUT OFF threshold within a stance bout.
5. **SCI + EES.** Add a tonic epidural-stimulation afferent drive. Human EES at
   ~5–15 Hz tends to produce tonic extension and ~25–50 Hz rhythmic stepping-like EMG
   in complete SCI (Minassian et al. 2004). Compare healthy vs. SCI (frozen/weak BS,
   reduced loading) vs. SCI + EES + training on the same circuit.
6. **Validation.** Compare simulated EMG envelopes, stance/swing timing and L/R phase
   with human healthy and SCI recordings. `validation/emg_data_requests.md` currently
   lists **rat** datasets only; a human data list is still to be written.

Keep `--species rat` runs working throughout: the rat model is the regression baseline.

## Original debug-pass goal (historical, superseded by "Project goal" above)

Get cleaner E/F counter-phase and self-sustained rhythm with **reduced BS dependence**.
Specifically: the model should keep alternating when BS_REGULAR_HZ is dropped from 60 to
20 Hz, relying on Ia closed-loop feedback into the spinal reciprocal-inhibition core
instead of the brainstem.

This is bio-plausibility-motivated: deafferented fictive locomotion in rat preparations
runs on weak tonic drive plus intrinsic INaP bursting plus reciprocal inhibition. We
don't have INaP in Izhikevich neurons, so we approximate it with closed-loop sensory
feedback (Ia → InE/InF → RG).

## Quick start

```bash
# Human: the five locomotion modes locally (debug-small), then the stage figure
./run_modes_local.sh human 120000 1e-4
python3 scripts/cpg_modes_stages.py --species human

# Human reflex latency (target ~30 ms)
python3 scripts/probe_reflex_latency.py --species human

# After ANY model change: the rat must stay byte-identical
./regress.sh

# Rat reference only (comparison): local debug run, MN5 production sweep
./rat-sh/debug.sh
sbatch rat-sh/run.sh
```

## File map

| File | Purpose |
|---|---|
| `cpg_2legs_fast.py` | The model. Neurons, connections, sim loop, HDF5 export. |
| `scripts/` | Current figure/analysis scripts (feed `paper/figures/`), `cpg_param_table.py`, `cpg_plot_from_hdf5.py`, `build_deck.py`. |
| `scripts/legacy/` | Superseded figure scripts, kept for reference only — not used by the current paper. |
| `scripts/cpg_plot_from_hdf5.py` | Reads HDF5, makes per-leg PNGs. |
| `scripts/cpg_cutforce_diagnostics.py` | Pass/fail check for `--cut-trigger force` sweep outputs: corr(Force-E,Force-F) plus `frac_at_cap` (is the failsafe timer doing the work, or genuine force-threshold crossings?). Run before trusting any correlation number from this mode. |
| `rat-sh/run.sh` | MN5 SLURM array script (N=100, 10-point μ:CV sweep). |
| `rat-sh/run_speed_stdp.sh` | Phase A: 3 speeds × 3 λ {1e-5,1e-4,1e-3}, 120 s. (descending/BS-plastic arm) |
| `rat-sh/run_sensory_stdp.sh` | Sensory-learning arm: same 3×3 matrix but `--freeze-bs-rg --stdp-ia-rg --wmax-ia 10`. Pair with `rat-sh/run_speed_stdp.sh` for descending-vs-sensory contrast. Outputs `cpg_sensory_stdp_*`. |
| `rat-sh/run_ablation_sensory.sh` | Sensory-learning ablation arm: graded loading × λ with frozen BS + plastic Ia→RG (Ia is the *gated* learning drive). Outputs `cpg_ablsens_*`. Plot with `--mode ablsens`. |
| `rat-sh/run_ablation_graded.sh` | Phase B: 3 Ia gains × 3 λ, 120 s. |
| `rat-sh/run_frozen.sh` | Frozen-weight control: STDP off, air stepping, (mean,CV) sweep. |
| `rat-sh/debug.sh` | Local single-config run with `--debug-small`. |
| `rat-sh/` | **Rat reference scripts** (comparison and regression only; see `rat-sh/README.md`). Run from the repo root, e.g. `./rat-sh/debug.sh`. Superseded rat sweeps (`run_cutforce_sweep*.sh`, `run_cutforce_sensory_unload.sh`, `run_consolidate_speed_arm_loading.sh`, `run_speed.sh`, `run_ablation.sh`) were deleted 2026-09-25; restore from git with `git show c047f24:<name>.sh`. |
| `regress.sh` | **Rat regression check (PLAN.md P0). Run after every model change; it must print `ALL PASS`.** Re-runs `rat-sh/debug.sh` and `rat-sh/debug_force.sh` unmodified in a scratch directory and compares content digests against `results/golden/rat/MANIFEST.txt`. The golden `.h5` files are local and git-ignored. Runs at 4 threads; runs are reproducible since the B11/B12 fix. `./regress.sh record` re-records the golden run; do that only on purpose. |
| `scripts/regression_compare.py` | `compare A.h5 B.h5` gives a per-array diff of two outputs. `digest F.h5` gives a content hash that skips `created_utc`. |
| `species_config.py` | YAML species-config loader (PLAN.md P1). `python3 species_config.py <name>` prints the resolved config; `--check` validates all of `config/species/`. |
| `config/species/<name>.yaml` | One file per species: constants, CLI defaults, body, neuron profile and the `delays:` section (delay model + per-path table). Rat values equal the pre-P1 code. |
| `scripts/cpg_force_weights_panel.py` | Force + plastic weights over a whole run, both legs, extensor and flexor. |
| `scripts/cpg_force_weights_stages.py` | Force + weights at beginning / middle / end of a run, both legs. |
| `scripts/probe_reflex_latency.py` | PLAN.md P2 reflex-latency probe: shortest causal Ia → RG-E / M-E / muscle latency for a species (control vs. volley runs). |
| `scripts/cpg_gait_phase_metrics.py` | PLAN.md P3 gait-phase metrics from `cut_on` and force: stance fraction, double support, flight, measured stride, r(E,F), r(E_L,E_R), extensor activity and "neural double support". |
| `scripts/cpg_gait_phase_figure.py` | PLAN.md P3 figure: per-leg stance bars with double support shaded, and both legs' Force-E. |
| `run_modes_mn5.sh` | MN5 check A: SLURM array, 10 tasks (human five modes, then the rat reference) at production size, 120 s, CPU partition `gp_bsccs`, 1 h. Submit from the repo root: `sbatch run_modes_mn5.sh`. Local smoke test: `SLURM_ARRAY_TASK_ID=0 SLURM_CPUS_PER_TASK=4 SIM_MS=2000 bash run_modes_mn5.sh`. |
| `run_modes_local.sh` | The five canonical locomotion modes (slow/medium/fast walk, toe/air stepping; sensory-learning model) locally at `--debug-small`, for one species → `results/modes/<species>/`. |
| `scripts/cpg_modes_stages.py` | Force + weights at three stages for all five modes of one species (overview figure). |
| `rat-sh/debug_force.sh` | Local single-config run with `--debug-small --cut-trigger force` (closed-loop, force-triggered CUT — see below). |
| `rat-sh/run_consolidate_all_modes_production.sh` | **STAGE 5, prepared 2026-09-17, not yet submitted.** First production-scale (full N, BS=60Hz) test of `--consolidate` at the new uniform descending-arm gain (`0.25`/`0.10`) confirmed at `--debug-small` across medium/fast/toe (see "Fast/toe re-confirmed under the BS→RG write-back fix" below). 8 cells × 3 seeds = 24 tasks: {medium, fast, toe} × {desc, sens} with `--consolidate` at 0.25/0.10 (mode's own `tau_tag_ms`), plus slow × {desc, sens} without `--consolidate` (unchanged control). Deliberately does **not** apply the debug-small tick-de-alignment fix to medium's timing — at production's 100ms tick those constants are already not exact multiples, so the fix's premise may not transfer; see the script's own header for the full reasoning. Fast/toe's *base* timing (not just the gain) is itself still debug-small-only, flagged explicitly in the script. Flag construction dry-run-verified for all 8 cells; not submitted — `sbatch` is the user's call. |
| `CLAUDE.md` | This file. |
| `spinal_plasticity_as_learning_spec.md` | Literature-grounded spec for the `--consolidate` tag-and-capture mechanism (see "Tag-and-capture consolidation" below). Spinal-cord-only scope: §1 motor-circuit plasticity timescales, §2 the gating signals (serotonergic, contingency, structural), §3 nociceptive plasticity kept separate, §4 the mapping onto this model's three plastic pathways. All references verified against PubMed and cited by number. |

> **Inherited rat-model history starts here** and runs to "Sensory-driven mode". All
> timing, cap, fatigue and correlation numbers below are rat-scale (`--species rat`).
> Use them for mechanism behaviour and failure modes, not as human operating points.
> Scripts named below now live in `rat-sh/`, or were deleted on 2026-09-25 as superseded
> (`run_cutforce_sweep*.sh`, `run_cutforce_sensory_unload.sh`,
> `run_consolidate_speed_arm_loading.sh`, `run_speed.sh`, `run_ablation.sh`; restore with
> `git show c047f24:<name>.sh`).

## Frozen-weight control (`rat-sh/run_frozen.sh`)

Tests the Phase B two-regime hypothesis: that the descending-weight
*distribution* (not the learning dynamics) carries the counter-phase quality.
Sets STDP frozen (`--stdp-lambda 0`) and imposes a lognormal CUT→RGE
distribution of prescribed (mean, CV) via `--stdp-winit-dist lognormal_cv
--stdp-winit-mean <M> --stdp-winit-std <CV> --stdp-winit-bs-mean-mul 0.25`,
all at air stepping (`--ia-feedback-gain 0.1`). Two sweeps isolate the
mechanisms: **mean** sweep at fixed CV=0.02 (weakness), **CV** sweep at fixed
mean=63 (heterogeneity). Plot with `scripts/legacy/cpg_frozen_figure.py`. No `--sweep-pairs`
(non-sweep mode uses `--out` directly).

## Current model state (as of this debug session)

- **Paced-gait mode** (`--paced-gait`): explicit 1 s trot cycle (L/R 180° offset). Force-E peaks ~17 a.u.
  with clean flat-top 500 ms stance windows, drops to ~0 in swing. Force-F peaks ~5–7 a.u. in debug
  (limited by RGF burst rate at BS=20 Hz); production will be higher.
- Activation-E: square-wave plateau at ~1.2, clean reset to 0 each swing.
- L vs R desynchronised via commissural inhibition + paced external drive.
- **Known debug-mode limitation for F**: FF force limited to ~7 a.u. at BS=20 Hz; production (BS=60 Hz,
  N=100) expected to reach >12 a.u.
- Without `--paced-gait`: cleanly alternates in debug mode; corr(RGE,RGF) ~−0.71 to −0.73.

### Force-triggered CUT (`--cut-trigger force`)

Replaces the paced-gait *clock* with a closed-loop stance detector: CUT (cutaneous/
paw-contact) firing is gated directly on each leg's own `force_e`, not on a fixed
timer — "foot touches down" (CUT ON) when `force_e` rises through
`--cut-force-on-frac` (default 0.80) of that leg's current-bout running peak, "foot
lifts off" (CUT OFF) when it falls through `--cut-force-off-frac` (default 0.20). The
peak is **not** time-decayed — it resets to a seed value at each new stance onset and
then holds monotonically (grows through stance, frozen through the following swing).
A time-decaying peak was tried first and rejected: with `--muscle-fatigue` on, a
slowly-fatiguing force and a slowly-decaying peak converge together and the *relative*
OFF threshold never actually gets crossed — the leg locks at a permanently-reduced-but-
still-"on" plateau instead of releasing.

**Symmetry-breaking**: real gait doesn't start from identical L/R initial conditions —
one leg is already planted. `--leading-leg` (default `R`) seeds that leg into stance at
t=0. `--lead-offset-ms` (default 150 ms) is also a *symmetric priming window*: **both**
legs' CUT is ON for this duration (not just the leader's) so both sides' plastic
CUT→RG-E synapse gets co-activation training before the split — at low initial STDP
weight (production sweeps start as low as mean=0–3.5) the lagging leg's synapse
otherwise never gets its first potentiation and that leg struggles to ever mount a real
stance (confirmed by direct test: without priming, leading leg reached corr(Force-E,
Force-F) −0.92, lagging leg only −0.20). At the end of the window the lagging leg is
cut back to swing immediately; too long a window desyncs this into leg synchronisation
instead (confirmed at 400 ms: corr(Force-E_L, Force-E_R) flipped to **+0.41**, legs
moving together — a real failure mode, not just a weaker one).

**Failsafe timeout (required, not optional)**: RG-E has no INaP-style self-terminating
burst mechanism — only RG-F got the intrinsically-bursting Izhikevich treatment
(`RGF_C`/`RGF_D`). So `CUT → RG-E → force_e → CUT` is a pure positive-feedback loop:
force saturates near its ceiling and **just sits there** — confirmed by direct test
(production N, BS=60Hz, cap disabled): R stayed in stance with force_e flat at ~17.5
for 4+ continuous seconds, L stayed in swing at ~0 the whole time. `--cut-max-stance-ms`
/ `--cut-max-swing-ms` (both default 600 ms) cap each phase and force the transition
regardless of force — the endogenous-timer backstop for when peripheral gating alone
stalls (bio: hip-extension/limb-position limit triggers swing even under continued
loading, Grillner & Rossignol 1978; matches the two-level sensory-gated +
endogenous-timer picture, Rybak/McCrea unit-burst-generator model). **Do not remove
this timeout.**

**Debug-scale validated** (`rat-sh/debug_force.sh`, debug-small, BS=20 Hz, 10 s): both legs
alternate stance/swing continuously for the full run (7-8 bouts/leg, no lock-in),
corr(Force-E,Force-F) **−0.967 (L) / −0.967 (R)**, corr(RGE,RGF) **−0.83 (L) / −0.88
(R)**, corr(Force-E_L, Force-E_R) **−0.80**, Force-E peaks ~17.5 a.u. with clean
near-0 troughs.

**Production scale is NOT yet at the same bar.** At full N, BS=60Hz, step_period=520ms,
sweep-pairs 3.5:0.30 (the established operating point for `rat-sh/run_speed_stdp.sh` etc.),
the debug-tuned defaults only reach corr(Force-E,Force-F) ≈ **−0.65 (L) / −0.77 to
−0.85 (R)** over 8-20s, and bout-duration analysis showed transitions landing almost
exactly at the `--cut-max-stance-ms` value every cycle — i.e. the failsafe was doing
essentially *all* the work, not genuine force-threshold crossings (this is true at
debug scale too, on closer inspection — the "validated" debug numbers above are real
and clean, but likely cap-dominated rather than proof the pure threshold mechanism
alone is what's producing them).

**Correlation target recalibrated.** −0.85+ (the timer-based debug bar) is the wrong
target for this mode — that number is an artifact of the clock imposing a literal
square wave. A genuinely emergent, force-triggered gait should look more like
**−0.7 to −0.8**, with real cycle-to-cycle variability, once STDP has saturated. The
number that actually matters is **frac_at_cap** (below), not the correlation.

**`--muscle-fatigue` round 1** (`run_cutforce_sweep.sh`, results/2026-08-25, 9 tasks:
fatigue-onset-τ {200,400,600} × cap {500,800,1100}) found slower fatigue → better
force amplitude and correlation, apparently plateauing around τ=600/cap=800
(corr(Force-E,Force-F) ≈ −0.57 L / −0.69 R). **Re-diagnosed with exact ground-truth
`cut_on` logging (added after round 1 — see MOD_CUT_FORCE_TRIGGER) and that "best"
result turned out to be 100% cap-dominated on both legs** — stance duration exactly
800.0ms, zero variance, every single bout. Round 1's files predate the `cut_on`
array and can only be re-checked by reconstructing bouts from a force threshold,
which is unreliable (confirmed: reconstruction gave different at-cap verdicts on the
*same* file depending on the threshold chosen — see `scripts/cpg_cutforce_diagnostics.py`
docstring). **Trust `cut_on`-based ("exact") diagnostics only; treat any
pre-2026-08-27 result as unverified.**

**`--muscle-fatigue` round 2** (`run_cutforce_sweep2.sh`) inverts the round-1 fix
direction. Round 1's implied fix (bigger cap) is in tension with bio-plausibility
anyway — cap=800ms already exceeds the paper's own locomotor-cycle constraint
(400-700ms for a *full* stride, Bellardita & Kiehn 2015) for a single half-cycle.
Round 2 instead holds fatigue-onset-τ in the range that gave good amplitude/quality
(400-800ms) but *tightens* the cap toward bio-plausible half-cycle durations
(300-600ms), to test directly whether genuine crossings emerge under a realistic
time budget. **Result: 100% cap-dominated on both legs, at every one of the 9
tested combinations** (durations exactly equal to the cap, zero variance,
confirmed with exact `cut_on` ground truth — results/2026-08-27). A fatigue/force
overlay at the best-correlation config (τ=800/cap=600) explains why: `fatigue_e`
only reaches **~0.62 of its 0.95 ceiling** by the time the cap fires — force is
still ~70-80% of peak, nowhere near the 0.20 (`--cut-force-off-frac`) crossing
target. Neither axis tried in rounds 1-2 (fatigue speed, cap duration) alone
gets there — ruling out "hold τ in the good range, shrink the cap" as a fix.

**Round 3** (`run_cutforce_sweep3.sh`) tests the two remaining untried levers
together, cap held **fixed** at 450ms so any drop in `frac_at_cap` is
unambiguously attributable to them: fatigue-onset-τ pushed much faster (100,
150, 250ms — below round 1-2's 200-800ms floor) × `--cut-force-off-frac` loosened
(0.30, 0.40, 0.50 — vs 0.20 throughout rounds 1-2, so the crossing target no
longer requires near-complete decay). A 4s local smoke-test at τ=150/off=0.40
did escape cap-domination (`frac_at_cap`=0.00 both legs) but showed legs
synchronising (corr(Force-E_L,Force-E_R) = +0.88, the same failure mode seen at
`--lead-offset-ms 400`) — too short a run to judge properly, but a concrete
thing to watch for in the full 60s sweep.

**Round 3 result (results/2026-08-30): first round to escape cap-domination.**
`frac_at_cap` ≈ 0 on both legs across **all 9 configs**, with genuine bout-duration
variability (std up to ±52ms, vs. the flat zero of rounds 1-2) — confirmed with
exact `cut_on` ground truth. Quality still varies sharply within the grid: τ=100-150ms
gives short (~100ms), weak bouts and **legs synchronise in 5 of 6 of those configs**
(corr(Force-E_L,Force-E_R) up to +0.47 — the failure mode flagged above, now
confirmed for real, not just in a short smoke-test). τ=250ms (this round's ceiling)
gives the best results and stays anti-phase: best config τ=250/off=0.30 —
corr(Force-E,Force-F) −0.61(L)/−0.66(R), corr(Force-E_L,Force-E_R) −0.67, bout
duration 341±52/343±49ms. Still short of the −0.7/−0.8 recalibrated target, and
quality was still climbing with τ at the top of the tested range — round 3 ran out
of grid before finding a ceiling, not because τ=250 is optimal.

**Round 4** (`run_cutforce_sweep4.sh`) narrows into the region that actually
worked: fatigue-onset-τ {250, 300, 350} × `--cut-force-off-frac` {0.25, 0.30, 0.35},
cap still fixed at 450ms (round 3's value, the one that actually escaped
cap-domination — not re-testing the cap axis). Extends past round 3's τ=250
ceiling while staying well below round 1-2's τ=400+ floor where cap-domination
returned.

**Round 4 result (results/2026-08-31): the mechanism is more brittle than round 3's
trend implied.** 6 of the 9 configs **reverted to cap-domination** (frac_at_cap
0.97-1.00), including the numerically best-looking correlation in the whole grid
(τ=350/off=0.35: corr(Force-E,Force-F) −0.70(L)/−0.78(R) — but 97-100% cap-dominated,
a disguised clock exactly like round 1's trap, visibly confirmed by a perfectly
regular force waveform). Round 3's "higher τ → better" trend does **not** simply
continue — off-frac has to loosen *together* with τ, not independently: at τ=250,
off=0.30 and off=0.35 both stay genuine (frac_at_cap=0.00 both legs); at τ=300, only
off=0.35 is even mostly genuine (0.26/0.17, not clean); at τ=350, nothing in this
grid escapes the cap. **Best genuine result across all four rounds: τ=250/off=0.35**
— corr(Force-E,Force-F) −0.59(L)/−0.65(R), corr(Force-E_L,Force-E_R) **−0.72** (inside
the −0.7/−0.8 target), frac_at_cap=0.00 both legs, bout duration 292±45/292±56ms
(genuine ~16-19% cycle-to-cycle variability, visibly irregular waveform unlike the
τ=350 trap). τ=250/off=0.30 is the second genuine candidate, slightly weaker
(corr(Force-E_L,Force-E_R) −0.69).

**Round 5** (`run_cutforce_sweep5.sh`) is a small confirmation refinement, not a new
exploration: brackets the τ=250/off=0.35 optimum tightly — fatigue-onset-τ
{240, 250, 260} × `--cut-force-off-frac` {0.35, 0.375, 0.40} — to check the winning
point isn't a lucky single grid cell (i.e. small perturbations either side stay
genuine and don't collapse back into cap-domination the way τ=300/350 did just
0.05-0.10 higher on off-frac). Same cap=450ms, same operating point, same 60s length
as rounds 1-4.

**Round 5 result (results/2026-09-01): confirmed — the whole neighborhood is
genuine, not just one lucky cell.** `frac_at_cap` = **0.00 on both legs, all 9
configs**, exact ground truth. Correlation is stable and good across the whole
grid: corr(Force-E,Force-F) −0.52 to −0.63 (L) / −0.60 to −0.67 (R), corr(Force-E_L,
Force-E_R) **−0.65 to −0.73** (every config strongly anti-phase, no synchronisation
anywhere in this grid). **Best point: τ=260/off=0.35** — corr(Force-E,Force-F)
−0.63(L)/−0.67(R), corr(Force-E_L,Force-E_R) −0.71, bout duration 308±27/310±29ms
(tightest, most consistent spread of any genuine result so far, ~9% relative
variability). This closes out the "fix cap-dominance" step of the maturation plan:
`--cut-trigger force --muscle-fatigue` with τ≈240-260ms, off-frac≈0.35-0.40, cap=450ms
is a demonstrated, robust, genuinely closed-loop operating point — not confirmed
across other STDP init points yet (Phase 3, next).

**Phase 3 — seed/init robustness** (`run_cutforce_sweep6.sh`) holds the round-5
winning config fixed (τ=260, off-frac=0.35, cap=450ms) and instead varies the STDP
initial-weight distribution across the same 10-point (μ,CV) diagnostic grid the
base timer-based model already uses for its own robustness claim (paper Algorithm 1
/ `rat-sh/run.sh`) — reusing the project's established methodology rather than inventing a
new one, so the two are directly comparable. Every round so far (1-5) tested only
μ=3.5,CV=0.30; this asks whether the mechanism holds at μ=0 and μ=16 too, the real
stress tests. 120s sim (matching Algorithm 1's own duration, not the 60s first-pass
length used in rounds 1-5) since this is confirmatory, not exploratory.

**Round 6 — partial result, 8/10 in (results/2026-09-07), very good so far.**
μ=0 through μ=9 (idx00-07) all confirmed genuine: `frac_at_cap` ≈ 0.00-0.01 on both
legs at every point, corr(Force-E,Force-F) tightly clustered −0.63 to −0.69 regardless
of initial weight, corr(Force-E_L,Force-E_R) −0.68 to −0.76 (tighter than round 5).
Bout-duration variability *shrinks* as μ increases (±39-46ms at μ=0-1 down to
±20-27ms at μ=5-9) — more initial synaptic drive needs less from the stochastic
bootstrap. STDP weight trends confirm the same initialization-independence the base
timer-based model already shows (paper §4.1): μ=0 (CUT→RG-E starts at 0 pA) and μ=9
(starts ~10-11 pA) converge to the identical ~62 pA plateau. **μ=12 (idx08) and μ=16
(idx09) — the two highest-weight stress tests — are still pending on MN5; do not
treat Phase 3 as closed until those land.**

**Required workflow from now on**: run `scripts/cpg_cutforce_diagnostics.py` on every
sweep output before trusting any correlation number. `frac_at_cap` near 1.0 on either
leg means the result is a disguised clock, regardless of how clean the correlation
looks.

### Muscle fatigue (`--muscle-fatigue`)

Opt-in (OFF by default — existing timer-based paced-gait runs are unaffected). Adds a
slow activity-dependent attenuation to the force proxy (both E and F): fatigue builds
toward `--fatigue-max-frac` (default 0.95) with time constant `--fatigue-tau-onset-ms`
(default 400 ms) while activation is high, and clears with `--fatigue-tau-recovery-ms`
(default 600 ms) while activation is low. This is what lets `force_e` actually decay
during a sustained stance bout instead of sitting flat at its ceiling forever (see
"Failsafe timeout" above) — the closest local analogue to the INaP-driven burst
termination the project's Izhikevich neurons don't have.

**`--fatigue-max-frac` must leave the fatigued force floor comfortably below the OFF
threshold**, or the leg locks at a reduced-but-still-"on" plateau instead of actually
releasing — confirmed at 0.85: force settled at a stable floor (~2.6, from residual
activation even at full fatigue) against an off-threshold of ~1.9 and never crossed it.
0.95 leaves a floor of ~0.9, safely below a typical off-threshold — this is why the
default was raised from the first value tried.

### Core architecture fix: Ia→RG-E/F now a standing plastic pathway (2026-09-14)

While chasing why force-triggered CUT can't be rescued by more Ia drive under
simulated unloading (see "Force-triggered CUT" above), a reference architecture
diagram (`CPG_feedback_loops_mems.png`) surfaced a real gap: it shows a **direct
excitatory Ia→RG-E/F projection**, separate from the existing `Ia→InE/InF`
reciprocal-inhibition loop (MOD_IA_LOOP). The code already had this exact synapse
(`stdp_ia_rge`/`stdp_ia_rgf`) but only wired it behind `--stdp-ia-rg`, i.e. only in
the sensory-learning arm. Decision (explicit user call, given the choice between
scoping this to force-trigger only vs. universal): **make it universal** — Ia→RG-E/F
is now always wired and always plastic, in every mode, alongside BS→RG and CUT→RG
(BS→RG still drops out under `--freeze-bs-rg`; Ia→RG and CUT→RG never do). A fixed
weight here was considered and rejected — the paper's whole point is
plasticity/rehabilitation, so a static baseline couldn't represent that; three
simultaneously plastic pathways is the new standing model.

**Consequence: every existing figure/sweep in the paper was generated on a circuit
missing this pathway** and needs regenerating — this is now "regenerate the paper's
evidence base," not a small patch. See `~/.claude/plans/virtual-forging-owl.md` for
the full rollout.

**Smoke test — base timer-based descending arm (`rat-sh/debug.sh`, unchanged flags, just
the new circuit):** results improved, didn't regress. corr(Force-E,Force-F)
−0.70(L)/−0.78(R), corr(RGE,RGF) −0.72 both legs, corr(Force-E_L,Force-E_R) **−0.98**.
Notably, **the long-standing weak-flexor debug problem looks fixed for free**:
Force-F peak was previously capped ~5-7 a.u. at BS=20 Hz (see "Known debug-mode
limitation for F" above) — with the new pathway it reaches **17.2-17.3**, matching
Force-E, without touching `--freeze-bs-rg`/`--stdp-ia-rg` at all. Converged weights
sane: bs→rge/rgf ~18, cut→rge ~63 (consistent with prior baselines), ia→rge ~5.2,
ia→rgf ~5.9-6.1 (well under WMAX_IA=10 cap).

**Smoke test — force-triggered CUT at the confirmed operating point (τ=260/off=0.35/
cap=450), descending arm, new circuit, 60s debug:** corr(Force-E,Force-F)
**−0.81(L)/−0.84(R)** (better than the old-circuit confirmed values of −0.63/−0.67),
corr(Force-E_L,Force-E_R) −0.25 (anti-phase, not synchronized), `frac_at_cap`
0.06-0.07 (close to genuine, not the old circuit's clean 0.00 — expected, since this
operating point was tuned on the old circuit; Phase 1 of the rollout plan is to
re-confirm/re-tune it on the new one, not assume it transfers exactly).

**Re-confirmation, steady-state (2026-09-15) — the operating point holds; the
0.06-0.07 above was the same recovery-transient artifact found throughout the
`--consolidate` tuning work, not a persisting regression.** Re-ran the identical
operating point at two seeds (12345, 54321) and applied
`scripts/cpg_cutforce_diagnostics.py --steady-from-ms 30000` (built during the
`--consolidate` tuning rounds specifically because whole-run `frac_at_cap`
conflates an early settling period with steady-state behavior — see "Tag-and-
capture consolidation" below). Steady-state: `frac_at_cap` **0.00/0.00 in both
seeds** (even cleaner than the whole-run 0.01/0.00-0.01), corr(Force-E_L,
Force-E_R) reproducibly negative in both (−0.286, −0.529) — no synchronization.
**This operating point is confirmed still genuine on the current (post-2026-09-14)
circuit at debug scale**, closing the "not yet re-tuned" flag above. Not yet
checked at production N/BS=60Hz (see CLAUDE.md's own MN5 checklist), and this
confirmation is a prerequisite for, not a substitute for, defining a force-trigger
speed axis (see `~/.claude/plans/resilient-soaring-flamingo.md` Stage 1) — this
single point remains one fixed timing, not a speed sweep.

**Sensory arm re-tested at baseline loading, new circuit:** stable and improved — 60s
debug, corr(Force-E,Force-F) −0.81(L)/−0.79(R), `frac_at_cap` 0.05-0.06,
corr(Force-E_L,Force-E_R) properly anti-phase (though its exact value bounces between
runs at debug scale, consistent with the already-noted L/R-metric instability at this
scale — per-leg metrics are the stable/trustworthy ones here).

**Unloading-rescue attempt — round 1: loading-dependent Ia→RG weight cap
(`--wmax-ia-unloaded`, MOD_IA_RG_LOADING_GAIN).** Boosting `--ia-feedback-gain` alone
(up to 8x) never rescued force under `--cut-feedback-gain 0.1` because the real
bottleneck wasn't the input rate, it was the Ia→RG-E STDP weight ceiling (WMAX_IA=10,
deliberately low so Ia stays a light boost when CUT is present at full strength —
raising it there destroys counter-phase, already validated). Fix: `WMAX_IA` now
linearly relaxes toward a new `--wmax-ia-unloaded` (default 60) as `--cut-feedback-gain`
drops from 1→0, so Ia can only take over more excitatory drive when cutaneous input is
genuinely reduced. Bio-plausible framing: post-SCI/deafferentation upregulation of
spinal sensory gain (central sensitization), not an arbitrary knob. At full loading the
effective cap is unchanged (=10, confirmed). Result at gain=0.1 (effective cap→55):
Ia→RG-E weight grew from ~4.5 (fixed-cap case) to ~30 pA, force_e max rose from ~1.6 to
~8 (vs. the normal ~17 ceiling) — real progress, not yet a clean rescue.

**Unloading-rescue attempt — round 2: loading-dependent peak-force seed
(`CUT_FORCE_PEAK_SEED_MIN_FRAC`).** With force now reaching ~8 but the Schmitt
trigger's adaptive-peak tracker still seeded at a fixed 10 (calibrated for the normal
~17 ceiling), the seed sat permanently *above* the achievable peak, so it never adapted
and on/off thresholds were meaningless relative to the leg's actual force scale (bout
durations were a degenerate 50±0ms — chattering every tick). Fix: the seed itself now
scales down with loading too (`CUT_FORCE_PEAK_SEED_FRAC * (0.5 + 0.5*cut_feedback_gain)`
— floor at half its full-loading value, not fully to zero, to avoid a pathologically
noise-sensitive trigger). Result: bout durations became real again (257±166ms/
295±159ms, still noisy) instead of degenerate chatter, `frac_at_cap` 0.23-0.33 (down
from chattering, but not yet genuine), corr(Force-E,Force-F) still weak (−0.18 to
−0.22) — **the mechanism now runs instead of degenerating, but hasn't converged to a
clean rescue within 60s debug scale.** This needs its own proper tuning round (longer
duration, on/off-frac retuning for the lower force ceiling, maybe a gain/cap-ratio
sweep) — the same kind of multi-round search Phase 3 rounds 1-6 needed, not a
one-shot fix.

**Local tuning attempted, did not converge — moved to production-scale test
(`run_cutforce_sensory_unload.sh`) instead of continuing to guess locally.**
Systematically varied duration (60/120s), `--ia-feedback-gain` (1/2/4/6/8/12),
`--cut-feedback-gain` (0.1/0.5, air/toe), and the on/off-frac hysteresis band
(0.80/0.35 baseline, 0.85/0.25, 0.90/0.20, 0.80/0.20) at debug-small scale.
Findings: (1) `frac_at_cap` goes low (0.00-0.04) at longer duration (120s) with the
*original* on=0.80/off=0.35 thresholds — widening or narrowing the hysteresis band
made it worse (0.29-0.94), so retuning that axis isn't the lever; (2) force ceiling
converges to ~7-9 (about half the normal ~17) regardless of gain 4-12 or loading
0.1-0.5 — a real plateau, not a transient; (3) `ia->rge` weight converges to ~29-30 pA
regardless of gain, well below the relaxed cap (35-55 depending on loading) — so it's
not cap-limited either, it's a genuine dynamical fixed point of the current STDP
setup; (4) **corr(Force-E,Force-F) stayed weak (−0.13 to −0.26) across every
combination tried**, including toe-stepping (a much milder condition than air —
essentially the same weak result, −0.13/−0.15). A flat, unmoving result across such a
wide parameter search, right after two structural fixes that were each individually
necessary just to get the mechanism running at all, looks like a debug-scale ceiling,
not a dead end: **`N_IA_E`/`N_IA_F` drops from 100 (production) to 30 at
`--debug-small`** (cpg_2legs_fast.py:1116-1117) — 3.3x fewer Ia units at the same
connection density feeding the new pathway, which may cap the aggregate Ia→RG-E
current well below what production N could deliver, independent of weight/gain
tuning. This is the same debug/production divergence pattern this project has hit
repeatedly (see the original force-trigger debug-vs-production gap noted earlier in
this section). `run_cutforce_sensory_unload.sh` tests this directly: production N,
3×3 grid of loading (`--cut-feedback-gain` 1.0/0.5/0.1) × Ia compensation
(`--ia-feedback-gain` 1.0/4.0/8.0), sensory arm (`--freeze-bs-rg`), 120s, otherwise
the confirmed operating point unchanged. Not yet submitted.

### Tag-and-capture consolidation (`--consolidate`, 2026-09-15)

**BS→RG write-back fix (2026-09-17) — read this before trusting any
descending-arm number below.** Every result in this section (gain searches,
Stage 2/3, the fast/toe `tau_tag_ms` extension, the medium tick-alignment
investigation) was generated when `BS→RG`'s consolidation bookkeeping was
tracked but never written back to NEST — `BS→RG` was vanilla-STDP-only in
practice the entire time, regardless of `--consolidate`. Fixed at explicit
user request: `consolidate_behavioral_keys` (the set that actually gets the
tag-leak write-back) now includes `bs->rge`/`bs->rgf` whenever they're
plastic, exactly like `cut->rge`/`ia->rge`/`ia->rgf` always did. Confirmed
live by direct test: `bs→rge` now converges to ~4.4\,pA under consolidation
(descending arm, medium timing, gain 0.20/0.15) instead of its natural
~18\,pA plateau — a real, substantial behavioral change, not a no-op.
**Consequence: every descending-arm (non-`--freeze-bs-rg`) `--consolidate`
number in this entire section — gain confirmations, `tau_tag_ms` values,
the medium/fast/toe operating points, all of it — predates this fix and
needs re-confirmation.** The sensory arm (`--freeze-bs-rg`) is unaffected,
since `BS→RG` isn't plastic there regardless. Do not treat any
descending-arm `--consolidate` claim below as current until re-checked.

Motivated by the unloading-rescue plateau immediately above and the round 1-6
tuning history: every search so far looked for a **static** fixed point of
gain/cap parameters, and rounds 1, 2 and 4 kept reverting to
`frac_at_cap`-dominated (disguised-clock) results under small perturbations.
[`spinal_plasticity_as_learning_spec.md`](spinal_plasticity_as_learning_spec.md)
(literature review, written this session) argues the mechanistic reason:
vanilla STDP with a fixed `Wmax` has no way to tell "genuine progress" apart
from "an artifact of a degenerate (failsafe-forced) bout" and un-learn the
latter — every potentiation is kept permanently. Real spinal plasticity has an
explicit retention gate absent here: Sandkühler's spinal dorsal-horn E-LTP/
L-LTP (protein-synthesis-dependent, BDNF/D1-D5-gated), Grau's contingency-
gated spinal instrumental learning (non-contingent outcomes actively
*suppress*, not just fail to reinforce), and Wolpaw's two-phase H-reflex
conditioning (a fast Phase I, a slow multi-site Phase II) on exactly the
Ia→motor pathway this model has.

**Mechanism** (full design: `~/.claude/plans/resilient-soaring-flamingo.md`):
NEST's native `stdp_synapse` keeps driving `weight` exactly as before (the
fast, local, per-synapse tag-setting process). A new per-connection
`baseline` is the captured/stable component; the live tag
(`weight − baseline`) decays toward it with time constant
`--consolidate-tau-tag-ms` at every gate tick, unless a shared per-leg
PRP-pool-like accumulator crosses `--consolidate-prp-threshold` first — genuine
(real force-threshold) bout endings push the pool up via
`--consolidate-prp-gain-genuine`, failsafe-forced ones push it down (steeper,
via `--consolidate-prp-gain-forced`), and crossing the threshold freezes
`baseline := weight` for every connection in that pathway/leg (a capture
event). `Wmax` is untouched throughout — this governs retention *within* the
existing ceiling, not the ceiling itself. Applies to `CUT→RG-E` and
`Ia→RG-E/F`; `BS→RG` gets identical bookkeeping logged for measurement
symmetry only and is never written back (weak literature support for
touching `WMAX_BS`'s documented anti-runaway role — spec doc §4). Scoped to
`--cut-trigger force` only (the only mode with a genuine-vs-failsafe-forced
bout-boundary signal to gate on); raises at start-up if passed without it.

**First-pass verification (debug-small, this session) — mechanism confirmed
working, default parameters do not yet show a self-correction benefit.**
Three checks:

1. *Regression*: `rat-sh/debug_force.sh` unmodified (no `--consolidate`) is
   byte-for-byte unaffected — confirmed, the flag is a true no-op when absent.
2. *Mechanism sanity* (a naturally-occurring falsification-test case): the
   plain `rat-sh/debug_force.sh` config has no `--muscle-fatigue`, so every bout is
   failsafe-forced (`frac_at_cap`=1.00 both legs, confirmed) — a run where
   `prp_pool` can only ever decrease. With `--consolidate` on, `baseline`
   stayed exactly flat at its t=0 init the entire 10s run on all three
   pathways (`prp_pool` never left 0) while `weight` visibly drifted away
   from it (`cut→rge`: baseline 22.2, live weight 34.6) — directly confirming
   the tag/capture split is doing real, inspectable work: an unreinforced
   potentiation shows up as a persistent gap from baseline instead of being
   silently retained the way vanilla STDP would.
3. *Self-correction hypothesis* (the actual target): re-ran the round-5
   operating point (τ=260/off=0.35/cap=450, 60s, new Ia-direct-pathway
   circuit) and round 4's brittle τ=300/off=0.30 point, with vs. without
   `--consolidate`. Results were **mixed, not positive**: at the round-5
   point (already near-genuine post-architecture-fix, `frac_at_cap`
   0.00-0.01 without consolidation), turning consolidation on made it
   slightly *worse* (0.10-0.12) — with the default gain ratio
   (`prp_gain_forced`=0.30 vs `prp_gain_genuine`=0.15) and this config's
   roughly even genuine/forced mix (~69/71 events each over the run),
   `prp_pool` net-decays to 0 almost every cycle and **capture never once
   triggered** on any pathway, so `Ia→RG` sat capture-starved near its low
   init the whole run instead of being allowed to reach the level that
   otherwise helps stabilize genuine crossings. At round 4's fully-degenerate
   point (100% `frac_at_cap` from the start, zero genuine bouts ever),
   consolidation made **no difference** (still 100% both legs) — with no
   genuine bouts to ever seed a PRP increment, there is nothing for the
   mechanism to bootstrap from; it cannot rescue a starting point that never
   produces the signal it depends on.

**Conclusion: implementation is correct and behaves exactly as designed
(confirmed by direct state inspection, not just aggregate correlation
numbers), but the first-pass default constants
(`tau_tag_ms`=2000, `prp_threshold`=1.0, `prp_gain_genuine`=0.15,
`prp_gain_forced`=0.30) do not yet demonstrate the hoped-for self-correction
benefit and need their own local tuning round** — the same multi-round
process Phase 3 (rounds 1-6) needed, not a one-shot fix. Two concrete levers
for that round: (a) the genuine/forced gain ratio is currently the most
aggressive part of the default (2:1) and may be actively starving capture at
borderline operating points — worth trying a shallower ratio or a lower
`prp_threshold` first; (b) the mechanism has no way to help a 100%-forced
starting point recover on its own — if that turns out to matter, it would
need either an exploration term (occasional stochastic relaxation of the
failsafe) or accepting that this mechanism only refines already-partially-
working operating points rather than rescuing fully broken ones. Also note:
bookkeeping overhead roughly doubled with `--consolidate` on (77-83% of wall
time vs. ~50% without, at 60s debug-small) from the added per-tick
`GetStatus`/`SetStatus` round trips — fine at debug scale, but worth
profiling before any production-scale use.

**Round 1 tuning (2026-09-15) — gain ratio, not threshold or `tau_tag`, is the
lever.** All runs at the round-5 operating point (τ=260/off=0.35/cap=450,
60s, new circuit), varying `--consolidate-prp-gain-genuine`/`-forced`/
`-prp-threshold` against the no-consolidate baseline (`frac_at_cap`
0.01/0.00, corr(F-E,F-F) −0.655/−0.661, corr(F-E_L,F-E_R) −0.263) and the
shipped defaults (0.15/0.30/1.0 — confirmed above to never capture):

| genuine/forced/threshold | captures L/R | `cut→rge` gap (weight−baseline) L/R | `frac_at_cap` L/R | corr(F-E,F-F) L/R | corr(F-E_L,F-E_R) |
|---|---|---|---|---|---|
| 0.15/0.30/1.0 (shipped default) | 0 / 0 | +12.1 / +12.3 | 0.12 / 0.10 | −0.540 / −0.703 | −0.491 |
| 0.15/0.15/1.0 (symmetric) | 0 / 0 | +12.2 / +12.7 | **0.32** / 0.12 | −0.522 / −0.609 | **+0.009** |
| **0.20/0.15/1.0** | 3 / 4 | +4.9 / +1.1 | 0.10 / 0.13 | −0.541 / −0.606 | **−0.724** |
| 0.25/0.15/1.0 | 7 / 7 | +0.5 / +0.0 | 0.07 / 0.03 | −0.583 / −0.688 | **+0.273** |
| 0.20/0.10/1.0 | 7 / 7 | +1.0 / +0.0 | 0.06 / 0.06 | −0.548 / −0.660 | −0.462 |
| 0.20/0.15/0.5 | 9 / 9 | +0.1 / −0.2 | 0.07 / 0.03 | −0.476 / −0.674 | **+0.242** |

Three findings, none of them "just raise the gain":

1. **Symmetric gain (1:1) does not fix the never-captures problem** and makes
   `frac_at_cap` *worse* (0.32) than the 2:1-suppressive shipped default —
   at this operating point's roughly-even genuine/forced mix (~68 genuine /
   71 forced events over 60s), even-money gain still nets slightly negative
   most of the time, so this isn't a knob that can be nudged gently; it needs
   to cross into genuine-favoring territory before anything changes.
2. **A mildly genuine-favoring ratio (0.20/0.15, i.e. ~1.3:1) is the best
   single point found**: captures actually happen (3-4, not 0), `cut→rge`'s
   baseline moves to ~55-57 pA (up from stuck at its ~22 pA init — real
   consolidation, not a rounding artifact), and `frac_at_cap` stays
   comparable to the shipped default (no worse). It also gives by far the
   best L/R desynchronization of everything tested (corr(F-E_L,F-E_R)
   −0.724, vs. −0.263 with no consolidation at all).
3. **Pushing further in the same direction (more genuine bias, or a lower
   threshold) is not monotonically better — it actively synchronizes the
   legs.** 7-9 captures converges `cut→rge`'s baseline to ~63 pA (matching
   this pathway's known natural STDP plateau almost exactly — the mechanism
   is doing something coherent, not just drifting), but corr(F-E_L,F-E_R)
   flips **positive** at every more-aggressive setting tried (+0.273, +0.242)
   except 0.20/0.10 (−0.462, still worse than 0.20/0.15's −0.724). The
   likely mechanism: capturing too easily and too often lets both legs'
   `cut→rge` converge to the *same* stable plateau independently, removing
   the run-to-run asymmetry that keeps the two legs desynchronized — a
   genuine over-consolidation failure mode, not a tuning artifact to shrug
   off.

**Status after round 1: promising lead, not yet confirmed.** 0.20/0.15/1.0
was the best point from a single round, at a single operating point and
seed — not yet bracketed or re-checked at a second seed, the same standard
every other constant in this file was held to before being called
"confirmed" (cf. Phase 3 rounds 1-6).

**Round 2 confirmation (2026-09-15) — bracket 0.15-0.25 (genuine) ×
0.10-0.20 (forced) at a second seed (54321 vs. round 1's 12345), same
round-5 operating point, `tau_tag_ms` still untested/held at 2000 (not part
of this round's scope):**

| genuine/forced | captures L/R | `frac_at_cap` L/R | corr(F-E,F-F) L/R | corr(F-E_L,F-E_R) |
|---|---|---|---|---|
| no-consolidate (reference) | n/a | 0.03 / 0.01 | −0.607 / −0.663 | −0.286 |
| 0.15/0.10 | 3 / 3 | 0.06 / 0.06 | −0.487 / −0.653 | −0.559 |
| 0.15/0.15 (symmetric-ish) | 0 / 0 | 0.14 / 0.09 | −0.417 / −0.570 | **+0.194** |
| 0.15/0.20 | 0 / 0 | 0.10 / 0.13 | −0.374 / −0.486 | −0.637 |
| 0.20/0.10 | 7 / 7 | 0.06 / 0.03 | −0.416 / −0.601 | −0.027 |
| **0.20/0.15 (round-1 winner)** | 4 / 4 | 0.03 / 0.06 | −0.501 / −0.557 | **−0.688** |
| 0.20/0.20 | 0 / 0 | 0.19 / 0.17 | −0.377 / −0.530 | −0.356 |
| 0.25/0.10 | 11 / 11 | 0.03 / 0.06 | −0.579 / −0.605 | −0.761 |
| 0.25/0.15 | 7 / 7 | 0.03 / 0.04 | −0.670 / −0.732 | −0.656 |
| 0.25/0.20 | 4 / 4 | 0.10 / 0.06 | −0.514 / −0.648 | +0.003 |

Two findings, one confirming round 1 and one qualifying it:

1. **Round 1's two structural findings replicate exactly.** Ratios at or
   below 1:1 (0.15/0.15, 0.15/0.20, 0.20/0.20) again either never capture at
   all or capture zero times, and 0.15/0.15 again gives a desynchronized/
   positive corr(F-E_L,F-E_R) (+0.194, vs. +0.009 at seed 1) — the same
   failure mode, reproduced with an independent seed. Genuine-favoring gain
   is confirmed to be the real lever, not a seed-1 artifact.
2. **But most individual points in the bracket are seed-sensitive — only
   0.20/0.15 is not.** 0.25/0.15 scored corr(F-E_L,F-E_R) **+0.273** (bad,
   synchronized) at seed 1 and **−0.656** (good) at seed 2 — the sign
   flips on the same config with only the seed changed. 0.20/0.10 similarly
   degrades from −0.462 (seed 1) to −0.027 (seed 2). **0.20/0.15 is the one
   point that stayed good in both**: −0.724 (seed 1) → −0.688 (seed 2), a
   ~5% difference, not a coin flip. Higher-capture-count configs (7-11
   captures, at 0.25/0.10 or 0.25/0.15) can look excellent at a given seed
   (0.25/0.10 hits the best corrLR of the whole seed-2 grid, −0.761) but
   without a second seed there was no way to tell that apart from noise —
   which is exactly why this confirmation step existed.

**0.20/0.15 is now confirmed and promoted to the shipped CLI defaults**
(`--consolidate-prp-gain-genuine 0.20`, `--consolidate-prp-gain-forced 0.15`,
replacing the original guessed 2:1 ratio of 0.15/0.30, which is now confirmed
across two seeds to never capture at all at this operating point). Still
open for a future round: `tau_tag_ms` was never varied (held at 2000ms
throughout both rounds).

**Sensory-arm generalization check (2026-09-15) — the confirmed default does
NOT transfer; this is a real, arm-specific negative result, not noise.**
Re-ran the identical 9-point bracket (genuine 0.15-0.25 × forced 0.10-0.20,
seed 12345) at the same round-5 timing config (τ=260/off=0.35/cap=450) but
with `--freeze-bs-rg` added (BS→RG frozen at weak init instead of plastic —
see "Sensory-driven mode" below):

| genuine/forced | captures L/R | `frac_at_cap` L/R | corr(F-E,F-F) L/R | corr(F-E_L,F-E_R) |
|---|---|---|---|---|
| no-consolidate (reference) | n/a | 0.04 / 0.03 | −0.676 / −0.785 | −0.267 |
| 0.15/0.10 | 0 / 3 | **0.89** / 0.28 | −0.402 / −0.711 | **+0.035** |
| 0.15/0.15 | 0 / 0 | **0.89** / 0.52 | −0.466 / −0.687 | +0.137 |
| 0.15/0.20 | 0 / 0 | **1.00** / 0.89 | −0.472 / −0.593 | **+0.564** |
| 0.20/0.10 | 7 / 7 | 0.22 / 0.13 | −0.585 / −0.748 | **+0.754** |
| **0.20/0.15 (descending-arm-confirmed default)** | 3 / 3 | 0.40 / 0.32 | −0.448 / −0.711 | **+0.522** |
| 0.20/0.20 | 0 / 0 | 0.91 / 0.60 | −0.453 / −0.700 | +0.129 |
| 0.25/0.10 | 11 / 11 | 0.23 / 0.07 | −0.683 / −0.725 | −0.147 |
| 0.25/0.15 | 6 / 7 | 0.38 / 0.17 | −0.631 / −0.731 | −0.440 |
| 0.25/0.20 | 4 / 4 | 0.30 / 0.22 | −0.534 / −0.655 | +0.655 |

Every single point in the bracket makes `frac_at_cap` **worse than the
no-consolidate reference**, several catastrophically (0.15/0.20: 1.00/0.89 —
essentially fully cap-dominated), and most give a **positive**
corr(F-E_L,F-E_R) — synchronized legs, the failure mode flagged as a risk
back in the original design. The descending-arm-confirmed default (0.20/0.15)
is squarely in the bad range here (0.40/0.32 `frac_at_cap`, +0.522 corrLR).
Only 0.25/0.10 and 0.25/0.15 (both high-genuine, low-forced) come out
directionally reasonable (negative corrLR, `frac_at_cap` still elevated but
not collapsed) — a different corner of the grid than the descending arm's
best point, not the same one holding up more weakly.

**This is not a mechanism bug** — the weight-trajectory plots
(`scripts/cpg_consolidate_weights_grid.py` output) show the identical, clean
capture staircase in the sensory arm as in the descending arm; `baseline`
correctly freezes at `weight` on each capture event in both. Per-leg
force traces (`scripts/cpg_consolidate_force_stages.py`) also look
qualitatively fine throughout (corr(F-E,F-F) −0.47 to −0.84) — this
generalization failure is invisible to eyeballing single-leg force plots,
which is exactly why `frac_at_cap` and corr(F-E_L,F-E_R) exist as the
decision metrics rather than a visual check. The likely reason it differs
from the descending arm: with `BS→RG` frozen at a weak init instead of
growing toward its own ~18 pA STDP plateau, the sensory arm has less tonic
excitatory buffering, so consolidating (permanently locking in) `CUT→RG-E`'s
weight growth pushes the loop into the same positive-feedback
force-saturation regime the failsafe timeout exists to catch (see "Force-
triggered CUT" above) more readily than when BS is also plastic and sharing
the excitatory load.

**Consequence: `--consolidate`'s shipped defaults are validated for the
descending arm only.** Do not use `--consolidate` on `--freeze-bs-rg` runs
with the current defaults without its own tuning round — this bracket found
a *different* promising corner (high-genuine/low-forced, e.g. 0.25/0.10-0.15).

**Sensory-arm tuning round (2026-09-15) — the 0.25/0.10-0.15 corner has a
reproducible bad zone in its middle, not a smooth trade-off.** Fine-swept
forced ∈ {0.10, 0.1125, 0.125, 0.1375, 0.15} at genuine=0.25 fixed, first at
seed 12345 then repeated at seed 54321 to separate real structure from
per-seed noise (the same check that mattered for the descending arm):

| forced | seed1 `frac_at_cap` L/R | seed1 corrLR | seed2 `frac_at_cap` L/R | seed2 corrLR |
|---|---|---|---|---|
| no-consolidate | 0.04 / 0.03 | −0.267 | 0.03 / 0.04 | −0.670 |
| **0.10** | 0.23 / 0.07 | **−0.147** | 0.10 / 0.09 | **−0.262** |
| 0.1125 | 0.20 / 0.07 | +0.299 | 0.23 / 0.16 | +0.527 |
| 0.125 | 0.12 / 0.07 | +0.257 | 0.22 / 0.13 | +0.714 |
| 0.1375 | 0.23 / 0.20 | −0.072 | 0.23 / 0.17 | +0.318 |
| 0.15 | 0.38 / 0.17 | −0.440 | 0.28 / 0.23 | +0.076 |

Two-seed comparison separates a real effect from what first looked like
random scatter: **0.10 is the only forced value that stays negative
(anti-phase) in both seeds** — the interior of the box (0.1125-0.1375) gives
a **positive** (synchronized) corrLR in *both* seeds, a reproducible bad zone,
not noise. 0.15, which looked like the round's best point at seed 1
(−0.440), flips to positive (+0.076) at seed 2 — unreliable, same pattern as
0.25/0.15 and 0.20/0.10 in the earlier descending-arm confirmation. Nothing
in this box fully restores `frac_at_cap` to the no-consolidate level (best
case 0.10/0.09 at seed 2, still ~3x worse than baseline) — this remains a
real, open regression for the sensory arm, not a solved problem.

**Working recommendation for `--freeze-bs-rg` runs: `--consolidate-prp-gain-
genuine 0.25 --consolidate-prp-gain-forced 0.10`** — the only point in the
tested region that is reproducibly better than doing nothing on
corr(F-E_L,F-E_R) without a compensating cap-domination regression as bad as
the rest of the box.

**Methodological correction (2026-09-15) — the "regression" above was
measuring the wrong window; the user's own read of it turned out to be
right.** The user pointed out that a `frac_at_cap` regression under
`--consolidate` is exactly what they'd expect, framed against the opposite
problem this project has previously had: vanilla STDP recovering the walking
pattern *too fast* to be a plausible stand-in for real rehabilitation timescales.
That prompted checking directly, with `bouts_from_cut_on` windowed into
0-20s/20-40s/40-60s, whether the whole-run `frac_at_cap` numbers above were
reporting a genuine steady-state problem or an extended-but-resolving early
transient. They were overwhelmingly the latter: e.g. sensory-arm 0.25/0.10
shows `frac_at_cap` 0.73/0.23 in the first 20s but 0.00/0.00 for the rest of
the run — statistically indistinguishable from the no-consolidate reference's
own steady state (also 0.00/0.00 after its first 20s) — and this holds for
essentially every genuine=0.25 point tested (0.10 through 0.20), not just the
working recommendation. The whole-run average was reporting the length of a
recovery period, not a persistent failure — which is the bio-plausible
behavior `--consolidate` was introduced to get (a genuine settling-in period
instead of instant convergence), not a bug.

This has a real consequence beyond the sensory arm: **the whole-run
`frac_at_cap`/corr(F-E_L,F-E_R) numbers used to score every bracket point in
both this round and the round-2 descending-arm confirmation are contaminated
by this same transient**, and restricting to steady-state
(`--steady-from-ms 30000`, now supported directly by
`scripts/cpg_cutforce_diagnostics.py`) changes some of those numbers
substantially:

| config (arm, gains) | whole-run corrLR | **steady-state (t≥30s) corrLR** |
|---|---|---|
| descending, 0.20/0.15, seed 12345 | −0.724 | **−0.839** |
| descending, 0.20/0.15, seed 54321 | −0.688 | **−0.839** |
| descending, 0.25/0.15, seed 12345 | +0.273 | +0.297 (still bad) |
| descending, 0.25/0.15, seed 54321 | −0.656 | −0.720 (still good — genuinely bistable) |
| sensory, 0.25/0.10, seed 12345 | −0.147 | **−0.286** (≈ no-consolidate's −0.285) |
| sensory, 0.25/0.10, seed 54321 | −0.262 | **−0.280** (≈ no-consolidate's −0.720... note seed2's own no-consolidate baseline is a stronger −0.720, so 0.25/0.10 is *not* quite matching baseline at seed 2, unlike seed 1) |
| sensory, 0.25/0.15, seed 12345 | −0.440 | −0.829 (excellent) |
| sensory, 0.25/0.15, seed 54321 | +0.076 | +0.316 (still bad — genuinely bistable, not a transient artifact) |
| sensory, 0.25/0.1125-0.1375 (both seeds, 6 runs) | −0.07 to +0.53 | +0.01 to +1.00 (positive in all 6 at steady state, incl. the one whole-run value that had looked negative — the "bad zone" is real, not a transient) |

**Two corrected conclusions:**
1. **The descending-arm confirmed default is confirmed more strongly than
   originally reported**, not less: 0.20/0.15's steady-state
   corr(F-E_L,F-E_R) is −0.839 in *both* seeds — not just same-sign but
   numerically identical, the tightest replication of any point tested in
   either arm. No change to the shipped default.
2. **Cap-domination is not the sensory arm's real, persistent problem — L/R
   phase-locking is.** Every tested genuine=0.25 point reaches clean,
   non-cap-dominated bout timing at steady state; what actually
   distinguishes them is whether the legs settle into anti-phase (0.10: good
   in both seeds) or in-phase (0.1125-0.1375: bad in both seeds) lock, with
   0.15 sitting on a genuine bistable boundary (excellent at seed 1, bad at
   seed 2) rather than being noise either way. The working recommendation
   (genuine=0.25, forced=0.10) is unchanged by this correction — if anything
   it's better supported now, since its steady-state numbers show it
   converging to a real anti-phase attractor rather than merely averaging out
   noise — but the previous framing ("`frac_at_cap` stays ~3x worse than
   no-consolidate, a real open regression") was measuring recovery-period
   length, not steady-state quality, and should not be read as a persisting
   defect. **Whole-run metrics should not be used alone for `--consolidate`
   tuning going forward — always pair with `--steady-from-ms` on
   `scripts/cpg_cutforce_diagnostics.py`.**

**Full 3×3 sensory-arm bracket, both seeds, steady-state (t≥30s) — completes
the grid the working recommendation was drawn from.** The earlier
sensory-arm bracket (round labeled "generalization check") only had seed-1
coverage across the full 3×3 grid; seed 54321 was filled in for the
remaining 7 cells to check the same two-seed standard applied everywhere
else in this file:

| genuine/forced | seed1 `atCap` L/R | seed1 corrLR | seed2 `atCap` L/R | seed2 corrLR | verdict |
|---|---|---|---|---|---|
| no-consolidate | 0.00/0.00 | −0.285 | 0.00/0.00 | −0.720 | reference |
| 0.15/0.10 | 0.82/0.03 | −0.147 | 0.20/0.00 | −0.316 | still cap-dominated (seed1 L) |
| 0.15/0.15 | 0.85/0.35 | −0.151 | 0.91/0.85 | +0.866 | cap-dominated both seeds, corrLR flips |
| 0.15/0.20 | 1.00/0.91 | +0.891 | 0.94/0.88 | +0.902 | cap-dominated **and** synchronized, both seeds |
| 0.20/0.10 | 0.00/0.00 | +1.000 | 0.00/0.00 | −0.527 | genuine both seeds, corrLR flips |
| 0.20/0.15 | 0.00/0.09 | +0.938 | 0.20/0.00 | +0.605 | genuine, but **synchronized in both seeds** |
| 0.20/0.20 | 0.85/0.47 | −0.297 | 0.71/0.82 | −0.200 | cap-dominated, both seeds |
| **0.25/0.10** | **0.00/0.00** | **−0.286** | **0.00/0.00** | **−0.280** | **genuine + anti-phase, both seeds** |
| 0.25/0.15 | 0.00/0.00 | −0.829 | 0.00/0.00 | +0.316 | genuine both seeds, corrLR flips (bistable) |
| 0.25/0.20 | 0.00/0.00 | +1.000 | 0.03/0.00 | +0.632 | genuine, but **synchronized in both seeds** |

The completed grid separates into three clean groups rather than a noisy
scatter: **genuine=0.15 is simply too weak** to reliably escape
cap-domination in this arm (still cap-dominated in 5 of 6 seed×forced
combinations); **genuine=0.20/0.25 paired with forced=0.15 or 0.20 reliably
escapes cap-domination but reliably synchronizes the legs instead**
(positive corrLR in *both* seeds at all four such cells — a real,
reproducible failure mode, not scatter); and **0.25/0.10 is the only cell in
the entire 3×3 grid that is both genuine and anti-phase in both seeds**, with
its two corrLR values (−0.286, −0.280) nearly identical — the same tight
cross-seed replication quality that confirmed 0.20/0.15 for the descending
arm. This is the strongest evidence yet for the working recommendation and
completes the sensory-arm bracket to the same two-seed standard as the
descending arm, though it remains a working recommendation, not a promoted
CLI default — see caveats above (one timing operating point, `tau_tag_ms`
unswept).

**Summary: every `--consolidate` config tested this session, sorted into
healthy vs. pathological.** The round-by-round tables above are the lab
notebook (chronological, includes dead ends); this collects the same numbers
by outcome instead, using the two failure modes this document already
established (cap-domination: `frac_at_cap` elevated; leg-synchronization:
corr(F-E_L,F-E_R) positive) plus two outcomes that are neither: a config that
never captures at all (**inert** — the mechanism is a no-op, not a failure,
but doesn't do anything either), and a config whose verdict **flips sign
between seeds** (**bistable** — confirmed reproducible in both directions,
not noise, but unusable as a fixed default either way). Steady-state
(t≥30s) numbers are used wherever computed; whole-run numbers are used
otherwise and marked accordingly — see the methodological correction above
for why that distinction matters.

*Descending arm (τ=260/off=0.35/cap=450):*

| genuine/forced/threshold | seed(s) | corrLR | Verdict |
|---|---|---|---|
| **0.20/0.15/1.0** | 12345 **and** 54321 | **−0.839 / −0.839** (steady-state, identical) | **HEALTHY — shipped CLI default** |
| 0.15/0.10/1.0 | 54321 only | −0.559 (whole-run) | Healthy-looking, single-seed only — not cross-confirmed |
| 0.25/0.10/1.0 | 54321 only | −0.761 (whole-run) | Healthy-looking, single-seed only — not cross-confirmed |
| 0.15/0.15/1.0 | 12345 **and** 54321 | +0.009 / +0.194 | **PATHOLOGICAL — synchronized, both seeds** |
| 0.25/0.20/1.0 | 54321 only | +0.003 | Pathological (borderline-synchronized) |
| 0.20/0.15/**0.5** | 12345 only | +0.242 | **PATHOLOGICAL — synchronized** (threshold, not just gain ratio, matters) |
| 0.25/0.15/1.0 | 12345 **and** 54321 | +0.297 (steady-state) / −0.720 (steady-state) | **BISTABLE — flips sign between seeds, do not use** |
| 0.20/0.10/1.0 | 12345 **and** 54321 | −0.462 / −0.027 | Unreliable — collapses toward zero at the second seed |
| 0.15/0.30/1.0 (original guess) | 12345 only | −0.491 | Inert — 0 captures, mechanism never engages |
| 0.15/0.20/1.0 | 54321 only | −0.637 | Inert — 0 captures despite an incidentally-OK corrLR |
| 0.20/0.20/1.0 | 54321 only | −0.356 | Inert — 0 captures |

*Sensory arm (`--freeze-bs-rg`, same timing config), full 3×3 bracket +
genuine=0.25 fine-sweep, steady-state, both seeds throughout:*

| genuine/forced | corrLR (seed1 / seed2) | Verdict |
|---|---|---|
| **0.25/0.10** | **−0.286 / −0.280** (nearly identical) | **HEALTHY — working recommendation, confirmed both seeds** |
| 0.15/0.10 | −0.147 / −0.316 | Pathological — cap-dominated at seed1 (`atCap` 0.82) |
| 0.15/0.15 | −0.151 / +0.866 | Pathological — cap-dominated both seeds, synchronizes at seed2 |
| 0.15/0.20 | +0.891 / +0.902 | **PATHOLOGICAL — worst case: cap-dominated AND synchronized, both seeds** |
| 0.20/0.15 | +0.938 / +0.605 | Pathological — genuine bout timing, but synchronized in both seeds |
| 0.20/0.20 | −0.297 / −0.200 | Pathological — cap-dominated both seeds |
| 0.25/0.1125 | positive, both seeds | Pathological — synchronized both seeds (interior "bad zone") |
| 0.25/0.125 | positive, both seeds | Pathological — synchronized both seeds (interior "bad zone") |
| 0.25/0.1375 | positive, both seeds | Pathological — synchronized both seeds (interior "bad zone") |
| 0.25/0.20 | +1.000 / +0.632 | Pathological — genuine bout timing, but synchronized both seeds |
| 0.20/0.10 | +1.000 / −0.527 | **BISTABLE — flips sign between seeds, do not use** |
| 0.25/0.15 | −0.829 / +0.316 | **BISTABLE — flips sign between seeds, do not use** |

**Reading the two tables together**: exactly one point per arm is healthy —
0.20/0.15 (descending, shipped) and 0.25/0.10 (sensory, working
recommendation) — and both are healthy for the same reason, tight
same-sign, near-identical corrLR across two independent seeds, not just a
good number once. Everything else sorts into one of three unhealthy
buckets, and they are different failures needing different fixes: inert
configs need a stronger genuine-favoring push before they'll do anything at
all; pathological configs need to move *away* from wherever they are,
generally toward less capture (sensory arm) or more (descending arm's
symmetric case) or a different threshold entirely; bistable configs are the
most dangerous of the three to mistake for progress, since a single-seed run
can make one look like either a clean win or a clean failure at random.

### Force-trigger speed axis (Stage 1, 2026-09-15) — partial progress, fast side only

Prompted by the question of whether the project is ready for a production
MN5 run across "all speeds" with `--consolidate`: force-trigger mode has no
existing speed concept at all. `--step-period-ms` (the timer-mode speed
knob) only paces the within-bout Ia-E heel→toe ramp here, not cycle length;
bout duration is emergent from `--fatigue-tau-onset-ms` × `--cut-force-off-
frac`, and rounds 1-6 only ever searched for **one** good point (τ=260/
off=0.35/cap=450, re-confirmed above), never a speed family. This is Stage 1
of `~/.claude/plans/resilient-soaring-flamingo.md`'s staged roadmap:
establish 2-4 more (τ, off-frac) points bracketing the confirmed one,
descending arm, 2 seeds, steady-state metrics.

**Fast direction — one clean point found, but the achievable range looks
narrow.** τ=200/off=0.30 is genuine and reproducible in both seeds
(`frac_at_cap` 0.00/0.00 and 0.01/0.00; stance duration tight at 350±0-12ms,
tighter than the confirmed point's own ±27ms; corr(F-E_L,F-E_R) −0.399 and
−0.619, both anti-phase). But measuring **full gait-cycle period**
(stance-onset to stance-onset, not just stance duration) shows it's only
modestly faster than the confirmed point: **800ms vs. 850ms, ≈6%** — not the
kind of spread timer mode's 1200/520/350ms (3.4×) speed grid covers. Two
intermediate attempts on the way there failed outright: τ=200/off=0.35 gave
genuine bouts (`frac_at_cap`=0.00) but wildly variable duration (±135-159ms,
~60% relative) and inconsistent corrLR across seeds (+0.165, −0.017) — not
usable despite passing the cap-domination check.

**Slow direction — two attempts, both failed, harder than the fast side.**
τ=280/off=0.35 (a modest +20ms step from the confirmed τ=260) **collapsed to
100% cap-domination in both seeds** (`frac_at_cap` 1.00/1.00, duration
exactly 450±0ms — a disguised clock). τ=300/off=0.40 (loosening off-frac
further, per round 4's old-circuit finding that off must loosen alongside
higher τ) didn't fix it either — **~50% cap-domination in both seeds**
(0.50/0.51, 0.49/0.48), a reproducible bimodal mix of genuine and
failsafe-capped bouts, not an improvement. The medium operating point
appears to sit much closer to its slow-side failure boundary than its
fast-side one on the current circuit — a real, currently unexplained
asymmetry, not yet root-caused.

**Status: Stage 1 not complete.** One additional confirmed point (fast,
modest speedup) plus two failed slow attempts. Before a 3+-point speed axis
can be called established: (a) the slow direction needs a different lever
than "more of the same" — candidates not yet tried: loosening `--cut-force-
on-frac` (never swept, fixed at 0.80 through every round including this
one), or accepting that a genuinely slower bout may require raising
`--cut-max-stance-ms` itself (currently untouched by design, since a moving
cap was previously how "disguised clock" results were diagnosed — raising it
deliberately as part of defining "slow" is a different, defensible use, but
changes what `frac_at_cap` even means for that point and should be flagged
explicitly if done); (b) even the fast side's ~6% spread needs a second,
more distinct fast point before "fast" is a meaningfully different speed
rather than a slightly-tighter version of medium.

**Swing has no closed-loop signal at all — it is a pure timer, always
(2026-09-15).** Checked directly: `cut_force_gate()` never reads `force_f`;
the only signal that ends swing is `fe >= on_thr` (extensor force rising),
which has nothing to do with the flexor/swing side itself. Measuring stance
and swing bout durations *separately* (the existing diagnostics script only
ever reported stance) shows **swing sits at exactly `--cut-max-swing-ms`
with zero variance in every config tested, including the confirmed
"genuine" medium point** — swing has always been failsafe-timed, not
force-triggered; there is no bug here, the model simply has no sensory
variable analogous to hip/limb position that would let swing end any other
way. This means `--cut-max-swing-ms` is not a backstop to avoid touching for
swing the way it is for stance — it is the *only* thing that sets swing
duration, so it looked like a natural, low-risk lever for the speed axis.

**Tested that directly — it isn't low-risk, because stance and swing are
coupled through muscle fatigue *recovery*, not independent.** Two attempts,
stance parameters held at their already-confirmed values in both cases:
- **Slow attempt 3**: medium's exact stance config (τ=260/off=0.35/stance-cap
  450, unchanged) + swing cap raised 450→600ms alone. Expected stance to be
  unaffected since nothing about it changed. Instead **stance itself
  collapsed to 100% cap-domination in both seeds** — a longer swing gives
  `fatigue_e` more time to clear via `--fatigue-tau-recovery-ms` before the
  next stance, so that stance starts less fatigued and takes measurably
  longer to re-fatigue down through `off_thr`, past the unchanged 450ms
  stance cap. The two phases are coupled through shared fatigue state, not
  independent just because they're gated by separate flags.
- **Fast attempt 3**: the confirmed fast stance config (τ=200/off=0.30) +
  swing cap lowered 450→350ms alone. Stance stayed genuine (`frac_at_cap`
  0.00/0.00 both seeds) but reintroduced the same failure as the earlier
  τ=200/off=0.35 attempt — high bout-duration variance (±144-160ms) and
  inconsistent corrLR across seeds (−0.235, +0.249) — plausibly the same
  coupling in reverse (less recovery time causing bout-to-bout drift).

**Revised status: Stage 1 needs a "scale the whole clock together" approach,
not single-parameter nudges.** Changing stance-side timing (τ, off-frac)
alone breaks stance directly; changing swing-side timing (swing cap) alone
breaks stance indirectly through fatigue recovery. The remaining untried
approach is scaling `--fatigue-tau-onset-ms`, `--fatigue-tau-recovery-ms`,
`--cut-max-stance-ms`, and `--cut-max-swing-ms` together (proportionally,
preserving the confirmed point's ratios) rather than moving one axis at a
time — this has not yet been attempted and is a reasonable next step, not
a confirmed fix.

**Tested — the scaling approach works cleanly for slow, but not for fast
(2026-09-15).** Confirms the hypothesis for one direction and rules it out
as a general fix for the other:

- **Slow, confirmed: 1.3× scale** (τ=340, recovery=780, both caps=585,
  off-frac unchanged at 0.35). Genuine and tight in both seeds
  (`frac_at_cap` 0.00/0.00; stance 535±23/537±22ms seed 1, 513±22/513±22ms
  seed 2 — **~4% relative variability, tighter than the confirmed medium
  point's own ~9%**), and corr(F-E_L,F-E_R) is nearly identical across seeds
  (−0.825, −0.832 — the same tight cross-seed match quality that confirmed
  0.20/0.15 for `--consolidate` and the medium point itself). Full gait
  cycle: **1135/1113ms vs. medium's 850ms, ≈31-34% slower** — a genuinely
  distinct speed, not a marginal nudge. **This is now a second confirmed
  force-trigger operating point** (slow), alongside the original medium one.
- **Fast, still not solved: 0.75× scale failed.** (τ=195, recovery=450,
  caps=340). Steady-state `frac_at_cap` 0.32-0.59 (partial cap-domination,
  mixed genuine/capped bouts) and corr(F-E_L,F-E_R) **positive in both
  seeds** (+0.342, +0.111 — synchronized, the same failure mode as every
  other fast attempt). Would-be full cycle ≈630-646ms (≈25-26% faster,
  a meaningfully distinct speed *if* it had worked) — but it isn't genuine,
  so it doesn't count.

**Net Stage 1 status: 2 of 3 speed points now confirmed (medium, slow);
fast remains open after 5 distinct attempts** (τ=200/off=0.35;
swing-cap-350-alone; 0.75× uniform scale; plus the earlier τ=200/off=0.30,
which is genuine but only a ~6% speedup, not a distinct fast point). The
fast direction is consistently harder than the slow direction across every
method tried so far (single-axis and proportional-scaling alike) — a
real, reproducible asymmetry in this circuit that a future round should
treat as the object of study itself (why does speeding up specifically
desynchronize the legs?), rather than keep attacking with the same class of
parameter nudge.

**Investigating the asymmetry: why speeding up desynchronizes the legs
(2026-09-15).** Two absolute-time constants are held fixed across every
Stage 1 attempt while bout duration shrinks for faster configs — and both
turn out to matter, for different reasons.

**Confirmed factor 1 — `--lead-offset-ms` doesn't scale with cycle period.**
It's a fixed 150ms absolute value throughout. As a *fraction of stance
duration* it stays a safe 28-38% for the two confirmed-good points (medium
400ms stance, slow 535ms) but balloons to 53-61% for every failed fast
attempt (245-283ms stance) — directly the failure zone this file already
documented for oversized priming windows (§ "Force-triggered CUT": 400ms
priming against a ~1000ms cycle flipped corr(F-E_L,F-E_R) to +0.41). Testing
it directly on the 0.75× scaled-fast config (150→112ms, same proportion):
steady-state `frac_at_cap` dropped from 0.32-0.59 to 0.22-0.36, and one
seed's corr(F-E_L,F-E_R) flipped from badly-synchronized (+0.342/+0.111) to
strongly anti-phase (−0.700) — a real, substantial improvement, confirming
this is a genuine contributing cause, not coincidence. Not a full fix on its
own: residual cap-domination and one seed's near-zero (ambiguous) corrLR
remained.

**Confirmed factor 2 — `--rate-update-ms` (the gate-check tick) doesn't scale
down either, but the "obvious" fix backfires.** Inspecting the raw
steady-state bout-duration sequence for the lead-offset-corrected config
showed durations locked to *only two discrete values*, 300 or 350ms — never
anything between — because the failsafe check only runs at 50ms ticks, and
340ms's failsafe fires at the first tick ≥340ms, which lands on 350
regardless of how close to genuinely completing the bout actually was. At
medium/slow speeds this tick is a fine fraction of bout duration (~9-12%);
at this fast config's ~300ms bouts it's a much coarser ~17%, so a
near-miss and a comfortable margin both round to the identical "at cap"
verdict. **Tested the obvious fix directly (`--rate-update-ms`/
`--simulate-chunk-ms` 50→20ms) and it made things dramatically worse, not
better**: mean bout duration collapsed to 40-84ms with variance exceeding
the mean (±78-128ms) — not finer resolution of the same rhythm, but outright
Schmitt-trigger **chattering**. `peak_e_est = max(fe, peak_e_est)` and the
on/off-threshold check both run every rate-update tick; sampling `force_e`
more often lets the per-bout running peak track force noise more precisely,
which makes the relative on/off thresholds cross spuriously on tiny
fluctuations instead of the real envelope. The coarse tick isn't just a
measurement artifact to fix by sampling faster — it's doing real,
load-bearing noise-averaging that a naive resolution increase removes.

**Answer to "why does speeding up desynchronize the legs": at least two
independent, confirmed mechanisms, not one.** (1) A fixed-duration symmetric
priming window becomes a larger fraction of a shorter cycle, pushing toward
the already-known over-priming synchronization failure. (2) A fixed gate
tick becomes a coarser fraction of a shorter cycle, inflating apparent
cap-domination — but the fix isn't simply finer sampling, since the same
tick also low-pass-filters the peak-tracking Schmitt trigger against noise,
and removing that naively causes chattering instead. A genuine fast
operating point likely needs `--lead-offset-ms` scaled down (factor 1,
confirmed to help) *and* a noise-robust way to shrink the effective tick
period (factor 2 — not yet solved; simple down-scaling doesn't work, and
whatever replaces it needs to preserve peak-tracking noise rejection while
still resolving a shorter bout).

**Factor 2 follow-up: an explicit noise filter, decoupled from tick rate
(2026-09-15) — implemented, tested, still doesn't solve it.** Added
`--cut-force-filter-tau-ms` (`MOD_CUT_FORCE_TRIGGER`, default 0 = off, exact
original behaviour): an exponential low-pass on `force_e` feeding both
`peak_e_est` and the on/off threshold comparisons, with its own time
constant independent of `--rate-update-ms`, so the tick can shrink without
losing noise rejection. Two problems found in sequence, both real:

1. **First test (τ_filter=30ms at rate-update=20ms) still chattered** —
   durations ~24-32ms, barely above the tick floor. Root cause found by
   inspection: the filter state was only re-seeded at *stance* onset
   (reusing the existing `peak_e_est` reset point), so a swing phase
   shorter than the filter's own settling time left `force_e_filt` carrying
   a stale, lagging estimate from the *previous* stance into the new bout
   — filter lag dominating a bout shorter than itself, not noise rejection.
   Fixed: re-seed `force_e_filt[side] = None` at *every* phase transition,
   not just stance onset.
2. **A stronger filter (τ=100ms) made it worse before the fix** (durations
   collapsed to exactly the 20ms tick floor, corr(F-E,F-F) degraded to
   ~-0.05, essentially no rhythm) — consistent with (1): a filter slower
   than the bout it's supposed to smooth doesn't stabilize the loop, it
   destabilizes it (lagged feedback into a hysteresis/relay controller is a
   classic route to a new oscillation mode, not noise suppression).
3. **After the fix, re-tested τ=30ms at rate-update=20ms: still broken**,
   though less severely — durations 28-90ms (still nowhere near the ~280
   -300ms target), std comparable to or exceeding the mean, and markedly
   asymmetric between legs in one seed (L=90ms vs R=28ms). corr(F-E,F-F)
   improved to -0.32 to -0.59 (better than the pre-fix -0.05 to -0.36, but
   still well short of working configs' -0.6 to -0.8).

**Weight trajectories confirm this is corrupting learning, not just
timing.** Every other comparison in this file (arms, gains, speeds) showed
near-identical CUT→RG-E convergence regardless of condition (§ "why the
weight profiles look identical" reasoning above) — this is the first
exception. Plotting the three chattering configs
(`scripts/cpg_consolidate_weights_grid.py`) against the medium reference
shows CUT→RG-E climbing well past the reference's ~63-67 pA plateau in all
three — off the top of a 0-70 pA axis, still rising at 60s, one case
(τ_filter=100, no fix) in an almost linear, unsaturated trajectory. Rapid,
spurious on/off flipping delivers far more STDP-eligible coincidence events
per second than genuine, slower cycling does, so chattering doesn't just
fail to produce a usable rhythm — it also drives the plastic synapse to a
different (higher, seemingly still-growing) trajectory than every genuine
operating point converges to. Another concrete way this fast-direction
failure mode differs qualitatively from the medium/slow successes, not just
quantitatively.

**Conclusion: the filter approach is real, the bug fix was necessary, and
neither is sufficient on its own.** Something beyond peak-tracking noise is
also unscaled at fine ticks — a plausible next suspect, not yet tested: the
Ia-E heel→toe sub-group pacing (`SUB_STANCE_MS`, derived from
`--step-period-ms`/`--stance-fraction`/`--n-ia-groups`, still at its
original ~167ms value throughout every Stage 1 attempt) is now much larger
than the collapsed ~20-90ms bouts, so only the first (weakest, 60Hz)
sub-group ever fires — a third absolute-time constant that was never scaled
alongside the others, on top of `--lead-offset-ms` (factor 1) and the tick/
filter (factor 2). The pattern across all three is the same: this circuit
has more independent absolute-time constants than were ever exercised by
rounds 1-6's single-operating-point search, and a coherent fast operating
point likely needs all of them scaled together, not one or two at a time.

**Also surfaced during this work, orthogonal to the filter itself but
consequential for the rest of this file's methodology: identical code, same
seed, same flags, produced different corr(F-E_L,F-E_R) on two consecutive
runs** (-0.318 vs +0.298, medium point, filter off) — confirmed not a code
regression (per-leg `frac_at_cap` and corr(F-E,F-F) matched the established
range in both runs; only corrLR differed) but genuine run-to-run
nondeterminism, most likely from NEST's multi-threaded execution affecting
spike-arrival order in ways a fixed `--seed` doesn't fully pin down. This is
a re-surfacing of an already-documented caution in this file ("L/R-metric
instability at debug scale... per-leg metrics are the stable/trustworthy
ones here"), but this session's `--consolidate` and Stage 1 tuning leaned on
corrLR more heavily than that caution suggests was warranted. Doesn't
invalidate prior 2-seed-confirmed results (per-leg metrics were consistent
throughout, and the confirmed points' corrLR matches were tight enough to
be real signal, not just luck — e.g. 0.20/0.15's steady-state -0.839 in
*both* seeds), but any *single* corrLR data point, including ones in this
file, should be read with this in mind, and a genuine future confirmation
pass would benefit from more than 2 repeats given now-demonstrated
same-seed variance.

**Full 3-speed × 2-arm visual summary (2026-09-15).** Filled in the two
missing cells (sensory arm at the slow and fast timing configs — only the
medium-speed sensory arm had been run before) and generated the full grid
with `scripts/cpg_consolidate_force_stages.py`/`cpg_consolidate_weights_grid.py`:
medium (τ=260/off=0.35/cap=450), slow (τ=340/recovery=780/caps=585, the
1.3× scale), and fast (τ=200/off=0.30, the confirmed-but-only-~6%-faster
point), each on both the descending arm and the sensory arm
(`--freeze-bs-rg`), same seed (12345) throughout for comparability.
All 18 force-stage panels (3 stages × 6 conditions) show clean, regular
counter-phase rhythms — no surprises, this is the expected picture given
every cell here is one of the two *confirmed-genuine* speed points, not one
of the fast-direction failure attempts. All 6 weight-trajectory panels
converge to the same CUT→RG-E ≈63-67 pA plateau and Ia→RG set-points
regardless of speed or arm — consistent with every other comparison in this
file except the chattering configs, and a useful independent confirmation
that the medium/slow speed points and the descending/sensory arm split are
all mutually compatible with each other, not just individually confirmed
in isolation. New sensory-arm files:
`results/sensory_slow_scaled13x_seed12345.h5`,
`results/sensory_fast_tau200_off0.30_seed12345.h5`.

**Correction: use the paper's own 5-locomotion-mode terminology, not
ad hoc "slow/medium/fast" (2026-09-15).** The paper (§4.1, Fig. 3) already
defines five locomotion modes as one set, not two separate axes: *slow
walk* (6 cm/s), *medium walk / plantar / baseline* (13.5 cm/s), *fast walk*
(21 cm/s) — all full weight-bearing — plus *toe stepping* (partial
unloading, `--ia-feedback-gain`/`--cut-feedback-gain` 0.5) and *air
stepping* (full unloading, gain 0.1), both at the baseline speed anchor.
Everything under "Force-trigger speed axis" above used the first three
correctly in spirit (their own force-trigger-mode timing analogues, not
validated against the paper's 6/13.5/21 cm/s figures — that mapping doesn't
exist for this mode, as documented above) but never exercised toe/air
stepping at all — a different, loading axis, not a timing one, and
distinct from the `--freeze-bs-rg` descending-vs-sensory *arm* split this
file also calls "sensory," which is a different thing again (a learning-
architecture choice, not a feedback-strength one). Ran the two missing
conditions (`--ia-feedback-gain`/`--cut-feedback-gain` 0.5 and 0.1) at the
confirmed medium timing point, crossed with both arms — completing the
full 5-mode × 2-arm grid, 10 cells, force-trigger mode, for the first time.

**Toe/air stepping reproduce the paper's documented unloading degradation,
and the loading-dependent Ia→RG cap-relaxation mechanism is confirmed
working in force-trigger mode.** Force profiles: the three walking speeds
stay clean (r ≈ −0.6 to −0.85) in both arms; toe stepping visibly weakens
(r ≈ −0.09 to −0.43) and air stepping becomes markedly irregular (r ≈ −0.09
to −0.62, visibly ragged traces) — the same qualitative pattern §4.4 of the
paper describes for timer mode ("the counter-phase is thus lost at the
muscle level before it is lost at the rhythm-generator level"), now shown
under force-triggered timing instead of a fixed clock. Weight trajectories
(after fixing a real bug in `cpg_consolidate_weights_grid.py` — the Ia→RG
axis was hardcoded to 0-12 pA and was silently clipping data that exceeds
it, invisible rather than erroring) show `Ia→RG` climbing well past its
usual ~4-5 pA set-point under both ablation conditions — to ~18-21 pA under
toe stepping, ~23-25 pA under air stepping — while `CUT→RG-E` stays
correspondingly weak (air stepping: ~35 pA by 60s vs. the normal ~63-67 pA
plateau). This is `MOD_IA_RG_LOADING_GAIN`'s `--wmax-ia-unloaded` mechanism
(cap relaxes as `--cut-feedback-gain` drops, letting Ia take over more
excitatory drive when cutaneous input is genuinely reduced) engaging
correctly — previously validated only in timer/paced-gait mode; this is its
first confirmation under `--cut-trigger force`. New files:
`results/{descending,sensory}_{toe,air}_seed12345.h5`.

**Fast direction, attempt 6 — SUB_STANCE_MS scaled too (2026-09-15): the
noise/chatter and reliable-synchronization failures are both fixed; a
sharper, purely bistable failure remains.** Scaled the third previously-
untested absolute-time constant flagged above — `SUB_STANCE_MS` (the Ia-E
heel→toe sub-group window, derived from `--step-period-ms`/
`--stance-fraction`/`--n-ia-groups`) — down alongside the already-confirmed
levers: `--step-period-ms` 1000→750 (0.75×, giving `sub_stance`≈125ms
instead of the ~167ms every prior attempt left fixed), `--lead-offset-ms`
150→112 (0.75×, factor 1 from the desynchronization investigation above),
and the same 0.75× fatigue-onset/recovery scale from the earlier failed
uniform-scale attempt (τ=195/recovery=450). Tested three cap values at
off-frac=0.30 (the confirmed-fast value), two seeds each:

| cap (ms) | seed1 steady atCap L/R | seed1 corrLR | seed2 steady atCap L/R | seed2 corrLR | steady duration (both seeds) |
|---|---|---|---|---|---|
| 340 | 1.00/1.00 | −0.793 | 1.00/1.00 | −0.738 | 350±0ms (disguised clock) |
| 420 | 0.00/0.00 | **−0.541** | 0.00/0.00 | **+0.576** | 400±0ms (genuine) |
| 450 | 0.00/0.00 | **−0.536** | 0.00/0.00 | **+0.999** | 400±0ms (genuine) |

(Loosening off-frac instead of the cap, at the 340ms cap, was tried first
and made things worse, not better — off=0.35 gave `frac_at_cap` 0.58-0.65
with corrLR flipping positive [+0.20]; off=0.40 gave 0.49-0.50 with corrLR
collapsing toward zero [-0.20]. Loosening the cap while holding off=0.30
fixed was the lever that actually worked.)

Two real, opposite-direction improvements over every earlier fast attempt,
both confirmed at 420ms and 450ms cap alike: (1) **bout duration is now
exactly deterministic** (±0ms steady-state std, vs. attempt 5's ±144-160ms
chatter) — scaling `SUB_STANCE_MS` alongside the tick/filter work removed
the noise-driven variability that every earlier fast attempt suffered from;
(2) **corr(F-E_L,F-E_R) is strongly negative in one seed of every config
tested**, unlike attempts 2-5 which were reliably *positive* (synchronized)
at comparable speeds. But the sign now **flips between seeds at both cap
values** (−0.54→+0.58 at 420ms, −0.54→+0.999 at 450ms) — a clean,
reproducible bistability, the same failure category already named and
rejected for several `--consolidate` gain configs elsewhere in this file,
not noise or a tuning miss. The underlying dynamics settle into a genuinely
deterministic 400ms limit cycle at both cap values (cap itself stops
mattering once it's loosened past ~380-400ms) — which leg-phase relationship
that limit cycle locks into is decided by run-to-run spike-timing
happenstance, not by any parameter tested so far.

**Conclusion: SUB_STANCE_MS was a real, load-bearing lever — it just
resolves a different failure mode than the one blocking a usable fast
point.** All three previously-identified absolute-time constants
(`--lead-offset-ms`, tick/filter, `SUB_STANCE_MS`) are now confirmed
individually load-bearing, and scaling them together removes the
noise/chatter pathology entirely. What remains is a structurally different
problem — a genuine deterministic bistability in L/R phase-locking at this
speed — that time-constant scaling doesn't touch, because it isn't a noise
or timing-resolution problem at all. **Stage 1's fast direction is closed
for this pass, unresolved, after 6 distinct attempts** (single-axis nudges,
proportional 0.75× fatigue-only scaling, lead-offset correction, two filter
strengths, and now full time-constant-family scaling including
`SUB_STANCE_MS`). A genuine fix would need to address the bistability
itself — e.g. a small deliberate L/R asymmetry maintained throughout the
run (not just at priming) — which is a different, not-yet-attempted class
of intervention, not a further parameter nudge. New files:
`results/stage1_fast_substance_{scaled,off040,off035,cap420,cap450}_seed*.h5`.

**Stage 1 status at the time (2026-09-15): 2 of 3 speed points confirmed
(medium, slow); fast excluded from the production scope below.** Medium
(τ=260/off=0.35/cap=450) and slow (τ=340/recovery=780/caps=585, 1.3× scale)
are both genuine and tightly cross-seed-confirmed. Fast has no confirmed
point after six attempts and should not be included in an MN5 submission
until solved in its own future pass. **Superseded 2026-09-16**: the
`--leg-fatigue-asym-frac` fix below resolves the bistability — see
"Persistent leg asymmetry breaks the fast/toe bistability."

**Production-scale (full N, BS=60Hz) sanity check, medium point, descending
arm, no `--consolidate` (2026-09-15).** Before scoping an MN5 run, checked
directly whether the confirmed medium operating point (last validated at
debug-small scale only, post-2026-09-14 architecture fix) even runs sanely
at production N — this was the outstanding flag from the "Core architecture
fix" re-confirmation above ("not yet checked at production N/BS=60Hz").
15s local run (`--step-period-ms 520`, same flags as `run_cutforce_sweep6.sh`
minus `--debug-small`): completed without error, `frac_at_cap` **0.00 both
legs** (genuine), bout duration 306±62/312±68ms — same ballpark as the
debug-scale confirmed value (308±27/310±29ms), corr(F-E_L,F-E_R) −0.526
(anti-phase). corr(Force-E,Force-F) itself was weaker (−0.41 L / −0.64 R)
than the debug-scale steady-state number, but 15s is almost entirely inside
the documented early recovery-transient window (steady-state metrics need
t≥30s) — not a discrepancy, just too short a smoke test to read as
converged. **Confirms the operating point is not broken at production
scale**, closing that outstanding flag; a full 60s+, two-seed production
confirmation (the actual Stage-0-at-production-scale bar) has not been run
locally — wall time is the reason: this 15s smoke test alone took 5m45s at
8 local threads (bookkeeping still ~91% of wall time, consistent with the
overhead noted earlier), so a proper 60s×2-seed local confirmation would
cost roughly an hour and was judged not worth spending before MN5
submission — a short array job on MN5 itself is the more efficient place to
get that confirmation, not a further local delay. New file:
`results/prodsmoke_medium_descending_seed12345.h5`.

**MN5 readiness verdict (2026-09-15, revised again after Stage 3's
loading-axis result above): ready for a scoped production run — 2
confirmed speeds × 2 arms, full weight-bearing only; loading axis and fast
speed both excluded pending their own passes.** Three things narrow this
submission below the original "all speeds and sensory ablation modes"
ask: Stage 1's fast direction remains open (bistable after 6 attempts);
Stage 2 found the medium-confirmed `--consolidate` gain pair actively
harmful at the slow point (12 configs, none genuine-and-stable); and Stage
3 found the medium timing config itself — independent of `--consolidate`
entirely — fails at toe and air loading in both arms (cap-domination at
toe, tick-floor chattering at air). The honest scope for the next MN5
submission is: medium + slow speeds (not fast), crossed with both arms
(descending/sensory), **full weight-bearing only** (not toe/air — those
need their own timing re-tune first, a "Stage 1 for the loading axis," not
yet attempted). `--consolidate` runs at medium only, at each arm's own
confirmed gain pair (0.20/0.15 descending, 0.25/0.10 sensory); the two
slow-speed cells run **without** `--consolidate` (a no-consolidate control
at slow, already confirmed excellent there — steady-state corrLR −0.822).
This ships only what's actually confirmed: no loading axis, no fast speed,
no consolidate at slow. See `run_consolidate_speed_arm_loading.sh` (now 4
cells × 3 seeds = 12 tasks, down from the original 8×3=24 once toe/air was
pulled).

### Stage 2 — `--consolidate` at the slow speed point, descending arm (2026-09-15)

Tests whether the medium-confirmed gain pair (0.20/0.15) transfers to the
slow operating point (τ=340/recovery=780/caps=585, off=0.35, 1.3× scale) —
the exact question Stage 2 exists to answer, not an assumption. **It does
not, and neither does anything else tried.** The no-consolidate reference
at slow is excellent on its own — steady-state `frac_at_cap` 0.00/0.00,
corr(F-E_L,F-E_R) **−0.822** (the best anti-phase number found anywhere in
this file). Turning `--consolidate` on, at any of 12 configurations tried
across three different axes, makes it worse:

| config | steady atCap L/R | steady corrLR | verdict |
|---|---|---|---|
| no-consolidate (reference) | 0.00/0.00 | −0.822 | excellent |
| 0.15/0.10 | 1.00/0.92 | −0.748 | cap-dominated (good number, disguised clock) |
| 0.15/0.15 | 0.47/1.00 | −0.601 | cap-dominated |
| 0.15/0.20 | 0.07/0.00 | +0.192 | genuine but degenerate (duration collapses to the 50ms tick floor on one leg) |
| **0.20/0.10** | 1.00/0.56 | +0.321 | cap-dominated **and** synchronized |
| **0.20/0.15 (medium-confirmed default)** | **0.96/0.96** | −0.069 | **cap-dominated, corrLR collapses toward zero** |
| 0.20/0.20 | 0.00/1.00 | −0.096 | mixed — one leg genuine, one leg fully capped |
| 0.25/0.10 | 0.96/0.00 | −0.191 | mixed, same asymmetric pattern |
| 0.25/0.15 | 0.92/0.88 | −0.581 | cap-dominated |
| 0.25/0.20 | 1.00/1.00 | −0.829 | cap-dominated (best-looking number, worst verdict) |
| 0.20/0.15, threshold=2.0 (slower capture) | 0.52/0.96 | +0.265 | still cap-dominated, now also synchronized |
| 0.10/0.05 (much weaker gains) | 1.00/0.92 | −0.818 | still cap-dominated despite weak gains |
| 0.20/0.15, `tau_tag_ms`=500 (vs. default 2000) | 0.15/0.07 | +0.022 | escapes cap-domination, but duration collapses to a chaotic ~70-140ms mean, corrLR is noise |

None of the three axes tested (gain ratio, capture threshold, tag decay
time constant) produces a config that is both genuine (low `frac_at_cap`)
and stable/anti-phase (reproducibly negative corrLR) — every attempt either
cap-dominates, synchronizes, or degenerates into chaotic/collapsed bout
durations. Even weakening the gains 4× below the working medium value
(0.10/0.05) still cap-dominates, which rules out "just needs a gentler
push" as the fix — something about `--consolidate`'s bookkeeping interacts
badly with the slow point specifically, not merely too-strong a gain
setting. A plausible mechanism, not yet confirmed: even a single early
capture event (seen in nearly every config above, "captures=1") locks in a
`cut→rge` baseline modestly above init (~4.3-5.8 pA vs. ~3.5 pA init) — at
medium this is harmless, but at slow's much longer stance/fatigue-recovery
window that small fixed excitatory increase may be enough to push force
decay past the off-threshold later than the unmodified-STDP case reaches
it, nudging bouts toward the 585ms cap. Not yet tested at a second seed —
this is a single-seed screen (12 configs, matching round 1's own original
single-seed-first methodology for the medium point), not a confirmed
negative; a second seed could in principle change the picture the way it
did for a few individual points in the medium-point round-2 bracket, but
given every one of 12 attempts across three different axes failed the same
way, that looks unlikely to flip the overall conclusion.

**Consequence for the MN5 script — fixed.** `run_consolidate_speed_arm_loading.sh`'s
two slow-speed cells (now labeled `slow_desc_full_noconsolidate`,
`slow_sens_full_noconsolidate`) no longer pass `--consolidate` at all —
they ship as a no-consolidate control at slow, which is already known to
be excellent there, rather than a gain pair this round showed to be
actively harmful. Sensory arm at slow was never itself tested with
`--consolidate` (Stage 2 only ran the descending arm) — moot now that
`--consolidate` is off for both arms at that speed. See "MN5 readiness
verdict" update below.

### Stage 3 — `--consolidate` at toe/air loading, medium speed, both arms (2026-09-15)

Set out to test whether each arm's confirmed medium-speed gain pair
(0.20/0.15 descending, 0.25/0.10 sensory) transfers to reduced loading —
the loading-axis analogue of Stage 2's speed-axis question. Ran
no-consolidate references plus the confirmed-pair test at toe
(`--ia-feedback-gain`/`--cut-feedback-gain` 0.5) and air (0.1) stepping,
both arms, seed 12345, same medium timing config (τ=260/off=0.35/cap=450)
throughout. **Result: the question of whether `--consolidate` transfers
doesn't arise, because the no-consolidate baseline itself is already broken
at both loading levels, in both arms:**

| config | steady atCap L/R | steady corrLR | steady duration | verdict |
|---|---|---|---|---|
| descending, toe, no-consolidate | 1.00/1.00 | +0.992 | 450±0ms | cap-dominated **and** synchronized |
| descending, toe, 0.20/0.15 | 0.00/0.07 | +0.291 | 57-97ms | escapes cap, but collapsed/erratic duration, synchronized |
| descending, air, no-consolidate | 0.00/0.00 | +0.738 | **50±0ms** | degenerate — pinned to the rate-update-ms tick floor |
| descending, air, 0.20/0.15 | 0.00/0.00 | +0.548 | **50±0ms** | same degenerate chatter |
| sensory, toe, no-consolidate | 1.00/1.00 | −0.758 | 450±0ms | cap-dominated (good-looking corrLR, disguised clock) |
| sensory, toe, 0.25/0.10 | 0.57/0.68 | −0.385 | 347-359ms | still substantially cap-dominated |
| sensory, air, no-consolidate | 0.00/0.00 | +0.753 | **50±0ms** | same degenerate chatter |
| sensory, air, 0.25/0.10 | 0.00/0.00 | +0.764 | **50±0ms** | same degenerate chatter |

Two distinct failure modes, neither caused by `--consolidate`:

1. **Toe stepping cap-dominates at steady state in both arms** — bout
   duration locks to exactly `--cut-max-stance-ms` (450ms) with zero
   variance, the same disguised-clock signature flagged throughout this
   file's "Force-triggered CUT" rounds. The reduced force ceiling under
   partial unloading apparently isn't reaching the 0.35 off-threshold
   within 450ms at this τ, the same class of problem rounds 1-2 solved for
   full loading by retuning τ/off-frac/cap together — never done for toe
   loading specifically.
2. **Air stepping doesn't cap-dominate — it chatters at the tick floor.**
   Every air condition, consolidate on or off, either arm, converges to
   *exactly* 50ms bout duration with zero variance — `--rate-update-ms`'s
   own tick granularity, the same chattering pathology already documented
   for Stage 1's fast-direction fine-tick attempts and for the original
   sensory-arm unloading-rescue work earlier in this file ("bout durations
   were a degenerate 50±0ms — chattering every tick"). Air stepping's much
   smaller force ceiling (see "Unloading-rescue attempt" above: ~7-9 vs. the
   normal ~17) makes the Schmitt trigger's relative on/off thresholds
   cross on tick-to-tick noise rather than a real envelope.

**This invalidates part of an earlier finding, not the whole thing.** The
"Toe/air stepping reproduce the paper's documented unloading degradation"
section above reported toe/air as a weaker-but-still-qualitatively-correct
version of the paper's finding, based on whole-run corr(Force-E,Force-F)
alone (r ≈ −0.09 to −0.62) — that correlation number itself isn't wrong,
but it was never checked against `frac_at_cap` or steady-state windowing,
the same two diagnostics this file has required for every other
force-trigger claim since round 1. Once checked, the "weaker rhythm" is
partly a disguised clock (toe) or outright chattering (air), not a clean
signal at reduced amplitude. The earlier finding's other claim — that
`MOD_IA_RG_LOADING_GAIN`'s `--wmax-ia-unloaded` cap-relaxation mechanism
engages correctly under loading — is unaffected by this (that was measured
directly from weight trajectories, not from timing diagnostics).

**Consequence: toe/air loading needs its own timing re-tune before any
`--consolidate` work there is meaningful — a "Stage 1 for the loading
axis."** Not attempted this round; scope note only. Pulled the four
medium-speed toe/air cells out of `run_consolidate_speed_arm_loading.sh`
(was 8 cells × 3 seeds = 24 tasks; now 4 cells × 3 seeds = 12 tasks —
medium/slow × descending/sensory, full weight-bearing only) rather than
ship cells known to be broken at the timing level. See "MN5 readiness
verdict" below for the updated scope.

**Also fixed in the same pass: a real shell portability bug, found while
building this round's test harness.** A space-joined flag string (e.g.
`LOADING_FLAGS="--ia-feedback-gain 0.5 --cut-feedback-gain 0.5"`) handed to
a command as unquoted `${LOADING_FLAGS}` is not guaranteed to word-split
back into separate argv tokens on every shell configuration — confirmed
directly in this session's own local shell, where it silently collapsed
into one unrecognized token instead of erroring cleanly, which is what
surfaced it. `run_consolidate_speed_arm_loading.sh`'s `ARM_FLAGS`/
`LOADING_FLAGS`/`CONSOLIDATE_FLAGS` used exactly this pattern; rewritten as
bash arrays (`ARM_FLAGS=(--freeze-bs-rg)`, expanded as
`"${ARM_FLAGS[@]}"`), which don't depend on IFS/word-splitting at all.
Smoke-tested end to end after the fix (debug-small, both arms) — confirmed
correct flag parsing, including `--freeze-bs-rg` correctly zeroing
`bs_rge`/`bs_rgf` plastic-synapse counts. This was latent in the version
committed for Stage 2 and could plausibly have misbehaved on MN5's shell
too, depending on its IFS/login-shell configuration — worth remembering as
a general pattern for any future script using this style of conditional
flag-building.

### Persistent leg asymmetry breaks the fast/toe bistability (`--leg-fatigue-asym-frac`, 2026-09-16)

Both open blockers left over from the previous session — Stage 1's fast
direction (bistable after 6 attempts) and Stage 3's toe-loading failure —
share the same signature: a genuine (non-cap-dominated), often
near-deterministic rhythm whose L/R phase relationship is decided by
run-to-run noise rather than any parameter tried. `--leading-leg`/
`--lead-offset-ms` only break L/R symmetry *at t=0* (the priming window);
by steady state, in these short/weak-bout regimes, nothing distinguishes
the two legs anymore and whichever phase relationship noise happens to
lock in persists for the rest of the run.

**Fix: a small, persistent (not just at-priming) L/R asymmetry.** Added
`--leg-fatigue-asym-frac` (`MOD_LEG_ASYM`, default 0.0 = exact no-op,
confirmed by regression check): the leading leg's `--fatigue-tau-onset-ms`
is scaled by `(1-frac)` (fatigues faster) and the other leg's by `(1+frac)`
(fatigues slower), for the whole run — a standing, bio-plausible asymmetry
(real limbs are not identical) rather than a one-time nudge.

**Both blockers respond to this fix, at different magnitudes:**

- **Toe stepping** (loading axis, medium timing anchor τ=100/off=0.35/
  cap=330/step-period=730, scaled down from the confirmed medium point for
  toe's reduced force ceiling — see below): `frac=0.10-0.12` converts a
  seed-flipping corrLR (+0.316 to −0.442 across earlier attempts) into a
  tight, reproducible small-negative value in both seeds
  (`frac=0.12`: steady corrLR −0.063 / −0.058, atCap 0.00/0.04, per-leg
  corr(F-E,F-F) −0.55 to −0.70). `frac=0.15` overcorrects (leg durations
  diverge too far, 259ms vs 130ms); `frac=0.05` is too weak (still flips
  sign, +0.497 at one seed).
- **Fast speed** (the SUB_STANCE_MS-scaled config from the previous
  session, cap=420/450, off=0.30, τ=195, step-period=750): `frac=0.06`
  converts the same seed-flipping pattern (−0.54 to +0.999 depending on
  seed) into tight, consistent small-negative corrLR (steady −0.088 /
  −0.104, both seeds fully genuine, atCap 0.00/0.00-0.04). `frac=0.12` at
  this same config over-corrects into cap-domination on one leg (the
  slower-fatiguing leg needs more time than the cap allows) — the working
  magnitude is config-dependent, not a universal constant.
- **A more aggressive fast point, only reachable with this fix**:
  step-period=600 (0.6× vs. the original 1000), τ=156/recovery=360/
  cap=380, off=0.30, lead-offset=90, `frac=0.04`. Fully genuine in both
  seeds (atCap 0.00/0.00 and 0.00/0.05) with tight, consistent corrLR
  (−0.010 / −0.015) — the magnitude is small (durations settle to two
  distinct deterministic values, R=700ms/L=750ms full cycle, rather than a
  strongly negative correlation), but it is stable and reproducible, not
  bistable. Full gait cycle ≈700-750ms vs. the medium point's 850ms — a
  genuine **≈13-18% speedup**, more distinct than the previous best fast
  point (τ=200/off=0.30, only ≈6% faster) and the first fast point found
  via structural scaling rather than a plateau at "barely faster."

**This is now the recommended lever for any future bistable force-trigger
operating point** — try it before concluding a config is fundamentally
unfixable. It does not (and is not expected to) fully restore the strongly
negative corrLR (−0.7 to −0.85) seen at the well-margined medium/slow
points; what it reliably does is convert an unusable bistable/seed-flipping
result into a small-but-stable, reproducible one. Not yet re-run at a third
seed or swept finely — the specific `frac` values above are single
2-seed-confirmed points, following this file's standard bar, not a
finished tuning round.

**Air stepping not attempted with this fix.** Steady-state force_e at air
loading (full unload, `--ia-feedback-gain`/`--cut-feedback-gain 0.1`) peaks
at only ≈0.84 a.u. at the medium timing anchor (vs. toe's ≈6.9 and full
loading's ≈17) — over an order of magnitude smaller than full loading, and
the Schmitt trigger's relative on/off thresholds (65%/29% of that tiny
peak, a ≈0.4 a.u. window) sit well within single-tick noise, which is the
likely reason air stepping chatters at the rate-update-ms tick floor
regardless of gain settings (Stage 3). This may not be a parameter-tuning
problem at all: the paper's own existing epidural-stimulation section
already frames *natural* air stepping as expected to collapse into
irregular, poorly-timed contact (corr −0.41, matching timer-mode data) —
a force-trigger analogue of that same natural condition may legitimately
be expected to fail to produce a clean closed loop, with the interesting
comparison being a force-trigger *epidural-stim analogue* (rhythmic CUT
drive held on independent of force, mirroring the existing timer-mode
epidural section) rather than a "fixed" natural-air-stepping timing.
Flagging this reframing rather than continuing to brute-force it — worth
discussing before spending more rounds on it.

### Consolidate transfers to fast and toe once `tau_tag_ms` is scaled up (2026-09-16)

With the fast and toe base-timing points now genuine (previous section),
tested whether `--consolidate` transfers to them — the same question
Stage 2/3 asked and failed for slow/toe. **It does, and the lever this
time was `--consolidate-tau-tag-ms` (default 2000, never varied in any
prior round), not the gain ratio.**

**Root cause found by inspection**: at the fast point, every gain
combination tried — even ones that never capture at all (0 capture
events) — showed suppressed `CUT→RG-E` growth (~13-17 pA final, vs. the
natural ~63-65 pA plateau every genuine operating point in this file
otherwise reaches). Consolidate's continuous tag→baseline leak runs
*regardless of captures* — it isn't gated on them — so at a shorter cycle
period, more leak-decay happens per unit of learning progress than at
medium/slow, and a fixed 2000ms time constant that was fine at ~850ms
cycles becomes actively suppressive at ~700-750ms ones. This also
explains why the earlier fast/slow consolidate failures always showed a
duration shift toward the cap even when captures never fired: it wasn't
a phase-locking problem at all, it was leaked-away excitation slowing
each stride's own force rise.

**Fast, descending arm, gain 0.20/0.15 (unchanged from medium) +
`tau_tag_ms=5000`**: fully genuine both seeds (steady atCap 0.00/0.00),
tight cross-seed corrLR (−0.008, −0.009 — nearly identical), `CUT→RG-E`
converges to ~62-65 pA with real captures (4 each), duration identical to
the no-consolidate reference (350/300ms). `tau_tag_ms=10000` works
equally well (−0.020). Sensory arm (gain 0.25/0.10, same `tau_tag_ms`)
**now confirmed at two seeds (2026-09-16)**: both genuine (atCap 0.00/0.00
both seeds), tight corrLR (+0.015, −0.040 — small magnitude, same as the
descending arm's own steady-state result, consistent not bistable),
healthy convergence to ~64 pA with 12-13 captures each seed.

**Toe, descending arm, gain 0.20/0.15 + `tau_tag_ms=20000`** (a much
longer constant than fast needed — toe's slower base dynamics, τ=100,
need the leak proportionally slower still): both seeds mostly genuine
(steady atCap 0.17-0.19 / 0.00-0.02 — the L leg carries a residual, not
fully clean, cap fraction, consistent with L already sitting closer to
its cap margin at this operating point even without consolidate) and
tight cross-seed corrLR (−0.067, −0.072). `tau_tag_ms=5000` (the value
that worked for fast) was tried first and did **not** work at toe
(atCap 0.82/0.73, corrLR bistable +0.395/−0.159) — confirming the right
`tau_tag_ms` scales with the *base* operating point's own time constants,
not a single universal replacement for 2000. Sensory arm (gain 0.25/0.10,
`tau_tag_ms=20000`) **now confirmed at two seeds (2026-09-16)**: slightly
cleaner than descending in both (atCap 0.06/0.00 and 0.02/0.00), tight
cross-seed corrLR (−0.045, −0.033 — nearly identical).

**Slow + consolidate: improved, not resolved — a genuinely different,
harder case.** Applying the same lever (gain 0.20/0.15, `tau_tag_ms=5000`
or `10000`) at the slow point gives one seed an excellent result
(corrLR −0.711 / −0.595, closely matching the −0.822 no-consolidate
reference) but the other seed synchronizes (+0.800) — still bistable, just
with `tau_tag_ms` fixing the cap-domination/degenerate-chatter failure
modes Stage 2 originally found and leaving a cleaner phase-locking
bistability behind. Adding `--leg-fatigue-asym-frac` on top (0.06, 0.10,
both leading-leg directions tried) shrank the bistable spread from
±0.6-0.8 down to ±0.08-0.12 but did not pin a consistent sign — one more
lever than fast/toe needed, not yet found. **Not shipped**: figures and
any future MN5 submission should run slow *without* `--consolidate`
(already excellent on its own, steady corrLR −0.822/−0.839) rather than a
config confirmed bistable.

**Net effect: 4 of 5 locomotion modes now have a genuine, reasonably
confirmed force-trigger-plus-consolidate story** (slow runs consolidate-free
by choice, not failure) — only air stepping remains unaddressed, per the
reframing above. Generated the full updated 5-mode × 2-arm force-stage and
weight-trajectory figures (`scripts/cpg_consolidate_force_stages.py`/
`cpg_consolidate_weights_grid.py`, single seed 12345 throughout for
comparability with the earlier 5-mode figure) —
`plots/final_locomotion_modes_force_stages.png` /
`final_locomotion_modes_weights_grid.png`. New result files:
`results/final_{desc,sens}_{slow,medium,fast,toe,air}.h5`. Copied into
`paper/figures/` as `fig_forcetrigger_all_modes_{force_stages,
weights_grid}.png`, replacing the superseded 3-speed-only figures, and
`paper/sections/results.tex`'s consolidate subsection rewritten to match
(see "Five locomotion modes, two learning architectures" and "The same
gain settings extend..." there).

### Fast/toe re-confirmed under the BS→RG write-back fix — one uniform gain across all three modes (2026-09-17)

The `0.20`/`0.15` gain confirmed above for fast and toe predates the
`BS→RG` write-back fix (see "Medium's tick-alignment fragility" below,
which found the same staleness for medium and fixed it there first). Re-ran
a single-seed gain screen (0.15/0.10, 0.20/0.10, 0.20/0.15, 0.25/0.10,
0.25/0.15) at each mode's own confirmed timing/`tau_tag_ms` (fast: τ=156/
off=0.30/cap=380, `tau_tag_ms`=5000; toe: τ=100/off=0.35/cap=330,
`tau_tag_ms`=20000), then confirmed the winner at a second seed — same
process just used for medium.

**Fast is robust to gain choice entirely** — all 5 ratios gave genuine
timing (`atCap`=0.00/0.00) and meaningful `bs→rge` suppression (12-15\,pA
vs. its ~18\,pA natural plateau); differences between them are noise-level
(`corrLR` −0.034 to +0.008). **Toe is more gain-sensitive**, with `0.25`/
`0.10` the clear single-seed standout (`atCap`=0.00/0.00, most captures
14/19, `corrLR`=−0.106 — the strongest anti-phase of the five, though still
modest in absolute terms).

**Two-seed confirmation, `0.25`/`0.10`** (the same gain just confirmed for
medium):

| mode | seed 1 (12345) | seed 2 (54321) | verdict |
|---|---|---|---|
| fast | atCap 0.00/0.00, corrLR +0.008, captures 12/13, bs→rge 14.9/14.8 | atCap 0.00/0.00, corrLR +0.009, captures 12/13, bs→rge 15.1/14.9 | **excellent — near-identical on every metric** |
| toe | atCap 0.00/0.00, corrLR −0.106, captures 14/19, bs→rge 12.1/10.9 | atCap 0.08/0.00, corrLR −0.032, captures 14/19, bs→rge 11.9/11.3 | **passes — same-sign both seeds, consistent captures/suppression, but corrLR shrinks ~3x and leg L keeps a small residual cap fraction (0.08)** |

Fast's confirmation is as tight a cross-seed match as anything in this
project's history. Toe's is real (same-sign corrLR both seeds, unlike the
sign-flipping failures documented elsewhere in this file, and captures/
suppression essentially identical across seeds) but weaker — its anti-phase
signal is modest and not fully clean on one leg.

**`0.25`/`0.10` is now the confirmed descending-arm gain for medium, fast,
AND toe — one uniform value instead of three separate per-mode tunings.**
This replaces every earlier descending-arm gain confirmation in this file
(the original `0.20`/`0.15` at medium, and its extension to fast/toe via
`tau_tag_ms` rescaling) — all of those predate the `BS→RG` write-back fix
and should not be treated as current. Not yet applied to
`run_consolidate_speed_arm_loading.sh` or `paper/sections/results.tex` —
same debug-small-only caveat as medium's own update above applies here too
(not yet checked at production N / MN5 scale).

### Medium's tick-alignment fragility and the consolidate leading-leg problem (2026-09-17)

While locally testing `MOD_WMAX_GROWTH` (below) against the medium+consolidate
operating point, the "baseline" (growth=0, i.e. should be an exact
reproduction of the already-shipped default) came back cap-dominated —
prompting a re-diagnosis of the actual shipped `results/final_desc_medium.h5`/
`final_sens_medium.h5` files with `--steady-from-ms 30000`. Both showed
`frac_at_cap=1.00` on both legs at steady state, contradicting this file's
own "confirmed, both seeds, steady corrLR −0.839" claim for medium. Fresh
seeds made this worse, not better: **13 of 13 local medium+consolidate
reproduction attempts** (6 seeds × baseline/growth, plus 1 thread-count
variant) landed 100% cap-dominated. Re-checking fast/toe the same way
(4 fresh seeds each, `--leg-fatigue-asym-frac` in place) found the opposite —
**genuine and tightly consistent in every single draw** (fast: atCap 0.00/0.00
all 4; toe: mild single-leg residual 0.13–0.28/0.00–0.05 all 4, matching
their own shipped numbers closely). Medium was uniquely broken; the other
three modes were not.

**Root cause 1 (base mechanism): exact tick-alignment.** Comparing each
mode's timing constants against the local `--debug-small` 50ms
rate-update/simulate-chunk tick: medium has **4 of 5** core constants
(`cut-max-stance-ms`=450=9×50, `lead-offset-ms`=150=3×50,
`step-period-ms`=1000=20×50, `fatigue-tau-recovery-ms`=600=12×50) landing
*exactly* on tick multiples, vs. only 1–2 of 5 for slow/fast/toe. This
matched a visible signature already in hand: medium's steady-state bout
durations were perfectly zero-variance and exact tick multiples (450±0ms,
400±0ms), unlike the genuinely jittery durations (±20–50ms) documented for
every other confirmed mode. Exact alignment appears to let the stance/swing
Schmitt trigger collapse onto razor-edge discrete states that flip
unpredictably depending on which side of a tick boundary NEST's
thread-order nondeterminism lands a spike on — plausible given this
project's own prior documentation of same-seed/same-config nondeterminism
(Stage 1's "Also surfaced during this work" note).

De-aligning by ~1% — `cut-max-stance-ms`/`cut-max-swing-ms` 450→453,
`fatigue-tau-onset-ms` 260→257, everything else unchanged — **cleanly fixed
the no-consolidate base mechanism**: steady corrLR −0.814/−0.799 (seeds
12345/54321, a tight cross-seed match, same quality bar as fast/toe's own
confirmations), atCap 0.00/0.00 both seeds, and genuine ±25ms bout-duration
jitter replacing the exact-tick zero-variance durations. A control sweep on
slow (4 fresh seeds, its own already-confirmed no-consolidate config) found
it is **not fully immune either** — 1 of 4 draws flipped to strongly
synchronized (corrLR +0.994) — but far less exposed than medium was (1 of 4
bad vs. medium's ~11 of 13), consistent with slow having only 2 of 5
constants tick-aligned vs. medium's 4 of 5. This reads as a graded,
dose-dependent relationship (more tick-aligned constants → more exposure to
a bistability that exists at every force-trigger operating point to some
degree), not a binary medium-only bug.

**Root cause 2 (consolidate-specific, separate from root cause 1):
`--consolidate` is still broken on top of the de-aligned base.** 14 configs
tried on the de-aligned config — 4 gain ratios (0.15/0.10, 0.20/0.10,
0.25/0.10, 0.25/0.15) × 2 seeds at the default `prp-threshold=1.0`, plus 3
threshold values (1.5/2.0/3.0) × 2 seeds at the best-looking gain pair
(0.20/0.10) — never got both legs genuine with a consistent-sign corrLR
across seeds. A clean, non-random pattern ran through every attempt: **leg L
(the non-leading leg, since `--leading-leg R`) was disproportionately the
one that locked up** — atCap ≥0.97 in most runs across every gain ratio,
every threshold, *and* the earlier `--leg-fatigue-asym-frac` test (both
directions — see "Persistent leg asymmetry" above), while leg R reached
atCap=0.00 cleanly in both seeds at 0.20/0.10 and 0.25/0.10 specifically.
Raising the capture threshold (to make captures rarer/later, hoping to miss
L's early-transient elevated weight) made things worse across the board,
including on the previously-clean leg R — ruling out "just needs fewer
captures" as the fix. This points at the priming/lead-offset asymmetry
itself interacting badly with `--consolidate`'s capture mechanism (the
lagging leg's `CUT→RG-E` synapse starts weaker and potentiates later per
"Force-triggered CUT" above, and a capture can freeze that leg's baseline at
an unluckily-elevated moment — `cut→rge` baseline jumping to ~19-60 pA from
a ~3.5 pA init was seen repeatedly on whichever leg got stuck) rather than a
gain/threshold tuning problem solvable by more parameter search.

**Decision: ship medium's base timing de-aligned, without `--consolidate`,
matching how slow already ships.** `run_consolidate_speed_arm_loading.sh`
updated 2026-09-17: `--consolidate` removed from all 4 cells (medium was the
only one that had it on); medium's stale `step-period=520` (never the
actually-tested value — every local confirmation, including this file's own
history, used 1000) fixed to `1000`. The debug-small-derived de-alignment
fix (453/257) was **not** applied to this production script's own
100ms-tick, full-N configuration — at 100ms, `cut-max-stance-ms`/
`fatigue-tau-onset-ms` are *already* not exact tick multiples (4.5/2.6
ticks), so the specific failure mode found at 50ms-tick debug-small may not
even apply at this discretization, and copying untested numbers across the
documented debug/production divergence would be guessing, not fixing.
Medium+consolidate needs its own dedicated pass into the leading-leg
asymmetry (e.g. a longer/differently-shaped priming window for the lagging
leg, checked at production scale) before being reconsidered — not another
blind gain sweep.

**Consequence for the paper's medium-mode figures**: `final_desc_medium.h5`/
`final_sens_medium.h5` (consolidate-on, tick-aligned) are superseded by
`final_desc_medium_v2.h5`/`final_sens_medium_v2.h5` (de-aligned,
no-consolidate, seed 12345, 2-seed-confirmed) — see "Five locomotion modes"
figures below for the updated set. The "Five locomotion modes, two learning
architectures" framing in `paper/sections/results.tex` needs revising:
medium no longer demonstrates `--consolidate` at all (joining slow as a
no-consolidate speed) — only fast and toe currently do.

**Update (2026-09-17, later the same day): the leading-leg problem above is
superseded, not by more parameter search on it directly, but by the
`BS→RG` write-back fix landing at the same time (see the top of "Tag-and-
capture consolidation" below) — a re-run of the descending-arm gain search
on the de-aligned base, now with `BS→RG` actually participating in
consolidation, found a new working point.** `0.25`/`0.10` (single-seed
screen: atCap 0.00/0.00, corrLR −0.773; confirmed second seed: atCap
0.00/0.00, corrLR −0.796 — a tight cross-seed match) is genuine on both
legs in both seeds, with `bs→rge` meaningfully and reproducibly suppressed
(~10–12 pA both seeds, vs. its natural ~18 pA plateau) — real, working
consolidation on all three pathways simultaneously, not just two. The old
default (`0.20`/`0.15`) is now confirmed *inert* on this fixed landscape
(0/1 captures, `bs→rge` untouched at ~4.2 pA, mostly cap-dominated) — a
different landscape than before, not merely a re-confirmation of the same
point. **`0.25`/`0.10` is the new descending-arm default for medium.**
`results/bsfix_gainsearch_g0.25_f0.10_seed{12345,54321}.h5` are the
confirming files; medium's row in the "Five locomotion modes" figures now
uses the seed-12345 file instead of the no-consolidate `final_desc_medium.h5`.

**This does not (yet) change `run_consolidate_speed_arm_loading.sh` or the
"ship without consolidate" MN5 scope decision above.** Everything in this
update was found at `--debug-small` scale (small N, BS=20Hz, 50ms tick) —
the same scale every other finding in this session was made at, and this
project has repeatedly documented debug/production divergence (see "Force-
triggered CUT"). Before re-enabling `--consolidate` for medium in the
production script: (1) re-verify the de-aligned base timing constants are
even meaningful at the production script's own 100ms tick and full N (the
tick-alignment mechanism itself doesn't obviously transfer — see the caveat
in the "Decision" paragraph above); (2) re-run this exact gain confirmation
at production scale, not just debug-small. **Fast and toe's own
descending-arm consolidate configs (`0.20`/`0.15` at each) also predate the
`BS→RG` write-back fix and are stale in the same way medium's was** — not
yet re-confirmed under the fix, flagged but not yet acted on.

### Medium+consolidate at production scale — one cell back from MN5, genuine but on stale code (2026-09-21)

`results/2026-09-21/` came back with a single file
(`cpg_consol_sal_medium_desc_full_idx00_mu03.50_cv00.30_seed12345.h5`), not
the 12-task batch `run_consolidate_speed_arm_loading.sh` currently defines —
no slurm logs, and the file's own attributes (`consolidate=True`,
`step_period_ms=520`, gains `0.20`/`0.15`) match the **pre-2026-09-17**
version of that script, before `--consolidate` was pulled out and the
520→1000ms step-period bug was fixed. So this tests the old medium+
consolidate config at production scale (full N, BS=60Hz, 120s), not what the
script currently ships — a leftover/orphaned run, not part of the 12-cell
batch.

**Result: genuine, not cap-dominated, anti-phase — the production check this
file's "Core architecture fix" section had flagged as outstanding.**
`scripts/cpg_cutforce_diagnostics.py --steady-from-ms 30000`: `frac_at_cap`
0.00/0.00 both legs, corr(F-E,F-F) −0.67(L)/−0.70(R), corr(F-E_L,F-E_R)
−0.78, stance 301±16ms. Whole-run numbers (−0.64/−0.69/−0.75) are pulled
slightly weaker by the first ~20s recovery transient (corr(F-E,F-F) −0.47/
−0.66 in that window) — same transient this file has documented for every
other `--consolidate` config, not new.

**Three things worth flagging, none of them a regression:**

1. **Consolidation slows CUT→RG-E's convergence ~5x without changing its
   plateau.** Reaches 90% of its ~61 pA final value at 28-29s, vs. 5-6s for
   vanilla STDP on the same operating point (compared directly against
   `results/2026-09-07/cpg_cutforce6_robustness_idx04_*.h5`, same μ=3.5/
   CV=0.30 point, old circuit but same plateau). The capture staircase is
   clearly visible in the weight trace. This is consolidation doing its
   intended job (a genuine settling-in period instead of instant
   convergence, the whole point per `spinal_plasticity_as_learning_spec.md`),
   not a new finding, but it's the first time it's been shown at production
   N rather than debug-small.
2. **Captures land almost exactly every 13.6s, both legs, all 8 captures** —
   because swing always ends on the failsafe (already documented: "Swing has
   no closed-loop signal at all — it is a pure timer, always"), every cycle
   contributes the same +0.20 (genuine stance) / −0.15 (forced swing) net
   push to the PRP pool regardless of bout quality. At this operating point
   the mechanism is not yet discriminating genuine-vs-forced *quality*, just
   accumulating a fixed net drift that happens to cross threshold on a
   metronomic schedule. Worth stating plainly if this operating point is
   used to illustrate consolidation in the paper.
3. **Steady-state bout timing is fully quantized by the 100ms production
   tick** (stance 300±0ms in the 60-80s and 100-120s windows exactly; swing
   exactly 500ms, the 450ms cap rounded up to the next tick) — `frac_at_cap`
   is genuinely 0 (300ms is well below the 450ms cap), but the previously-
   claimed "~9% cycle-to-cycle variability" argument for debug-scale medium
   doesn't carry over to production resolution: at 100ms ticks this is a
   locked, deterministic limit cycle, not a jittery one. Steady-state force
   amplitude is also much lower here than the debug-scale numbers quoted
   elsewhere in this file (Force-E 99th-percentile ≈5.3, Force-F ≈3.9,
   troughs ≈0) — but this matches the vanilla-STDP old-circuit run at the
   same operating point almost exactly (5.3-5.4 / 4.0-4.5), so it's a
   property of this operating point at production scale generally, not
   something consolidation changed.

**Consequence: does not confirm or extend the current
`run_consolidate_speed_arm_loading.sh` scope.** The script now ships medium
*without* `--consolidate` and at `step-period=1000` (post-2026-09-17); this
file tests neither. It's supporting evidence that medium+consolidate *can*
be genuine at production scale in principle, but the actual re-confirmation
needed before re-enabling it in the script — current code (BS→RG write-back
fix), current gain (`0.25`/`0.10`), current step-period (1000) — has not
been run. The other 11 cells of the intended batch (slow, sensory arm,
seeds 2-3) were also not present in this folder.

### Sensory-driven mode (`--freeze-bs-rg`, now just freezing BS since Ia→RG is always on — WMAX_IA=10)

Learning shifted from descending (BS) to sensory (muscle-Ia) pathway: BS→RG frozen at
weak init, plastic homonymous Ia→RG added. **Validated to outperform the BS-plastic
control** (debug-small, paced, 25 s): corr(Force-E,Force-F) **−0.978 vs −0.955**,
corr(RGE,RGF) −0.813 vs −0.788, and the **weak flexor is fixed** — Force-F peak rises
**11→17 a.u.** with clean troughs (F-E min 0.16). Mechanism: a light phased Ia→RG loop
reinforces each burst without filling the inter-burst trough; raising WMAX_IA saturates
it into tonic co-excitation that destroys counter-phase (monotonic in the sweep). This is
the bio-plausibility win the debug goal was after: self-sustained counter-phase on weak
tonic BS + closed-loop proprioception.

**Confirmed at production scale** (full N, BS=60 Hz, paced, 15 s): corr(RGE,RGF) **−0.965**,
corr(F-E,F-F) **−0.983**, Force-E/F peaks **16.7/16.7** (fully balanced), troughs ~1.0–1.1,
CUT→RGE→62.4, Ia→RG self-stabilises at **~4.5 pA** (same as debug — robust, sub-cap).
Cleaner than debug-small. Production sweep: `rat-sh/run_sensory_stdp.sh` (sensory-learning arm,
mirrors `rat-sh/run_speed_stdp.sh` for a descending-vs-sensory paired contrast).

## Architecture

```
              CUT (cutaneous, phasic)         BS (brainstem, tonic)
               │ static + STDP                 │ STDP, Wmax=30
               ▼                               ▼
              RG-E ◄──── InF ◄───── RG-F   (asymmetric: F→E STRONG, E→F WEAK)
               │          ▲          │
               │          │          │
               ▼     (Ia loop)       ▼
              M-E                   M-F        (motor pools, reciprocal inhibition)
               │                     │
               ▼                     ▼
              mus-E                 mus-F      (parrot relays → activation proxy)
               │                     │
               └───── force, length ─┘
                          │
                          ▼
                         Ia-E, Ia-F  (rate-coded, force + stretch)
                          │
                          └──→ InE, InF, ia_int → motor antagonist
```

Cross-leg: L↔R commissural inhibition on RG-F (strong) and RG-E (weak).

## Key constants in `cpg_2legs_fast.py`

| Constant | Where | Notes |
|---|---|---|
| `BS_REGULAR_HZ = 60` | line ~80 | Tonic BS rate. `--debug-small` drops to 20. |
| `CUT_RATE_ON_HZ = 100` | line ~66 | Rat Group-II/Aβ peak rate. Don't push >100 Hz. |
| `W_INF2RGE = -48`, `W_INE2RGF = -8` | lines ~75-82 | **Asymmetric reciprocal inhibition (Zhang 2022). KEEP THIS RATIO.** F→E is 6× stronger (48:8). |
| `WMAX_BS = 30` | line ~236 | BS STDP weight cap, prevents BS-alone runaway. |
| `W_CUT2INE = 6`, `P_CUT2INE = 0.30` | line ~266 | Stance-phase cutaneous reflex. |
| `W_IA2IN = 6`, `P_IA2IN = 0.25` | lines ~69-70 | Ia → RG reciprocal interneurons. Closed-loop knob. 5 too weak; 8 over-speeds cycle. |
| `RGF_C = -55, RGF_D = 4` | line ~288 | Intrinsically bursting Izhikevich for RG-F. |
| `rg_ref = 100` | line ~1190 | Activation gate reference Hz. 100 Hz calibrated for debug-mode burst peaks; clamps to 1 in production (300+ Hz). |
| `ACT_SAT_K = 0.02` | line ~291 | Activation saturation slope. **Was 5e-4 (40× too small) — regression fixed.** |
| `TAU_ACT_RISE/DECAY_MS = 20/20` | line ~288 | Activation time constants. Tuned for 150–200 ms debug cycles. **Overridden to 40/40 by `--paced-gait`.** |
| `TAU_FORCE_RISE/DECAY_MS = 30/30` | line ~294 | Force time constants. Rat fast-twitch range. **Overridden to 80/80 by `--paced-gait`.** |
| `FORCE_SAT_K = 1.0` | line ~301 | Force saturation. K=1 keeps force linear. |
| `N_INF = 40` (debug-small) | line ~792 | Doubled in debug-small to give 12 InF connections per RGE vs 6 at N=20. |
| `--step-period-ms 1000` | `rat-sh/debug.sh` | Full gait cycle period. HALF_MS=500ms per leg. |
| `--n-ia-groups 3` | `rat-sh/debug.sh` | Heel/mid/toe sequential Ia-E groups (60/80/100 Hz). Each active 167ms. |
| `config/species/*.yaml` | — | **Species configuration (PLAN.md P1).** Species-dependent constants (drive, afferents, muscle τ incl. `PACED_TAU_*`), CLI defaults and the per-path delay table. Loaded by `species_config.py`, applied by `apply_species_constants()` before anything else runs. Only existing numeric constants can be set, so a typo fails. The human `delays:` section **still gives rat-like ~2 ms delays** until Phase 2. |
| `FLEXOR_BS_GAIN` | line ~128 | Flexor BS gain, set per species (`constants.drive`). `1.00` for both rat and human. |

## Modification history (grep-friendly)

| Tag | What it does |
|---|---|
| `MOD_RECORDER_CLEAR` | **2026-09-25 (PLAN.md §7 B14).** `new_spikes()` clears each spike recorder (`n_events = 0`) after reading its count. A NEST status read costs O(stored events), so the never-cleared recorders made bookkeeping grow with the square of simulated time (MN5 Round 6: ~135 s NEST vs ~17,000 s bookkeeping). The recorders are only used for these per-chunk counts, and the outputs are byte-identical. **Never read a recorder's `events` array without clearing it.** |
| `MOD_CONN_INDEGREE` | **2026-09-26 (PLAN.md P3b, §7 B16).** `--conn-rule {bernoulli,indegree}`; human default `indegree` (species `cli_defaults`), rat `bernoulli`. All 31 projections go through `connect()`:<br>• `bernoulli` is the original `pairwise_bernoulli(p)`, byte-identical (`./regress.sh`);<br>• `indegree` uses `fixed_indegree` with K = round(K\*), K\* = p × production size of the source (`N_REF`, captured before `--debug-small`/`--n-scale`), so the mean input per neuron no longer depends on N;<br>• multapses only when the source is smaller than K (down-scaled runs); a static weight is scaled by K\*/K when K\* is fractional (`ia_ext_e->in_e` 8.25, `in_e->rg_f` 7.5);<br>• `connectivity.indegree_override: {projection: K*}` in the species YAML overrides K\* per projection (Phase 9);<br>• the M→mus fan-in used for the muscle rate is the built K.<br>Under `indegree`, `--debug-small` keeps the configured BS rate (the 20 Hz was an in-degree compensation). `--n-scale s` multiplies every population size (size sweep; not with `--debug-small`). HDF5 attrs `conn_rule`, `n_scale`, `conn_table_json`, `n_pop_json`, written only when not bernoulli ×1 (absent = original wiring). |
| `MOD_CONSOLIDATE` (B13 fix) | **2026-09-26 (PLAN.md P3b).** Consolidation baselines, capture and tag decay use the **full** synapse collection of each plastic pathway (`conns_full_cache`), not the `--max-weight-conns` stats subset; before, only ~40% of each pathway was consolidated at production N. Attr `consolidate_frac_synapses` (must be 1.0). Cost: the decay step reads and writes every plastic weight from Python each `--rate-update-ms` tick, ~2.6 µs per synapse (no faster NEST call exists); at N = 100 that is ~30k synapses per tick, bookkeeping ~2× NEST time. Infeasible at adult size: needs an in-NEST synapse model (MN5 check B). |
| `MOD_PHASE_GAIT` | **2026-09-25 (PLAN.md P3).** `--gait-scheduler phase`, the human default via the species config. It is a per-leg timer schedule:<br>• each leg is in stance for `stance_fraction × stride`, the right leg offset by half a stride;<br>• `stance_fraction > 0.5` gives double support, `< 0.5` gives flight;<br>• the heel→toe Ia-E groups step through each leg's own stance;<br>• the flexor swing afferent is on during that leg's swing;<br>• the CUT stretch term is per leg, and `cut_on` is logged per leg.<br>`halfcycle` (the rat default, the original `MOD_PACED_GAIT` loop) is unchanged. It passes one CUT fraction to both legs (legacy quirk). Force-trigger mode ignores the flag. Metrics: `scripts/cpg_gait_phase_metrics.py`; figure: `scripts/cpg_gait_phase_figure.py`. |
| `MOD_DETERMINISM` | **2026-09-24 (PLAN.md §7, B11/B12).** `sorted_connections()` puts every connection list used positionally in a fixed order: the static-weight heterogeneity factors, the plastic `conns_cache` (the `--max-weight-conns` subset and consolidation baselines) and `--dump-connectivity`. NEST `rng_seed` is set from the run seed (`nest_rng_seed` HDF5 attribute). numpy is seeded in every mode, not only in sweep mode. Runs are now bit-reproducible for a given seed and thread count. Rat outputs from before this change are not reproducible bit-for-bit, and before it "different seeds" shared all NEST randomness. **Always use `sorted_connections()` when pairing connections with numpy arrays.** |
| `MOD_TONIC_BS` | BS is constant-rate, identical for both legs (not phase-gated). |
| `MOD_COACT` | BS subthreshold alone; CUT co-activates RG via static pathway. |
| `MOD_ZHANG_ASYM` | F→E inhibition 6× stronger than E→F (W_INF2RGE=-48, W_INE2RGF=-8). |
| `MOD_CUT_REFLEX` | CUT → InE (stance-phase cutaneous reflex). |
| `MOD_ACT_GATE` | Activation gated by RG rate (rg_ref=100 Hz, ACT_GATE_POWER=2). |
| `MOD_FORCE_LINEAR` | FORCE_SAT_K=1.0 — force linear in working range. |
| `MOD_DEBUG_SMALL` | Small-N + low-BS local debug mode; N_INF=40 (doubled). |
| `MOD_IA_LOOP` | Ia → InE/InF closed-loop sensory drive into CPG core (W_IA2IN=6). |
| `MOD_PACED_GAIT` | Explicit 1-s trot cycle: L/R 180° offset, sequential Ia-E heel→toe during stance. |
| `MOD_CUT_FORCE_TRIGGER` | `--cut-trigger force`: replaces the paced-gait clock with a per-leg Schmitt trigger on `force_e` (CUT ON/OFF at `--cut-force-on-frac`/`--cut-force-off-frac` of a per-bout running peak — "foot touches"/"foot lifts"). `--leading-leg`/`--lead-offset-ms` break initial L/R symmetry (the offset window is also a symmetric CUT→RG-E STDP priming window). `--cut-max-stance-ms`/`--cut-max-swing-ms` are a required failsafe timeout (RG-E has no self-terminating burst mechanism and locks permanently without it — see "Force-triggered CUT" above). Logs a per-leg ground-truth `cut_on` (0/1) array to the output HDF5 so `scripts/cpg_cutforce_diagnostics.py` can measure exact bout durations instead of reconstructing them from force. Requires `--paced-gait`. Production-scale tuning not yet confirmed — see "Force-triggered CUT" above and `run_cutforce_sweep2.sh`. |
| `MOD_MUSCLE_FATIGUE` | `--muscle-fatigue`: opt-in (OFF by default) slow activity-dependent force attenuation (`--fatigue-tau-onset-ms`/`--fatigue-tau-recovery-ms`/`--fatigue-max-frac`), so `force_e` can decay on its own during sustained activation instead of relying entirely on the `--cut-trigger force` failsafe cap. Only affects the force proxy, not the neural circuit. |
| `MOD_FREEZE_BS` | `--freeze-bs-rg`: BS→RG-E/RG-F static (no STDP), held at weak lognormal init (W_INIT_BS). BS becomes fixed tonic drive; Ia→RG and CUT→RG keep training regardless (see MOD_IA_RG_STDP). |
| `MOD_IA_RG_STDP` | **Always wired, always plastic homonymous Ia→RG** (Ia-E→RG-E, Ia-F→RG-F, Wmax=WMAX_IA=10, density P_IA2RG_STDP=0.5) — matches the reference architecture diagram's direct excitatory Ia→RG projection (distinct from the Ia→InE/InF reciprocal-inhibition loop, MOD_IA_LOOP). A third standing plastic pathway alongside BS→RG and CUT→RG in every mode (2026-09-14 — previously gated behind `--stdp-ia-rg`, opt-in only for the sensory-learning arm; see "Core architecture fix" below for why). `--wmax-ia`/`--p-ia2rg` still override the cap/density. |
| `MOD_CONSOLIDATE` | `--consolidate`: opt-in (OFF by default), requires `--cut-trigger force`. Replaces vanilla STDP's "every potentiation kept forever, up to Wmax" retention with tag-and-capture consolidation on **all plastic pathways** — `CUT→RG-E`, `Ia→RG-E/F`, and `BS→RG-E/F` when not frozen: `weight` still evolves via native `stdp_synapse` (unchanged, the fast/local tag-setting process); a new per-connection `baseline` is the captured/stable component, and the live tag (`weight − baseline`) decays toward it with time constant `--consolidate-tau-tag-ms` unless a shared per-leg PRP-pool-like accumulator crosses `--consolidate-prp-threshold` first (genuine force-threshold bout endings push it up via `--consolidate-prp-gain-genuine`, failsafe-forced endings push it down via `--consolidate-prp-gain-forced`, matching Grau's finding that non-contingent outcomes actively suppress rather than merely fail to reinforce). `Wmax` is untouched on every pathway, including `BS→RG` — this governs retention *within* the existing ceiling (including `WMAX_BS`'s anti-runaway role), not the ceiling itself. **Changed 2026-09-17** (explicit user request): `BS→RG` previously got identical bookkeeping but was never written back to NEST (vanilla-STDP-only in practice); confirmed by direct test that the fix is live — `bs→rge` now converges to ~4.4 pA under consolidation instead of its natural ~18 pA plateau. **This changes the dynamics of every existing descending-arm (non-frozen-BS) `--consolidate` result generated before this fix** — see the note under "Tag-and-capture consolidation" below. See that section for the literature basis and first-pass verification results. |
| `MOD_LEG_ASYM` | `--leg-fatigue-asym-frac`: opt-in (default 0.0, exact no-op — regression-checked), requires `--muscle-fatigue`. Scales `--fatigue-tau-onset-ms` by `(1∓frac)` per leg (leading leg fatigues faster), a *persistent* L/R asymmetry rather than the one-time priming `--lead-offset-ms` already provides. Fixes the bistable-L/R-phase-locking failure mode seen at several short/weak-bout force-trigger operating points (fast speed, toe loading) — see "Persistent leg asymmetry" below. Does **not** fix medium+consolidate's own leading-leg problem (tried both directions — see "Medium's tick-alignment fragility" below). |
| `MOD_WMAX_GROWTH` | `--consolidate-wmax-ia-growth-per-capture`: opt-in (default 0.0, exact no-op — regression-checked), requires `--consolidate`. Each capture event on `Ia→RG-E`/`Ia→RG-F` (only — not `CUT→RG-E`, not `BS→RG`) raises that connection's own `Wmax` by the given amount, capped at `--consolidate-wmax-ia-ceiling` (default 60). Structural consolidation of the ceiling itself (Wolpaw Phase I→II), not just retention beneath a fixed cap — addresses a gap `spinal_plasticity_as_learning_spec.md` §4 names explicitly for `Ia→RG`. Verified correct by direct HDF5 inspection (2026-09-17): flat when off or when a run captures zero times, steps by exactly the configured amount on each real capture. **No observable effect yet at full loading** — `Ia→RG` weights sit at ~3.5-4 pA there, nowhere near even the base `Wmax=10`, so raising an already-slack ceiling changes nothing. Only meaningful where Ia→RG is actually cap-constrained, i.e. toe/air loading (`wmax_ia_effective` already relaxed to 35 via `--wmax-ia-unloaded` there) — not yet tested in that regime. |
| `--ia-feedback-gain` | Multiplicative gain on closed-loop Ia rate. 1.0 baseline / 0.5 toe stepping / 0.1 air stepping (Courtine/Lavrov SCI paradigm). |
| `--cut-feedback-gain` | Multiplicative gain on cutaneous CUT stance drive (loading-dependent paw contact). Scaled with loading alongside `--ia-feedback-gain`; the external Ia-E heel→toe ramp (stim pacing) stays at full. |
| `--ia-ext-f-hz` | MOD_FLEXOR_AFFERENT: rate (Hz) of the external flexor swing-afferent (hip/flexor-stretch signal; Grillner & Rossignol 1978). Drives RG-F directly + InF during swing, clocking the flexor symmetrically to the stance Ia-E ramp. 0 = off (intrinsic-only flexor); 80 = on. Un-gated by loading (joint-position, not load-based). |
| `--stdp-lambda` | Override STDP LAMBDA (default 1e-3). Bio-plausible range 5e-4 to 5e-3 (Bi & Poo 1998; Morrison 2007). |
| `--dump-connectivity` | Build the network, write per-connection WEIGHT + DELAY arrays for all 18 named projections to an HDF5, then exit (no sim — runs in seconds at production N). Feeds the connectivity-statistics figure (`scripts/cpg_connectivity_figure.py`) and CSV table. Static weights are delta-valued; plastic are lognormal-init; delays follow the rat `length_velocity` preset + 0.2 ms jitter. |
| `--freeze-bs-rg` | MOD_FREEZE_BS: freeze BS→RG (static at weak init). Removes descending plasticity only; Ia→RG and CUT→RG keep training (always on, see MOD_IA_RG_STDP). Frozen runs drop `bs->rge`/`bs->rgf` from the tracked plastic-weight keys. |
| `--stdp-ia-rg` | **DEPRECATED/no-op** (2026-09-14): plastic homonymous Ia→RG is now always wired (MOD_IA_RG_STDP). Flag kept only so old scripts passing it don't break. |
| `--wmax-ia` | Weight cap for Ia→RG STDP (default 10). **Low cap is critical**: homonymous Ia→RG is in-phase positive feedback — light (≤10) reinforces bursts without filling troughs; high (≥60) saturates into tonic co-excitation that destroys counter-phase. |
| `--p-ia2rg` | Connection probability of the Ia→RG projection (default 0.5). |
| `--static-weight-cv` | **Bio-plausibility (default 0.5):** per-connection lognormal weight heterogeneity on all static synapses (mean/sign preserved). Biological weights are lognormal (Song 2005; Buzsáki & Mizuseki 2014). `0` = legacy delta weights (used by the frozen-weight control). |
| `--cut-static-w` | **Bio-plausibility (default 0 = dropped):** weight of the fixed CUT→RG-E co-activation pathway. Default leaves a single plastic cutaneous projection; set `14` to restore the legacy bootstrap. |

## Bio-plausibility constraints (human)

| Quantity | Range | Source |
|---|---|---|
| Stride period (comfortable walking) | ~1.0–1.2 s (cadence ~100–120 steps/min) | Perry & Burnfield 2010 |
| Stance / swing split | ~60% / ~40% of the gait cycle; ~10% double support at each end | Perry & Burnfield 2010 |
| Comfortable walking speed | ~1.2–1.4 m/s | Bohannon & Andrews 2011 |
| Soleus H-reflex latency | ~30 ms | Palmieri et al. 2004 |
| Peripheral path (soleus ↔ L5/S1) | ~0.8–1 m each way (adult; scales with height) | anthropometric estimate |
| EES for stepping-like EMG in complete SCI | ~25–50 Hz (5–15 Hz → tonic extension) | Minassian et al. 2004 |
| Rehabilitation time course (EES + training) | weeks to months | Harkema et al. 2011; Angeli et al. 2018; Gill et al. 2018; Wagner et al. 2018 |
| BS reticulospinal | 20–80 Hz (cat/rat proxy; no direct human recordings) | Drew, Rossignol |
| CUT peak rate | ≤100 Hz until checked against human plantar afferents | Kennedy & Inglis 2002 (to verify) |

Don't push values outside these ranges without flagging it. Rows marked "to verify" or
"proxy" are provisional: check the source before building a result on them.

### Rat constraints (inherited reference, for `--species rat` regression runs)

| Quantity | Range | Source |
|---|---|---|
| BS reticulospinal | 20–80 Hz | Drew, Rossignol |
| CUT Group-II / Aβ | 80–100 Hz peak | Loeb, Pearson |
| Locomotor cycle | 400–700 ms | Bellardita & Kiehn 2015 |
| Rat trot speed | ~30 cm/s | Lemieux et al. 2016 |

## What "good" looks like in debug output

- Clean alternation: RG-E vs RG-F correlation < −0.85
- Force-E vs Force-F correlation < −0.80
- Force minima < 2, peaks > 12, both half-centers
- L vs R legs not perfectly synchronised
- Cycle period in range for the species: human ~1.0–1.2 s at comfortable speed (stance ~60%);
  rat 400–700 ms for `--species rat` regression runs
- Activation reaches 0 cleanly between bursts

## What "broken" looks like

- Everything dies → BS too low for current Ia loop strength → bump `W_IA2IN` or `P_IA2IN`
- One half-center locked permanently → inhibition asymmetry too extreme → reduce `|W_INF2RGE|`
- Both legs synchronised → commissural too weak → bump `W_COMM_F_INH`
- Force flat-tops at 17 → `FORCE_SAT_K` regressed; should be 1.0
- Activation rides at 0.5 constantly → `rg_ref` too low; should be ~100 Hz (debug) — gate always clamped to 1 means no burst/trough discrimination

## Debug iteration pattern

1. Edit one knob in `cpg_2legs_fast.py` (typically `W_IA2IN`, `P_IA2IN`, `BS_REGULAR_HZ`, or one of the `W_*2*` weights)
2. `./rat-sh/debug.sh`
3. `python3 scripts/cpg_plot_from_hdf5.py --in results/debug.h5 --save-prefix debug`
4. Inspect `debug_legL_rg_rate.png`, `debug_legL_force.png`, `debug_legL_activation.png`
5. Repeat

Each iteration is ~30 s. Don't edit `rat-sh/run.sh` during debug.

## When ready for MN5

1. Verify alternation works at BS=20 Hz with `./rat-sh/debug.sh`
2. Verify it still works at BS=60 Hz: remove `--debug-small` from `rat-sh/debug.sh` and re-run with `--sim-ms 5000`
3. `sbatch rat-sh/run.sh`
4. After completion, plot one HDF5 to confirm: `python3 scripts/cpg_plot_from_hdf5.py --in results/cpg_bursting_commfix_idx04_*.h5 --save-prefix solid_bs`

## Things NOT to touch without flagging the user

- The asymmetric inhibition ratio (`W_INF2RGE` / `W_INE2RGF` ≈ 6:1) — this is the Zhang 2022 finding
- The `--enforce-tonic-bs` semantics — bio-plausibility commitment
- `bs_rates_tonic` — should return identical values for both legs
- `BS_REGULAR_HZ` upper bound — keep below 80 Hz (reticulospinal; cat/rat proxy, also used for human)
- `CUT_RATE_ON_HZ` upper bound — keep below 100 Hz (rat Group-II/Aβ; human plantar-afferent range still to verify)
- `config/species/rat.yaml` and the rat mode timing in the inherited `run_*.sh` scripts — the rat model is the regression baseline. Put human changes in the `human` preset and in new `*_human` scripts
- Default `--species rat`. Switching the default to `human` changes every inherited script's behaviour
