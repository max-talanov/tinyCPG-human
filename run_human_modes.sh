#!/bin/bash -l
#SBATCH --job-name=CPG_HUMAN
#SBATCH --output=Nest_human_%A_%a.slurmout
#SBATCH --error=Nest_human_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --time=02:00:00
#SBATCH --partition=gp_bsccs
#SBATCH --array=0-4
#
# PLAN.md Phase 5: the five human locomotion modes from config/modes/human.yaml
# (slow / comfortable / fast walk, BWS 50% / 90%), human model (species config
# defaults: fixed in-degree wiring, Ia/Ib split, ankle coupling, soleus/TA tau),
# sensory-learning arm (frozen BS->RG, Wmax_Ia 10, mu=3.5 / CV=0.30).
#
#   TRIGGER=paced  timer-paced phase scheduler at the mode's stride and stance
#                  fraction (default)
#   TRIGGER=force  force-triggered stance/swing with the mode's `force:` timing
#                  (+ tag-and-capture consolidation unless CONSOLIDATE=0)
#   SIZE=production (N=100; default) | debug (--debug-small)
#   TAG            output subfolder name (default: $TRIGGER)
#   TRAINED=1 (default): modes with `init_from: <mode>` (BWS) start from that mode's
#                  end-of-run weights, $OUTDIR/<mode>.h5, which must exist (run it first,
#                  same SIZE/SEED/THREADS). TRAINED=0: naive start for every mode.
#   TICK           gate/rate-update tick and simulate chunk (ms); default the mode's
#                  tick_ms, else 50 (P5 round 11). Below 100 the
#                  --long-run preset (which forces >= 100 ms) is replaced by its other
#                  settings, given explicitly.
#   SRC_DIR        directory of the init_from runs (default: the output directory)
#   SIM_MS, SEED, EXTRA (extra model flags, appended last)
# Plasticity: the species default (human: spinal induction + consolidation, P6), not STDP.
#
# MN5:    sbatch run_human_modes.sh            (array 0-4 = modes in file order)
#         BWS needs comfortable first: jid=$(sbatch --parsable --array=0-2 run_human_modes.sh)
#                                      sbatch --array=3-4 --dependency=afterok:$jid run_human_modes.sh
# Local (plain bash, so your usual python3 is used; the -l login shell may not see NEST):
#         THREADS=4 bash run_human_modes.sh comfortable fast
#         THREADS=4 bash run_human_modes.sh     (all five, one after another)
# Output: results/human_modes/<TAG>/<mode>.h5 (+ .log, .config.yaml)
# Figure: python3 scripts/cpg_modes_stages.py --modes-config config/modes/human.yaml \
#           --indir results/human_modes/<TAG> --out plots/modes/<TAG>/human_modes_stages.png
set -euo pipefail
export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
[ -f "$REPO/cpg_2legs_fast.py" ] || REPO="$(pwd)"   # sbatch copies the script elsewhere
MODES_CFG="$REPO/config/modes/human.yaml"
TRIGGER=${TRIGGER:-paced}
SIZE=${SIZE:-production}
TAG=${TAG:-$TRIGGER}
SIM_MS=${SIM_MS:-120000}
SEED=${SEED:-12345}
CONSOLIDATE=${CONSOLIDATE:-1}
TRAINED=${TRAINED:-1}
SRC_DIR=${SRC_DIR:-}   # where init_from runs live (default: the output directory)
TICK_ENV=${TICK:-}   # explicit TICK overrides the mode's tick_ms (default 50)
THREADS=${THREADS:-${SLURM_CPUS_PER_TASK:-4}}
EXTRA=${EXTRA:-}

python3 -c "import nest, yaml, h5py, numpy" 2>/dev/null \
  || { echo "[human-modes] missing python module (need nest, pyyaml, h5py, numpy)" >&2; exit 1; }

