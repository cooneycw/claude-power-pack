#!/bin/bash
# flow-worktree-sweep.sh - Retire worktrees whose work has landed (issue #887)
#
# WHO OWNS TEARDOWN. Nobody did, and that is why worktrees accumulate: the party
# that can remove a worktree has finished by the time the party that discovers it
# exists gets there. `gh pr merge --delete-branch` deletes the REMOTE branch and
# then tries `git branch -d` locally; git refuses while a worktree holds the
# branch, and gh has no notion of worktrees, so it stops. The worktree survives,
# holding a branch that no longer exists on the remote. Measured on cooneycw/kyle
# after ONE wave: 33 worktrees, 3.1G, 25 of them holding merged branches.
#
# #887 named three candidate owners. This script is the third - a SWEEP, run at
# wave close or session teardown rather than at merge time. The reasoning is in
# docs/decisions/0006-worktree-teardown-ownership.md; the two facts that decide it:
#
#   1. A merge-time owner cannot cover the population. It fires only on merges it
#      performs, so a PR closed rather than merged, one merged in the GitHub UI,
#      or a worktree orphaned when its session died are all structurally out of
#      its reach - and those are most of what actually accumulates.
#   2. A refusal costs a sweep nothing. The merging session must finish its merge,
#      so a guard that blocks it is an obstacle to route around - which is how
#      `--force` came to be on every /flow:auto Step 7 call in the first place. A
#      sweep that skips a worktree has simply done its job; it reports and moves
#      on. A guard whose refusal is free is a guard that stays honest.
#
# THIS SCRIPT NEVER DELETES ANYTHING ITSELF. Every removal goes through
# worktree-remove.sh, and deliberately WITHOUT --force and WITHOUT --steal:
#
#   - The sweep passes NO flag but --delete-branch. Every other flag the helper
#     accepts overrides a refusal, and the sweep is the one caller that would
#     apply one to every worktree on the host. Its contribution to safety is
#     largely what it does not pass.
#     (This read "no --force means the uncommitted-changes check is ARMED" until
#     issue #899 split --force into --force/--allow-dirty/--allow-unpushed and
#     armed that check unconditionally. The flag the sweep must never pass is now
#     --allow-dirty; the test asserts an allowlist rather than naming any of
#     them, so the next flag is covered on the day it lands.)
#   - No --steal means the #597 claim (exit 4) and the #888 in-use refusal
#     (exit 5) are both final here. A non-zero exit is recorded as a skip with its
#     code and the sweep continues to the next worktree. It is never retried, and
#     never re-attempted with an override - doing that in a loop over every
#     worktree on a host is precisely the data-loss path #889 closed.
#
# THE SAFETY TEST (#887), five conditions ANDed, all re-read for a worktree
# IMMEDIATELY BEFORE that worktree's own removal - never from a list built
# earlier, because the state moves while a wave runs:
#
#   PR is MERGED (or CLOSED with --include-closed)
#   working tree clean         git status --porcelain empty
#   nothing unpushed           see "two independent mechanisms" below
#   no live process inside     no /proc/<pid>/cwd at or under the worktree
#   not locked                 no `locked` line in git worktree list --porcelain
#
# The dry-run report is a REPORT, not a manifest: --apply re-derives all five
# from scratch rather than executing anything the report produced.
#
# Concretely: one worktree is carried from classification to removal before the
# next is looked at, and `dirty` and `unpushed` are re-read again as the last
# statements before the removal call - because the occupancy scan and the PR
# lookup between them are slow enough to make the earlier reads stale. `unpushed`
# is the one that matters most: it is the only condition with no backstop beneath
# it, since a clean `git status` says nothing about a commit that was never
# pushed and a session paused between tool calls has no process for the occupancy
# scan to find.
#
# NOT REMOVABLE IS THE DEFAULT ANSWER. Every condition that cannot be positively
# established is a skip, and the three that cannot be established at all -
# `pr-unknown`, `unpushed-unknown`, `occupancy-unknown` - are reported as
# UNDECIDABLE and make the whole run `partial` (exit 3). They are not folded into
# the skip count: "I looked and it must stay" and "I could not tell" are different
# facts, and a sweep that renders the second as the first is claiming a clean tree
# it never established. Two of tonight's skips on the measured host mattered - a
# deliberately preserved WIP branch and a wayfinder research branch, both with no
# PR by design - and a sweep keyed on "no PR" would have destroyed both. `pr-none`
# is therefore a skip, never a reason to remove.
#
# WHY THIS IS STRICTER THAN worktree-remove.sh, ON PURPOSE. The helper removes an
# occupied-but-clean worktree (nothing unrecoverable to lose) and falls open when
# /proc is unreadable. Both are right for a caller who has named one path and
# asked for it. They are wrong for a sweep, which is CHOOSING its targets and pays
# nothing to skip one. So the occupancy scan below is a filter, not a second
# authority: worktree-remove.sh runs last and its refusal is final. Do not
# "de-duplicate" the two by deleting either - they answer different questions.
#
# Usage:
#   flow-worktree-sweep.sh [--repo <path>] [--apply] [--include-closed]
#
# Options:
#   --repo <path>     Any path inside the repository (default: cwd)
#   --apply           Actually remove. Without it the sweep only reports.
#   --include-closed  Treat a CLOSED PR as terminal too (default: MERGED only)
#
# Output (greppable):
#   FLOW_WORKTREE_SWEEP_PLAN: dry-run | apply
#   SWEEP_WORKTREE: <path> <disposition> <detail>
#   FLOW_WORKTREE_SWEEP_COUNTS: candidates=N removable=N removed=N skipped=N \
#                               undecidable=N refused=N
#   FLOW_WORKTREE_SWEEP: ok | nothing-to-do | no-candidates | partial | error
#
# `no-candidates` is distinct from `nothing-to-do` deliberately: a repo with no
# linked worktrees examined an empty population and must not report the same word
# as one that examined nine and correctly kept them all.
#
# Exit codes:
#   0  the sweep classified every candidate (ok | nothing-to-do | no-candidates)
#   1  usage error, or not a git repository
#   3  partial - at least one candidate was undecidable or refused at removal
#
# Environment:
#   FLOW_WORKTREE_SWEEP_PROC_ROOT  test seam for the occupancy scan, not a knob.
#                                  It exists so the "cannot scan" lane is
#                                  reachable on a host with a working /proc.

