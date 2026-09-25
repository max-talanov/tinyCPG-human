#!/bin/bash -l
#SBATCH --job-name=CPG_CONSOL_ALL
#SBATCH --output=Nest_consol_all_%A_%a.slurmout
#SBATCH --error=Nest_consol_all_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-23
#SBATCH --cpus-per-task=64
#SBATCH --time=04:00:00
#SBATCH --partition=gp_bsccs
#
# STAGE 5 -- first production-scale (full N, BS=60Hz) test of --consolidate
# across medium/fast/toe with a single, uniform descending-arm gain
# (0.25/0.10), following two local (--debug-small) fixes made 2026-09-17:
#
#   1. medium's timing constants (cap=450, lead-offset=150, step-period=1000,
#      fatigue-recovery=600) were found to sit exactly on multiples of
#      --debug-small's 50ms simulation tick, causing seed/thread-sensitive
#      collapse onto discrete states. De-aligning them by ~1% fixed this
#      cleanly at debug-small -- but this script does NOT apply that
#      de-alignment: at production's own 100ms tick, those same constants
#      are already NOT exact multiples (450/100=4.5, 260/100=2.6), so the
#      failure mode may not even exist at this discretization, and copying
#      untested debug-small-derived numbers to full-N production would be
#      guessing, not fixing (this project has repeatedly documented debug/
#      production divergence -- see CLAUDE.md "Force-triggered CUT"). This
#      script's medium timing is otherwise unchanged from its own long-
#      standing confirmed values, with only the previously-stale
#      step-period (520, never actually tested) corrected to 1000.
#   2. --consolidate previously tracked BS->RG-E/F's bookkeeping but never
#      wrote it back to NEST, so BS->RG ran pure vanilla STDP regardless of
#      the flag for as long as --consolidate has existed. Fixed in
#      cpg_2legs_fast.py (consolidate_behavioral_keys now includes bs->rge/
#      bs->rgf whenever plastic). Every --consolidate gain confirmed before
#      this fix (0.20/0.15 at medium, extended to fast/toe via tau_tag_ms
#      rescaling) is now known-stale. Re-running the descending-arm gain
#      search on the fixed code, at debug-small, found a NEW gain --
#      0.25/0.10 -- that is genuine and reproducibly anti-phase at all
#      three loading-bearing modes (medium, fast, toe), two-seed-confirmed
#      in every case (see CLAUDE.md, "Fast/toe re-confirmed under the
#      BS->RG write-back fix", 2026-09-17). This script exists to check
#      whether that debug-small finding survives at full N / BS=60Hz.
#
# SCOPE (8 cells x 3 seeds = 24 tasks):
#   Modes: medium, fast, toe -- each crossed with both arms (descending/
#          sensory) and run WITH --consolidate at the new uniform gain
#          (0.25/0.10, --consolidate-tau-tag-ms per mode: 2000/5000/20000
#          respectively, unchanged from each mode's own debug-small-
#          confirmed value). Plus slow, both arms, WITHOUT --consolidate
#          (a no-consolidate control -- Stage 2 found consolidate actively
#          harmful there, unrelated to any of today's fixes, not
#          re-tested here).
#   Loading: full weight-bearing only for medium/fast/slow; toe already IS
#          the partial-unloading condition (--ia-feedback-gain/
#          --cut-feedback-gain 0.5, baked into its own timing block below).
#          Air stepping excluded entirely -- still an open, unrelated
#          problem (Schmitt-trigger chattering at the rate-update-ms tick
#          floor, see CLAUDE.md "Stage 3").
#   Seeds: 12345 / 54321 / 98765 -- matching every other production
#          confirmatory sweep in this project, given documented NEST
#          multi-threaded run-to-run nondeterminism.
#
# NOT in scope for this submission (deliberately -- do not silently add):
#   - Fast speed's own base-timing confirmation is itself only debug-small
#     (a fast operating point was never separately re-validated at full N
#     the way medium's base timing was -- see CLAUDE.md "Production-scale
#     sanity check, medium point"). This script's fast cells therefore test
#     TWO unconfirmed-at-scale things at once (base timing AND consolidate
#     gain) -- if a fast cell fails, check frac_at_cap/corrLR on a
#     no-consolidate control run locally before concluding the gain is at
#     fault.
#   - Toe/air's own base-timing confirmation is likewise debug-small only.
#   - The medium tick-de-alignment fix (see point 1 above) -- intentionally
#     not applied here.
#   - STDP initial-weight (mu, CV) robustness grid.
#
# 120s sim, matching this project's established precedent for a
# confirmatory (not exploratory) production submission.
#
# TIME BUDGET: 4h (was 12h, 2026-09-25). The old 12h absorbed the recorder bug
# fixed in cpg_2legs_fast.py (MOD_RECORDER_CLEAR): spike recorders were never
# cleared, so Python bookkeeping grew with the square of simulated time
# (Round 6: ~135 s NEST vs ~17,000 s bookkeeping). Force-trigger + fatigue +
# consolidate bookkeeping is still slower per simulated second than the
# timer-only path, but now linear.
#
# After completion, run on every output:
#   python3 scripts/cpg_cutforce_diagnostics.py --steady-from-ms 30000 results/cpg_consol_all_*.h5
# Read per cell across its 3 seeds: frac_at_cap should stay near 0.00 on
# both legs and corr(F-E_L,F-E_R) should be reproducibly negative (or, for
# fast, reproducibly small-magnitude and same-signed -- see CLAUDE.md, fast
# is known to be a weak-but-consistent-sign case even at debug-small) in at
# least 2 of 3 seeds. Also check bs->rge's final weight against its
# baseline (not printed by the diagnostics script -- read directly via
# h5py, leg_L/R weights/bs->rge_mean vs consolidation/bs->rge_baseline_mean)
# to confirm BS->RG is actually being consolidated at production scale too,
# not just escaping cap-domination for an unrelated reason.
#
# Output: results/cpg_consol_all_<cell-label>_idx00_mu03.50_cv00.30_seed<SEED>.h5

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[ConsolAll] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
SIM_MS=120000

