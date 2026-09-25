#!/bin/bash -l
#SBATCH --job-name=CPG_FROZEN
#SBATCH --output=Nest_frozen_%A_%a.slurmout
#SBATCH --error=Nest_frozen_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-9
#SBATCH --cpus-per-task=64
#SBATCH --time=03:00:00
#SBATCH --partition=acc
#
# Frozen-weight control — does the descending-weight DISTRIBUTION (mean +
# spread), held fixed with plasticity OFF, reproduce the clean plastic
# rhythm at FULL WEIGHT-BEARING?  All runs at baseline loading
# (Ia gain = 1.0), STDP frozen (--stdp-lambda 0), 30 s, 520 ms paced.
# Inherits the bio-plausible defaults (static-weight-cv 0.5, cut-static-w 0).
#
# Reference: the plastic natural arm at baseline loading (2026-07-01) reaches
# corr(F_E,F_F) -0.90 (lambda 1e-3) / -0.95 (lambda 1e-5), with the converged
# CUT->RGE marginal distribution at mean ~63 pA, std ~3 pA (CV ~0.05).
# Question: does imposing THAT marginal distribution by hand, frozen, recover
# the clean baseline rhythm, or does the plastic rhythm depend on finer
# learning-induced weight structure a matched random draw does not capture?
#
# We freeze a lognormal CUT->RGE distribution of prescribed (mean, CV) and
# scale BS->RGE to 0.25× the CUT mean (the observed ratio). Two sweeps:
#
#   MEAN sweep (weakness; CV fixed 0.02, the "tight" / degraded spread):
#     idx 0  mean=15   idx 1  mean=25   idx 2  mean=35
#     idx 3  mean=45   idx 4  mean=55   idx 5  mean=63
#     prediction: low mean → clean (-0.9+), high mean → degraded (-0.7)
#
#   CV sweep (heterogeneity; mean fixed 63, the "full" strength):
#     idx 6  CV=0.04   idx 7  CV=0.06   idx 8  CV=0.08   idx 9  CV=0.10
#     (idx 5 above, mean=63 CV=0.02, is the tight anchor for this sweep)
#     prediction: low CV → degraded, high CV → clean
#
# Output: results/cpg_frozen_m<MEAN>_cv<CV3>_baseline_seed12345.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SIM_MS=30000             # frozen weights — no convergence transient needed
PERIOD=520               # medium walk anchor (matches Phase B)
IA_GAIN=1.0              # baseline / full weight-bearing (the clean rhythm to reproduce)
BS_MEAN_MUL=0.25         # BS->RGE mean = 0.25 × CUT->RGE mean (observed ratio)

T=${SLURM_ARRAY_TASK_ID:-0}
case $T in
    0) MEAN=15; CV=0.02 ;;
    1) MEAN=25; CV=0.02 ;;
    2) MEAN=35; CV=0.02 ;;
    3) MEAN=45; CV=0.02 ;;
    4) MEAN=55; CV=0.02 ;;
    5) MEAN=63; CV=0.02 ;;
    6) MEAN=63; CV=0.04 ;;
    7) MEAN=63; CV=0.06 ;;
    8) MEAN=63; CV=0.08 ;;
    9) MEAN=63; CV=0.10 ;;
    *) echo "Unknown array task $T"; exit 1 ;;
esac

# CV3 = CV × 1000, zero-padded to 3 digits (0.02 → 020) for the filename
CV3=$(printf "%03d" "$(echo "$CV * 1000 / 1" | bc)")
TAG="frozen_m${MEAN}_cv${CV3}_baseline"
OUT="${OUTDIR}cpg_${TAG}_seed${BASE_SEED}.h5"
echo "[Frozen] task=$T mean=$MEAN CV=$CV BSmean=$(echo "$MEAN*$BS_MEAN_MUL"|bc) -> $OUT"

srun --cpu-bind=cores --distribution=block:block \
  python3 -u cpg_2legs_fast.py \
    --out "$OUT" \
    --seed "$BASE_SEED" \
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
    --stdp-lambda 0 \
    --stdp-winit-dist lognormal_cv \
    --stdp-winit-mean "$MEAN" \
    --stdp-winit-std "$CV" \
    --stdp-winit-bs-mean-mul "$BS_MEAN_MUL" \
    --stdp-winit-bs-std-mul 1.0
