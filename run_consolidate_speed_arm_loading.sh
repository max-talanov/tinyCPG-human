#!/bin/bash -l
#SBATCH --job-name=CPG_CONSOL_SAL
#SBATCH --output=Nest_consol_sal_%A_%a.slurmout
#SBATCH --error=Nest_consol_sal_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-11
#SBATCH --cpus-per-task=64
#SBATCH --time=12:00:00
#SBATCH --partition=acc
#
# STAGE 4 of ~/.claude/plans/resilient-soaring-flamingo.md -- originally the
# first MN5 submission for --consolidate under --cut-trigger force.
#
# REVISED 2026-09-17: --consolidate is now OFF for BOTH speeds (see below) --
# this script has been narrowed from "confirm --consolidate at medium+slow"
# to "confirm the base force-trigger mechanism at medium+slow, no
# consolidate at all". Do not extend scope without re-reading the CLAUDE.md
# sections cited throughout; the reasons are not small.
#
# Two things drove this revision, both found locally at --debug-small
# scale (50ms rate-update/simulate-chunk tick, NOT this script's 100ms --
# see the tick-alignment caveat under "Speeds" below) while investigating
# why medium's numbers weren't reproducing across seeds:
#
#   1. medium's OWN base (no-consolidate) force-trigger mechanism was itself
#      unexpectedly seed/thread-sensitive -- steady-state corr(F-E_L,F-E_R)
#      swung from -0.86 to +0.86 across just 4 local seed/thread draws,
#      instead of reliably landing anti-phase. Root cause: 4 of medium's 5
#      timing constants (cap=450, lead-offset=150, step-period=1000,
#      recovery=600) landed EXACTLY on multiples of the local 50ms
#      simulation tick, vs. only 1-2 of 5 for every other confirmed mode
#      (slow/fast/toe) -- exact alignment let the stance/swing Schmitt
#      trigger collapse onto razor-edge discrete states (confirmed by
#      perfectly zero-variance, exact-tick-multiple bout durations) that
#      flip unpredictably depending on which side of a tick boundary NEST's
#      thread-order nondeterminism lands a spike. De-aligning cap/tau-onset
#      by ~1% (450->453, 260->257) at --debug-small/50ms-tick cleanly fixed
#      this (steady corrLR -0.814/-0.799, both seeds, tight match) -- see
#      "Persistent leg asymmetry breaks the fast/toe bistability" section's
#      sibling investigation in CLAUDE.md (tick-alignment discovery,
#      2026-09-17). This fix is NOT applied to this script's own 100ms-tick,
#      full-N configuration below -- at 100ms, cap/tau-onset are not exactly
#      aligned in the first place (4.5/2.6 ticks, not integers), so the same
#      failure mode may not even apply at this script's actual
#      discretization, and blindly copying debug-small-derived numbers to
#      full-N (a divergence this project has hit before -- see "Force-
#      triggered CUT") would be guessing, not fixing.
#   2. --consolidate on top of the (locally de-aligned) base mechanism is
#      SEPARATELY broken: 14 configurations tried (4 gain ratios x 2 seeds,
#      3 capture-threshold values x 2 seeds, all at genuine=0.20/forced=0.10
#      -- the pair that already cleanly fixed one leg) never got BOTH legs
#      genuine with a consistent-sign corr(F-E_L,F-E_R) across seeds. The
#      non-leading leg (L, since --leading-leg R) was disproportionately the
#      one that locked up across every gain ratio, every threshold, AND the
#      earlier --leg-fatigue-asym-frac attempt -- a structural fingerprint
#      pointing at the priming/lead-offset asymmetry itself interacting
#      badly with --consolidate's capture mechanism, not something a gain or
#      threshold knob can route around. See CLAUDE.md's "medium+consolidate
#      gain/threshold re-tune" investigation (2026-09-17) for the full
#      14-config table. This needs its own dedicated pass into the
#      leading-leg asymmetry, not another parameter sweep.
#
# SCOPE (4 cells x 3 seeds = 12 tasks, --consolidate now OFF everywhere):
#   Speeds:  medium (step-period=1000ms -- FIXED from a stale 520ms this
#            session; 1000ms is what every local confirmation in CLAUDE.md
#            actually used, including the paper's own final_desc_medium.h5;
#            520ms was never the tested value) and slow (step-period=1200ms,
#            ~6cm/s) -- FAST IS EXCLUDED, see prior scope notes below.
#   Arms:    descending (BS->RG plastic, default) and sensory
#            (--freeze-bs-rg) -- both now run as no-consolidate controls
#            (see revision note above; the previously-confirmed per-arm gain
#            pairs, 0.20/0.15 descending / 0.25/0.10 sensory, are UNUSED by
#            this script now).
#   --consolidate is OFF for every cell in this script (see revision note
#            above). Medium used to be the one consolidate-on speed; slow
#            was already a no-consolidate control (Stage 2 found the
#            medium-confirmed gain pair actively harmful at slow). Now both
#            are no-consolidate controls, for different reasons -- slow
#            because consolidate regresses it, medium because consolidate
#            has an unresolved leading-leg-asymmetry interaction.
#   Loading: FULL WEIGHT-BEARING ONLY -- toe and air stepping are excluded.
#            Stage 3's seed-1 screen found the confirmed medium timing
#            config (tau=260/off=0.35/cap=450) fails EVEN WITHOUT
#            --consolidate at toe stepping (steady-state atCap 1.00/1.00,
#            both arms -- a disguised clock) and at air stepping (bout
#            duration collapses to the 50ms rate-update-ms tick floor with
#            zero variance, both arms -- degenerate chattering, not a
#            genuine rhythm at all). This is a timing-mechanism failure at
#            reduced loading, independent of --consolidate entirely -- see
#            "Stage 3" in CLAUDE.md. A previous whole-run-correlation-only
#            check had read this as the paper's expected qualitative
#            unloading degradation; it wasn't checked against frac_at_cap or
#            steady-state windowing until now, and that check shows the
#            mechanism itself is broken there, not just weaker. Toe/air stay
#            out of this script until the medium timing config (or a
#            loading-specific alternative) is re-tuned for the reduced force
#            ceiling under partial/full unloading -- a "Stage 1 for the
#            loading axis," not yet attempted.
#   Seeds:   12345 / 54321 / 98765 -- three, not two, given the documented
#            same-seed/same-config run-to-run nondeterminism finding (NEST
#            multi-threaded execution can flip corr(F-E_L,F-E_R) sign with
#            everything else held fixed -- see "Also surfaced during this
#            work" in CLAUDE.md's Stage 1 section).
#
# NOT in scope for this submission (deliberately -- do not silently add):
#   - Fast speed (unresolved, see above).
#   - --consolidate at ANY speed now (see 2026-09-17 revision note above) --
#     all 4 cells are no-consolidate controls, not a TODO. Re-enabling it at
#     medium needs a dedicated leading-leg-asymmetry investigation first;
#     re-enabling it at slow needs Stage 2's already-documented failure
#     (cap-domination/synchronization/chattering across 12 configs) to be
#     overturned by new evidence.
#   - Toe/air loading at any speed (confirmed broken even without
#     --consolidate, see above) -- needs its own timing re-tune first.
#   - STDP initial-weight (mu, CV) robustness grid (Phase 3's own 10-point
#     sweep).
#   - Applying the debug-small-derived tick-de-alignment fix (450->453,
#     260->257) to this script's full-N/100ms-tick configuration -- see
#     revision note above for why that would be guessing, not fixing.
#
# 120s sim, matching run_cutforce_sweep6.sh's own precedent for a
# confirmatory (not exploratory) production submission -- more gait cycles
# per run than the 60s local tuning rounds used.
#
# TIME BUDGET: same 12h precedent as run_cutforce_sweep6.sh (force-trigger
# + muscle-fatigue bookkeeping is measurably slower per simulated second
# than the timer-only path -- do not shrink this; consolidate is off in
# this revision so its own extra overhead no longer applies, but the budget
# is left unchanged as a safety margin rather than re-measured).
#
# After completion, run BOTH diagnostics on every output, same as every
# prior force-trigger round:
#   python3 scripts/cpg_cutforce_diagnostics.py --steady-from-ms 30000 results/cpg_consol_sal_*.h5
# Read per cell across its 3 seeds: frac_at_cap should stay near 0.00 and
# corr(F-E_L,F-E_R) should be reproducibly negative in at least 2 of 3 --
# a cell that behaves like the excluded fast point (deterministic but
# seed-flipping) should be flagged, not averaged over silently.
#
# Output: results/cpg_consol_sal_<cell-label>_idx00_mu03.50_cv00.30_seed<SEED>.h5
# (auto-named by --tag/--outdir via the sweep-pairs machinery, same pattern
# as run_cutforce_sweep6.sh -- idx/mu/cv are fixed since this run doesn't
# sweep the STDP init grid, see "NOT in scope" above.)

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[ConsolSAL] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

