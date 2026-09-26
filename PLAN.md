# PLAN — Migrating the rat NEST CPG model to human parameters

Status: **in progress** (2026-09-24). Decisions D1–D7 are agreed (§4).
**Done:** Phase 0 (rat regression harness; B11/B12 reproducibility fixes) and
Phase 1 (YAML species configs, delays tied to species), Phase 2 (human
conduction delays, reflex probe at 30 ms), Phase 3 (phase scheduler, human
stance 0.60 with double support) and MN5 check A (five modes at production N).
**Next:** Phase 3b (size-invariant connectivity, plus the B13 fix), then MN5
check B (scaling benchmark and MPI-safe loop) alongside Phase 4. Both were moved
forward on 2026-09-26 so that everything tuned from P4 on carries over to the
adult-size model (P9) without re-tuning.

This plan moves `cpg_2legs_fast.py` from rat to human parameters. The circuit,
plasticity and consolidation mechanisms stay the same. What changes is timing,
delays, muscle and afferent dynamics, the SCI and stimulation protocol, and the
validation data. The rat model must keep working unchanged as the regression
baseline.

Contents:

1. The human CPG model
2. Migration phases
3. Order and dependencies
4. Decisions
5. References to verify
6. Guiding principles
7. Current state: what blocks a human run

---

## 1. The human CPG model

### 1.1 Circuit

![tinyCPG two-leg spinal CPG schematic](paper/figures/fig1_schematic.png)

*Figure 1 — Two-leg spinal CPG schematic
([`paper/figures/fig1_schematic.png`](paper/figures/fig1_schematic.png)).
Orange: excitatory populations. Blue and dark blue: inhibitory populations.
Boxes: muscles, afferents and brainstem projections.*

The two legs are mirror images. Each leg has:

- **A rhythm generator with two half-centres:** an extensor half-centre
  (**RG-E**) and a flexor half-centre (**RG-F**). They inhibit each other
  through the inhibitory interneurons **InE** (E → F) and **InF** (F → E). The
  inhibition is asymmetric: F→E is about 6× stronger than E→F (Zhang 2022).
  This ratio is a core commitment of the model.
- **A motor layer.** The motoneuron pools **M-E** and **M-F** drive the
  muscles **mus-E** and **mus-F**. Muscle activity is converted into force and
  length, which set the rates of the **Ia** afferents. The Ia afferents
  project back onto the motoneurons and onto the Ia inhibitory interneurons
  **Ia-E** and **Ia-F**, which provide reciprocal inhibition between the
  antagonist motor pools. This closes the sensory loop.
- **Afferent inputs to the rhythm generator.** The **cutaneous** afferent
  (**cut**), a foot-contact/stance signal, and the **Ia** afferents excite
  their own-side rhythm-generator half-centre (CUT→RG-E, Ia→RG-E/F).
- **Descending drive.** Tonic brainstem (reticulospinal) projections, **BS to
  E** and **BS to F**, reach both legs' half-centres.

**Left–right coupling.** The figure shows the biological commissural classes
(Shevtsova 2015; Danner 2017):

- V2a → V0v → In1: an excitatory pathway ending in inhibition;
- V0d: direct inhibition.

Both act between the two RG-F centres. In the NEST implementation, these
classes are **lumped** into direct commissural inhibition: strong RG-F → RG-F
and weak RG-E → RG-E (`P_COMM_*`, `W_COMM_*`). The figure is the target
architecture; the code is its reduced form.

The same circuit represents both conditions:

- **Healthy:** full descending drive and full loading.
- **Injured:**
  - reduced or frozen descending drive (`--freeze-bs-rg`, lower BS rate);
  - reduced loading and afferent input (`--ia-feedback-gain`,
    `--cut-feedback-gain`);
  - later, epidural stimulation (Phase 7).

### 1.2 Neuron parameters

All spinal neurons use NEST's `izhikevich` model with canonical parameter
sets:

| Population | Izhikevich type | a, b, c, d |
|---|---|---|
| RG-E, M-E, M-F | regular spiking | 0.02, 0.2, −65, 8 |
| RG-F | bursting/chattering-like (intrinsic burster standing in for INaP) | 0.02, 0.2, −55, 4 |
| InE, InF, Ia-E, Ia-F interneurons | fast spiking | 0.1, 0.2, −65, 2 |

- **Inputs:** afferents (CUT, Ia) and brainstem drive are Poisson or regular
  spike generators, relayed through `parrot_neuron`s.
- **Muscles:** parrot relays that feed a rate-based activation → force →
  length model. That model is computed in Python every `--rate-update-ms`.
- **Population sizes:** 100 per RG half-centre, motor pool and afferent
  group; 50 per interneuron group. `--debug-small` is smaller.

**Note on species.** These parameters are **abstract**, not fitted to rat or
human data, and they are identical for both species today. Per decision D6:

- the **local/debug** human configuration keeps them abstract;
- the **MN5 production** configuration will be **fully species-fitted to
  adult humans** (neuron parameters, population sizes, muscle model). See
  Phase 9.

### 1.3 Delays — goal: human conduction delays

**Goal:** every delay in the human model is a human conduction delay. Each
one is computed as `syn_delay + path_length / conduction_velocity + jitter`
for a reference adult of **1.74 m** (D7). The delays are defined in the
species YAML, so a human run cannot use any other delays (D2).

Target delays at 1.74 m. All values are estimates to be calibrated in
Phase 2; path lengths and velocities still need sources:

| Path (model key) | Anatomy | Path length | Target delay | Basis |
|---|---|---|---|---|
| `ia_path` | soleus Ia afferent → L5/S1 | ~0.8–1.0 m | ~12–16 ms | large myelinated afferent, ~60 m/s |
| `m_to_mus` | L5/S1 motoneuron → soleus / TA | ~0.8–1.0 m | ~13–17 ms | α-motor axon, ~50 m/s |
| `cut_to_rg` | plantar cutaneous afferent → lumbar cord | ~1.0 m | ~15–22 ms | Aβ afferent, ~45–60 m/s |
| `bs_to_rg`, `base_to_rg` | brainstem → lumbar cord (reticulospinal) | ~0.5 m | ~5–10 ms (to verify) | fast descending tract; low priority because BS drive is tonic |
| `rg_rec`, `rg_recip`, `motor_e2f`, `motor_f2e` | intraspinal, within segment | mm–cm | ~1–2 ms | synaptic delay dominates |
| `commissural` | crossing the cord | mm–cm | ~1–3 ms | synaptic delay dominates |

**Closed-loop check:** `ia_path` + central (~1–2 ms) + `m_to_mus` must sum to
the human soleus H-reflex latency of **~30 ms** (Palmieri et al. 2004). This
is measured with the reflex-latency probe in Phase 2. Peripheral path lengths
are stored as fractions of `height_m`, so the whole table rescales with body
size.

**Status: done in Phase 2** (2026-09-25). The human table in
`config/species/human.yaml` gives Ia afferent 13.6 ms, motor axon 15.9 ms,
cutaneous 23.6 ms and reticulospinal 8.3 ms at 1.74 m. The reflex-latency
probe measures **30.2 ms**. See the Phase 2 status for details.

### 1.4 Bio-plausible spinal plasticity