set -euo pipefail

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

START_PATH="$PWD"
APPLY=false
INCLUDE_CLOSED=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)
            START_PATH="${2:-}"
            if [[ -z "$START_PATH" ]]; then
                echo "Error: --repo requires a path" >&2
                echo "FLOW_WORKTREE_SWEEP: error" >&2
                exit 1
            fi
            shift 2
            ;;
        --apply)          APPLY=true; shift ;;
        --include-closed) INCLUDE_CLOSED=true; shift ;;
        -h|--help)
            sed -n '/^# Usage:/,/^# Environment:/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Error: unknown argument '$1'" >&2
            echo "Usage: flow-worktree-sweep.sh [--repo <path>] [--apply] [--include-closed]" >&2
            echo "FLOW_WORKTREE_SWEEP: error" >&2
            exit 1
            ;;
    esac
done

if ! git -C "$START_PATH" rev-parse --git-dir >/dev/null 2>&1; then
    echo "Error: not a git repository: $START_PATH" >&2
    echo "FLOW_WORKTREE_SWEEP: error" >&2
    exit 1
fi

# --- The removal helper ------------------------------------------------------
# Prefer the copy beside this script, then the stable install path. If neither
# exists the sweep still REPORTS - classification needs no helper - but it cannot
# apply, and says so rather than falling back to a bare `git worktree remove`,
# which would drop the #597 and #888 guards the whole design leans on.
SELF_SCRIPT_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")")"
REMOVE_HELPER=""
for cand in "$SELF_SCRIPT_DIR/worktree-remove.sh" "$HOME/.claude/scripts/worktree-remove.sh"; do
    if [[ -f "$cand" ]]; then
        REMOVE_HELPER="$cand"
        break
    fi
