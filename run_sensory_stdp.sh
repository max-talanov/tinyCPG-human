#!/bin/bash -l
#SBATCH --job-name=CPG_SENSORY
#SBATCH --output=Nest_sensory_%A_%a.slurmout
#SBATCH --error=Nest_sensory_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-14
#SBATCH --cpus-per-task=64
#SBATCH --time=10:00:00
#SBATCH --partition=acc
#
# SENSORY-LEARNING arm — frozen descending drive, plastic proprioception.
# Identical matrix to run_speed_stdp.sh (3 speeds × 3 STDP λ, 120 s, paced
# gait) but with the learning relocated from the DESCENDING (brainstem) to
# the SENSORY (muscle-Ia) pathway:
#   --freeze-bs-rg : BS->RG-E/RG-F held static at the weak lognormal init
#                    (no descending plasticity; BS is fixed tonic drive)
#   --stdp-ia-rg   : plastic homonymous Ia->RG (Ia-E->RG-E, Ia-F->RG-F)
#   --wmax-ia 10   : validated sweet spot — a light *phased* sensory boost
#                    reinforces each burst without filling the inter-burst
#                    trough. Higher caps saturate into tonic co-excitation
#                    that destroys counter-phase (see CLAUDE.md sweep).
#
# Pair with run_speed_stdp.sh (the DESCENDING arm, BS->RG plastic) for the
# descending-vs-sensory learning contrast. Both arms share everything else
# (speed grid, λ grid, paced gait, flexor swing-afferent --ia-ext-f-hz 80).
# In debug-small validation the sensory arm matched/beat the descending
# control on counter-phase AND fixed the weak flexor (Force-F peak 11->17).
#
# array_task = 5 * speed_idx + lambda_idx
#   speed_idx 0/1/2 → step_period_ms 1200 / 520 / 350  (6 / 13.5 / 21 cm/s)
#   lambda_idx 0..4 → λ = 1e-6 / 1e-5 / 1e-4 / 1e-3 / 1e-2
#
# Output: results/cpg_sensory_stdp_<spd>_<lam>_idx00_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SWEEP_PAIRS="3.5:0.30"   # operating point — known-good (μ, CV)
SIM_MS=120000            # 120 s long-term run

# Decode array index — 3 speeds x 5 STDP rates = 15 tasks
T=${SLURM_ARRAY_TASK_ID:-0}
SPD_IDX=$(( T / 5 ))
LAM_IDX=$(( T % 5 ))

case $SPD_IDX in
    0) PERIOD=1200; SPD_LABEL="06cms"  ;;   # ≈  6 cm/s
    1) PERIOD=520;  SPD_LABEL="13_5cms" ;;  # ≈ 13.5 cm/s
    2) PERIOD=350;  SPD_LABEL="21cms"  ;;   # ≈ 21 cm/s
    *) echo "Unknown SPD_IDX=$SPD_IDX"; exit 1 ;;
esac

case $LAM_IDX in
    0) LAMBDA=1e-6; LAM_LABEL="lam1em6" ;;
    1) LAMBDA=1e-5; LAM_LABEL="lam1em5" ;;
    2) LAMBDA=1e-4; LAM_LABEL="lam1em4" ;;
    3) LAMBDA=1e-3; LAM_LABEL="lam1em3" ;;
    4) LAMBDA=1e-2; LAM_LABEL="lam1em2" ;;
    *) echo "Unknown LAM_IDX=$LAM_IDX"; exit 1 ;;
esac

TAG="sensory_stdp_${SPD_LABEL}_${LAM_LABEL}"
echo "[Sensory] task=$T period=${PERIOD}ms lambda=$LAMBDA TAG=$TAG (frozen BS + plastic Ia->RG)"

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
    --freeze-bs-rg \
    --stdp-ia-rg \
    --wmax-ia 10 \
    --long-run
