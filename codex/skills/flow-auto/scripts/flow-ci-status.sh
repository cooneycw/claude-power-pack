#!/usr/bin/env bash
# flow-ci-status.sh - Resolve the CI outcome for ONE commit SHA (issues #766, #768).
#
# Problem:
#   /flow:auto Step 8 (Verify CI) was the last un-helpered step in the flow. It
#   inlined a curl+jq Woodpecker lookup gated on WOODPECKER_API_TOKEN already
#   being exported - which it usually is not, because the token lives in an AWS
#   secret, not a shell profile. With no helper the model improvises, and on
#   flow:auto #516 the improvisation was a grep over `woodpecker-cli pipeline
#   ls`: it matched an unrelated PR pipeline from a DIFFERENT concurrent fleet
#   session and reported STATUS=failure while the run's own pipeline was still
#   queued. With ~7 sessions merging into one repo, a positional grep over that
#   shared list is a coin flip.
#
#   Pipeline COLOUR is also not the answer Step 8 needs: for kyle's push
#   pipelines a red can mean "tests failed" or "the SSH deploy step hit a
#   connect timeout", which are materially different outcomes.
#
# So this helper anchors on the SHA, never on list position, and names the
# failed STEPS. It has three provider lanes: the Woodpecker HTTP API when its
# credentials resolve, authenticated `woodpecker-cli` with machine-readable
# go-template output otherwise (issue #768), then GitHub Actions. It is
# ADVISORY and FAIL-OPEN: no token, no network, no provider all yield `unknown`
# and exit 0, never a blocked flow (unless --exit-code).
#
# The token is read from $WOODPECKER_API_TOKEN when exported, else fetched from
# AWS Secrets Manager. It is never echoed, and never passed on a command line
# where `ps` could see it.
#
# Usage:
#   flow-ci-status.sh [SHA] [--path <checkout>] [--repo <owner/name>]
#                     [--event push|pull_request] [--wait [SECONDS]]
#                     [--secret-name <name>] [--region <region>] [--exit-code]
#
#   SHA            Commit to resolve (default: HEAD of the checkout).
#   --path <dir>   The checkout to read HEAD/remote from - DECLARED by the
#                  caller, not inferred (issue #614, the #592 rule): the Bash
#                  process cwd drifts on any earlier `cd`. Default: process cwd.
#   --repo         owner/name override; default is resolved from the checkout.
#   --event        Prefer this pipeline event when several share the SHA (a
#                  merge commit typically has both `push` and `pull_request`).
#                  Default: DERIVED from the DEFAULT branch's required status
#                  contexts (issue #1262; a PR into another base passes --event) - `ci/woodpecker/pr/*` required alone
#                  means pull_request, `ci/woodpecker/push/*` alone means push.
#                  Both, neither, or unreadable falls back to `push`, and the
#                  FLOW_CI_EVENT line says which source decided.
#   --strict-event Treat the event as a FILTER, not a preference (issue #1300):
#                  a pipeline on another event never answers. The wait-then-merge
#                  recipe uses it so a green push pipeline cannot end a wait for
#                  the required pull_request lane.
#   --wait [SECS]  Poll until the status is terminal or SECS elapse
#                  (default 600, 15s interval). Without it, report once.
#   --exit-code    Exit 1 when the verdict is `failure`. Every other verdict,
#                  including `unknown`, still exits 0.
#
# Output ends with a machine-readable contract - the failed-step lines, when
# present, immediately precede the verdict:
#   FLOW_CI_PROVIDER: woodpecker | github-actions | none
#   FLOW_CI_REF: <sha>
#   FLOW_CI_REPO: <owner/name|->           (issue #1262)
#   FLOW_CI_EVENT: <event> (<source>)      (issue #1262; source is `flag`,
#                                           `branch-protection: <contexts>` or
#                                           `default: <why>`)
#   FLOW_CI_PIPELINE: <number|->
#   FLOW_CI_URL: <url|->
#   FLOW_CI_WAIT: none | settled | expired (<N>s)   (issue #1262)
#   FLOW_CI_FAILED_STEP: <name>        (repeated, only on failure)
#   FLOW_CI_STALL_CHECK: checked | unavailable (<why>)   (issue #1552; only
#                                       when a Woodpecker HTTP pipeline was
#                                       running or terminal - see below)
#   FLOW_CI_STALLED: past-timeout (<E>m > <T>m + <G>m grace)
#                  | terminal-pipeline-live-children     (issue #1552)
#   FLOW_CI_STALLED_STEP: <name>       (repeated, a step still reading running)
#   FLOW_CI_STATUS: success | failure | running | pending | stalled
#                   | not-found | unknown
#
# `stalled` (issue #1552) is a TERMINAL verdict: the server still lists the
# pipeline `running` more than <grace> minutes past the repository's own
# timeout. Woodpecker's AGENT enforces that timeout, so a pipeline its agent
# still holds cannot outlive it; one that does was stranded by an agent restart
# (measured on 3.19.0, cooneycw/woodpecker-baseline#2). It means "dead, kill it
# on the server", never "slow, keep waiting" - and this helper kills nothing.
# A pipeline already `killed`/`failure`/`error` whose workflow or steps still
# read `running` keeps STATUS `failure` and adds the stalled lines: the cancel
# did not land. `FLOW_CI_STALL_CHECK: unavailable` means the timeout or the
# pipeline detail could not be read, so a `running` verdict was NOT checked for
# staleness - unchecked, never "not stalled". The woodpecker-cli and GitHub
# Actions lanes do not run this check and print no STALL_CHECK line.
#
# Env (test hooks - unset in normal use):
#   FLOW_CI_CURL   override the `curl` binary
#   FLOW_CI_AWS    override the `aws` binary
#   FLOW_CI_WPCLI  override the `woodpecker-cli` binary
#   FLOW_CI_GH     override the `gh` binary
#   FLOW_CI_SLEEP  override the `sleep` binary (make --wait instant in tests)
#   FLOW_CI_NOW    override "now" in epoch seconds (stalled-verdict tests)
#   FLOW_CI_STALL_GRACE_MIN  minutes past the repo timeout before `stalled`
#                  (default 10; not a test hook - a host may widen it)

