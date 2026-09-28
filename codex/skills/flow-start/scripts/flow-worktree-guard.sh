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
# in main. Overlapping dirt -> a loud WARNING (and, when the overlapping file was
# itself touched within FRESH_MIN, a --strict failure - issue #576);
# non-overlapping dirt -> a quiet info note, never a failure.
#
# The one leak the overlap check cannot see is a TOTAL leak (issue #573): when
# EVERY edit lands in main, the worktree stays pristine, so "paths this run
# edited" is empty and nothing can overlap. That case is caught separately: if
# the run produced NO worktree activity at all (no branch commits, no worktree
# dirt) yet main carries tracked modifications edited within FRESH_MIN minutes,
# it is flagged as a total leak. Freshness (mtime) is what keeps this from
# re-crying-wolf on genuinely pre-existing main dirt (issue #536) - stale dirt
# with an idle worktree stays a quiet note.
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
#   --strict   Exit non-zero (3) on a FRESH leak signature: a main modification
#              that OVERLAPS a path this run edited and was itself modified within
#              FRESH_MIN, OR a total leak (idle worktree + fresh main edits, issue
#              #573). Freshness is the discriminator in BOTH branches (issue
#              #576): a leak is written during this run, while pre-existing dirt
#              on a shared file this run also edits is someone else's uncommitted
#              work and must not stop the run. Stale overlap and non-overlapping
#              dirt warn but never fail. Default is advisory: always exit 0, just
#              warn/note.
#
#              /flow:auto Steps 4 and 6 invoke this WITH --strict (issue #576):
#              a live leak means every further edit compounds and the commit the
#              flow is about to make does not contain the work, so exit 3 is a
#              STOP at both call sites, not a warning to narrate past.
#
# Output:
#   - Overlap (leak): a "[flow] WARNING" block naming the overlapping paths with
#     a remediation hint (and, under --strict, exit 3).
#   - Total leak (idle worktree + fresh main edits): a "[flow] WARNING" block
#     naming the fresh main paths (and, under --strict, exit 3) (issue #573).
#   - Non-overlap / stale only: a quiet "[flow] note" listing the pre-existing
#     main modifications, exit 0.
#   - Nothing else when main is clean.
#   - Always, as the last contract line (issue #1014), the verdict:
#       FLOW_WORKTREE_GUARD: no-leak | leak | unknown | not-applicable - <detail>
#     no-leak         looked: no leak SIGNATURE - main is clean, or its dirt
#                     matches none of this run's edits and none is fresh
#     leak            looked: a leak SIGNATURE - fresh main dirt overlapping this
#                     run's edits, or fresh main dirt beside an idle worktree.
#                     A signature, not proof of authorship: freshness and overlap
#                     cannot name the writer, so investigate before reverting main
#     not-applicable  nothing to examine: not in a git work tree, or this IS the
#                     main checkout (the current-branch lane), with no separate
#                     tree to leak into
#     unknown         could not examine: git missing or failing, or main's tree
#                     unreadable, or a freshness that could not be established (a
#                     path deleted in main, a failing `find`). NEVER rendered as
#                     no-leak - these used to share the silent `exit 0` of a clean
#                     pass. The verdict is computed the same with or without
#                     --strict; --strict only decides the exit.
#
# Exit under --strict (gate-lib's gate_map, #1014): no-leak 0, leak 3,
# unknown 4, not-applicable 5 - so a could-not-look answer can never share the
# good exit. /flow:auto Steps 4 and 6 STOP on 3 and PROCEED-AND-REPORT on 4 and
# 5. Without --strict the guard stays advisory and always exits 0, but it still
# prints the verdict.
#
# Env (test hook - unset in normal use):
#   FLOW_WORKTREE_GIT     override the `git` binary (default: git)
#   FLOW_LEAK_FRESH_MIN   freshness window in minutes for BOTH strict checks -
#                         the total-leak check (issue #573) and the overlap check
#                         (issue #576); default 30. A main modification blocks
#                         --strict only if edited within this window.

set -uo pipefail

