#!/usr/bin/env bash
# flow-pr-watch.sh - Watch ONE PR's pipeline to a CLASSIFIED verdict (issue #788).
#
# Problem:
#   In a wave, the merge-queue critic clears a PR's queue position, the PR's next
#   pipeline runs, and NOTHING watches the result. On the kyle-completion wave
#   (2026-09-05) the owner noticed a red pipeline on a cleared PR before the
#   critic did: the clearance stood unrevised over a red run, because issuing it
#   is where the critic's attention ended.
#
#   Colour alone is not the answer either. A red on a cleared PR is one of three
#   things, and the wrong response to each is expensive:
#
#     cancelled  A superseding push killed the run mid-flight. NOT a defect;
#                re-pushing it only lengthens the queue.
#     flake      A test already on the wave's declared-flaky list. Treating it as
#                the PR's defect stalls a clean merge.
#     red        A real failure. Retrying until it wins hides the defect; the
#                worker should hear the failing test names and assertions.
#
#   Triage was done by hand all evening: `pipeline ps` for the failed step,
#   `pipeline log show` for the pytest summary, then a comparison against the
#   wave's flake baseline and the commit history. Each class has a MECHANICAL
#   signature, so the classification is automatable and this helper automates it.
#
# What it does NOT do, deliberately:
#   - It does not decide what is a flake. That stays a human/critic judgment,
#     recorded in the baseline file; the helper only reports whether the failures
#     are all inside the declared set.
#   - It does not retry, re-push, or merge anything. It reports; the worker acts.
#
# Run it as a BACKGROUND call after issuing a clearance: it blocks until the
# pipeline is terminal and then exits, so the harness re-invokes the critic with
# the verdict in hand - the same wake shape as `flow-wave-mailbox.sh watch`. The
# critic then revises the clearance EXPLICITLY rather than leaving a stale CLEAR
# standing over a red.
#
# Why the check rollup, not `pipeline ls`:
#   For a `pull_request` event Woodpecker records the TARGET branch, not the
#   head - so a branch grep over `pipeline ls` finds the wrong run, or none.
#   GitHub's status-check rollup on the PR head carries the pipeline's own URL,
#   which is the only link from "this PR right now" to "that pipeline number"
#   that cannot drift. The CLI lane below is a fallback and anchors on the exact
#   head SHA, never on list position (the #766/#516 lesson).
#
# Usage:
#   flow-pr-watch.sh <pr-number> [--repo <owner/name>] [--timeout <s>]
#                    [--interval <s>] [--baseline <file>] [--path <checkout>]
#
#   <pr-number>     The PR to watch (required).
#   --repo          owner/name override; default resolved from `gh`, else the
#                   checkout's origin remote.
#   --timeout <s>   Give up after S seconds (default 1800). `--timeout 0` reads
#                   once and reports whatever state it finds - no blocking.
#   --interval <s>  Poll interval (default 15).
#   --baseline <f>  Declared-flaky test ids, one per line; `#` comments and blank
#                   lines ignored. Default:
#                   <checkout>/.claude/flow-flake-baseline.txt when it exists.
#                   An entry may be a full id (`tests/test_x.py::test_y`) or a
#                   bare test name (`test_y`), which matches any id whose last
#                   `::` component equals it.
#   --path <dir>    Checkout used to resolve the repo and the default baseline -
#                   DECLARED by the caller, never inferred (issue #614, the #592
#                   rule): the Bash process cwd drifts on any earlier `cd`.
#                   Default: process cwd.
#
# Output ends with a machine-readable contract - detail lines first, verdict last
# (the flow-wave-mailbox shape, which the issue's own proposal uses):
#   FLOW_PR_WATCH_PR=<number>
#   FLOW_PR_WATCH_HEAD=<sha|->
#   FLOW_PR_WATCH_PIPELINE=<number|->
#   FLOW_PR_WATCH_URL=<url|->
#   FLOW_PR_WATCH_SUPERSEDED_BY=<number|->    (set whenever a newer run exists)
#   FLOW_PR_WATCH_FAILED=<test ids, space-separated|->  (flake and red)
#   FLOW_PR_WATCH_BASELINE=<file|->
#   FLOW_PR_WATCH_ASSERT=<test id>: <first `E` line>    (repeated, red only)
#   FLOW_PR_WATCH: green | cancelled | flake | red | timeout | unknown
#
# Exit codes - the same convention as the mailbox watch, and NO new code for a
# new verdict (the #674 rule):
#   0  green, cancelled, flake, unknown   nothing for the caller to fix
#   1  red                                a real failure the worker must hear
#   2  usage error
#   5  timeout                            the pipeline never reached a verdict
#
# `unknown` exits 0 because this helper is ADVISORY and FAIL-OPEN: no `gh`, no
# CLI, no credentials, no pipeline for the head - all report `unknown` rather
# than manufacturing a verdict. A watch that cannot see must never be the reason
# a wave stops.
#
# Cancellation is deliberately conjunctive: a superseding run must exist AND the
# watched run must carry the kill signature (server state `killed`, or every
# stopped step sharing one timestamp with no pytest summary in the log). Either
# half alone would excuse a genuine defect that merely happened to be re-pushed
# over - the expensive direction of this error.
#
# Env (test hooks - unset in normal use):
#   FLOW_PR_WATCH_GH      override the `gh` binary
#   FLOW_PR_WATCH_WPCLI   override the `woodpecker-cli` binary
#   FLOW_PR_WATCH_SLEEP   override `sleep` (makes polling instant in tests)

