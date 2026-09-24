#!/bin/bash -l
#SBATCH --job-name=CPG_CUTFORCE2
#SBATCH --output=Nest_cutforce2_%A_%a.slurmout
#SBATCH --error=Nest_cutforce2_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-8
#SBATCH --cpus-per-task=64
#SBATCH --time=03:00:00
#SBATCH --partition=acc
#
# EXPLORATORY sweep round 2 for MOD_CUT_FORCE_TRIGGER. Round 1
# (run_cutforce_sweep.sh, results/2026-08-25) swept fatigue-onset-tau {200,400,
# 600} x cap {500,800,1100} and found slower fatigue = better counter-phase
# (best: tau=600/cap=800, corr(Force-E,Force-F) ~-0.57/-0.69). But re-checked
# with EXACT ground-truth cut_on logging (added this round, see
# MOD_CUT_FORCE_TRIGGER in cpg_2legs_fast.py -- round 1's files predate it and
# had to be diagnosed by reconstructing bouts from a force threshold, which
# gave inconsistent verdicts depending on the threshold chosen): at
# tau=600/cap=800, BOTH legs hit the cap on 100% of bouts (durations exactly
# 800.0ms, zero variance). That "best" result is a disguised clock, not a
# genuine force-threshold-driven gait -- confirming the concern raised before
# this round: the mechanism has not yet been shown to work as designed at
# production scale.
#
# Round 1's fix direction (larger cap) is also in tension with bio-plausibility:
# cap=800 alone already exceeds the paper's own locomotor-cycle constraint
# (400-700ms FULL stride, Bellardita & Kiehn 2015) for a single HALF-cycle.
# Going bigger makes the disguised-clock problem harder to detect, not smaller.
#
# This round inverts the approach: hold fatigue-onset-tau in the range that
# gave good force amplitude/quality in round 1 (400-800ms) but *tighten* the
# cap toward bio-plausible half-cycle durations (300-600ms), to test directly
# whether genuine (non-cap) threshold crossings emerge under a realistic time
# budget, and at what quality cost:
#   fatigue_onset_idx 0/1/2 -> --fatigue-tau-onset-ms 400 / 600 / 800
#   cap_idx           0/1/2 -> --cut-max-stance-ms = --cut-max-swing-ms 300 / 450 / 600
# All other settings unchanged from round 1 (--fatigue-tau-recovery-ms 600,
# --fatigue-max-frac 0.95, --leading-leg R, --lead-offset-ms 150,
# --cut-force-on-frac 0.80, --cut-force-off-frac 0.20, sweep-pairs 3.5:0.30,
# step_period=520ms, 60s sim).
#
# array_task = 3 * fatigue_onset_idx + cap_idx
#
# After completion, run the (now-exact) diagnostic on every output FIRST --
# frac_at_cap is the number that matters, not correlation alone (round 1's
# apparent "best" result was 100% cap-dominated despite a plausible-looking
# correlation number):
#   python3 scripts/cpg_cutforce_diagnostics.py results/<dated>/cpg_cutforce2_*.h5
#
# Output: results/cpg_cutforce2_fat<ONSET>_cap<CAP>_idx00_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SWEEP_PAIRS="3.5:0.30"   # established production operating point (run_speed_stdp.sh etc.)
SIM_MS=60000             # first-pass filter length; re-run winner(s) at 120s to confirm
PERIOD=520               # medium walk (~13.5 cm/s) -- NOTE: in --cut-trigger force mode
                          # this only shapes Ia-E heel->toe sub-group timing within a
                          # detected stance bout; it does NOT set the gait cycle length
                          # the way it does in timer mode (that's emergent here, governed
                          # by the force threshold + failsafe caps under test).

T=${SLURM_ARRAY_TASK_ID:-0}
FAT_IDX=$(( T / 3 ))
CAP_IDX=$(( T % 3 ))

case $FAT_IDX in
    0) FAT_ONSET=400; FAT_LABEL="fat400" ;;
    1) FAT_ONSET=600; FAT_LABEL="fat600" ;;
    2) FAT_ONSET=800; FAT_LABEL="fat800" ;;
    *) echo "Unknown FAT_IDX=$FAT_IDX"; exit 1 ;;
esac

case $CAP_IDX in
    0) CAP=300; CAP_LABEL="cap300" ;;
    1) CAP=450; CAP_LABEL="cap450" ;;
    2) CAP=600; CAP_LABEL="cap600" ;;
    *) echo "Unknown CAP_IDX=$CAP_IDX"; exit 1 ;;
esac

TAG="cutforce2_${FAT_LABEL}_${CAP_LABEL}"
echo "[CutForceSweep2] task=$T fatigue_onset=${FAT_ONSET}ms cap=${CAP}ms TAG=$TAG"

srun --cpu-bind=cores --distribution=block:block \
  python3 -u cpg_2legs_fast.py \
    --tag "$TAG" \
    --out cpg_run.h5 \
    --outdir "$OUTDIR" \
    --seed "$BASE_SEED" \
    --sweep-pairs "$SWEEP_PAIRS" \
    --sweep-run-idx 0 \
    --sweep-dist lognormal_cv \
    --sim-ms "$SIM_MS" \
    --dt-ms 10 \
    --threads "$SLURM_CPUS_PER_TASK" \
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
    --step-period-ms "$PERIOD" \
    --stance-fraction 0.5 \
    --n-ia-groups 3 \
    --ia-ext-hz 60 80 100 \
    --ia-ext-f-hz 80 \
    --cut-trigger force \
    --leading-leg R \
    --lead-offset-ms 150 \
    --cut-force-on-frac 0.80 \
    --cut-force-off-frac 0.20 \
    --cut-max-stance-ms "$CAP" \
    --cut-max-swing-ms "$CAP" \
    --muscle-fatigue \
    --fatigue-tau-onset-ms "$FAT_ONSET" \
    --fatigue-tau-recovery-ms 600 \
    --fatigue-max-frac 0.95 \
    --long-run
