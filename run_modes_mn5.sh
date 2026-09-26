#!/bin/bash -l
#SBATCH --job-name=CPG_MODES
#SBATCH --output=Nest_modes_%A_%a.slurmout
#SBATCH --error=Nest_modes_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --time=01:00:00
#SBATCH --partition=gp_bsccs
#SBATCH --array=0-9
#
# MN5 check A (PLAN.md): the five locomotion modes at PRODUCTION size (N=100
# per population, BS 60 Hz -- no --debug-small), human and rat reference.
# Same mode definitions and flags as ./run_modes_local.sh (the paper's
# sensory-learning model: paced gait, frozen BS->RG, plastic CUT->RG-E and
# Ia->RG-E/F, Wmax_Ia 10, mu=3.5 / CV=0.30), 120 s, lambda 1e-4.
# Stance fraction and gait scheduler come from the species config:
# human 0.60 with the P3 phase scheduler (double support), rat 0.5 halfcycle.
# Human stride periods are still the rat ones (Phase 5).
#
#   array task  0-4 : human  slow / medium / fast / toe / air
#   array task  5-9 : rat    slow / medium / fast / toe / air
#
#   mode    stride (ms)  Ia/CUT loading
#   slow    1200         1.0
#   medium  520          1.0
#   fast    350          1.0
#   toe     520          0.5
#   air     520          0.1
#
# CPU partition (no GPU is used). Time: one 120 s task needs a few minutes of
# NEST time; 1 h is a wide margin now that the recorder bug is fixed
# (MOD_RECORDER_CLEAR -- bookkeeping used to grow with the square of sim time).
#
# Submit from the repo root:   sbatch run_modes_mn5.sh
# Local smoke test (no SLURM; plain bash, so your usual python3 is used):
#   SLURM_ARRAY_TASK_ID=0 SLURM_CPUS_PER_TASK=4 SIM_MS=2000 bash run_modes_mn5.sh
# Output: results/modes_mn5/<species>/<mode>.h5 (+ .config.yaml)
# Figures: python3 scripts/cpg_modes_stages.py --species human \
#            --indir results/modes_mn5/human --out plots/modes/mn5/human_modes_stages.png

set -euo pipefail
export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

T=${SLURM_ARRAY_TASK_ID:-0}
THREADS=${SLURM_CPUS_PER_TASK:-4}
SIM_MS=${SIM_MS:-120000}
LAMBDA=${LAMBDA:-1e-4}
MODES=(slow medium fast toe air)
SPECIES_LIST=(human rat)

SPECIES=${SPECIES_LIST[$(( T / 5 ))]}
MODE=${MODES[$(( T % 5 ))]}
case "$MODE" in
  slow)   PERIOD=1200; GAIN=1.0 ;;
  medium) PERIOD=520;  GAIN=1.0 ;;
  fast)   PERIOD=350;  GAIN=1.0 ;;
  toe)    PERIOD=520;  GAIN=0.5 ;;
  air)    PERIOD=520;  GAIN=0.1 ;;
esac

# Preflight: fail in seconds, not after queueing, if the environment is incomplete.
python3 -c "import nest, yaml, h5py, numpy" 2>/dev/null \
  || { echo "[modes-mn5] missing python module (need nest, pyyaml, h5py, numpy)" >&2; exit 1; }
python3 species_config.py --check >/dev/null \
  || { echo "[modes-mn5] species config check failed" >&2; python3 species_config.py --check; exit 1; }

OUTDIR="${OUTDIR:-results/modes_mn5/$SPECIES}"
mkdir -p "$OUTDIR"
if command -v srun >/dev/null 2>&1 && [ -n "${SLURM_JOB_ID:-}" ]; then
  LAUNCH=(srun --cpu-bind=cores --distribution=block:block)
else
  LAUNCH=()
fi

echo "[modes-mn5] task=$T species=$SPECIES mode=$MODE period=${PERIOD}ms loading=$GAIN sim=${SIM_MS}ms lambda=$LAMBDA threads=$THREADS"
${LAUNCH[@]+"${LAUNCH[@]}"} python3 -u cpg_2legs_fast.py \
  --species "$SPECIES" \
  --tag "modes_mn5_${SPECIES}_${MODE}" \
  --out "$OUTDIR/$MODE.h5" \
  --seed 12345 \
  --sweep-pairs "3.5:0.30" \
  --sweep-run-idx 0 \
  --sweep-dist lognormal_cv \
  --sim-ms "$SIM_MS" \
  --dt-ms 10 \
  --threads "$THREADS" \
  --nest-verbosity M_ERROR \
  --max-weight-conns 2000 \
  --save-weights snapshots \
  --delay-jitter-ms 0.2 \
  --weight-sample-ms 1000 \
  --rate-update-ms 100 \
  --simulate-chunk-ms 100 \
  --bs-base-hz 6 \
  --bs-noise-std-hz 0.25 \
  --enforce-tonic-bs \
  --paced-gait \
  --step-period-ms "$PERIOD" \
  --n-ia-groups 3 \
  --ia-ext-hz 60 80 100 \
  --ia-ext-f-hz 80 \
  --ia-feedback-gain "$GAIN" \
  --cut-feedback-gain "$GAIN" \
  --stdp-lambda "$LAMBDA" \
  --freeze-bs-rg \
  --wmax-ia 10 \
  --long-run