SEEDS=(12345 54321 98765)

# cell index 0-7 -- see header comment for what each one is.
CELL_LABELS=(medium_desc_c medium_sens_c fast_desc_c fast_sens_c toe_desc_c toe_sens_c slow_desc_noconsolidate slow_sens_noconsolidate)
CELL_MODE=(medium medium fast fast toe toe slow slow)
CELL_ARM=(desc sens desc sens desc sens desc sens)

TASK=${SLURM_ARRAY_TASK_ID:-0}
CELL_IDX=$(( TASK / 3 ))
SEED_IDX=$(( TASK % 3 ))
SEED=${SEEDS[$SEED_IDX]}
LABEL=${CELL_LABELS[$CELL_IDX]}
MODE=${CELL_MODE[$CELL_IDX]}
ARM=${CELL_ARM[$CELL_IDX]}

# ---- mode -> confirmed force-trigger timing (debug-small-confirmed values, unchanged) ----
# Loading flags are per-mode too (toe = partial unload); default gain (1.0)
# applies to medium/fast/slow, no flags needed there.
LOADING_FLAGS=()
TAU_TAG=2000
case "$MODE" in
  medium)
    PERIOD=1000
    FAT_ONSET=260
    FAT_RECOVERY=600
    CAP=450
    OFFFRAC=0.35
    LEAD_OFFSET=150
    ASYM=0.0
    TAU_TAG=2000
    ;;
  fast)
    PERIOD=600
    FAT_ONSET=156
    FAT_RECOVERY=360
    CAP=380
    OFFFRAC=0.30
    LEAD_OFFSET=90
    ASYM=0.04
    TAU_TAG=5000
    ;;
  toe)
    PERIOD=730
    FAT_ONSET=100
    FAT_RECOVERY=438
    CAP=330
    OFFFRAC=0.35
    LEAD_OFFSET=110
    ASYM=0.12
    TAU_TAG=20000
    LOADING_FLAGS=(--ia-feedback-gain 0.5 --cut-feedback-gain 0.5)
    ;;
  slow)
    PERIOD=1200
    FAT_ONSET=340
    FAT_RECOVERY=780
    CAP=585
    OFFFRAC=0.35
    LEAD_OFFSET=150
    ASYM=0.0
    ;;
esac

# ---- leg-fatigue asymmetry: only fast/toe use it (see CLAUDE.md "Persistent
# leg asymmetry" -- medium's own leading-leg problem was superseded by the
# BS->RG fix + new gain instead, not by this) ----
ASYM_FLAGS=()
if [ "$ASYM" != "0.0" ]; then
  ASYM_FLAGS=(--leg-fatigue-asym-frac "$ASYM")
fi

# ---- arm -> BS plasticity ----
# NOTE: flags are built as arrays, not space-joined strings -- see
# CLAUDE.md "Stage 3" for why (a space-joined string handed to "${VAR}"
# unquoted is not guaranteed to word-split back into separate argv tokens
# on every shell/IFS configuration).
ARM_FLAGS=()
if [ "$ARM" = "sens" ]; then
  ARM_FLAGS=(--freeze-bs-rg)
fi

# ---- --consolidate: uniform gain (0.25/0.10) at medium/fast/toe; OFF at slow ----
if [ "$MODE" = "slow" ]; then
  CONSOLIDATE_FLAGS=()
  echo "[ConsolAll] task=$TASK cell=$LABEL mode=$MODE(period=${PERIOD}ms) arm=$ARM seed=$SEED consolidate=OFF (no-consolidate control)"
else
  CONSOLIDATE_FLAGS=(--consolidate --consolidate-prp-gain-genuine 0.25 --consolidate-prp-gain-forced 0.10 --consolidate-tau-tag-ms "$TAU_TAG")
  echo "[ConsolAll] task=$TASK cell=$LABEL mode=$MODE(period=${PERIOD}ms) arm=$ARM seed=$SEED consolidate=ON gain=0.25/0.10 tau_tag=${TAU_TAG}ms"
fi

srun --cpu-bind=cores --distribution=block:block \
  python3 -u cpg_2legs_fast.py \
    --tag "consol_all_${LABEL}" \
    --out cpg_run.h5 \
    --outdir "$OUTDIR" \
    --seed "$SEED" \
    --sweep-pairs "3.5:0.30" \
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
    --lead-offset-ms "$LEAD_OFFSET" \
    --cut-force-on-frac 0.80 \
    --cut-force-off-frac "$OFFFRAC" \
    --cut-max-stance-ms "$CAP" \
    --cut-max-swing-ms "$CAP" \
    --muscle-fatigue \
    --fatigue-tau-onset-ms "$FAT_ONSET" \
    --fatigue-tau-recovery-ms "$FAT_RECOVERY" \
    --fatigue-max-frac 0.95 \
    "${ASYM_FLAGS[@]}" \
    "${LOADING_FLAGS[@]}" \
    "${CONSOLIDATE_FLAGS[@]}" \
    "${ARM_FLAGS[@]}" \
    --long-run
