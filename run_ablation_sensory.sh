#!/bin/bash -l
#SBATCH --job-name=CPG_ABL_SENS
#SBATCH --output=Nest_ablsens_%A_%a.slurmout
#SBATCH --error=Nest_ablsens_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-14
#SBATCH --cpus-per-task=64
#SBATCH --time=10:00:00
#SBATCH --partition=acc
#
# Phase B (SENSORY-LEARNING) — graded ablation × STDP λ, but with learning
# relocated to the sensory pathway (--freeze-bs-rg --stdp-ia-rg --wmax-ia 10).
# Identical loading grid to run_ablation_graded.sh (the natural arm: both Ia
# and CUT gated by loading), so it is the sensory-learning counterpart of
# that descending-learning experiment.
#
# This is the most pointed test of the sensory-learning hypothesis: the
# plastic Ia->RG projection IS the learning drive, and unloading (toe/air)
# directly attenuates that same proprioceptive input (--ia-feedback-gain).
# So this sweep asks: how does a sensory-trained CPG degrade when the
# sensory input it learns from is progressively removed? (Lavrov/Courtine
# air-stepping ≈ deafferentation of the learning pathway itself.)
#
# array_task = 5 * gain_idx + lambda_idx  (3 loadings x 5 STDP rates = 15 tasks)
#   gain_idx 0/1/2 → Ia,CUT gain 1.0 / 0.5 / 0.1  (baseline / toe / air)
#   lambda_idx 0..4 → λ = 1e-6 / 1e-5 / 1e-4 / 1e-3 / 1e-2
#
# Output: results/cpg_ablsens_<gain>_<lam>_idx00_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SWEEP_PAIRS="3.5:0.30"
SIM_MS=120000            # 120 s — long enough for slow λ=1e-4 to converge
PERIOD=520               # medium walk (≈13.5 cm/s)

T=${SLURM_ARRAY_TASK_ID:-0}
GAIN_IDX=$(( T / 5 ))
LAM_IDX=$(( T % 5 ))

# IA_GAIN drives BOTH the proprioceptive (Ia) and cutaneous (CUT) feedback
# gains, since both scale with limb loading. The external Ia-E heel→toe ramp
# (the epidural-stim pacing) stays at full amplitude regardless.
case $GAIN_IDX in
    0) IA_GAIN=1.0; GAIN_LABEL="baseline" ;;   # full weight-bearing
    1) IA_GAIN=0.5; GAIN_LABEL="toe"      ;;   # toe stepping (partial)
    2) IA_GAIN=0.1; GAIN_LABEL="air"      ;;   # air stepping (no paw contact)
    *) echo "Unknown GAIN_IDX=$GAIN_IDX"; exit 1 ;;
esac

case $LAM_IDX in
    0) LAMBDA=1e-6; LAM_LABEL="lam1em6" ;;
    1) LAMBDA=1e-5; LAM_LABEL="lam1em5" ;;
    2) LAMBDA=1e-4; LAM_LABEL="lam1em4" ;;
    3) LAMBDA=1e-3; LAM_LABEL="lam1em3" ;;
    4) LAMBDA=1e-2; LAM_LABEL="lam1em2" ;;
    *) echo "Unknown LAM_IDX=$LAM_IDX"; exit 1 ;;
esac

TAG="ablsens_${GAIN_LABEL}_${LAM_LABEL}"
echo "[AblSens] task=$T ia_gain=$IA_GAIN lambda=$LAMBDA TAG=$TAG (frozen BS + plastic Ia->RG)"

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
    --cut-feedback-gain "$IA_GAIN" \
    --stdp-lambda "$LAMBDA" \
    --freeze-bs-rg \
    --stdp-ia-rg \
    --wmax-ia 10 \
    --long-run
