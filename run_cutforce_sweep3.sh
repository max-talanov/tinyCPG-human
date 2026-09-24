#!/bin/bash -l
#SBATCH --job-name=CPG_CUTFORCE3
#SBATCH --output=Nest_cutforce3_%A_%a.slurmout
#SBATCH --error=Nest_cutforce3_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-8
#SBATCH --cpus-per-task=64
#SBATCH --time=03:00:00
#SBATCH --partition=acc
#
# EXPLORATORY sweep round 3 for MOD_CUT_FORCE_TRIGGER.
#
# Round 1 (fatigue-onset-tau {200,400,600} x cap {500,800,1100}) and round 2
# (tau {400,600,800} x tighter cap {300,450,600}) both came back 100%
# failsafe-cap-dominated on EVERY tested config, on both legs, exact ground
# truth (results/2026-08-25, results/2026-08-27; see CLAUDE.md "Force-triggered
# CUT" and run_cutforce_sweep2.sh header for the full diagnosis). A fatigue
# overlay at the round-2 "best" config (tau=800/cap=600) showed why: fatigue_e
# only reaches ~0.62 of its 0.95 ceiling by the time the cap fires -- force is
# still ~70-80% of peak, nowhere near the --cut-force-off-frac (0.20) crossing
# target. Neither axis tried so far (fatigue speed, cap duration) alone gets
# there.
#
# Round 3 tests the two remaining, untried levers together instead of one at a
# time:
#   fatigue_onset_idx 0/1/2 -> --fatigue-tau-onset-ms 100 / 150 / 250
#   offfrac_idx        0/1/2 -> --cut-force-off-frac    0.30 / 0.40 / 0.50
# --cut-max-stance-ms/--cut-max-swing-ms held FIXED at 450ms (round 2's middle,
# bio-plausible-ish half-cycle value) so any escape from cap-domination in this
# round is unambiguous -- if frac_at_cap drops, it's because of the new levers,
# not because the cap itself moved. --cut-force-on-frac stays at 0.80,
# --fatigue-tau-recovery-ms at 600, --fatigue-max-frac at 0.95, --leading-leg R,
# --lead-offset-ms 150, sweep-pairs 3.5:0.30, step_period=520ms, 60s sim --
# all unchanged from rounds 1-2.
#
# Faster fatigue-onset (100-250ms, vs round 1-2's 200-800ms floor) should let
# force actually decay within a short bio-plausible window; a looser off-frac
# (0.30-0.50, vs 0.20 throughout rounds 1-2) makes the crossing target easier
# to reach without needing near-complete decay. Round 1 already showed fast
# fatigue alone (200ms) hurts amplitude/quality -- this round asks whether
# pairing it with a looser threshold recovers that cost while finally escaping
# the cap.
#
# array_task = 3 * fatigue_onset_idx + offfrac_idx
#
# After completion, run the diagnostic FIRST, same as rounds 1-2 -- frac_at_cap
# is still the number that decides whether a result means anything:
#   python3 scripts/cpg_cutforce_diagnostics.py results/<dated>/cpg_cutforce3_*.h5
#
# Output: results/cpg_cutforce3_fat<ONSET>_off<OFFFRAC>_idx00_*.h5

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
                          # by the force threshold + failsafe cap under test).
CAP=450                  # FIXED this round (round 2's bio-plausible-ish middle value) --
                          # not swept, so any drop in frac_at_cap is attributable to the
                          # fatigue/off-frac levers actually under test.

T=${SLURM_ARRAY_TASK_ID:-0}
FAT_IDX=$(( T / 3 ))
OFF_IDX=$(( T % 3 ))

case $FAT_IDX in
    0) FAT_ONSET=100; FAT_LABEL="fat100" ;;
    1) FAT_ONSET=150; FAT_LABEL="fat150" ;;
    2) FAT_ONSET=250; FAT_LABEL="fat250" ;;
    *) echo "Unknown FAT_IDX=$FAT_IDX"; exit 1 ;;
esac

case $OFF_IDX in
    0) OFFFRAC=0.30; OFF_LABEL="off030" ;;
    1) OFFFRAC=0.40; OFF_LABEL="off040" ;;
    2) OFFFRAC=0.50; OFF_LABEL="off050" ;;
    *) echo "Unknown OFF_IDX=$OFF_IDX"; exit 1 ;;
esac

TAG="cutforce3_${FAT_LABEL}_${OFF_LABEL}"
echo "[CutForceSweep3] task=$T fatigue_onset=${FAT_ONSET}ms off_frac=$OFFFRAC cap=${CAP}ms(fixed) TAG=$TAG"

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
    --cut-force-off-frac "$OFFFRAC" \
    --cut-max-stance-ms "$CAP" \
    --cut-max-swing-ms "$CAP" \
    --muscle-fatigue \
    --fatigue-tau-onset-ms "$FAT_ONSET" \
    --fatigue-tau-recovery-ms 600 \
    --fatigue-max-frac 0.95 \
    --long-run
