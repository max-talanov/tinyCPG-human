# Methods (skeleton)

> Skeleton for the paper Methods section. Each subsection lists what to write,
> which figure / table / parameter to cite, and where the prose should land
> relative to the existing artefacts (figures, code, CSVs).
> Cross-references use `[Fig X]`, `[Table Y]`, `[Eq Z]` as placeholders.

---

## 2.1 Model overview

**Write:** One paragraph that frames the work in the Rybak/Danner/Zhang
lineage and states the four extensions in one sentence (STDP, Ia closed
loop, motoneuron/muscle, paced Ia). Reference the architecture schematic.

**Cite:** Rybak 2006; Shevtsova 2015; Danner 2017; Zhang/Shevtsova 2022;
Kiehn 2016.

**Anchor figure:** `[Fig 1]` = architecture schematic (the diagram you
already have).

Suggested opening: *"The two-leg spinal CPG model presented here extends the
canonical Rybak-style architecture (Rybak 2006; Shevtsova 2015) with four
mechanisms not present in the Zhang 2022 reference: (i) STDP-driven
self-organisation of descending and cutaneous afferent synapses onto the
rhythm-generator (RG), (ii) a closed-loop Ia feedback pathway to the
reciprocal-inhibition interneurons, (iii) motoneuron pools driving Hill-like
muscle proxies with force and length dynamics, and (iv) an externally paced
sequential Ia activation simulating heel→toe weight transfer during stance.
Each leg comprises an extensor and a flexor half-centre, organised as a
half-centre oscillator with asymmetric reciprocal inhibition (Zhang 2022),
coupled across the midline by commissural inhibition (Kiehn 2016). The model
is implemented in NEST 3.9 (Diesmann & Gewaltig 2002) and is publicly
available at github.com/max-talanov/tinyCPG."*

---

## 2.2 Single-neuron model

**Write:** Short subsection on Izhikevich neurons and rationale for choosing
them over Hodgkin–Huxley.

> *"All spiking neurons are modelled as Izhikevich quadratic-integrate-fire
> units (Izhikevich 2003), implemented in NEST as `izhikevich`. Excitatory
> rhythm-generator extensor neurons (RG-E) use the regular-spiking parameter
> set (a = 0.02, b = 0.2, c = −65, d = 8). Rhythm-generator flexor neurons
> (RG-F) use the intrinsic-bursting set (a = 0.02, b = 0.2, **c = −55, d = 4**),
> approximating the persistent-sodium-driven bursting (INaP) used in
> Hodgkin–Huxley CPG models (Rybak 2006). Inhibitory interneurons (InE, InF,
> Ia-INT) use a fast-spiking parameter set (d = 2). Synapse currents are
> instantaneous (delta synapses, NEST default). Conduction delays are drawn
> from the rat `length_velocity` preset (Table 2) with Gaussian jitter
> σ = 0.2 ms."*

