# MN5 run manifest

§0 is the **human** workflow (tinyCPG-human). §1–§5 below are the inherited
**rat** manifest (descending vs sensory learning + ablation), kept for the rat
reference runs.

> **tinyCPG-human note (2026-09-25):** this is the inherited **rat** MN5 workflow. The
> rat run scripts now live in `rat-sh/` and are submitted from the repo root
> (`sbatch rat-sh/<script>.sh`). The superseded force-trigger sweeps described
> below (`run_cutforce_sweep*.sh`, `run_cutforce_sensory_unload.sh`) were deleted.
> Restore one with `git show c047f24:<name>.sh` (see `rat-sh/README.md`).
>
> **2026-09-25:**
> - All scripts now use the CPU partition, `--partition=gp_bsccs`. They used
>   to request `acc`, the GPU partition, although no GPU is used, and sat
>   pending.
> - Time limits are 2 h (4 h for consolidation).
> - The 10–12 h limits mentioned below were forced by a model bug, now fixed
>   (PLAN.md §7 B14): recorder bookkeeping grew with the square of simulated
>   time.
> - Mentions of "partition acc" below are historical.
> - Human production: `sbatch run_modes_mn5.sh` (MN5 check A).
> - **2026-09-26:** human runs use the fixed in-degree wiring by default
>   (PLAN.md P3b). Phase 3b size sweep: `sbatch run_p3b_mn5.sh` (§0b).

What to upload to MN5, what to submit, and what to bring back for local plotting.
Plotting is done **locally** (after `scp`-ing results back), not on MN5.

## 0. Human production — MN5 check A (`run_modes_mn5.sh`)

The five locomotion modes at production size (N = 100, BS 60 Hz), 120 s,
λ = 1e-4. It is one 10-task array: tasks 0–4 are human slow / medium / fast /
toe / air, and tasks 5–9 are the same modes for rat as the reference.

- Stance and scheduler come from the species config: human 0.60 with double
  support, rat 0.5 halfcycle.
- CPU partition `gp_bsccs`, 1 node, 64 threads, 1 h per task.
- Details are in the script header and PLAN.md "MN5 check A".

**Files.** Since PLAN.md P1 the model is **not** standalone. It imports
`species_config.py` and reads `config/species/*.yaml`, and stops at startup
without them.

Option A, if MN5 has a git clone (on MN5, in the clone):

```bash
git pull origin main
```

Option B, from this repo root on your laptop. `--relative` keeps the
`config/species/` path:

```bash
rsync -av --relative cpg_2legs_fast.py species_config.py config/species/ run_modes_mn5.sh <user>@<mn5-login>:/path/to/tinyCPG-human/
```

| File | Role |
|---|---|
| `cpg_2legs_fast.py` | The model |
| `species_config.py` | Species-config loader, imported by the model |
| `config/species/human.yaml`, `rat.yaml` | Constants, delays and gait defaults per species |
| `run_modes_mn5.sh` | The job script |

`scripts/` is not needed on MN5 (plotting is local).

**Run.** On MN5, from the directory you uploaded to. The job writes
`results/modes_mn5/` relative to the submission directory.

1. Check the environment (PyYAML is new since P1):

   ```bash
   python3 -c "import nest, yaml, h5py; print(nest.__version__)"
   ```

2. If `yaml` is missing:

   ```bash
   pip install --user pyyaml
   ```

3. Validate the species configs:

   ```bash
   python3 species_config.py --check
   ```

4. Optional cheap first check, task 0 only (human slow):

   ```bash
   sbatch --array=0 run_modes_mn5.sh
   ```

5. The full array (10 tasks):

   ```bash
   sbatch run_modes_mn5.sh
   ```

6. Monitor:

   ```bash
   squeue -u $USER
   ```

- The job runs in a login shell (`#!/bin/bash -l`, as in tinyHippo), so it
  uses the NEST environment your MN5 login profile provides.
- Each task logs to `Nest_modes_<jobid>_<task>.slurmout` and `.slurmerr` in
  the submission directory.
- A missing module or config fails the task within seconds, with a
  `[modes-mn5]` message in the `.slurmerr` file.

