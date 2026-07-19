#!/usr/bin/env bash
# branch-protection.sh - declare, check, and apply a repo's branch-protection posture.
#
# Why (issue #577, ADR 0004):
#   Branch protection is otherwise an undocumented click-path: nobody can tell
#   from the repo whether "0 required checks" is a deliberate solo-operator
#   choice or an accident nobody noticed. This makes the posture DATA
#   (.claude/branch-protection.json), reviewable in a PR like anything else,
#   with a read-only drift check and a single idempotent apply.
#
# Posture of record for CPP (ADR 0004): the Woodpecker PR pipeline is a REQUIRED
# status check, reviews stay at 0 (solo repo - a review requirement would force
# --admin on every merge, and --admin bypasses the CI check at the same time),
# and enforce_admins stays OFF so the owner keeps a documented break-glass for a
# pipeline that never reports. gh-pr-merge.sh is what makes the required check
# real rather than theatre: it WAITS for the check instead of overriding it.
#
# Usage:
#   branch-protection.sh [check]            compare live protection to the declared
#                                           posture; exit 0 in sync, 1 on drift
#   branch-protection.sh --apply            PUT the declared posture (idempotent)
#   branch-protection.sh --show             print the normalized live posture
#
#   --config <path>   posture file (default: .claude/branch-protection.json)
#   --repo <o/n>      target repo (default: the cwd's repo, via gh's {owner}/{repo})
#
# Exit: 0 ok / in sync, 1 drift or failure, 2 usage error.
#
# Env (test hooks - unset in normal use):
#   BRANCH_PROTECTION_GH   override the `gh` binary (default: gh)

set -uo pipefail

GH_BIN="${BRANCH_PROTECTION_GH:-gh}"
CONFIG=".claude/branch-protection.json"
REPO=""
MODE="check"

while [[ $# -gt 0 ]]; do
    case "$1" in
        check)    MODE="check"; shift ;;
        --apply)  MODE="apply"; shift ;;
        --show)   MODE="show"; shift ;;
        --config) CONFIG="${2:-}"; shift 2 ;;
        --repo)   REPO="${2:-}"; shift 2 ;;
        -h|--help)
            sed -n '2,30p' "$0"
            exit 0
            ;;
        *)
            echo "branch-protection.sh: unknown argument '$1'" >&2
            echo "Usage: branch-protection.sh [check|--apply|--show] [--config <path>] [--repo <owner/name>]" >&2
            exit 2
            ;;
    esac
done

if ! command -v jq >/dev/null 2>&1; then
    echo "branch-protection.sh: jq is required (see 'make bootstrap-check')." >&2
    exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
    echo "branch-protection.sh: posture file not found: $CONFIG" >&2
    exit 1
fi

BRANCH=$(jq -r '.branch // "main"' "$CONFIG")
# gh expands the {owner}/{repo} placeholders from the cwd's remote; an explicit
# --repo overrides that for a repo you are not standing in.
if [[ -n "$REPO" ]]; then
    SLUG="$REPO"
else
    SLUG='{owner}/{repo}'
fi
API_PATH="repos/$SLUG/branches/$BRANCH/protection"

# The keys this posture governs, normalized to one shape so the live GitHub
# representation (nested {"enabled": bool} objects) and the declared file (plain
# booleans) are comparable. Keys NOT listed here are deliberately unmanaged.
normalize_live() {
    jq -S '{
      required_status_checks: (
        if .required_status_checks == null then null else {
          strict: (.required_status_checks.strict // false),
          contexts: ((
            (.required_status_checks.contexts // [])
            + ((.required_status_checks.checks // []) | map(.context))
          ) | unique)
        } end),
      required_pull_request_reviews: (
        if .required_pull_request_reviews == null then null else {
          dismiss_stale_reviews: (.required_pull_request_reviews.dismiss_stale_reviews // false),
          require_code_owner_reviews: (.required_pull_request_reviews.require_code_owner_reviews // false),
          required_approving_review_count: (.required_pull_request_reviews.required_approving_review_count // 0)
        } end),
      enforce_admins: (.enforce_admins.enabled // false),
      allow_force_pushes: (.allow_force_pushes.enabled // false),
      allow_deletions: (.allow_deletions.enabled // false)
    }'
}

normalize_declared() {
    jq -S '.protection | {
      required_status_checks: (
        if .required_status_checks == null then null else {
          strict: (.required_status_checks.strict // false),
          contexts: ((.required_status_checks.contexts // []) | unique)
        } end),
      required_pull_request_reviews: (
        if .required_pull_request_reviews == null then null else {
          dismiss_stale_reviews: (.required_pull_request_reviews.dismiss_stale_reviews // false),
          require_code_owner_reviews: (.required_pull_request_reviews.require_code_owner_reviews // false),
          required_approving_review_count: (.required_pull_request_reviews.required_approving_review_count // 0)
        } end),
      enforce_admins: (.enforce_admins // false),
      allow_force_pushes: (.allow_force_pushes // false),
      allow_deletions: (.allow_deletions // false)
    }'
}

fetch_live() {
    # An UNPROTECTED branch 404s; report that as the empty posture rather than an
    # error, so `check` says "drift" (nothing is protected) instead of dying.
    local out
    out=$("$GH_BIN" api "$API_PATH" 2>/dev/null)
    if [[ -z "$out" ]] || ! jq -e . >/dev/null 2>&1 <<<"$out"; then
        echo "{}"
        return 0
    fi
    printf '%s\n' "$out"
}

case "$MODE" in
    show)
        fetch_live | normalize_live
        exit 0
        ;;
    apply)
        # PUT the declared payload verbatim (minus the wrapper keys). The GitHub
        # API replaces the whole protection object, so this is idempotent: the
        # same file always produces the same posture.
        if ! jq -c '.protection' "$CONFIG" |
                "$GH_BIN" api --method PUT "$API_PATH" --input - >/dev/null; then
            echo "BRANCH_PROTECTION: apply-failed ($SLUG $BRANCH)" >&2
            exit 1
        fi
        echo "Applied declared posture to $BRANCH:"
        fetch_live | normalize_live
        echo "BRANCH_PROTECTION: applied"
        exit 0
        ;;
    check)
        live=$(fetch_live | normalize_live)
        declared=$(normalize_declared <"$CONFIG")
        if [[ "$live" == "$declared" ]]; then
            echo "BRANCH_PROTECTION: in-sync ($BRANCH matches $CONFIG)"
            exit 0
        fi
        echo "Branch protection on '$BRANCH' has drifted from $CONFIG." >&2
        echo "--- declared" >&2
        printf '%s\n' "$declared" >&2
        echo "--- live" >&2
        printf '%s\n' "$live" >&2
        echo "Reconcile with: make branch-protection-apply" >&2
        echo "BRANCH_PROTECTION: drift" >&2
        exit 1
        ;;
esac