**Cite:** Izhikevich 2003; Brette & Gerstner 2005 (for comparison rationale);
Rybak 2006 (for what we're approximating).

**Anchor:** `[Table 1]` = Izhikevich neuron parameter rows from
`paper/params.md` (Section "Izhikevich neurons").

---

## 2.3 Network architecture

**Write:** Connectivity-by-section paragraph, organised by the seven
modulation tags (MOD_ZHANG_ASYM, MOD_IA_LOOP, MOD_PACED_GAIT, MOD_TONIC_BS,
MOD_COACT, MOD_CUT_REFLEX, MOD_ACT_GATE). For each, name source and target
populations, weights, and connection probability. Cite the literature
justifying each pathway.

**Anchor table:** `[Table 1]` = `paper/params.md` (full parameter table).
**Anchor figure:** `[Fig 1]` = schematic.

Sub-paragraphs to include:

1. **Asymmetric reciprocal inhibition (Zhang 2022).** F→InF→E pathway is
   strong (`W_INF2RGE = -48 pA`, `P = 0.30`); E→InE→F pathway is weak
   (`W_INE2RGF = -8 pA`, `P = 0.15`) — a 6:1 ratio. *Cite:* Zhang 2022;
   Talpalar 2013.

2. **Closed-loop Ia → reciprocal IN (this work, MOD_IA_LOOP).** Ia-E parrots
   project to InE (`W = 6 pA`, `P = 0.25`), Ia-F to InF. *Cite:* Pearson 1995;
   Rossignol 2006; Hultborn 2006 (for the bio justification).

3. **Cutaneous reflex (MOD_CUT_REFLEX).** CUT parrots project to RG-E
   (STDP-plastic) and to InE (`W = 6 pA`, `P = 0.30`). *Cite:* Forssberg 1980;
   Pearson 1995.

4. **Commissural inhibition (Kiehn 2016).** L↔R flexor RG inhibition
   (`W = -20 pA`, `P = 0.22`) is strong, extensor (`W = -8 pA`, `P = 0.10`)
   is weak. *Cite:* Kiehn 2016; Talpalar 2013.

5. **Motor pool reciprocal inhibition** (MOTOR_RECIP). M-E↔M-F mutual
   inhibition (`W = -22 pA`, `P = 0.25`). *Cite:* McCrea & Rybak 2008.

6. **Motor → muscle proxy.** Each motor neuron projects to N_MUS parrots
   (`P_M2MUS = 0.8`); muscle parrots aggregate motoneuron spikes into the
   rate signal that drives the activation dynamics. *Cite:* McCrea & Rybak
   2008 (for the rationale of separating M from RG).

---

## 2.4 Brainstem drive

**Write:** Two short paragraphs.

1. **Tonic descending drive (MOD_TONIC_BS).** Reticulospinal input modelled
   as a `BS_REGULAR_HZ = 60 Hz` Poisson process with `σ = 0.25 Hz` noise,
   identical for both legs (`--enforce-tonic-bs`). The 60 Hz value sits in
   the middle of the rat reticulospinal range (20–80 Hz; Drew & Rossignol
   1986). *Cite:* Drew & Rossignol 1986; Brocard 2010.

2. **Why constant (not phase-gated) drive.** Contrasts with Zhang 2022, who
   modulate α to vary speed. We keep BS tonic and pace the rhythm via Ia
   instead (see § 2.7).

---

## 2.5 STDP learning

**Write:** One paragraph on the spike-time-dependent plasticity rule, one on
which synapses are plastic, one on the initial-weight sweep design.

> *"Two projections — cutaneous CUT→RG-E and brainstem BS→RG-{E,F} — are
> equipped with multiplicative STDP synapses (NEST `stdp_synapse`,
> tau_plus = 20 ms, λ = 0.001, α = 0.95, µ = 0.4 / 0.4, w_max = 120 pA;
> for BS w_max = 30 pA — see § 2.6 for the cap rationale). Initial weights
> are drawn from a lognormal distribution with mean µ and CV (Morrison 2007).
> We swept (µ, CV) across 10 diagnostic points spanning four orders of
> magnitude (Table 3) to verify that the post-training weight distribution
> converges to the same plateau regardless of initialisation, demonstrating
> self-organisation."*

**Cite:** Bi & Poo 1998; Morrison 2007; Gilson 2011.

**Anchor table:** `[Table 3]` = the 10 (µ, CV) sweep points (in the
`run.sh` SWEEP_PAIRS string).

**Anchor figure:** `[Fig 2c–e]` = the STDP convergence subpanels from
`combined_summary_portrait.png`.

---

## 2.6 Sensory feedback and Ia rate-coding

**Write:** Subsection describing how Ia rates are computed from the muscle
proxy and fed back into the network.

> *"Ia afferent firing rate r_Ia (Hz) is computed at each chunk boundary as
> a linear combination of muscle force F and stretch (length above resting)
> Δℓ:*"
>
> ```
> r_Ia = IA_BASE_HZ + IA_K_FORCE * F + IA_K_STRETCH * Δℓ
> ```
>
> *"with `IA_BASE_HZ = 10 Hz`, `IA_K_FORCE = 6 Hz/F`, `IA_K_STRETCH = 250 Hz/L`,
> clamped to [0, IA_RATE_MAX_HZ = 500 Hz]. This rate is pushed to the Ia
> Poisson generator population every `rate-update-ms = 100 ms`. The
> resulting Ia spike trains drive (a) the classical Ia-INT → antagonist
> motor-pool pathway (Jankowska 1992), and (b) the closed-loop Ia → recip-IN
> pathway introduced in this work (MOD_IA_LOOP, see § 2.3.2)."*

**Cite:** Loeb 1981; Prochazka 1999; Jankowska 1992; Hultborn 2006.

**Anchor:** Parameter table rows in `paper/params.md` § "Ia spindle
rate-coding (NEW)".

---

## 2.7 Activation and force dynamics

**Write:** Paragraph deriving the Hill-style activation, force, and length
proxies from muscle-parrot rates.

Equations:

```
a_raw  = ACT_MAX * (1 - exp(-ACT_SAT_K * r_mus))           # saturation
d      = clamp(r_RG / rg_ref, 0, 1) ^ ACT_GATE_POWER       # RG gate
a_tgt  = clamp(a_raw * d, 0, ACT_MAX)
a(t+1) = a(t) + (1 - exp(-Δt/τ_a)) * (a_tgt - a(t))         # first-order LP

F_tgt  = FORCE_MAX * (1 - exp(-FORCE_SAT_K * a))
F(t+1) = F(t) + (1 - exp(-Δt/τ_F)) * (F_tgt - F(t))         # first-order LP

ℓ(t+1) = ℓ(t) + κ_L * (L0 - ℓ(t)) - SHORTEN_GAIN * F * Δt
         + STRETCH_GAIN * I_CUT * Δt
```

**Time constants for paced gait** (overridden by `--paced-gait`):
τ_act_rise = τ_act_decay = 40 ms, τ_force_rise = τ_force_decay = 80 ms.
Rationale: time constants must be < half stance (~250 ms) to track the 500 ms
stance plateau, but > 30 ms to filter spiking jitter. *Cite:* Zajac 1989;
Winters 1995.

---

## 2.8 Paced gait protocol (MOD_PACED_GAIT)

**Write:** Subsection describing the externally paced cycle.

> *"To probe gait at controlled cycle periods, we introduced a paced
> activation protocol. Each step period (`--step-period-ms`, default 1000 ms)
> is divided into two half-cycles of 500 ms each. During the stance half of
> leg L, the L cutaneous generator fires at CUT_RATE_ON_HZ = 100 Hz, and
> three sequential Ia-E sub-groups fire at 60, 80, and 100 Hz over
> consecutive ~167 ms windows — emulating heel → mid → toe pressure transfer
> during stance (Loeb & Duysens 2018). During the swing half, all CUT and
> Ia-E drive is silenced for that leg. The contralateral leg R runs the
> mirror schedule (180° trot offset). Reciprocal inhibition and the RGF
> intrinsic-bursting dynamics maintain the swing-leg flexor burst without
> external pacing."*

**Anchor:** `[Fig 3]` (or row 1 of the combined summary).

---

## 2.9 Simulation setup

**Write:** Brief paragraph on the simulation parameters.

> *"All simulations were performed with NEST 3.9 (Diesmann & Gewaltig 2002)
> using a kernel resolution of 0.2 ms, simulation chunks of 100 ms, and
> 64 OpenMP threads per task on a single AMD EPYC node (MN5 system,
> Barcelona Supercomputing Center). Initial-weight sweeps were run as
> 10-task SLURM job arrays; ablation and speed-sweep experiments used
> 5-task arrays. Each 30 s simulation completes in ~30 min wall clock; each
> 120 s simulation completes in ~2 h."*

---

## 2.10 Data analysis

**Write:** How we computed the reported metrics.

1. **Cycle period (`cycle_mean_ms`, `cycle_std_ms`):** Force-E peak-to-peak
   interval, computed on the last 20 s of each run with a 5.0 a.u. minimum
   peak height and a 300 ms minimum inter-peak gap. (Reference: helper
   `_find_cycle_periods` in `cpg_ablation_figure.py`.)

2. **Counter-phase strength (`corr_ef`):** Pearson correlation between
   Force-E and Force-F over the last 20 s.

3. **Peak force amplitude:** 95th percentile of the force signal over the
   last 20 s. (Robust to outliers.)

4. **STDP convergence:** Per-projection mean ± std of synaptic weights,
   sampled every 1 s, smoothed with a 1 s moving average for plotting.

5. **Statistical tests:** No formal statistical comparisons are reported in
   the present work — all reported numbers are point estimates from
   deterministic simulations with a fixed seed (12345 + 10007 × idx for
   sweep tasks). Reproducibility is therefore exact.

---

## 2.11 Code, data, and reproducibility

**Write:** Two short paragraphs.

> *"All source code is available at github.com/max-talanov/tinyCPG. The
> simulator is invoked from three top-level shell scripts: `run.sh` (10-point
> µ:CV sweep, 30 s), `run_ablation.sh` (5-condition ablation, 30 s each),
> `run_speed.sh` (5-step-period speed sweep, 30 s each). All HDF5 outputs
> from the SLURM job arrays used to produce Figures 2–4 are deposited at
> [Zenodo DOI: TODO] (raw spike rates and weights, ~50 MB per file)."*
>
> *"To reproduce the main figure, run `./run.sh` on a 64-thread node (or
> `./debug.sh` locally for the small-N variant) and plot with
> `python3 cpg_combined_summary.py --files results/cpg_*.h5 \\
> --layout landscape --out fig.png`. Total wall-clock for the main figure
> on MN5 is ~6 h × 10 tasks ≈ 60 core-hours."*

