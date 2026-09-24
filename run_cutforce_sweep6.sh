#!/bin/bash -l
#SBATCH --job-name=CPG_CUTFORCE6
#SBATCH --output=Nest_cutforce6_%A_%a.slurmout
#SBATCH --error=Nest_cutforce6_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-9
#SBATCH --cpus-per-task=64
#SBATCH --time=12:00:00
#SBATCH --partition=acc
#
# TIME BUDGET (calibrated from a real timeout, not guessed): the first
# submission of this script used --time=03:00:00 and every one of the 10
# tasks was CANCELLED DUE TO TIME LIMIT at the exact same point -- chunk
# 800/1200, i.e. 80s of the 120s sim (66.7%), never reaching the final HDF5
# write (results/2026-09-03: 10 slurmout/slurmerr pairs, zero .h5 files).
# 180min for 66.7% of the run extrapolates linearly to ~270min (4.5h) for the
# full 120s under THAT run's load -- this mode's per-chunk bookkeeping
# (force-threshold gate + muscle-fatigue update every rate-update tick) makes
# it measurably slower per simulated second than the timer-based paced-gait
# path. A flat 06:00:00 (~33% margin over 4.5h) was tried next but is still
# only sized for that one observed load level, and MN5 load varies run to
# run -- a slower shared node or heavier cluster contention could still burn
# through it. --time=12:00:00 instead matches run.sh's own precedent (same
# partition, its 120s/10-task runs already budget 12h despite reportedly
# finishing in ~2h -- see paper Sec 3.9), which has proven itself against
# that load variance in practice. Do not drop this below 12:00:00.
#
# PHASE 3 -- seed/initial-weight ROBUSTNESS check for MOD_CUT_FORCE_TRIGGER.
# Not a parameter search (that's done -- see rounds 1-5 below); this holds the
# force-trigger config fixed and varies the STDP initial-weight distribution
# instead.
#
# Rounds 1-5 (run_cutforce_sweep.sh .. run_cutforce_sweep5.sh) found and then
# confirmed a genuinely closed-loop (non-cap-dominated) operating point:
#   --fatigue-tau-onset-ms 260, --cut-force-off-frac 0.35, --cut-max-stance-ms/
#   --cut-max-swing-ms 450 (all held fixed here) -- results/2026-09-01, exact
#   cut_on ground truth, frac_at_cap=0.00 on both legs across the whole
#   {240,250,260}ms x {0.35,0.375,0.40} neighborhood, corr(Force-E,Force-F)
#   -0.63(L)/-0.67(R), corr(Force-E_L,Force-E_R) -0.71 at the best point.
#
# EVERY round so far tested only ONE STDP initial-weight point: sweep-pairs
# 3.5:0.30 (mu=3.5, CV=0.30). This round asks whether the mechanism holds up
# away from that point, using the SAME 10-point (mu, CV) diagnostic grid the
# base (timer-based) model already uses for its own robustness claim (paper
# Algorithm 1 / run.sh) -- not inventing a new methodology, reusing the
# project's established one so the two are directly comparable:
#   0:0, 0.5:0.8, 1.0:0.6, 2.0:0.45, 3.5:0.30, 5.0:0.20, 7.0:0.15, 9.0:0.10,
#   12.0:0.08, 16.0:0.05
# array_task 0-9 selects --sweep-run-idx directly into that list (same mapping
# as run.sh). mu=0 and mu=16 are the real stress tests -- near-zero and much
# stronger initial CUT/BS weight than the 3.5 every prior round used.
#
# 120s sim (matching Algorithm 1's own duration, not the 60s first-pass filter
# used in rounds 1-5) -- this is a confirmatory step, not exploration, so it
# should carry the same statistical weight as the base model's own robustness
# claim: more gait cycles per run, cleaner frac_at_cap and correlation
# estimates. All non-varying flags identical to round 5's winning config.
#
# After completion, run the diagnostic on every output FIRST, same as every
# round since round 1 -- frac_at_cap is still the number that decides whether
# a result means anything:
#   python3 scripts/cpg_cutforce_diagnostics.py results/<dated>/cpg_cutforce6_*.h5
# Read across all 10: frac_at_cap should stay low and corr(Force-E_L,Force-E_R)
# strongly negative at EVERY point, not just mu=3.5 -- if it only holds near
# mu=3.5, that's a real finding (initialization-sensitivity), not a pass.
#
# Output: results/cpg_cutforce6_mu<MU>_cv<CV>_idx0<N>_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
TAG="cutforce6_robustness"
BASE_SEED=12345
# Same 10-point (mu, CV) diagnostic grid as run.sh / paper Algorithm 1 --
# reusing the established methodology, not a new one.
SWEEP_PAIRS="0:0,0.5:0.8,1.0:0.6,2.0:0.45,3.5:0.30,5.0:0.20,7.0:0.15,9.0:0.10,12.0:0.08,16.0:0.05"
SIM_MS=120000            # matches Algorithm 1's duration -- confirmatory, not a first-pass filter
PERIOD=520               # medium walk (~13.5 cm/s) -- shapes Ia-E sub-group timing only in this mode
CAP=450                  # round 5's confirmed value
FAT_ONSET=260             # round 5's best point
OFFFRAC=0.35              # round 5's best point

echo "[CutForceSweep6] task=${SLURM_ARRAY_TASK_ID} sweep_pairs_idx=${SLURM_ARRAY_TASK_ID} fatigue_onset=${FAT_ONSET}ms off_frac=$OFFFRAC cap=${CAP}ms(fixed) TAG=$TAG"

srun --cpu-bind=cores --distribution=block:block \
  python3 -u cpg_2legs_fast.py \
    --tag "$TAG" \
    --out cpg_run.h5 \
    --outdir "$OUTDIR" \
    --seed "$BASE_SEED" \
    --sweep-pairs "$SWEEP_PAIRS" \
    --sweep-run-idx ${SLURM_ARRAY_TASK_ID} \
    --sweep-dist lognormal_cv \
    --sim-ms "$SIM_MS" \
    --dt-ms 10 \
    --threads "$SLURM_CPUS_PER_TASK" \
    --nest-verbosity M_ERROR \
    --max-weight-conns 2000 \
    --save-weights snapshots \
    --delay-model length_velocity \
    --species rat \
    --delay-jitter-ms 0.2 \
    --weight-sample-ms 1000 \
    --rate-update-ms 100 \
    --simulate-chunk-ms 100 \
    --bs-base-hz 6 \
    --bs-noise-std-hz 0.25 \
    --enforce-tonic-bs \
    --paced-gait \
    --step-period-ms "$PERIOD" \
    --stance-fraction 0.5 \
    --n-ia-groups 3 \
    --ia-ext-hz 60 80 100 \
    --ia-ext-f-hz 80 \
    --cut-trigger force \
    --leading-leg R \
    --lead-offset-ms 150 \
    --cut-force-on-frac 0.80 \
    --cut-force-off-frac "$OFFFRAC" \
    --cut-max-stance-ms "$CAP" \
    --cut-max-swing-ms "$CAP" \
    --muscle-fatigue \
    --fatigue-tau-onset-ms "$FAT_ONSET" \
    --fatigue-tau-recovery-ms 600 \
    --fatigue-max-frac 0.95 \
    --long-run