**Bring back.** From this repo root on your laptop:

```bash
rsync -av '<user>@<mn5-login>:/path/to/tinyCPG-human/results/modes_mn5/' results/modes_mn5/
```

This gives `human/` and `rat/`, each with `<mode>.h5` and `<mode>.h5.config.yaml`
for the five modes.

**Plot locally:**

```bash
python3 scripts/cpg_modes_stages.py --species human --indir results/modes_mn5/human --out plots/modes/mn5/human_modes_stages.png
```

```bash
python3 scripts/cpg_modes_stages.py --species rat --indir results/modes_mn5/rat --out plots/modes/mn5/rat_modes_stages.png
```

```bash
python3 scripts/cpg_gait_phase_metrics.py results/modes_mn5/human/*.h5
```

## 0b. Human Phase 3b — size sweep at 3× and 10× (`run_p3b_mn5.sh`)

PLAN.md Phase 3b: does the human network behave the same at any population
size under the fixed in-degree wiring (`--conn-rule indegree`, the human
default since 2026-09-26)? The 0.3× and 1× runs and the bernoulli-vs-indegree
switch check run locally (`./run_p3b_local.sh`). This job runs the sizes too
large for a laptop: human medium at N × {1, 3, 10}, seeds 1–3, 120 s. It is
one 9-task array, CPU partition, 64 threads, 2 h per task.

**Files.** The same as §0, plus the two scripts:

```bash
rsync -av --relative cpg_2legs_fast.py species_config.py config/species/ run_p3b_local.sh run_p3b_mn5.sh <user>@<mn5-login>:/path/to/tinyCPG-human/
```

**Run** (from the upload directory; cheap first check is task 0):

```bash
sbatch --array=0 run_p3b_mn5.sh
```

```bash
sbatch run_p3b_mn5.sh
```

**Bring back** into the same folder as the local runs:

```bash
rsync -av '<user>@<mn5-login>:/path/to/tinyCPG-human/results/p3b/' results/p3b/
```

**Summary and figure** (all local and MN5 runs together):

```bash
python3 scripts/p3b_size_invariance.py results/p3b/*.h5
```

Each task's `.log` ends with a `[Timing]` line (NEST vs Python bookkeeping):
the first cost-vs-N data point for MN5 check B.

> **NOTE — architecture fix + unloading-rescue exploration (2026-09-14,
> `feature/ia-rge-direct-pathway`).** `Ia→RG-E`/`Ia→RG-F` (a direct excitatory
> projection matching the reference architecture diagram) is now always wired and
> always plastic in every mode — previously it only existed, gated, in the
> sensory-learning arm. **Every prior result in this manifest and in the paper was
> generated on a circuit missing this pathway** and is superseded pending
> re-validation; the μ=12/16 round-6 jobs still pending in the MN5 queue should be
> cancelled (`scancel <jobid>_8 <jobid>_9`) rather than waited on, since they're
> running the old circuit. Smoke-tested clean at debug scale: the base timer model
> improved (long-standing weak-flexor limitation looks fixed), force-trigger at the
> confirmed operating point improved too (corr −0.81/−0.84 vs the old circuit's
> −0.63/−0.67). Full details and numbers: `CLAUDE.md` "Core architecture fix".
>
> The actual motivating question — can boosted Ia (proprioceptive) drive rescue
> rhythm under simulated unloading, now that a real Ia→RG-E route exists — needed
> two more fixes (`WMAX_IA` and the peak-force seed both now scale with
> `--cut-feedback-gain`, MOD_IA_RG_LOADING_GAIN) before the mechanism would even run
> without degenerating. Local debug-scale tuning after those fixes plateaued at weak
> counter-phase (corr ≈ −0.15 to −0.26) across a wide gain/threshold search that did
> NOT respond to further local tuning — suspected debug-scale population-size
> ceiling (`N_IA_E`/`N_IA_F` = 30 at `--debug-small` vs 100 production), not a
> broken mechanism. `run_cutforce_sensory_unload.sh` (9 tasks, below) tests this
> directly at production N. **Do not trust any correlation number from this arm
> below production scale.**

