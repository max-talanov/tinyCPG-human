#!/bin/bash -l
#SBATCH --job-name=CPG_P7
#SBATCH --output=Nest_p7_%A_%a.slurmout
#SBATCH --error=Nest_p7_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=80
#SBATCH --time=08:00:00
#SBATCH --partition=gp_bsccs
#SBATCH --array=0-2
#
# PLAN.md P7b at PRODUCTION size (N = 100), 3 seeds: training chains of the incomplete-SCI model with
# the extensor weakness (--extensor-strength) and epidural stimulation (EES), against the controls.
#
# One node-sized job per seed (array 0..(#SEEDS-1)); the ten conditions below run side by side in two
# waves of five, THREADS (16) each, no srun steps (NO_SRUN=1; 80 CPUs = 5 x 16).
#
#   condition             mode   extra flags
#   bws50_ees10           bws50  EES
#   bws90_ees10           bws90  EES
#   s0.5_bws50[_ees10]    bws50  --extensor-strength 0.5 [EES]
#   s0.25_bws50[_ees10]   bws50  --extensor-strength 0.25 [EES]
#   s0.5_bws90[_ees10]    bws90  --extensor-strength 0.5 [EES]
#   s0.25_bws90[_ees10]   bws90  --extensor-strength 0.25 [EES]
#   EES = --ees-hz 10 --ees-amp 0 --ees-amp-cut 1.0 (cutaneous-like recruitment, 10 Hz; PLAN.md P7)
# Controls (healthy extensor, no EES) are the P6 spinal production chains already on MN5:
#   results/human_modes/p6_spinal/chain/s<seed>/{bws50,bws90}
#
# The healthy source of every seed is the P6 spinal one (SRC_ROOT/src/s<seed>/comfortable.h5, made with
# 16 threads): the chain must run with the source's seed, size and THREADS (the weight loader checks every
# synapse), so keep THREADS = 16. EES objects are built after the network, so the wiring is the same.
# Output: results/human_modes/$ROOT/chain/s<seed>/<condition>/s<k>/<mode>.h5 (resumable: a resubmitted job
# skips saved sessions; a chain cut by the time limit continues where it stopped).
#
# Submit from the repo root:
#   sbatch run_p7_chain_mn5.sh
#   sbatch --array=0 run_p7_chain_mn5.sh          # one seed only
#
# Local smoke test (production size, tiny times; first make a source with THREADS=2):
#   STAGE=src is run_p6_chain_mn5.sh:  STAGE=src SLURM_ARRAY_TASK_ID=0 THREADS=2 SRC_SIM_MS=2000 ROOT=p7_smoke bash run_p6_chain_mn5.sh
#   SLURM_ARRAY_TASK_ID=0 THREADS=2 SESSION_MS=2000 N=2 SRC_ROOT=p7_smoke ROOT=p7_smoke_out \
#     CONDS="bws50_ees10:bws50:EES s0.5_bws50:bws50:EXT05" bash run_p7_chain_mn5.sh
#
# Env: SEEDS ("12345 54321 777"), N (15), SESSION_MS (60000), SRC_ROOT (p6_spinal), ROOT (p7), THREADS (16),
#      CONDS ("name:mode:flagset ..." with flagset in EES, EXT05, EXT025, or combined with + e.g. EXT05+EES), EXTRA.
# Summary: python3 scripts/p7_chain_compare.py --root results/human_modes/p7/chain/s12345
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
[ -f "$REPO/cpg_2legs_fast.py" ] || REPO="$(pwd)"   # sbatch copies the script elsewhere

read -r -a SEEDS <<< "${SEEDS:-12345 54321 777}"
N=${N:-15}
SESSION_MS=${SESSION_MS:-60000}
SRC_ROOT=${SRC_ROOT:-p6_spinal}
ROOT=${ROOT:-p7}
T=${SLURM_ARRAY_TASK_ID:-0}
export THREADS=${THREADS:-16} NO_SRUN=1 SIZE=production TRIGGER=force
EXTRA=${EXTRA:-}
WAVE=${WAVE:-5}
DEFAULT_CONDS="bws50_ees10:bws50:EES bws90_ees10:bws90:EES \
s0.5_bws50:bws50:EXT05 s0.5_bws50_ees10:bws50:EXT05+EES s0.25_bws50:bws50:EXT025 s0.25_bws50_ees10:bws50:EXT025+EES \
s0.5_bws90:bws90:EXT05 s0.5_bws90_ees10:bws90:EXT05+EES s0.25_bws90:bws90:EXT025 s0.25_bws90_ees10:bws90:EXT025+EES"
read -r -a CONDS <<< "${CONDS:-$DEFAULT_CONDS}"
EES_FLAGS="--ees-hz 10 --ees-amp 0 --ees-amp-cut 1.0"

python3 -c "import nest, yaml, h5py, numpy" 2>/dev/null \
  || { echo "[p7-mn5] missing python module (need nest, pyyaml, h5py, numpy)" >&2; exit 1; }

SEED=${SEEDS[$T]:?no seed for task $T}
SRC="$REPO/results/human_modes/$SRC_ROOT/src/s$SEED"
[ -f "$SRC/comfortable.h5" ] || { echo "[p7-mn5] missing source $SRC/comfortable.h5 (run run_p6_chain_mn5.sh STAGE=src, or upload the P6 sources)" >&2; exit 1; }

flags_of() {  # flagset -> flags
  local out="" part
  IFS='+' read -r -a parts <<< "$1"
  for part in "${parts[@]}"; do
    case "$part" in
      EES) out="$out $EES_FLAGS" ;;
      EXT05) out="$out --extensor-strength 0.5" ;;
      EXT025) out="$out --extensor-strength 0.25" ;;
      NONE) ;;
      *) echo "[p7-mn5] unknown flagset $part" >&2; exit 1 ;;
    esac
  done
  echo "$out"
}

echo "[p7-mn5] seed=$SEED conditions=${#CONDS[@]} waves of $WAVE, threads=$THREADS each, N=$N sessions of ${SESSION_MS} ms"
i=0
for c in "${CONDS[@]}"; do
  IFS=':' read -r name mode fs <<< "$c"
  fl=$(flags_of "$fs")
  echo "[p7-mn5]   $name: mode=$mode flags:$fl"
  SEED="$SEED" SIM_MS="$SESSION_MS" MODE="$mode" N="$N" SRC="$SRC" \
    TAG="$ROOT/chain/s$SEED/$name" EXTRA="$fl $EXTRA" bash "$REPO/run_p6_sessions.sh" &
  i=$((i + 1))
  if [ $((i % WAVE)) -eq 0 ]; then wait; fi
done
wait
echo "[p7-mn5] seed=$SEED done"
