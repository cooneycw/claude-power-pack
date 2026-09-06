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
# Base moved DURING the required-check wait (issue #767):
#   /flow:auto syncs the branch with the base and re-runs the quality gate before
#   invoking this helper, but the required-check wait can then last several
#   minutes. A sibling PR can advance the base during that window, leaving the
#   checks green for a tree that is no longer the tree the squash would land.
#   Snapshot the fetched base tip before the non-admin wait and compare it after
#   the checks succeed. An unchanged tip, or a new tip already contained in HEAD,
#   proceeds; unreadable snapshots fail open. A changed tip not contained in HEAD
#   is a clean exit-6 stop before the review gate or squash work. The explicit
#   --allow-base-move flag is the loud, per-merge override; --admin skips this
#   guard together with the queue and required-check waits it already bypasses.
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
# Usage:  gh-pr-merge.sh [--admin] [--allow-negated-close] [--allow-incidental-close] [--allow-base-move] <pr-number> <branch-name>
#           --admin  force `gh pr merge --admin` from the first attempt - the
#                    conscious, HUMAN-TYPED branch-protection override (issues
#                    #517/#579). It skips the required-check wait AND the review
#                    gate. Without it, an admin override is applied automatically
#                    only for the residual ADMINISTRATIVE protection family
#                    (protected-branch / push-authorization / base-branch-policy
#                    blocks) - never for a required status check (#577) and never
#                    for a required review (#579): automation must not bypass a
#                    human-approval control.
#           --allow-negated-close  consciously bypass the issue #726 refusal
#                    after the detected trigger and surrounding text are printed;
#                    this is a loud, per-merge override, never persistent config.
#           --allow-incidental-close  consciously bypass the issue #794 refusal
#                    (a close/fix/resolve keyword adjacent to #N that reads as
#                    incidental, not a directive) after the detected trigger and
#                    surrounding text are printed; loud, per-merge, never
#                    persistent config.
#           --allow-base-move  consciously bypass the issue #767 clean stop when
#                    the base advances during the required-check wait; the moved
#                    tips and an override-consumed audit line are still printed.
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
# Negated close keywords still close issues (issues #726 and #772):
#   GitHub matches a literal close/fix/resolve keyword plus `#N` even when prose
#   negates it, so "does not close #N" closes the issue when the squash lands.
#   Author-time prose cannot reliably prevent that composition trap. Immediately
#   before the squash, scan the exact title/body being sent, trim each keyword's
#   prefix at the nearest sentence or clause boundary, and recognize only an
#   adjacent negation with at most two intervening words. CLEAN STOP before any
#   merge attempt. The per-invocation --allow-negated-close escape hatch stays
#   loud: it prints every detected issue/context plus an audit line before
#   deliberately proceeding.
#
# Incidental proximity also closes issues, and every PR commit is a surface
# (issue #794): GitHub matches close/fix/resolve + #N by proximity, ignoring
# grammar - a keyword that is not a directive at all, merely adjacent, still
# closes on squash. Two real near-misses: a commit subject where the keyword was
# an ADJECTIVE ("...with the resolved #N/topic finding") and a PR body where the
# keyword governed a different noun ("closes #N's investigation against..."),
# neither negated so #726's guard does not see them. A closing directive is
# conventionally the whole clause (`Closes #N` at a line/clause start); flag
# instead when the keyword is NOT clause-initial, or when #N is immediately
# followed by a possessive or a slash-compound modifier (the two concrete shapes
# above), on the title, body, AND every commit subject on the PR branch - the
# squash composes its message from the PR's own commits whenever neither
# --subject nor --body is supplied (issue #716 above), so a `git commit -m`
# typed inline is exactly as much a closing surface as the PR description, and
# never passes through whatever review the body gets. Same CLEAN STOP shape as
# #726, and its own --allow-incidental-close escape hatch. The guard verifies
# its own classifier against a fixed, unreachable-numbered self-check pair
# before trusting a clean scan - a scan that silently cannot run must never
# read the same as a scan that ran and found nothing (this repo has hit exactly
# that failure mode before: a regex that could not compile printed no output
# and was indistinguishable from a clean result).
#
# Squash-commit trailer carries the tested tree hash (issue #716):
#   poker-measure's CI throughput on its single shared Woodpecker agent
#   (WOODPECKER_MAX_WORKFLOWS=2) is capped enough that every squash-to-main
#   re-runs the full suite and competes for a scarce slot with the next PR's
#   pipeline (poker-measure#236). When this PR's branch was up to date with
#   its base at squash time - no intervening base commits since the branch
#   point - the squashed tree is PROVABLY identical to the PR head that
#   already passed CI, so this helper appends a git trailer naming the TESTED
#   TREE HASH: `Woodpecker-Tested-Tree: <sha1 of HEAD^{tree}>`. Deliberately
#   NOT a boolean trailer - `gh pr merge --squash` composes the squash body
#   from the PR's own commits when neither --subject nor --body is given, so
#   a bare `Woodpecker-Skip-Full-Test: true` typed into ANY commit message
#   would silently propagate and skip the consuming CI's full suite with this
#   script's up-to-date check never consulted. The tree hash is
#   self-verifying instead: the consumer (poker-measure/.woodpecker.yml)
#   recomputes `git rev-parse HEAD^{tree}` on the squash commit it just
#   checked out and skips only when it EQUALS this value - forging a skip
#   then requires naming the exact tree hash of genuinely matching content.
#   Fail-open per component (the #610 posture): an unreadable base, an
#   unresolvable ancestry check, or a branch behind its base all omit the
#   trailer, and the consumer's push pipeline runs the full suite - the safe
#   default either way.
#
# Poll window vs. CI queue depth (issue #717):
#   The required-check poll below (GH_PR_MERGE_CHECK_ATTEMPTS x
#   GH_PR_MERGE_CHECK_DELAY) counts from when polling STARTS, not from when
#   the pipeline is actually picked up - so on the same shared 2-worker
#   Woodpecker agent, a PR that sits queued behind others eats into the same
#   budget as one that is genuinely stuck. Measured the same night: 8 of 8
#   poker-measure merges needed exactly one retry - a deterministic tax, not
#   an intermittent fault. GitHub's classic commit-status API - what
#   Woodpecker posts (`ci/woodpecker/pr/woodpecker`) - has no queued-vs-
#   running distinction in its `state` field (only GitHub Check Runs expose
#   that), so the fix asks Woodpecker's OWN pipeline API instead: when
#   WOODPECKER_API_TOKEN is set (the same credential /flow:auto Step 8 uses
#   for post-merge CI verification), wait out a QUEUED pipeline on a separate
#   bounded budget (GH_PR_MERGE_QUEUE_WAIT_ATTEMPTS x
#   GH_PR_MERGE_QUEUE_WAIT_DELAY) before the existing check-poll budget
#   starts counting - so that budget only has to cover genuine run time.
#   Entirely fail-open: no token, no curl/jq, an unresolvable repo id, or no
#   matching pipeline all fall straight through to the unchanged pre-#717
#   poll. This can only ever shrink the effective wait; it is never a new way
#   to stop the merge.
#
# Stacked dependent PRs are retargeted before branch deletion (poker-measure#405):
#   During the 2026-08-20 poker wave merge drain, squash-merging PR #375 through
#   this helper deleted its branch and GitHub auto-closed open PR #382, whose base
#   was that branch, in the same second. GitHub retargets stacked children only
#   in its web-UI merge flow, not when the API/CLI squash and branch deletion used
#   here remove the base ref. Before any squash attempt, enumerate every open PR
#   based on `$BRANCH` and retarget it to the repo's resolved default branch; the
#   temporarily inflated child diff self-corrects after the parent lands. The
#   operation is non-destructive and fail-open per the #610 posture: unreadable
#   enumeration/default metadata prints `GH_PR_MERGE_STACKED_RETARGET: skipped`,
#   while successful edits print `GH_PR_MERGE_STACKED_RETARGET: <n> <PRs...>`;
#   one failed child edit warns but never blocks the remaining edits or merge.
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
#         5  CLEAN STOP, not a failure (issue #726): the squash title, body, or a
#            commit subject on the branch has a negated close/fix/resolve
#            keyword that GitHub would still honor. The PR is left open and
#            untouched - reword it or consciously re-run with
#            --allow-negated-close after reviewing the printed context.
#         6  CLEAN STOP, not a failure (issue #767): the base advanced during the
#            required-check wait and its new tip is not contained in HEAD. The PR
#            is left open and untouched - sync the base, re-run the quality gate,
#            push, and re-run the merge (or consciously use --allow-base-move).
#         7  CLEAN STOP, not a failure (issue #794): the squash title, body, or a
#            commit subject on the branch has a close/fix/resolve keyword
#            adjacent to #N that is not actually a directive (not clause-
#            initial, or #N is immediately followed by a possessive or a
#            slash-compound). The PR is left open and untouched - reword it or
#            consciously re-run with --allow-incidental-close after reviewing
#            the printed context.
#         8  the incidental-close classifier (issue #794) failed its own
#            self-check - this is a BROKEN CHECK, not a clean scan, and is
#            never conflated with "no hazard found". Investigate the guard
#            itself before re-running; there is no override for this one.
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
#   GH_PR_MERGE_CURL                 override the `curl` binary (default: curl)
#   GH_PR_MERGE_QUEUE_WAIT_ATTEMPTS  Woodpecker queued-pipeline poll attempts
#                                    before the check-poll budget starts (default: 30)
#   GH_PR_MERGE_QUEUE_WAIT_DELAY     seconds between queued-pipeline polls (default: 10)
#
# Env (optional integration, issue #717):
#   WOODPECKER_API_TOKEN      enables the queued-pipeline wait; unset skips it
#                              entirely (same credential /flow:auto Step 8 uses)
#   WOODPECKER_SERVER         Woodpecker base URL (default: https://woodpecker.essent-ai.com)
#
# Env (operator opt-in):
#   GH_PR_MERGE_STRICT_DELETIONS=1   turn surfaced deletions into the exit-4
#                                    clean pre-squash stop (issue #657)