set -uo pipefail

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
trap 'printf "FLOW_CI_EXIT=%d\n" "$?" >&2' EXIT

SHA=""
CHECK_PATH=""
REPO=""
PREFER_EVENT=""
EVENT_SOURCE="flag"
#: The fallback when the required lane cannot be derived. It was the ONLY
#: behaviour until #1262, which is why it stays the fallback: a repo whose
#: protection cannot be read gets exactly what it always got.
DEFAULT_EVENT="push"
WAIT_SECS=0
#: `none` without --wait; `settled` when a terminal verdict ended the wait;
#: `expired (<N>s)` when the deadline did (issue #1262). The STATUS values are
#: deliberately unchanged, so no consumer's parse breaks; this line is what
#: separates "the pipeline never registered in N seconds" from "one look found
#: nothing", which printed identical output before.
WAIT_STATE="none"
SECRET_NAME="${CPP_WOODPECKER_SECRET:-essent-ai}"
AWS_REGION="${AWS_REGION:-us-east-1}"
WANT_EXIT_CODE=0
STRICT_EVENT=0

CURL_BIN="${FLOW_CI_CURL:-curl}"
AWS_BIN="${FLOW_CI_AWS:-}"
WPCLI_BIN="${FLOW_CI_WPCLI:-woodpecker-cli}"
GH_BIN="${FLOW_CI_GH:-gh}"
SLEEP_BIN="${FLOW_CI_SLEEP:-sleep}"

die_usage() {
    echo "flow-ci-status: $1" >&2
    echo "usage: flow-ci-status.sh [SHA] [--path <dir>] [--repo <owner/name>] [--event <e>] [--strict-event] [--wait [SECS]] [--exit-code]" >&2
    exit 2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --path)        CHECK_PATH="${2:-}"; [[ -n "$CHECK_PATH" ]] || die_usage "--path needs a directory"; shift 2 ;;
        --path=*)      CHECK_PATH="${1#*=}"; shift ;;
        --repo)        REPO="${2:-}"; [[ -n "$REPO" ]] || die_usage "--repo needs owner/name"; shift 2 ;;
        --repo=*)      REPO="${1#*=}"; shift ;;
        --event)       PREFER_EVENT="${2:-}"; [[ -n "$PREFER_EVENT" ]] || die_usage "--event needs a value"; EVENT_SOURCE="flag"; shift 2 ;;
        --event=*)     PREFER_EVENT="${1#*=}"; EVENT_SOURCE="flag"; shift ;;
        --secret-name) SECRET_NAME="${2:-}"; [[ -n "$SECRET_NAME" ]] || die_usage "--secret-name needs a value"; shift 2 ;;
        --secret-name=*) SECRET_NAME="${1#*=}"; shift ;;
        --region)      AWS_REGION="${2:-}"; [[ -n "$AWS_REGION" ]] || die_usage "--region needs a value"; shift 2 ;;
        --region=*)    AWS_REGION="${1#*=}"; shift ;;
        --exit-code)   WANT_EXIT_CODE=1; shift ;;
        --strict-event) STRICT_EVENT=1; shift ;;
        --wait)
            # Optional numeric argument: `--wait` alone means the default.
            if [[ "${2:-}" =~ ^[0-9]+$ ]]; then WAIT_SECS="$2"; shift 2; else WAIT_SECS=600; shift; fi
            ;;
        --wait=*)      WAIT_SECS="${1#*=}"; [[ "$WAIT_SECS" =~ ^[0-9]+$ ]] || die_usage "--wait needs seconds"; shift ;;
        -h|--help)     sed -n '2,75p' "$0"; exit 0 ;;
        -*)            die_usage "unknown argument: $1" ;;
        *)             [[ -z "$SHA" ]] || die_usage "unexpected argument: $1"; SHA="$1"; shift ;;
    esac
done

PROVIDER="none"
PIPELINE="-"
URL="-"
STATUS="unknown"
FAILED_STEPS=()
# The provider's TYPE for each failed step, index-aligned with FAILED_STEPS
# (issue #1342). Empty means the lane could not say - never "a code step".
FAILED_STEP_TYPES=()
# The provider's EXIT CODE for each failed step, index-aligned with
# FAILED_STEPS (issue #1411). Empty/absent means the lane could not say -
# never treated as the fetch-failure code, and never treated as evidence of
# anything else either.
FAILED_STEP_EXIT_CODES=()
# Provider cancellation marker, index-aligned with FAILED_STEPS.
FAILED_STEP_ERRORS=()
# Set when the failed-step enumeration itself failed part-way: the names that
# arrived are still reported, but an origin over a partial list is not one.
FAILED_STEPS_INCOMPLETE=0
# Stalled-pipeline evidence (issue #1552). STALL_CHECK stays empty on lanes
# that never run the check, so emit() prints nothing rather than a false
# "checked".
STALL_CHECK=""
STALLED_REASON=""
STALLED_STEPS=()
STALL_GRACE_MIN="${FLOW_CI_STALL_GRACE_MIN:-10}"
[[ "$STALL_GRACE_MIN" =~ ^[0-9]+$ ]] || STALL_GRACE_MIN=10

