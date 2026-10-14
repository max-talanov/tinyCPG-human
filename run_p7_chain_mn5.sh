#!/bin/bash -l
#SBATCH --job-name=CPG_P7
#SBATCH --output=Nest_p7_%A_%a.slurmout
#SBATCH --error=Nest_p7_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=80
#SBATCH --time=12:00:00
#SBATCH --partition=gp_bsccs
#SBATCH --array=0-2
#
# PLAN.md P7b at PRODUCTION size (N = 100), 3 seeds, on the ARCHITECTURE-ROUND wiring (2026-10-13: homonymous
# Ia->MN, swing afferent folded into Ia-F, no CUT->InE; config/species/human.yaml): training chains of the
# incomplete-SCI model with the extensor weakness (--extensor-strength), strength recovery with the captured
# CUT->RG-E weight (REC) and epidural stimulation (EES), against the plain BWS controls.
#
# One node-sized job per seed (array 0..(#SEEDS-1)); the 20 conditions below run side by side in four
# waves of five, THREADS (16) each, no srun steps (NO_SRUN=1; 80 CPUs = 5 x 16).
#
#   condition             mode   extra flags
#   bws50, bws90          bws    (controls: plain BWS, healthy extensor, no EES)
#   bws50_ees10           bws50  EES
#   bws90_ees10           bws90  EES
#   s0.5_bws50[_ees10]    bws50  --extensor-strength 0.5 [EES]
#   s0.25_bws50[_ees10]   bws50  --extensor-strength 0.25 [EES]
#   s0.5_bws90[_ees10]    bws90  --extensor-strength 0.5 [EES]
#   s0.25_bws90[_ees10]   bws90  --extensor-strength 0.25 [EES]
#   r0.5_bws50[_ees10]    bws50  --extensor-strength 0.5 + REC [EES]   (also r0.25_*, *_bws90)
#   REC = --strength-recovery-w0/-wref: s_eff rises from s to 1 as the captured CUT->RG-E weight goes from the
#         injured-start value w0 (= wref x the mode's init_scale) to the healthy trained value wref; both are read
#         from the seed's healthy source here (production values, not the debug-small ones).
#   EES = --ees-hz 10 --ees-amp 0 --ees-amp-cut 1.0 (cutaneous-like recruitment, 10 Hz; PLAN.md P7)
# The old P6/P7 production chains are on the pre-architecture wiring and are NOT valid controls; the plain BWS
# chains above are rerun here.
#
# A chain needs its seed's healthy source, the trained comfortable walk the injured start is made from
# (SRC_ROOT/src/s<seed>/comfortable.h5). If it is not there, the job builds it first (naive comfortable walk,
# 120 s, --spinal-eta 0.05, PRP threshold 1; ~9 min at 16 threads). A source whose h5 does not carry the new
# wiring (cut_to_ine False, swing_afferent_as_ia True, ia_mn_weight > 0) is refused: sources from before the
# architecture round (ROOT p7, p6_spinal) cannot be loaded and must not be reused. The
# chain must run with the source's seed, size and THREADS (the weight loader checks every synapse), so
# keep THREADS = 16. EES objects are built after the network, so the wiring is the same.
# Output: results/human_modes/$ROOT/chain/s<seed>/<condition>/s<k>/<mode>.h5 (resumable: a resubmitted job
# skips saved sessions; a chain cut by the time limit continues where it stopped).
#
# Submit from the repo root:
#   sbatch run_p7_chain_mn5.sh
#   sbatch --array=0 run_p7_chain_mn5.sh          # one seed only
#
# Local smoke test (production size, tiny times; builds its own source):
#   SLURM_ARRAY_TASK_ID=0 THREADS=2 SRC_SIM_MS=2000 SESSION_MS=2000 N=2 ROOT=p7_smoke \
#     CONDS="bws50_ees10:bws50:EES s0.5_bws50:bws50:EXT05" bash run_p7_chain_mn5.sh
#
# Env: SEEDS ("12345 54321 777"), N (15), SESSION_MS (60000), ROOT (p7_arch), SRC_ROOT (= ROOT; p6_spinal reuses
#      existing P6 sources), SRC_SIM_MS (120000), THREADS (16),
#      CONDS ("name:mode:flagset ..." with flagset in EES, EXT05, EXT025, REC, or combined with + e.g. EXT05+EES), EXTRA.
# Summary: python3 scripts/p7_chain_compare.py --root results/human_modes/p7_arch/chain/s12345
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
[ -f "$REPO/cpg_2legs_fast.py" ] || REPO="$(pwd)"   # sbatch copies the script elsewhere

