#!/usr/bin/env bash
#
# speckit-tasks-to-issues.sh - Create GitHub issues from a spec-kit tasks.md
# using the gh CLI (CPP's Option-B sync; no github-mcp-server required).
#
# Part of Claude Power Pack (CPP). Replaces upstream /speckit-taskstoissues, which
# hard-requires the github-mcp-server. CPP is gh-CLI based, so this reproduces the
# same behaviour with `gh`:
#   - one label-free issue per task, titled "T001: <description>"
#   - dedup against existing issues by \bT\d{3}\b title match (re-run safe)
#   - refuses to run unless the git remote is a GitHub URL
#
# Usage:
#   scripts/speckit-tasks-to-issues.sh [--dry-run] [--tasks PATH] [--repo OWNER/NAME]
#
# Options:
#   --dry-run        Print what would be created; create nothing.
#   --tasks PATH     Path to tasks.md. Default: auto-detect the single
#                    .specify/specs/*/tasks.md, else error.
#   --repo OWNER/NM  Target repo for gh (default: the origin remote's repo).
#   -h, --help       Show this help.
set -euo pipefail

DRY_RUN=0
TASKS=""
REPO=""

usage() { sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --tasks) TASKS="${2:?--tasks needs a path}"; shift 2 ;;
        --repo) REPO="${2:?--repo needs OWNER/NAME}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

command -v gh > /dev/null 2>&1 || { echo "ERROR: gh CLI not found." >&2; exit 1; }

# --- Safety: only operate against a GitHub remote --------------------------------
REMOTE_URL="$(git config --get remote.origin.url 2>/dev/null || true)"
if [ -z "$REMOTE_URL" ]; then
    echo "ERROR: no git remote 'origin' found. Refusing to create issues." >&2
    exit 1
fi
case "$REMOTE_URL" in
    *github.com[:/]*) : ;;   # ok: https://github.com/o/r(.git) or git@github.com:o/r.git
    *) echo "ERROR: remote is not a GitHub URL ($REMOTE_URL). Refusing." >&2; exit 1 ;;
esac

# --- Locate tasks.md -------------------------------------------------------------
if [ -z "$TASKS" ]; then
    mapfile -t _candidates < <(find .specify/specs -maxdepth 2 -name tasks.md 2>/dev/null | sort)
    if [ "${#_candidates[@]}" -eq 0 ]; then
        echo "ERROR: no .specify/specs/*/tasks.md found. Pass --tasks PATH." >&2
        exit 1
    elif [ "${#_candidates[@]}" -gt 1 ]; then
        echo "ERROR: multiple tasks.md found; disambiguate with --tasks PATH:" >&2
        printf '  %s\n' "${_candidates[@]}" >&2
        exit 1
    fi
    TASKS="${_candidates[0]}"
fi
[ -f "$TASKS" ] || { echo "ERROR: tasks file not found: $TASKS" >&2; exit 1; }

GH_REPO_ARGS=()
[ -n "$REPO" ] && GH_REPO_ARGS=(--repo "$REPO")

echo "Tasks file: $TASKS"
echo "Remote:     $REMOTE_URL"
[ "$DRY_RUN" -eq 1 ] && echo "Mode:       DRY RUN (no issues will be created)"

# --- Existing issue IDs (dedup) --------------------------------------------------
# Match \bT\d{3}\b in existing titles (open + closed) so re-runs skip done tasks.
declare -A EXISTING
while IFS= read -r title; do
    if [[ "$title" =~ (^|[^A-Za-z0-9])(T[0-9]{3})([^0-9]|$) ]]; then
        EXISTING["${BASH_REMATCH[2]}"]=1
    fi
done < <(gh issue list "${GH_REPO_ARGS[@]}" --state all --limit 1000 --json title --jq '.[].title' 2>/dev/null || true)

# --- Parse tasks.md and create issues -------------------------------------------
created=0; skipped=0
while IFS= read -r line; do
    # Only checkbox task lines.
    [[ "$line" =~ ^-\ \[[\ xX]\] ]] || continue
    # Strip the checkbox (up to the first "] ") and any [P] / [US#] markers.
    body="${line#*] }"
    body="$(printf '%s' "$body" | sed -E 's/\[P\]//g; s/\[US[0-9]+\]//g; s/^[[:space:]]+//')"
    # Recover the task ID (T + 3 digits) and description.
    [[ "$body" =~ ^(T[0-9]{3})[:[:space:]]+(.*)$ ]] || continue
    tid="${BASH_REMATCH[1]}"
    desc="$(printf '%s' "${BASH_REMATCH[2]}" | sed -E 's/[[:space:]]+$//')"
    title="${tid}: ${desc}"

    if [ -n "${EXISTING[$tid]:-}" ]; then
        echo "skip  ${tid} (issue already exists)"
        skipped=$((skipped + 1))
        continue
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "would create: ${title}"
    else
        url="$(gh issue create "${GH_REPO_ARGS[@]}" --title "$title" --body "Auto-created from ${TASKS} (${tid}) by CPP speckit-tasks-to-issues." 2>&1)"
        echo "create ${tid} -> ${url}"
        EXISTING["$tid"]=1
    fi
    created=$((created + 1))
done < "$TASKS"

echo "---"
echo "Done. ${created} $([ "$DRY_RUN" -eq 1 ] && echo 'to create' || echo 'created'), ${skipped} skipped (already exist)."