done

if [[ "$APPLY" == true && -z "$REMOVE_HELPER" ]]; then
    echo -e "${RED}Error: worktree-remove.sh not found; refusing to --apply.${NC}" >&2
    echo "  Looked in: $SELF_SCRIPT_DIR and \$HOME/.claude/scripts" >&2
    echo "  Removal goes through that helper so the #597 claim and #888 in-use" >&2
    echo "  refusals apply. Run /flow:repair to install it." >&2
    echo "FLOW_WORKTREE_SWEEP: error" >&2
    exit 1
fi

# --- Ownership boundary: the population is THIS repository's worktrees --------
# Enumerated from git, never from a glob over the parent directory. On the git
# lane worktrees are visible siblings (#627: `<parent>/<repo>-<branch>`), so a
# neighbouring checkout of an UNRELATED repository sits right beside them and a
# path glob would sweep it up. `git worktree list` cannot: it reports only
# worktrees registered to this repository.
mapfile -t WT_PORCELAIN < <(git -C "$START_PATH" worktree list --porcelain)

MAIN_REPO=""
CAND_PATHS=()
CAND_BRANCHES=()
CAND_FLAGS=()

cur_path=""
cur_branch=""
cur_flags=""
flush_entry() {
    [[ -n "$cur_path" ]] || return 0
    if [[ -z "$MAIN_REPO" ]]; then
        # The first entry git reports is the main worktree; it is never a
        # candidate and is not counted as one.
        MAIN_REPO="$cur_path"
    else
        CAND_PATHS+=("$cur_path")
        CAND_BRANCHES+=("$cur_branch")
        CAND_FLAGS+=("$cur_flags")
    fi
    cur_path=""; cur_branch=""; cur_flags=""
}

for line in "${WT_PORCELAIN[@]}"; do
    case "$line" in
        "worktree "*) flush_entry; cur_path="${line#worktree }" ;;
        "branch "*)   cur_branch="${line#branch }"; cur_branch="${cur_branch#refs/heads/}" ;;
        "locked"|"locked "*)     cur_flags="${cur_flags} locked" ;;
        "prunable"|"prunable "*) cur_flags="${cur_flags} prunable" ;;
        "detached")              cur_flags="${cur_flags} detached" ;;
        "bare")                  cur_flags="${cur_flags} bare" ;;
    esac
done
flush_entry

# --- GitHub repo slug, parsed offline ----------------------------------------
# Parsed from the remote URL rather than asked of `gh repo view`, so an offline
# or unauthenticated host reaches the PR lookup and reports `pr-unknown` there -
# one place that can be unable to answer, instead of two.
repo_slug() {
    local url slug
    url="$(git -C "$MAIN_REPO" remote get-url origin 2>/dev/null || echo "")"
    [[ -n "$url" ]] || return 1
    url="${url%.git}"
    case "$url" in *github.com[:/]*) ;; *) return 1 ;; esac
    slug="${url#*github.com}"
    slug="${slug#:}"
    slug="${slug#/}"
    [[ "$slug" == */* ]] || return 1
    printf '%s\n' "$slug"
}
REPO_SLUG="$(repo_slug || echo "")"

# --- Occupancy scan ----------------------------------------------------------
# A filter, not an authority - worktree-remove.sh asks the same question last and
# its answer is the one that decides. See the header.
PROC_ROOT="${FLOW_WORKTREE_SWEEP_PROC_ROOT:-/proc}"

occupancy_self_pids() {
    local pid=$$ depth=0 ppid
    while [[ -n "$pid" && "$pid" != "0" && "$depth" -lt 64 ]]; do
        printf '%s\n' "$pid"
        ppid="$(awk '/^PPid:/{print $2}' "/proc/$pid/status" 2>/dev/null || true)"
        pid="$ppid"
        depth=$((depth + 1))
    done
}

# Prints "<pid>" per live process whose cwd is at or under $1.
# Exit 0 = the scan RAN. Exit 2 = it could NOT run, which must read as unknown
# and never as clear.
occupancy_scan() {
    local wt="$1" entry pid cwd
    [[ -r "$PROC_ROOT/self/cwd" ]] || return 2
    local skip_pids
    skip_pids=" $(occupancy_self_pids | tr '\n' ' ') "
    local saw_any=false
    for entry in "$PROC_ROOT"/[0-9]*; do
        if [[ "$entry" == "$PROC_ROOT/[0-9]*" ]]; then
            return 2   # a proc tree exposing no process - we learned nothing
        fi
        saw_any=true
        pid="${entry##*/}"
        case "$skip_pids" in *" $pid "*) continue ;; esac
        cwd="$(readlink "$entry/cwd" 2>/dev/null)" || continue
        [[ -n "$cwd" ]] || continue
        # Exact path or a genuine child. A bare prefix test would make `<wt>-2`
        # look like it lives inside `<wt>`, and on the host this was measured on
        # `kyle-issue-1142` is a real prefix of
        # `kyle-issue-1142-container-spec-superseded`.
        if [[ "$cwd" == "$wt" || "${cwd#"$wt"/}" != "$cwd" ]]; then
            printf '%s\n' "$pid"
        fi
    done
    [[ "$saw_any" == true ]] || return 2
    return 0
}