set -uo pipefail

# Parse optional per-invocation flags from anywhere in the argv, keeping the two
# positional args (pr-number, branch-name) backward-compatible for every caller.
ADMIN_OPT_IN=0
ALLOW_NEGATED_CLOSE=0
ALLOW_INCIDENTAL_CLOSE=0
ALLOW_BASE_MOVE=0
POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --admin)
            ADMIN_OPT_IN=1
            shift
            ;;
        --allow-negated-close)
            ALLOW_NEGATED_CLOSE=1
            shift
            ;;
        --allow-incidental-close)
            ALLOW_INCIDENTAL_CLOSE=1
            shift
            ;;
        --allow-base-move)
            ALLOW_BASE_MOVE=1
            shift
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do POSITIONAL+=("$1"); shift; done
            ;;
        -*)
            echo "gh-pr-merge.sh: unknown option '$1'" >&2
            echo "Usage: gh-pr-merge.sh [--admin] [--allow-negated-close] [--allow-incidental-close] [--allow-base-move] <pr-number> <branch-name>" >&2
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
    echo "Usage: gh-pr-merge.sh [--admin] [--allow-negated-close] [--allow-incidental-close] [--allow-base-move] <pr-number> <branch-name>" >&2
    exit 2
fi

GH_BIN="${GH_PR_MERGE_GH:-gh}"
GIT_BIN="${GH_PR_MERGE_GIT:-git}"
CURL_BIN="${GH_PR_MERGE_CURL:-curl}"

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

    local out line
    [[ -z "$PR_BASE_BRANCH" ]] && return 0

    local -a found=()
    local answered=0

    if out=$(_gh_api_jq "repos/{owner}/{repo}/branches/${PR_BASE_BRANCH}/protection/required_status_checks" \
                        '((.contexts // []) + ((.checks // []) | map(.context))) | unique | .[]'); then
        answered=1
        while IFS= read -r line; do
            [[ -n "$line" ]] && found+=("$line")
        done <<<"$out"
    fi

    if out=$(_gh_api_jq "repos/{owner}/{repo}/rules/branches/${PR_BASE_BRANCH}" \
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

# Resolve the Woodpecker repo id once (issue #717). Sets WOODPECKER_REPO_ID /
# WOODPECKER_SERVER_RESOLVED on success. Fails (return 1) - and stays failed
# for the rest of the run - on a missing token, a missing curl/jq, or an
# unresolvable repo; every caller must treat that as "skip the queue wait
# entirely", never as a merge blocker.
WOODPECKER_REPO_ID=""
WOODPECKER_SERVER_RESOLVED=""
woodpecker_repo_id() {
    [[ -n "$WOODPECKER_REPO_ID" ]] && return 0
    [[ -z "${WOODPECKER_API_TOKEN:-}" ]] && return 1
    command -v "$CURL_BIN" >/dev/null 2>&1 || return 1
    command -v jq >/dev/null 2>&1 || return 1
    local server repo_full raw id
    server="${WOODPECKER_SERVER:-https://woodpecker.essent-ai.com}"
    repo_full=$("$GH_BIN" repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null)
    [[ -z "$repo_full" ]] && return 1
    raw=$("$CURL_BIN" -sf -H "Authorization: Bearer $WOODPECKER_API_TOKEN" \
        -H "Accept: application/json" "${server}/api/repos/lookup/${repo_full}" 2>/dev/null) || return 1
    id=$(jq -r '.id // empty' <<<"$raw" 2>/dev/null)
    [[ -z "$id" || "$id" == "null" ]] && return 1
    WOODPECKER_REPO_ID="$id"
    WOODPECKER_SERVER_RESOLVED="$server"
    return 0
}

# The status ("pending" | "running" | "success" | "failure" | ...) of the
# Woodpecker pipeline for the current HEAD commit - the PR's pushed head,
# under the same HEAD-is-PR-head assumption the #716 trailer relies on.
# Prints nothing (and the caller must fail-open) on any unreadable input.
woodpecker_pipeline_status() {
    local sha raw
    sha=$("$GIT_BIN" rev-parse HEAD 2>/dev/null)
    [[ -z "$sha" ]] && return 1
    raw=$("$CURL_BIN" -sf -H "Authorization: Bearer $WOODPECKER_API_TOKEN" \
        -H "Accept: application/json" \
        "${WOODPECKER_SERVER_RESOLVED}/api/repos/${WOODPECKER_REPO_ID}/pipelines?per_page=5" 2>/dev/null) || return 1
    jq -r --arg sha "$sha" '[.[] | select(.commit == $sha)] | .[0].status // empty' <<<"$raw" 2>/dev/null
}

# Wait out a QUEUED Woodpecker pipeline on its OWN bounded budget, before the
# required-check poll below starts counting (issue #717). Entirely advisory:
# an unresolvable token/repo/pipeline, or a status that already left "pending",
# returns immediately - callers get the unchanged pre-#717 poll either way.
wait_out_woodpecker_queue() {
    woodpecker_repo_id || return 0
    local attempts="${GH_PR_MERGE_QUEUE_WAIT_ATTEMPTS:-30}"
    local delay="${GH_PR_MERGE_QUEUE_WAIT_DELAY:-10}"
    local i status announced=0
    for ((i = 1; i <= attempts; i++)); do
        status=$(woodpecker_pipeline_status)
        [[ -z "$status" || "$status" != "pending" ]] && return 0
        if (( announced == 0 )); then
            echo "note: Woodpecker pipeline for PR #$PR_NUMBER is queued (not yet" \
                 "running) - waiting it out before starting the required-check poll" \
                 "budget (issue #717)." >&2
            announced=1
        fi
        (( i < attempts )) && sleep "$delay"
    done
    return 0
}

if ! poll_mergeable; then
    exit 1
fi

# Resolve the PR base once for every feature that needs it. A failed or empty
# metadata read remains fail-open at each caller; GitHub is the final arbiter.
PR_BASE_BRANCH=$("$GH_BIN" pr view "$PR_NUMBER" --json baseRefName --jq '.baseRefName' 2>/dev/null)

# Pre-squash deletion surfacing (issue #657): print every path this PR deletes
# vs its base BEFORE the squash - and before the (possibly long) required-check
# wait, so the signal is out while there is still time to act on it - as one
# greppable marker line. Fail-open: an unreadable root/base/diff prints
# `skipped`, never silence and never a block. Ref-scoped reads only -
# `git -C <root>` with full refs, no bare relative pathspecs (the #657
# companion finding: a cwd-drifted relative pathspec reads as an empty diff,
# which is indistinguishable from "no deletions").
surface_deletions() {
    local root deletions n
    root=$("$GIT_BIN" rev-parse --show-toplevel 2>/dev/null)
    if [[ -z "$root" || -z "$PR_BASE_BRANCH" ]]; then
        echo "GH_PR_MERGE_DELETIONS: skipped"
        return 0
    fi
    "$GIT_BIN" -C "$root" fetch origin "$PR_BASE_BRANCH" --quiet 2>/dev/null || true
    if ! deletions=$("$GIT_BIN" -C "$root" diff --name-only --diff-filter=D "origin/${PR_BASE_BRANCH}...HEAD" 2>/dev/null); then
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
    echo "warning: this squash will land $n deletion(s) vs origin/${PR_BASE_BRANCH} - confirm they are" >&2
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

# Retarget open stacked children BEFORE the squash can delete their base branch
# (poker-measure#405). GitHub's API/CLI path closes an open PR when its base ref
# is deleted; only the web-UI merge flow retargets it automatically. Enumeration
# and default-branch resolution are advisory reads, so either failing prints
# `skipped` and never blocks the merge (#610 posture). Each edit is independently
# fail-open so one unreadable child cannot strand the rest.
retarget_stacked_children() {
    local listed default_branch child n
    local -a children=() retargeted=()

    if ! listed=$("$GH_BIN" pr list --state open --base "$BRANCH" --json number \
        --jq '.[].number' 2>/dev/null); then
        echo "GH_PR_MERGE_STACKED_RETARGET: skipped"
        return 0
    fi
    while IFS= read -r child; do
        [[ -n "$child" ]] && children+=("$child")
    done <<<"$listed"
    if (( ${#children[@]} == 0 )); then
        echo "GH_PR_MERGE_STACKED_RETARGET: 0"
        return 0
    fi

    if ! default_branch=$("$GH_BIN" repo view --json defaultBranchRef \
        --jq '.defaultBranchRef.name' 2>/dev/null) || \
        [[ -z "$default_branch" || "$default_branch" == "null" ]]; then
        echo "GH_PR_MERGE_STACKED_RETARGET: skipped"
        return 0
    fi

    for child in "${children[@]}"; do
        # The list is base-filtered, so every returned child's observed base is
        # BRANCH. If that is already the resolved default, there is nothing to do.
        [[ "$BRANCH" == "$default_branch" ]] && continue
        if "$GH_BIN" pr edit "$child" --base "$default_branch" >/dev/null 2>&1; then
            retargeted+=("$child")
        else
            echo "warning: failed to retarget stacked child PR #$child from '$BRANCH'" \
                 "to '$default_branch' before branch deletion (poker-measure#405); continuing." >&2
        fi
    done

    n=${#retargeted[@]}
    if (( n == 0 )); then
        echo "GH_PR_MERGE_STACKED_RETARGET: 0"
        return 0
    fi
    echo "GH_PR_MERGE_STACKED_RETARGET: $n ${retargeted[*]}"
    echo "note: retargeted stacked child PR(s) ${retargeted[*]} from '$BRANCH' to" \
         "'$default_branch' before deleting '$BRANCH' (poker-measure#405), so GitHub" \
         "does not auto-close them when their base branch is removed." >&2
    return 0
}

# Every close/fix/resolve-keyword surface for this squash (issue #794): the
# title and body this script sends as --subject/--body, PLUS every commit
# subject on the PR branch. The squash composes its message from the PR's own
# commits whenever neither --subject nor --body is supplied (issue #716 above),
# and GitHub's own closing-issue linking already reads every commit in the PR
# independently of that - so a `git commit -m` typed inline is exactly as much
# a closing surface as the PR description, and it never passes through
# whatever review the body gets. Populates the parallel global arrays
# CLOSE_SCAN_SOURCES (a label per entry: title, body, commit:<short-sha>) and
# CLOSE_SCAN_TEXTS (that entry's text) for both close-keyword guards to share.
# Fail-open on an unreadable commit list (network hiccup, PR closed mid-run):
# title/body are always scanned regardless.
CLOSE_SCAN_SOURCES_LOADED=0
close_keyword_scan_sources() {
    # Memoized: both guards call this, and the commit-list fetch is a real
    # gh API round trip - do it once per run, not once per guard.
    (( CLOSE_SCAN_SOURCES_LOADED )) && return 0
    CLOSE_SCAN_SOURCES=(title body)
    CLOSE_SCAN_TEXTS=("$SQUASH_TITLE" "${SQUASH_BODY:-}")
    local commit_out sha subject
    # \037 (unit separator), never a whitespace char, is this repo's field
    # separator for exactly this reason (issues #698/#700): a tab- or
    # space-delimited `read` shifts fields silently - never an error - the
    # instant a commit subject happens to contain that same whitespace char.
    commit_out=$("$GH_BIN" pr view "$PR_NUMBER" --json commits \
        --jq '.commits[] | (.oid // "") + "" + (.messageHeadline // "")' 2>/dev/null) || commit_out=""
    while IFS=$'\037' read -r sha subject; do
        [[ -z "$sha" && -z "$subject" ]] && continue
        CLOSE_SCAN_SOURCES+=("commit:${sha:0:7}")
        CLOSE_SCAN_TEXTS+=("$subject")
    done <<< "$commit_out"
    CLOSE_SCAN_SOURCES_LOADED=1
}

# Negated issue-closing keywords (issues #726 and #772): GitHub's matcher sees
# the literal trigger even in "does not close #N", so a disclaimer silently
# closes the issue after merge. Trim each prefix at sentence and clause
# boundaries, then require the negation to be adjacent to the close/fix/resolve
# keyword with no more than two intervening words. Stop before either squash
# call. The per-merge override is deliberately loud so consuming it leaves an
# audit trail.
guard_negated_close_keywords() {
    local keyword_re auxiliary_re negation_re source text line entry offset match issue
    local after prefix suffix context found=0 idx
    local en_dash=$'\xE2\x80\x93' em_dash=$'\xE2\x80\x94' apostrophe=$'\xE2\x80\x99'
    # grep -b reports byte offsets, so keep Bash and the grep children byte-oriented.
    local -x LC_ALL=C
    keyword_re='(?i)\b(?:close(?:s|d)?|fix(?:es|ed)?|resolve(?:s|d)?)\b:?\s*#[[:digit:]]+'
    auxiliary_re='does|do|did|will|would|shall|should|can|could|must|may|might|is|are|was|were|be|been|has|have|had'
    negation_re="(?i)(?:\\b(?:(?:${auxiliary_re})\\h+not|not|never|no)\\b|\\b[[:alpha:]]+n(?:'|${apostrophe})t\\b)(?:\\h+[[:alpha:]]+){0,2}\\h*$"

    close_keyword_scan_sources
    for idx in "${!CLOSE_SCAN_SOURCES[@]}"; do
        source="${CLOSE_SCAN_SOURCES[$idx]}"
        text="${CLOSE_SCAN_TEXTS[$idx]}"
        while IFS= read -r line || [[ -n "$line" ]]; do
            while IFS= read -r entry; do
                [[ -z "$entry" ]] && continue
                offset=${entry%%:*}
                match=${entry#*:}
                prefix=${line:0:offset}
                prefix=${prefix##*[.!?,;:()]}
                prefix=${prefix##*"$en_dash"}
                prefix=${prefix##*"$em_dash"}
                if ! printf '%s\n' "$prefix" | grep -Pqi "$negation_re"; then
                    continue
                fi
                issue=${match##*#}
                after=$(( offset + ${#match} ))
                suffix=${line:after:30}
                suffix=${suffix%%[.!?]*}
                context="${prefix}${match}${suffix}"
                printf 'GH_PR_MERGE_NEGATED_CLOSE: %s matched #%s in "%s"\n' \
                    "$source" "$issue" "$context" >&2
                found=1
            done < <(printf '%s\n' "$line" | grep -Pob "$keyword_re" || true)
        done <<< "$text"
    done

    (( found == 0 )) && return 0
    if (( ALLOW_NEGATED_CLOSE )); then
        echo "override consumed: --allow-negated-close bypassed the issue #726 negated-close-keyword refusal." >&2
        return 0
    fi
    echo "CLEAN STOP: negated issue-closing keyword detected - not merging (issue #726)." >&2
    echo "  The PR is left open and untouched. Reword without the literal trigger pattern," >&2
    echo "  e.g. '#N remains open for T0xx' instead of 'does not close #N', then re-run." >&2
    exit 5
}

# Classify one close/fix/resolve + #N match as incidental (issue #794): flag
# when #N is immediately followed by a possessive or a slash-compound modifier
# ("closes #N's investigation...", "...the resolved #N/topic finding" -
# checked first and unconditionally, since it stands regardless of what
# precedes the keyword), OR when the keyword is not clause-initial (other
# words precede it in its sentence/clause) AND those words are not a
# recognized adjacent NEGATION - that shape is issue #726's guard's hazard,
# not this one's, and the two must never both fire off the same text asking
# for two different overrides of what is, to a human, one decision. A plain
# "Closes #N" / "Fixes #N" at a line or clause start, with nothing but
# punctuation or another reference after the digits, is a legitimate directive
# and is NOT flagged. $1 = prefix (already trimmed to the nearest clause
# boundary, as guard_negated_close_keywords also does), $2 = the up-to-4-byte
# text immediately following the matched digits. Echoes 1 (incidental) or 0.
_is_incidental_close_match() {
    local prefix="$1" immediate_suffix="$2" apostrophe=$'\xE2\x80\x99'
    local clause_initial_re='^[[:space:]]*(?:[-*+]|[0-9]+[.)])?[[:space:]]*$'
    local bad_suffix_re="(?i)^(?:'s|${apostrophe}s|/[[:alpha:]])"
    local auxiliary_re='does|do|did|will|would|shall|should|can|could|must|may|might|is|are|was|were|be|been|has|have|had'
    local negation_re="(?i)(?:\\b(?:(?:${auxiliary_re})\\h+not|not|never|no)\\b|\\b[[:alpha:]]+n(?:'|${apostrophe})t\\b)(?:\\h+[[:alpha:]]+){0,2}\\h*$"
    # grep sees ZERO lines - never a match, regardless of anchors - on a
    # zero-byte stream, so an empty $prefix/$immediate_suffix (the common,
    # legitimate case) must still be handed to grep AS one empty line, not as
    # no input at all: printf '%s\n' (never bare '%s') makes that distinction
    # for every check below.
    if printf '%s\n' "$immediate_suffix" | grep -Pq "$bad_suffix_re"; then
        echo 1
        return
    fi
    if printf '%s\n' "$prefix" | grep -Pq "$clause_initial_re"; then
        echo 0
        return
    fi
    if printf '%s\n' "$prefix" | grep -Pqi "$negation_re"; then
        echo 0
        return
    fi
    echo 1
}

# A scan that silently cannot run must never read the same as a scan that ran
# and found nothing (this repo has hit exactly that failure mode: a regex that
# failed to compile printed no output and was indistinguishable from a clean
# result). Before trusting a clean guard_incidental_close_keywords pass, prove
# the classifier still recognizes each concrete shape it exists to catch - the
# not-clause-initial case AND the bad-suffix case, both independently, plus a
# known-legitimate case it must NOT flag. These are calls to the classifier
# directly, never text sent to GitHub, so no real issue number is at risk.
# Exits 8 (a distinct code from every merge-refusal exit) and refuses to
# proceed if the classifier's own answer ever changes.
_incidental_close_selfcheck() {
    local hit_position hit_suffix miss
    hit_position=$(_is_incidental_close_match "note: the resolved " "")
    hit_suffix=$(_is_incidental_close_match "" "'s inv")
    miss=$(_is_incidental_close_match "" "")
    if [[ "$hit_position" != 1 || "$hit_suffix" != 1 || "$miss" != 0 ]]; then
        echo "GH_PR_MERGE_INCIDENTAL_CLOSE_SELFCHECK: broken - classifier answered" \
             "position=$hit_position suffix=$hit_suffix miss=$miss (expected 1, 1, 0)" >&2
        echo "CLEAN STOP: the incidental-close classifier failed its own self-check - refusing to" >&2
        echo "  trust a clean scan rather than silently merging (issue #794)." >&2
        exit 8
    fi
}

# Incidental proximity still closes issues (issue #794): a close/fix/resolve
# keyword adjacent to #N that is not actually a directive - not negated, #726's
# guard does not see it, but GitHub's proximity matcher does not care that the
# keyword is an adjective or governs a different noun. Same sources as the
# negated guard (title, body, every commit subject), same CLEAN STOP shape, own
# escape hatch.
guard_incidental_close_keywords() {
    local keyword_re source text line entry offset match issue idx
    local after prefix suffix display_suffix context found=0 immediate_suffix
    local en_dash=$'\xE2\x80\x93' em_dash=$'\xE2\x80\x94'
    local -x LC_ALL=C
    keyword_re='(?i)\b(?:close(?:s|d)?|fix(?:es|ed)?|resolve(?:s|d)?)\b:?\s*#[[:digit:]]+'

    _incidental_close_selfcheck

    close_keyword_scan_sources
    for idx in "${!CLOSE_SCAN_SOURCES[@]}"; do
        source="${CLOSE_SCAN_SOURCES[$idx]}"
        text="${CLOSE_SCAN_TEXTS[$idx]}"
        while IFS= read -r line || [[ -n "$line" ]]; do
            while IFS= read -r entry; do
                [[ -z "$entry" ]] && continue
                offset=${entry%%:*}
                match=${entry#*:}
                prefix=${line:0:offset}
                prefix=${prefix##*[.!?,;:()]}
                prefix=${prefix##*"$en_dash"}
                prefix=${prefix##*"$em_dash"}
                issue=${match##*#}
                after=$(( offset + ${#match} ))
                immediate_suffix=${line:after:4}
                if [[ "$(_is_incidental_close_match "$prefix" "$immediate_suffix")" != 1 ]]; then
                    continue
                fi
                suffix=${line:after:30}
                display_suffix=${suffix%%[.!?]*}
                context="${prefix}${match}${display_suffix}"
                printf 'GH_PR_MERGE_INCIDENTAL_CLOSE: %s matched #%s in "%s"\n' \
                    "$source" "$issue" "$context" >&2
                found=1
            done < <(printf '%s\n' "$line" | grep -Pob "$keyword_re" || true)
        done <<< "$text"
    done

    (( found == 0 )) && return 0
    if (( ALLOW_INCIDENTAL_CLOSE )); then
        echo "override consumed: --allow-incidental-close bypassed the issue #794 incidental-close-keyword refusal." >&2
        return 0
    fi
    echo "CLEAN STOP: incidental issue-closing keyword detected - not merging (issue #794)." >&2
    echo "  The PR is left open and untouched. The matched keyword reads as adjacent to #N," >&2
    echo "  not a directive - reword the clause, or consciously re-run with" >&2
    echo "  --allow-incidental-close after reviewing the printed context." >&2
    exit 7
}

surface_deletions
retarget_stacked_children

# An explicit --admin is a conscious owner override of protection, so it also
# skips the wait, the queue wait that precedes it, and the base-move guard around
# them (issues #717/#767); without it, required checks must be green before the
# squash and the gated tree must still contain the fetched base.
if (( ADMIN_OPT_IN == 0 )); then
    BASE_WAIT_ROOT=$("$GIT_BIN" rev-parse --show-toplevel 2>/dev/null)
    BASE_TIP_BEFORE=""
    if [[ -n "$BASE_WAIT_ROOT" && -n "$PR_BASE_BRANCH" ]] && \
       "$GIT_BIN" -C "$BASE_WAIT_ROOT" fetch origin "$PR_BASE_BRANCH" --quiet 2>/dev/null; then
        BASE_TIP_BEFORE=$("$GIT_BIN" -C "$BASE_WAIT_ROOT" rev-parse \
            "refs/remotes/origin/${PR_BASE_BRANCH}" 2>/dev/null)
    fi

    wait_out_woodpecker_queue
    if ! wait_for_required_checks; then
        exit 1
    fi

    BASE_TIP_AFTER=""
    if [[ -n "$BASE_WAIT_ROOT" && -n "$PR_BASE_BRANCH" ]] && \
       "$GIT_BIN" -C "$BASE_WAIT_ROOT" fetch origin "$PR_BASE_BRANCH" --quiet 2>/dev/null; then
        BASE_TIP_AFTER=$("$GIT_BIN" -C "$BASE_WAIT_ROOT" rev-parse \
            "refs/remotes/origin/${PR_BASE_BRANCH}" 2>/dev/null)
    fi

    if [[ -z "$BASE_TIP_BEFORE" || -z "$BASE_TIP_AFTER" ]]; then
        echo "GH_PR_MERGE_BASE_MOVED: skipped"
    elif [[ "$BASE_TIP_BEFORE" == "$BASE_TIP_AFTER" ]] || \
         "$GIT_BIN" -C "$BASE_WAIT_ROOT" merge-base --is-ancestor \
            "$BASE_TIP_AFTER" HEAD 2>/dev/null; then
        echo "GH_PR_MERGE_BASE_MOVED: 0"
    else
        echo "GH_PR_MERGE_BASE_MOVED: $BASE_TIP_BEFORE -> $BASE_TIP_AFTER"
        if (( ALLOW_BASE_MOVE )); then
            echo "warning: override consumed: --allow-base-move bypassed the issue #767 base-move clean stop for PR #$PR_NUMBER." >&2
        else
            echo "CLEAN STOP: base '$PR_BASE_BRANCH' advanced while the required checks were running - not merging PR #$PR_NUMBER (issue #767)." >&2
            echo "  The tree that was gated is not the tree that would land. The PR is left open and untouched." >&2
            echo "  Bring the branch current, re-run the quality gate, push, and re-run the merge:" >&2
            echo "        git fetch origin $PR_BASE_BRANCH" >&2
            echo "        git merge origin/$PR_BASE_BRANCH" >&2
            echo "  Resume /flow:auto Step 7 from its sync sub-step, or re-run /flow:merge." >&2
            echo "  Conscious override: re-run this helper with --allow-base-move." >&2
            exit 6
        fi
    fi
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
# Tested-tree trailer (issue #716): if and only if this PR's branch was up to
# date with its base at squash time, append a self-verifying
# `Woodpecker-Tested-Tree: <hash>` trailer so the consumer (poker-measure's
# push pipeline) can skip re-running the full suite by recomputing the same
# hash on what it actually checked out. Ref-scoped reads only (`git -C <root>`,
# full refs - the #657/#659 companion rule); fail-open per component, so an
# unreadable base or an ancestry check that cannot resolve simply omits the
# trailer - the safe default.
TESTED_TREE_TRAILER=""
resolve_tested_tree_trailer() {
    local root tree
    root=$("$GIT_BIN" rev-parse --show-toplevel 2>/dev/null)
    [[ -z "$root" || -z "$PR_BASE_BRANCH" ]] && return 0
    "$GIT_BIN" -C "$root" fetch origin "$PR_BASE_BRANCH" --quiet 2>/dev/null || true
    "$GIT_BIN" -C "$root" merge-base --is-ancestor \
        "origin/${PR_BASE_BRANCH}" HEAD 2>/dev/null || return 0
    tree=$("$GIT_BIN" -C "$root" rev-parse "HEAD^{tree}" 2>/dev/null)
    [[ -z "$tree" ]] && return 0
    TESTED_TREE_TRAILER="Woodpecker-Tested-Tree: ${tree}"
}
resolve_tested_tree_trailer

SQUASH_TITLE=$("$GH_BIN" pr view "$PR_NUMBER" --json title --jq '.title' 2>/dev/null)
if [[ -n "$SQUASH_TITLE" ]]; then
    SQUASH_BODY=$("$GH_BIN" pr view "$PR_NUMBER" --json body --jq '.body' 2>/dev/null) || SQUASH_BODY=""
    if [[ -n "$TESTED_TREE_TRAILER" ]]; then
        if [[ -n "$SQUASH_BODY" ]]; then
            SQUASH_BODY="${SQUASH_BODY}"$'\n\n'"${TESTED_TREE_TRAILER}"
        else
            SQUASH_BODY="$TESTED_TREE_TRAILER"
        fi
    fi
    BASE_FLAGS+=(--subject "${SQUASH_TITLE} (#${PR_NUMBER})" --body "$SQUASH_BODY")
elif [[ -n "$TESTED_TREE_TRAILER" ]]; then
    # Title read failed/empty (the #655 fail-open path omits --subject/--body
    # together), but the trailer still needs to land in the squash message -
    # pass --body alone; GitHub derives the subject as it always has here.
    BASE_FLAGS+=(--body "$TESTED_TREE_TRAILER")
fi

guard_negated_close_keywords
guard_incidental_close_keywords

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
