#!/bin/bash
# PLAN.md Phase 3b: size-invariance checks, human medium (stride 520 ms, full
# loading), the same sensory-learning model and flags as run_modes_mn5.sh (MN5
# check A), but at a chosen wiring rule and population scale:
#
#   ./run_p3b_local.sh <conn_rule> <n_scale> <seed> [sim_ms]
#
#   conn_rule  bernoulli | indegree   (human default: indegree)
#   n_scale    population sizes = production (N=100) x n_scale; 1 = production
#   seed       run seed (also the NEST rng_seed)
#   sim_ms     default 120000
#
# Switch check:  bernoulli vs indegree at n_scale 1, seeds 1 2 3.
# Size sweep:    indegree at n_scale 0.3 / 1 (local) and 3 (MN5, check B).
# Output: results/p3b/<conn_rule>_n<n_scale>_s<seed>.h5 (+ .log, .config.yaml)
# Summary: python3 scripts/p3b_size_invariance.py results/p3b/*.h5
set -euo pipefail

RULE="${1:?conn_rule: bernoulli|indegree}"
SCALE="${2:?n_scale}"
SEED="${3:?seed}"
SIM_MS="${4:-120000}"
THREADS="${THREADS:-4}"
EXTRA=${EXTRA:-}

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTDIR="${OUTDIR:-$REPO/results/p3b}"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/${RULE}_n${SCALE}_s${SEED}.h5"

echo "[p3b] rule=$RULE n_scale=$SCALE seed=$SEED sim=${SIM_MS}ms threads=$THREADS -> $OUT"
start=$(date +%s)
# shellcheck disable=SC2086
python3 -u "$REPO/cpg_2legs_fast.py" \
  --species human \
  --conn-rule "$RULE" \
  --n-scale "$SCALE" \
  --out "$OUT" \
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
  --delay-jitter-ms 0.2 \
  --weight-sample-ms 1000 \
  --rate-update-ms 100 \
  --simulate-chunk-ms 100 \
  --bs-base-hz 6 \
  --bs-noise-std-hz 0.25 \
  --enforce-tonic-bs \
  --paced-gait \
  --step-period-ms 520 \
  --n-ia-groups 3 \
  --ia-ext-hz 60 80 100 \
  --ia-ext-f-hz 80 \
  --ia-feedback-gain 1.0 \
  --cut-feedback-gain 1.0 \
  --stdp-lambda 1e-4 \
  --freeze-bs-rg \
  --wmax-ia 10 \
  --long-run \
  $EXTRA \
  > "${OUT%.h5}.log" 2>&1
echo "[p3b]   done in $(( $(date +%s) - start )) s"