set -uo pipefail

PR_NUMBER=""
REPO=""
TIMEOUT=1800
INTERVAL=15
BASELINE=""
CHECK_PATH=""

GH_BIN="${FLOW_PR_WATCH_GH:-gh}"
WPCLI_BIN="${FLOW_PR_WATCH_WPCLI:-woodpecker-cli}"
SLEEP_BIN="${FLOW_PR_WATCH_SLEEP:-sleep}"

die_usage() {
    echo "flow-pr-watch: $1" >&2
    echo "usage: flow-pr-watch.sh <pr-number> [--repo <owner/name>] [--timeout <s>] [--interval <s>] [--baseline <file>] [--path <dir>]" >&2
    exit 2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)       REPO="${2:-}"; [[ -n "$REPO" ]] || die_usage "--repo needs owner/name"; shift 2 ;;
        --repo=*)     REPO="${1#*=}"; shift ;;
        --timeout)    TIMEOUT="${2:-}"; [[ "$TIMEOUT" =~ ^[0-9]+$ ]] || die_usage "--timeout needs seconds"; shift 2 ;;
        --timeout=*)  TIMEOUT="${1#*=}"; [[ "$TIMEOUT" =~ ^[0-9]+$ ]] || die_usage "--timeout needs seconds"; shift ;;
        --interval)   INTERVAL="${2:-}"; [[ "$INTERVAL" =~ ^[0-9]+$ ]] || die_usage "--interval needs seconds"; shift 2 ;;
        --interval=*) INTERVAL="${1#*=}"; [[ "$INTERVAL" =~ ^[0-9]+$ ]] || die_usage "--interval needs seconds"; shift ;;
        --baseline)   BASELINE="${2:-}"; [[ -n "$BASELINE" ]] || die_usage "--baseline needs a file"; shift 2 ;;
        --baseline=*) BASELINE="${1#*=}"; shift ;;
        --path)       CHECK_PATH="${2:-}"; [[ -n "$CHECK_PATH" ]] || die_usage "--path needs a directory"; shift 2 ;;
        --path=*)     CHECK_PATH="${1#*=}"; shift ;;
        -h|--help)    sed -n '2,100p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*)           die_usage "unknown argument: $1" ;;
        *)
            [[ -z "$PR_NUMBER" ]] || die_usage "unexpected argument: $1"
            PR_NUMBER="${1#\#}"
            shift
            ;;
    esac
done

[[ -n "$PR_NUMBER" ]] || die_usage "a PR number is required"
[[ "$PR_NUMBER" =~ ^[0-9]+$ ]] || die_usage "PR number must be numeric: $PR_NUMBER"
[[ "$INTERVAL" -gt 0 ]] || INTERVAL=1

HEAD_SHA="-"
PIPELINE="-"
URL="-"
SUPERSEDED_BY="-"
VERDICT="unknown"
STATE=""
FAILED_IDS=()
ASSERT_LINES=()

