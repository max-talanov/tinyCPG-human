# rat-sh/ — rat reference scripts

tinyCPG-human is dedicated to the **human** model. The rat model is kept only
as a **comparison and regression baseline**. These are the rat run scripts
inherited from tinyCPG that are still needed for that. They run the model with
`--species rat`.

The SLURM scripts request the **CPU partition** (`gp_bsccs`, 2 h; 4 h for
consolidation). They used the GPU partition `acc` before 2026-09-25.

**Run them from the repository root.** They call `cpg_2legs_fast.py` and write
`results/` relative to the current directory:

```bash
./rat-sh/debug.sh
```

```bash
sbatch rat-sh/run_sensory_stdp.sh
```

| Script | What it is | Why kept |
|---|---|---|
| `debug.sh` | Local debug-small run, timer-paced gait | Golden rat reference #1 for `../regress.sh` |
| `debug_force.sh` | Same, force-triggered stance/swing | Golden rat reference #2 for `../regress.sh` |
| `run_sensory_stdp.sh` | MN5: 3 speeds × 5 λ, sensory-learning arm (paper) | Rat side of the five-mode comparison (slow/medium/fast); `../run_modes_local.sh` mirrors its flags |
| `run_ablation_sensory.sh` | MN5: 3 loadings × 5 λ, sensory arm (paper) | Rat side of toe/air stepping |
| `run_speed_stdp.sh` | MN5: 3 speeds × λ, descending arm (BS plastic) | Descending-vs-sensory learning contrast; relevant to healthy vs. SCI (PLAN.md P7) |
| `run_ablation_graded.sh` | MN5: loading × λ, natural arm (Ia and CUT gated) | Unloading reference for SCI (P7) |
| `run_ablation_stim.sh` | MN5: loading × λ, CUT held at full (epidural-stim arm) | Rat counterpart of the EES contrast (P7) |
| `run.sh` | MN5: 10-point (μ, CV) initial-weight sweep (paper Algorithm 1) | Init-robustness method, reused for human production (P9) |
| `run_frozen.sh` | MN5: frozen-weight control (plasticity off) | Paper control |
| `run_consolidate_all_modes_production.sh` | MN5: force-trigger + `--consolidate`, medium/fast/toe/slow (Stage 5) | Latest rat consolidation operating points; template for human P5/P6 |
| `run_sim_mt.sh` | Rat container job | Optional rat run inside the Docker image (`--script=rat-sh/run_sim_mt.sh`); the image default is the human five-mode job |

## Deleted on 2026-09-25

These were superseded exploratory or development sweeps. Their results are
documented in `../CLAUDE.md` (rat tuning history). They are still in git
history; restore one with:

```bash
git show c047f24:run_cutforce_sweep6.sh > run_cutforce_sweep6.sh
```

- **`run_cutforce_sweep.sh` … `run_cutforce_sweep6.sh`:** six force-trigger
  tuning rounds (fatigue τ × cap / off-fraction, then init robustness). Finished;
  the operating point is recorded in `CLAUDE.md`.
- **`run_cutforce_sensory_unload.sh`:** unloading-rescue exploration, round 1.
- **`run_consolidate_speed_arm_loading.sh`:** consolidation Stage 4, superseded
  by `run_consolidate_all_modes_production.sh` (Stage 5).
- **`run_speed.sh`:** early speed sweep without the λ axis, superseded by
  `run_speed_stdp.sh`.
- **`run_ablation.sh`:** rat model-component necessity test (5 conditions), not
  a comparison target.
