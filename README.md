# tinyCPG-human

The tinyCPG NEST spinal central pattern generator (sCPG) model, adapted to
**human data** with **bio-plausible spinal plasticity**. It covers both the
**healthy** (intact) cord and **spinal cord injury (SCI)**.

This repository is a fork of
[tinyCPG](https://github.com/max-talanov/tinyCPG). It was imported from the
`feature/spinal-tag-capture-consolidation` branch, with full history. tinyCPG
is a closed-loop spiking model of the two-legged **rat** sCPG. Its sensory and
descending synapses are not hand-tuned: they self-organise through
spike-timing-dependent plasticity (STDP), with a tag-and-capture consolidation
step on top. tinyCPG-human keeps that circuit and learning machinery. It
re-targets parameters, timing and validation data from rat to human.

## Goal

Build and demonstrate a **bio-plausible human spinal CPG model**, intact and
after SCI. Its gradual rehabilitation dynamics must come from bio-plausible
spinal plasticity. The goal has three parts:

1. **Human spinal CPG.** Parameters must stay within human physiological
   ranges. These include conduction delays over human path lengths, human
   gait-cycle and stance/swing timing, and human afferent and reticulospinal
   firing rates. The circuit keeps the established spinal architecture:
   asymmetric reciprocal inhibition, tonic reticulospinal drive, Ia and
   cutaneous closed-loop feedback, and left/right commissural coupling.
2. **Healthy vs. SCI.** The intact and injured cords run on the **same
   circuit**. Injury is modelled by:
   - reduced or frozen descending drive (`--freeze-bs-rg`, the sensory-learning
     arm);
   - reduced loading and afferent input (`--ia-feedback-gain`,
     `--cut-feedback-gain`);
   - later, epidural-stimulation-like tonic afferent drive, the main
     rehabilitation manipulation in human SCI.
3. **Gradual rehabilitation through spinal plasticity.** Recovery must emerge
   from spinal learning over a realistic time course, not return instantly.
   Three pathways are plastic: `BS→RG`, `CUT→RG-E` and `Ia→RG-E/F`.
   Tag-and-capture consolidation (`--consolidate`) adds a retention gate and a
   settling-in period on top of vanilla STDP. Force-triggered stance/swing
   (`--cut-trigger force`) makes the gait emergent, so the learning signal
   comes from behaviour, not a clock.

## What the model contains

Each leg has an extensor and a flexor rhythm generator (RG-E, RG-F). They are
coupled by asymmetric reciprocal inhibition, with F→E about 6× stronger than
E→F (Zhang 2022). The rhythm generators drive motoneuron pools and Hill-like
muscle proxies. Muscle force and length close the loop back through Ia
afferents. Left and right legs are coupled by commissural inhibition.

```
              CUT (cutaneous, phasic)         BS (brainstem, tonic)
               │ STDP                          │ STDP
               ▼                               ▼
              RG-E ◄──── InF ◄───── RG-F   (asymmetric: F→E strong, E→F weak)
               │          ▲          │
               ▼     (Ia loop)       ▼
              M-E                   M-F        (motor pools, reciprocal inhibition)
               ▼                     ▼
              mus-E                 mus-F      (activation → force, length)
               └───── force, length ─┘
                          ▼
                     Ia-E, Ia-F ──STDP──► RG-E / RG-F
```

The model inherits these mechanisms from tinyCPG:

- **STDP self-organisation** of the descending (`BS→RG`) and afferent
  (`CUT→RG-E`, `Ia→RG-E/F`) synapses.
- **Tag-and-capture consolidation** (`--consolidate`). NEST STDP sets a fast
  "tag". A per-leg, PRP-pool-like accumulator decides whether the tag is
  captured into a stable baseline. Bouts that end on a genuine force threshold
  reinforce capture. Bouts forced by the failsafe timer suppress it. The
  literature grounding is in
  [`spinal_plasticity_as_learning_spec.md`](spinal_plasticity_as_learning_spec.md).
- **Closed-loop force-triggered gait** (`--cut-trigger force`). A per-leg
  Schmitt trigger on extensor force switches between stance and swing, with a
  required failsafe timeout. `--muscle-fatigue` lets force decay within a
  stance bout.
- **Species-aware conduction delays**
  (`--species human`, which loads `config/species/human.yaml`, including its
  `delays:` section). Each delay is computed as
  `syn_delay + path_length / conduction_velocity`, using the species' path
  lengths and velocities.

## Human adaptation: status and roadmap

| Item | Status |
|---|---|
| Rat tinyCPG model, STDP and consolidation imported | done |
| YAML species configs with delays tied to species (`config/`, `species_config.py`) | done (P1) |
| Human conduction/synaptic delay values (`delays:` in `config/species/human.yaml`) | done (P2; reflex probe 30.2 ms) |
| Species-dependent flexor BS gain (`FLEXOR_BS_GAIN` in the species YAML) | present, currently 1.0 for both species |
| Human stance fraction with double support (`--gait-scheduler phase`, stance 0.60) | done (P3) |
| Size-invariant wiring (`--conn-rule indegree`, human default) and consolidation of every plastic synapse (B13) | done (P3b); 3×/10× size check on MN5 pending |
| Vanilla STDP retired for human: force-trigger + tag-and-capture consolidation by default | to do (P5, after the P4 muscle) |
| Human gait timing: stride period and cadence per mode | to do (P5) |
| Human bio-plausibility constraint table, replacing the rat table in `CLAUDE.md` | to do |
| Human locomotion modes (slow/normal/fast walking, reduced body-weight support) | to do |
| Validation against human EMG and kinematics, healthy and SCI | to do |
| SCI + epidural-stimulation rehabilitation protocol with consolidation | to do |

The main rat-to-human changes:

- **Timing.** The rat locomotor cycle is 400–700 ms. A human stride at
  comfortable walking speed lasts about 1.0–1.2 s, with stance about 60% of
  the cycle. `--step-period-ms`, `--stance-fraction`, the failsafe caps
  (`--cut-max-stance-ms`, `--cut-max-swing-ms`), the fatigue time constants
  and `--consolidate-tau-tag-ms` must all be rescaled together.
- **Delays.** Human spinal and peripheral paths are much longer than rat
  paths. The `human` delay preset already encodes this. Its path lengths and
  velocities still need to be checked against human nerve-conduction data.
- **Plasticity time course.** Rehabilitation in human SCI takes weeks to
  months of training. The consolidation gate is the mechanism that maps
  simulated training sessions onto that slow, incremental time course.

## Repository layout

| Path | Contents |
|---|---|
| `cpg_2legs_fast.py` | The model: neurons, connectivity, plasticity, consolidation, simulation loop, HDF5 export |
| `run_modes_local.sh` | The five locomotion modes (slow/medium/fast walk, toe/air stepping) locally, for one species |
| `regress.sh` | Rat regression check; must pass after every model change |
| `rat-sh/` | Rat reference scripts, kept only for comparison: local debug runs and MN5 SLURM sweeps (see `rat-sh/README.md`) |
| `scripts/` | Figure and analysis generators, including `cpg_plot_from_hdf5.py` and `cpg_cutforce_diagnostics.py` |
| `scripts/legacy/` | Superseded generators, kept for reference |
| `paper/` | LaTeX manuscript of the rat model (`main.tex`, `sections/`, `figures/`) |
| `validation/` | Literature-validation notes and EMG data requests |
| `spinal_plasticity_as_learning_spec.md` | Literature spec for spinal plasticity timescales and gating, and for tag-and-capture |
| `config/species/`, `species_config.py` | YAML species configs (constants, CLI defaults, delays) and their loader |
| `CLAUDE.md` | Detailed model internals, tuning history, key constants and "do not touch" list |
| `MN5_RUN.md` | Workflow for MN5 runs: upload, submit, retrieve, plot |

## Quick start

```bash
pip install -r requirements.txt     # needs nest-simulator>=3.9 (not the `nest` package)
```

Human model, the five locomotion modes (debug-small, local), and their
force/weight figures at three stages:

```bash
./run_modes_local.sh human 120000 1e-4
```

```bash
python3 scripts/cpg_modes_stages.py --species human
```

A single short human run:

```bash
python3 cpg_2legs_fast.py --debug-small --paced-gait --species human --sim-ms 10000 --out results/debug_human.h5
```

Reflex latency of the human delays (target ~30 ms):

```bash
python3 scripts/probe_reflex_latency.py --species human
```

The rat model is kept only for comparison: `./rat-sh/debug.sh` is the rat
reference run, and `./regress.sh` checks that rat output is unchanged.

Use the healthy vs. SCI flags on top of this. Descending plasticity off:
`--freeze-bs-rg`. Reduced loading: `--ia-feedback-gain`,
`--cut-feedback-gain`. Closed-loop gait with consolidation:
`--cut-trigger force --muscle-fatigue --consolidate`. Run
`scripts/cpg_cutforce_diagnostics.py` on any force-trigger output before you
trust its correlations. A `frac_at_cap` near 1.0 means the failsafe timer is
driving the gait, not the force threshold.

## Implementations

The reduced model runs in **NEST 3.9** with Izhikevich neurons. It is cheap
enough to make large parameter sweeps practical. A conductance-based
**Hodgkin–Huxley** implementation of the same circuit, used as a biophysical
cross-check, lives in
[memCPG/CPG_STDP/py](https://github.com/max-talanov/memCPG/tree/main/CPG_STDP/py).

## Keeping in sync with tinyCPG

The upstream repository is set up as the `tinycpg` remote. To pull in new
rat-model work:

```bash
git fetch tinycpg feature/spinal-tag-capture-consolidation
```

```bash
git merge tinycpg/feature/spinal-tag-capture-consolidation
```

## License

MIT. See [LICENSE](LICENSE).
