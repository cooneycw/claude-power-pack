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
# Strategy: `git status --ignored=matching` lists every TOP-LEVEL ignored
# path, but collapses a whole directory a `.gitignore` directory rule covers
# to the one entry `dir/` rather than its files. That collapse cut both ways
# (Nit Store #864, comments 5983077287 and 6192075101): a non-scratch file
# inside a wholly-ignored directory went uninspected (the directory name alone
# is not in the scratch list), and - the opposite failure - a gate's OWN
# scratch output (e.g. `reports/pytest.log` behind a blanket `reports/` rule)
# blocked on the bare directory name, because `is_scratch` matches a file
# extension like `*.log` against the full path and never sees one once it is
# collapsed to `reports/`.
#
# We do NOT fix this by listing every ignored file individually up front
# (`git ls-files --others --ignored --exclude-standard`, no `--directory`):
# measured at 50k files behind one ignored directory (a synthetic venv-sized
# tree), that call itself stays under 0.2s, but the bash classification loop
# below does not - 3.4s total, against ~0.01s for the collapsed form - because
# a repo's REAL noise (.venv, node_modules, .mypy_cache) is exactly what this
# guard exists to walk past, not into. So a directory entry is expanded only
# when it has already survived the three cheap checks below AT THE DIRECTORY
# LEVEL - scratch-by-name, intentional-ignore, and a repo-declared gate-scratch
# prefix - which is what drops .venv/node_modules/etc. without ever reading a
# file inside them. Only a directory nobody has vouched for by name gets
# expanded, and only that one directory's files, via a git call scoped to it.
#
# The scratch check drops the usual scratch/build noise by scanning each path
# component against a known set of cache/venv/build dir names, plus a few
# scratch file patterns. The intentional-ignore check drops a short allow-list
# of files that are git-ignored BY DESIGN (env-only, per-machine runtime state
# that can never be an intended source addition) so the guard stops crying
# wolf on them every run (issue #504). The gate-scratch check drops paths a
# REPO declares are its own gate output (issue #864) - this script cannot know
# every consumer's output directory name, so the consumer names it instead,
# the same shape as `_INTENTIONAL_IGNORE_DIRS` but populated from a file this
# script does not own. What remains is an ignored file sitting in a tracked
# source area - the trap - which we warn about. Near-zero false positives
# against normal venv/cache noise.
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
# A repo can declare its own gate-output directories so this guard never flags
# them, without editing this script (issue #864): one root-relative path
# PREFIX per line (e.g. `dashboard-runs/`) in `.claude/gate-scratch.txt` (or
# the file named by $CHECK_IGNORED_ADDITIONS_GATE_SCRATCH); `#` comments and
# blank lines are ignored, matching the `--baseline` file convention in
# flow-pr-watch.sh. An undeclared gate-output directory still blocks - this
# script cannot know a consumer's output path on its own.
#
# Exit codes: 0 clean (or advisory), 2 usage, 3 findings while blocking,
# 4 the ignored-file inventory could NOT be read while blocking - never 0,
# because an unread inventory and an empty one are different answers.
#
# Output:
#   Prints a "[flow] WARNING" (advisory) or "[flow] ERROR" (blocking) block
#   listing suspicious ignored files with a remediation hint, then
#   CHECK_IGNORED_ADDITIONS_MODE=<blocking|advisory> on stderr. Prints nothing
#   (exit 0) when clean.

set -euo pipefail

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
# (Re-armed below, once there is a temp file for it to remove as well.)
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
# `.claude/runs/` held lib.cicd's per-run state, inside the worktree: removed
# on success but LEFT BEHIND by a failed gate (issue #1258) - so without this
# entry the first failed gate would make every later run in that worktree
# block. Issue #1409 moved new state to `<git-dir>/cpp-runs/`, which `git
# status` cannot see at all, so this entry no longer matches a current write
# - kept for a leftover file from a pre-#1409 runner, or for a target that
# `runner_state_dir()` could not resolve a git directory for at all.
_INTENTIONAL_IGNORE_DIRS=".claude/runs/"

is_intentional_ignore() {
  case " $_INTENTIONAL_IGNORES " in *" $1 "*) return 0 ;; esac
  # Environment files at any depth: local runtime configuration that is
  # ignored so that it is NEVER committed - a clean clone is supposed to lack
  # it (counter-model review, #1258). The tracked template forms are not
  # exempt: an ignored `.env.example` is a real swallowed addition.
  case "${1##*/}" in
    .env.example|.env.sample|.env.template) ;;
    .env|.env.*) return 0 ;;
  esac
  local d
  for d in $_INTENTIONAL_IGNORE_DIRS; do
    case "$1" in "$d"*) return 0 ;; esac
  done
  return 1
}

