#!/bin/bash
# PLAN.md P7 step 1 (more seeds), debug-small: per seed, the healthy comfortable source, then the
# recovering-strength chains (--extensor-strength s + --strength-recovery-w0/wref) at BWS 50%, s 0.5 / 0.25, +-10 Hz
# cutaneous-like EES. Chains must use the source's seed and THREADS.
#   SEEDS="54321 777" bash run_p7_seeds_local.sh        (stage src, then chains; resumable)
# Output: results/human_modes/p7_seeds/s<seed>/{src,chain/r<s>_<noees|ees10>}. Summary: scripts/p7_seed_summary.py
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
read -r -a SEEDS <<< "${SEEDS:-54321 777}"
N=${N:-10}; THREADS=${THREADS:-2}; export SIZE=debug THREADS
REC="--strength-recovery-w0 14.1 --strength-recovery-wref 56.5"
EES="--ees-hz 10 --ees-amp 0 --ees-amp-cut 1.0"
for sd in "${SEEDS[@]}"; do   # sources, all seeds in parallel
  d=results/human_modes/p7_seeds/s$sd/src
  [ -f "$d/comfortable.h5" ] && grep -q '^\[HDF5\] saved' "$d/comfortable.log" 2>/dev/null && continue
  ( SEED=$sd SIM_MS=120000 TRAINED=0 TRIGGER=force TAG=p7_seeds/s$sd/src \
      EXTRA="--consolidate-prp-threshold 1 --spinal-eta 0.05" bash run_human_modes.sh comfortable >/dev/null 2>&1 ) &
done
wait
for sd in "${SEEDS[@]}"; do   # chains of one seed at a time (4 runs x 2 threads)
  for s in 0.5 0.25; do for e in noees ees10; do
    fl="--extensor-strength $s $REC"; [ $e = ees10 ] && fl="$fl $EES"
    ( SEED=$sd SIM_MS=60000 MODE=bws50 N=$N SRC=results/human_modes/p7_seeds/s$sd/src \
        TAG=p7_seeds/s$sd/chain/r${s}_$e EXTRA="$fl" bash run_p6_sessions.sh >/dev/null 2>&1 ) &
  done; done
  wait
done
echo "[p7-seeds] done: ${SEEDS[*]}"
