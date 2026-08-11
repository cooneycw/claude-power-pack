#!/usr/bin/env bash
# gh-pr-merge.sh - Squash-merge a PR robustly from any git worktree layout.
#
# Problem (issue #461):
#   From inside a LINKED worktree - a native `.claude/worktrees/<name>` checkout
#   or a legacy sibling dir - `gh pr merge <N> --squash --delete-branch` fails
#   AFTER the remote merge has already succeeded:
#
#     failed to run git: fatal: 'main' is already checked out at '<main-repo>'
#
#   gh, having merged and deleted the remote branch, tries to switch THIS worktree
#   off the now-gone branch onto the default branch - which is checked out in the
#   primary worktree, so the local checkout errors and gh exits non-zero. The
#   remote squash still landed (and `Closes #N` still fired); only gh's local
#   post-merge step failed. Callers that trust the exit code read this as a failed
#   merge and stop - a false negative that cost a full re-diagnosis on flow:auto
#   #433.
#
# Transient un-mergeability (issue #485):
#   Right after a `git push`, GitHub is still asynchronously computing the PR's
#   mergeability, so `gh pr view --json mergeable` returns UNKNOWN for a beat and a
#   raw `gh pr merge` fails with "Pull Request is not mergeable". That is a purely
#   transient blip - a re-check moments later returns MERGEABLE and the squash
#   succeeds. To stop that from being a false STOP, poll mergeability before the
#   merge: proceed only on MERGEABLE, hard-stop on a genuine CONFLICTING, and
#   fail-open (attempt the merge anyway) if it never resolves - the post-merge
#   MERGED-state check below stays the final backstop.
#
# Base moved at squash time (issue #502):
#   The pre-merge poll structurally cannot catch a sibling PR that merges in the
#   poll->merge race window: the squash then fails with "Base branch was
#   modified. Review and try the merge again." even though a refetch + re-attempt
#   succeeds moments later (observed live on the flow:auto #485 run itself). On
#   that specific error - and no other - refetch, re-poll mergeability, and
#   re-attempt the squash a bounded number of times before reporting failure.
#
# Branch protection blocks an owner merge (issue #517):
#   With main branch-protected (PR + review + CI required, the #449 posture), a
#   repo owner's squash is rejected by GitHub until it is re-run with --admin, so
#   every owner merge otherwise stalls at a manual `gh pr merge --squash --admin`.
#   Handle it two ways: an opt-in --admin flag that forces the override from the
#   first attempt, and - when a squash fails with a protection-block message, the
#   caller did not pass --admin, and the actor is a repo admin - a single
#   automatic retry with --admin. The override only ever fires for a repo admin,
#   only once, and the MERGED-state check below stays authoritative. --admin
#   bypasses every protection at once (including a red required check), so the
#   auto-retry is deliberately bounded and admin-gated.
#
# Required status checks are WAITED FOR, never overridden (issue #577, ADR 0004):
#   With a required status check on the base branch (CPP's posture makes the
#   Woodpecker PR pipeline required), a squash attempted the instant after a push
#   is rejected because the check has not reported yet. The #517 auto-retry above
#   would then "fix" that by merging with --admin - bypassing the very check the
#   posture exists to enforce, on every single run. That is protection theatre.
#   So: before merging, resolve the base branch's required contexts and POLL the
#   PR head until they are green; hard-stop on a genuinely red one; and exclude a
#   required-status-check block from the --admin auto-retry (a review block, the
#   #517 case, is unchanged). An explicit --admin from the caller still skips the
#   wait - a conscious owner override is the documented break-glass.
#
# The wait must never fire on contexts it only IMAGINED (issue #610):
#   The #577 resolver read one endpoint - classic branch protection - and threw
#   away its exit code. Two independent consequences, and both of them turned a
#   green PR into a 10-minute stall plus a hard refusal (25 flow:auto runs,
#   roughly 4h of wall-clock, every one ending in a manual `gh pr merge --squash`):
#     1. `gh api` prints the ERROR body on stdout WITHOUT applying --jq, so a 404
#        `{"message":"Branch not protected", ...}` was mapped straight into the
#        required-contexts list. The wait then polled for a context literally
#        named `{"message": ...` - which can never report - and hard-stopped.
#     2. GitHub declares required checks through TWO mechanisms, and the legacy
#        endpoint cannot see the modern one: a branch guarded by a repository
#        RULESET returns that same 404, so a repo that genuinely does require a
#        check reads as unprotected.
#   So resolution now reads BOTH sources - /branches/{b}/protection/... and
#   /repos/{o}/{r}/rules/branches/{b} - treats ONLY a 2xx response as data, and
#   reports one of three states: `declared` (wait, exactly as #577 does),
#   `none` (a source answered and nothing is required -> skip the wait), or
#   `unresolved` (neither source readable -> fall back to what the PR itself
#   reports). Enumeration failure is no longer allowed to outrank observed
#   reality, and the client-side wait is defence in depth: GitHub enforces the
#   posture server-side at squash time, so a plain `gh pr merge --squash` cannot
#   bypass a ruleset even when this script decides not to wait.
#
# This wrapper makes the merge layout-aware:
#   * Linked worktree (cwd's `.git` is a FILE): run `gh pr merge --squash` WITHOUT
#     --delete-branch so gh never attempts the local branch switch, then delete the
#     REMOTE branch ourselves (what --delete-branch would have done). Local worktree
#     + branch removal is left to the caller (worktree-remove.sh / ExitWorktree),
#     so the native cleanup path is unaffected.
#   * Primary repo (cwd's `.git` is a DIRECTORY): keep --delete-branch; the local
#     switch to the default branch is safe there.
#   * Either way, verify the PR actually reached MERGED before returning non-zero,
#     so a stray local post-merge error is never mistaken for a merge failure.
#
# Usage:  gh-pr-merge.sh [--admin] <pr-number> <branch-name>
#           --admin  force `gh pr merge --admin` from the first attempt - the
#                    conscious, HUMAN-TYPED branch-protection override (issues
#                    #517/#579). It skips the required-check wait AND the review
#                    gate. Without it, an admin override is applied automatically
#                    only for the residual ADMINISTRATIVE protection family
#                    (protected-branch / push-authorization / base-branch-policy
#                    blocks) - never for a required status check (#577) and never
#                    for a required review (#579): automation must not bypass a
#                    human-approval control.
# Deletion surfacing + post-merge completeness (issue #657):
#   A collapse onto a moved base (`git reset --soft origin/main` + commit, the
#   #655-thread workaround) silently records the DELETION of everything the
#   moved base added - poker-measure lost a merged 2,085-line feature this way
#   with a conflict-free merge and honestly-green CI. GitHub cannot distinguish
#   authored deletions from collapse damage at merge time (the damage IS inside
#   the PR's own file list - incident PR #234 listed all 40 paths), so this
#   helper does the two things that ARE sound here, both fail-open (#610
#   posture: enumeration failure never outranks observed reality):
#     * BEFORE the squash, surface every path the PR deletes vs its base -
#       `GH_PR_MERGE_DELETIONS: <n> <paths...>` (or `0`, or `skipped` when the
#       diff is unreadable) - so a reviewer/orchestrator sees "this squash
#       lands N deletions" while there is still time to stop. Opt-in
#       GH_PR_MERGE_STRICT_DELETIONS=1 turns any surfaced deletion into a
#       CLEAN pre-squash stop (exit 4, PR untouched).
#     * AFTER a confirmed merge, verify the landed squash commit touched ONLY
#       paths in the PR's file list - `GH_PR_MERGE_COMPLETENESS: ok|violation|
#       skipped`. A violation is LOUD but never flips the exit code (the merge
#       already landed); it catches base-race/squash contamination, and
#       honestly does NOT catch the collapse incident (damage inside the file
#       list) - that guard lives at collapse time (auto.md Step 6 recipe).
#   All git reads here are ref-scoped (`git -C <root>`, full refs, no bare
#   relative pathspecs) - the companion #657 finding: a cwd-drifted relative
#   pathspec reads as an empty diff, indistinguishable from "no changes".
#
# Exit:   0  the PR is merged on the remote
#         1  the PR genuinely did not merge (conflicts, red required check,
#            unresolvable state)
#         2  usage error (bad flag or missing pr-number/branch-name)
#         3  CLEAN STOP, not a failure (issue #579): merge awaits a human review
#            (reviewDecision REVIEW_REQUIRED or CHANGES_REQUESTED). The PR is
#            left open, current, and green - approve or merge it on GitHub, then
#            resume with /flow:merge (or re-run with an explicit --admin to
#            consciously override the review requirement).
#         4  CLEAN STOP, not a failure (issue #657): GH_PR_MERGE_STRICT_DELETIONS=1
#            is set and the PR deletes files vs its base. The PR is left open and
#            untouched - review the surfaced paths, then re-run without strict
#            mode (or fix the branch) once the deletions are confirmed intended.
#
# Env (test hooks - unset in normal use):
#   GH_PR_MERGE_GH             override the `gh` binary (default: gh)
#   GH_PR_MERGE_GIT            override the `git` binary (default: git)
#   GH_PR_MERGE_POLL_ATTEMPTS  mergeability poll attempts (default: 5)
#   GH_PR_MERGE_POLL_DELAY     seconds between poll attempts (default: 2)
#   GH_PR_MERGE_BASE_RETRY_ATTEMPTS  squash retries on "Base branch was modified" (default: 2)
#   GH_PR_MERGE_BASE_RETRY_DELAY     seconds before each such retry (default: 2)
#   GH_PR_MERGE_CHECK_ATTEMPTS       required-check poll attempts (default: 60)
#   GH_PR_MERGE_CHECK_DELAY          seconds between check polls (default: 10)
#
# Env (operator opt-in):
#   GH_PR_MERGE_STRICT_DELETIONS=1   turn surfaced deletions into the exit-4
#                                    clean pre-squash stop (issue #657)

