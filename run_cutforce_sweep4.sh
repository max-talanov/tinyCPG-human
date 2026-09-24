#!/bin/bash -l
#SBATCH --job-name=CPG_CUTFORCE4
#SBATCH --output=Nest_cutforce4_%A_%a.slurmout
#SBATCH --error=Nest_cutforce4_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-8
#SBATCH --cpus-per-task=64
#SBATCH --time=03:00:00
#SBATCH --partition=acc
#
# EXPLORATORY sweep round 4 for MOD_CUT_FORCE_TRIGGER.
#
# Round 3 (fatigue-onset-tau {100,150,250} x --cut-force-off-frac {0.30,0.40,
# 0.50}, cap fixed 450ms) was the first round to escape cap-domination:
# frac_at_cap ~0 on both legs across the ENTIRE grid, with genuine bout-duration
# variability (std up to +-52ms, vs the flat zero of rounds 1-2) -- results/
# 2026-08-30, confirmed with exact cut_on ground truth. But quality still
# varies a lot within that grid:
#   - tau=100-150ms: short (~100ms), weak bouts, and legs SYNCHRONISE in 5/6
#     configs (corr(Force-E_L,Force-E_R) up to +0.47) -- a known failure mode.
#   - tau=250ms (this round's ceiling): best results, legs stay anti-phase,
#     closest to target: off=0.30 -> corr(Force-E,Force-F) -0.61(L)/-0.66(R),
#     corr(Force-E_L,Force-E_R) -0.67. Still short of the -0.7/-0.8 recalibrated
#     target, and quality was still climbing with tau at the top of the tested
#     range -- i.e. round 3 didn't find a ceiling, it ran out of grid.
#
# Round 4 narrows in on the region that actually worked, extending past round
# 3's tau=250 ceiling but staying well below round 1-2's tau=400+ floor (where
# cap-domination returned):
#   fatigue_onset_idx 0/1/2 -> --fatigue-tau-onset-ms 250 / 300 / 350
#   offfrac_idx        0/1/2 -> --cut-force-off-frac    0.25 / 0.30 / 0.35
# --cut-max-stance-ms/--cut-max-swing-ms held FIXED at 450ms, same as round 3
# (that's what actually produced non-cap-dominated results -- not re-testing
# the cap axis here). --cut-force-on-frac 0.80, --fatigue-tau-recovery-ms 600,
# --fatigue-max-frac 0.95, --leading-leg R, --lead-offset-ms 150, sweep-pairs
# 3.5:0.30, step_period=520ms, 60s sim -- all unchanged from rounds 1-3.
#
# array_task = 3 * fatigue_onset_idx + offfrac_idx
#
# After completion, run the diagnostic FIRST, same as rounds 1-3 -- frac_at_cap
# is still the number that decides whether a result means anything, and check
# corr(Force-E_L,Force-E_R) specifically for the leg-synchronisation failure
# mode seen at tau=100-150ms in round 3:
#   python3 scripts/cpg_cutforce_diagnostics.py results/<dated>/cpg_cutforce4_*.h5
#
# Output: results/cpg_cutforce4_fat<ONSET>_off<OFFFRAC>_idx00_*.h5

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
CAP=450                  # FIXED (round 3's value, which actually escaped cap-domination) --
                          # not swept, so any quality change this round is attributable to
                          # the fatigue/off-frac levers actually under test.

T=${SLURM_ARRAY_TASK_ID:-0}
FAT_IDX=$(( T / 3 ))
OFF_IDX=$(( T % 3 ))

case $FAT_IDX in
    0) FAT_ONSET=250; FAT_LABEL="fat250" ;;
    1) FAT_ONSET=300; FAT_LABEL="fat300" ;;
    2) FAT_ONSET=350; FAT_LABEL="fat350" ;;
    *) echo "Unknown FAT_IDX=$FAT_IDX"; exit 1 ;;
esac

case $OFF_IDX in
    0) OFFFRAC=0.25; OFF_LABEL="off025" ;;
    1) OFFFRAC=0.30; OFF_LABEL="off030" ;;
    2) OFFFRAC=0.35; OFF_LABEL="off035" ;;
    *) echo "Unknown OFF_IDX=$OFF_IDX"; exit 1 ;;
esac

TAG="cutforce4_${FAT_LABEL}_${OFF_LABEL}"
echo "[CutForceSweep4] task=$T fatigue_onset=${FAT_ONSET}ms off_frac=$OFFFRAC cap=${CAP}ms(fixed) TAG=$TAG"

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
