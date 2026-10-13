#!/bin/bash
# PLAN.md P7 on the architecture-round wiring (2026-10-13), debug-small: per seed, the healthy comfortable source (seed 12345
# reuses results/human_modes/arch2/src), then 10 chains of N sessions: EES (10 Hz cutaneous-like) at BWS 50% / 90%; fixed
# extensor weakness s 0.5 / 0.25 (BWS 50%) +- EES; recovering strength (REC: s_eff follows the captured CUT->RG-E weight,
# w0 = injured-start weight 14.4 pA = 0.25 x healthy, wref = healthy 57.7 pA) +- EES.
#   SEEDS="12345" bash run_p7_arch_local.sh      (resumable; WAVE chains at a time, THREADS threads each)
# Output: seed 12345 -> results/human_modes/arch2/chain/<cond>; other seeds -> results/human_modes/arch2_seeds/s<seed>/chain/<cond>
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
read -r -a SEEDS <<< "${SEEDS:-12345}"
N=${N:-10}; THREADS=${THREADS:-2}; WAVE=${WAVE:-5}; export SIZE=debug THREADS
REC="--strength-recovery-w0 ${REC_W0:-14.4} --strength-recovery-wref ${REC_WREF:-57.7}"
EES="--ees-hz 10 --ees-amp 0 --ees-amp-cut 1.0"
for sd in "${SEEDS[@]}"; do
  if [ "$sd" = 12345 ]; then base=arch2; else base=arch2_seeds/s$sd; fi
  src=results/human_modes/$base/src
  if [ ! -f "$src/comfortable.h5" ] || ! grep -q '^\[HDF5\] saved' "$src/comfortable.log" 2>/dev/null; then
    SEED=$sd SIM_MS=120000 TRAINED=0 TRIGGER=force TAG=$base/src \
      EXTRA="--consolidate-prp-threshold 1 --spinal-eta 0.05" bash run_human_modes.sh comfortable >/dev/null 2>&1
  fi
  i=0
  while read -r name mode fl; do
    ( SEED=$sd SIM_MS=60000 MODE=$mode N=$N SRC=$src TAG=$base/chain/$name TRIGGER=force EXTRA="$fl" bash run_p6_sessions.sh >/dev/null 2>&1 ) &
    i=$((i + 1)); if [ $((i % WAVE)) -eq 0 ]; then wait; fi
  done <<EOF
ees10_bws50 bws50 $EES
ees10_bws90 bws90 $EES
f0.5_noees bws50 --extensor-strength 0.5
f0.5_ees10 bws50 --extensor-strength 0.5 $EES
f0.25_noees bws50 --extensor-strength 0.25
f0.25_ees10 bws50 --extensor-strength 0.25 $EES
r0.5_noees bws50 --extensor-strength 0.5 $REC
r0.5_ees10 bws50 --extensor-strength 0.5 $REC $EES
r0.25_noees bws50 --extensor-strength 0.25 $REC
r0.25_ees10 bws50 --extensor-strength 0.25 $REC $EES
EOF
  wait
done
echo "[p7-arch] done: ${SEEDS[*]}"
