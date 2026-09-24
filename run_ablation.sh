#!/bin/bash -l
#SBATCH --job-name=CPG_ABLATE
#SBATCH --output=Nest_ablate_%A_%a.slurmout
#SBATCH --error=Nest_ablate_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-4
#SBATCH --cpus-per-task=64
#SBATCH --time=03:00:00
#SBATCH --partition=acc
#
# Ablation array — 5 conditions × 1 fixed (mu, CV) = idx04 (μ=3.5, CV=0.30)
# Single 30-s paced-gait run per condition. Shows necessity of each MOD component.
#
# array_task → condition:
#   0  baseline       : all features ON (control)
#   1  noIa           : --ablate-ia-loop                  (no Ia → InE/InF feedback)
#   2  symInh         : --ablate-asym                     (W_INF2RGE = W_INE2RGF = -28)
#   3  noComm         : --ablate-comm                     (W_COMM_*_INH = 0)
#   4  noPaced        : (no --paced-gait flag)            (legacy rotating CUT)
#
# Output: results/cpg_ablate_<tag>_idx04_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SWEEP_PAIRS="3.5:0.30"   # single (mu, CV) pair — known-good config
SIM_MS=30000

# Common args
COMMON_ARGS=(
    --out cpg_run.h5
    --outdir "$OUTDIR"
    --seed "$BASE_SEED"
    --sweep-pairs "$SWEEP_PAIRS"
    --sweep-run-idx 0
    --sweep-dist lognormal_cv
    --sim-ms "$SIM_MS"
    --dt-ms 10
    --threads "$SLURM_CPUS_PER_TASK"
    --nest-verbosity M_ERROR
    --max-weight-conns 2000
    --save-weights snapshots
    --delay-model length_velocity
    --species rat
    --delay-jitter-ms 0.2
    --weight-sample-ms 1000
    --rate-update-ms 100
    --simulate-chunk-ms 100
    --bs-base-hz 6
    --bs-noise-std-hz 0.25
    --enforce-tonic-bs
    --step-period-ms 1000
    --stance-fraction 0.5
    --n-ia-groups 3
    --ia-ext-hz 60 80 100
    --long-run
)

case ${SLURM_ARRAY_TASK_ID:-0} in
    0) TAG="ablate_baseline";   EXTRA=(--paced-gait) ;;
    1) TAG="ablate_noIa";       EXTRA=(--paced-gait --ablate-ia-loop) ;;
    2) TAG="ablate_symInh";     EXTRA=(--paced-gait --ablate-asym) ;;
    3) TAG="ablate_noComm";     EXTRA=(--paced-gait --ablate-comm) ;;
    4) TAG="ablate_noPaced";    EXTRA=() ;;   # no --paced-gait → legacy CUT rotation
    *) echo "Unknown array task ${SLURM_ARRAY_TASK_ID}"; exit 1 ;;
esac

echo "[Ablate] task=$SLURM_ARRAY_TASK_ID TAG=$TAG EXTRA=${EXTRA[*]}"

srun --cpu-bind=cores --distribution=block:block \
  python3 -u cpg_2legs_fast.py \
    --tag "$TAG" \
    "${COMMON_ARGS[@]}" \
    "${EXTRA[@]}"