OUTDIR="results/"
SIM_MS=120000

SEEDS=(12345 54321 98765)

# cell index 0-3 -- see header comment for what each one is. Full weight-
# bearing only -- toe/air excluded, see header "Loading" note above. All
# four cells are now no-consolidate controls (2026-09-17 revision).
CELL_LABELS=(medium_desc_full_noconsolidate medium_sens_full_noconsolidate slow_desc_full_noconsolidate slow_sens_full_noconsolidate)
CELL_SPEED=(medium medium slow slow)
CELL_ARM=(desc sens desc sens)

TASK=${SLURM_ARRAY_TASK_ID:-0}
CELL_IDX=$(( TASK / 3 ))
SEED_IDX=$(( TASK % 3 ))
SEED=${SEEDS[$SEED_IDX]}
LABEL=${CELL_LABELS[$CELL_IDX]}
SPEED=${CELL_SPEED[$CELL_IDX]}
ARM=${CELL_ARM[$CELL_IDX]}

# ---- speed -> confirmed force-trigger timing (Stage 1: medium, slow only) ----
# NOTE: medium's step-period was 520 here previously -- a stale value never
# actually used by any of the local tuning that established tau=260/off=0.35/
# cap=450 (that work, and the paper's own final_desc_medium.h5, all used
# step-period=1000ms). Fixed 2026-09-17 alongside the --consolidate removal.
if [ "$SPEED" = "medium" ]; then
  PERIOD=1000
  FAT_ONSET=260
  FAT_RECOVERY=600
  CAP=450
  OFFFRAC=0.35
  LEAD_OFFSET=150
