#!/usr/bin/env bash
# flow-worktree-guard.sh - Warn when a flow edit LEAKED into the MAIN repo
# working tree instead of landing in the active worktree (issue #486).
#
# Motivation: in a native `EnterWorktree` session the session cwd IS the
# worktree, but the worktree physically lives inside the main repo at
# `.claude/worktrees/<name>/`. A `Write`/`Edit` given a hand-built ABSOLUTE
# `.claude/worktrees/<name>/...` path has been observed (flow:auto #442 x2, #471)
# to modify the file in the MAIN repo working tree instead of the worktree - work
# looks done but is written to the wrong tree, either lost or left as a stray
# dirty file on main that other concurrent sessions then see.
#
# The durable fix is a directive: resolve edit paths from
# `git rev-parse --show-toplevel` (the active worktree root), never a hand-built
# `.claude/worktrees/...` absolute path. This guard is the VERIFIABLE backstop for
# that directive: run from inside a linked worktree, it inspects the MAIN repo's
# TRACKED working tree for the leaked-edit signature - so the trap is caught
# before commit rather than discovered later.
#
# To avoid crying wolf (issue #536), it does NOT warn about every dirty file in
# main: the main checkout often carries PRE-EXISTING local modifications
# unrelated to this run (deploy configs, etc.), and flagging those as a leak
# buries the real signal. A dirty main file is treated as a leak only when it
# ALSO appears among the paths THIS run edited (branch commits vs the base, plus
# worktree dirt) - i.e. the run tried to touch that path yet it shows up modified
# in main. Overlapping dirt -> a loud WARNING (and a --strict failure);
# non-overlapping dirt -> a quiet info note, never a failure. Trade-off: a pure
# leak of a file the worktree never also edited is downgraded to info - the
# accepted cost of killing the recurring false positives.
#
# Scope: only meaningful in a linked-worktree session (`.git` is a file). In the
# main checkout itself (`.git` is a directory) there is no "other tree" to leak
# into, so the guard is a no-op. A git-fallback worktree (manual `git worktree
# add`, cwd not a native session) does not hit the trap either, but the main-tree
# cleanliness check is still valid there, so it runs in any linked worktree.
#
# Usage:
#   flow-worktree-guard.sh [--strict]
#
# Options:
#   --strict   Exit non-zero (3) ONLY when a main modification OVERLAPS a path
#              this run edited (the leak signature). Non-overlapping pre-existing
#              dirt never fails, even under --strict. Default is advisory:
#              always exit 0, just warn/note.
#
# Output:
#   - Overlap (leak): a "[flow] WARNING" block naming the overlapping paths with
#     a remediation hint (and, under --strict, exit 3).
#   - Non-overlap only: a quiet "[flow] note" listing the pre-existing main
#     modifications, exit 0.
#   - Nothing (exit 0) when main is clean or when not in a linked worktree.
#
# Env (test hook - unset in normal use):
#   FLOW_WORKTREE_GIT   override the `git` binary (default: git)

set -uo pipefail

GIT="${FLOW_WORKTREE_GIT:-git}"

STRICT=0
for arg in "$@"; do
  case "$arg" in
    --strict) STRICT=1 ;;
    --help|-h)
      sed -n '2,36p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "flow-worktree-guard.sh: unknown option '$arg'" >&2; exit 2 ;;
  esac
done

# Not a git repo -> nothing to check (fail-open).
if ! "$GIT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

# Distinguish a linked worktree from the main checkout: in a linked worktree the
# per-worktree git dir (--git-dir) differs from the shared common dir
# (--git-common-dir); in the main checkout they are the same. Only a linked
# worktree can leak edits into a *separate* main tree.
GIT_DIR="$("$GIT" rev-parse --path-format=absolute --git-dir 2>/dev/null || true)"
COMMON_DIR="$("$GIT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [ -z "$COMMON_DIR" ] || [ "$GIT_DIR" = "$COMMON_DIR" ]; then
  exit 0   # main checkout (or indeterminate) -> no separate tree to leak into.
fi

# The main working tree is the parent of the shared .git directory (standard,
# non-bare layout). Bail out fail-open if that does not resolve to a work tree.
MAIN_REPO="$(dirname "$COMMON_DIR")"
if ! "$GIT" -C "$MAIN_REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

