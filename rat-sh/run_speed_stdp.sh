#!/bin/bash -l
#SBATCH --job-name=CPG_SPDxSTDP
#SBATCH --output=Nest_spdxstdp_%A_%a.slurmout
#SBATCH --error=Nest_spdxstdp_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-8
#SBATCH --cpus-per-task=64
#SBATCH --time=10:00:00
#SBATCH --partition=acc
#
# Phase A — speed × STDP learning rate matrix.
# 3 walking speeds (Courtine/Lavrov rat treadmill, step length ≈ 7 cm)
#   × 3 STDP learning rates λ (bio-plausible cortical range)
# = 9 tasks, 120 s each, paced gait.
#
# array_task = 3 * speed_idx + lambda_idx
#
#   speed_idx 0 → step_period_ms=1200,  ≈  6 cm/s (slow walk)    Lavrov 2008 low
#   speed_idx 1 → step_period_ms= 520,  ≈ 13.5 cm/s (med walk)   Courtine 2009 mid
#   speed_idx 2 → step_period_ms= 350,  ≈ 21 cm/s (fast walk)    Courtine 2009 high
#
#   lambda_idx 0 → λ = 1e-5 (very slow STDP; τ ≈ 250 s, so the weight
#                            climbs steadily without plateauing in 120 s —
#                            shows continuous "progress")
#   lambda_idx 1 → λ = 1e-4 (slow STDP; converges ~75 s)
#   lambda_idx 2 → λ = 1e-3 (baseline; Morrison 2007; converges ~7 s)
# Range shifted down one decade from the earlier {1e-4,1e-3,1e-2}: the
# fast 1e-2 merely fluctuated around its plateau (large per-update steps,
# no visible convergence), so it was dropped in favour of 1e-5, which
# exposes the slow-learning transient across the whole run.
#
# Output: results/cpg_speed_stdp_spd<P>_lam<L>_idx00_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SWEEP_PAIRS="3.5:0.30"   # operating point — known-good (μ, CV)
SIM_MS=120000            # 120 s long-term run

# Decode array index
T=${SLURM_ARRAY_TASK_ID:-0}
SPD_IDX=$(( T / 3 ))
LAM_IDX=$(( T % 3 ))

case $SPD_IDX in
    0) PERIOD=1200; SPD_LABEL="06cms"  ;;   # ≈  6 cm/s
    1) PERIOD=520;  SPD_LABEL="13_5cms" ;;  # ≈ 13.5 cm/s
    2) PERIOD=350;  SPD_LABEL="21cms"  ;;   # ≈ 21 cm/s
    *) echo "Unknown SPD_IDX=$SPD_IDX"; exit 1 ;;
esac

case $LAM_IDX in
    0) LAMBDA=1e-5; LAM_LABEL="lam1em5" ;;
    1) LAMBDA=1e-4; LAM_LABEL="lam1em4" ;;
    2) LAMBDA=1e-3; LAM_LABEL="lam1em3" ;;
    *) echo "Unknown LAM_IDX=$LAM_IDX"; exit 1 ;;
esac

TAG="speed_stdp_${SPD_LABEL}_${LAM_LABEL}"
echo "[SpdxStdp] task=$T period=${PERIOD}ms lambda=$LAMBDA TAG=$TAG"

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
    --stdp-lambda "$LAMBDA" \
    --long-run