else # slow
  PERIOD=1200
  FAT_ONSET=340
  FAT_RECOVERY=780
  CAP=585
  OFFFRAC=0.35
  LEAD_OFFSET=150
fi

# ---- arm -> BS plasticity ----
# NOTE: flags are built as arrays, not space-joined strings -- a space-joined
# string handed to "${VAR}" (unquoted) is not guaranteed to word-split back
# into separate argv tokens on every shell/IFS configuration (confirmed to
# silently fail, landing as one unrecognized argparse token, in local testing
# for this exact pattern -- see "Stage 3" in CLAUDE.md). Arrays sidestep the
# ambiguity entirely.
ARM_FLAGS=()
if [ "$ARM" = "sens" ]; then
  ARM_FLAGS=(--freeze-bs-rg)
fi

# loading is full weight-bearing only in this script (see header) -- default
# --ia-feedback-gain/--cut-feedback-gain (1.0) apply, no flags needed.

# ---- --consolidate is OFF everywhere in this revision (see header) ----
CONSOLIDATE_FLAGS=()
echo "[ConsolSAL] task=$TASK cell=$LABEL speed=$SPEED(period=${PERIOD}ms) arm=$ARM loading=full seed=$SEED consolidate=OFF (no-consolidate control, see header)"

srun --cpu-bind=cores --distribution=block:block \
  python3 -u cpg_2legs_fast.py \
    --tag "consol_sal_${LABEL}" \
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
    "${CONSOLIDATE_FLAGS[@]}" \
    "${ARM_FLAGS[@]}" \
    --long-run