# The fetch-failure exit code `ci-stage-jq.py`, `ci-stage-git.py` and
# `ci-stage-make.py` all return for "could not fetch" (issue #1411) - 75,
# BSD sysexits.h's EX_TEMPFAIL. Defined once here to cite, not to invent:
# each stager defines the SAME value independently (no shared Python module
# this bash script could import from); `tests/test_ci_stage_exit_codes.py`
# pins all three against drift from this number.
readonly EX_FETCH_FAILED=75

# Exit 75 counts as a FETCH failure only from a step that declares itself a
# stager by name (`*-stage`: make-stage, jq-stage, git-stage, shellcheck-stage).
# EX_TEMPFAIL is a general sysexits code - an application test or deploy
# command may exit 75 after running the changed code, and that is a code
# failure (counter-model review, #1411). A naming convention, not a list: a
# new stager joins by its name, and nothing else can.
is_fetch_failure() {
    [[ "$2" == "$EX_FETCH_FAILED" && "$1" == *-stage ]]
}

# WHERE a failure happened, not only which step (issue #1342). A red `clone`
# step - the checkout that runs before any of the change's code - read exactly
# like a red test suite, so a worker debugged its own diff for a network blip.
# Pre-code is decided by the provider's step TYPE (`clone` on Woodpecker) OR
# its EXIT CODE (issue #1411: `EX_FETCH_FAILED` from a `commands`-type stager
# step, e.g. `jq-stage`) - never by a list of step names: a name list is a
# hardcoded universe, and a step renamed or added later would silently fall
# outside it. The exit-code check does not require a `clone` type (a fetch
# failure is never that type) and does not replace it (a `clone` failure
# carries no exit code of this convention at all) - the two signals name
# disjoint step shapes.
#
# The ORIGIN line is what keeps the marker's ABSENCE from being read as
# evidence. Without it, "no FLOW_CI_PRECODE_FAILURE line" would mean "a code
# failure" on every lane that cannot classify at all - GitHub Actions, whose
# checkout is a step inside a job, or a CLI whose template gave no type. Those
# report `unknown`, which is a different answer from `code`. A step with NO
# type, NO exit code and NO cancellation marker is unknown; a step with a type but
# no exit code (the common case - only a fetch failure sets this convention)
# is classified by type alone, exactly as before.
# Cancellation takes precedence over type/exit code. Only a homogeneous known
# category gets its own origin; known combinations are mixed, missing evidence
# remains unknown. The origin line alone surfaces cancellation.
failure_origin() {
    local i n="${#FAILED_STEPS[@]}" precode=0 code=0 canceled=0 t ec
    if [[ "$n" -eq 0 || "$FAILED_STEPS_INCOMPLETE" -eq 1 ]]; then echo "unknown"; return; fi
    for (( i = 0; i < n; i++ )); do
        t="${FAILED_STEP_TYPES[$i]:-}"
        ec="${FAILED_STEP_EXIT_CODES[$i]:-}"
        if [[ "${FAILED_STEP_ERRORS[$i]:-}" == "Canceled" ]]; then
            canceled=$(( canceled + 1 ))
        elif [[ "$t" == "clone" ]] || is_fetch_failure "${FAILED_STEPS[$i]}" "$ec"; then
            precode=$(( precode + 1 ))
        elif [[ -n "$t" ]]; then
            code=$(( code + 1 ))
        else
            echo "unknown"; return
        fi
    done
    if [[ "$canceled" -eq "$n" ]]; then echo "canceled"
    elif [[ "$precode" -eq "$n" ]]; then echo "precode"
    elif [[ "$code" -eq "$n" ]]; then echo "code"
    else echo "mixed"
    fi
}

#: NEGATIVE-CONTROL: controls/flow-ci-status-stalled
#: A server-listed `running` past the repo timeout is dead, not slow (issue #1552).
#: NEGATIVE-CONTROL: controls/flow-ci-status-cancellation
#: Provider Canceled errors are distinct from code failures (issue #1486).
#: NEGATIVE-CONTROL: controls/flow-ci-status
#: ADR 0008 row 10, class G: FLOW_CI_STATUS decides Step 8's deploy-or-stop,
#: and nothing re-derives it (issue #1411). The control answers this script's
#: curl from files through a stub on PATH, varying only a failed step's
#: exit_code, and checks that exit 75 (EX_FETCH_FAILED) reports precode while
#: exit 1 still reports code. See its `limits`.