read -r -a SEEDS <<< "${SEEDS:-12345 54321 777}"
N=${N:-15}
SESSION_MS=${SESSION_MS:-60000}
ROOT=${ROOT:-p7_arch}
SRC_ROOT=${SRC_ROOT:-$ROOT}
SRC_SIM_MS=${SRC_SIM_MS:-120000}
T=${SLURM_ARRAY_TASK_ID:-0}
export THREADS=${THREADS:-16} NO_SRUN=1 SIZE=production TRIGGER=force
EXTRA=${EXTRA:-}
WAVE=${WAVE:-5}
DEFAULT_CONDS="bws50:bws50:NONE bws90:bws90:NONE bws50_ees10:bws50:EES bws90_ees10:bws90:EES \
s0.5_bws50:bws50:EXT05 s0.5_bws50_ees10:bws50:EXT05+EES s0.25_bws50:bws50:EXT025 s0.25_bws50_ees10:bws50:EXT025+EES \
s0.5_bws90:bws90:EXT05 s0.5_bws90_ees10:bws90:EXT05+EES s0.25_bws90:bws90:EXT025 s0.25_bws90_ees10:bws90:EXT025+EES \
r0.5_bws50:bws50:EXT05+REC r0.5_bws50_ees10:bws50:EXT05+REC+EES r0.25_bws50:bws50:EXT025+REC r0.25_bws50_ees10:bws50:EXT025+REC+EES \
r0.5_bws90:bws90:EXT05+REC r0.5_bws90_ees10:bws90:EXT05+REC+EES r0.25_bws90:bws90:EXT025+REC r0.25_bws90_ees10:bws90:EXT025+REC+EES"
read -r -a CONDS <<< "${CONDS:-$DEFAULT_CONDS}"
EES_FLAGS="--ees-hz 10 --ees-amp 0 --ees-amp-cut 1.0"
# REC (MOD_EXT_STRENGTH_RECOVERY): wref = the healthy trained captured CUT->RG-E weight, read from the seed's source
# below; w0 = wref x the mode's init_scale (the injured start). Set per condition in flags_of.

python3 -c "import nest, yaml, h5py, numpy" 2>/dev/null \
  || { echo "[p7-mn5] missing python module (need nest, pyyaml, h5py, numpy)" >&2; exit 1; }

SEED=${SEEDS[$T]:?no seed for task $T}
SRC="$REPO/results/human_modes/$SRC_ROOT/src/s$SEED"
if ! grep -q '^\[HDF5\] saved' "$SRC/comfortable.log" 2>/dev/null; then
  # no source yet: make it here (the P6 source recipe: naive comfortable walk, eta 0.05, PRP threshold 1;
  # deterministic for a seed, size and thread count, so it equals the P6 one)
  echo "[p7-mn5] seed=$SEED: building the healthy source $SRC/comfortable.h5 (${SRC_SIM_MS} ms)"
  SEED="$SEED" SIM_MS="$SRC_SIM_MS" TRAINED=0 TAG="$SRC_ROOT/src/s$SEED" \
    EXTRA="--consolidate-prp-threshold 1 --spinal-eta 0.05" bash "$REPO/run_human_modes.sh" comfortable
  grep -q '^\[HDF5\] saved' "$SRC/comfortable.log" 2>/dev/null \
    || { echo "[p7-mn5] source failed (see $SRC/comfortable.log)" >&2; exit 1; }
fi

python3 - "$SRC/comfortable.h5" <<'PY' || { echo "[p7-mn5] $SRC/comfortable.h5 is on the old wiring (or unreadable): use a fresh ROOT/SRC_ROOT" >&2; exit 1; }
import sys, h5py
a = h5py.File(sys.argv[1], "r").attrs
ok = (not bool(a.get("cut_to_ine", True))) and bool(a.get("swing_afferent_as_ia", False)) and float(a.get("ia_mn_weight", 0)) > 0
sys.exit(0 if ok else 1)
PY
WREF=$(python3 - "$SRC/comfortable.h5" <<'PY'
import sys, h5py, numpy as np
f = h5py.File(sys.argv[1], "r")
print("%.2f" % np.mean([f[f"leg_{s}/consolidation/cut->rge_baseline_mean"][()][-1] for s in "LR"]))
PY
)
echo "[p7-mn5] seed=$SEED healthy captured CUT->RG-E weight wref=$WREF pA"
init_scale() {  # mode -> injured-start weight scale from config/modes/human.yaml
  python3 -c "import yaml,sys; print(yaml.safe_load(open('$REPO/config/modes/human.yaml'))['modes']['$1']['init_scale'])"
}

flags_of() {  # flagset mode -> flags
  local out="" part
  local mode_="$2" w0
  IFS='+' read -r -a parts <<< "$1"
  for part in "${parts[@]}"; do
    case "$part" in
      EES) out="$out $EES_FLAGS" ;;
      EXT05) out="$out --extensor-strength 0.5" ;;
      EXT025) out="$out --extensor-strength 0.25" ;;
      REC) w0=$(python3 -c "print('%.2f' % ($WREF * $(init_scale "$mode_")))")
           out="$out --strength-recovery-w0 $w0 --strength-recovery-wref $WREF" ;;
      NONE) ;;
      *) echo "[p7-mn5] unknown flagset $part" >&2; exit 1 ;;
    esac
  done
  echo "$out"
}

echo "[p7-mn5] seed=$SEED conditions=${#CONDS[@]} waves of $WAVE, threads=$THREADS each, N=$N sessions of ${SESSION_MS} ms"
i=0
for c in "${CONDS[@]}"; do
  IFS=':' read -r name mode fs <<< "$c"
  fl=$(flags_of "$fs" "$mode")
  echo "[p7-mn5]   $name: mode=$mode flags:$fl"
  SEED="$SEED" SIM_MS="$SESSION_MS" MODE="$mode" N="$N" SRC="$SRC" \
    TAG="$ROOT/chain/s$SEED/$name" EXTRA="$fl $EXTRA" bash "$REPO/run_p6_sessions.sh" &
  i=$((i + 1))
  if [ $((i % WAVE)) -eq 0 ]; then wait; fi
done
wait
echo "[p7-mn5] seed=$SEED done"
