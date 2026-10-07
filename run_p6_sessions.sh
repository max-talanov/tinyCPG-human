#!/bin/bash
# PLAN.md Phase 6: a session chain -- N training sessions of one human mode, each starting
# from the previous session's captured (consolidated) baselines and PRP pools
# (--init-weights-state baseline, MOD_SESSIONS): the uncaptured tag decays during the rest.
# Session 1 starts as run_human_modes.sh starts the mode (e.g. BWS: the trained
# comfortable run x init_scale, an injured start), so SRC must hold that run.
#
#   MODE=bws50 N=5 SIM_MS=60000 SIZE=debug SRC=results/human_modes/inj_base \
#   TAG=p6_chain/bws50 EXTRA="--consolidate-prp-threshold 10" bash run_p6_sessions.sh
#
# Output: results/human_modes/<TAG>/s<k>/<MODE>.h5, k = 1..N.
# Resumable: a session whose log says the HDF5 was saved is skipped (RESUME=0 reruns it),
# so a chain cut by a time limit continues where it stopped when resubmitted.
# Summary: python3 scripts/p6_session_metrics.py results/human_modes/<TAG>/s*/<MODE>.h5
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
MODE=${MODE:?set MODE}
N=${N:-5}
SRC=${SRC:?set SRC (directory with the run session 1 starts from, e.g. comfortable.h5)}
TAG=${TAG:-p6_chain/$MODE}
EXTRA=${EXTRA:-}
RESUME=${RESUME:-1}
export TRIGGER=${TRIGGER:-force}
INITFROM=$(python3 "$REPO/scripts/mode_params.py" "$REPO/config/modes/human.yaml" "$MODE" | tr ' ' '\n' | sed -n 's/^INITFROM=//p')

prev=""
for k in $(seq 1 "$N"); do
  out="$REPO/results/human_modes/$TAG/s$k"
  mkdir -p "$out"
  if [ "$RESUME" = "1" ] && [ -f "$out/$MODE.h5" ] && grep -q '^\[HDF5\] saved' "$out/$MODE.log" 2>/dev/null; then
    echo "[p6-sessions] $MODE session $k done, skipped"
    prev="$out/$MODE.h5"
    continue
  fi
  if [ "$k" -eq 1 ]; then
    # The source run is read from SRC_DIR. It must NOT be linked into the session directory: for a
    # walking mode (INITFROM == MODE) the session writes <MODE>.h5 there, and writing through a link
    # overwrote the source run (2026-10-07).
    TRAINED=1 SRC_DIR="$(cd "$SRC" && pwd)" TAG="$TAG/s$k" EXTRA="$EXTRA" bash "$REPO/run_human_modes.sh" "$MODE"
  else
    TRAINED=0 TAG="$TAG/s$k" \
      EXTRA="$EXTRA --init-weights-from $prev --init-weights-state baseline --init-weights-scale 1" \
      bash "$REPO/run_human_modes.sh" "$MODE"
  fi
  prev="$out/$MODE.h5"
done
echo "[p6-sessions] $MODE: $N sessions in results/human_modes/$TAG"