WORKTREE_ROOT="$("$GIT" rev-parse --show-toplevel 2>/dev/null || true)"
if [ "$MAIN_REPO" = "$WORKTREE_ROOT" ]; then
  exit 0   # defensive: we somehow resolved to our own tree.
fi

# Tracked modifications in the MAIN working tree are the leaked-edit signature.
# --untracked-files=no keeps normal scratch/untracked noise out; the worktree's
# own files live under main's gitignored `.claude/worktrees/` and never appear
# here, so they cannot false-positive.
main_dirty=()
while IFS= read -r -d '' entry; do
  # porcelain -z: 2-char status, a space, then the path.
  path="${entry:3}"
  [ -n "$path" ] || continue
  main_dirty+=("$path")
done < <("$GIT" -C "$MAIN_REPO" status --porcelain --untracked-files=no -z 2>/dev/null)

if [ "${#main_dirty[@]}" -eq 0 ]; then
  exit 0
fi

# Not every dirty file in main is a leak: the main checkout often carries
# PRE-EXISTING local modifications unrelated to this run (e.g. deploy configs),
# and screaming "LEAKED" about them buries the real signal (issue #536). A dirty
# main file is a leak only when it ALSO appears among the paths THIS run edited -
# the run tried to touch that path, yet it shows up modified in main. So compute
# this run's edited set (branch commits vs the base + anything dirty in the
# worktree) and partition main-dirty into overlap (leak) vs unrelated (info).
run_edited=""
base_ref=""
for cand in origin/main main; do
  if "$GIT" rev-parse --verify --quiet "${cand}^{commit}" >/dev/null 2>&1; then
    base_ref="$cand"; break
  fi
done
if [ -n "$base_ref" ]; then
  mb="$("$GIT" merge-base HEAD "$base_ref" 2>/dev/null || true)"
  [ -n "$mb" ] && run_edited="$("$GIT" diff --name-only "$mb"..HEAD 2>/dev/null)"
fi
# Worktree dirt (staged/unstaged/new): strip status, keep the rename destination.
wt_dirty="$("$GIT" status --porcelain 2>/dev/null | sed 's/^...//' | sed 's/.* -> //')"
run_edited="$(printf '%s\n%s\n' "$run_edited" "$wt_dirty" | sed '/^$/d' | sort -u)"

overlap=()
unrelated=()
for p in "${main_dirty[@]}"; do
  if [ -n "$run_edited" ] && printf '%s\n' "$run_edited" | grep -qxF -- "$p"; then
    overlap+=("$p")
  else
    unrelated+=("$p")
  fi
done

# No overlap -> pre-existing/unrelated dirt in main. Downgrade to an info note
# (never a WARNING, never a --strict failure) so it stops drowning real signals.
if [ "${#overlap[@]}" -eq 0 ]; then
  echo "[flow] note: main has ${#unrelated[@]} modified tracked file(s) unrelated to this run's edits (pre-existing, not a leak; issue #536):" >&2
  for p in "${unrelated[@]}"; do
    echo "  - $p" >&2
  done
  echo "         main: $MAIN_REPO" >&2
  exit 0
fi

# Overlap -> a file this run edited is ALSO dirty in main: the leaked-edit
# signature (issue #486). Warn loudly (and fail under --strict).
echo "[flow] WARNING: ${#overlap[@]} file(s) this run edited are ALSO modified in the MAIN working tree:" >&2
echo "         main: $MAIN_REPO" >&2
for p in "${overlap[@]}"; do
  echo "  - $p" >&2
done
if [ "${#unrelated[@]}" -gt 0 ]; then
  echo "  (${#unrelated[@]} further pre-existing main modification(s) unrelated to this run - ignored.)" >&2
fi
echo "" >&2
echo "  An edit likely LEAKED into main instead of the worktree (issue #486)." >&2
echo "  Fix: resolve edit paths from 'git rev-parse --show-toplevel' (the worktree root)," >&2
echo "  never a hand-built '.claude/worktrees/<name>/...' absolute path. Move the change" >&2
echo "  into the worktree, then revert main:  git -C \"$MAIN_REPO\" checkout -- <path>" >&2
echo "  (If these are intentional edits to main, ignore this warning.)" >&2

if [ "$STRICT" -eq 1 ]; then
  exit 3
fi
exit 0