set -uo pipefail

# Parse an optional --admin flag from anywhere in the argv, keeping the two
# positional args (pr-number, branch-name) backward-compatible for every caller.
ADMIN_OPT_IN=0
POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --admin)
            ADMIN_OPT_IN=1
            shift
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do POSITIONAL+=("$1"); shift; done
            ;;
        -*)
            echo "gh-pr-merge.sh: unknown option '$1'" >&2
            echo "Usage: gh-pr-merge.sh [--admin] <pr-number> <branch-name>" >&2
            exit 2
            ;;
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac
done

PR_NUMBER="${POSITIONAL[0]:-}"
BRANCH="${POSITIONAL[1]:-}"

if [[ -z "$PR_NUMBER" || -z "$BRANCH" ]]; then
    echo "Usage: gh-pr-merge.sh [--admin] <pr-number> <branch-name>" >&2
    exit 2
fi

GH_BIN="${GH_PR_MERGE_GH:-gh}"
GIT_BIN="${GH_PR_MERGE_GIT:-git}"

# stderr of the last `gh pr merge` attempt - inspected by is_protection_block.
LAST_MERGE_ERR=""

# A linked worktree has a `.git` FILE (a gitdir pointer); the primary repo has a
# `.git` DIRECTORY. This is the exact condition under which --delete-branch trips.
in_linked_worktree() { [[ -f .git ]]; }

