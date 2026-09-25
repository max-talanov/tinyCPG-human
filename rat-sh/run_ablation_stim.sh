#!/bin/bash -l
#SBATCH --job-name=CPG_ABL_STIM
#SBATCH --output=Nest_ablstim_%A_%a.slurmout
#SBATCH --error=Nest_ablstim_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-8
#SBATCH --cpus-per-task=64
#SBATCH --time=10:00:00
#SBATCH --partition=acc
#
# Phase B — STIM-ASSISTED arm of the epidural-stimulation contrast.
# Identical to run_ablation_graded.sh EXCEPT the cutaneous (CUT) drive is
# held at FULL amplitude regardless of loading: only the proprioceptive Ia
# feedback is attenuated. CUT is the computational analogue of epidural
# electrical stimulation (loading-independent rhythmic drive; Lavrov 2008,
# Courtine 2009, Harkema 2011).
#
# Pair with run_ablation_graded.sh (the NATURAL arm, where CUT is also gated
# by loading) for the epidural-stim rescue contrast. Both use the flexor
# swing-afferent (--ia-ext-f-hz 80), so the only difference between the two
# arms is whether the cutaneous drive collapses with unloading.
#
# array_task = 3 * gain_idx + lambda_idx
#   gain_idx 0/1/2 → Ia gain 1.0 / 0.5 / 0.1  (baseline / toe / air)
#   lambda_idx 0/1/2 → λ = 1e-5 / 1e-4 / 1e-3
#
# Output: results/cpg_ablstim_<gain>_<lam>_idx00_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SWEEP_PAIRS="3.5:0.30"
SIM_MS=120000
PERIOD=520

T=${SLURM_ARRAY_TASK_ID:-0}
GAIN_IDX=$(( T / 3 ))
LAM_IDX=$(( T % 3 ))

# Only Ia is gated by loading here; CUT stays at full (the stim drive).
case $GAIN_IDX in
    0) IA_GAIN=1.0; GAIN_LABEL="baseline" ;;
    1) IA_GAIN=0.5; GAIN_LABEL="toe"      ;;
    2) IA_GAIN=0.1; GAIN_LABEL="air"      ;;
    *) echo "Unknown GAIN_IDX=$GAIN_IDX"; exit 1 ;;
esac

case $LAM_IDX in
    0) LAMBDA=1e-5; LAM_LABEL="lam1em5" ;;
    1) LAMBDA=1e-4; LAM_LABEL="lam1em4" ;;
    2) LAMBDA=1e-3; LAM_LABEL="lam1em3" ;;
    *) echo "Unknown LAM_IDX=$LAM_IDX"; exit 1 ;;
esac

TAG="ablstim_${GAIN_LABEL}_${LAM_LABEL}"
echo "[AblStim] task=$T ia_gain=$IA_GAIN (CUT=1.0, stim) lambda=$LAMBDA TAG=$TAG"

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
    --ia-feedback-gain "$IA_GAIN" \
    --stdp-lambda "$LAMBDA" \
    --long-run