# Repo-declared gate-output prefixes (issue #864): unlike _INTENTIONAL_IGNORE_DIRS
# above, this script does not own the list - a consuming repo's own gate writes
# ignored scratch under a path only IT knows (`dashboard-runs/<utc>-<sha>/` is
# kyle's; `reports/` is skillc's), so the repo declares it rather than this
# script trying to enumerate every consumer. One root-relative path PREFIX per
# line, `#` comments and blank lines ignored - the same shape `flow-pr-watch.sh`
# uses for its `--baseline` file. Declaring nothing changes nothing: an empty or
# absent file is the same as today, every path still judged by scratch/intentional
# alone.
GATE_SCRATCH_FILE="${CHECK_IGNORED_ADDITIONS_GATE_SCRATCH:-.claude/gate-scratch.txt}"
_DECLARED_GATE_SCRATCH=()
if [ -f "$GATE_SCRATCH_FILE" ]; then
  while IFS= read -r _gs_line || [ -n "$_gs_line" ]; do
    _gs_line="${_gs_line%%#*}"
    # Trim leading/trailing whitespace without a subshell.
    _gs_line="${_gs_line#"${_gs_line%%[![:space:]]*}"}"
    _gs_line="${_gs_line%"${_gs_line##*[![:space:]]}"}"
    [ -n "$_gs_line" ] && _DECLARED_GATE_SCRATCH+=("$_gs_line")
  done < "$GATE_SCRATCH_FILE"
fi

is_declared_gate_scratch() {
  local d
  for d in "${_DECLARED_GATE_SCRATCH[@]:-}"; do
    [ -n "$d" ] || continue
    case "$1" in "$d"*) return 0 ;; esac
  done
  return 1
}

# Read the inventory into a file FIRST and check that git answered (counter-
# model review): a process substitution discards the exit status, so an
# unreadable index produced no entries and the same exit 0 as a clean tree.
# `status --ignored=matching`, not `ls-files`: collapsed is the CHEAP read
# (see the strategy note above, #864) - expansion happens below, and only for
# a directory entry that survives the name-based filters.
_inventory=$(mktemp "${TMPDIR:-/tmp}/check-ignored-additions.XXXXXX")
_expansion=$(mktemp "${TMPDIR:-/tmp}/check-ignored-additions.XXXXXX")
trap 'printf "CHECK_IGNORED_ADDITIONS_EXIT=%d\n" "$?" >&2; rm -f "$_inventory" "$_expansion"' EXIT
if ! git status --ignored=matching --porcelain -z > "$_inventory" 2>/dev/null; then
  echo "[flow] check-ignored-additions: 'git status' failed, so the ignored files were NOT inspected - this is not a clean result." >&2
  if [ "$MODE" = blocking ]; then
    exit 4
  fi
  exit 0
fi

# Expand ONE collapsed directory - and only it, via a pathspec scoped to it -
# into its individual ignored files. `--full-name` plus the `:/` magic
# pathspec prefix root-anchor the read and its output regardless of the
# caller's cwd, matching what `status --porcelain` paths already are. A
# failure here is read exactly like the top-level inventory failing: NOT
# inspected is not the same fact as clean, so it is never silently skipped.
expand_dir() {
  if ! git ls-files --other --ignored --exclude-standard --full-name -z \
          -- ":/$1" > "$_expansion" 2>/dev/null; then
    echo "[flow] check-ignored-additions: 'git ls-files' failed expanding '$1' - NOT inspected, this is not a clean result." >&2
    if [ "$MODE" = blocking ]; then
      exit 4
    fi
    exit 0
  fi
}

suspicious=()
while IFS= read -r -d '' entry; do
  # porcelain -z format: 2-char status, a space, then the path.
  status="${entry:0:2}"
  path="${entry:3}"
  [ "$status" = "!!" ] || continue
  is_scratch "$path" && continue
  is_intentional_ignore "$path" && continue
  is_declared_gate_scratch "$path" && continue
  case "$path" in
    */)
      # A directory nobody has vouched for by name: expand IT, and only it,
      # so the files actually inside decide - not the directory's own name.
      expand_dir "$path"
      while IFS= read -r -d '' subpath; do
        is_scratch "$subpath" && continue
        is_intentional_ignore "$subpath" && continue
        is_declared_gate_scratch "$subpath" && continue
        suspicious+=("$subpath")
      done < "$_expansion"
      ;;
    *)
      suspicious+=("$path")
      ;;
  esac
done < "$_inventory"

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
  echo "  If they are scratch or deliberately local files that are not meant to ship, delete" >&2
  echo "  them or re-run with --advisory (issue #1258)." >&2
  echo "CHECK_IGNORED_ADDITIONS_MODE=blocking" >&2
  exit 3
fi
echo "  If they are scratch files, ignore this warning." >&2
echo "CHECK_IGNORED_ADDITIONS_MODE=advisory" >&2
exit 0