# --- PR state ----------------------------------------------------------------
# Sets PR_STATE to merged | closed | open | none | unknown, and PR_HEAD_OID to
# the head commit GitHub saw (empty when unknown).
#
# `none` and `unknown` are kept apart because conflating them is the whole
# hazard: `[]` from a successful query means this branch genuinely has no PR,
# while a gh that is missing, unauthenticated, rate-limited or offline has told
# us nothing at all. Both are skips, but only the second means the sweep cannot
# claim it classified the tree.
lookup_pr() {
    local branch="$1" out rc line state oid num
    PR_STATE="unknown"; PR_HEAD_OID=""; PR_DETAIL=""
    if [[ -z "$branch" ]]; then PR_DETAIL="no-branch"; return 0; fi
    if ! command -v gh >/dev/null 2>&1; then PR_DETAIL="gh-not-installed"; return 0; fi
    if [[ -z "$REPO_SLUG" ]]; then PR_DETAIL="no-github-remote"; return 0; fi

    # gh carries its own jq, so this needs no jq on the host: one fewer thing
    # whose absence would have to be reported as an undecidable.
    rc=0
    out="$(gh pr list --repo "$REPO_SLUG" --head "$branch" --state all --limit 20 \
             --json state,headRefOid,number \
             --jq '.[] | [.state, .headRefOid, (.number|tostring)] | join("|")' 2>/dev/null)" || rc=$?
    if [[ "$rc" -ne 0 ]]; then PR_DETAIL="gh-query-failed"; return 0; fi

    # Exit 0 with no rows is a real answer: this branch has no PR. That is how a
    # preserved WIP branch and a wayfinder research branch look, permanently.
    if [[ -z "$out" ]]; then
        PR_STATE="none"; PR_DETAIL="no-pr-for-branch"; return 0
    fi

    local open_prs="" merged_prs="" closed_prs="" merged_oid="" closed_oid=""
    # `|`, not a tab: a whitespace IFS splits silently on a field that contains
    # one, shifting every field after it with no error at all, and scripts/ is
    # swept for that shape (#698/#700). No PR state, OID or number can contain a
    # pipe, so this separator cannot collide with the data.
    while IFS='|' read -r state oid num; do
        [[ -n "$state" ]] || continue
        case "$state" in
            OPEN)   open_prs="${open_prs},#${num}" ;;
            MERGED) merged_prs="${merged_prs},#${num}"; [[ -n "$merged_oid" ]] || merged_oid="$oid" ;;
            CLOSED) closed_prs="${closed_prs},#${num}"; [[ -n "$closed_oid" ]] || closed_oid="$oid" ;;
            *)      PR_DETAIL="unrecognised-state:$state"; return 0 ;;
        esac
    done <<< "$out"

    # An OPEN PR outranks everything: the branch is still under review, whatever
    # else was opened against it earlier.
    if [[ -n "$open_prs" ]]; then
        PR_STATE="open"; PR_DETAIL="pr=${open_prs#,}"; return 0
    fi
    if [[ -n "$merged_prs" ]]; then
        PR_STATE="merged"; PR_HEAD_OID="$merged_oid"; PR_DETAIL="pr=${merged_prs#,}"; return 0
    fi
    if [[ -n "$closed_prs" ]]; then
        PR_STATE="closed"; PR_HEAD_OID="$closed_oid"; PR_DETAIL="pr=${closed_prs#,}"; return 0
    fi
    # Rows were returned but none classified - do not fall through to a verdict.
    PR_DETAIL="no-classifiable-state"
    return 0
}

