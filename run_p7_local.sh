#!/bin/bash
# PLAN.md Phase 7a/7b at debug-small (SIZE=production for MN5-size runs; same stages).
#
#   STAGE=src    healthy sources: naive 120 s walks (slow, comfortable, fast), spinal rule, eta 0.05,
#                PRP threshold 1, as run_p6_chain_mn5.sh STAGE=src
#   STAGE=7a     the five modes from trained starts, intact descending drive (the reference)
#   STAGE=7b     one-session scan of the injury: extensor weakness (--extensor-strength s, $STRENGTHS) x
#                loading (walker / support level L = both feedback gains, $LOADS), trained start;
#                read with scripts/p7_wl_grid.py --root results/human_modes/p7/7b
#
#   bash run_p7_local.sh src && bash run_p7_local.sh 7a && bash run_p7_local.sh 7b
#   extra flags (e.g. EES): EXTRA="--ees-hz 30 --ees-amp 0.5 --ees-amp-ib 0.5 --ees-amp-cut 0.5"
# Output: results/human_modes/p7/{src,7a,7b/...}. Summaries: scripts/cpg_gait_phase_metrics.py,
#   scripts/p7_ees_summary.py.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
STAGE=${1:?stage: src | 7a | 7b}
SIZE=${SIZE:-debug}; SEED=${SEED:-12345}; THREADS=${THREADS:-2}; JOBS=${JOBS:-4}
SRC=$PWD/results/human_modes/p7/src
STRENGTHS=${STRENGTHS:-"1.0 0.75 0.5 0.25 0.1"}; LOADS=${LOADS:-"1.0 0.75 0.5 0.25 0.1"}
EXTRA=${EXTRA:-}
run() { # tag, extra flags, modes...
  local tag=$1 ex=$2; shift 2
  for m in "$@"; do
    ( SIZE=$SIZE TRIGGER=force SEED=$SEED THREADS=$THREADS SRC_DIR=$SRC TAG=$tag EXTRA="$ex" "${RUNENV[@]}" \
        bash run_human_modes.sh "$m" >/dev/null 2>&1 ) &
    while [ "$(jobs -r | wc -l)" -ge "$JOBS" ]; do wait -n; done
  done
}
case $STAGE in
  src) RUNENV=(env TRAINED=0 SIM_MS=120000)
       run p7/src "--consolidate-prp-threshold 1 --spinal-eta 0.05 $EXTRA" slow comfortable fast ;;
  7a)  RUNENV=(env TRAINED=1 SIM_MS=${SIM_MS:-60000})
       run p7/7a "$EXTRA" slow comfortable fast bws50 bws90 ;;
  7b)  RUNENV=(env TRAINED=1 SIM_MS=${SIM_MS:-60000})
       for w in $STRENGTHS; do for l in $LOADS; do
         run "p7/7b/w${w}_l$l" "--init-weights-scale 1 --extensor-strength $w --ia-feedback-gain $l --cut-feedback-gain $l $EXTRA" bws50
       done; done ;;
  *) echo "stage must be src, 7a or 7b" >&2; exit 1 ;;
esac
wait
echo "[p7] stage $STAGE done"
