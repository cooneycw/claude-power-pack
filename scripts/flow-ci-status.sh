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
#                  Default: push.
#   --wait [SECS]  Poll until the status is terminal or SECS elapse
#                  (default 600, 15s interval). Without it, report once.
#   --exit-code    Exit 1 when the verdict is `failure`. Every other verdict,
#                  including `unknown`, still exits 0.
#
# Output ends with a machine-readable contract - the failed-step lines, when
# present, immediately precede the verdict:
#   FLOW_CI_PROVIDER: woodpecker | github-actions | none
#   FLOW_CI_REF: <sha>
#   FLOW_CI_PIPELINE: <number|->
#   FLOW_CI_URL: <url|->
#   FLOW_CI_FAILED_STEP: <name>        (repeated, only on failure)
#   FLOW_CI_STATUS: success | failure | running | pending | not-found | unknown
#
# Env (test hooks - unset in normal use):
#   FLOW_CI_CURL   override the `curl` binary
#   FLOW_CI_AWS    override the `aws` binary
#   FLOW_CI_WPCLI  override the `woodpecker-cli` binary
#   FLOW_CI_GH     override the `gh` binary
#   FLOW_CI_SLEEP  override the `sleep` binary (make --wait instant in tests)

set -uo pipefail

SHA=""
CHECK_PATH=""
REPO=""
PREFER_EVENT="push"
WAIT_SECS=0
SECRET_NAME="${CPP_WOODPECKER_SECRET:-essent-ai}"
AWS_REGION="${AWS_REGION:-us-east-1}"
WANT_EXIT_CODE=0

CURL_BIN="${FLOW_CI_CURL:-curl}"
AWS_BIN="${FLOW_CI_AWS:-}"
WPCLI_BIN="${FLOW_CI_WPCLI:-woodpecker-cli}"
GH_BIN="${FLOW_CI_GH:-gh}"
SLEEP_BIN="${FLOW_CI_SLEEP:-sleep}"

die_usage() {
    echo "flow-ci-status: $1" >&2
    echo "usage: flow-ci-status.sh [SHA] [--path <dir>] [--repo <owner/name>] [--event <e>] [--wait [SECS]] [--exit-code]" >&2
    exit 2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --path)        CHECK_PATH="${2:-}"; [[ -n "$CHECK_PATH" ]] || die_usage "--path needs a directory"; shift 2 ;;
        --path=*)      CHECK_PATH="${1#*=}"; shift ;;
        --repo)        REPO="${2:-}"; [[ -n "$REPO" ]] || die_usage "--repo needs owner/name"; shift 2 ;;
        --repo=*)      REPO="${1#*=}"; shift ;;
        --event)       PREFER_EVENT="${2:-}"; [[ -n "$PREFER_EVENT" ]] || die_usage "--event needs a value"; shift 2 ;;
        --event=*)     PREFER_EVENT="${1#*=}"; shift ;;
        --secret-name) SECRET_NAME="${2:-}"; shift 2 ;;
        --secret-name=*) SECRET_NAME="${1#*=}"; shift ;;
        --region)      AWS_REGION="${2:-}"; shift 2 ;;
        --region=*)    AWS_REGION="${1#*=}"; shift ;;
        --exit-code)   WANT_EXIT_CODE=1; shift ;;
        --wait)
            # Optional numeric argument: `--wait` alone means the default.
            if [[ "${2:-}" =~ ^[0-9]+$ ]]; then WAIT_SECS="$2"; shift 2; else WAIT_SECS=600; shift; fi
            ;;
        --wait=*)      WAIT_SECS="${1#*=}"; [[ "$WAIT_SECS" =~ ^[0-9]+$ ]] || die_usage "--wait needs seconds"; shift ;;
        -h|--help)     sed -n '2,62p' "$0"; exit 0 ;;
        -*)            die_usage "unknown argument: $1" ;;
        *)             [[ -z "$SHA" ]] || die_usage "unexpected argument: $1"; SHA="$1"; shift ;;
    esac
done

PROVIDER="none"
PIPELINE="-"
URL="-"
STATUS="unknown"
FAILED_STEPS=()

