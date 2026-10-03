#!/bin/bash -l
#SBATCH --job-name=CPG_MODES6
#SBATCH --output=Nest_modes6_%A_%a.slurmout
#SBATCH --error=Nest_modes6_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=80
#SBATCH --time=02:00:00
#SBATCH --partition=gp_bsccs
#SBATCH --array=0-2
#
# PLAN.md P5/P6: the five human locomotion modes at PRODUCTION size (N = 100), 3 seeds,
# with spinal plasticity (MOD_SPINAL_INDUCTION, human default; no STDP) and trained
# starts. Confirms the fast-walk stride fix (2026-10-03) across seeds.
#
#   STAGE=seed   (default; packed, 3 jobs -- fits the account's job-submit limit)
#                array 0..(#SEEDS-1), one node-sized job per seed: the 3 walk sources run
#                side by side, then the 5 modes side by side, THREADS (16) each, no srun
#                steps (NO_SRUN=1). --cpus-per-task 80 = 5 x 16.
#   or the same work as one array task per run (24 jobs; needs a larger submit limit):
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
# every synapse), so both stages use the same thread count (THREADS).
#
# Submit from the repo root, packed (3 jobs):
#   sbatch run_p6_modes_mn5.sh
# Unpacked (24 jobs; the modes wait for all nine sources):
#   jid=$(sbatch --parsable --array=0-8 --cpus-per-task=16 --export=ALL,STAGE=src run_p6_modes_mn5.sh)
#   sbatch --array=0-14 --cpus-per-task=16 --dependency=afterok:$jid --export=ALL,STAGE=modes run_p6_modes_mn5.sh
#
# Local smoke test (production size, tiny times; plain bash):
#   SLURM_ARRAY_TASK_ID=0 THREADS=2 SIM_MS=2000 ROOT=p6_modes_smoke bash run_p6_modes_mn5.sh
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

STAGE=${STAGE:-seed}
read -r -a SEEDS <<< "${SEEDS:-12345 54321 777}"
WALKS=(slow comfortable fast)
MODES=($(python3 -c "import yaml; print(' '.join(yaml.safe_load(open('$REPO/config/modes/human.yaml'))['modes']))"))
ROOT=${ROOT:-p6_modes}
T=${SLURM_ARRAY_TASK_ID:-0}
if [ "$STAGE" = "seed" ]; then
  export THREADS=${THREADS:-16} NO_SRUN=1
else
  export THREADS=${THREADS:-${SLURM_CPUS_PER_TASK:-4}}
fi
export SIZE=production TRIGGER=force SIM_MS=${SIM_MS:-120000}
EXTRA=${EXTRA:-}

python3 -c "import nest, yaml, h5py, numpy" 2>/dev/null \
  || { echo "[modes-mn5] missing python module (need nest, pyyaml, h5py, numpy)" >&2; exit 1; }

case "$STAGE" in
  seed)
    SEED=${SEEDS[$T]:?no seed for task $T}
    SRC="$REPO/results/human_modes/$ROOT/src/s$SEED"
    echo "[modes-mn5] seed=$SEED: ${#WALKS[@]} sources then ${#MODES[@]} modes in parallel, threads=$THREADS each"
    for WALK in "${WALKS[@]}"; do
      SEED="$SEED" TRAINED=0 TAG="$ROOT/src/s$SEED" \
        EXTRA="--consolidate-prp-threshold 1 --spinal-eta 0.05 $EXTRA" bash "$REPO/run_human_modes.sh" "$WALK" &
    done
    wait
    for WALK in "${WALKS[@]}"; do
      grep -q '^\[HDF5\] saved' "$SRC/$WALK.log" 2>/dev/null \
        || { echo "[modes-mn5] source $SRC/$WALK failed (see $SRC/$WALK.log)" >&2; exit 1; }
    done
    for MODE in "${MODES[@]}"; do
      SEED="$SEED" TRAINED=1 SRC_DIR="$SRC" TAG="$ROOT/modes/s$SEED" EXTRA="$EXTRA" \
        bash "$REPO/run_human_modes.sh" "$MODE" &
    done
    wait
    OUT="$REPO/results/human_modes/$ROOT/modes/s$SEED"
    fail=0
    for MODE in "${MODES[@]}"; do
      grep -q '^\[HDF5\] saved' "$OUT/$MODE.log" 2>/dev/null || { echo "[modes-mn5] $OUT/$MODE failed" >&2; fail=1; }
    done
    exit $fail
    ;;
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
  *) echo "[modes-mn5] STAGE must be seed, src or modes" >&2; exit 1 ;;
esac
