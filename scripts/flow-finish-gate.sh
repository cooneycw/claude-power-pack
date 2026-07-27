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
#
#   ok      gate passed (runner, or Makefile fallback)         -> exit 0
#   fail    gate failed                                        -> exit 1
#   warn    --check-summary found gaps (advisory), OR the gate  -> exit 0
#           passed but the runner qualified it (issue #621: a
#           test step that exited 0 having executed no tests)
#   skipped no runner AND no Makefile gates to run             -> exit 0
#
# The #621 qualification exists because this helper is the layer the flow
# commands read: a runner that carefully reports "completed WITH WARNINGS"
# would be flattened back to a bare `ok` here, re-hiding the false green one
# level up. Exit status is unchanged (0) - the warning is a signal, not a gate.
#
# Env (test hooks - unset in normal use):
#   FLOW_GATE_CPP_DIR   override the CPP checkout path (set empty to force
#                       "no checkout found" and exercise the fallback)

set -uo pipefail

PLAN="finish"
MODE="gate"
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
            sed -n '2,44p' "$0" | sed 's/^# \{0,1\}//'
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
    PYTHONPATH="$CPP_DIR:${PYTHONPATH:-}" uv run --project "$CPP_DIR" python -m lib.cicd run --plan "$PLAN" \
        | tee "$RUNNER_JSON"
    RUNNER_EXIT=${PIPESTATUS[0]}
    QUALIFIED=0
    if grep -q '"warnings"' "$RUNNER_JSON" 2>/dev/null; then
        QUALIFIED=1
    fi
    rm -f "$RUNNER_JSON"
    if [[ "$RUNNER_EXIT" -eq 0 ]]; then
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
echo "NOTE: deterministic runner unavailable ($REASON); using Makefile fallback." >&2
RAN=0
FAILED=0
if [[ -f Makefile ]]; then
    if grep -q "^lint:" Makefile; then
        echo "flow-finish-gate: running fallback gate 'make lint'"
        make lint || FAILED=1
        RAN=1
    fi
    if grep -q "^test:" Makefile; then
        echo "flow-finish-gate: running fallback gate 'make test'"
        make test || FAILED=1
        RAN=1
    fi
    # Typecheck is a hard step in every shipped CI template, so the fallback
    # runs it too - otherwise a repo that degrades here gets the same
    # local-green-then-CI-red the runner plan had before #617.
    if grep -q "^typecheck:" Makefile; then
        echo "flow-finish-gate: running fallback gate 'make typecheck'"
        make typecheck || FAILED=1
        RAN=1
    fi
fi
if [[ "$RAN" -eq 0 ]]; then
    echo "WARNING: no deterministic runner and no Makefile lint/test/typecheck targets - quality gates SKIPPED." >&2
    verdict skipped
    exit 0
fi
if [[ "$FAILED" -eq 1 ]]; then
    verdict fail
    exit 1
fi
verdict ok
exit 0