emit() {
    echo "FLOW_CI_PROVIDER: $PROVIDER"
    echo "FLOW_CI_REF: ${SHA:--}"
    echo "FLOW_CI_PIPELINE: $PIPELINE"
    echo "FLOW_CI_URL: $URL"
    for step in ${FAILED_STEPS+"${FAILED_STEPS[@]}"}; do
        echo "FLOW_CI_FAILED_STEP: $step"
    done
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

if [[ -z "$REPO" ]]; then
    REPO="$("$GH_BIN" repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)"
fi
if [[ -z "$REPO" ]]; then
    ORIGIN="$(git -C "$CHECK_PATH" remote get-url origin 2>/dev/null)"
    # git@host:owner/name.git  or  https://host/owner/name(.git)
    REPO="$(sed -E 's#^.*[:/]([^/:]+/[^/]+?)(\.git)?$#\1#' <<<"${ORIGIN:-}")"
    [[ "$REPO" == "$ORIGIN" ]] && REPO=""
fi
if [[ -z "$REPO" ]]; then
    echo "flow-ci-status: could not resolve owner/name for $CHECK_PATH (fail-open)" >&2
    emit
fi

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

# ── Woodpecker lookup ──────────────────────────────────────────────────────
if [[ "$HAVE_JQ" -eq 1 && -n "$WP_TOKEN" && -n "$WP_SERVER" ]]; then
    REPO_ID="$(wp_api "/api/repos/lookup/$REPO" | jq -r '.id // empty' 2>/dev/null)"
    if [[ -n "$REPO_ID" ]]; then
        PROVIDER="woodpecker"
        DEADLINE=$(( $(date +%s) + WAIT_SECS ))
        while :; do
            MATCHES="$(wp_api "/api/repos/$REPO_ID/pipelines?per_page=50" \
                | jq -c --arg sha "$SHA" --arg ev "$PREFER_EVENT" \
                    '[.[] | select(.commit == $sha)]
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

            # Terminal, or out of patience.
            if [[ "$STATUS" == "success" || "$STATUS" == "failure" || "$STATUS" == "unknown" ]]; then break; fi
            if [[ "$WAIT_SECS" -eq 0 || "$(date +%s)" -ge "$DEADLINE" ]]; then break; fi
            "$SLEEP_BIN" 15
        done

        # Name the failed steps: pipeline colour cannot tell a red test suite
        # from a red deploy step, and Step 8 needs that distinction.
        if [[ "$STATUS" == "failure" && "$PIPELINE" != "-" ]]; then
            while IFS= read -r step; do
                [[ -n "$step" ]] && FAILED_STEPS+=("$step")
            done < <(wp_api "/api/repos/$REPO_ID/pipelines/$PIPELINE" \
                | jq -r '[.workflows[]?.children[]? | select(.state=="failure" or .state=="error" or .state=="killed") | .name] | .[]' 2>/dev/null)
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

            # Terminal, or out of patience.
            if [[ "$STATUS" == "success" || "$STATUS" == "failure" || "$STATUS" == "unknown" ]]; then break; fi
            if [[ "$WAIT_SECS" -eq 0 || "$(date +%s)" -ge "$DEADLINE" ]]; then break; fi
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
            while IFS='|' read -r step state; do
                case "$state" in
                    failure|error|killed) [[ -n "$step" ]] && FAILED_STEPS+=("$step") ;;
                esac
            done < <("$WPCLI_BIN" pipeline ps --format '{{ .step.Name }}|{{ .step.State }}
' "$REPO" "$PIPELINE" 2>/dev/null)
        fi
        emit
    fi
fi

# ── GitHub Actions fallback ────────────────────────────────────────────────
if [[ "$HAVE_JQ" -eq 1 ]] && command -v "$GH_BIN" >/dev/null 2>&1; then
    RUN_JSON="$("$GH_BIN" run list --repo "$REPO" --commit "$SHA" \
        --json status,conclusion,databaseId,url --jq '.[0]' 2>/dev/null)"
    if [[ -n "$RUN_JSON" && "$RUN_JSON" != "null" ]]; then
        PROVIDER="github-actions"
        DEADLINE=$(( $(date +%s) + WAIT_SECS ))
        while :; do
            GH_STATUS="$(jq -r '.status // empty' <<<"$RUN_JSON")"
            GH_CONCL="$(jq -r '.conclusion // empty' <<<"$RUN_JSON")"
            PIPELINE="$(jq -r '.databaseId // "-"' <<<"$RUN_JSON")"
            URL="$(jq -r '.url // "-"' <<<"$RUN_JSON")"
            if [[ "$GH_STATUS" == "completed" ]]; then
                [[ "$GH_CONCL" == "success" ]] && STATUS="success" || STATUS="failure"
                break
            fi
            STATUS="running"
            if [[ "$WAIT_SECS" -eq 0 || "$(date +%s)" -ge "$DEADLINE" ]]; then break; fi
            "$SLEEP_BIN" 15
            RUN_JSON="$("$GH_BIN" run list --repo "$REPO" --commit "$SHA" \
                --json status,conclusion,databaseId,url --jq '.[0]' 2>/dev/null)"
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