The plasticity is taken as-is from tinyCPG
[`feature/spinal-tag-capture-consolidation`](https://github.com/max-talanov/tinyCPG/tree/feature/spinal-tag-capture-consolidation).
That branch is merged into this repo's `main`. Its literature specification,
[`spinal_plasticity_as_learning_spec.md`](spinal_plasticity_as_learning_spec.md),
is on `main` unchanged from the branch.

**Three plastic pathways**, each a NEST `stdp_synapse` (multiplicative STDP,
λ = 1e-3, τ₊ = 20 ms):

| Pathway | Wmax | Role |
|---|---|---|
| BS → RG-E/F | 30 | descending drive; frozen in the sensory-learning / SCI arm |
| CUT → RG-E | 120 | foot-contact drive for stance |
| Ia → RG-E / Ia → RG-F | 10; raised when unloaded | proprioceptive, in-phase |

**Tag-and-capture consolidation (`--consolidate`).** Vanilla STDP keeps every
potentiation forever. Spinal plasticity instead has a fast, decaying change
that becomes permanent only if a slower gating signal arrives in time. In the
model:

- The STDP weight is the fast **tag**.
- A per-connection **baseline** holds the captured, stable component.
- The tag decays toward the baseline with time constant τ_tag unless a
  per-leg, PRP-pool-like accumulator crosses a threshold. When it does, the
  current weight is captured as the new baseline.
- Stance bouts that end on a genuine force threshold push the accumulator
  up. Bouts forced by the failsafe timer push it down.

**Literature grounding** (spec §2 and §4):

- **Ia→RG ↔ Wolpaw's operant H-reflex conditioning.** This has a two-phase
  (fast/slow) time course and has been shown to restore locomotor symmetry
  (Wolpaw 2010; Chen et al. 2006).
- **CUT→RG-E ↔ Grau's contingency-gated spinal learning.** Non-contingent
  outcomes actively suppress learning. The model's "genuine vs.
  failsafe-forced" bout signal plays that role.
- **BS→RG** is the weakest fit (by analogy to corticospinal LTP).
- **Serotonergic gating** (5-HT2/5-HT7) is the best-documented supply side of
  consolidation and the most directly therapeutic (spec §2.1).

**Two model failure modes match maladaptive spinal plasticity** (spec §2.4
and §4):

- **Cap-domination** (`frac_at_cap` → 1): a positive-feedback loop that never
  releases.
- **L/R synchronisation**: over-consolidation.

**Caveats for the human model:**

- The spec's evidence is mostly rat, with some cat and mouse. Directly human
  evidence in the spec is limited to intermittent-hypoxia walking trials
  (Hayes et al. 2014; Tan et al. 2020). Human operant H-reflex conditioning
  after incomplete SCI (Thompson et al. 2013, to verify) is the most relevant
  addition to look for. It is the human counterpart of the Ia→RG mapping.
- Since 2026-09-17, consolidation is also written back to `BS→RG` (spec §4,
  updated 2026-09-24; CLAUDE.md, "Tag-and-capture consolidation").
  Descending-arm consolidation results from before that date need
  re-confirmation.

---

## 2. Migration phases

Each phase lists its **goal**, the **changes** it makes, its **acceptance
criteria** and its **risks**. Size is a rough relative effort: S, M or L.
Blocker IDs (B1–B10) are listed in §7.

**Plasticity reference.** All plasticity and consolidation logic comes from
tinyCPG
[`feature/spinal-tag-capture-consolidation`](https://github.com/max-talanov/tinyCPG/tree/feature/spinal-tag-capture-consolidation),
with its literature spec
[`spinal_plasticity_as_learning_spec.md`](spinal_plasticity_as_learning_spec.md).
None of the phases below changes the learning rules. Phases 5–7 only rescale
their **time constants** (τ_tag, gate cadence) to human bout durations and
session protocols. Any change to the rules themselves must be flagged and
checked against the spec. New upstream work on that branch can be merged with
`git fetch tinycpg feature/spinal-tag-capture-consolidation` followed by a
merge (see README).

### Phase 0 — Safety net (S)

**Goal:** make rat regressions detectable before touching the model.

**Changes**
- Record rat "golden" outputs from `rat-sh/debug.sh` and `rat-sh/debug_force.sh`, with fixed
  seed and fixed `--threads`, under `results/golden/rat/`. They stay local
  because `*.h5` is git-ignored. A checksum manifest is committed.
- Add `scripts/regression_compare.py`. It compares two HDF5 files array by
  array (rates, force, activation, `cut_on`, weights) and exits non-zero on any
  difference, or on a difference above a tolerance if one is given.
- Add `regress.sh`, which re-runs both debug configs and compares them against
  the golden files.

**Acceptance:** two consecutive runs of `regress.sh` on the untouched code
give identical output.

**Risk:** NEST results depend on the thread count, so the golden files must
record `--threads`.

**Status: done (2026-09-24, local, 4 threads).**

- P0 found two reproducibility bugs in the rat model, B11 and B12 (§7). Both
  are fixed, with your approval, because a regression baseline is meaningless
  without them.
- The fixes change rat output once. The new output is statistically
  equivalent: same connection statistics, with seeds now actually honoured.
- The golden run was recorded after the fixes. Its digests are in
  `results/golden/rat/MANIFEST.txt` (NEST 3.9.0, Darwin arm64, `threads=4`).
- Verified:
  - two consecutive `./regress.sh` checks pass at 4 threads, and at 1 thread;
  - a `--consolidate` run repeats exactly at 4 threads;
  - `--seed 12345` and `--seed 22222` now give different NEST-drawn initial
    weights and dynamics;
  - a negative control catches a change of 0.01 in one weight (`W_RG_REC_E`)
    on both configs;
  - sorting costs about 2 s once, at network build, at production size
    (123k static synapses).
- New issue, not fixed: B13, consolidation acts only on a subset of synapses
  at production scale (§7). It needs your decision.

### Phase 1 — Species configuration in YAML (M)

**Goal:** one place for all species-dependent values, **with delays tied to
the species**. No behaviour change yet. Implements D1, D2 and D7.

**Changes**
- Add YAML configuration files. PyYAML becomes a dependency: add it to
  `requirements.txt` and check that it exists in the MN5 NEST environment.

  ```
  config/
    species/
      rat.yaml            # species: rat; constants; cli_defaults;
                          #   delays: {model, jitter_ms, paths}   <- in the same file
      human.yaml          # species: human; body: {height_m: 1.74}; profile: abstract;
                          #   delays: peripheral paths from body height (Phase 2)
      human_adult.yaml    # extends: human.yaml; profile: adult  (Phase 9, MN5)
    modes/
      rat.yaml            # (optional) rat per-mode timing, mirrors the rat scripts
      human.yaml          # slow / comfortable / fast / BWS timing (Phase 5)
    plasticity.yaml       # species-agnostic STDP + consolidation defaults
  ```

- **Every species file contains its own `delays:` section** (model,
  jitter_ms, per-path table). The loader refuses a species file without one,
  and refuses a `delays:` that is a link to another file. Per D2, there is no
  way to run a species without its delays, or with another species' delays.
  (Revised 2026-09-25: P1 first shipped delays as separate
  `config/delays/*.yaml` files referenced from the species file. That allowed
  a species to point at the wrong species' delays, so they were merged in.)
- `--species rat|human|human_adult` loads `config/species/<name>.yaml`.
  `--species-config <path>` loads a custom file. The old `--delay-model` flag
  is **deprecated**: it is accepted only if it matches the species'
  `delays: model`, and fails otherwise.
- All existing rat scripts already pass `--delay-model length_velocity`, so
  they keep working without edits. The legacy `fixed` model is not reachable
  through any species file. It could be kept as an explicit
  `species/rat_fixed.yaml` (`delays: {model: fixed}`) if you ever need it.
- `rat.yaml` holds exactly today's constants and today's rat
  `DELAY_PRESETS`.
- `human.yaml` holds `body.height_m: 1.74` (D7). Peripheral path lengths are
  computed as `fraction × height_m`, using segment-length ratios
  (Winter 2009, to verify), so a different height is a one-line change.
- Resolution order: YAML defaults → mode file → CLI flags. The fully resolved
  configuration, including the delay table and height, is written to the
  HDF5 attributes and dumped next to each output as `<out>.config.yaml`.
- Fix the `--stance-fraction` help text so it states one meaning (B2). The
  meaning itself is settled in Phase 3.

**Acceptance**
- `regress.sh` passes: rat is byte-identical when loaded from YAML.
- A `--species human` run records its resolved configuration.
- A species file without `delays:` fails to load.

**Status: done (2026-09-24, local).**

- `config/species/{rat,human}.yaml`, each with its own `delays:` section, and
  `species_config.py` (loader; `python3 species_config.py --check` validates
  all configs).
- The model reads constants, CLI defaults and delays from the species YAML.
  `DELAY_PRESETS` and `FLEXOR_BS_GAIN_BY_SPECIES` are gone from the code.
- The paced-gait muscle τ literals (40/40/80/80) became named constants
  (`PACED_TAU_*`), so they are configurable too.
- Every output records the resolved config: `config_*` HDF5 attributes and a
  `<out>.config.yaml` sidecar. `scripts/regression_compare.py` skips
  `config_*` attributes as provenance.
- Verified:
  - `./regress.sh` passes, so rat is byte-identical;
  - a human run records `species=human`, `height_m=1.74`, the human delay
    table and a sidecar;
  - the loader refuses:
    - a species file without a `delays:` section, or with `delays:` pointing
      at another file;
    - duplicate keys anywhere in a species file (plain YAML would silently
      keep the last one);
    - a contradicting `--delay-model`;
    - an unknown constant, an unknown CLI default and an unknown species;
  - negative controls: an unmodified copy of `rat.yaml` reproduces the golden
    run exactly, and changing one value (`IA_K_FORCE`,
    `PACED_TAU_FORCE_RISE_MS`, CLI default `ia_feedback_gain`) changes the
    output.
- B2 fixed: `--stance-fraction` help now states the real meaning (fraction of
  the full stride). Values above 0.5 are refused under `--paced-gait` until
  Phase 3.

Departures from the design above, each deferred to where it is first needed:

- **Delay values:** `human.yaml` delays were moved unchanged (absolute lengths,
  still rat-like). Deriving peripheral lengths from `body.height_m` is Phase 2.
- **Muscle τ:** still shared by extensor and flexor. The E/F split lands in
  Phase 4, where soleus and TA values first differ; a split with equal values
  would only add code.
- **`modes/` and `plasticity.yaml`:** not created yet. Human mode timing is
  Phase 5. Plasticity defaults are species-agnostic and stay in code for now.
- **`human_adult.yaml`:** the loader already supports `extends:`, but the file
  itself is Phase 9.

### Phase 2 — Human conduction delays (M)

**Goal:** reach the human delay targets in §1.3, with the H-reflex loop at
~30 ms (fixes B3).

**Changes**
- In the `delays:` section of `config/species/human.yaml`, split the paths into **peripheral**
  (`ia_path`, `cut_to_rg`, `m_to_mus`) and **intraspinal** (`rg_rec`,
  `rg_recip`, `motor_*`, `commissural`, which stay at about 1–2 ms).
- Peripheral path lengths come from the reference adult (1.74 m; soleus ↔
  L5/S1 about 0.8–1.0 m each way). Tune conduction velocities within human
  ranges so the loop latency hits its target. Do not trust any single
  velocity figure. Illustration: 0.9 m afferent at ~60 m/s (~15 ms), plus
  ~1–2 ms central, plus 0.9 m efferent at ~50 m/s (~18 ms), gives ~34 ms.
- Reticulospinal `bs_to_rg` (~0.5 m) is low priority, because BS drive is
  tonic and its delay hardly affects the rhythm.
- Add a **reflex-latency probe**, `scripts/probe_reflex_latency.py` or a
  `--probe-reflex` flag. With plasticity off, it sends one synchronous volley
  into Ia-E and measures the latency to the first `mus-E` response. This is
  the model analogue of the H-reflex.
- Document how the Python sensory loop adds to the latency. Ia and CUT rates
  are recomputed only every `--rate-update-ms` (20 ms by default). Consider
  10 ms for human runs and check the effect on speed.

**Acceptance**
- Probe latency is 28–35 ms at 1.74 m (target ~30 ms; Palmieri et al. 2004).
  It scales with `height_m`.
- `--dump-connectivity` shows the new delay arrays.
- The rat regression passes.

**Risk:** a larger NEST `max_delay` slightly changes how NEST communicates
between threads and MPI ranks, which could affect run time. Measure it.

**Status: done (2026-09-25, local).**

- Human delay table: peripheral paths as fractions of body height via a new
  `length_frac_height` field. At 1.74 m:
  - Ia afferent 13.6 ms;
  - motor axon 15.9 ms;
  - cutaneous 23.6 ms;
  - reticulospinal 8.3 ms.

  Intraspinal paths stay ~1–2 ms. All anatomical fractions and velocities
  are estimates to verify (§5).
- New delay key `ia_int_to_m`: the intraspinal Ia-interneuron → antagonist
  motoneuron hop used to share `ia_path`, and would otherwise have inherited
  the ~13 ms afferent delay.
  - Rat gives it the identical value, and the model then reuses `ia_path`'s
    NEST Parameter object.
  - This matters because two separate, identical random-delay Parameters
    draw differently in NEST (verified), which would have changed rat output.
- Reflex-latency probe (`--probe-reflex-at-ms`,
  `scripts/probe_reflex_latency.py`).
  - The model has no monosynaptic Ia → motoneuron connection, so the probe
    measures the shortest causal Ia → muscle latency.
  - Method: identical control and volley runs; the first diverging spike
    gives the latency. It uses 10 volleys across one stride.
- **Result (rat-sh/debug.sh configuration):** human mus-E **30.2 ms** (median
  30.9 ms; RG-E 13.4 ms, M-E 14.8 ms), inside the 28–35 ms target. Rat:
  5.0 ms.
- `./regress.sh` passes (rat byte-identical).
- Run time is unchanged by the longer delays: the five-mode runs take the
  same wall time for rat and human.
- The Python sensory update tick (`--rate-update-ms`: 50 ms in `rat-sh/debug.sh`,
  100 ms in the paper's mode scripts) is still coarser than the reflex loop.
  It sets how fast *rate-coded* feedback responds. Revisit it in Phase 4/5.
- **Five-mode check** (`run_modes_local.sh`: the paper's sensory-learning
  model, debug-small, 120 s, λ = 1e-4). Figures:
  `plots/modes/{rat,human}_modes_stages.png`.
  - **Rat:** counter-phase sharpens with learning in every loaded mode. r(E,F)
    left leg, beginning → end:
    - slow −0.87 → −0.98;
    - medium −0.82 → −0.96;
    - fast −0.79 → −0.91;
    - toe −0.75 → −0.92 (the extensor recovers as CUT→RG-E reaches ~21 pA).
  - **Human delays with rat stride timing:** slow and medium peak mid-run
    (−0.99, −0.95) and then degrade (end −0.92 and −0.71). Fast degrades
    throughout (−0.74 → −0.40).
    - Mechanism: CUT→RG-E over-potentiates (medium 69, fast 75 pA vs ~60 in
      rat), and the extensor no longer relaxes between strides.
    - Likely cause: the ~24 ms cutaneous and ~30 ms reflex delays shift STDP
      timing inside a 350–520 ms rat stride.
    - Check again in Phases 3/5 with human strides (≥ 900 ms). If it
      persists, it is a plasticity-timing issue to raise before Phase 6.
  - **Air stepping (both species):** the extensor stays silent and CUT does
    not learn (~4.7 pA). The r(E,F) ≈ −0.7 there reflects flexor oscillation
    against a flat extensor, not real alternation.

### Phase 3 — Human gait scheduler with double support (L)

**Goal:** allow human stance ≈ 60% with ~10% double support at each
transition (fixes B1).

**Changes**
- Replace the sequential half-cycle schedule with a **per-leg phase
  schedule**. Each leg has its own stance window `[φ_leg, φ_leg + f_st·T)` and
  R is offset from L by `T/2`. With `f_st > 0.5`, the windows overlap and
  double support emerges. With `f_st = 0.5`, the rat schedule is reproduced
  exactly, which is the regression requirement.
- Settle what `--stance-fraction` means: fraction of the **full stride** that
  each leg spends in stance.
- Update the heel→mid→toe Ia-E sub-groups (`SUB_STANCE_MS`) and the flexor
  swing afferent (`--ia-ext-f-hz`) to follow the new per-leg windows.
- Force-trigger mode (`--cut-trigger force`) already uses independent per-leg
  Schmitt triggers, so overlap is allowed in principle. However, the lead
  offset, priming window and commissural inhibition were all tuned for strict
  alternation. Re-check them.

**Acceptance**
- Timer mode at `--species human`, comfortable speed: measured stance
  fraction (from `cut_on`) is 0.60 ± 0.03, double support is 8–12% per
  transition, and L/R anti-phase holds.
- Rat regression passes with `f_st = 0.5`.

**Risk:** the highest-risk phase. Commissural inhibition on RG-E may fight
double support. **Per D4 (agreed):** if needed, weaken `W_COMM_E_INH` in the
human configuration only. The change is flagged in the commit and in
CLAUDE.md; the rat value is untouched.

**Status: done (2026-09-25, local).**

- **Implementation:** an opt-in scheduler instead of a rewrite. New flag
  `--gait-scheduler {halfcycle, phase}`, selected by the species config:
  - rat keeps `halfcycle`, the old code path, so rat stays byte-identical by
    construction;
  - human uses `phase` with stance 0.60.
- **The `phase` scheduler (`MOD_PHASE_GAIT`):**
  - each leg is in stance for `stance_fraction × stride`, the right leg offset
    by half a stride;
  - the heel→mid→toe Ia-E groups step through each leg's own stance;
  - the flexor swing afferent is on in that leg's swing only;
  - the CUT stretch term is applied per leg;
  - per-leg `cut_on` is logged.
- **Legacy quirk left untouched in the rat path:** `halfcycle` passes one CUT
  fraction to both legs, so the swing leg's extensor also gets the
  stance-leg stretch term.
- **`--stance-fraction`:** means the fraction of the full stride. Values above
  0.5 are refused only under `halfcycle`.
- **Results** (`scripts/cpg_gait_phase_metrics.py`; `rat-sh/debug.sh`
  configuration, 1000 ms stride, 30 s, from 5 s; figure
  `plots/p3/human_gait_phase.png`):

  | run | stance L/R | double support | r(E,F) L/R | r(E_L,E_R) | ext. active in stance |
  |---|---|---|---|---|---|
  | human halfcycle 0.50 | — | — | −0.90/−0.90 | −0.94 | — |
  | human phase 0.50 | 0.500 | 0 | −0.90/−0.89 | −0.94 | 0.90 |
  | **human phase 0.60** | **0.600** | **0.20 (10% per transition)** | −0.88/−0.86 | −0.74 | 0.92 |
  | human phase 0.65 | 0.650 | 0.30 | −0.88/−0.86 | −0.62 | 0.92 |
  | human phase 0.40 | 0.400 | 0 (flight 0.20) | −0.87/−0.88 | −0.97 | — |
  | rat halfcycle 0.50 | — | — | −0.95/−0.91 | −0.99 | — |
  | rat phase 0.50 | 0.500 | 0 | −0.93/−0.91 | −0.99 | 0.90 |

- **Acceptance met:**
  - stance 0.600 and double support 10% per transition;
  - L/R anti-phase holds. With 60% stance the ideal square-wave limit is
    r ≈ −0.67, and the model gives −0.74.
  - `phase` at 0.50 reproduces `halfcycle` statistically.
  - Rat regression passes.
- **D4 not needed:** both extensors are co-active in 30% of the stride and
  each extensor is active through ~92% of its stance, so commissural
  inhibition does not block double support.
- `run_modes_local.sh` no longer forces `--stance-fraction 0.5`: rat gets 0.5
  and human 0.60 from the species config.
- **Not in scope:** force-trigger mode (`--cut-trigger force`) already has
  per-leg triggers and ignores `--gait-scheduler`. Its lead offset and caps
  are re-tuned for human timing in Phase 5.
- **Five-mode rerun, human** (`run_modes_local.sh human 120000 1e-4`, now
  stance 0.60 with double support; still rat stride periods). Figure:
  `plots/modes/p3/human_modes_stages.png`. Left-leg r(E,F), beginning / middle
  / end, P2 (halfcycle 0.50) → P3 (phase 0.60):

  | mode | P2 | P3 | CUT→RG-E at end, P2 → P3 |
  |---|---|---|---|
  | slow | −0.89 / −0.99 / −0.92 | −0.89 / −0.98 / −0.93 | 63 → 65 pA |
  | medium | −0.78 / −0.95 / −0.71 | −0.68 / −0.84 / −0.70 | 69 → 69 pA |
  | fast | −0.74 / −0.67 / −0.40 | −0.58 / −0.79 / **−0.78** | 75 → 75 pA |
  | toe | −0.79 / −0.78 / −0.93 | −0.50 / −0.56 / −0.88 | 21 → 24 pA |
  | air | −0.70 / −0.71 / −0.76 | −0.50 / −0.48 / −0.51 | 5 → 5 pA |

  - **Fast mode no longer collapses late** (end −0.40 → −0.78).
  - Medium ends the same. Toe and air start weaker, although toe recovers by
    the end.
  - **CUT→RG-E over-potentiation is unchanged** (69–75 pA vs ~60 in rat).
    The double-support schedule does not address it, so it stays open for
    Phase 5 (human strides) and, if it persists, Phase 6.

### MN5 check A (after Phase 3) — human five modes at production N (S)

**Goal:** check whether the local `--debug-small` findings hold at the model's
real size. Debug-small uses ~30 neurons per population and BS at 20 Hz;
production uses N = 100 and BS at 60 Hz.

**Changes**
- `run_modes_mn5.sh`: one SLURM array for both species, 10 tasks. Tasks 0–4
  are the human five modes, tasks 5–9 the rat reference.
  - 1 node, 1 task, 64 threads, CPU partition `gp_bsccs`, 1 h limit.
  - 120 s, λ = 1e-4, sensory-learning model.
  - Stance fraction and scheduler come from the species config: human 0.60
    with double support, rat 0.5 halfcycle.
  - A preflight check (NEST, PyYAML, species configs) fails the task in
    seconds instead of after queueing.
  - Output: `results/modes_mn5/<species>/`. Figures come from
    `scripts/cpg_modes_stages.py --indir results/modes_mn5/<species>`.

**Acceptance:** the runs complete. Compare against the local five-mode
results in the Phase 2 status. In particular, does fast/medium degradation
through CUT→RG-E over-potentiation persist at N = 100?

**Cost:** 10 tasks, each a few minutes of NEST time.

**Status: done 2026-09-25** (MN5 job, results in `results/2026-09-25/{human,rat}/`;
figures `plots/modes/mn5/{human,rat}_modes_stages.png`).

- All 10 tasks completed: production size (~5,000 CUT→RG-E synapses per leg,
  ~173k synapses), 120 s, λ = 1e-4, 64 threads, NEST 3.9.0.
- Human used the phase scheduler with stance 0.60 (measured stance 0.600,
  double support 0.200). Rat used halfcycle 0.50.
- Before the run, two fixes were made: B14 (recorder bookkeeping was
  quadratic) and B15 (the jobs requested the GPU partition).

Left-leg r(E,F), beginning / middle / end (4–9 s, 40–45 s, 115–120 s), and
CUT→RG-E at the end:

| mode | human MN5 (N=100) | human local debug-small | rat MN5 (N=100) | CUT→RG-E end: human / rat |
|---|---|---|---|---|
| slow | −0.68 / −0.79 / −0.84 | −0.89 / −0.98 / −0.93 | −0.78 / −1.00 / −0.99 | 68 / 65 pA |
| medium | −0.45 / −0.92 / **−0.91** | −0.68 / −0.84 / −0.70 | −0.76 / −0.98 / −0.97 | 72 / 65 pA |
| fast | −0.65 / −0.95 / **−0.96** | −0.58 / −0.79 / −0.78 | −0.49 / −0.87 / −0.96 | 77 / 65 pA |
| toe | −0.23 / −0.33 / −0.34 | −0.50 / −0.56 / −0.88 | −0.31 / −0.26 / −0.31 | 62 / 50 pA |
| air | −0.19 / −0.41 / −0.31 | −0.50 / −0.48 / −0.51 | −0.52 / −0.49 / −0.34 | 10 / 9 pA |

Findings:

1. **The late degradation of human medium/fast was a debug-small artifact.**
   - At N = 100, human medium and fast end at −0.91 and −0.96, like rat
     (−0.97, −0.96).
   - CUT→RG-E still settles higher in human (72–77 vs ~65 pA in rat), but it
     no longer destroys alternation.
   - That narrows the open "over-potentiation" item from P2/P3 to a
     set-point difference to keep watching, not a failure.
2. **Human slow is the weakest loaded mode** (end −0.84 vs rat −0.99).
   - The right leg settles late (beginning r = −0.31).
   - With 60% stance and 80 ms force time constants, some E/F overlap is
     expected, so part of this may be the stance fraction rather than a
     defect. Recheck with human strides in P5.
3. **Both unloaded modes collapse in both species at production N:** the
   flexor stays tonically near its ceiling (5th-percentile F-force ~11–13 of
   ~17) while the extensor oscillates underneath, i.e. E/F co-contraction.
   - Under unloading, the Ia→RG cap is relaxed toward `WMAX_IA_UNLOADED`: the
     effective cap is 10 loaded, 35 toe and 55 air (MOD_IA_RG_LOADING_GAIN).
     Ia→RG-F then potentiates to 13–19 pA (vs ~4 when loaded).
   - This is inherited rat-model behaviour (rat collapses the same way),
     consistent with the paper's "unloading collapses the sensory arm".
   - It matters directly for P7, where body-weight support and SCI are
     unloading conditions.
   - Flag for P5/P7: look at the unloaded Ia→RG-F cap and the flexor
     intrinsic drive before building SCI conditions on toe/air.
4. **Human fast mode:** the extensor is active through only ~67% of its
   210 ms stance (vs 96–100% in medium and slow). The 80 ms force time
   constants cannot fill a rat-length stance. Expected to resolve with human
   strides (P5).
5. **Early learning is slower at N = 100 than at debug-small in both species**
   (lower r at 4–9 s; CUT→RG-E reaches ~60 pA by 40 s).

### Phase 3b — Size-invariant connectivity (M) — moved forward 2026-09-26

**Goal:** the network behaves the same at any population size N. Then the
operating points tuned at N = 100 in P4–P7 carry over to the adult-size model
in P9 by construction, instead of having to be re-found there. This is the
earliest point where it can be done: it changes the wiring that every later
phase tunes against.

**Why now.** All 39 projections use `pairwise_bernoulli` with a fixed
probability p, tuned for N = 30–100 (B16). The mean in-degree is p × N_source,
so it grows with N at unchanged weights:
- 10× the neurons means 10× the synaptic input per neuron, and the network
  saturates;
- `--debug-small` needs a hand-tuned BS drive (20 Hz instead of 60 Hz) to
  compensate for its smaller in-degree. This is the same problem in the other
  direction.

Muscle and afferent read-outs are already normalised per neuron
(`sp / N_MUS` and fan-in in the muscle loop), so only the connectivity is
size dependent.

**Changes**
- New flag `--conn-rule {bernoulli, indegree}`, with the default set in the
  species YAML (`cli_defaults`):
  - human: `indegree`;
  - rat: `bernoulli`, so the rat golden files stay byte-identical.
- Under `indegree`, each projection uses NEST `fixed_indegree` with a target
  in-degree K* = p × N_ref, where N_ref is the production source size today
  (100 for most populations). At N = 100 the mean input is therefore the same
  as now, and MN5 check A stays a valid reference.
- If a source population is smaller than K* (debug-small), use
  K = min(K*, N_source) and scale the weight, and for plastic synapses Wmax,
  by K*/K. That keeps the total input w × K constant. The debug-small BS
  compensation can then be dropped under `indegree`.
- The K* values go into the species YAML (`connectivity:`), not code
  constants. Each is stored as an in-degree, not a probability, so P9 can
  replace it with sourced values.
- **Fix B13 in the same phase:** consolidation baselines and write-back use
  the full synapse collection of each plastic pathway, and only the weight
  statistics use the `--max-weight-conns` subset. Log the consolidated
  fraction (it must be 1.0). This touches the same connection bookkeeping and
  also has to be size-invariant: at adult size, a 2,000-synapse subset would
  be a few percent of the pathway.
- Record `conn_rule` and the K* table in the HDF5 attributes and the
  `.config.yaml` sidecar.

**Acceptance**
- `./regress.sh` passes (rat unchanged).
- **Switch check.** Human medium at N = 100, 3 seeds, `indegree` vs
  `bernoulli`: gait metrics agree within the seed-to-seed spread. The metrics
  are r(E,F), r(E_L,E_R), stance fraction, cycle period and end CUT→RG-E
  weight. If they don't agree, document the shift and re-run MN5 check A under
  `indegree`.
- **Size sweep.** Human medium, 120 s, N scale × {0.3, 1, 3}: the same metrics
  within the seed spread of N = 100. N × 0.3 and × 1 run locally; × 3 runs on
  MN5 (it can share the MN5 check B job).
- B13: consolidated fraction 1.0 at production N. Re-run the consolidate
  operating point once to measure the behavioural change.

**Risks**
- Fixed in-degree removes the binomial spread of in-degrees, so neurons are a
  little more homogeneous. The existing `--static-weight-cv` heterogeneity
  can compensate if alternation turns out to depend on it.
- Full-collection consolidation costs Python time per gate event. It is cheap
  at N = 100 (~5,000 synapses per pathway and leg), but it must be measured
  in MN5 check B before adult size.

### Phase 4 — Muscle and afferent model (M)

**Goal:** human contraction dynamics and afferent rates (B5, B6).

**Changes**
- Split force and activation τ by pool. **Per D3 (agreed):** the extensor
  pool is modelled as **soleus** (slow-twitch dominant) and the flexor pool
  as **tibialis anterior**. Take twitch time-to-peak values from the
  literature. The source still has to be verified; the soleus target is on
  the order of 100 ms. Note that the current paced-gait override (80/80 ms)
  is already close to the soleus scale, so the change may be small for E.
- Rescale `TAU_LENGTH_MS`, `SHORTEN_GAIN` and `STRETCH_GAIN` to the longer
  human stance.
- First **measure** the Ia and CUT rate distributions the model actually
  produces. Then set `IA_RATE_MAX_HZ`, `IA_K_FORCE`, `IA_K_STRETCH` and
  `CUT_RATE_ON_HZ` against human microneurography, which is still to be
  sourced. Plantar cutaneous afferents: Kennedy & Inglis 2002.
- All values go into `config/species/human.yaml`, not into code constants.

**Acceptance**
- Force-E rises through stance and reaches the CUT-OFF threshold within the
  human stance window. Force-trigger mode needs this; see the rat "Muscle
  fatigue" notes.
- Ia and CUT rates stay within the sourced human ranges.

### Phase 5 — Human locomotion modes and force-trigger operating point (L)

**Goal:** stable, genuinely closed-loop human gait across speeds and loading
conditions.

**Changes**
- Define the human modes in `config/modes/human.yaml` and in new scripts,
  `debug_human.sh`, `debug_force_human.sh` and `run_*_human.sh`. Rat scripts
  stay untouched.

  | Mode | Stride (ms) | Stance fraction | Stands in for |
  |---|---|---|---|
  | slow | ~1300–1500 | ~0.62–0.65 | slow walking |
  | comfortable | ~1000–1200 | ~0.60 | self-selected speed, ~1.2–1.4 m/s |
  | fast | ~900 | ~0.57 | fast walking |
  | BWS-x% | as comfortable | as comfortable | body-weight-supported treadmill stepping; replaces rat toe and air stepping via `--ia-feedback-gain` / `--cut-feedback-gain` |

- Rescale per mode, together: `--cut-max-stance-ms`, `--cut-max-swing-ms`,
  fatigue onset and recovery τ, `--cut-force-off-frac`, `--lead-offset-ms`
  and `--consolidate-tau-tag-ms`. The first guess for each is the rat value
  × (human bout ÷ rat bout). After that, run a small local sweep like rat
  rounds 3–5, at `--debug-small`.
- The consolidation mechanism is unchanged from the tinyCPG plasticity
  branch. Only τ_tag is re-confirmed per human mode, following the rat rule
  that τ_tag scales with bout length and loading.
- Check **tick alignment**: stride and stance durations must not be exact
  multiples of the gate tick. See "Medium's tick-alignment fragility" in the
  rat history.

**Acceptance, per mode, force-trigger, debug-small then production:**
- `frac_at_cap` ≈ 0 on both legs, confirmed with `cut_on` ground truth.
- corr(Force-E, Force-F) and corr(Force-E_L, Force-E_R) in the rat-recalibrated
  target band (−0.6 to −0.8), with no L/R synchronisation.
- Measured stride period and stance fraction within ±5% of the mode target.

### Phase 6 — Plasticity time course and multi-session rehabilitation (M)

**Goal:** make "gradual rehabilitation" a protocol, not a single run (B8).

**Changes**
- Add `--init-weights-from <h5>`. It restores plastic weights, and
  `baseline`/`prp_pool` when `--consolidate` is on, from a previous run's
  final snapshot. This allows **session → rest → session** chains.
- Define the protocol: N simulated training sessions of M minutes each, with
  weights carried between sessions. Consolidation handles offline retention.
  Real weeks cannot be simulated, so compare the **shape** of the recovery
  curve (sessions to criterion, retention between sessions) with human
  training studies, not absolute days.
- Keep STDP λ in 5e-4 to 5e-3, which is species-agnostic. Re-confirm
  `tau_tag_ms` per human mode (Phase 5).
- Map the protocol onto the spec's gating signals. For example, a
  serotonergic-gating "supply" parameter per session (spec §2.1) is the model
  counterpart of adjuvants such as intermittent hypoxia (Hayes et al. 2014).
  This is optional and must be flagged before it is implemented.

**Acceptance:** a 5-session chain on the incomplete-SCI configuration
(Phase 7b) improves gait metrics gradually and monotonically, not in one
jump, and keeps them across the session boundaries.

### Phase 7 — Healthy → incomplete SCI → complete SCI, with epidural stimulation (L)

**Goal:** the three conditions on the same circuit, in the agreed order (D5),
plus epidural electrical stimulation (EES) (B7).

**Shared change:** add EES as a tonic afferent input. EES mainly recruits large
proprioceptive afferents in the dorsal roots (Capogrosso et al. 2013), so model
it as a pulse train at `--ees-hz` and `--ees-amp` onto the Ia-E and Ia-F
populations, not phase-gated. A later option is spatiotemporal (phase-gated)
EES (Wagner et al. 2018). The existing external Ia-E heel→toe ramp, described
in the code as epidural-stim pacing, must be clearly separated from the new
tonic EES.

- **7a — Healthy.** Full BS drive and full loading, at all Phase 5 modes.
  This is the reference every SCI result is compared against.
  **Acceptance:** Phase 5 criteria, plus EES off leaves the output unchanged.
- **7b — Incomplete SCI.** Reduced BS rate and/or weak frozen BS→RG, combined
  with BWS loading levels. Run with and without EES, and with and without
  multi-session training (Phase 6).
  **Acceptance:** stepping degrades relative to 7a without intervention, and
  recovers gradually with training ± EES. This is the qualitative pattern of
  EES + training in incomplete SCI (Wagner et al. 2018).
- **7c — Complete SCI.** BS off or near zero.
  **Acceptance:** qualitative reproduction of the human EES frequency
  dependence. EES at ~5–15 Hz gives tonic extensor activity; ~25–50 Hz gives
  rhythmic E/F alternation (Minassian et al. 2004).

### Phase 8 — Validation against human data (M, plus data access)

**Goal:** quantitative comparison with human recordings, in the same order:
healthy, then incomplete SCI, then complete SCI.

**Changes**
- Write `validation/human_data_sources.md`, the human counterpart of the rat
  `emg_data_requests.md`. Candidate public healthy-gait datasets, whose
  contents and licences still need checking:
  - Schreiber & Moissenet 2019 (Sci Data): multi-speed gait with EMG;
  - Lencioni et al. 2019 (Sci Data): walking with EMG;
  - Fukuchi et al. 2018 (PeerJ): speed-dependent kinematics and kinetics.

  Human SCI EMG under EES/training is mostly not public, so it will likely
  need data requests.
- Add `scripts/cpg_human_gait_metrics.py`, which computes metrics from model
  HDF5 and dataset files in one format:
  - stride period vs. speed;
  - stance fraction and double support;
  - soleus/TA envelope onset and offset (% gait cycle) vs. model motor-pool
    rate;
  - E/F co-activation index;
  - L/R phase.

**Acceptance:** model metrics within the inter-subject range of the chosen
healthy dataset at each speed. SCI comparisons are qualitative until data is
obtained.

### MN5 check B (after Phase 3b, alongside Phase 4) — scaling benchmark (M)

**Goal:** turn the Phase 9 size estimate into data. This is a benchmark, not
science. An adult lumbar model is plausibly 10⁴–10⁵ neurons and 10⁸–10⁹
synapses; raw NEST compute for that is feasible on a handful of MN5 nodes.
The obstacles are in the model code (found 2026-09-25):

1. **Closed sensory loop is not MPI-safe.**
   - Muscle force and Ia/CUT rates are computed in Python each chunk from
     spike counts, with no MPI reduction; `rank` only gates printing and
     writing.
   - On more than one rank, each rank would compute force from its local
     spikes only, which is silently wrong.
   - Production today is 1 node, 1 task, 64 threads.
2. **Connectivity does not scale.** All 39 projections use
   `pairwise_bernoulli` with fixed p (~0.1–0.5), tuned for N = 30–100.
   - Scaling N multiplies every in-degree at the same weights, which
     saturates the network.
   - **Moved to Phase 3b** (fixed in-degree with normalised weights). Check B
     runs on the Phase 3b model.
3. **Human population data are thin.**
   - Motor pools: order-of-magnitude figures exist (to source).
   - Human CPG interneuron classes (RG, V0/V1/V2a/V3) have never been
     counted, so they would be extrapolated from rodent/cat.

**Changes**
- Benchmark script: build and simulate ~10 s at N × {1, 3, 10, 30} under
  `--conn-rule indegree` (Phase 3b), so dynamics stay comparable while size
  grows. Include full-collection consolidation (B13 fix) in the timing.
- Measure build time, memory, NEST simulate time and Python-loop time per
  chunk. Record them in PLAN.md.
- Prototype the MPI reduction of the per-chunk spike counts. Check that a
  2-rank run reproduces the 1-rank closed-loop behaviour statistically. Runs
  are not bit-identical across rank counts, because each virtual process has
  its own RNG stream.

**Acceptance:** a table of cost vs. N and a named bottleneck (expected: the
per-chunk Python bookkeeping). Also a go/no-go on the Phase 9 adult size
within the MN5 budget.

### Phase 9 — Adult-human production profile (MN5) and paper (L)

**Goal:** per D6, the MN5 production model is **fully species-fitted to adult
humans**. The local/debug model stays abstract.

**Changes**
- Create `config/species/human_adult.yaml` (`extends: human.yaml`). It adds:
  - **neuron parameters:** Izhikevich parameters re-fitted per population to
    human data. Motoneurons fitted to human motor-unit discharge rates and
    recruitment during walking; interneurons to the best available
    human/primate proxies. Sources to be collected;
  - **population sizes:** motor pools and afferent groups scaled toward human
    soleus and TA pool sizes (sources to be collected), within the MN5 compute
    budget;
  - **delays and body size:** the human `delays:` section (inherited from `human.yaml`) at `height_m: 1.74`;
  - **muscles:** the fitted soleus/TA muscle model from Phase 4.
- Re-confirm the Phase 5 operating points under `human_adult`. Fitting can
  move them, just as production N moved the rat operating points relative to
  `--debug-small`.
- Build the MN5 array scripts `run_*_human.sh`, following the `MN5_RUN.md`
  workflow. Seeds and init robustness use the same 10-point (μ, CV) grid as
  the rat paper, so rat and human results are directly comparable.
- Update README, CLAUDE.md and the figure scripts. Figures must label species
  and profile (`human` / `human_adult`) explicitly.

**Prerequisites:** Phase 3b (fixed-in-degree connectivity), MN5 check B
(MPI-safe closed loop, cost table) and sourced human population data.

**Risk:** larger populations raise MN5 cost. Benchmark one production cell
before submitting arrays.

---

## 3. Order and dependencies

```
P0 ─► P1 ─► P2 ─► P3 ─► MN5-A ─► P3b ─┬─► P4 ─► P5 ─► P6 ─► P7a ─► P7b ─► P7c ─┬─► P9
                                      └─► MN5-B (alongside P4) ────────────────┤
                             P8 (data sourcing can start now) ─────────────────┘
```

- P0–P3 and MN5 check A are done (2026-09-25).
- MN5 check A runs right after P3.
- **P3b and MN5 check B were moved forward (2026-09-26)**, from just before P9
  to right after MN5 check A. Tuning P4–P7 on a size-invariant network means
  the adult-size run in P9 needs no re-tuning. P9 itself stays last: it needs
  the settled SCI conditions (P7) and the sourced human population data.
- P5 needs P3 and P4.
- P7 follows the agreed condition order: healthy, then incomplete, then
  complete.
- Data sourcing for P8, and parameter sourcing for P9 (human motor-unit and
  pool data), have the longest lead times and should start immediately.

**Suggested first milestone:** P0 + P1 + P2. The result: a regression-safe,
YAML-configured code base in which `--species human` always means human-scale
reflex latencies at 1.74 m, checked by the probe.

---

## 4. Decisions (agreed 2026-09-24)

| # | Decision | Outcome |
|---|---|---|
| D1 | Where species profiles live | **YAML files** under `config/` (Phase 1) |
| D2 | Species vs. delay model | **The species determines its delays.** Each species YAML contains its own `delays:` section (revised 2026-09-25 from a separate, referenced delay file, which could be mixed up). Running a species without its delays is impossible, and `--delay-model` is deprecated (Phase 1) |
| D3 | Muscle identity of the pools | **Extensor = soleus, flexor = tibialis anterior** (Phase 4) |
| D4 | Human-only commissural change if double support needs it | **Allowed** in the human configuration only, flagged in the commit and in CLAUDE.md (Phase 3) |
| D5 | Condition order | **Healthy → incomplete SCI → complete SCI** (Phases 7a–7c, 8) |
| D6 | Abstract vs. species-fitted | **Local/debug stays abstract; MN5 production is fully species-fitted to adult humans** (`human_adult`, Phase 9) |
| D7 | Body size for path lengths | **From YAML, default `height_m: 1.74`** (Phases 1–2) |

---

## 5. References to verify before citing in the paper

The following are cited in CLAUDE.md and this plan. Before any number reaches
the manuscript, each one should be checked the same way the rat spec was
checked against PubMed:

- Perry & Burnfield 2010
- Bohannon & Andrews 2011
- Palmieri et al. 2004
- Minassian et al. 2004
- Dimitrijevic et al. 1998
- Harkema et al. 2011
- Angeli et al. 2018
- Gill et al. 2018
- Wagner et al. 2018
- Capogrosso et al. 2013
- Kennedy & Inglis 2002
- Winter 2009
- Thompson et al. 2013
- Schreiber & Moissenet 2019
- Lencioni et al. 2019
- Fukuchi et al. 2018

References already verified in
[`spinal_plasticity_as_learning_spec.md`](spinal_plasticity_as_learning_spec.md)
(Wolpaw 2010, Chen et al. 2006, Hayes et al. 2014, Tan et al. 2020, the Grau
series) need no re-check.

Values marked "to verify" in CLAUDE.md (soleus twitch time, human plantar
afferent rates, reticulospinal delay) have no confirmed source yet. The same
applies to the human motor-unit and pool-size data needed for Phase 9.

---

## 6. Guiding principles

1. **Rat stays byte-identical.** `--species rat`, the default, must produce
   exactly the same HDF5 output as today for the same seed and thread count.
   Every phase ends with that regression check.
2. **One switch, one configuration.** All species-dependent values, including
   delays, come from the species YAML selected by `--species`. Explicit CLI
   flags still override the YAML, except that delays cannot be detached from
   the species. The resolved values are written to the HDF5 attributes, so
   every output says which parameters it actually used.
3. **Hard targets before tuning.** Each phase has a measurable acceptance
   criterion taken from human physiology, such as reflex latency, stance
   fraction or stride period. A phase is not done because the output "looks
   right".
4. **Circuit and learning rules unchanged unless a phase says otherwise.**
   The ~6:1 asymmetric reciprocal inhibition, tonic BS, the three plastic
   pathways and the tag-and-capture rule stay as they are. The only
   pre-agreed exception is D4. Neuron parameters and population sizes stay
   abstract locally and are species-fitted only in the MN5 `human_adult`
   profile (D6).
5. **The rat lessons still apply.** Check `frac_at_cap` on every force-trigger
   run, watch for L/R synchronisation, and check tick alignment. The rat
   history in CLAUDE.md shows how these failure modes appear. They will
   reappear at human timing.

---

## 7. Current state: what blocks a human run

| # | Blocker | Where | Effect |
|---|---|---|---|
| B1 | **FIXED in P3 (2026-09-25)** by `--gait-scheduler phase` (human default); `halfcycle` kept for rat. Was: The paced-gait scheduler is strictly sequential: one leg's stance, then the other's. `SWING_MS = HALF_MS − STANCE_MS` | `cpg_2legs_fast.py` ~L1111–1113, ~L2366–2410 | Stance can never exceed 50% of the stride, so there is **no double support**. Human stance is ~60%. With `--stance-fraction 0.6`, `SWING_MS` goes negative. |
| B2 | **FIXED in P1 (2026-09-24)**: help text now says "fraction of the full stride"; >0.5 is refused under `--paced-gait` until P3. Was: `--stance-fraction` help text says "fraction of HALF the step period". The code multiplies the full period. | ~L561 vs ~L1112 | The flag's meaning is ambiguous. It must be fixed before human values are set. |
| B3 | **FIXED in P2 (2026-09-25):** human peripheral delays now 13.6–23.6 ms, reflex probe 30.2 ms. Was: the human delay preset gives ~1.7–2.3 ms delays, the same as rat | `DELAY_PRESETS["human"]` ~L185 | The peripheral loop is ~10× too fast. The human soleus H-reflex latency is ~30 ms. |
| B4 | **FIXED in P1 (2026-09-24).** `--species` had no effect under the default `--delay-model fixed` | `make_delay_param` | A run labelled "human" can be pure rat without any warning. Resolved by D2 / Phase 1. |
| B5 | Muscle τ values are rat-tuned and shared between extensor and flexor (`TAU_FORCE_*`, `TAU_ACT_*`, `TAU_LENGTH_MS`). The paced-gait override is 80/80 ms. | ~L326–365, ~L1123–1126 | Human soleus (extensor) and tibialis anterior (flexor) contract at different speeds. |
| B6 | Afferent rate model has `IA_RATE_MAX_HZ = 500` and `IA_K_*` gains | ~L372–375, ~L2035–2045 | The 500 Hz cap is far above plausible human Ia rates. The real rates the model produces have not been measured yet. |
| B7 | No epidural-stimulation (EES) input | — | The key human SCI intervention cannot be modelled. |
| B8 | No weight save → restore between runs (`--save-weights` writes only) | ~L479 | Multi-session rehabilitation protocols are not possible. |
| B9 | No test or regression harness in the repo | — | Nothing checks that rat is unchanged. |
| B11 | **FIXED 2026-09-24.** Not reproducible with >1 NEST thread (found in P0). NEST builds identical connections, but `GetConnections` returns them in a different order each run. The static-weight heterogeneity (`--static-weight-cv`, 0.5 by default) assigned its seeded numpy lognormal factors in that order. The `--max-weight-conns` subset and the consolidation baselines are positional too. | `sorted_connections()`; static heterogeneity, plastic `conns_cache`, `--dump-connectivity` | Before the fix, the same seed gave a differently wired network on every multi-thread run, including on MN5. **Rat results produced before 2026-09-24 cannot be reproduced bit-for-bit.** They remain statistically valid samples. |
| B12 | **FIXED 2026-09-24.** NEST `rng_seed` was never set, so `--seed` only seeded numpy, and numpy was seeded only in sweep mode | kernel setup (`NEST_RNG_SEED`), `np.random.seed` now in every mode | Before the fix, every run used NEST's default seed (143202461). Poisson afferent noise, NEST-drawn weight init and delay jitter were identical across "different seeds". Multi-seed sweeps (for example the 3 seeds in `rat-sh/run_consolidate_all_modes_production.sh`) varied only the numpy-drawn parts. Now `rng_seed` = run seed; recorded as the `nest_rng_seed` attribute. |
| B13 | **Open, scheduled for Phase 3b** (full collection for consolidation, subset for stats only). Consolidation acts only on the `--max-weight-conns` subset. `conns_cache` is cut down to that subset "for weight stats", but the consolidation baselines and write-back use the same cache. | `cpg_2legs_fast.py` `conns_cache` downsampling and `MOD_CONSOLIDATE` | Production scripts pass `--max-weight-conns 2000`, but each plastic pathway has ~5,000 synapses per leg (100 × 100 × p = 0.5). So **only ~40% of synapses are consolidated**; the rest are vanilla STDP. Since B11 it is at least the same 40% every run. Debug-small is unaffected (all pathways are under 1,000 synapses). Possible fix: consolidation always uses the full collection, and only the stats use the subset. This changes production behaviour, and consolidate results at production N would need re-running. |
| B14 | **FIXED 2026-09-25 (MOD_RECORDER_CLEAR).** Python bookkeeping grew with the square of simulated time. The model counted spikes by reading `n_events` from spike recorders that were never cleared. A NEST status read costs O(stored events), about 0.9 ms per million on this machine, and 16 reads happen per chunk. | `new_spikes()` in `cpg_2legs_fast.py` | tinyCPG MN5 Round 6: ~135 s in NEST vs ~17,000 s in bookkeeping per task, which forced 12 h limits. Now the recorder is cleared after each read. Measured locally, 60 s human medium: bookkeeping 17.2 s → 4.6 s, linear (20 s: 1.5 s). Spike counts are unchanged, so outputs are byte-identical (`./regress.sh` passes). |
| B15 | **FIXED 2026-09-25.** Every SLURM script asked for the GPU partition (`--partition=acc`, 64 cores, 10–12 h), although no GPU is used; jobs sat pending. | `rat-sh/*.sh`, `mpi_test.sh` | Now `--partition=gp_bsccs` (the CPU partition, as in tinyHippo). Limits are 2 h (4 h for consolidation) and 10 min for `mpi_test.sh`. |
| B16 | **Open, scheduled for Phase 3b.** Connectivity is not size-invariant: all 39 projections use `pairwise_bernoulli` with a fixed p, so the mean in-degree grows with N at unchanged weights. | `nest.Connect(..., rule pairwise_bernoulli)` in the network build | A larger network saturates, so the adult-size model (P9) cannot reuse the N = 100 operating points. `--debug-small` already needs a hand-tuned BS drive (20 Hz) to compensate for its smaller in-degree. |
| B10 | (Rat scripts moved to `rat-sh/` on 2026-09-25; superseded ones deleted.) All per-mode timing is hard-coded in rat scripts (`run_*.sh`, `debug*.sh`), and constants are hard-coded in `cpg_2legs_fast.py` | scripts, model | Human modes need their own configuration. Resolved by D1 / Phase 1 (YAML) and Phase 5 (human scripts). |
