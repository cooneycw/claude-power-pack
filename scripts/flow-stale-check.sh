#!/usr/bin/env bash
# flow-stale-check.sh - Detect a STALE BASE early in the flow (issue #473).
#
# Problem:
#   /flow:auto's #462 guard only notices that `origin/main` moved at Step 7
#   (merge time). When sibling PRs land DURING implementation - the common case
#   for serialization hotspots (.claude/commands/flow/*.md, CHANGELOG.md, the
#   CLAUDE.md inventory) - the edits were made against stale versions of the very
#   files the siblings changed, forcing a `git reset`/`git merge` + re-apply cycle
#   regardless. Observed on flow:auto #444, #463, #461.
#
# This helper surfaces the collision EARLY (Step 4 start-of-implement and Step 6
# finish), NAMING which file(s) you have touched that also changed upstream, so
# you can merge `origin/main` in now - before more edits pile onto a stale base.
# It COMPLEMENTS the #462 Step-7 guard (which stays as the final backstop); it
# does not replace it.
#
# It is ADVISORY and FAIL-OPEN: it never blocks the flow (exit 0) unless
# --exit-code is passed, and a missing base ref / not-a-repo / fetch failure is
# reported and shrugged off, never fatal.
#
# Usage:
#   flow-stale-check.sh [BASE_REF] [CHECKOUT_PATH] [--path <dir>] [--no-fetch] [--exit-code]
#
#   BASE_REF       Ref to compare against (default: origin/main).
#   CHECKOUT_PATH  The checkout to inspect - DECLARED by the caller, not
#                  inferred (issue #614, the #592 rule): the Bash process cwd
#                  drifts on any earlier `cd`, and on flow:auto #597 this
#                  advisory silently answered for the MAIN repo while the
#                  run's worktree was behind. Also accepted as `--path <dir>`
#                  / `--path=<dir>`. Defaults to the process cwd (back-compat).
#   --no-fetch     Skip `git fetch` (offline / tests / already fetched).
#   --exit-code    Return non-zero (1) when a COLLISION is detected; still 0 for
#                  "current" and "moved-clean". Default is always-0 (advisory).
#
# Output ends with a machine-readable TWO-LINE contract, in this order - the
# path line immediately before the verdict line, both colon-space form (#614):
#   FLOW_STALE_PATH: <abs path of the tree inspected (as given, if unresolvable)>
#   FLOW_STALE_BASE: current | moved-clean | collision | unknown
# The path line is emitted on EVERY verdict, including the fail-open unknowns,
# so a cwd-drift mismatch is visible in the transcript even with the default.
#
# Env (test hook - unset in normal use):
#   FLOW_STALE_GIT   override the `git` binary (default: git)

set -uo pipefail

BASE_REF=""
CHECK_PATH=""
DO_FETCH=1
WANT_EXIT_CODE=0
EXPECT_PATH=0
for arg in "$@"; do
    if [[ "$EXPECT_PATH" -eq 1 ]]; then
        CHECK_PATH="$arg"
        EXPECT_PATH=0
        continue
    fi
    case "$arg" in
        --no-fetch)  DO_FETCH=0 ;;
        --exit-code) WANT_EXIT_CODE=1 ;;
        --path)      EXPECT_PATH=1 ;;
        --path=*)    CHECK_PATH="${arg#--path=}" ;;
        --help|-h)
            sed -n '2,45p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        --*)
            echo "flow-stale-check: unknown option: $arg" >&2
            exit 2
            ;;
        *)
            if [[ -z "$BASE_REF" ]]; then
                BASE_REF="$arg"
            elif [[ -z "$CHECK_PATH" ]]; then
                # Second positional = the checkout to inspect (issue #614).
                CHECK_PATH="$arg"
            else
                echo "flow-stale-check: unexpected argument: $arg" >&2
                exit 2
            fi
            ;;
    esac
done
if [[ "$EXPECT_PATH" -eq 1 ]]; then
    echo "flow-stale-check: --path requires a directory" >&2
    exit 2