# A squash rejected by branch protection (issue #517) vs. any other failure.
# Matches the required-review / required-status-check / protected-branch families
# GitHub returns, and deliberately NOT the #502 "Base branch was modified" text -
# that race has its own bounded retry and must never trigger an --admin override.
is_protection_block() {
    grep -qiE \
        'required status check|approving review|review is required|changes must be made through|protected branch|branch protection|not authorized to push|base branch policy|at least [0-9]+ (approving )?review' \
        <<<"$LAST_MERGE_ERR"
}

# A protection block caused specifically by a REQUIRED STATUS CHECK that is not
# green (issue #577). Distinguished from the review-required family above because
# the two want opposite handling: a review block is the #517 owner-authority case
# the --admin retry exists for, while a status-check block means CI has not passed
# - overriding it with --admin would defeat the posture on every run. This is the
# narrower match, so it is tested BEFORE the generic protection families.
is_required_check_block() {
    grep -qiE \
        'required status check|expected status check|status checks? (are|is) (expected|pending|failing)|checks? (are|is) still (pending|running|expected)' \
        <<<"$LAST_MERGE_ERR"
}

# A protection block caused specifically by a REQUIRED REVIEW (issue #579).
# Split out of the generic protection family because it must NEVER trigger the
# #517 --admin auto-retry: a review requirement is a human-approval control, and
# automation overriding it silently defeats the rule the owner set up. Only an
# explicit, human-typed --admin may do that. A match here becomes the exit-3
# clean stop instead.
is_review_block() {
    grep -qiE \
        'approving review|review is required|changes (have been |were )?requested|at least [0-9]+ (approving )?review' \
        <<<"$LAST_MERGE_ERR"
}

# Pre-squash review gate (issue #579): detect a review-blocked PR BEFORE
# attempting the merge, and hand off cleanly instead of failing or bypassing.
# Fail-open on an empty/unreadable reviewDecision (no review protection, or an
# API hiccup) - GitHub enforces the rule server-side at squash time regardless,
# and the is_review_block backstop below catches what this gate misses.
review_stop() {
    local decision="$1" pr_url
    pr_url=$("$GH_BIN" pr view "$PR_NUMBER" --json url --jq '.url' 2>/dev/null)
    echo "CLEAN STOP: PR #$PR_NUMBER awaits a human review (reviewDecision: $decision) - this is a handoff, NOT a failure (issue #579)." >&2
    echo "  The branch is synced and green; nothing more for automation to do." >&2
    echo "  Next: approve or merge the PR on GitHub: ${pr_url:-<gh pr view $PR_NUMBER --web>}" >&2
    echo "        then resume with /flow:merge." >&2
    echo "  To consciously override the review requirement instead (owner call):" >&2
    echo "        gh-pr-merge.sh --admin $PR_NUMBER $BRANCH" >&2
    exit 3
}

