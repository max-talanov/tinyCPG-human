#!/bin/bash -l
#SBATCH --job-name=CPG_MODES6
#SBATCH --output=Nest_modes6_%A_%a.slurmout
#SBATCH --error=Nest_modes6_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
#SBATCH --partition=gp_bsccs
#SBATCH --array=0-14
#
# PLAN.md P5/P6: the five human locomotion modes at PRODUCTION size (N = 100), 3 seeds,
# with spinal plasticity (MOD_SPINAL_INDUCTION, human default; no STDP) and trained
# starts. Confirms the fast-walk stride fix (2026-10-03) across seeds. Two stages:
#
#   STAGE=src    array 0..(#SEEDS x 3 - 1): per seed, the trained sources -- naive slow,
#                comfortable and fast walks, 120 s, --spinal-eta 0.05 and PRP threshold 1
#                (reach the trained state within the run, as run_p6_chain_mn5.sh STAGE=src).
#                task = seed_index x 3 + walk_index (slow, comfortable, fast).
#                Output: results/human_modes/$ROOT/src/s<seed>/<walk>.h5
#   STAGE=modes  array 0..(#SEEDS x 5 - 1): per seed, the five modes from trained starts
#                (walks from themselves, BWS 50%/90% injured from comfortable), species
#                defaults (eta 0.003, PRP threshold 10). task = seed_index x 5 + mode_index
#                (config/modes/human.yaml order: slow, comfortable, fast, bws50, bws90).
#                Output: results/human_modes/$ROOT/modes/s<seed>/<mode>.h5
#
# A trained start must match the source's seed, size and THREADS (the weight loader checks
# every synapse), so both stages use the same --cpus-per-task.
#
# Submit from the repo root (the modes wait for all nine sources):
#   jid=$(sbatch --parsable --array=0-8 --export=ALL,STAGE=src run_p6_modes_mn5.sh)
#   sbatch --array=0-14 --dependency=afterok:$jid --export=ALL,STAGE=modes run_p6_modes_mn5.sh
#
# Local smoke test (production size, tiny times; plain bash):
#   STAGE=src   SLURM_ARRAY_TASK_ID=2 THREADS=2 SIM_MS=2000 ROOT=p6_modes_smoke bash run_p6_modes_mn5.sh
#   STAGE=modes SLURM_ARRAY_TASK_ID=2 THREADS=2 SIM_MS=2000 ROOT=p6_modes_smoke bash run_p6_modes_mn5.sh
#
# Env: SEEDS ("12345 54321 777"), SIM_MS (120000), ROOT (p6_modes), THREADS
#      (SLURM_CPUS_PER_TASK), EXTRA.
# Summary and figures:
#   python3 scripts/p5_seed_summary.py --modes-config config/modes/human.yaml --from-ms 60000 \
#       results/human_modes/p6_modes/modes/s*
#   python3 scripts/cpg_modes_stages.py --modes-config config/modes/human.yaml \
#       --indir results/human_modes/p6_modes/modes/s12345 --out plots/modes/p6_prod/s12345_human_modes_stages.png
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
[ -f "$REPO/cpg_2legs_fast.py" ] || REPO="$(pwd)"   # sbatch copies the script elsewhere

STAGE=${STAGE:?set STAGE=src or STAGE=modes}
read -r -a SEEDS <<< "${SEEDS:-12345 54321 777}"
WALKS=(slow comfortable fast)
MODES=($(python3 -c "import yaml; print(' '.join(yaml.safe_load(open('$REPO/config/modes/human.yaml'))['modes']))"))
ROOT=${ROOT:-p6_modes}
T=${SLURM_ARRAY_TASK_ID:-0}
export THREADS=${THREADS:-${SLURM_CPUS_PER_TASK:-4}}
export SIZE=production TRIGGER=force SIM_MS=${SIM_MS:-120000}
EXTRA=${EXTRA:-}

python3 -c "import nest, yaml, h5py, numpy" 2>/dev/null \
  || { echo "[modes-mn5] missing python module (need nest, pyyaml, h5py, numpy)" >&2; exit 1; }

case "$STAGE" in
  src)
    SEED=${SEEDS[$(( T / 3 ))]:?no seed for task $T}
    WALK=${WALKS[$(( T % 3 ))]}
    echo "[modes-mn5] src seed=$SEED walk=$WALK threads=$THREADS sim=${SIM_MS}ms"
    SEED="$SEED" TRAINED=0 TAG="$ROOT/src/s$SEED" \
      EXTRA="--consolidate-prp-threshold 1 --spinal-eta 0.05 $EXTRA" bash "$REPO/run_human_modes.sh" "$WALK"
    ;;
  modes)
    SEED=${SEEDS[$(( T / ${#MODES[@]} ))]:?no seed for task $T}
    MODE=${MODES[$(( T % ${#MODES[@]} ))]}
    SRC="$REPO/results/human_modes/$ROOT/src/s$SEED"
    echo "[modes-mn5] modes seed=$SEED mode=$MODE threads=$THREADS sim=${SIM_MS}ms"
    SEED="$SEED" TRAINED=1 SRC_DIR="$SRC" TAG="$ROOT/modes/s$SEED" EXTRA="$EXTRA" \
      bash "$REPO/run_human_modes.sh" "$MODE"
    ;;
  *) echo "[modes-mn5] STAGE must be src or modes" >&2; exit 1 ;;
esac