---

# Notes for prose-writing

- **Tense:** Past tense for actions ("We trained the synapses…"), present
  tense for the model description ("RG-E projects to InE…").
- **Voice:** First-person plural ("we"), consistent with comp-neuro
  convention.
- **Lengths to aim for:** Methods total ~1500–2000 words for PLOS Comp Bio;
  Frontiers allows up to ~3000 words but more concise reads better.
- **Eq numbering:** Number eqs sequentially across § 2.6–§ 2.7. Match Zhang
  2022 style: bold equation labels in parentheses, e.g., (Eq. 5).
- **What to put in Supplementary:** Full param table (Markdown / LaTeX from
  `paper/params.{md,tex}`), exact NEST kernel settings dump, all 10 sweep
  HDF5 files (Zenodo).
- **Reviewer fishhooks to address pre-emptively** (insert as short
  paragraphs in Methods or Discussion):
   - *"Why Izhikevich and not HH?"* — efficiency + reduced parameter count
     for the 200-neuron×8-population NEST model; intrinsic bursting is
     captured at the qualitative level needed here.
   - *"Why only 2 legs, not 4?"* — scope: the present paper extends Rybak
     architecture below the RG, not laterally to fore-hind coordination.
     4-limb extension is straightforward and left for future work.
   - *"Why no formal statistics?"* — deterministic simulations with fixed
     seeds produce point estimates that are reproducible; the relevant
     uncertainty is captured by the (µ, CV) initialisation sweep, which is
     reported in full.

# Figure → section mapping

| Figure | Section that introduces it | Result text refers to it |
|---|---|---|
| Fig 1 — architecture schematic | § 2.1 model overview | § 3.1 |
| Fig 2 — main result (combined_summary_portrait.png) | § 2.5–§ 2.8 | § 3.2 |
| Fig 3 — ablation study (fig_ablation.png) | § 2.10 | § 3.3 |
| Fig 4 — speed sweep (fig_speed.png) | § 2.10 | § 3.4 |
| Table 1 — parameter table (params.md → params.tex) | § 2.3 | (supplementary) |
| Table 2 — delay model (rat / human presets) | § 2.2 | (supplementary) |
| Table 3 — (µ, CV) sweep points | § 2.5 | § 3.2 |