#: NEGATIVE-CONTROL: controls/flow-worktree-guard

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
trap 'printf "FLOW_WORKTREE_GUARD_EXIT=%d\n" "$?" >&2' EXIT

# gate-lib is the one home for the exit mapping (#1126, #1014). `${0%/*}`, never
# `dirname`, for the reason shellcheck-gate.sh records: a PATH without it would
# leave the guard unable to load, and so unable to say `unknown`.
_gate_lib_dir=${0%/*}
[ "$_gate_lib_dir" = "$0" ] && _gate_lib_dir=.
# shellcheck disable=SC1091  # gate-lib.sh is resolved at run time and linted as its own file (#972)
. "$_gate_lib_dir/gate-lib.sh"
gate_map no-leak=0 leak=3 unknown=4 not-applicable=5

GIT="${FLOW_WORKTREE_GIT:-git}"
FRESH_MIN="${FLOW_LEAK_FRESH_MIN:-30}"

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

# verdict VERDICT DETAIL - print the contract line and exit per the declared map
# under --strict; advisory mode stays exit 0 but still says what it found.
verdict() {
  gate_emit FLOW_WORKTREE_GUARD "$1" "$2"
  if [ "$STRICT" -eq 1 ]; then gate_exit "$1"; fi
  exit 0
}

# freshness PATH -> fresh | stale | unknown (counter-model review of #1014). A
# failed or absent `find`, and a tracked path DELETED in main (nothing to stat),
# used to read as "no output" and so as stale, and stale reads as no-leak. A
# freshness that was never established is unknown, never stale.
freshness() {
  [ -e "$MAIN_REPO/$1" ] || { echo unknown; return; }
  command -v find >/dev/null 2>&1 || { echo unknown; return; }
  _f=$(find "$MAIN_REPO/$1" -maxdepth 0 -mmin "-${FRESH_MIN}" 2>/dev/null) || { echo unknown; return; }
  if [ -n "$_f" ]; then echo fresh; else echo stale; fi
}

# No git at all is could-not-look; not inside a work tree is nothing-to-look-at.
command -v "$GIT" >/dev/null 2>&1 || verdict unknown "git ('$GIT') is not on PATH"
# Only git's own "not a git repository" is not-applicable. Any other failure -
# corrupt metadata, a safe.directory ownership refusal, a broken binary - is git
# unable to answer, which is could-not-look (counter-model review).
if ! probe_out=$("$GIT" rev-parse --is-inside-work-tree 2>&1); then
  case "$probe_out" in
    *"not a git repository"*) verdict not-applicable "not inside a git work tree" ;;
    *) verdict unknown "git could not say whether this is a work tree: $(printf '%s' "$probe_out" | head -1)" ;;
  esac
fi

# Distinguish a linked worktree from the main checkout: in a linked worktree the
# per-worktree git dir (--git-dir) differs from the shared common dir
# (--git-common-dir); in the main checkout they are the same. Only a linked
# worktree can leak edits into a *separate* main tree.
GIT_DIR="$("$GIT" rev-parse --path-format=absolute --git-dir 2>/dev/null || true)"
COMMON_DIR="$("$GIT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
# These were ONE branch - `exit 0 # main checkout (or indeterminate)` - and are
# two different facts (#1014): the main checkout has nothing to leak into, while
# an unresolvable git dir means the guard could not look at all.
if [ -z "$COMMON_DIR" ] || [ -z "$GIT_DIR" ]; then
  verdict unknown "git could not resolve this checkout's git dir or common dir"
fi
if [ "$GIT_DIR" = "$COMMON_DIR" ]; then
  verdict not-applicable "this is the main checkout, with no separate tree to leak into"
fi

# The main working tree is the parent of the shared .git directory (standard,
# non-bare layout). Bail out fail-open if that does not resolve to a work tree.
MAIN_REPO="$(dirname "$COMMON_DIR")"
if ! "$GIT" -C "$MAIN_REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  verdict unknown "the main tree '$MAIN_REPO' is not a readable work tree"
fi

WORKTREE_ROOT="$("$GIT" rev-parse --show-toplevel 2>/dev/null || true)"
if [ "$MAIN_REPO" = "$WORKTREE_ROOT" ]; then
  verdict unknown "the main tree resolved to this worktree itself"
fi

# Tracked modifications in the MAIN working tree are the leaked-edit signature.
# --untracked-files=no keeps normal scratch/untracked noise out; the worktree's
# own files live under main's gitignored `.claude/worktrees/` and never appear
# here, so they cannot false-positive.
# Read into a file first so a FAILED status is seen (#1014): through a process
# substitution its exit status was discarded and an unreadable main read as a
# clean one.
main_status_file=$(mktemp) || verdict unknown "no temporary file for main's status"
if ! "$GIT" -C "$MAIN_REPO" status --porcelain --untracked-files=no -z >"$main_status_file" 2>/dev/null; then
  rm -f "$main_status_file"
  verdict unknown "git status of the main tree '$MAIN_REPO' failed"
fi
main_dirty=()
while IFS= read -r -d '' entry; do
  # porcelain -z: 2-char status, a space, then the path.
  path="${entry:3}"
  [ -n "$path" ] || continue
  main_dirty+=("$path")
done <"$main_status_file"
rm -f "$main_status_file"

if [ "${#main_dirty[@]}" -eq 0 ]; then
  verdict no-leak "main is clean"
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

# No overlap -> no main file matches a path this run edited. Two very different
# situations hide here, split on whether this run produced ANY worktree activity:
#
#  (a) run_edited NON-empty: the run IS producing work in the worktree, so main's
#      dirt is genuinely unrelated pre-existing modification (issue #536) -> quiet
#      note, never a failure. Unchanged behaviour.
#
#  (b) run_edited EMPTY: the run produced NOTHING in the worktree (no branch
#      commits, no worktree dirt) yet main has tracked modifications. That is the
#      TOTAL-LEAK signature (issue #573): a hand-built absolute path sent EVERY
#      edit to main, leaving the worktree pristine, so there is nothing for the
#      overlap check to match. Distinguish a fresh leak from merely pre-existing
#      main dirt by mtime - a leaked edit happened DURING this run (within
#      FRESH_MIN), pre-existing deploy-config dirt did not. Fresh + idle worktree
#      -> warn (and fail --strict); all-stale -> keep the quiet note.
if [ "${#overlap[@]}" -eq 0 ]; then
  if [ -n "$run_edited" ]; then
    # (a) classic #536: unrelated pre-existing dirt while the run works elsewhere.
    echo "[flow] note: main has ${#unrelated[@]} modified tracked file(s) unrelated to this run's edits (pre-existing, not a leak; issue #536):" >&2
    for p in "${unrelated[@]}"; do
      echo "  - $p" >&2
    done
    echo "         main: $MAIN_REPO" >&2
    verdict no-leak "no leak signature: ${#unrelated[@]} main modification(s) match none of this run's edits"
  fi

  # (b) total-leak suspect: worktree idle, main dirty. Keep only FRESH main edits.
  fresh=()
  undetermined=()
  for p in "${unrelated[@]}"; do
    case "$(freshness "$p")" in
      fresh)   fresh+=("$p") ;;
      unknown) undetermined+=("$p") ;;
    esac
  done

  if [ "${#fresh[@]}" -eq 0 ] && [ "${#undetermined[@]}" -gt 0 ]; then
    echo "[flow] note: the worktree is idle and ${#undetermined[@]} main modification(s) have no establishable freshness (deleted in main, or unreadable):" >&2
    for p in "${undetermined[@]}"; do echo "  - $p" >&2; done
    echo "         main: $MAIN_REPO" >&2
    verdict unknown "idle worktree; freshness of ${#undetermined[@]} main modification(s) could not be established"
  fi
  if [ "${#fresh[@]}" -eq 0 ]; then
    # All main dirt predates this run's window -> genuinely pre-existing, stay quiet.
    echo "[flow] note: main has ${#unrelated[@]} modified tracked file(s), none edited within the last ${FRESH_MIN}m (pre-existing, not a leak; issue #536/#573):" >&2
    for p in "${unrelated[@]}"; do
      echo "  - $p" >&2
    done
    echo "         main: $MAIN_REPO" >&2
    verdict no-leak "no leak signature: ${#unrelated[@]} stale main modification(s) with an idle worktree"
  fi

  # Fresh main edits with a completely idle worktree -> the total-leak signature.
  echo "[flow] WARNING: this run produced NO worktree changes, yet ${#fresh[@]} tracked file(s) were edited in MAIN within the last ${FRESH_MIN}m:" >&2
  echo "         main: $MAIN_REPO" >&2
  for p in "${fresh[@]}"; do
    echo "  - $p" >&2
  done
  echo "" >&2
  echo "  A TOTAL leak likely wrote EVERY edit into main instead of the worktree (issue #573/#486)." >&2
  echo "  Fix: resolve edit paths from 'git rev-parse --show-toplevel' (the worktree root)," >&2
  echo "  never a hand-built '.claude/worktrees/<name>/...' absolute path. Move the changes" >&2
  echo "  into the worktree, then revert main:  git -C \"$MAIN_REPO\" checkout -- <path>" >&2
  echo "  (If main was intentionally edited outside this run, ignore this warning.)" >&2
  verdict leak "total-leak signature: ${#fresh[@]} fresh main edit(s) with an idle worktree (writer unverified)"
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

# Overlap alone is not enough to BLOCK (issue #576). Overlap answers "did this run
# touch a path that is also dirty in main?", and that question has a second, common
# answer besides a leak: main was ALREADY carrying an uncommitted edit to a
# high-traffic shared file (CLAUDE.md, a template) before this run started, and the
# run legitimately edits that same file in its worktree. The advisory warning above
# is right to fire either way - a human should look - but exiting 3 on it would
# stop the run for someone else's dirty tree.
#
# Freshness is the discriminator, exactly as it already is for the total-leak
# branch (#573): a LEAKED edit is written to main DURING this run (within
# FRESH_MIN), while pre-existing dirt predates the window. So --strict fails only
# on FRESH overlap; stale overlap warns and exits 0. This is what makes promoting
# both /flow:auto call sites to --strict (#576) safe rather than a false-stop
# generator - the promotion was blocked on it during the #576 run itself, where
# main carried uncommitted retro edits to CLAUDE.md, a file that run had to edit.
# THE VERDICT IS THE SAME WITH OR WITHOUT --strict (counter-model review):
# --strict decides only the exit. Advisory mode used to call any overlap `leak`
# while --strict called a stale one `no-leak` - opposite facts, same input.
fresh_overlap=()
undetermined_overlap=()
for p in "${overlap[@]}"; do
  case "$(freshness "$p")" in
    fresh)   fresh_overlap+=("$p") ;;
    unknown) undetermined_overlap+=("$p") ;;
  esac
done
if [ "${#fresh_overlap[@]}" -gt 0 ]; then
  echo "" >&2
  echo "  ${#fresh_overlap[@]} of these were modified in main within the last ${FRESH_MIN}m" >&2
  echo "  (this run's window)$( [ "$STRICT" -eq 1 ] && echo ' - blocking.')" >&2
  verdict leak "overlap signature: ${#fresh_overlap[@]} fresh main modification(s) on paths this run edited (writer unverified)"
fi
if [ "${#undetermined_overlap[@]}" -gt 0 ]; then
  echo "" >&2
  echo "  The freshness of ${#undetermined_overlap[@]} overlapping path(s) could not be established" >&2
  echo "  (deleted in main, or unreadable) - reported as unknown, not as stale." >&2
  verdict unknown "overlap on ${#undetermined_overlap[@]} path(s) whose freshness could not be established"
fi
echo "" >&2
echo "  None of the overlapping file(s) were modified in main within the last ${FRESH_MIN}m," >&2
echo "  so this is pre-existing dirt rather than a leak from THIS run - warning only," >&2
echo "  not blocking (issue #576)." >&2
verdict no-leak "no fresh leak signature: ${#overlap[@]} stale overlap(s), pre-existing main dirt (issue #576)"