> **NOTE — force-triggered CUT Phase 3, seed/init robustness (post 2026-09-01).**
> `--cut-trigger force` (closed-loop stance detection: CUT fires off each leg's own
> extensor `force_e` crossing an adaptive threshold, instead of the paced-gait
> clock) is validated at debug scale, and at production scale the parameter-search
> phase (rounds 1-5) is now **closed**: `--fatigue-tau-onset-ms 260
> --cut-force-off-frac 0.35 --cut-max-stance-ms/--cut-max-swing-ms 450` is a
> confirmed, robust, genuinely closed-loop operating point (round 5,
> results/2026-09-01 — `frac_at_cap`=0.00 on both legs across the whole
> {240,250,260}ms × {0.35,0.375,0.40} neighborhood, not just one lucky cell;
> corr(Force-E,Force-F) −0.63(L)/−0.67(R), corr(Force-E_L,Force-E_R) −0.71 at the
> best point). Getting there took 5 rounds and two false positives (rounds 1 and 4
> each produced a clean-looking correlation number that turned out to be a
> disguised clock on `frac_at_cap` re-diagnosis) — see `CLAUDE.md` "Force-triggered
> CUT" for the full history.
>
> Every round so far tested only **one** STDP initial-weight point (μ=3.5,
> CV=0.30). Phase 3 (`run_cutforce_sweep6.sh`) holds the winning config fixed and
> sweeps the same 10-point (μ,CV) grid the base timer-based model already uses for
> its own robustness claim (`rat-sh/run.sh` / paper Algorithm 1), at the same 120s
> duration. **Always run `scripts/cpg_cutforce_diagnostics.py` on the outputs
> before trusting any correlation number.** Not a final result to plot into the
> paper yet.

> **NOTE — 5×5 matrix + logistic gate (post 2026-07-07).** Two changes require a
> re-run of the sensory arms: (i) the activation gate is now a smooth logistic
> (`MOD_LOGISTIC_GATE`, replaces the hard clamp — bio-plausibility) so all figures
> should be regenerated against the new equations; (ii) `rat-sh/run_sensory_stdp.sh` and
> `rat-sh/run_ablation_sensory.sh` now sweep **5 STDP rates** (λ = 1e-6 … 1e-2, arrays
> `0-14`) for the 5 modes × 5 λ comparison. Submit both, bring back
> `cpg_sensory_stdp_*` and `cpg_ablsens_*`, then run
> `scripts/cpg_mode_lambda_summary.py --indir <dated>` (heatmaps + trends + table, auto-detects
> the 5 λ) plus the per-λ figure scripts (which loop `lam1em2..lam1em6`).

> **NOTE — bio-plausibility defaults changed (post 2026-06-30).** The model now
> defaults to lognormal static-weight heterogeneity (`--static-weight-cv 0.5`) and
> a single plastic cutaneous projection (`--cut-static-w 0`, the static co-activation
> pathway dropped). These improve counter-phase but change the canonical numbers, so
> **all arms must be re-run** to regenerate a single-version result set. The run
> scripts need no edits — they pick up the new defaults automatically; the HDF5
> attrs `static_weight_cv` / `cut_static_w` record the configuration.

## 1. Files to upload

Since PLAN.md P1 the model needs `species_config.py` and `config/species/*.yaml`
next to `cpg_2legs_fast.py`, plus the SLURM scripts you intend to submit.

**Option A — git (cleanest, if MN5 has a clone):**
```bash
# on MN5, in the repo clone
git pull origin main
```

**Option B — scp/rsync the minimal set:**
```bash
# from this repo root, on your laptop
rsync -av --relative \
  cpg_2legs_fast.py \
  species_config.py \
  config/species/ \
  rat-sh/run_speed_stdp.sh \
  rat-sh/run_sensory_stdp.sh \
  rat-sh/run_ablation_stim.sh \
  rat-sh/run_ablation_graded.sh \
  rat-sh/run_ablation_sensory.sh \
  rat-sh/run_frozen.sh \
  <user>@mn5:/path/to/tinyCPG/
```