emit() {
    echo "FLOW_PR_WATCH_PR=$PR_NUMBER"
    echo "FLOW_PR_WATCH_HEAD=$HEAD_SHA"
    echo "FLOW_PR_WATCH_PIPELINE=$PIPELINE"
    echo "FLOW_PR_WATCH_URL=$URL"
    echo "FLOW_PR_WATCH_SUPERSEDED_BY=$SUPERSEDED_BY"
    if [[ "${#FAILED_IDS[@]}" -gt 0 ]]; then
        echo "FLOW_PR_WATCH_FAILED=${FAILED_IDS[*]}"
    else
        echo "FLOW_PR_WATCH_FAILED=-"
    fi
    echo "FLOW_PR_WATCH_BASELINE=${BASELINE:--}"
    for line in ${ASSERT_LINES+"${ASSERT_LINES[@]}"}; do
        echo "FLOW_PR_WATCH_ASSERT=$line"
    done
    echo "FLOW_PR_WATCH: $VERDICT"
    case "$VERDICT" in
        red)     exit 1 ;;
        timeout) exit 5 ;;
        *)       exit 0 ;;
    esac
}

# ── Resolve the checkout and the repo ──────────────────────────────────────
[[ -n "$CHECK_PATH" ]] || CHECK_PATH="$PWD"

if [[ -z "$REPO" ]]; then
    REPO="$("$GH_BIN" repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)"
fi
if [[ -z "$REPO" && -d "$CHECK_PATH" ]]; then
    ORIGIN="$(git -C "$CHECK_PATH" remote get-url origin 2>/dev/null)"
    # git@host:owner/name.git  or  https://host/owner/name(.git)
    REPO="$(sed -E 's#^.*[:/]([^/:]+/[^/]+?)(\.git)?$#\1#' <<<"${ORIGIN:-}")"
    [[ "$REPO" == "${ORIGIN:-}" ]] && REPO=""
fi
if [[ -z "$REPO" ]]; then
    echo "flow-pr-watch: could not resolve owner/name (fail-open)" >&2
    emit
fi

# ── Resolve the baseline ───────────────────────────────────────────────────
if [[ -z "$BASELINE" && -f "$CHECK_PATH/.claude/flow-flake-baseline.txt" ]]; then
    BASELINE="$CHECK_PATH/.claude/flow-flake-baseline.txt"
fi
if [[ -n "$BASELINE" && ! -f "$BASELINE" ]]; then
    echo "flow-pr-watch: baseline file not found: $BASELINE (no id will match)" >&2
fi

# ── gh lane ────────────────────────────────────────────────────────────────
gh_pr_json() { # gh_pr_json <json-fields> <jq-filter>
    "$GH_BIN" pr view "$PR_NUMBER" --repo "$REPO" --json "$1" --jq "$2" 2>/dev/null
}

# The pipeline number and its web URL, read off the PR head's status-check
# rollup. The rollup mixes two node shapes - a commit STATUS (context/state/
# targetUrl, what Woodpecker posts) and a GitHub CHECK RUN (name/status/
# conclusion/detailsUrl) - so both are flattened to `url|state`. Only URLs
# shaped like a Woodpecker pipeline permalink are considered; the highest
# pipeline number wins, so a re-run's status is preferred over a stale one.
rollup_pipeline() { # -> "<number>|<state>|<url>" or empty
    gh_pr_json statusCheckRollup \
        '.statusCheckRollup[]? | "\(.targetUrl // .detailsUrl // "")|\(.state // .conclusion // .status // "PENDING")"' \
    | {
        best_num=-1
        best=""
        while IFS='|' read -r url state; do
            [[ "$url" =~ /pipeline/([0-9]+) ]] || continue
            num="${BASH_REMATCH[1]}"
            if [[ "$num" -gt "$best_num" ]]; then
                best_num="$num"
                best="$num|$state|$url"
            fi
        done
        [[ -n "$best" ]] && echo "$best"
    }
}

# ── woodpecker-cli lane ────────────────────────────────────────────────────
have_wpcli() { command -v "$WPCLI_BIN" >/dev/null 2>&1; }

wp_rows() {
    "$WPCLI_BIN" pipeline ls --output-no-headers \
        --output 'go-template={{range .}}{{.Number}}|{{.Status}}|{{.Commit}}{{"\n"}}{{end}}' \
        --limit 50 "$REPO" 2>/dev/null
}

# Highest-numbered pipeline whose commit is exactly $1 - anchored on the SHA,
# never on list position, because that shared list is mostly other sessions' runs.
wp_pipeline_for_sha() { # -> "<number>|<status>" or empty
    local sha="$1" best="" best_num=-1 number status commit
    while IFS='|' read -r number status commit; do
        [[ "$commit" == "$sha" ]] || continue
        [[ "$number" =~ ^[0-9]+$ ]] || continue
        if [[ "$number" -gt "$best_num" ]]; then
            best_num="$number"
            best="$number|$status"
        fi
    done < <(wp_rows)
    [[ -n "$best" ]] && echo "$best"
}