review_gate() {
    local decision
    decision=$("$GH_BIN" pr view "$PR_NUMBER" --json reviewDecision --jq '.reviewDecision' 2>/dev/null)
    case "$decision" in
        REVIEW_REQUIRED | CHANGES_REQUESTED)
            review_stop "$decision"
            ;;
    esac
    return 0
}

# True when the authenticated actor has admin permission on the repo - the only
# actor for whom `gh pr merge --admin` can override protection (issue #517).
is_repo_admin() {
    local perm
    perm=$("$GH_BIN" repo view --json viewerPermission --jq '.viewerPermission' 2>/dev/null)
    [[ "$perm" == "ADMIN" ]]
}

# Wait out a transient `mergeable=UNKNOWN` before attempting the squash (issue
# #485). Returns 0 to proceed (MERGEABLE, or fail-open after the poll never
# resolved), 1 to stop (genuine CONFLICTING).
poll_mergeable() {
    local attempts="${GH_PR_MERGE_POLL_ATTEMPTS:-5}"
    local delay="${GH_PR_MERGE_POLL_DELAY:-2}"
    local i mergeable
    for ((i = 1; i <= attempts; i++)); do
        mergeable=$("$GH_BIN" pr view "$PR_NUMBER" --json mergeable --jq '.mergeable' 2>/dev/null)
        case "$mergeable" in
            MERGEABLE)
                return 0
                ;;
            CONFLICTING)
                echo "error: PR #$PR_NUMBER is not mergeable (mergeable: CONFLICTING) -" \
                     "resolve the conflicts, then re-run." >&2
                return 1
                ;;
            *)
                # UNKNOWN or empty: GitHub is still computing mergeability. Wait and
                # retry, unless this was the last attempt (then fall through to
                # fail-open below).
                if [[ $i -lt $attempts ]]; then
                    sleep "$delay"
                fi
                ;;
        esac
    done
    # Never resolved - fail open: attempt the merge and let the post-merge
    # MERGED-state verification be the arbiter, rather than STOP on a transient.
    echo "note: mergeability still UNKNOWN for PR #$PR_NUMBER after $attempts" \
         "check(s); attempting the merge anyway (post-merge state check is the" \
         "backstop)." >&2
    return 0
}

# `gh api <path> --jq <filter>`, but ONLY a successful response counts as data
# (issue #610). On any non-2xx, gh writes the raw error body to STDOUT with the
# --jq filter unapplied, so a caller that ignores the exit code silently promotes
# `{"message":"Branch not protected"}` to a required status-check context. Return
# 1 printing nothing in that case, so an error can never be mistaken for a fact.
_gh_api_jq() {
    local path="$1" filter="$2" out rc
    out=$("$GH_BIN" api "$path" --jq "$filter" 2>/dev/null)
    rc=$?
    (( rc != 0 )) && return 1
    [[ -n "$out" ]] && printf '%s\n' "$out"
    return 0
}

# Resolution result, set by resolve_required_contexts:
#   REQUIRED_CONTEXTS  the contexts the base branch requires (may be empty)
#   RESOLVE_STATUS     declared | none | unresolved (see the header, issue #610)
REQUIRED_CONTEXTS=()
RESOLVE_STATUS="unresolved"

