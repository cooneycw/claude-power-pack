#!/bin/sh
# #1917 PR-A: run this committed command file at the frozen pushed checkpoint.
# Usage: sh host-run.sh CHECKPOINT_SHA OUTPUT_DIRECTORY
# Requires host Git + Docker. No host configuration or credentials are copied.
set -eu
checkpoint=${1:?exact pushed checkpoint SHA required}
output=${2:?absolute output directory required}
case "$checkpoint" in *[!0-9a-f]*|'') exit 2;; esac
[ "${#checkpoint}" -eq 40 ] || exit 2
case "$output" in /*) ;; *) exit 2;; esac
mkdir -p "$output"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT HUP INT TERM
git clone --quiet https://github.com/cooneycw/claude-power-pack.git "$scratch/source"
git -C "$scratch/source" fetch --quiet origin "$checkpoint"
git -C "$scratch/source" checkout --quiet --detach "$checkpoint"
test "$(git -C "$scratch/source" rev-parse HEAD)" = "$checkpoint"
python3 "$scratch/source/scripts/ci-shape-check.py" run --tier image \
  --receipt "$output/image.json" > "$output/image-launch.log" 2>&1