emit() {
    echo "FLOW_CI_PROVIDER: $PROVIDER"
    echo "FLOW_CI_REF: ${SHA:--}"
    echo "FLOW_CI_REPO: ${REPO:--}"
    echo "FLOW_CI_EVENT: ${PREFER_EVENT:-$DEFAULT_EVENT} (${EVENT_SOURCE}$( (( STRICT_EVENT )) && echo '; strict'))"
    echo "FLOW_CI_PIPELINE: $PIPELINE"
    echo "FLOW_CI_URL: $URL"
    echo "FLOW_CI_WAIT: $WAIT_STATE"
    for step in ${FAILED_STEPS+"${FAILED_STEPS[@]}"}; do
        echo "FLOW_CI_FAILED_STEP: $step"
    done
    if [[ "$STATUS" == "failure" ]]; then
        local i
        for (( i = 0; i < ${#FAILED_STEPS[@]}; i++ )); do
            [[ "${FAILED_STEP_ERRORS[$i]:-}" == "Canceled" ]] && continue
            if [[ "${FAILED_STEP_TYPES[$i]:-}" == "clone" ]] \
                || is_fetch_failure "${FAILED_STEPS[$i]}" "${FAILED_STEP_EXIT_CODES[$i]:-}"; then
                echo "FLOW_CI_PRECODE_FAILURE: ${FAILED_STEPS[$i]}"
            fi
        done
        echo "FLOW_CI_FAILURE_ORIGIN: $(failure_origin)"
    fi
    [[ -n "$STALL_CHECK" ]] && echo "FLOW_CI_STALL_CHECK: $STALL_CHECK"
    if [[ -n "$STALLED_REASON" ]]; then
        echo "FLOW_CI_STALLED: $STALLED_REASON"
        for step in ${STALLED_STEPS+"${STALLED_STEPS[@]}"}; do
            echo "FLOW_CI_STALLED_STEP: $step"
        done
    fi
    echo "FLOW_CI_STATUS: $STATUS"
    if [[ "$WANT_EXIT_CODE" -eq 1 && "$STATUS" == "failure" ]]; then
        exit 1
    fi
    exit 0
}

# ── Resolve checkout, SHA, repo ────────────────────────────────────────────
[[ -n "$CHECK_PATH" ]] || CHECK_PATH="$PWD"
if [[ ! -d "$CHECK_PATH" ]]; then
    echo "flow-ci-status: checkout not found: $CHECK_PATH (fail-open)" >&2
    emit
fi

if [[ -z "$SHA" ]]; then
    SHA="$(git -C "$CHECK_PATH" rev-parse HEAD 2>/dev/null)"
    if [[ -z "$SHA" ]]; then
        echo "flow-ci-status: not a git checkout: $CHECK_PATH (fail-open)" >&2
        emit
    fi
else
    # Accept a short SHA / ref and expand it, so `.commit` compares exactly.
    FULL="$(git -C "$CHECK_PATH" rev-parse "$SHA" 2>/dev/null)"
    [[ -n "$FULL" ]] && SHA="$FULL"
fi

# IN THE DECLARED CHECKOUT, never the caller's cwd (issue #1262). `gh repo
# view` has no -C, so it answered for whatever repository the Bash process
# happened to be standing in - measured: invoked from a kyle clone with
# `--path` naming a CPP checkout, it resolved `cooneycw/kyle`. The SHA was
# anchored to the declared checkout and the repository was not, which is two
# answers about two different trees presented as one.
if [[ -z "$REPO" ]]; then
    REPO="$(cd "$CHECK_PATH" 2>/dev/null && "$GH_BIN" repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)"
fi
if [[ -z "$REPO" ]]; then
    ORIGIN="$(git -C "$CHECK_PATH" remote get-url origin 2>/dev/null)"
    # git@host:owner/name.git  or  https://host/owner/name(.git). The suffix is
    # stripped FIRST: `[^/]+?` is not a lazy quantifier in ERE, so the old
    # single expression swallowed `.git` into the name (issue #1262) and every
    # lookup then asked for `owner/name.git`.
    REPO="$(sed -E -e 's#\.git/?$##' -e 's#^.*[:/]([^/:]+/[^/:]+)$#\1#' <<<"${ORIGIN:-}")"
    [[ "$REPO" == "${ORIGIN%.git}" || "$REPO" == "$ORIGIN" ]] && REPO=""
fi
if [[ -z "$REPO" ]]; then
    echo "flow-ci-status: could not resolve owner/name for $CHECK_PATH (fail-open)" >&2
    emit
fi

# ── Which lane the verdict describes (issue #1262) ─────────────────────────
# A SHA pushed to a PR branch carries BOTH a push and a pull_request pipeline,
# and only one of them is what branch protection requires. The default was a
# hard-coded `push` while this repository (and kyle) require only the pr lane,
# so the helper could report the push pipeline's green over a red required
# check. So the default is now the lane the base branch REQUIRES, read from
# GitHub; when that cannot be decided the old default stands and says so.
derive_event() {
    local default_branch contexts ctx pr=0 push=0
    if ! command -v "$GH_BIN" >/dev/null 2>&1; then
        EVENT_SOURCE="default: gh unavailable, required contexts unreadable"; return
    fi
    default_branch="$("$GH_BIN" api "repos/$REPO" --jq .default_branch 2>/dev/null)"
    if [[ -z "$default_branch" ]]; then
        EVENT_SOURCE="default: default branch unreadable, required contexts unreadable"; return
    fi
    if ! contexts="$("$GH_BIN" api "repos/$REPO/branches/$default_branch/protection/required_status_checks" \
            --jq '.contexts[]' 2>/dev/null)"; then
        EVENT_SOURCE="default: required contexts unreadable on $default_branch"; return
    fi
    # ONLY WOODPECKER'S OWN CONTEXTS DECIDE (counter-model review). Matching any
    # `/pr/` or `/push/` let a neighbouring provider's `other-ci/push/tests`
    # turn a pr-only repository into "both lanes required" and hand the verdict
    # back to the push pipeline.
    while IFS= read -r ctx; do
        case "$ctx" in
            ci/woodpecker/pr/*|ci/woodpecker/pull_request/*) pr=1 ;;
            ci/woodpecker/push/*) push=1 ;;
        esac
    done <<<"$contexts"
    local listed
    listed="$(paste -sd, <<<"$contexts")"
    # The branch NAMED, because it is the DEFAULT branch's protection that was
    # read (counter-model review): this helper resolves a commit, not a PR, so it
    # does not know which base a PR targets. A PR into a differently-protected
    # branch should pass --event; the marker says which branch decided.
    if (( pr && !push )); then
        PREFER_EVENT="pull_request"; EVENT_SOURCE="branch-protection on $default_branch: ${listed}"
    elif (( push && !pr )); then
        PREFER_EVENT="push"; EVENT_SOURCE="branch-protection on $default_branch: ${listed}"
    elif (( pr && push )); then
        EVENT_SOURCE="default: both lanes required on $default_branch (${listed})"
    else
        EVENT_SOURCE="default: no woodpecker lane among required contexts on $default_branch${listed:+ (${listed})}"
    fi
}
if [[ -z "$PREFER_EVENT" ]]; then
    derive_event
fi
[[ -n "$PREFER_EVENT" ]] || PREFER_EVENT="$DEFAULT_EVENT"

# ── jq preflight (issue #789) ──────────────────────────────────────────────
# The Woodpecker API lane and the GitHub Actions lane both parse JSON with jq;
# the `woodpecker-cli` lane (issue #768) does not - it asks for go-template
# output precisely so it needs no formatter. So this is a per-lane flag, NOT an
# early exit: short-circuiting here would disable the one lane that still works.
#
# Without the flag a missing jq was silent: every `jq ... 2>/dev/null` yielded
# empty, the lookup found no REPO_ID, and the script emitted
# `FLOW_CI_STATUS: unknown` and exited 0 - indistinguishable from "no
# credentials" or "no network", which is the reading Step 8 acts on by
# proceeding. Name the real reason instead. It DEGRADES rather than exiting:
# `unknown` is this helper's documented fail-open verdict and Step 8 is built on
# it, so a missing formatter must never be the thing that stops a merge.
HAVE_JQ=1
if ! command -v jq >/dev/null 2>&1; then
    HAVE_JQ=0
    echo "flow-ci-status: jq not found - the Woodpecker API and GitHub Actions lanes need it" >&2
    echo "  Trying the woodpecker-cli lane, which does not. If that is unavailable the" >&2
    echo "  verdict is 'unknown' because of a MISSING TOOL, not because of a CI result." >&2
fi

# ── Woodpecker credentials ─────────────────────────────────────────────────
# Prefer an exported token; otherwise pull host+token from AWS Secrets Manager.
# The secret is read ONCE into shell variables and never printed or argv-passed.
WP_TOKEN="${WOODPECKER_API_TOKEN:-}"
WP_SERVER="${WOODPECKER_SERVER:-${WOODPECKER_HOST:-}}"

if [[ -z "$AWS_BIN" ]]; then
    if [[ -x "$HOME/.local/bin/aws" ]]; then AWS_BIN="$HOME/.local/bin/aws"; else AWS_BIN="aws"; fi
fi

if [[ "$HAVE_JQ" -eq 1 && ( -z "$WP_TOKEN" || -z "$WP_SERVER" ) ]]; then
    # The secret is JSON, so this resolution path needs jq too (issue #789).
    if command -v "$AWS_BIN" >/dev/null 2>&1; then
        SECRET_JSON="$("$AWS_BIN" secretsmanager get-secret-value \
            --secret-id "$SECRET_NAME" --region "$AWS_REGION" \
            --query SecretString --output text 2>/dev/null)"
        if [[ -n "$SECRET_JSON" ]]; then
            [[ -z "$WP_TOKEN" ]] && WP_TOKEN="$(jq -r '.WOODPECKER_API_TOKEN // empty' <<<"$SECRET_JSON" 2>/dev/null)"
            [[ -z "$WP_SERVER" ]] && WP_SERVER="$(jq -r '.WOODPECKER_HOST // .WOODPECKER_URL // empty' <<<"$SECRET_JSON" 2>/dev/null)"
        fi
        unset SECRET_JSON
    fi
fi
WP_SERVER="${WP_SERVER%/}"

wp_api() {
    # $1 = path. Token travels in a header via --header @-, never in argv.
    printf 'Authorization: Bearer %s\n' "$WP_TOKEN" \
        | "$CURL_BIN" -s --max-time 30 -H @- -H "Accept: application/json" "${WP_SERVER}$1" 2>/dev/null
}

# Stalled-pipeline check (issue #1552). Reads ONE pipeline's detail and decides,
# from the server's own record, whether it is dead rather than slow:
#   - running past the repo timeout + grace -> STATUS=stalled (terminal);
#   - terminal pipeline with a workflow or step still `running` -> stalled
#     lines beside the existing `failure` verdict (a cancel that did not land).
# $1 = pipeline number, $2 = repo timeout in minutes ("" when unreadable).
# Never cancels or kills anything; it only reports.
wp_stall_check() {
    local number="$1" timeout_min="$2" detail started now elapsed_min live step
    STALLED_REASON=""; STALLED_STEPS=()
    if ! detail="$(wp_api "/api/repos/$REPO_ID/pipelines/$number")" \
        || ! jq -e '.workflows | type == "array"' <<<"$detail" >/dev/null 2>&1; then
        STALL_CHECK="unavailable (pipeline detail unreadable)"
        return 0
    fi
    live="$(jq -r '[.workflows[]? | select(.state == "running" or .state == "started")]
                   + [.workflows[]?.children[]? | select(.state == "running" or .state == "started")]
                   | length' <<<"$detail" 2>/dev/null)"
    case "$STATUS" in
        failure)
            STALL_CHECK="checked"
            if [[ "${live:-0}" =~ ^[0-9]+$ && "${live:-0}" -gt 0 ]]; then
                STALLED_REASON="terminal-pipeline-live-children"
            fi ;;
        running)
            if [[ ! "$timeout_min" =~ ^[0-9]+$ ]] || [[ "$timeout_min" -eq 0 ]]; then
                STALL_CHECK="unavailable (repo timeout unreadable)"
                return 0
            fi
            started="$(jq -r '.started // 0' <<<"$detail" 2>/dev/null)"
            if [[ ! "$started" =~ ^[0-9]+$ ]] || [[ "$started" -eq 0 ]]; then
                STALL_CHECK="unavailable (pipeline start time unreadable)"
                return 0
            fi
            now="${FLOW_CI_NOW:-$(date +%s)}"
            elapsed_min=$(( (now - started) / 60 ))
            STALL_CHECK="checked"
            if [[ "$elapsed_min" -gt $(( timeout_min + STALL_GRACE_MIN )) ]]; then
                STATUS="stalled"
                STALLED_REASON="past-timeout (${elapsed_min}m > ${timeout_min}m + ${STALL_GRACE_MIN}m grace)"
            fi ;;
        *) return 0 ;;
    esac
    if [[ -n "$STALLED_REASON" ]]; then
        while IFS= read -r step; do
            [[ -n "$step" ]] && STALLED_STEPS+=("$step")
        done < <(jq -r '.workflows[]?.children[]? | select(.state == "running" or .state == "started") | .name' <<<"$detail" 2>/dev/null)
    fi
    return 0
}

# ── Woodpecker lookup ──────────────────────────────────────────────────────
if [[ "$HAVE_JQ" -eq 1 && -n "$WP_TOKEN" && -n "$WP_SERVER" ]]; then
    REPO_JSON="$(wp_api "/api/repos/lookup/$REPO")"
    REPO_ID="$(jq -r '.id // empty' <<<"$REPO_JSON" 2>/dev/null)"
    # Minutes; the AGENT enforces it, which is what makes "past it" evidence
    # of a lost agent rather than of a slow job (issue #1552).
    REPO_TIMEOUT_MIN="$(jq -r '.timeout // empty' <<<"$REPO_JSON" 2>/dev/null)"
    if [[ -n "$REPO_ID" ]]; then
        PROVIDER="woodpecker"
        DEADLINE=$(( $(date +%s) + WAIT_SECS ))
        while :; do
            MATCHES="$(wp_api "/api/repos/$REPO_ID/pipelines?per_page=50" \
                | jq -c --arg sha "$SHA" --arg ev "$PREFER_EVENT" --argjson strict "$STRICT_EVENT" \
                    '[.[] | select(.commit == $sha) | select($strict == 0 or .event == $ev)]
                     | sort_by(.event != $ev)            # preferred event first
                     | map({number, event, status})' 2>/dev/null)"
            COUNT="$(jq -r 'length' <<<"${MATCHES:-[]}" 2>/dev/null || echo 0)"
            if [[ "${COUNT:-0}" -gt 0 ]]; then
                PIPELINE="$(jq -r '.[0].number' <<<"$MATCHES")"
                WP_STATE="$(jq -r '.[0].status' <<<"$MATCHES")"
                URL="${WP_SERVER}/repos/${REPO_ID}/pipeline/${PIPELINE}"
                if [[ "$COUNT" -gt 1 ]]; then
                    echo "flow-ci-status: $COUNT pipelines share $SHA; reporting the '$PREFER_EVENT' one first:" >&2
                    jq -r '.[] | "  #\(.number) \(.event) \(.status)"' <<<"$MATCHES" >&2
                fi
                case "$WP_STATE" in
                    success)                 STATUS="success" ;;
                    failure|error|killed)    STATUS="failure" ;;
                    running|started)         STATUS="running" ;;
                    pending|blocked|created) STATUS="pending" ;;
                    *)                       STATUS="unknown" ;;
                esac
            else
                PIPELINE="-"; STATUS="not-found"
            fi
            # Dead-versus-slow (issue #1552): may turn `running` into the
            # terminal `stalled`, or annotate a `failure` whose children live.
            if [[ "$PIPELINE" != "-" && ( "$STATUS" == "running" || "$STATUS" == "failure" ) ]]; then
                wp_stall_check "$PIPELINE" "$REPO_TIMEOUT_MIN"
            fi

            # Terminal, or out of patience - and SAY which (issue #1262).
            if [[ "$STATUS" == "success" || "$STATUS" == "failure" || "$STATUS" == "stalled" || "$STATUS" == "unknown" ]]; then
                [[ "$WAIT_SECS" -gt 0 ]] && WAIT_STATE="settled"
                break
            fi
            if [[ "$WAIT_SECS" -eq 0 ]]; then break; fi
            if [[ "$(date +%s)" -ge "$DEADLINE" ]]; then WAIT_STATE="expired (${WAIT_SECS}s)"; break; fi
            "$SLEEP_BIN" 15
        done

        # Name the failed steps: pipeline colour cannot tell a red test suite
        # from a red deploy step, and Step 8 needs that distinction.
        if [[ "$STATUS" == "failure" && "$PIPELINE" != "-" ]]; then
            # Name, TYPE, EXIT CODE and ERROR from the one response (issues #1342,
            # #1411). A step with no `type` or `exit_code` field records an
            # empty value, which classifies as unknown (type) or simply
            # uninvolved (exit code - absence is never read as the
            # fetch-failure code). `|`, not a tab: a tab is IFS WHITESPACE,
            # which collapses an empty field and shifts the rest silently
            # (#698/#700).
            while IFS='|' read -r step step_type step_exit_code step_error; do
                if [[ -n "$step" ]]; then
                    FAILED_STEPS+=("$step")
                    FAILED_STEP_TYPES+=("$step_type")
                    FAILED_STEP_EXIT_CODES+=("$step_exit_code")
                    FAILED_STEP_ERRORS+=("$step_error")
                fi
            done < <(wp_api "/api/repos/$REPO_ID/pipelines/$PIPELINE" \
                | jq -r '[.workflows[]?.children[]? | select(.state=="failure" or .state=="error" or .state=="killed") | "\(.name)|\(.type // "")|\(.exit_code // "")|\(.error // "")"] | .[]' 2>/dev/null)
        fi
        emit
    fi
fi

# ── Woodpecker CLI fallback ────────────────────────────────────────────────
if command -v "$WPCLI_BIN" >/dev/null 2>&1; then
    WPCLI_ROWS="$("$WPCLI_BIN" pipeline ls --output-no-headers \
        --output 'go-template={{range .}}{{.Number}}|{{.Status}}|{{.Commit}}|{{.Event}}{{"\n"}}{{end}}' \
        --limit 50 "$REPO" 2>/dev/null)"
    WPCLI_RC=$?
    if [[ "$WPCLI_RC" -eq 0 && -n "$(sed -n '/[^[:space:]]/p' <<<"$WPCLI_ROWS")" ]]; then
        PROVIDER="woodpecker"
        # The canonical web URL needs the numeric repo id, which this lane does not have.
        URL="-"
        DEADLINE=$(( $(date +%s) + WAIT_SECS ))
        while :; do
            MATCHES=()
            while IFS='|' read -r number state commit event; do
                [[ "$commit" == "$SHA" && "$event" == "$PREFER_EVENT" ]] || continue
                MATCHES+=("$number|$state|$commit|$event")
            done <<<"$WPCLI_ROWS"
            while IFS='|' read -r number state commit event; do
                (( STRICT_EVENT )) && continue
                [[ "$commit" == "$SHA" && "$event" != "$PREFER_EVENT" ]] || continue
                MATCHES+=("$number|$state|$commit|$event")
            done <<<"$WPCLI_ROWS"

            COUNT="${#MATCHES[@]}"
            if [[ "$COUNT" -gt 0 ]]; then
                IFS='|' read -r PIPELINE WP_STATE _ _ <<<"${MATCHES[0]}"
                if [[ "$COUNT" -gt 1 ]]; then
                    echo "flow-ci-status: $COUNT pipelines share $SHA; reporting the '$PREFER_EVENT' one first:" >&2
                    for match in "${MATCHES[@]}"; do
                        IFS='|' read -r MATCH_NUMBER MATCH_STATE _ MATCH_EVENT <<<"$match"
                        echo "  #$MATCH_NUMBER $MATCH_EVENT $MATCH_STATE" >&2
                    done
                fi
                case "$WP_STATE" in
                    success)                 STATUS="success" ;;
                    failure|error|killed)    STATUS="failure" ;;
                    running|started)         STATUS="running" ;;
                    pending|blocked|created) STATUS="pending" ;;
                    *)                       STATUS="unknown" ;;
                esac
            else
                PIPELINE="-"; STATUS="not-found"
            fi

            # Terminal, or out of patience - and SAY which (issue #1262).
            if [[ "$STATUS" == "success" || "$STATUS" == "failure" || "$STATUS" == "unknown" ]]; then
                [[ "$WAIT_SECS" -gt 0 ]] && WAIT_STATE="settled"
                break
            fi
            if [[ "$WAIT_SECS" -eq 0 ]]; then break; fi
            if [[ "$(date +%s)" -ge "$DEADLINE" ]]; then WAIT_STATE="expired (${WAIT_SECS}s)"; break; fi
            "$SLEEP_BIN" 15
            WPCLI_ROWS="$("$WPCLI_BIN" pipeline ls --output-no-headers \
                --output 'go-template={{range .}}{{.Number}}|{{.Status}}|{{.Commit}}|{{.Event}}{{"\n"}}{{end}}' \
                --limit 50 "$REPO" 2>/dev/null)"
            WPCLI_RC=$?
            if [[ "$WPCLI_RC" -ne 0 || -z "$(sed -n '/[^[:space:]]/p' <<<"$WPCLI_ROWS")" ]]; then
                STATUS="unknown"
                break
            fi
        done

        if [[ "$STATUS" == "failure" && "$PIPELINE" != "-" ]]; then
            # Captured, not process-substituted, so the exit status is seen. A
            # call that printed some rows and then failed keeps the names it
            # gave (the pre-#1342 behaviour) but cannot vouch that the list is
            # complete, so the origin is unknown (counter-model review pass 2).
            if ! WPCLI_STEP_ROWS="$("$WPCLI_BIN" pipeline ps --format '{{ .step.Name }}|{{ .step.State }}
' "$REPO" "$PIPELINE" 2>/dev/null)"; then
                FAILED_STEPS_INCOMPLETE=1
            fi
            while IFS='|' read -r step state; do
                case "$state" in
                    failure|error|killed) [[ -n "$step" ]] && FAILED_STEPS+=("$step") ;;
                esac
            done <<<"$WPCLI_STEP_ROWS"
            # The step TYPE comes from a SEPARATE call (issue #1342). `.step.Type`
            # is untested against a real woodpecker-cli; folded into the call
            # above, a template that cannot render it would erase the failed-step
            # NAMES too. Here a failed or partial answer only leaves a type empty,
            # which reports `unknown`.
            # Plain rows, not an associative array: `declare -A` is bash 4+.
            # A NON-ZERO exit discards the rows even when some were printed: a
            # partial answer is not a classification (counter-model review).
            if ! WPCLI_TYPE_ROWS="$("$WPCLI_BIN" pipeline ps --format '{{ .step.Name }}|{{ .step.Type }}
' "$REPO" "$PIPELINE" 2>/dev/null)"; then
                WPCLI_TYPE_ROWS=""
            fi
            # The join is by NAME, the only identity these rows carry. A name
            # that appears with two different types (the same step name in two
            # workflows) cannot say which one failed, so it stays unknown rather
            # than borrowing a neighbour's type (counter-model review).
            for step in ${FAILED_STEPS+"${FAILED_STEPS[@]}"}; do
                found_type=""
                seen=0
                while IFS='|' read -r row_step row_type; do
                    [[ "$row_step" == "$step" ]] || continue
                    if [[ "$seen" -eq 0 ]]; then
                        found_type="$row_type"; seen=1
                    elif [[ "$row_type" != "$found_type" ]]; then
                        found_type=""; break
                    fi
                done <<<"$WPCLI_TYPE_ROWS"
                FAILED_STEP_TYPES+=("$found_type")
            done
            # Error is isolated from names and types too: a failed or partial
            # template response must not erase names or lend cancellation to
            # another workflow's identically named step.
            if ! WPCLI_ERROR_ROWS="$("$WPCLI_BIN" pipeline ps --format '{{ .step.Name }}|{{ .step.Error }}
' "$REPO" "$PIPELINE" 2>/dev/null)"; then
                WPCLI_ERROR_ROWS=""
            fi
            for step in ${FAILED_STEPS+"${FAILED_STEPS[@]}"}; do
                found_error=""
                seen=0
                while IFS='|' read -r row_step row_error; do
                    [[ "$row_step" == "$step" ]] || continue
                    if [[ "$seen" -eq 0 ]]; then
                        found_error="$row_error"; seen=1
                    elif [[ "$row_error" != "$found_error" ]]; then
                        found_error=""; break
                    fi
                done <<<"$WPCLI_ERROR_ROWS"
                FAILED_STEP_ERRORS+=("$found_error")
            done
        fi
        emit
    fi
fi

# ── GitHub Actions fallback ────────────────────────────────────────────────
# The run LIST is fetched and filtered here rather than asking gh for `.[0]`,
# so --strict-event can hold on this lane too (counter-model review, #1300): a
# successful push workflow must not end a wait for the pull_request lane. A
# provider that answers with no run on the required event is `not-found`, and a
# --wait keeps waiting for it; the event is a preference without --strict-event.
gha_runs() {
    "$GH_BIN" run list --repo "$REPO" --commit "$SHA" \
        --json status,conclusion,databaseId,url,event 2>/dev/null
}
gha_pick() {
    jq -c --arg ev "$PREFER_EVENT" --argjson strict "$STRICT_EVENT" \
        'if $strict == 1 then [.[] | select(.event == $ev)] else (sort_by(.event != $ev)) end | .[0]' \
        <<<"$1" 2>/dev/null
}
if [[ "$HAVE_JQ" -eq 1 ]] && command -v "$GH_BIN" >/dev/null 2>&1; then
    ALL_RUNS="$(gha_runs)"
    if [[ -n "$ALL_RUNS" && "$(jq -r 'if type == "array" then length else 0 end' <<<"$ALL_RUNS" 2>/dev/null)" -gt 0 ]]; then
        PROVIDER="github-actions"
        DEADLINE=$(( $(date +%s) + WAIT_SECS ))
        while :; do
            RUN_JSON="$(gha_pick "$ALL_RUNS")"
            if [[ -z "$RUN_JSON" || "$RUN_JSON" == "null" ]]; then
                PIPELINE="-"; URL="-"; STATUS="not-found"
            else
                GH_STATUS="$(jq -r '.status // empty' <<<"$RUN_JSON")"
                GH_CONCL="$(jq -r '.conclusion // empty' <<<"$RUN_JSON")"
                PIPELINE="$(jq -r '.databaseId // "-"' <<<"$RUN_JSON")"
                URL="$(jq -r '.url // "-"' <<<"$RUN_JSON")"
                if [[ "$GH_STATUS" == "completed" ]]; then
                    [[ "$GH_CONCL" == "success" ]] && STATUS="success" || STATUS="failure"
                    [[ "$WAIT_SECS" -gt 0 ]] && WAIT_STATE="settled"
                    break
                fi
                STATUS="running"
            fi
            if [[ "$WAIT_SECS" -eq 0 ]]; then break; fi
            if [[ "$(date +%s)" -ge "$DEADLINE" ]]; then WAIT_STATE="expired (${WAIT_SECS}s)"; break; fi
            "$SLEEP_BIN" 15
            ALL_RUNS="$(gha_runs)"
            [[ -n "$ALL_RUNS" ]] || ALL_RUNS="[]"
        done
        if [[ "$STATUS" == "failure" && "$PIPELINE" != "-" ]]; then
            while IFS= read -r step; do
                [[ -n "$step" ]] && FAILED_STEPS+=("$step")
            done < <("$GH_BIN" run view "$PIPELINE" --repo "$REPO" --json jobs \
                --jq '.jobs[]? | select(.conclusion!="success" and .conclusion!="skipped" and .conclusion!="") | .name' 2>/dev/null)
        fi
        emit
    fi
fi

echo "flow-ci-status: no CI provider answered for $REPO @ ${SHA:0:12} (fail-open)" >&2
emit