ALL_MODES=($(python3 -c "import yaml; print(' '.join(yaml.safe_load(open('$MODES_CFG'))['modes']))"))
if [ $# -gt 0 ]; then
  MODES=("$@")
elif [ -n "${SLURM_ARRAY_TASK_ID:-}" ]; then
  MODES=("${ALL_MODES[${SLURM_ARRAY_TASK_ID}]}")
else
  MODES=("${ALL_MODES[@]}")
fi

OUTDIR="$REPO/results/human_modes/$TAG"
mkdir -p "$OUTDIR"
if command -v srun >/dev/null 2>&1 && [ -n "${SLURM_JOB_ID:-}" ]; then
  LAUNCH=(srun --cpu-bind=cores --distribution=block:block)
else
  LAUNCH=()
fi

for MODE in "${MODES[@]}"; do
  # mode parameters as shell assignments, straight from the YAML
  eval "$(python3 "$REPO/scripts/mode_params.py" "$MODES_CFG" "$MODE")"
  TRIG_FLAGS=(--cut-trigger timer --no-consolidate --no-muscle-fatigue)
  if [ "$TRIGGER" = "force" ]; then
    TRIG_FLAGS=(--cut-trigger force --leading-leg R --lead-offset-ms "$LEAD"
                --cut-force-on-frac "$ON" --cut-force-off-frac "$OFF"
                --cut-max-stance-ms "$CAP" --cut-max-swing-ms "$CAP"
                --muscle-fatigue --fatigue-tau-onset-ms "$FON" --fatigue-tau-recovery-ms "$FREC"
                --fatigue-max-frac 0.95
                --swing-end-f-frac "$SWF" --swing-afferent-tau-ms "$SWTAU"
                --leg-fatigue-asym-frac "$ASYM")
    if [ "$CONSOLIDATE" = "1" ]; then
      TRIG_FLAGS+=(--consolidate --consolidate-prp-gain-genuine 0.25 --consolidate-prp-gain-forced 0.10
                   --consolidate-tau-tag-ms "$TAUTAG")
    else
      TRIG_FLAGS+=(--no-consolidate)
    fi
  fi
  SIZE_FLAGS=()
  [ "$SIZE" = "debug" ] && SIZE_FLAGS=(--debug-small)
  TICK=${TICK_ENV:-${TICKM:-50}}
  if [ "$TICK" -lt 100 ]; then
    TICK_FLAGS=(--print-every 200)
  else
    TICK_FLAGS=(--long-run)
  fi
  INIT_FLAGS=()
  if [ -n "$INITFROM" ] && [ "$TRAINED" = "1" ]; then
    SRC="${SRC_DIR:-$OUTDIR}/$INITFROM.h5"
    [ -f "$SRC" ] || { echo "[human-modes] $MODE starts trained from $SRC: run $INITFROM first (or TRAINED=0)" >&2; exit 1; }
    INIT_FLAGS=(--init-weights-from "$SRC" --init-weights-scale "$INITSCALE")
    echo "[human-modes]   trained start: weights from $INITFROM x$INITSCALE"
  fi
  echo "[human-modes] mode=$MODE trigger=$TRIGGER size=$SIZE tick=${TICK}ms stride=${STRIDE}ms stance=$STANCE loading=$GAIN sim=${SIM_MS}ms seed=$SEED -> $OUTDIR/$MODE.h5"
  start=$(date +%s)
  # shellcheck disable=SC2086
  ${LAUNCH[@]+"${LAUNCH[@]}"} python3 -u "$REPO/cpg_2legs_fast.py" \
    --species human \
    --tag "human_${TAG}_${MODE}" \
    --out "$OUTDIR/$MODE.h5" \
    --seed "$SEED" \
    --sweep-pairs "3.5:0.30" \
    --sweep-run-idx 0 \
    --sweep-dist lognormal_cv \
    --sim-ms "$SIM_MS" \
    --dt-ms 10 \
    --threads "$THREADS" \
    --nest-verbosity M_ERROR \
    --max-weight-conns 2000 \
    --save-weights snapshots \
    --weight-sample-ms 1000 \
    --rate-update-ms "$TICK" \
    --simulate-chunk-ms "$TICK" \
    --bs-base-hz 6 \
    --bs-noise-std-hz 0.25 \
    --enforce-tonic-bs \
    --paced-gait \
    --step-period-ms "$STRIDE" \
    --stance-fraction "$STANCE" \
    --n-ia-groups 3 \
    --ia-ext-hz 60 80 100 \
    --ia-ext-f-hz 80 \
    --ia-feedback-gain "$GAIN" \
    --cut-feedback-gain "$GAIN" \
    --freeze-bs-rg \
    --wmax-ia 10 \
    "${TICK_FLAGS[@]}" \
    "${SIZE_FLAGS[@]+"${SIZE_FLAGS[@]}"}" \
    "${TRIG_FLAGS[@]}" \
    "${INIT_FLAGS[@]+"${INIT_FLAGS[@]}"}" \
    $EXTRA \
    > "$OUTDIR/$MODE.log" 2>&1
  echo "[human-modes]   done in $(( $(date +%s) - start )) s"
done
