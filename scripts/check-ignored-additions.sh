#!/bin/bash
# check-ignored-additions.sh - Warn when a working-tree file is git-ignored
# but looks like an intentional source addition (the blanket-ignore trap).
#
# Motivation: .gitignore uses blanket rules with hand-maintained negation
# allow-lists (e.g. `*.json` + `!package.json` + `!renovate.json`, or the
# `.dockerignore *.md` incident in agentic-asst #452). When you author a new
# file the repo *should* track, `git add` silently no-ops - nothing fails
# until someone notices the file never got committed. This guard makes that
# loud instead of silent.
#
# Strategy: `git status --ignored=matching` lists every ignored file
# individually (it does NOT collapse whole ignored directories the way the
# default mode does, so a file in a brand-new all-ignored directory is still
# seen). We then drop the usual scratch/build noise by scanning each path
# component against a known set of cache/venv/build dir names, plus a few
# scratch file patterns. What remains is an ignored file sitting in a tracked
# source area - the trap - which we warn about. Near-zero false positives
# against normal venv/cache noise.
#
# Usage:
#   check-ignored-additions.sh [--strict]
#
# Options:
#   --strict   Exit non-zero (3) when suspicious ignored files are found.
#              Default is advisory: always exit 0, just print the warning.
#
# Output:
#   Prints a "[flow] WARNING" block listing suspicious ignored files with a
#   remediation hint. Prints nothing (exit 0) when clean.

set -euo pipefail

STRICT=0
for arg in "$@"; do
  case "$arg" in
    --strict) STRICT=1 ;;
    *) echo "check-ignored-additions.sh: unknown option '$arg'" >&2; exit 2 ;;
  esac
done

# Not a git repo -> nothing to check.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

# Path components that mark a scratch/build/cache tree (matched at any depth).
_SCRATCH_DIRS=".git .venv venv env __pycache__ node_modules .pytest_cache \
.ruff_cache .mypy_cache .tox .nox .cache .eggs dist build htmlcov coverage \
.next .turbo .parcel-cache site-packages artifacts"

is_scratch() {
  # Scratch by file pattern.
  case "$1" in
    *.pyc|*.pyo|*.log|*.swp|*~|*.DS_Store|.coverage) return 0 ;;
  esac
  # Scratch by any path component (dir name or *.egg-info).
  local comp
  local IFS='/'
  for comp in $1; do
    case " $_SCRATCH_DIRS " in *" $comp "*) return 0 ;; esac
    case "$comp" in *.egg-info) return 0 ;; esac
  done
  return 1
}

suspicious=()
while IFS= read -r -d '' entry; do
  # porcelain -z format: 2-char status, a space, then the path.
  status="${entry:0:2}"
  path="${entry:3}"
  [ "$status" = "!!" ] || continue
  case "$path" in */) continue ;; esac   # defensive: skip any dir entry
  is_scratch "$path" && continue
  suspicious+=("$path")
done < <(git status --ignored=matching --porcelain -z 2>/dev/null)

if [ "${#suspicious[@]}" -eq 0 ]; then
  exit 0
fi

echo "[flow] WARNING: ${#suspicious[@]} file(s) are git-ignored and will NOT be committed:" >&2
for p in "${suspicious[@]}"; do
  reason="$(git check-ignore -v "$p" 2>/dev/null || echo "(ignored)")"
  echo "  - $p    <- $reason" >&2
done
echo "" >&2
echo "  If these are intentional additions, add a negation to .gitignore" >&2
echo "  (e.g. '!$( [ "${#suspicious[@]}" -ge 1 ] && echo "${suspicious[0]}" )') or narrow the blanket rule." >&2
echo "  If they are scratch files, ignore this warning." >&2

if [ "$STRICT" -eq 1 ]; then
  exit 3
fi
exit 0
