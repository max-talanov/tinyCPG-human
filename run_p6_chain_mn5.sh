#!/bin/bash -l
#SBATCH --job-name=CPG_P6
#SBATCH --output=Nest_p6_%A_%a.slurmout
#SBATCH --error=Nest_p6_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=12:00:00
#SBATCH --partition=gp_bsccs
#SBATCH --array=0-5
#
# PLAN.md Phase 6: session chains at PRODUCTION size (N = 100), 3 seeds, on MN5.
# Two stages, one script (STAGE):
#
#   STAGE=src    array 0..(#SEEDS-1): the healthy source per seed -- a naive comfortable
#                walk, 120 s, force + consolidation at the P5 capture setting
#                (PRP threshold 1), as results/human_modes/p5_seeds/*/comfortable.h5.
#                Output: results/human_modes/$ROOT/src/s<seed>/comfortable.h5
#   STAGE=chain  array 0..(#SEEDS x #MODES - 1), task = seed_index x #MODES + mode_index:
#                N sessions of SESSION_MS each (run_p6_sessions.sh, calibrated capture:
#                species defaults), session 1 = injured start from that seed's source.
#                Output: results/human_modes/$ROOT/chain/s<seed>/<mode>/s<k>/<mode>.h5
#
# The chain must run with the source's seed, size and THREADS (the weight loader checks
# every synapse), so both stages use the same --cpus-per-task. Keep it the same.
#
# Submit from the repo root (the chain waits for all three sources):
#   jid=$(sbatch --parsable --array=0-2 --time=03:00:00 --export=ALL,STAGE=src run_p6_chain_mn5.sh)
#   sbatch --array=0-5 --dependency=afterok:$jid --export=ALL,STAGE=chain run_p6_chain_mn5.sh
# A chain cut by the time limit resumes at the first unfinished session when resubmitted
# with the same command (without the dependency).
#
# Local smoke test (production size, tiny times; plain bash):
#   STAGE=src   SLURM_ARRAY_TASK_ID=0 THREADS=2 SRC_SIM_MS=2000 ROOT=p6_prod_smoke bash run_p6_chain_mn5.sh
#   STAGE=chain SLURM_ARRAY_TASK_ID=0 THREADS=2 SESSION_MS=2000 N=2 ROOT=p6_prod_smoke bash run_p6_chain_mn5.sh
#
# Env: SEEDS ("12345 54321 777"), MODES ("bws50 bws90"), N (15), SESSION_MS (60000),
#      SRC_SIM_MS (120000), ROOT (p6_prod), THREADS (SLURM_CPUS_PER_TASK), EXTRA.
# Figure (per seed):
#   python3 scripts/p6_chain_stages.py results/human_modes/p6_prod/chain/s12345/bws50 \
#       results/human_modes/p6_prod/chain/s12345/bws90 --out plots/p6/prod_s12345_stages.png
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
[ -f "$REPO/cpg_2legs_fast.py" ] || REPO="$(pwd)"   # sbatch copies the script elsewhere

STAGE=${STAGE:?set STAGE=src or STAGE=chain}
read -r -a SEEDS <<< "${SEEDS:-12345 54321 777}"
read -r -a MODES <<< "${MODES:-bws50 bws90}"
N=${N:-15}
SESSION_MS=${SESSION_MS:-60000}
SRC_SIM_MS=${SRC_SIM_MS:-120000}
ROOT=${ROOT:-p6_prod}
T=${SLURM_ARRAY_TASK_ID:-0}
export THREADS=${THREADS:-${SLURM_CPUS_PER_TASK:-4}}
export SIZE=production TRIGGER=force
EXTRA=${EXTRA:-}

python3 -c "import nest, yaml, h5py, numpy" 2>/dev/null \
  || { echo "[p6-mn5] missing python module (need nest, pyyaml, h5py, numpy)" >&2; exit 1; }

case "$STAGE" in
  src)
    SEED=${SEEDS[$T]:?no seed for task $T}
    echo "[p6-mn5] src seed=$SEED threads=$THREADS sim=${SRC_SIM_MS}ms"
    SEED="$SEED" SIM_MS="$SRC_SIM_MS" TRAINED=0 TAG="$ROOT/src/s$SEED" \
      EXTRA="--consolidate-prp-threshold 1 $EXTRA" bash "$REPO/run_human_modes.sh" comfortable
    ;;
  chain)
    SEED=${SEEDS[$(( T / ${#MODES[@]} ))]:?no seed for task $T}
    MODE=${MODES[$(( T % ${#MODES[@]} ))]}
    SRC="$REPO/results/human_modes/$ROOT/src/s$SEED"
    [ -f "$SRC/comfortable.h5" ] || { echo "[p6-mn5] missing source $SRC/comfortable.h5 (run STAGE=src first)" >&2; exit 1; }
    echo "[p6-mn5] chain seed=$SEED mode=$MODE N=$N session=${SESSION_MS}ms threads=$THREADS"
    SEED="$SEED" SIM_MS="$SESSION_MS" MODE="$MODE" N="$N" SRC="$SRC" \
      TAG="$ROOT/chain/s$SEED/$MODE" EXTRA="$EXTRA" bash "$REPO/run_p6_sessions.sh"
    ;;
  *) echo "[p6-mn5] STAGE must be src or chain" >&2; exit 1 ;;
esac