# The status-check contexts the BASE branch requires, read from BOTH mechanisms
# GitHub offers (issues #577, #610):
#   * classic branch protection - /branches/{base}/protection/required_status_checks,
#     in both its API shapes (the legacy `contexts` list and the newer
#     `checks[].context` form)
#   * repository rulesets - /repos/{o}/{r}/rules/branches/{base}, the modern
#     mechanism, entirely invisible to the endpoint above
# A source that 404s (or is not permitted) contributes NOTHING and does not mark
# the lookup as answered; only a 2xx does. That distinction is the whole fix: a
# branch with no protection of either kind gets a 200 + empty array from the
# rulesets endpoint, so it resolves as `none` and skips the wait, while a branch
# whose posture is simply unreadable resolves as `unresolved` and falls back to
# the PR's own checks rather than to a 10-minute stall.
resolve_required_contexts() {
    REQUIRED_CONTEXTS=()
    RESOLVE_STATUS="unresolved"

    local base out line
    base=$("$GH_BIN" pr view "$PR_NUMBER" --json baseRefName --jq '.baseRefName' 2>/dev/null)
    [[ -z "$base" ]] && return 0

    local -a found=()
    local answered=0

    if out=$(_gh_api_jq "repos/{owner}/{repo}/branches/${base}/protection/required_status_checks" \
                        '((.contexts // []) + ((.checks // []) | map(.context))) | unique | .[]'); then
        answered=1
        while IFS= read -r line; do
            [[ -n "$line" ]] && found+=("$line")
        done <<<"$out"
    fi

    if out=$(_gh_api_jq "repos/{owner}/{repo}/rules/branches/${base}" \
                        '[.[] | select(.type == "required_status_checks")
                              | .parameters.required_status_checks[]?.context] | unique | .[]'); then
        answered=1
        while IFS= read -r line; do
            [[ -n "$line" ]] && found+=("$line")
        done <<<"$out"
    fi

    # Union the two sources - a context declared by both must be waited on once.
    local -A seen=()
    local ctx
    for ctx in ${found+"${found[@]}"}; do
        [[ -n "${seen[$ctx]:-}" ]] && continue
        seen["$ctx"]=1
        REQUIRED_CONTEXTS+=("$ctx")
    done

    if (( ${#REQUIRED_CONTEXTS[@]} > 0 )); then
        RESOLVE_STATUS="declared"
    elif (( answered )); then
        RESOLVE_STATUS="none"
    else
        RESOLVE_STATUS="unresolved"
    fi
}

# Current state of each check on the PR head, as `name|state` lines. The rollup
# mixes two node types - a commit STATUS (context/state, what Woodpecker posts)
# and a GitHub CHECK RUN (name/status/conclusion) - so both are flattened to one
# shape. A check run that is still running has no conclusion yet; report its
# status so the poller treats it as pending rather than as an unknown.
check_states() {
    "$GH_BIN" pr view "$PR_NUMBER" --json statusCheckRollup \
        --jq '.statusCheckRollup[] | "\(.context // .name)|\(.state // .conclusion // .status // "PENDING")"' \
        2>/dev/null
}

# Wait for every required context to go green before the squash (issue #577).
# Returns 0 to proceed, 1 to stop. A required check that FAILS is a hard stop -
# never an --admin override - and so is one that never reports within the budget.
wait_for_required_checks() {
    resolve_required_contexts

    case "$RESOLVE_STATUS" in
        none)
            # A source answered and declares nothing required: pre-#577 behavior.
            return 0
            ;;
        unresolved)
            wait_for_observed_checks
            return $?
            ;;
    esac

    local -a required=("${REQUIRED_CONTEXTS[@]}")

    local attempts="${GH_PR_MERGE_CHECK_ATTEMPTS:-60}"
    local delay="${GH_PR_MERGE_CHECK_DELAY:-10}"
    local i ctx state line pending failed

    for ((i = 1; i <= attempts; i++)); do
        local -A states=()
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            states["${line%%|*}"]="${line##*|}"
        done < <(check_states)

        pending=""
        failed=""
        for ctx in "${required[@]}"; do
            state="${states[$ctx]:-MISSING}"
            case "${state^^}" in
                SUCCESS|NEUTRAL|SKIPPED)
                    ;;
                FAILURE|ERROR|CANCELLED|TIMED_OUT|ACTION_REQUIRED|STARTUP_FAILURE)
                    failed+="${ctx} (${state}) "
                    ;;
                *)
                    pending+="${ctx} (${state}) "
                    ;;
            esac
        done

        if [[ -n "$failed" ]]; then
            echo "error: required status check(s) are RED on PR #$PR_NUMBER: ${failed}" >&2
            echo "       Fix CI and push again - this is a required check, so it is" \
                 "never merged past automatically (issue #577, ADR 0004)." >&2
            return 1
        fi
        if [[ -z "$pending" ]]; then
            (( i > 1 )) && echo "note: required status check(s) are green; merging." >&2
            return 0
        fi
        if (( i < attempts )); then
            (( i == 1 )) && echo "note: waiting for required status check(s) on PR" \
                "#$PR_NUMBER: ${pending}" >&2
            sleep "$delay"
        fi
    done

    echo "error: required status check(s) never reported for PR #$PR_NUMBER after" \
         "$attempts check(s): ${pending}" >&2
    echo "       Not merging: overriding a required check would defeat the posture." \
         "If the pipeline genuinely will not run, the documented break-glass is" \
         "'gh-pr-merge.sh --admin $PR_NUMBER $BRANCH' (issue #577, ADR 0004)." >&2
    return 1
}

