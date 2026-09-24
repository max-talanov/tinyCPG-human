#!/bin/bash -l
#SBATCH --job-name=CPG_CUTFORCE
#SBATCH --output=Nest_cutforce_%A_%a.slurmout
#SBATCH --error=Nest_cutforce_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-8
#SBATCH --cpus-per-task=64
#SBATCH --time=03:00:00
#SBATCH --partition=acc
#
# EXPLORATORY sweep for MOD_CUT_FORCE_TRIGGER (--cut-trigger force) at production
# scale (full N, BS=60Hz). NOT a confirmatory run -- local production-scale
# validation (N=100, BS=60Hz, step_period=520ms, sweep-pairs 3.5:0.30) showed the
# debug-tuned defaults (--cut-force-on-frac 0.80/--cut-force-off-frac 0.20,
# --cut-max-stance-ms/--cut-max-swing-ms 600, no fatigue) do NOT transfer cleanly:
# corr(Force-E,Force-F) dropped from debug's -0.97 to ~-0.65/-0.85 (L/R), and
# bout-duration analysis showed the OFF transition (stance->swing) was almost
# entirely --cut-max-stance-ms failsafe-driven, not genuine force decay -- RG-E
# has no INaP-style self-terminating burst mechanism (only RG-F got the
# intrinsically-bursting Izhikevich treatment), so force saturates and sits flat
# until the timeout fires. Added --muscle-fatigue (activity-dependent force
# attenuation, see cpg_2legs_fast.py MOD_MUSCLE_FATIGUE) to make OFF genuinely
# force-driven, but its time constant interacts with --cut-max-stance-ms in ways
# that didn't converge from a few local trials (some combinations chattered in
# 200-400ms bursts, others left a leg reduced-but-still-"on" indefinitely).
#
# This sweep explores that 2D interaction directly on MN5 (9 tasks in parallel,
# vs. one-at-a-time local iteration) so the right combination can be picked from
# actual results instead of more manual guessing:
#   fatigue_onset_idx 0/1/2 -> --fatigue-tau-onset-ms 200 / 400 / 600
#   cap_idx           0/1/2 -> --cut-max-stance-ms = --cut-max-swing-ms 500 / 800 / 1100
# --fatigue-tau-recovery-ms fixed at 600ms, --fatigue-max-frac fixed at 0.95 (chosen
# so the fatigued force floor sits well below any reasonable OFF threshold -- see
# --fatigue-max-frac help for the arithmetic and the 0.85 failure mode it fixes).
# --leading-leg R, --lead-offset-ms 150 (also the symmetric CUT->RG-E STDP priming
# window -- see MOD_CUT_FORCE_TRIGGER comments in cpg_2legs_fast.py) held fixed;
# both were validated locally at debug scale and are not the axis under test here.
#
# 60 s per run: long enough for STDP to converge (~7s at lambda=1e-3) and for
# dozens of gait cycles' worth of correlation statistics, short enough for 9
# tasks to turn around quickly as a first-pass filter before any longer
# confirmatory run.
#
# array_task = 3 * fatigue_onset_idx + cap_idx
#
# After completion, for each output check (in order of importance):
#   1. corr(Force-E, Force-F) per leg, and corr(Force-E_L, Force-E_R) -- want both
#      strongly negative (< -0.85 target, matching debug), not near 0 or positive
#      (positive = legs synchronised, a real failure mode seen locally at
#      --lead-offset-ms 400).
#   2. Stance-bout-duration variability (not logged directly -- reconstruct from
#      leg_L/force_e, leg_R/force_e in the output HDF5, e.g. threshold-crossing
#      analysis like the diagnostic snippets in this session). Uniform bout
#      durations sitting exactly at the --cut-max-stance-ms value indicate the
#      failsafe is still doing all the work rather than genuine force-threshold
#      crossings; want the majority of transitions to occur before the cap fires.
#
# Output: results/cpg_cutforce_fat<ONSET>_cap<CAP>_idx00_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SWEEP_PAIRS="3.5:0.30"   # established production operating point (run_speed_stdp.sh etc.)
SIM_MS=60000             # first-pass filter length; re-run winner(s) at 120s to confirm
PERIOD=520               # medium walk (~13.5 cm/s) -- NOTE: in --cut-trigger force mode
                          # this only shapes Ia-E heel->toe sub-group timing within a
                          # detected stance bout; it does NOT set the gait cycle length
                          # the way it does in timer mode (that's now emergent, governed
                          # by the force threshold + failsafe caps under test here).

T=${SLURM_ARRAY_TASK_ID:-0}
FAT_IDX=$(( T / 3 ))
CAP_IDX=$(( T % 3 ))

case $FAT_IDX in
    0) FAT_ONSET=200; FAT_LABEL="fat200" ;;
    1) FAT_ONSET=400; FAT_LABEL="fat400" ;;
    2) FAT_ONSET=600; FAT_LABEL="fat600" ;;
    *) echo "Unknown FAT_IDX=$FAT_IDX"; exit 1 ;;
esac

case $CAP_IDX in
    0) CAP=500;  CAP_LABEL="cap500"  ;;
    1) CAP=800;  CAP_LABEL="cap800"  ;;
    2) CAP=1100; CAP_LABEL="cap1100" ;;
    *) echo "Unknown CAP_IDX=$CAP_IDX"; exit 1 ;;
esac

TAG="cutforce_${FAT_LABEL}_${CAP_LABEL}"
echo "[CutForceSweep] task=$T fatigue_onset=${FAT_ONSET}ms cap=${CAP}ms TAG=$TAG"

srun --cpu-bind=cores --distribution=block:block \
  python3 -u cpg_2legs_fast.py \
    --tag "$TAG" \
    --out cpg_run.h5 \
    --outdir "$OUTDIR" \
    --seed "$BASE_SEED" \
    --sweep-pairs "$SWEEP_PAIRS" \
    --sweep-run-idx 0 \
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
    --cut-force-off-frac 0.20 \
    --cut-max-stance-ms "$CAP" \
    --cut-max-swing-ms "$CAP" \
    --muscle-fatigue \
    --fatigue-tau-onset-ms "$FAT_ONSET" \
    --fatigue-tau-recovery-ms 600 \
    --fatigue-max-frac 0.95 \
    --long-run