wp_status_of() { # wp_status_of <pipeline-number> -> "<status>" or empty
    local want="$1" number status commit
    while IFS='|' read -r number status commit; do
        if [[ "$number" == "$want" ]]; then
            echo "$status"
            return 0
        fi
    done < <(wp_rows)
    return 1
}

wp_steps() { # -> "<name>|<state>|<stopped>" lines
    "$WPCLI_BIN" pipeline ps --format '{{ .step.Name }}|{{ .step.State }}|{{ .step.Stopped }}
' "$REPO" "$1" 2>/dev/null
}

wp_log() { "$WPCLI_BIN" pipeline log show "$REPO" "$1" 2>/dev/null; }

# ── State mapping ──────────────────────────────────────────────────────────
# Woodpecker states and GitHub rollup states/conclusions land in one of three
# buckets. Anything unrecognized is pending, so an unknown state makes the watch
# keep waiting rather than inventing a terminal verdict.
outcome_of() {
    case "${1,,}" in
        success)                                            echo "success" ;;
        failure|error|killed|cancelled|timed_out|declined)  echo "failure" ;;
        *)                                                  echo "pending" ;;
    esac
}

# ── Watch loop ─────────────────────────────────────────────────────────────
WATCH_HEAD="$(gh_pr_json headRefOid '.headRefOid')"
if [[ -z "$WATCH_HEAD" ]]; then
    echo "flow-pr-watch: could not read PR #$PR_NUMBER head from $REPO (fail-open)" >&2
    emit
fi
HEAD_SHA="$WATCH_HEAD"

DEADLINE=$(( $(date +%s) + TIMEOUT ))
SUPERSEDED=0

while :; do
    # 1. A superseding push moves the PR head. That is the cheapest and most
    #    reliable supersession signal there is, and it needs no CI provider.
    CURRENT_HEAD="$(gh_pr_json headRefOid '.headRefOid')"
    if [[ -n "$CURRENT_HEAD" && "$CURRENT_HEAD" != "$WATCH_HEAD" ]]; then
        SUPERSEDED=1
        if have_wpcli; then
            NEWER="$(wp_pipeline_for_sha "$CURRENT_HEAD")"
            [[ -n "$NEWER" ]] && SUPERSEDED_BY="${NEWER%%|*}"
        fi
        echo "flow-pr-watch: PR head moved ${WATCH_HEAD:0:12} -> ${CURRENT_HEAD:0:12}; the watched run was superseded by a push." >&2
    fi

    # 2. Resolve the pipeline carrying the head we are watching.
    CUR_NUM="-"
    CUR_STATE=""
    ROLLUP="$(rollup_pipeline)"
    if [[ -n "$ROLLUP" ]]; then
        IFS='|' read -r CUR_NUM CUR_STATE CUR_URL <<<"$ROLLUP"
    fi
    if have_wpcli; then
        WP_MATCH="$(wp_pipeline_for_sha "$WATCH_HEAD")"
        if [[ -n "$WP_MATCH" ]]; then
            WP_NUM="${WP_MATCH%%|*}"
            if [[ "$CUR_NUM" == "-" ]] || [[ "$WP_NUM" -gt "$CUR_NUM" ]]; then
                CUR_NUM="$WP_NUM"
                CUR_STATE="${WP_MATCH##*|}"
                CUR_URL="${CUR_URL:--}"
            elif [[ "$WP_NUM" == "$CUR_NUM" ]]; then
                # The CLI knows `killed`; the rollup only ever reports failure.
                CUR_STATE="${WP_MATCH##*|}"
            fi
        fi
    fi

    if [[ "$CUR_NUM" != "-" ]]; then
        if [[ "$PIPELINE" == "-" ]]; then
            # First resolution: this is the run we are watching.
            PIPELINE="$CUR_NUM"
            STATE="$CUR_STATE"
            [[ -n "${CUR_URL:-}" ]] && URL="$CUR_URL"
        elif [[ "$CUR_NUM" -gt "$PIPELINE" ]]; then
            # A newer run exists for the same head - a re-run supersedes just as
            # a push does. Keep reporting on the run we were asked to watch.
            SUPERSEDED=1
            SUPERSEDED_BY="$CUR_NUM"
            if have_wpcli; then
                OWN_STATE="$(wp_status_of "$PIPELINE")"
                [[ -n "$OWN_STATE" ]] && STATE="$OWN_STATE"
            fi
        else
            STATE="$CUR_STATE"
        fi
    fi

    # 3. Terminate on a terminal state, or on supersession - the issue's two
    #    stopping conditions.
    if [[ "$PIPELINE" != "-" ]]; then
        case "$(outcome_of "${STATE:-}")" in
            success) VERDICT="green";   break ;;
            failure) VERDICT="failure"; break ;;
        esac
    fi
    if [[ "$SUPERSEDED" -eq 1 ]]; then
        VERDICT="failure"
        break
    fi

    if [[ "$TIMEOUT" -eq 0 ]]; then
        if [[ "$PIPELINE" == "-" ]]; then
            echo "flow-pr-watch: no pipeline carries ${WATCH_HEAD:0:12} yet (single-shot read)." >&2
        else
            echo "flow-pr-watch: pipeline #$PIPELINE is '${STATE:-unknown}' (single-shot read)." >&2
        fi
        emit
    fi
    if [[ "$(date +%s)" -ge "$DEADLINE" ]]; then
        VERDICT="timeout"
        echo "flow-pr-watch: pipeline #$PIPELINE for PR #$PR_NUMBER did not finish within ${TIMEOUT}s (state '${STATE:-unknown}')." >&2
        emit
    fi
    "$SLEEP_BIN" "$INTERVAL"