# Neither mechanism could be read (issue #610), so nothing is KNOWN to be
# required. Hard-stopping here is what cost 25 runs ~4h of waiting, so trust what
# the PR itself reports instead - the same rollup the declared path polls:
#   * no checks at all, or all of them terminal and green -> merge immediately
#   * any check genuinely RED                             -> hard stop; a red
#     check is authoritative on its own, whoever declared it
#   * still pending -> poll, then FAIL OPEN once the budget is spent. GitHub
#     enforces any ruleset/protection posture server-side at squash time, so the
#     squash itself is the real gate; a client-side guess must never be the thing
#     that blocks a PR whose posture it cannot even see.
wait_for_observed_checks() {
    local attempts="${GH_PR_MERGE_CHECK_ATTEMPTS:-60}"
    local delay="${GH_PR_MERGE_CHECK_DELAY:-10}"
    local i line name state pending failed announced=0

    for ((i = 1; i <= attempts; i++)); do
        pending=""
        failed=""
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            name="${line%%|*}"
            state="${line##*|}"
            case "${state^^}" in
                SUCCESS|NEUTRAL|SKIPPED)
                    ;;
                FAILURE|ERROR|CANCELLED|TIMED_OUT|ACTION_REQUIRED|STARTUP_FAILURE)
                    failed+="${name} (${state}) "
                    ;;
                *)
                    pending+="${name} (${state}) "
                    ;;
            esac
        done < <(check_states)

        if [[ -n "$failed" ]]; then
            echo "error: status check(s) are RED on PR #$PR_NUMBER: ${failed}" >&2
            echo "       Required contexts could not be enumerated (issue #610), but a red" \
                 "check is authoritative on its own - fix CI and push again." >&2
            return 1
        fi
        if [[ -z "$pending" ]]; then
            (( announced )) && echo "note: reported check(s) are green; merging." >&2
            return 0
        fi
        if (( i < attempts )); then
            if (( announced == 0 )); then
                echo "note: required status-check contexts are not enumerable for PR" \
                     "#$PR_NUMBER (no classic branch protection and no readable ruleset)" \
                     "- waiting on the check(s) the PR itself reports: ${pending}" >&2
                announced=1
            fi
            sleep "$delay"
        fi
    done

    echo "note: check(s) still pending on PR #$PR_NUMBER after $attempts check(s):" \
         "${pending}" >&2
    echo "      Not treating that as a required-check violation - the posture was never" \
         "enumerable, and GitHub enforces it server-side at squash time. Attempting the" \
         "merge (issue #610)." >&2
    return 0
}

if ! poll_mergeable; then
    exit 1
fi

# Pre-squash deletion surfacing (issue #657): print every path this PR deletes
# vs its base BEFORE the squash - and before the (possibly long) required-check
# wait, so the signal is out while there is still time to act on it - as one
# greppable marker line. Fail-open: an unreadable root/base/diff prints
# `skipped`, never silence and never a block. Ref-scoped reads only -
# `git -C <root>` with full refs, no bare relative pathspecs (the #657
# companion finding: a cwd-drifted relative pathspec reads as an empty diff,
# which is indistinguishable from "no deletions").
surface_deletions() {
    local root base deletions n
    root=$("$GIT_BIN" rev-parse --show-toplevel 2>/dev/null)
    base=$("$GH_BIN" pr view "$PR_NUMBER" --json baseRefName --jq '.baseRefName' 2>/dev/null)
    if [[ -z "$root" || -z "$base" ]]; then
        echo "GH_PR_MERGE_DELETIONS: skipped"
        return 0
    fi
    "$GIT_BIN" -C "$root" fetch origin "$base" --quiet 2>/dev/null || true
    if ! deletions=$("$GIT_BIN" -C "$root" diff --name-only --diff-filter=D "origin/${base}...HEAD" 2>/dev/null); then
        echo "GH_PR_MERGE_DELETIONS: skipped"
        return 0
    fi
    deletions=$(printf '%s\n' "$deletions" | sed '/^$/d')
    if [[ -z "$deletions" ]]; then
        echo "GH_PR_MERGE_DELETIONS: 0"
        return 0
    fi
    n=$(printf '%s\n' "$deletions" | wc -l | tr -d ' ')
    echo "GH_PR_MERGE_DELETIONS: $n $(printf '%s\n' "$deletions" | tr '\n' ' ' | sed 's/ $//')"
    echo "warning: this squash will land $n deletion(s) vs origin/${base} - confirm they are" >&2
    echo "         intended by PR #$PR_NUMBER, not a collapse onto a moved base (issue #657):" >&2
    printf '         deleted: %s\n' $deletions >&2
    if [[ "${GH_PR_MERGE_STRICT_DELETIONS:-0}" == "1" ]]; then
        echo "CLEAN STOP: GH_PR_MERGE_STRICT_DELETIONS=1 and the PR deletes files - not merging (issue #657)." >&2
        echo "  The PR is left open and untouched. Review the paths above; if the deletions are" >&2
        echo "  intended, re-run without strict mode." >&2
        exit 4
    fi
    return 0
}

