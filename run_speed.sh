#!/bin/bash -l
#SBATCH --job-name=CPG_SPEED
#SBATCH --output=Nest_speed_%A_%a.slurmout
#SBATCH --error=Nest_speed_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-4
#SBATCH --cpus-per-task=64
#SBATCH --time=03:00:00
#SBATCH --partition=acc
#
# Speed sweep — vary --step-period-ms across rat locomotor range.
# Bio range (Bellardita & Kiehn 2015): walk 600-800ms, trot 400-700ms.
# We probe 600/800/1000/1200/1400ms at idx04 (μ=3.5, CV=0.30).
#
# array_task → step_period_ms:
#   0  600 ms   (fast trot — high end of rat trot speed)
#   1  800 ms   (trot)
#   2  1000 ms  (slow trot / our calibration baseline)
#   3  1200 ms  (slow walk)
#   4  1400 ms  (very slow walk — bio limit)
#
# Output: results/cpg_speed_period<P>ms_idx04_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SWEEP_PAIRS="3.5:0.30"
SIM_MS=30000

case ${SLURM_ARRAY_TASK_ID:-0} in
    0) PERIOD=600  ;;
    1) PERIOD=800  ;;
    2) PERIOD=1000 ;;
    3) PERIOD=1200 ;;
    4) PERIOD=1400 ;;
    *) echo "Unknown array task ${SLURM_ARRAY_TASK_ID}"; exit 1 ;;
esac

TAG="speed_period${PERIOD}ms"
echo "[Speed] task=$SLURM_ARRAY_TASK_ID PERIOD=${PERIOD}ms TAG=$TAG"

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
    --long-run