fi
BASE_REF="${BASE_REF:-origin/main}"
CHECK_PATH="${CHECK_PATH:-.}"
GIT_BIN="${FLOW_STALE_GIT:-git}"

# Resolve the declared path for the contract line; keep the as-given form when
# it cannot be resolved so the fail-open verdict still names what was asked.
ABS_CHECK_PATH="$CHECK_PATH"
if [[ -d "$CHECK_PATH" ]]; then
    ABS_CHECK_PATH="$(cd "$CHECK_PATH" 2>/dev/null && pwd -P)" || ABS_CHECK_PATH="$CHECK_PATH"
fi

# Every git call runs against the DECLARED checkout, never the drifting
# process cwd (issue #614).
git_() { "$GIT_BIN" -C "$CHECK_PATH" "$@"; }
# The two-line contract, fixed order: path first, verdict second (#614).
verdict() {
    echo "FLOW_STALE_PATH: $ABS_CHECK_PATH"
    echo "FLOW_STALE_BASE: $1"
}

# True when FETCH_HEAD was written recently (within the last 5 minutes), i.e. a
# fetch already succeeded this run. Used to suppress the alarming "fetch failed"
# line when the on-disk ref is in fact fresh - the common sandbox-DNS case where
# an earlier fetch worked and only a redundant one failed (issue #536).
fetch_head_is_fresh() {
    local fh
    fh="$(git_ rev-parse --git-path FETCH_HEAD 2>/dev/null)" || return 1
    # `--git-path` output can be RELATIVE to the inspected checkout; with a
    # declared path (#614) the caller's cwd is a different tree, so re-anchor
    # a relative result against the checkout before probing it.
    [[ "$fh" = /* ]] || fh="$CHECK_PATH/$fh"
    [[ -s "$fh" ]] || return 1
    [[ -n "$(find "$fh" -mmin -5 2>/dev/null)" ]]
}

# Cap noisy lists so a large upstream diff does not scroll the whole flow away.
print_list() {
    local max=20 n=0 f
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        n=$((n + 1))
        [[ $n -le $max ]] && echo "    - $f"
    done <<< "$1"
    [[ $n -gt $max ]] && echo "    ... and $((n - max)) more"
    return 0
}

# --- Fail-open guards -------------------------------------------------------
if [[ ! -d "$CHECK_PATH" ]]; then
    echo "flow-stale-check: declared checkout '$CHECK_PATH' is not a directory - skipping (advisory)." >&2
    verdict unknown
    exit 0
fi
if ! git_ rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "flow-stale-check: '$ABS_CHECK_PATH' is not inside a git work tree - skipping (advisory)." >&2
    verdict unknown
    exit 0
fi

# Best-effort refresh of the base's remote-tracking ref. A network hiccup must
# never break the flow - the check just runs against whatever ref is on disk.
# On failure, cry wolf only when it matters: if a fetch already succeeded this
# run (fresh FETCH_HEAD) the on-disk ref is current, so stay silent; otherwise
# surface the ACTUAL git error instead of a generic line, so a blocked-DNS
# sandbox is distinguishable from a real fetch problem (issue #536).
if [[ "$DO_FETCH" -eq 1 ]]; then
    if [[ "$BASE_REF" == */* ]]; then
        remote="${BASE_REF%%/*}"
        rbranch="${BASE_REF#*/}"
        # Record freshness BEFORE the attempt: a failing fetch can itself clobber
        # FETCH_HEAD, which would otherwise erase the evidence that an earlier
        # fetch this run already succeeded.
        was_fresh=0; fetch_head_is_fresh && was_fresh=1
        if ! fetch_err="$(git_ fetch "$remote" "$rbranch" --quiet 2>&1)"; then
            if [[ "$was_fresh" -eq 0 ]] && ! fetch_head_is_fresh; then
                echo "flow-stale-check: 'git fetch $remote $rbranch' failed - using on-disk ref." >&2
                [[ -n "$fetch_err" ]] && printf '%s\n' "$fetch_err" | sed 's/^/  git: /' >&2
            fi
        fi
    else
        git_ fetch --quiet 2>/dev/null || true
    fi
fi

if ! git_ rev-parse --verify --quiet "${BASE_REF}^{commit}" >/dev/null 2>&1; then
    echo "flow-stale-check: base ref '$BASE_REF' not found - skipping (advisory)." >&2
    verdict unknown
    exit 0
fi

# --- Is the base ahead of us at all? ---------------------------------------
behind=$(git_ rev-list --count "HEAD..${BASE_REF}" 2>/dev/null || echo 0)
if [[ "${behind:-0}" -eq 0 ]]; then
    echo "flow-stale-check: base '$BASE_REF' is current (HEAD is not behind)."
    verdict current
    exit 0
fi

# --- The base moved. What changed upstream, and did it hit my edits? --------
# `git diff A...B` == `git diff $(git merge-base A B) B`, so:
#   HEAD...BASE  -> files changed on the BASE side since we diverged (upstream).
#   BASE...HEAD  -> files this branch changed since we diverged (my commits).
upstream_changed=$(git_ diff --name-only "HEAD...${BASE_REF}" 2>/dev/null | sed '/^$/d' | sort -u)
my_committed=$(git_ diff --name-only "${BASE_REF}...HEAD" 2>/dev/null)
# Anything dirty in the work tree counts as "touched" too (staged/unstaged/new).
# Strip the 2-char status + space; for renames "old -> new" keep the new path.
my_worktree=$(git_ status --porcelain 2>/dev/null | sed 's/^...//' | sed 's/.* -> //')
my_edits=$(printf '%s\n%s\n' "$my_committed" "$my_worktree" | sed '/^$/d' | sort -u)

if [[ -n "$my_edits" ]]; then
    collisions=$(printf '%s\n' "$my_edits" | grep -Fxf <(printf '%s\n' "$upstream_changed") 2>/dev/null || true)
else
    collisions=""
fi

# Secondary (issue #473): if a flow command file changed upstream, the global
# flow-* mirror will drift after you merge; remind to re-sync it.
flow_cmd_changed=$(printf '%s\n' "$upstream_changed" | grep -E '^\.claude/commands/flow/.*\.md$' || true)

echo "flow-stale-check: base '$BASE_REF' moved - HEAD is $behind commit(s) behind."

if [[ -n "$collisions" ]]; then
    echo ""
    echo "  COLLISION: file(s) you have edited ALSO changed on ${BASE_REF}:"
    print_list "$collisions"
    echo ""
    echo "  Merge the new base in NOW, before more edits pile onto a stale base:"
    echo "      git merge --no-edit ${BASE_REF}"
    echo "  (Resolve any conflict in the file(s) above, then continue.)"
    result="collision"
elif [[ -z "$my_edits" ]]; then
    # Step-4 case: nothing edited yet. Show what moved so you can merge proactively
    # before touching any of these files.
    echo ""
    echo "  Base moved but you have not edited anything yet. Changed upstream:"
    print_list "$upstream_changed"
    echo ""
    echo "  If you plan to touch any of these, merge the base in first:"
    echo "      git merge --no-edit ${BASE_REF}"
    result="moved-clean"
else
    echo "  No overlap: none of the file(s) you edited changed on ${BASE_REF}."
    echo "  Safe to continue; the Step-7 #462 guard merges the base in before the squash."
    result="moved-clean"
fi

if [[ -n "$flow_cmd_changed" ]]; then
    echo ""
    echo "  NOTE: flow command file(s) changed upstream:"
    print_list "$flow_cmd_changed"
    echo "  After merging the base in, regenerate the Codex skill copies:"
    echo "      python3 scripts/codex-skill-sync.py --write flow"
    echo "  so the codex/skills/ copies do not drift (issue #506; marketplace retired #662)."
fi

verdict "$result"

if [[ "$WANT_EXIT_CODE" -eq 1 && "$result" == "collision" ]]; then
    exit 1
fi
exit 0
