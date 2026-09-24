#!/bin/bash
set -e

SCRIPT=""

for arg in "$@"; do
    case $arg in
        --script=*)
            SCRIPT="${arg#*=}"
            ;;
    esac
done

if [ -n "$SCRIPT" ]; then
    if [ -f "./$SCRIPT" ] && [ -x "./$SCRIPT" ]; then
        exec ./"$SCRIPT"
    else
        echo "Error: script '$SCRIPT' not found or not executable in /tinyCPG" >&2
        exit 1
    fi
else
    exec "$@"
fi