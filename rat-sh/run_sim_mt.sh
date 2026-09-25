#!/bin/bash
set -e
THREADS=${THREADS:-12}
SWEEP_RUN_IDX=${SWEEP_RUN_IDX:-0}

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

export OMP_NUM_THREADS=$THREADS

echo "[NEST Run] Running with $THREADS OpenMP threads | Sweep Task ID: $SWEEP_RUN_IDX"

python3 - <<'PY'
import nest
ks = nest.GetKernelStatus()
thr = ks.get("local_num_threads", ks.get("num_threads", ks.get("threads", 1)))
print("nest", nest.__version__, "local_threads", thr)
PY

SWEEP_PAIRS="0:0,0.5:0.8,1.0:0.6,2.0:0.45,3.5:0.30,5.0:0.20,7.0:0.15,9.0:0.10,12.0:0.08,16.0:0.05"
OUTDIR="results/"
TAG="bursting_paced_120s"
BASE_SEED=12345

mkdir -p "$OUTDIR"

python3 -u cpg_2legs_fast.py \
  --out cpg_run.h5 \
  --outdir "$OUTDIR" \
  --tag "$TAG" \
  --seed $BASE_SEED \
  --sweep-pairs "$SWEEP_PAIRS" \
  --sweep-run-idx $SWEEP_RUN_IDX \
  --sweep-dist lognormal_cv \
  --sim-ms 120000 \
  --dt-ms 10 \
  --threads $THREADS \
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
  --step-period-ms 520 \
  --stance-fraction 0.5 \
  --n-ia-groups 3 \
  --ia-ext-hz 60 80 100 \
  --ia-ext-f-hz 80 \
  --long-run