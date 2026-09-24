#!/bin/bash -l
#SBATCH --job-name=CPG_CUTFORCE5
#SBATCH --output=Nest_cutforce5_%A_%a.slurmout
#SBATCH --error=Nest_cutforce5_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-8
#SBATCH --cpus-per-task=64
#SBATCH --time=03:00:00
#SBATCH --partition=acc
#
# CONFIRMATION REFINEMENT for MOD_CUT_FORCE_TRIGGER -- not a new exploration.
#
# Round 4 (fatigue-onset-tau {250,300,350} x --cut-force-off-frac {0.25,0.30,
# 0.35}, cap fixed 450ms) found the mechanism is more brittle than round 3's
# trend suggested: 6 of 9 configs REVERTED to cap-domination, including the
# numerically best-looking correlation in the whole grid (tau=350/off=0.35:
# corr(Force-E,Force-F) -0.70(L)/-0.78(R) but 97-100% cap-dominated -- a
# disguised clock, visibly confirmed by a perfectly regular force waveform,
# the same trap round 1 fell into). Off-frac has to loosen TOGETHER with tau,
# not independently: at tau=250, off=0.30 and off=0.35 both stayed genuine
# (frac_at_cap=0.00 both legs); at tau=300 only off=0.35 was even mostly
# genuine (0.26/0.17, not clean); at tau=350 nothing escaped the cap.
#
# Best genuine result across all four rounds so far: tau=250/off=0.35 --
# corr(Force-E,Force-F) -0.59(L)/-0.65(R), corr(Force-E_L,Force-E_R) -0.72
# (inside the -0.7/-0.8 recalibrated target), frac_at_cap=0.00 both legs,
# bout duration 292+-45/292+-56ms (genuine cycle-to-cycle variability) --
# results/2026-08-31.
#
# This round does NOT explore further -- it brackets that optimum tightly to
# check it isn't a lucky single grid cell, given how sharply round 4 showed
# quality can collapse back into cap-domination just 0.05-0.10 higher on
# off-frac:
#   fatigue_onset_idx 0/1/2 -> --fatigue-tau-onset-ms 240 / 250 / 260
#   offfrac_idx        0/1/2 -> --cut-force-off-frac    0.35 / 0.375 / 0.40
# --cut-max-stance-ms/--cut-max-swing-ms held FIXED at 450ms, same as rounds
# 3-4. --cut-force-on-frac 0.80, --fatigue-tau-recovery-ms 600,
# --fatigue-max-frac 0.95, --leading-leg R, --lead-offset-ms 150, sweep-pairs
# 3.5:0.30, step_period=520ms, 60s sim -- all unchanged from rounds 1-4.
#
# array_task = 3 * fatigue_onset_idx + offfrac_idx
#
# After completion, run the diagnostic FIRST -- want frac_at_cap low on both
# legs across MOST or ALL of this narrow grid (not just the center point) for
# tau=250/off=0.35 to count as a robust operating point rather than a fluke:
#   python3 scripts/cpg_cutforce_diagnostics.py results/<dated>/cpg_cutforce5_*.h5
# If it holds up, this is the config to carry into Phase 3 (seed/init
# robustness sweep) -- see CLAUDE.md maturation-plan status for what Phase 3
# covers.
#
# Output: results/cpg_cutforce5_fat<ONSET>_off<OFFFRAC>_idx00_*.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
BASE_SEED=12345
SWEEP_PAIRS="3.5:0.30"   # established production operating point (run_speed_stdp.sh etc.)
SIM_MS=60000             # same length as rounds 1-4 for direct comparability
PERIOD=520               # medium walk (~13.5 cm/s) -- NOTE: in --cut-trigger force mode
                          # this only shapes Ia-E heel->toe sub-group timing within a
                          # detected stance bout; it does NOT set the gait cycle length
                          # the way it does in timer mode (that's emergent here, governed
                          # by the force threshold + failsafe cap under test).
CAP=450                  # FIXED (rounds 3-4's value, which produced genuine crossings) --
                          # not swept, so this round isolates the tau/off-frac sensitivity
                          # right around the round-4 optimum.

T=${SLURM_ARRAY_TASK_ID:-0}
FAT_IDX=$(( T / 3 ))
OFF_IDX=$(( T % 3 ))

case $FAT_IDX in
    0) FAT_ONSET=240; FAT_LABEL="fat240" ;;
    1) FAT_ONSET=250; FAT_LABEL="fat250" ;;
    2) FAT_ONSET=260; FAT_LABEL="fat260" ;;
    *) echo "Unknown FAT_IDX=$FAT_IDX"; exit 1 ;;
esac

case $OFF_IDX in
    0) OFFFRAC=0.350; OFF_LABEL="off0350" ;;
    1) OFFFRAC=0.375; OFF_LABEL="off0375" ;;
    2) OFFFRAC=0.400; OFF_LABEL="off0400" ;;
    *) echo "Unknown OFF_IDX=$OFF_IDX"; exit 1 ;;
esac

TAG="cutforce5_${FAT_LABEL}_${OFF_LABEL}"
echo "[CutForceSweep5] task=$T fatigue_onset=${FAT_ONSET}ms off_frac=$OFFFRAC cap=${CAP}ms(fixed) TAG=$TAG"

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