done

[[ "$VERDICT" == "green" ]] && emit

# ── Failure triage ─────────────────────────────────────────────────────────
# Reaching here means the watched run ended red, or was superseded before it
# could finish. Which of the three reds it is decides what the worker does next.
if ! have_wpcli; then
    # Honest degradation: without the CLI there is no log to read and no step
    # timing to inspect, so the ids and the kill signature are unavailable. A
    # bare supersession still answers cancelled; anything else reports red
    # rather than guessing.
    if [[ "$SUPERSEDED" -eq 1 ]]; then
        VERDICT="cancelled"
        echo "flow-pr-watch: superseded, and '$WPCLI_BIN' is not on PATH - reporting cancelled without step evidence." >&2
    else
        VERDICT="red"
        echo "flow-pr-watch: '$WPCLI_BIN' not on PATH - reporting red without test ids (no log to read)." >&2
    fi
    emit
fi

if [[ "$PIPELINE" == "-" ]]; then
    # Superseded before any pipeline was observed for this head.
    VERDICT="cancelled"
    echo "flow-pr-watch: no pipeline was ever observed for ${WATCH_HEAD:0:12} before it was superseded." >&2
    emit
fi

STEP_ROWS="$(wp_steps "$PIPELINE")"
LOG="$(wp_log "$PIPELINE")"

# A pytest run that reached its own conclusion prints a summary. Its ABSENCE is
# half the cancellation signature: a killed run's log stops mid-suite.
HAS_SUMMARY=0
if grep -qE 'short test summary info|^=+ .*(passed|failed|error)' <<<"$LOG"; then
    HAS_SUMMARY=1
fi