# --- Unpushed check ----------------------------------------------------------
# Two mechanisms that do not share an input, because #888's lesson was that two
# guards fed by one signal degrade to one:
#
#   upstream    `git log @{u}..` - git-native, offline, exact. Unavailable once
#               `git fetch --prune` drops refs/remotes/origin/<branch>, which is
#               the normal state after `gh pr merge --delete-branch`.
#   PR head     the branch tip GitHub saw. Survives the prune, and is also an
#               IDENTITY check: it says this local branch is the thing that
#               merged, not a same-named branch recreated since.
#
# Neither available means unpushed-unknown, which is undecidable, not clean.
# Sets UNPUSHED_STATE to pushed | unpushed | unknown.
check_unpushed() {
    local wt="$1" oid="$2" local_tip
    UNPUSHED_STATE="unknown"; UNPUSHED_DETAIL=""
    if git -C "$wt" rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
        if [[ -z "$(git -C "$wt" log '@{u}..' --oneline 2>/dev/null || echo "err")" ]]; then
            UNPUSHED_STATE="pushed"; UNPUSHED_DETAIL="upstream-current"
        else
            UNPUSHED_STATE="unpushed"
            UNPUSHED_DETAIL="ahead-of-upstream=$(git -C "$wt" rev-list --count '@{u}..' 2>/dev/null || echo '?')"
        fi
        return 0
    fi
    if [[ -n "$oid" ]]; then
        local_tip="$(git -C "$wt" rev-parse HEAD 2>/dev/null || echo "")"
        if [[ -n "$local_tip" && "$local_tip" == "$oid" ]]; then
            UNPUSHED_STATE="pushed"; UNPUSHED_DETAIL="tip-matches-pr-head"
        elif [[ -n "$local_tip" ]]; then
            UNPUSHED_STATE="unpushed"; UNPUSHED_DETAIL="tip-differs-from-pr-head"
        else
            UNPUSHED_DETAIL="tip-unreadable"
        fi
        return 0
    fi
    UNPUSHED_DETAIL="no-upstream-and-no-pr-head"
    return 0
}

