#!/bin/bash -l
#SBATCH --job-name=CPG_P3B
#SBATCH --output=Nest_p3b_%A_%a.slurmout
#SBATCH --error=Nest_p3b_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --time=02:00:00
#SBATCH --partition=gp_bsccs
#SBATCH --array=0-8
#
# PLAN.md Phase 3b size sweep, the part too large for a laptop: human medium
# under --conn-rule indegree at 3x and 10x the production population sizes,
# plus the 1x reference on the same machine. Same model and flags as
# ./run_p3b_local.sh (which this calls), 120 s, seeds 1-3.
#
#   array task  0-2 : n_scale 1   seeds 1 2 3
#   array task  3-5 : n_scale 3   seeds 1 2 3
#   array task  6-8 : n_scale 10  seeds 1 2 3
#
# Submit from the repo root:   sbatch run_p3b_mn5.sh
# Output: results/p3b/indegree_n<scale>_s<seed>.h5 (+ .log, .config.yaml)
# Summary (after copying back, together with the local runs):
#   python3 scripts/p3b_size_invariance.py results/p3b/*.h5
# The .log files hold the [Timing] line (NEST vs Python bookkeeping), the first
# data point for MN5 check B.
set -euo pipefail
export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

T=${SLURM_ARRAY_TASK_ID:-0}
SCALES=(1 3 10)
SCALE=${SCALES[$(( T / 3 ))]}
SEED=$(( T % 3 + 1 ))

python3 -c "import nest, yaml, h5py, numpy" 2>/dev/null \
  || { echo "[p3b-mn5] missing python module (need nest, pyyaml, h5py, numpy)" >&2; exit 1; }
python3 species_config.py --check >/dev/null \
  || { echo "[p3b-mn5] species config check failed" >&2; python3 species_config.py --check; exit 1; }

THREADS=${SLURM_CPUS_PER_TASK:-4} ./run_p3b_local.sh indegree "$SCALE" "$SEED" "${SIM_MS:-120000}"
