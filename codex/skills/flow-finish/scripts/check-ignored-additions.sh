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
# scratch file patterns. We also drop a short allow-list of files that are
# git-ignored BY DESIGN (env-only, per-machine runtime state that can never be
# an intended source addition) so the guard stops crying wolf on them every run
# (issue #504). What remains is an ignored file sitting in a tracked source
# area - the trap - which we warn about. Near-zero false positives against
# normal venv/cache noise.
#
# Usage:
#   check-ignored-additions.sh [--strict | --advisory]
#
# Options:
#   --strict    Exit 3 when suspicious ignored files are found, anywhere.
#   --advisory  Always exit 0, just print the warning.
#   (neither)   Depends on WHERE it runs (issue #1258):
#                 - a LINKED WORKTREE blocks (exit 3). A flow worktree is
#                   created clean from a tracked tree, so a non-scratch ignored
#                   file in it was written during that worktree's life - the
#                   run's own addition, which is the class that ships a hole: a
#                   clean clone will not have the file (#1144 shipped a runtime
#                   manifest this way, and `/project:next` raised on every clean
#                   clone while the author's tree passed everything).
#                 - the PRIMARY checkout stays advisory (exit 0): years of local
#                   clutter live there legitimately, and a guard that blocked on
#                   it would be routed around.
#               "In a linked worktree" is a proxy for "this run wrote it", not
#               proof - so the message names the cost rather than asserting
#               intent, and --advisory is the override.
#
# Output:
#   Prints a "[flow] WARNING" (advisory) or "[flow] ERROR" (blocking) block
#   listing suspicious ignored files with a remediation hint, then
#   CHECK_IGNORED_ADDITIONS_MODE=<blocking|advisory> on stderr. Prints nothing
#   (exit 0) when clean.

set -euo pipefail

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
trap 'printf "CHECK_IGNORED_ADDITIONS_EXIT=%d\n" "$?" >&2' EXIT

MODE=auto
for arg in "$@"; do
  case "$arg" in
    --strict) MODE=blocking ;;
    --advisory) MODE=advisory ;;
    *) echo "check-ignored-additions.sh: unknown option '$arg'" >&2; exit 2 ;;
  esac
done

# Not a git repo -> nothing to check.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

if [ "$MODE" = auto ]; then
  # A linked worktree's git dir is .git/worktrees/<name> under the COMMON dir;
  # the primary checkout's git dir IS the common dir. Compared as absolute
  # paths, since the two plumbing answers are relative in different ways.
  _gd=$(git rev-parse --path-format=absolute --git-dir 2>/dev/null || true)
  _cd=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)
  if [ -n "$_gd" ] && [ -n "$_cd" ] && [ "$_gd" != "$_cd" ]; then
    MODE=blocking
  else
    MODE=advisory
  fi
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

# Files git-ignored BY DESIGN: env-only, per-machine runtime state that can
# never be an intended source addition. Matched as exact repo-root-relative
# paths (git porcelain output is root-relative regardless of cwd), so the guard
# stays silent on them without over-excluding a similarly named file elsewhere.
# All are documented never-committed in .gitignore (issue #504). Keep this list
# short - each entry is a path the guard will NEVER warn about again.
_INTENTIONAL_IGNORES=".claude/settings.local.json .claude/friction.jsonl \
.claude/learnings.md .claude/learnings.rejected.jsonl .claude/deploy.log \
.claude/deploy-baseline.json"

# Directories of by-design runtime state, matched as a root-relative PREFIX.
# `.claude/runs/` holds lib.cicd's per-run state: removed on success but LEFT
# BEHIND by a failed gate, inside the worktree - so without this entry the first
# failed gate would make every later run in that worktree block (issue #1258).
_INTENTIONAL_IGNORE_DIRS=".claude/runs/"

is_intentional_ignore() {
  case " $_INTENTIONAL_IGNORES " in *" $1 "*) return 0 ;; esac
  local d
  for d in $_INTENTIONAL_IGNORE_DIRS; do
    case "$1" in "$d"*) return 0 ;; esac
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
  is_intentional_ignore "$path" && continue
  suspicious+=("$path")
done < <(git status --ignored=matching --porcelain -z 2>/dev/null)

if [ "${#suspicious[@]}" -eq 0 ]; then
  exit 0
fi

if [ "$MODE" = blocking ]; then
  echo "[flow] ERROR: ${#suspicious[@]} file(s) are git-ignored and will NOT be committed - a clean clone will not have them:" >&2
else
  echo "[flow] WARNING: ${#suspicious[@]} file(s) are git-ignored and will NOT be committed:" >&2
fi
for p in "${suspicious[@]}"; do
  reason="$(git check-ignore -v "$p" 2>/dev/null || echo "(ignored)")"
  echo "  - $p    <- $reason" >&2
done
echo "" >&2
echo "  If these are intentional additions, add a negation to .gitignore" >&2
echo "  (e.g. '!$( [ "${#suspicious[@]}" -ge 1 ] && echo "${suspicious[0]}" )') or narrow the blanket rule." >&2
if [ "$MODE" = blocking ]; then
  echo "  If they are scratch files, delete them, or re-run with --advisory once you are sure" >&2
  echo "  nothing reads them at run time (issue #1258)." >&2
  echo "CHECK_IGNORED_ADDITIONS_MODE=blocking" >&2
  exit 3
fi
echo "  If they are scratch files, ignore this warning." >&2
echo "CHECK_IGNORED_ADDITIONS_MODE=advisory" >&2
exit 0
