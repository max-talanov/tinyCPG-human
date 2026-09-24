#!/bin/bash -l
#SBATCH --job-name=CPG_CUTF_UNLOAD
#SBATCH --output=Nest_cutf_unload_%A_%a.slurmout
#SBATCH --error=Nest_cutf_unload_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-8
#SBATCH --cpus-per-task=64
#SBATCH --time=12:00:00
#SBATCH --partition=acc
#
# EXPLORATORY -- production-scale test of the unloading-rescue mechanism
# (MOD_IA_RG_LOADING_GAIN), round 1. Not a confirmation -- local debug-scale
# tuning (debug-small, N_IA_E/F=30) never got past corr(Force-E,Force-F)
# ~-0.15 to -0.25 across a wide gain/threshold search (vs. the ~-0.7 to -0.8
# genuine target), while frac_at_cap did settle low (0.00-0.04) at the
# original on=0.80/off=0.35 thresholds -- so the trigger itself isn't
# obviously broken, but debug-scale couldn't show a clean rescue either.
# Suspected cause, not confirmed: N_IA_E/F drops from 100 (production) to 30
# at debug-small (3.3x fewer Ia units, same P_IA2RG_STDP=0.5 density) -- may
# be a hard aggregate-current ceiling on the NEW Ia->RG-E/F pathway that has
# nothing to do with weight/gain tuning and would not hold at full N. This
# mirrors this project's own repeated pattern (see run_cutforce_sweep.sh
# history in CLAUDE.md): debug-scale results are not always predictive of
# production and the only way to know is to actually run production scale.
#
# Prerequisite (must already be on MN5): the two architecture-fix commits on
# feature/ia-rge-direct-pathway -- Ia->RG-E/F now always wired+plastic, and
# WMAX_IA/the peak-force seed both scale with --cut-feedback-gain
# (MOD_IA_RG_LOADING_GAIN). Without these this sweep tests nothing new.
#
# Sensory-learning arm (--freeze-bs-rg): BS frozen, so Ia->RG-E/F is the only
# pathway that CAN compensate for reduced CUT drive (in the descending arm,
# BS->RG would confound the read on whether Ia is doing the rescuing).
# Force-trigger held at the confirmed baseline-loading operating point
# (on=0.80, off=0.35, cap=450ms, fatigue-tau=260ms) -- local sweeps this
# round found retuning on/off-frac does NOT help (widening or narrowing the
# hysteresis band made frac_at_cap worse, not better; 0.80/0.35 was already
# the best of everything tried), so that axis is not swept here.
#
# 3x3 grid: cut-feedback-gain (loading: baseline/toe/air) x ia-feedback-gain
# (compensation strength). Includes gain=1.0 baseline loading as a sanity
# anchor -- should reproduce the already-confirmed round 5/6 numbers exactly
# regardless of ia-feedback-gain, since the loading-dependent cap/seed reduce
# to their unmodified values at cut-feedback-gain=1.0.
#
# array_task = 3 * loading_idx + ia_gain_idx
#   loading_idx 0/1/2 -> cut-feedback-gain 1.0 / 0.5 / 0.1  (baseline/toe/air)
#   ia_gain_idx 0/1/2 -> ia-feedback-gain  1.0 / 4.0 / 8.0
#
# After completion, run scripts/cpg_cutforce_diagnostics.py on every output
# FIRST as always -- frac_at_cap is what decides whether any correlation
# number here means anything, same rule as every round since round 1.
#
# Output: results/cpg_cutfunload_<loading>_ia<gain>_idx0<N>_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SWEEP_PAIRS="3.5:0.30"   # established operating point, not a new init sweep
SIM_MS=120000
PERIOD=520
CAP=450
FAT_ONSET=260
OFFFRAC=0.35

T=${SLURM_ARRAY_TASK_ID:-0}
LOAD_IDX=$(( T / 3 ))
GAIN_IDX=$(( T % 3 ))

case $LOAD_IDX in
    0) CUTGAIN=1.0; LOAD_LABEL="baseline" ;;
    1) CUTGAIN=0.5; LOAD_LABEL="toe"      ;;
    2) CUTGAIN=0.1; LOAD_LABEL="air"      ;;
    *) echo "Unknown LOAD_IDX=$LOAD_IDX"; exit 1 ;;
esac

case $GAIN_IDX in
    0) IAGAIN=1.0; GAIN_LABEL="ia1" ;;
    1) IAGAIN=4.0; GAIN_LABEL="ia4" ;;
    2) IAGAIN=8.0; GAIN_LABEL="ia8" ;;
    *) echo "Unknown GAIN_IDX=$GAIN_IDX"; exit 1 ;;
esac

TAG="cutfunload_${LOAD_LABEL}_${GAIN_LABEL}"
echo "[CutForceUnload] task=$T cut_feedback_gain=$CUTGAIN ia_feedback_gain=$IAGAIN TAG=$TAG (frozen BS, sensory arm)"

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
    --ia-feedback-gain "$IAGAIN" \
    --cut-feedback-gain "$CUTGAIN" \
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
    --stdp-lambda 1e-3 \
    --freeze-bs-rg \
    --long-run
