#!/bin/bash
# debug.sh — local fast-iteration run of the CPG model.
# Uses --debug-small (small N + BS=20 Hz) for ~30 s wall clock.
# Output goes to results/debug.h5.
#
# After running, plot with:
#   python3 scripts/cpg_plot_from_hdf5.py --in results/debug.h5 --save-prefix debug

set -e

mkdir -p results

# Number of local threads — adjust for your machine
THREADS=${THREADS:-4}

python3 -u cpg_2legs_fast.py \
    --debug-small \
    --paced-gait \
    --step-period-ms 1000 \
    --stance-fraction 0.5 \
    --n-ia-groups 3 \
    --ia-ext-hz 60 80 100 \
    --ia-ext-f-hz 80 \
    --out results/debug.h5 \
    --sim-ms 10000 \
    --dt-ms 10 \
    --threads "$THREADS" \
    --sweep-pairs "22:0.30" \
    --sweep-run-idx 0 \
    --sweep-dist lognormal_cv \
    --seed 12345 \
    --nest-verbosity M_WARNING \
    --max-weight-conns 1000 \
    --save-weights snapshots \
    --delay-model length_velocity \
    --species rat \
    --delay-jitter-ms 0.2 \
    --weight-sample-ms 500 \
    --rate-update-ms 50 \
    --simulate-chunk-ms 50 \
    --bs-base-hz 6 \
    --bs-noise-std-hz 0.25 \
    --enforce-tonic-bs

echo ""
echo "=========================================="
echo "Done. To plot:"
echo "  python3 scripts/cpg_plot_from_hdf5.py --in results/debug.h5 --save-prefix debug"
echo "=========================================="
