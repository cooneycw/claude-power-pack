#!/usr/bin/env bash
# flow-finish-gate.sh - Deterministic quality-gate runner invocation for the
# flow commands (issue #613, the #581 pattern).
#
# Problem:
#   /flow:auto Step 6 (and the Step-7/merge re-gate, /flow:finish Step 2) run
#   the deterministic CI/CD runner as:
#
#       PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" \
#           python -m lib.cicd run --plan finish
#
#   A leading env-var assignment plus an interpolated $CPP_DIR can never match
#   a permission allow-rule PREFIX, so the line prompts as CODE-EXEC on every
#   finish and every merge re-gate. Same structural friction #581 removed from
#   Step 1 by extracting flow-start-resolve.sh: put the compound plumbing in
#   ONE audited script at a stable path, allowlist that path, invoke it BARE.
#
# What it does:
#   Resolves the CPP checkout, checks `uv`, and invokes the runner with the
#   documented PYTHONPATH / `uv run --project` contract (PYTHONPATH names the
#   PARENT of lib/ so `-m lib.cicd` resolves for external projects too, and uv
#   pins the >= 3.11 interpreter plus pydantic - issue #430). When the runner
#   is unavailable it degrades to `make lint` + `make test` + `make typecheck`,
#   the same fallback the command docs describe; with no Makefile gates either,
#   it skips loudly. The fallback mirrors the runner's `finish` plan target for
#   target: when it ran only lint + test it reproduced the exact false green the
#   plan itself had (issue #617) for every repo without uv or a CPP checkout.
#
# Usage:
#   flow-finish-gate.sh                  # run the 'finish' quality-gate plan
#   flow-finish-gate.sh --plan check     # pass a different plan through
#   flow-finish-gate.sh --check-summary  # lib.cicd check --summary (Makefile
#                                        # completeness, advisory: always exit 0)
#
# Output ends with a machine-readable verdict line:
#   FLOW_FINISH_GATE: ok | fail | warn | skipped
# A first-attempt failure cleared by the one targeted re-run also prints:
#   RERUN_PASSED: <space-separated pytest node ids>
#
#   ok      gate passed AND every gate actually executed        -> exit 0
#   fail    gate failed                                         -> exit 1
#   warn    --check-summary found gaps (advisory), OR the gate   -> exit 0
#           passed but a gate proved nothing: a quality gate was
#           SKIPPED (issue #628 - `warn (skipped gates: ...)`),
#           or a test step exited 0 having executed no tests
#           (issue #621), OR a failed test was re-run against only
#           its failed ids and PASSED (issue #769 - `warn (rerun
#           passed: ...)`). Every qualification names the reason.
#   skipped no runner AND no Makefile/pyproject gates to run     -> exit 0
#
# The #621/#628/#769 qualification exists because this helper is the layer the flow
# commands read: a runner that carefully reports "completed WITH WARNINGS"
# would be flattened back to a bare `ok` here, re-hiding the false green one
# level up. Both the runner and the Makefile-less fallback now prefer a gate's
# Makefile target but fall back to `uv run --extra dev <tool>` when pyproject
# configures the tool (issue #628), so a gate SKIPS only when it genuinely
# cannot run - and then it is named, never a silent ok. Exit status is
# unchanged (0) - the warning is a signal, not a gate.
#
# The #769 opt-in reaches the runner as an environment variable, not a CLI flag,
# because this helper invokes whatever CPP checkout is installed. That checkout
# may predate #769: an unknown env var is ignored, while an unknown argparse flag
# is a hard error that prevents the quality gate from running at all.
#
# Env (test hooks - unset in normal use):
#   FLOW_GATE_CPP_DIR   override the CPP checkout path (set empty to force
#                       "no checkout found" and exercise the fallback)
#   FLOW_GATE_RERUN     set to 0 to disable the #769 targeted re-run and get
#                       the pre-#769 first-failure-is-fail behaviour