# Failed ids come from pytest's own summary lines, which name the id straight
# after the FAILED/ERROR token. The id must contain `::` so that the word
# "ERROR" in ordinary log prose cannot be mistaken for a summary line, and the
# token is matched field-wise rather than by regex so a parametrized id full of
# brackets and dots cannot corrupt the pattern.
mapfile -t FAILED_IDS < <(awk '
    {
        for (i = 1; i < NF; i++) {
            if (($i == "FAILED" || $i == "ERROR") && $(i + 1) ~ /::/) {
                if (!seen[$(i + 1)]++) print $(i + 1)
                break
            }
        }
    }
' <<<"$LOG")
[[ "${#FAILED_IDS[@]}" -eq 1 && -z "${FAILED_IDS[0]}" ]] && FAILED_IDS=()
[[ "${#FAILED_IDS[@]}" -gt 0 ]] && HAS_SUMMARY=1

# The other half of the signature: every stopped step shares ONE stop timestamp,
# because the server killed them together rather than each finishing on its own.
SIMULTANEOUS_STOP=0
STOPPED_ROWS="$(awk -F'|' 'NF>=3 && $3 != "" && $3 != "0" { print $3 }' <<<"$STEP_ROWS")"
STOP_COUNT="$(grep -c . <<<"$STOPPED_ROWS")"
DISTINCT_STOPS="$(sort -u <<<"$STOPPED_ROWS" | grep -c .)"
if [[ "$STOP_COUNT" -ge 2 && "$DISTINCT_STOPS" -eq 1 ]]; then
    SIMULTANEOUS_STOP=1
fi

# `cancelled` requires supersession AND the kill signature - never either alone.
if [[ "$SUPERSEDED" -eq 1 ]]; then
    if [[ "${STATE,,}" == "killed" || "${STATE,,}" == "cancelled" ]] \
       || [[ "$SIMULTANEOUS_STOP" -eq 1 && "$HAS_SUMMARY" -eq 0 ]] \
       || [[ "$(outcome_of "${STATE:-}")" == "pending" ]]; then
        VERDICT="cancelled"
        SUPERSEDED_LABEL="${SUPERSEDED_BY}"
        [[ "$SUPERSEDED_LABEL" == "-" ]] && SUPERSEDED_LABEL="a newer push"
        echo "flow-pr-watch: pipeline #$PIPELINE was superseded by $SUPERSEDED_LABEL and shows the kill signature (state '${STATE:-unknown}', simultaneous-stop=$SIMULTANEOUS_STOP, pytest-summary=$HAS_SUMMARY)." >&2
        emit
    fi
    echo "flow-pr-watch: pipeline #$PIPELINE was superseded, but its log carries a real pytest summary - classifying on the failures, not on the supersession." >&2
fi

if [[ "${#FAILED_IDS[@]}" -eq 0 ]]; then
    VERDICT="red"
    echo "flow-pr-watch: pipeline #$PIPELINE is red but its log names no failed test (a non-pytest step, or a truncated log)." >&2
    while IFS='|' read -r name state _; do
        case "$state" in
            failure|error|killed) [[ -n "$name" ]] && echo "flow-pr-watch: failed step: $name" >&2 ;;
        esac
    done <<<"$STEP_ROWS"
    emit
fi

# ── Baseline comparison ────────────────────────────────────────────────────
# The helper does NOT decide what is a flake. It reports whether every failure is
# inside the set the wave has already declared flaky.
in_baseline() { # in_baseline <test-id>
    local id="$1" entry short
    short="${id##*::}"
    [[ -n "$BASELINE" && -f "$BASELINE" ]] || return 1
    while IFS= read -r entry || [[ -n "$entry" ]]; do
        entry="${entry%%#*}"
        entry="${entry#"${entry%%[![:space:]]*}"}"
        entry="${entry%"${entry##*[![:space:]]}"}"
        [[ -n "$entry" ]] || continue
        [[ "$entry" == "$id" ]] && return 0
        [[ "$entry" != *"::"* && "$entry" == "$short" ]] && return 0
    done < "$BASELINE"
    return 1
}

ALL_BASELINE=1
for id in "${FAILED_IDS[@]}"; do
    if ! in_baseline "$id"; then
        ALL_BASELINE=0
        break
    fi
done

if [[ "$ALL_BASELINE" -eq 1 ]]; then
    VERDICT="flake"
    echo "flow-pr-watch: every failed test on pipeline #$PIPELINE is in the declared baseline ($BASELINE) - reporting flake, which is not a clearance." >&2
    emit
fi

# ── Real failure: name the tests and the assertions ────────────────────────
# The first `E` line under a test's own traceback header is what the worker
# needs; the `- <message>` tail of the summary line is the fallback when the
# traceback section is missing from a truncated log. Both are matched with
# fixed-string comparisons so a parametrized id cannot corrupt a pattern.
VERDICT="red"
for id in "${FAILED_IDS[@]}"; do
    short="${id##*::}"
    assertion="$(awk -v name="$short" '
        /^_{3,}.*_{3,}$/ { inblock = (index($0, name) > 0); next }
        inblock && /^E +/ {
            line = $0
            sub(/^E +/, "", line)
            print line
            exit
        }
    ' <<<"$LOG")"
    if [[ -z "$assertion" ]]; then
        assertion="$(awk -v id="$id" '
            {
                for (i = 1; i < NF; i++) {
                    if (($i == "FAILED" || $i == "ERROR") && $(i + 1) == id) {
                        rest = ""
                        for (j = i + 2; j <= NF; j++) rest = rest (rest == "" ? "" : " ") $j
                        sub(/^- /, "", rest)
                        print rest
                        exit
                    }
                }
            }
        ' <<<"$LOG")"
    fi
    [[ -n "$assertion" ]] || assertion="(no assertion line in the log)"
    ASSERT_LINES+=("$id: $assertion")
done

echo "flow-pr-watch: pipeline #$PIPELINE is a REAL failure - ${#FAILED_IDS[@]} test(s) outside the baseline. Tell the worker before it retries." >&2
emit
