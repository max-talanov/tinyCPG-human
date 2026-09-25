#!/bin/bash -l
#SBATCH --job-name=CPG_ABL_GRAD
#SBATCH --output=Nest_ablgrad_%A_%a.slurmout
#SBATCH --error=Nest_ablgrad_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-8
#SBATCH --cpus-per-task=64
#SBATCH --time=10:00:00
#SBATCH --partition=acc
#
# Phase B — graded sensory ablation × STDP learning rate matrix.
# 3 Ia-feedback gains (Courtine/Lavrov SCI rehab paradigm)
#   × 3 STDP learning rates λ
# = 9 tasks, 120 s each, paced gait at medium-walk speed (520 ms).
#
# Sim length raised from 30 s to 120 s so the slow λ=1e-4 condition
# (~75 s to converge) reaches steady state — a fair comparison across the
# wider decade-spanning λ range that matches Phase A.
#
# array_task = 3 * gain_idx + lambda_idx
#
#   gain_idx 0 → Ia gain = 1.0  (baseline, full weight-bearing)
#   gain_idx 1 → Ia gain = 0.5  (toe stepping; partial weight)
#                              Edgerton 2008; Cha 2007
#   gain_idx 2 → Ia gain = 0.1  (air stepping; lifted hindlimb, ≈deafferented)
#                              Lavrov 2008; Hägglund 2013
#
#   lambda_idx 0 → λ = 1e-5 (very slow STDP; τ ≈ 250 s, climbs throughout)
#   lambda_idx 1 → λ = 1e-4 (slow STDP; converges ~75 s)
#   lambda_idx 2 → λ = 1e-3 (baseline; converges ~7 s)
# λ shifted down one decade to match Phase A (run_speed_stdp.sh): the
# fast 1e-2 only fluctuated around its plateau, so it was dropped for 1e-5.
#
# Output: results/cpg_ablgrad_g<G>_lam<L>_idx00_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SWEEP_PAIRS="3.5:0.30"
SIM_MS=120000            # 120 s — long enough for slow λ=1e-4 to converge
PERIOD=520               # medium walk (≈13.5 cm/s) — Lavrov's typical condition

T=${SLURM_ARRAY_TASK_ID:-0}
GAIN_IDX=$(( T / 3 ))
LAM_IDX=$(( T % 3 ))

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
    0) LAMBDA=1e-5; LAM_LABEL="lam1em5" ;;
    1) LAMBDA=1e-4; LAM_LABEL="lam1em4" ;;
    2) LAMBDA=1e-3; LAM_LABEL="lam1em3" ;;
    *) echo "Unknown LAM_IDX=$LAM_IDX"; exit 1 ;;
esac

TAG="ablgrad_${GAIN_LABEL}_${LAM_LABEL}"
echo "[AblGrad] task=$T ia_gain=$IA_GAIN lambda=$LAMBDA TAG=$TAG"

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
    --long-run
