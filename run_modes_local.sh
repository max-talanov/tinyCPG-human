#!/bin/bash
# run_modes_local.sh — the five canonical locomotion modes, locally (debug-small).
#
# Same mode definitions and flags as the paper's sensory-learning model
# (run_sensory_stdp.sh for the three speeds, run_ablation_sensory.sh for the
# two unloading modes): paced gait, frozen BS->RG, plastic CUT->RG-E and
# Ia->RG-E/F (Wmax_Ia 10), sweep point mu=3.5 / CV=0.30 -- but at --debug-small
# (small N, BS 20 Hz) so it runs on a workstation. Production-scale runs stay
# on MN5.
#
#   mode    stride (ms)  Ia/CUT loading   stands for
#   slow    1200         1.0              slow walk   (~6 cm/s in rat)
#   medium  520          1.0              medium / plantar stepping (~13.5 cm/s)
#   fast    350          1.0              fast walk   (~21 cm/s)
#   toe     520          0.5              toe stepping (partial unloading)
#   air     520          0.1              air stepping (no paw contact)
#
# Stance fraction and scheduler come from the species config: rat 0.5 with the
# halfcycle scheduler (as in the paper); human 0.60 with the P3 phase scheduler
# (double support). NOTE (human): stride periods are still the rat ones --
# human strides per mode are Phase 5.
#
# Usage:  ./run_modes_local.sh [species] [sim_ms] [lambda] [modes...]
#   e.g.  ./run_modes_local.sh human 120000 1e-4
#         ./run_modes_local.sh rat 30000 1e-3 medium air
# Output: results/modes/<species>/<mode>.h5 (+ .config.yaml, .log)
# Plot:   python3 scripts/cpg_modes_stages.py --species <species>

set -euo pipefail

SPECIES="${1:-human}"
SIM_MS="${2:-120000}"
LAMBDA="${3:-1e-4}"
shift $(( $# < 3 ? $# : 3 ))
MODES=("$@")
[ ${#MODES[@]} -eq 0 ] && MODES=(slow medium fast toe air)
THREADS="${THREADS:-4}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTDIR="$REPO/results/modes/$SPECIES"
mkdir -p "$OUTDIR"

for MODE in "${MODES[@]}"; do
  case "$MODE" in
    slow)   PERIOD=1200; GAIN=1.0 ;;
    medium) PERIOD=520;  GAIN=1.0 ;;
    fast)   PERIOD=350;  GAIN=1.0 ;;
    toe)    PERIOD=520;  GAIN=0.5 ;;
    air)    PERIOD=520;  GAIN=0.1 ;;
    *) echo "unknown mode: $MODE" >&2; exit 2 ;;
  esac
  echo "[modes] species=$SPECIES mode=$MODE period=${PERIOD}ms loading=$GAIN sim=${SIM_MS}ms lambda=$LAMBDA"
  start=$(date +%s)
  python3 -u "$REPO/cpg_2legs_fast.py" \
    --species "$SPECIES" \
    --debug-small \
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
    --long-run \
    > "$OUTDIR/$MODE.log" 2>&1
  echo "[modes]   done in $(( $(date +%s) - start )) s -> $OUTDIR/$MODE.h5"
done