| File | Role |
|---|---|
| `cpg_2legs_fast.py` | The model. |
| `species_config.py`, `config/species/` | Species-config loader and YAML (required since P1). |
| `rat-sh/run_speed_stdp.sh` | Phase A — **descending** arm: speed × λ (BS→RG plastic). |
| `rat-sh/run_sensory_stdp.sh` | Phase A — **sensory** arm: speed × λ (frozen BS + plastic Ia→RG). |
| `rat-sh/run_ablation_stim.sh` | Phase B — epidural-**stim** arm (CUT intact). |
| `rat-sh/run_ablation_graded.sh` | Phase B — **natural** arm (CUT + Ia gated by loading). |
| `rat-sh/run_ablation_sensory.sh` | Phase B — **sensory** arm: loading × λ, Ia is the gated learning drive. |

`make sure they're executable: chmod +x run_*.sh` (already +x in git).

## 2. What to run on MN5

Each script is a 9-task array (`--array=0-8` = 3 conditions × 3 λ), 120 s/task,
64 cpus/task, partition `acc`.

**New / required (the sensory-learning results don't exist yet):**
```bash
sbatch rat-sh/run_sensory_stdp.sh       # -> results/cpg_sensory_stdp_<spd>_<lam>_*.h5
sbatch rat-sh/run_ablation_sensory.sh   # -> results/cpg_ablsens_<gain>_<lam>_*.h5
```

**Descending / ablation arms — only if not already produced with the current
model** (these scripts are unchanged in behaviour; the freeze/Ia flags are OFF
by default, so existing `cpg_speed_stdp_*`, `cpg_ablstim_*`, `cpg_ablgrad_*`
outputs are still valid). Re-run for single-version consistency if you prefer:
```bash
sbatch rat-sh/run_speed_stdp.sh         # -> results/cpg_speed_stdp_<spd>_<lam>_*.h5
sbatch rat-sh/run_ablation_stim.sh      # -> results/cpg_ablstim_<gain>_<lam>_*.h5
sbatch rat-sh/run_ablation_graded.sh    # -> results/cpg_ablgrad_<gain>_<lam>_*.h5
```

**Frozen-weight control (§3.6) — re-run required at BASELINE loading.**
`rat-sh/run_frozen.sh` now runs at full weight-bearing (`IA_GAIN=1.0`) and inherits
the bio-plausible defaults; it tests whether imposing the converged
CUT$\to$RG-E marginal distribution by hand reproduces the clean baseline
rhythm (corr $-0.90$). The old air-stepping frozen data is superseded.
```bash
sbatch rat-sh/run_frozen.sh             # -> results/cpg_frozen_m<M>_cv<CV3>_baseline_*.h5
```

Check progress: `squeue -u <user>`. Each array job writes its tasks into
`results/`. Logs: `Nest_*_<jobid>_<task>.slurmout/.slurmerr`.

> Connectivity figure (`--dump-connectivity`) is **already generated locally at
> production N** (`results/connectivity/conn_dump.h5`, committed) — no MN5 run needed.

## 3. What to bring back

```bash
# from your laptop — pull just the HDF5s into a dated folder
mkdir -p results/$(date +%F)
rsync -av '<user>@mn5:/path/to/tinyCPG/results/cpg_sensory_stdp_*.h5'  results/$(date +%F)/
rsync -av '<user>@mn5:/path/to/tinyCPG/results/cpg_ablsens_*.h5'       results/$(date +%F)/
# (and cpg_speed_stdp_* / cpg_ablstim_* / cpg_ablgrad_* if you re-ran them)
```
Each HDF5 is ~14 MB at production N — verify sizes after transfer (a truncated
scp shows up as a few MB and breaks the plotters).

## 4. Plot locally (after transfer)

Point `--indir` at the dated results folder. These are the **current** generators
(all write straight into `paper/figures/`, the single source of truth for the
manuscript — see `paper/README.md`). Superseded generators live in
`scripts/legacy/` and are not part of this pipeline.

```bash
INDIR=results/$(date +%F)

# Architecture + connectivity (Methods) — only need re-running after a --dump-connectivity change
python3 scripts/cpg_architecture_diagram.py
python3 scripts/cpg_connectivity_figure.py --in results/connectivity/conn_dump_sensory.h5 \
        --out paper/figures/fig_connectivity.png

# STDP weights: both legs x 3 projections x 5 modes, and 5 modes x 5 lambda
python3 scripts/cpg_stdp_weight_matrix.py --indir $INDIR --out paper/figures/fig_stdp_weight_matrix.png
python3 scripts/cpg_stdp_weights_grid.py  --indir $INDIR --out paper/figures/fig_stdp_weights_grid.png

# Force at 3 learning stages x 5 modes, one figure per lambda
for lam in lam1em2 lam1em3 lam1em4 lam1em5 lam1em6; do
  python3 scripts/cpg_force_stages.py --indir $INDIR --lambda-tag $lam \
          --out paper/figures/fig_force_stages_$lam.png
done

# Full-circuit population activity x 5 modes, one figure per lambda
for lam in lam1em2 lam1em3 lam1em4 lam1em5 lam1em6; do
  python3 scripts/cpg_network_matrix.py --indir $INDIR --lambda-tag $lam \
          --out paper/figures/fig_network_matrix_$lam.png
done

# 5x5 mode x lambda comparison: heatmaps + trends + table (auto-detects available lambda tags)
python3 scripts/cpg_mode_lambda_summary.py --indir $INDIR --out paper/figures/fig_mode_lambda
cp paper/figures/fig_mode_lambda_table.tex paper/mode_lambda_table.tex

# Epidural-stim vs natural loading contrast (needs cpg_ablstim_* and cpg_ablgrad_*)
python3 scripts/cpg_epidural_contrast.py --stim-dir $INDIR --natural-dir $INDIR \
        --out paper/figures/fig9_epidural_contrast.png

# Per-run gait/force/weights for any single file (debug tool, writes to results/)
python3 scripts/cpg_plot_from_hdf5.py --in $INDIR/cpg_sensory_stdp_13_5cms_lam1em3_*.h5 --save-prefix sensory_med
```

## 5. Force-triggered CUT Phase 3 — seed/init robustness (run separately from §1-4)

Rounds 1-5 (parameter search, now closed) found and confirmed a genuine,
non-cap-dominated operating point: τ=260/off=0.35/cap=450ms. See the NOTE above
and `CLAUDE.md` "Force-triggered CUT" for the full history. This phase holds
that config fixed and checks it isn't an artifact of the single STDP init point
(μ=3.5, CV=0.30) every prior round used. Use `run_cutforce_sweep6.sh`. Only two
files needed; the model is standalone.

**Option A — git (cleanest, if MN5 has a clone):**
```bash
# on MN5, in the repo clone
git pull origin main
```

**Option B — rsync the minimal set:**
```bash
# from this repo root, on your laptop
rsync -av \
  cpg_2legs_fast.py \
  run_cutforce_sweep6.sh \
  scripts/cpg_cutforce_diagnostics.py \
  <user>@mn5:/path/to/tinyCPG/
```

**Submit:**
```bash
# on MN5
chmod +x run_cutforce_sweep6.sh   # already +x in git; harmless if already set
sbatch run_cutforce_sweep6.sh     # 10-task array, 120s/task, 64 cpus/task, partition acc
squeue -u <user>                  # check progress
```
Logs: `Nest_cutforce6_<jobid>_<task>.slurmout/.slurmerr`. Output:
`results/cpg_cutforce6_robustness_idx0<N>_mu<MU>_cv<CV>_*.h5` (10 files, one per
(μ,CV) point in the same grid `rat-sh/run.sh`/Algorithm 1 uses — see the script header).

**Runtime — calibrated from a real timeout, not an estimate.** The first
submission used `--time=03:00:00` and every one of the 10 tasks was
**cancelled by SLURM at the exact same point** (chunk 800/1200, 80s of the
120s sim, 66.7%) — zero `.h5` files were ever produced (the script only
writes the HDF5 at the very end). 180min for 66.7% extrapolates to ~270min
(4.5h) for the full run *at that load level* — but MN5 load varies run to
run, so a flat 33%-margin budget (06:00:00) is still only sized for the one
load level actually observed. `--time` is now `12:00:00`, matching `rat-sh/run.sh`'s
own precedent for its 120s/10-task runs on the same partition (which budgets
12h despite reportedly finishing in ~2h — see paper Sec 3.9), a margin that's
already proven itself against MN5's load variance in practice. If you see
`results/<dated>/` fill up with `.slurmout`/`.slurmerr` pairs but no `.h5`
files, check the `.slurmerr` for `CANCELLED ... DUE TO TIME LIMIT` before
assuming something else broke.

**Bring back:**
```bash
# from your laptop
mkdir -p results/$(date +%F)
rsync -av '<user>@mn5:/path/to/tinyCPG/results/cpg_cutforce6_*.h5' results/$(date +%F)/
```

**Evaluate — run the diagnostic script first, before looking at correlation:**
```bash
python3 scripts/cpg_cutforce_diagnostics.py results/$(date +%F)/cpg_cutforce6_*.h5
```
Same bar as round 5: `frac_at_cap` should stay low on both legs and
corr(Force-E_L,Force-E_R) strongly negative **across all 10 points**, not just
near μ=3.5. μ=0 and μ=16 are the real stress tests — near-zero and much
stronger initial CUT/BS weight than every prior round has tested. If it holds
broadly, Phase 4 (loading/speed breadth) is next; if it only holds near μ=3.5,
that's a real finding (initialization-sensitivity) to document, not a pass.

## Unloading-rescue exploration, round 1 (`run_cutforce_sensory_unload.sh`)

Branch: `feature/ia-rge-direct-pathway`. Prerequisite: both architecture-fix
commits on that branch must be on MN5 first (Ia→RG-E/F always-on, and the
loading-dependent `WMAX_IA`/peak-seed) — this script tests nothing new without
them.

**Upload:**
```bash
# from this repo root, on your laptop
rsync -av \
  cpg_2legs_fast.py \
  run_cutforce_sensory_unload.sh \
  scripts/cpg_cutforce_diagnostics.py \
  <user>@mn5:/path/to/tinyCPG/
```

**Submit:**
```bash
# on MN5
chmod +x run_cutforce_sensory_unload.sh   # already +x in git; harmless if already set
sbatch run_cutforce_sensory_unload.sh     # 9-task array, 120s/task, 64 cpus/task, partition acc
squeue -u <user>
```
Logs: `Nest_cutf_unload_<jobid>_<task>.slurmout/.slurmerr`. Output:
`results/cpg_cutfunload_<loading>_ia<gain>_idx00_*.h5` — 9 files, one per
(loading, Ia-gain) point (3×3 grid: `--cut-feedback-gain` 1.0/0.5/0.1 ×
`--ia-feedback-gain` 1.0/4.0/8.0; see script header for the exact array-index
mapping). `--time=12:00:00` follows the same established precedent as
`run_cutforce_sweep6.sh` (this mode's per-chunk bookkeeping is measurably
slower than timer-based paced-gait) — do not shorten it without a real
timeout observation to calibrate from.

**Bring back:**
```bash
# from your laptop
mkdir -p results/$(date +%F)
rsync -av '<user>@mn5:/path/to/tinyCPG/results/cpg_cutfunload_*.h5' results/$(date +%F)/
```

**Evaluate — diagnostic first, as always:**
```bash
python3 scripts/cpg_cutforce_diagnostics.py results/$(date +%F)/cpg_cutfunload_*.h5
```
What to look for: (1) the `ia1`/baseline (`--cut-feedback-gain 1.0`) row should
reproduce the already-confirmed baseline numbers regardless of Ia gain (sanity
anchor — if it doesn't, something about the loading-dependent cap/seed logic
broke the unmodified full-loading case, a red flag independent of the
unloading question); (2) whether corr(Force-E,Force-F) improves toward the
−0.7 to −0.8 genuine range at production N for `toe`/`air` rows, where debug
scale plateaued at −0.15 to −0.26 regardless of gain — if production shows the
same flat, unmoving result, that argues the ceiling is real (not a debug-scale
population-size artifact) and the mechanism needs a different fix, not more
gain; (3) `frac_at_cap` as always — a clean-looking correlation with high
`frac_at_cap` is a disguised clock, not a rescue.