# --- The sweep ---------------------------------------------------------------
n_candidates=${#CAND_PATHS[@]}
n_removable=0
n_removed=0
n_skipped=0
n_undecidable=0
n_refused=0

if [[ "$APPLY" == true ]]; then
    echo "FLOW_WORKTREE_SWEEP_PLAN: apply"
else
    echo "FLOW_WORKTREE_SWEEP_PLAN: dry-run"
fi
echo -e "${BLUE}Main repository: ${MAIN_REPO}${NC}"

report() {   # path disposition detail
    echo "SWEEP_WORKTREE: $1 $2 $3"
}

for i in "${!CAND_PATHS[@]}"; do
    wt="${CAND_PATHS[$i]}"
    branch="${CAND_BRANCHES[$i]}"
    flags="${CAND_FLAGS[$i]}"

    # Every condition below is read HERE, immediately before this worktree's own
    # removal call - not collected into a plan and executed later. The state
    # moves while a wave runs, which is why the issue specifies removal-time
    # verification, and it is why --apply re-derives rather than replaying a
    # dry-run report.

    case "$flags" in
        *prunable*)
            # A registration whose directory is gone. `git worktree prune` owns
            # that, and taking it here would race the prune for no gain.
            report "$wt" skip prunable; n_skipped=$((n_skipped + 1)); continue ;;
        *locked*)
            # Includes a live #597 claim, which IS a git worktree lock. The sweep
            # never reaches worktree-remove.sh for these, and never needs --steal.
            report "$wt" skip locked; n_skipped=$((n_skipped + 1)); continue ;;
        *detached*)
            report "$wt" skip detached-head; n_skipped=$((n_skipped + 1)); continue ;;
    esac

    if [[ ! -d "$wt" ]]; then
        report "$wt" skip directory-missing; n_skipped=$((n_skipped + 1)); continue
    fi
    if [[ -z "$branch" ]]; then
        report "$wt" skip no-branch; n_skipped=$((n_skipped + 1)); continue
    fi

    lookup_pr "$branch"
    case "$PR_STATE" in
        unknown)
            report "$wt" undecidable "pr-unknown:$PR_DETAIL"
            n_undecidable=$((n_undecidable + 1)); continue ;;
        open)
            report "$wt" skip "pr-open:$PR_DETAIL"; n_skipped=$((n_skipped + 1)); continue ;;
        none)
            # The preserved-WIP and wayfinder-research case. Deliberately a skip:
            # "no PR" is how those branches look and always will.
            report "$wt" skip pr-none; n_skipped=$((n_skipped + 1)); continue ;;
        closed)
            if [[ "$INCLUDE_CLOSED" != true ]]; then
                report "$wt" skip "pr-closed:$PR_DETAIL (use --include-closed)"
                n_skipped=$((n_skipped + 1)); continue
            fi ;;
    esac

    dirty="$(git -C "$wt" status --porcelain 2>/dev/null || echo "__unreadable__")"
    if [[ "$dirty" == "__unreadable__" ]]; then
        report "$wt" undecidable status-unreadable
        n_undecidable=$((n_undecidable + 1)); continue
    fi
    if [[ -n "$dirty" ]]; then
        report "$wt" skip "dirty:$(printf '%s\n' "$dirty" | wc -l | tr -d ' ')-paths"
        n_skipped=$((n_skipped + 1)); continue
    fi

    check_unpushed "$wt" "$PR_HEAD_OID"
    case "$UNPUSHED_STATE" in
        unknown)
            report "$wt" undecidable "unpushed-unknown:$UNPUSHED_DETAIL"
            n_undecidable=$((n_undecidable + 1)); continue ;;
        unpushed)
            report "$wt" skip "unpushed:$UNPUSHED_DETAIL"
            n_skipped=$((n_skipped + 1)); continue ;;
    esac

    occ_rc=0
    occ_out="$(occupancy_scan "$wt")" || occ_rc=$?
    if [[ "$occ_rc" -eq 2 ]]; then
        # Unlike worktree-remove.sh, which falls open here, the sweep skips: it
        # is choosing targets and pays nothing to leave one alone.
        report "$wt" undecidable occupancy-unknown
        n_undecidable=$((n_undecidable + 1)); continue
    fi
    if [[ -n "$occ_out" ]]; then
        report "$wt" skip "occupied:pids=$(printf '%s' "$occ_out" | tr '\n' ',' | sed 's/,$//')"
        n_skipped=$((n_skipped + 1)); continue
    fi

    n_removable=$((n_removable + 1))
    if [[ "$APPLY" != true ]]; then
        report "$wt" removable "$PR_STATE,branch=$branch"
        continue
    fi

    # --- Final re-verification, immediately before this worktree's removal ---
    # Everything above is already per-worktree rather than a batch pre-pass, but
    # the occupancy scan walks all of /proc and the PR lookup is a network call,
    # so "already checked" can be seconds old by the time we get here. These two
    # conditions are re-read as the LAST thing before the invocation because they
    # are the two whose loss is unrecoverable, and one of them has nothing
    # underneath it:
    #
    #   dirty     re-read, and also backstopped - worktree-remove.sh runs its own
    #             uncommitted-changes check because we pass no --force.
    #   unpushed  re-read, and backstopped by NOTHING. `git status --porcelain`
    #             says nothing about a commit that was never pushed, and a worker
    #             paused between tool calls has no live process for the occupancy
    #             scan to find. A session that commits without pushing in this
    #             window is invisible to every guard except this one.
    #
    # The residual window is what remains between these reads and the `git
    # worktree remove` inside the helper: one subprocess spawn, its claim check
    # and its own /proc scan. That is not zero and cannot be made zero without
    # git-level locking we do not hold. It is accepted because the consequence is
    # bounded rather than absent - the commit objects survive in the common
    # object database and are reachable via `git fsck --lost-found` until gc -
    # and because the alternative, holding a lock across the whole sweep, would
    # block the very sessions the sweep exists to stay out of the way of.
    dirty_now="$(git -C "$wt" status --porcelain 2>/dev/null || echo "__unreadable__")"
    if [[ "$dirty_now" == "__unreadable__" || -n "$dirty_now" ]]; then
        report "$wt" skip "dirty-at-removal:changed-since-check"
        n_removable=$((n_removable - 1)); n_skipped=$((n_skipped + 1)); continue
    fi
    check_unpushed "$wt" "$PR_HEAD_OID"
    if [[ "$UNPUSHED_STATE" != "pushed" ]]; then
        report "$wt" skip "unpushed-at-removal:$UNPUSHED_DETAIL"
        n_removable=$((n_removable - 1)); n_skipped=$((n_skipped + 1)); continue
    fi

    rc=0
    bash "$REMOVE_HELPER" "$wt" --delete-branch >/dev/null 2>&1 || rc=$?
    case "$rc" in
        0) report "$wt" removed "$PR_STATE,branch=$branch"; n_removed=$((n_removed + 1)) ;;
        4) report "$wt" refused "claimed-by-live-session(exit 4)"; n_refused=$((n_refused + 1)) ;;
        5) report "$wt" refused "in-use-and-dirty(exit 5)";        n_refused=$((n_refused + 1)) ;;
        1) report "$wt" refused "helper-declined(exit 1)";         n_refused=$((n_refused + 1)) ;;
        *) report "$wt" refused "helper-exit-$rc";                 n_refused=$((n_refused + 1)) ;;
    esac