surface_deletions

# An explicit --admin is a conscious owner override of protection, so it also
# skips the wait; without it, required checks must be green before the squash.
if (( ADMIN_OPT_IN == 0 )) && ! wait_for_required_checks; then
    exit 1
fi

# Review gate (issue #579): a required human review is a clean stop, never an
# automated bypass. An explicit --admin skips it - the same conscious-override
# semantics as the check wait above.
if (( ADMIN_OPT_IN == 0 )); then
    review_gate
fi

# Attempt the squash, retrying (bounded) only when the base moved under us at
# squash time (issue #502). Sets the global merge_exit; any error other than
# "Base branch was modified" is NOT retried, and the post-merge MERGED-state
# verification below remains the final arbiter either way.
run_squash() {
    # $@: extra gh flags (--delete-branch in the primary repo)
    local retries="${GH_PR_MERGE_BASE_RETRY_ATTEMPTS:-2}"
    local delay="${GH_PR_MERGE_BASE_RETRY_DELAY:-2}"
    local errfile attempt
    errfile=$(mktemp)
    for ((attempt = 0; attempt <= retries; attempt++)); do
        if (( attempt > 0 )); then
            echo "note: base branch moved under PR #$PR_NUMBER at squash time" \
                 "(sibling merge race, issue #502) - refetching and retrying" \
                 "(${attempt}/${retries})." >&2
            "$GIT_BIN" fetch origin >/dev/null 2>&1 || true
            sleep "$delay"
            # The sibling merge may have made the PR genuinely CONFLICTING -
            # re-poll so that stops us with the clear conflict message instead
            # of a retry that can never succeed.
            if ! poll_mergeable; then
                merge_exit=1
                break
            fi
        fi
        "$GH_BIN" pr merge "$PR_NUMBER" --squash "$@" 2>"$errfile"
        merge_exit=$?
        cat "$errfile" >&2
        LAST_MERGE_ERR=$(cat "$errfile")
        if [[ $merge_exit -eq 0 ]] || ! grep -q "Base branch was modified" "$errfile"; then
            break
        fi
    done
    rm -f "$errfile"
}

# Assemble the squash flags once: --admin if explicitly opted in, plus
# --delete-branch in the primary repo (a linked worktree deletes the remote
# branch itself below, to avoid the #461 local branch-switch failure).
BASE_FLAGS=()
(( ADMIN_OPT_IN )) && BASE_FLAGS+=(--admin)
in_linked_worktree || BASE_FLAGS+=(--delete-branch)

# Explicit squash subject + body, derived from the PR (issue #655): with no
# --subject, GitHub may title the squash commit from the branch's FIRST commit
# message - and #635's commit-first stale-base handling makes WIP-first branches
# routine, so finished features were landing on main as "WIP: ..." with an empty
# body. Passing both explicitly makes the squash message deterministic (the same
# "<PR title> (#N)" convention as GitHub's web squash button) regardless of
# branch history or per-repo squash-message settings. Fail-open: if the title
# cannot be read (API hiccup) or comes back empty, merge exactly as before - the
# merge must never be hostage to a metadata read - and the two flags are omitted
# TOGETHER, never one without the other.
SQUASH_TITLE=$("$GH_BIN" pr view "$PR_NUMBER" --json title --jq '.title' 2>/dev/null)
if [[ -n "$SQUASH_TITLE" ]]; then
    SQUASH_BODY=$("$GH_BIN" pr view "$PR_NUMBER" --json body --jq '.body' 2>/dev/null) || SQUASH_BODY=""
    BASE_FLAGS+=(--subject "${SQUASH_TITLE} (#${PR_NUMBER})" --body "$SQUASH_BODY")
fi

run_squash ${BASE_FLAGS+"${BASE_FLAGS[@]}"}

# Branch-protection auto-retry (issue #517): if the squash was rejected by branch
# protection, the caller did not already force --admin, and the actor is a repo
# admin, retry once with --admin. Any non-protection failure, or a non-admin
# actor, is left to the MERGED-state check below - never an --admin override.
#
# One protection family is deliberately EXCLUDED (issue #577): a required STATUS
# CHECK that is not green. The wait above already gave it every chance to pass, so
# a block here means CI is red or absent - and auto-overriding it would silently
# defeat the required check on every run. Only a human --admin may do that.
if [[ $merge_exit -ne 0 ]] && is_required_check_block; then
    echo "note: PR #$PR_NUMBER was blocked by a required status check - NOT retrying" \
         "with --admin (issue #577: a required check is waited for, never overridden" \
         "automatically)." >&2
