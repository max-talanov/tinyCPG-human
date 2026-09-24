#!/bin/bash
# debug_force.sh — local fast-iteration run with MOD_CUT_FORCE_TRIGGER.
# Same config as debug.sh, but CUT (cutaneous/paw-contact) firing is triggered by
# each leg's own extensor force_e crossing an adaptive peak-fraction threshold
# ("foot touches down" / "foot lifts off") instead of the fixed gait-cycle clock.
# --leading-leg breaks initial L/R symmetry (one leg starts already planted, as in
# real gait initiation); --cut-max-stance-ms/--cut-max-swing-ms are the endogenous-
# timer failsafe that prevents a leg from locking permanently in one phase (the
# CUT->RG-E->force_e loop has no fatigue term, so a pure force threshold can plateau
# forever without it).
#
# Output goes to results/debug_force.h5.
#
# After running, plot with:
#   python3 scripts/cpg_plot_from_hdf5.py --in results/debug_force.h5 --save-prefix debug_force

set -e

mkdir -p results

# Number of local threads — adjust for your machine
THREADS=${THREADS:-4}

python3 -u cpg_2legs_fast.py \
    --debug-small \
    --paced-gait \
    --cut-trigger force \
    --leading-leg R \
    --lead-offset-ms 150 \
    --cut-force-on-frac 0.80 \
    --cut-force-off-frac 0.20 \
    --cut-max-stance-ms 600 \
    --cut-max-swing-ms 600 \
    --step-period-ms 1000 \
    --stance-fraction 0.5 \
    --n-ia-groups 3 \
    --ia-ext-hz 60 80 100 \
    --ia-ext-f-hz 80 \
    --out results/debug_force.h5 \
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
echo "  python3 scripts/cpg_plot_from_hdf5.py --in results/debug_force.h5 --save-prefix debug_force"
echo "=========================================="