set -uo pipefail

PLAN="finish"
MODE="gate"
RERUN_ENABLED="${FLOW_GATE_RERUN:-1}"
MAX_RERUN_IDS=25
expect_plan=0
for arg in "$@"; do
    if [[ "$expect_plan" -eq 1 ]]; then
        PLAN="$arg"
        expect_plan=0
        continue
    fi
    case "$arg" in
        --plan) expect_plan=1 ;;
        --plan=*) PLAN="${arg#--plan=}" ;;
        --check-summary) MODE="check-summary" ;;
        --help|-h)
            sed -n '2,69p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "flow-finish-gate: unknown argument: $arg" >&2
            exit 2
            ;;
    esac
done
if [[ "$expect_plan" -eq 1 || -z "$PLAN" ]]; then
    echo "flow-finish-gate: --plan requires a value" >&2
    exit 2
fi

verdict() { echo "FLOW_FINISH_GATE: $1"; }

# --- Locate the CPP checkout (same search the command docs use) -------------
if [[ -n "${FLOW_GATE_CPP_DIR+x}" ]]; then
    CPP_DIR="$FLOW_GATE_CPP_DIR"
else
    CPP_DIR=""
    for dir in "$HOME/Projects/claude-power-pack" /opt/claude-power-pack "$HOME/.claude-power-pack"; do
        if [[ -d "$dir" && -f "$dir/CLAUDE.md" ]]; then
            CPP_DIR="$dir"
            break
        fi
    done
fi

RUNNER_OK=0
if [[ -n "$CPP_DIR" ]] && command -v uv >/dev/null 2>&1; then
    RUNNER_OK=1
else
    REASON=$([[ -z "$CPP_DIR" ]] && echo "CPP checkout not found" || echo "uv not installed")
fi

# --- Advisory Makefile-completeness mode (/flow:check Step 5) ---------------
if [[ "$MODE" == "check-summary" ]]; then
    if [[ "$RUNNER_OK" -eq 0 ]]; then
        echo "NOTE: lib.cicd unavailable ($REASON); skipping Makefile completeness check." >&2
        verdict skipped
        exit 0
    fi
    if [[ ! -f Makefile ]]; then
        echo "NOTE: no Makefile here; skipping Makefile completeness check." >&2
        verdict skipped
        exit 0
    fi
    PYTHONPATH="$CPP_DIR:${PYTHONPATH:-}" uv run --project "$CPP_DIR" python -m lib.cicd check --summary
    if [[ $? -eq 0 ]]; then
        verdict ok
    else
        verdict warn
    fi
    exit 0
fi

