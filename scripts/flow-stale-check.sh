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
#   flow-stale-check.sh [BASE_REF] [--no-fetch] [--exit-code]
#
#   BASE_REF     Ref to compare against (default: origin/main).
#   --no-fetch   Skip `git fetch` (offline / tests / already fetched).
#   --exit-code  Return non-zero (1) when a COLLISION is detected; still 0 for
#                "current" and "moved-clean". Default is always-0 (advisory).
#
# Output ends with a machine-readable verdict line:
#   FLOW_STALE_BASE: current | moved-clean | collision | unknown
#
# Env (test hook - unset in normal use):
#   FLOW_STALE_GIT   override the `git` binary (default: git)

set -uo pipefail

BASE_REF=""
DO_FETCH=1
WANT_EXIT_CODE=0
for arg in "$@"; do
    case "$arg" in
        --no-fetch)  DO_FETCH=0 ;;
        --exit-code) WANT_EXIT_CODE=1 ;;
        --help|-h)
            sed -n '2,33p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        --*)
            echo "flow-stale-check: unknown option: $arg" >&2
            exit 2
            ;;
        *)
            if [[ -z "$BASE_REF" ]]; then
                BASE_REF="$arg"
            else
                echo "flow-stale-check: unexpected argument: $arg" >&2
                exit 2
            fi
            ;;
    esac
done
BASE_REF="${BASE_REF:-origin/main}"
GIT_BIN="${FLOW_STALE_GIT:-git}"

git_() { "$GIT_BIN" "$@"; }
verdict() { echo "FLOW_STALE_BASE: $1"; }

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
if ! git_ rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "flow-stale-check: not inside a git work tree - skipping (advisory)." >&2
    verdict unknown
    exit 0
fi

# Best-effort refresh of the base's remote-tracking ref. A network hiccup must
# never break the flow - the check just runs against whatever ref is on disk.
if [[ "$DO_FETCH" -eq 1 ]]; then
    if [[ "$BASE_REF" == */* ]]; then
        remote="${BASE_REF%%/*}"
        rbranch="${BASE_REF#*/}"
        git_ fetch "$remote" "$rbranch" --quiet 2>/dev/null \
            || echo "flow-stale-check: 'git fetch $remote $rbranch' failed - using on-disk ref." >&2
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
    echo "  After merging the base in, regenerate the packaged copies:"
    echo "      scripts/plugin-sync.sh --write flow && python3 scripts/codex-prompt-sync.py --write flow"
    echo "  so the plugins/flow/ and codex/prompts/ copies do not drift (issue #506)."
fi

verdict "$result"

if [[ "$WANT_EXIT_CODE" -eq 1 && "$result" == "collision" ]]; then
    exit 1
fi
exit 0