elif [[ $merge_exit -ne 0 && $ADMIN_OPT_IN -eq 0 ]] && is_review_block; then
    # Belt-and-braces for the pre-squash review gate (issue #579): a review
    # block that slipped past it (empty reviewDecision, race) is the same
    # clean stop - NEVER the #517 --admin auto-retry.
    review_stop "review-blocked at squash time"
elif [[ $merge_exit -ne 0 && $ADMIN_OPT_IN -eq 0 ]] && is_protection_block && is_repo_admin; then
    echo "note: PR #$PR_NUMBER was blocked by an administrative branch-protection rule" \
         "(not a required check, not a required review) and the actor is a repo admin -" \
         "retrying the squash once with --admin (issue #517, narrowed by #577/#579)." >&2
    run_squash --admin ${BASE_FLAGS+"${BASE_FLAGS[@]}"}
fi

# In a linked worktree, delete the remote branch ourselves once the squash has
# landed - what --delete-branch would have done, minus the local branch switch
# that fails there (issue #461).
if in_linked_worktree && [[ $merge_exit -eq 0 ]]; then
    "$GIT_BIN" push origin --delete "$BRANCH" >/dev/null 2>&1 || true
fi

# Post-merge completeness verification (issue #657): the landed squash commit
# must touch ONLY paths in the PR's own file list. A violation is LOUD but never
# flips the exit code - the merge already landed, so this is a signal to
# investigate, not a failure to report (the #610 loud-never-obstructive posture).
# Honestly scoped: it catches base-race/squash contamination, NOT a collapse
# whose damage is inside the file list - that guard lives at collapse time.
# Fail-open per component: any unreadable input prints `skipped`, never silence.
verify_completeness() {
    local root merge_sha files landed extras path
    root=$("$GIT_BIN" rev-parse --show-toplevel 2>/dev/null)
    merge_sha=$("$GH_BIN" pr view "$PR_NUMBER" --json mergeCommit --jq '.mergeCommit.oid' 2>/dev/null)
    files=$("$GH_BIN" pr view "$PR_NUMBER" --json files --jq '.files[].path' 2>/dev/null)
    if [[ -z "$root" || -z "$merge_sha" || "$merge_sha" == "null" || -z "$files" ]]; then
        echo "GH_PR_MERGE_COMPLETENESS: skipped"
        return 0
    fi
    "$GIT_BIN" -C "$root" fetch origin --quiet 2>/dev/null || true
    if ! landed=$("$GIT_BIN" -C "$root" diff --name-only "${merge_sha}^" "$merge_sha" 2>/dev/null); then
        echo "GH_PR_MERGE_COMPLETENESS: skipped"
        return 0
    fi
    extras=""
    while IFS= read -r path; do
        [[ -z "$path" ]] && continue
        if ! grep -qxF "$path" <<<"$files"; then
            extras+="$path "
        fi
    done <<<"$landed"
    if [[ -n "$extras" ]]; then
        echo "GH_PR_MERGE_COMPLETENESS: violation"
        echo "warning: the landed squash ${merge_sha:0:7} touched path(s) OUTSIDE PR #$PR_NUMBER's" >&2
        echo "         file list (issue #657) - the merge landed, but investigate before building on it:" >&2
        printf '         unexpected: %s\n' $extras >&2
    else
        echo "GH_PR_MERGE_COMPLETENESS: ok"
    fi
    return 0
}

# Trust the PR state over the exit code: a non-zero from a local post-merge step
# must never mask a remote merge that actually succeeded.
state=$("$GH_BIN" pr view "$PR_NUMBER" --json state --jq '.state' 2>/dev/null)

if [[ "$state" == "MERGED" ]]; then
    if [[ $merge_exit -ne 0 ]]; then
        echo "note: gh exited $merge_exit but PR #$PR_NUMBER is MERGED - a local" \
             "post-merge step failed, not the merge itself. Continuing." >&2
        # Ensure the remote branch is gone even if the failure preceded our push.
        if in_linked_worktree; then
            "$GIT_BIN" push origin --delete "$BRANCH" >/dev/null 2>&1 || true
        fi
    fi
    verify_completeness
    echo "merged"
    exit 0
fi

echo "error: PR #$PR_NUMBER did not merge (state: ${state:-unknown})." >&2
exit 1
