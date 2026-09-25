#!/bin/bash
# regress.sh — rat regression check (PLAN.md, Phase 0).
#
# Re-runs the two rat debug configs (rat-sh/debug.sh, rat-sh/debug_force.sh) exactly as
# they are, and checks that their output content is unchanged against the
# recorded rat "golden" run. Every migration phase must end with this passing
# (PLAN.md, guiding principle 1: rat stays byte-identical).
#
#   ./regress.sh            check against the golden run (default)
#   ./regress.sh record     (re)record the golden run -- only on purpose, e.g.
#                           on a new machine or after an agreed rat change
#
# How it works:
#   * Each debug script runs unmodified inside a scratch directory (with a
#     symlink to cpg_2legs_fast.py), so real results/ outputs are never
#     overwritten and the rat scripts need no edits.
#   * Comparison is by content digest (scripts/regression_compare.py digest):
#     all datasets and attributes, minus volatile ones like created_utc.
#     Digests live in results/golden/rat/MANIFEST.txt, which is committed;
#     the golden .h5 files themselves are git-ignored (*.h5) and stay local.
#     If they are present, a failing check also prints a per-array diff.
#   * Runs with 4 NEST threads by default. Multi-thread runs are reproducible
#     since the B11 fix (PLAN.md §7): before it, GetConnections returned the
#     same connections in a run-to-run varying order and the static-weight
#     heterogeneity assigned its seeded factors in that order. Now every
#     positional use of connections goes through sorted_connections().
#   * NEST results still depend on the thread count (one RNG stream per
#     virtual process), so the golden run records REGRESS_THREADS and a check
#     refuses to run with a different value.
#
# Env:
#   REGRESS_THREADS   threads passed to the debug scripts (default 4)
#   REGRESS_KEEP=1    keep the scratch directory even when the check passes

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GOLDEN_DIR="$REPO/results/golden/rat"
MANIFEST="$GOLDEN_DIR/MANIFEST.txt"
COMPARE="$REPO/scripts/regression_compare.py"
THREADS="${REGRESS_THREADS:-4}"
MODE="${1:-check}"

# config name | script | output path inside the scratch dir
CONFIGS="debug|rat-sh/debug.sh|results/debug.h5
debug_force|rat-sh/debug_force.sh|results/debug_force.h5"

case "$MODE" in
  check|record) ;;
  *) echo "usage: $0 [check|record]" >&2; exit 2 ;;
esac

manifest_value() {  # manifest_value <key>
  grep -E "^$1=" "$MANIFEST" | head -1 | cut -d= -f2-
}

if [ "$MODE" = "check" ]; then
  if [ ! -f "$MANIFEST" ]; then
    echo "[regress] no manifest at $MANIFEST -- run '$0 record' first." >&2
    exit 2
  fi
  golden_threads="$(manifest_value threads)"
  if [ "$golden_threads" != "$THREADS" ]; then
    echo "[regress] golden run used threads=$golden_threads, this check would use $THREADS." >&2
    echo "[regress] NEST output depends on the thread count; set REGRESS_THREADS=$golden_threads." >&2
    exit 2
  fi
  nest_now="$(python3 -c 'import nest; print(nest.__version__)' 2>/dev/null | tail -1)"
  nest_golden="$(manifest_value nest_version)"
  if [ "$nest_now" != "$nest_golden" ]; then
    echo "[regress] WARNING: NEST $nest_now here, golden recorded with NEST $nest_golden." >&2
  fi
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/tinycpg-regress.XXXXXX")"
ln -s "$REPO/cpg_2legs_fast.py" "$WORK/cpg_2legs_fast.py"
echo "[regress] mode=$MODE threads=$THREADS scratch=$WORK"

fail=0
digests=""
while IFS='|' read -r name script out <&3; do
  log="$WORK/$name.log"
  echo "[regress] running $script ..."
  start=$(date +%s)
  if ! (cd "$WORK" && THREADS="$THREADS" bash "$REPO/$script" </dev/null >"$log" 2>&1); then
    echo "[regress] FAIL $name: $script exited non-zero (log: $log)"
    tail -20 "$log"
    fail=1
    continue
  fi
  secs=$(( $(date +%s) - start ))
  digest="$(python3 "$COMPARE" digest "$WORK/$out")"
  digests="$digests$name=$digest
"

  if [ "$MODE" = "record" ]; then
    mkdir -p "$GOLDEN_DIR"
    cp "$WORK/$out" "$GOLDEN_DIR/$name.h5"
    echo "[regress] recorded $name (${secs}s) digest=$digest"
    continue
  fi

  expected="$(manifest_value "$name")"
  if [ "$digest" = "$expected" ]; then
    echo "[regress] PASS $name (${secs}s)"
  else
    echo "[regress] FAIL $name (${secs}s): digest $digest != golden $expected"
    if [ -f "$GOLDEN_DIR/$name.h5" ]; then
      python3 "$COMPARE" compare "$GOLDEN_DIR/$name.h5" "$WORK/$out" || true
    else
      echo "[regress] (no local golden $name.h5 -- re-record on the last good commit for a per-array diff)"
    fi
    fail=1
  fi
done 3<<EOF
$CONFIGS
EOF

if [ "$MODE" = "record" ]; then
  if [ "$fail" -ne 0 ]; then
    echo "[regress] record FAILED; manifest not written. Scratch kept: $WORK" >&2
    exit 1
  fi
  {
    echo "# Rat golden run for regress.sh (PLAN.md, Phase 0). Written by './regress.sh record'."
    echo "# Digests: scripts/regression_compare.py digest (content only, created_utc excluded)."
    echo "recorded_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "git_commit=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)$(git -C "$REPO" diff --quiet -- cpg_2legs_fast.py species_config.py config rat-sh/debug.sh rat-sh/debug_force.sh 2>/dev/null || echo '+dirty')"
    echo "threads=$THREADS"
    echo "nest_version=$(python3 -c 'import nest; print(nest.__version__)' 2>/dev/null | tail -1)"
    echo "python=$(python3 -c 'import platform; print(platform.python_version())')"
    echo "numpy=$(python3 -c 'import numpy; print(numpy.__version__)')"
    echo "h5py=$(python3 -c 'import h5py; print(h5py.__version__)')"
    echo "platform=$(uname -sm)"
    printf "%s" "$digests"
  } >"$MANIFEST"
  rm -rf "$WORK"
  echo "[regress] manifest written: $MANIFEST"
  exit 0
fi

if [ "$fail" -ne 0 ]; then
  echo "[regress] REGRESSION CHECK FAILED. Scratch kept for inspection: $WORK"
  exit 1
fi
if [ "${REGRESS_KEEP:-0}" = "1" ]; then
  echo "[regress] scratch kept: $WORK"
else
  rm -rf "$WORK"
fi
echo "[regress] ALL PASS -- rat output unchanged."