# --- Primary path: the deterministic runner ---------------------------------
if [[ "$RUNNER_OK" -eq 1 ]]; then
    echo "flow-finish-gate: running deterministic gate (lib.cicd run --plan $PLAN, CPP at $CPP_DIR)"
    # Tee the runner's JSON (stdout) so the #621 qualification can be read back
    # while the user still sees it live; stderr - the per-step progress log -
    # streams straight through untouched.
    RUNNER_JSON=$(mktemp "${TMPDIR:-/tmp}/flow-finish-gate.XXXXXX")
    if [[ "$RERUN_ENABLED" == "1" ]]; then
        CPP_GATE_RERUN_FAILED=1 PYTHONPATH="$CPP_DIR:${PYTHONPATH:-}" uv run --project "$CPP_DIR" python -m lib.cicd run --plan "$PLAN" \
            | tee "$RUNNER_JSON"
        RUNNER_EXIT=${PIPESTATUS[0]}
    else
        # Pass an explicit 0 rather than simply declining to set the variable:
        # an opt-out that only omits the assignment does not disable anything
        # when CPP_GATE_RERUN_FAILED=1 is already exported, which is the normal
        # case for a NESTED gate (CPP's own suite runs under an outer gate that
        # exported it). FLOW_GATE_RERUN=0 has to override an inherited value,
        # not merely abstain from setting one.
        CPP_GATE_RERUN_FAILED=0 PYTHONPATH="$CPP_DIR:${PYTHONPATH:-}" uv run --project "$CPP_DIR" python -m lib.cicd run --plan "$PLAN" \
            | tee "$RUNNER_JSON"
        RUNNER_EXIT=${PIPESTATUS[0]}
    fi
    QUALIFIED=0
    if grep -q '"warnings"' "$RUNNER_JSON" 2>/dev/null; then
        QUALIFIED=1
    fi
    # Quality gates the runner skip_if-skipped (issue #628): a skipped gate
    # verified nothing about the change, so the marker must report `warn` and
    # NAME the skipped gates rather than flatten the run to a bare `ok` - the
    # false green this helper exists to prevent one level up. The runner emits
    # them as a top-level "skipped": [...] JSON array; pull the gate ids out of
    # that block without needing jq (the validate container has none). Anchor on
    # the array-opening bracket so the scalar "skipped": <n> INSIDE the #621
    # "tests" object is not mistaken for the array (json.dumps(indent=2) always
    # multi-lines the array).
    SKIPPED_GATES=$(sed -n '/"skipped": \[/,/\]/p' "$RUNNER_JSON" 2>/dev/null \
        | grep -oE '"(lint|test|typecheck)"' | tr -d '"' | tr '\n' ' ' | sed 's/ *$//')
    # Pull ids only from #769 entries whose outcome is "passed". The runner's
    # json.dumps(indent=2) shape gives the top-level array and each entry stable
    # indentation, so this small state machine stays readable without jq (which
    # is absent from the validate container). Failed/inconclusive entries are
    # deliberately discarded because their non-zero runner exit already wins.
    RERUN_PASSED_IDS=$(awk '
        /^  "reruns": \[$/ { in_reruns = 1; next }
        in_reruns && /^  \][,]?$/ { exit }
        in_reruns && /^    \{$/ {
            in_entry = 1
            in_ids = 0
            passed = 0
            ids = ""
            next
        }
        in_entry && /^      "ids": \[$/ { in_ids = 1; next }
        in_ids && /^      \][,]?$/ { in_ids = 0; next }
        in_ids {
            id = $0
            sub(/^[[:space:]]*"/, "", id)
            sub(/"[,]?$/, "", id)
            ids = ids (ids ? " " : "") id
            next
        }
        in_entry && /^      "outcome": "passed"[,]?$/ { passed = 1; next }
        in_entry && /^    \}[,]?$/ {
            if (passed && ids) {
                print ids
            }
            in_entry = 0
        }
    ' "$RUNNER_JSON" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')
    rm -f "$RUNNER_JSON"
    # Print the #769 evidence before verdict precedence is applied: a later
    # failing step or skipped gates are more serious, but must not erase a flake
    # that also occurred earlier in the same run.
    if [[ -n "$RERUN_PASSED_IDS" ]]; then
        echo "RERUN_PASSED: $RERUN_PASSED_IDS"
    fi
    if [[ "$RUNNER_EXIT" -eq 0 ]]; then
        if [[ -n "$SKIPPED_GATES" ]]; then
            echo "WARNING: quality gates did NOT run: $SKIPPED_GATES (no Makefile target and no configured tool). This gate proved nothing about those checks - do not read as 'safe to merge' (issue #628)." >&2
            verdict "warn (skipped gates: $SKIPPED_GATES)"
            exit 0
        fi
        if [[ -n "$RERUN_PASSED_IDS" ]]; then
            RERUN_COUNT=$(awk '{ print NF }' <<< "$RERUN_PASSED_IDS")
            echo "WARNING: $RERUN_COUNT test(s) FAILED on the first attempt and PASSED when re-run against only their failed ids (issue #769): $RERUN_PASSED_IDS. The flow is not stopped - but this run is NOT a clean pass: either these are the documented host-state flakes, or you have a real intermittent failure. Never summarize this run as \"tests passed\"." >&2
            verdict "warn (rerun passed: $RERUN_PASSED_IDS)"
            exit 0
        fi
        if [[ "$QUALIFIED" -eq 1 ]]; then
            echo "WARNING: the gate passed but the runner QUALIFIED it (see \"warnings\" above) - a test step exited 0 without executing any tests (issue #621). Do not read this as 'safe to merge' until you know why." >&2
            verdict warn
            exit 0
        fi
        verdict ok
        exit 0
    fi
    verdict fail
    exit 1
fi

# --- Fallback: Makefile gates (same degrade path the command docs document) --
# Mirrors the runner's #628 gate discovery and #769 targeted re-run: each gate
# prefers its Makefile target but falls back to `uv run --extra dev <tool>` when
# pyproject configures the tool and no target exists, and a gate that can run
# NEITHER is reported as `warn` with the skipped gates named - never a bare `ok`.
echo "NOTE: deterministic runner unavailable ($REASON); using Makefile fallback." >&2
RAN=0
FAILED=0
SKIPPED_GATES=""
RERUN_PASSED_IDS=""
UV_OK=0
command -v uv >/dev/null 2>&1 && UV_OK=1

parse_fallback_failed_ids() {
    # pytest's short summary is enough for the human report; --last-failed uses
    # pytest's cache for the actual narrowed selection (issue #769). The re-run
    # APPENDS to any host PYTEST_ADDOPTS rather than replacing it, the way the
    # runner's rerun_env does - overwriting it would silently drop the caller's
    # own pytest options only on the re-run, so the two attempts would not be
    # the same invocation.
    awk '
        /^[[:space:]]*(FAILED|ERROR)[[:space:]]+/ {
            id = $2
            if ((id ~ /::/ || id ~ /\.py$/) && !seen[id]++) {
                printf "%s%s", separator, id
                separator = " "
            }
        }
    ' "$1" 2>/dev/null
}

run_fallback_gate() {
    # $1=id  $2=uv-tool-args  $3=pyproject-token
    local id="$1" uvargs="$2" token="$3"
    if grep -q "^${id}:" Makefile 2>/dev/null; then
        echo "flow-finish-gate: running fallback gate 'make ${id}'"
        if [[ "$id" == "test" && "$RERUN_ENABLED" == "1" ]]; then
            local first_output gate_exit failed_ids failed_count
            first_output=$(mktemp "${TMPDIR:-/tmp}/flow-finish-gate-test.XXXXXX")
            make "${id}" 2>&1 | tee "$first_output"
            gate_exit=${PIPESTATUS[0]}
            if [[ "$gate_exit" -ne 0 ]]; then
                failed_ids=$(parse_fallback_failed_ids "$first_output")
                failed_count=$(awk '{ print NF }' <<< "$failed_ids")
                if [[ -n "$failed_ids" && "$failed_count" -le "$MAX_RERUN_IDS" ]]; then
                    echo "flow-finish-gate: RE-RUNNING failed id(s) once (issue #769): $failed_ids"
                    if PYTEST_ADDOPTS="${PYTEST_ADDOPTS:+$PYTEST_ADDOPTS }--last-failed --last-failed-no-failures none" make "${id}"; then
                        RERUN_PASSED_IDS="${RERUN_PASSED_IDS:+$RERUN_PASSED_IDS }${failed_ids}"
                    else
                        FAILED=1
                    fi
                else
                    FAILED=1
                fi
            fi
            rm -f "$first_output"
        else
            make "${id}" || FAILED=1
        fi
        RAN=1
    elif [[ "$UV_OK" -eq 1 ]] && grep -q "${token}" pyproject.toml 2>/dev/null; then
        echo "flow-finish-gate: running fallback gate 'uv run --extra dev ${uvargs}' (no '${id}' Makefile target)"
        if [[ "$id" == "test" && "$RERUN_ENABLED" == "1" ]]; then
            local first_output gate_exit failed_ids failed_count
            first_output=$(mktemp "${TMPDIR:-/tmp}/flow-finish-gate-test.XXXXXX")
            # shellcheck disable=SC2086
            uv run --extra dev ${uvargs} 2>&1 | tee "$first_output"
            gate_exit=${PIPESTATUS[0]}
            if [[ "$gate_exit" -ne 0 ]]; then
                failed_ids=$(parse_fallback_failed_ids "$first_output")
                failed_count=$(awk '{ print NF }' <<< "$failed_ids")
                if [[ -n "$failed_ids" && "$failed_count" -le "$MAX_RERUN_IDS" ]]; then
                    echo "flow-finish-gate: RE-RUNNING failed id(s) once (issue #769): $failed_ids"
                    # shellcheck disable=SC2086
                    if PYTEST_ADDOPTS="${PYTEST_ADDOPTS:+$PYTEST_ADDOPTS }--last-failed --last-failed-no-failures none" uv run --extra dev ${uvargs}; then
                        RERUN_PASSED_IDS="${RERUN_PASSED_IDS:+$RERUN_PASSED_IDS }${failed_ids}"
                    else
                        FAILED=1
                    fi
                else
                    FAILED=1
                fi
            fi
            rm -f "$first_output"
        else
            # shellcheck disable=SC2086
            uv run --extra dev ${uvargs} || FAILED=1
        fi
        RAN=1
    else
        SKIPPED_GATES="${SKIPPED_GATES:+$SKIPPED_GATES }${id}"
    fi
}

if [[ -f Makefile || -f pyproject.toml ]]; then
    run_fallback_gate lint "ruff check ." "ruff"
    run_fallback_gate test "pytest" "pytest"
    # Typecheck is a hard step in every shipped CI template, so the fallback
    # runs it too - otherwise a repo that degrades here gets the same
    # local-green-then-CI-red the runner plan had before #617.
    run_fallback_gate typecheck "mypy ." "mypy"
fi

if [[ "$RAN" -eq 0 && -z "$SKIPPED_GATES" ]]; then
    echo "WARNING: no deterministic runner and no Makefile/pyproject lint/test/typecheck gates - quality gates SKIPPED." >&2
    verdict skipped
    exit 0
fi
# Print the #769 evidence BEFORE verdict precedence, exactly as the runner path
# does: a later gate failing is the more serious verdict, but it must not erase a
# flake that already happened in the same run. Printing this after the `fail`
# branch lost the ids on precisely the red-and-flaky run that is hardest to read
# - the fallback silently diverging from the runner is the #617/#621/#628 trap.
if [[ -n "$RERUN_PASSED_IDS" ]]; then
    echo "RERUN_PASSED: $RERUN_PASSED_IDS"
fi
if [[ "$FAILED" -eq 1 ]]; then
    verdict fail
    exit 1
fi
if [[ -n "$SKIPPED_GATES" ]]; then
    echo "WARNING: quality gates did NOT run: $SKIPPED_GATES (no Makefile target and no runnable tool). This gate proved nothing about those checks - do not read as 'safe to merge' (issue #628)." >&2
    verdict "warn (skipped gates: $SKIPPED_GATES)"
    exit 0
fi
if [[ -n "$RERUN_PASSED_IDS" ]]; then
    RERUN_COUNT=$(awk '{ print NF }' <<< "$RERUN_PASSED_IDS")
    echo "WARNING: $RERUN_COUNT test(s) FAILED on the first attempt and PASSED when re-run against only their failed ids (issue #769): $RERUN_PASSED_IDS. The flow is not stopped - but this run is NOT a clean pass: either these are the documented host-state flakes, or you have a real intermittent failure. Never summarize this run as \"tests passed\"." >&2
    verdict "warn (rerun passed: $RERUN_PASSED_IDS)"
    exit 0
fi
verdict ok
exit 0