done

echo "FLOW_WORKTREE_SWEEP_COUNTS: candidates=$n_candidates removable=$n_removable removed=$n_removed skipped=$n_skipped undecidable=$n_undecidable refused=$n_refused"

if [[ "$n_candidates" -eq 0 ]]; then
    # Not "everything is clean" - nothing was examined. The distinction is the
    # point: a universal claim over an empty population is the one this script
    # must never make.
    echo -e "${BLUE}No linked worktrees in this repository - nothing was examined.${NC}"
    echo "FLOW_WORKTREE_SWEEP: no-candidates"
    exit 0
fi

if [[ "$n_undecidable" -gt 0 || "$n_refused" -gt 0 ]]; then
    echo -e "${YELLOW}Sweep incomplete: ${n_undecidable} could not be classified, ${n_refused} refused at removal.${NC}" >&2
    echo "FLOW_WORKTREE_SWEEP: partial"
    exit 3
fi

if [[ "$n_removable" -eq 0 ]]; then
    echo -e "${GREEN}All ${n_candidates} worktrees classified; none is removable.${NC}"
    echo "FLOW_WORKTREE_SWEEP: nothing-to-do"
    exit 0
fi

if [[ "$APPLY" == true ]]; then
    echo -e "${GREEN}Removed ${n_removed} of ${n_candidates} worktrees.${NC}"
else
    echo -e "${GREEN}${n_removable} of ${n_candidates} worktrees are removable. Re-run with --apply.${NC}"
    echo -e "${YELLOW}That list is a report, not a plan: --apply re-checks all five conditions itself.${NC}"
fi
echo "FLOW_WORKTREE_SWEEP: ok"
exit 0
