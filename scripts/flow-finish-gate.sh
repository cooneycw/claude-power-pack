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
#   is unavailable it degrades to the same Makefile gates the command docs
#   describe - `make lint`, `make test`, `make typecheck` and, since issue
#   #1147, `make verify`; with no Makefile gates either, it skips loudly. The
#   fallback mirrors the runner's `finish` plan target for target: when it ran
#   only lint + test it reproduced the exact false green the plan itself had
#   (issue #617) for every repo without uv or a CPP checkout, and when it ran
#   three of four it did the same thing again for `verify` (issue #1147).
#
#: NEGATIVE-CONTROL: controls/flow-finish-gate
#: NEGATIVE-CONTROL: controls/flow-finish-gate-declared-gates
#: NEGATIVE-CONTROL: controls/flow-finish-gate-plan-reconciliation
#: NEGATIVE-CONTROL: controls/flow-finish-gate-subsumption
#: NEGATIVE-CONTROL: controls/flow-finish-gate-derivation
#
# Usage:
#   flow-finish-gate.sh                  # run the 'finish' quality-gate plan
#   flow-finish-gate.sh --plan check     # pass a different plan through
#   flow-finish-gate.sh --check-summary  # lib.cicd check --summary (Makefile
#                                        # completeness, advisory - see the
#                                        # exit-code table below: it no longer
#                                        # always exits 0 either (issue #1027)
#
# Output ends with a machine-readable verdict line:
#   FLOW_FINISH_GATE: ok | fail | warn | skipped
# A first-attempt failure cleared by the one targeted re-run also prints:
#   RERUN_PASSED: <space-separated pytest node ids>
#
# Exit code (issue #1027 - each verdict gets its OWN code; before this, `ok`,
# `warn` and `skipped` all exited 0, so a caller reading only `$?` (the
# documented `if gate; then proceed; fi` / `gate && git push` shape) could not
# tell "passed cleanly" from "passed but proved nothing" from "did not run at
# all". `fail` was always distinct and is unchanged; usage errors (`exit 2`,
# below the option-parsing loop) predate this issue and are ALSO unchanged -
# do not reuse 2 for `skipped` even though the rest of this repo uses 2 for
# UNKNOWN (`shellcheck-gate.sh`, `dependency-audit.py`): 2 already means "you
# typed the flag wrong" in THIS script, and colliding the two would make a
# usage error indistinguishable from an unrunnable gate.
#
#   verdict  exit  meaning
#   -------  ----  -------
#   ok         0   ran, every gate passed, every gate actually executed
#   fail       1   ran, a gate failed
#   (usage)    2   bad argument or missing --plan value - unchanged, not a verdict
#   warn       3   ran and passed, but something is soft-bad - proceed, report it
#   skipped    4   did NOT run - no evidence either way, never a pass
#
#   warn (exit 3) is --check-summary finding gaps (advisory), OR the gate
#           passed but a gate proved nothing: a quality gate was
#           SKIPPED (issue #628 - `warn (skipped gates: ...)`),
#           a gate RAN but examined nothing (issue #1027 -
#           `warn (zero coverage: ...)`: `ruff check .` on a tree with
#           no Python files warns on stderr, prints "All checks
#           passed!" on stdout and exits 0, so a stage with no input
#           is otherwise indistinguishable from a clean one),
#           or a test step exited 0 having executed no tests
#           (issue #621), OR a failed test was re-run against only
#           its failed ids and PASSED (issue #769 - `warn (rerun
#           passed: ...)`), OR a resumed run carried a step's result
#           from an earlier invocation WITHOUT proof the tree was
#           unchanged since (issue #804 - `warn (carried, unverified:
#           ...)`). A carry the runner verified via tree_signature is
#           NOT a warning - see the #804 note below. Every
#           qualification names the reason.
#   skipped (exit 4) is no runner AND no Makefile/pyproject gates to run.
#
# `warn` and `skipped` are deliberately DIFFERENT exit codes from each other,
# not just from `ok`: "ran, passed, something is soft-bad" and "did not run,
# no evidence" are different facts a caller must be able to branch on
# separately - collapsing them into one non-zero code would fix the ok/warn
# confusion #1027 reports while creating the identical collision one level
# down.
#
# The #621/#628/#769 qualification exists because this helper is the layer the flow
# commands read: a runner that carefully reports "completed WITH WARNINGS"
# would be flattened back to a bare `ok` here, re-hiding the false green one
# level up. Both the runner and the Makefile-less fallback now prefer a gate's
# Makefile target but fall back to `uv run --extra dev <tool>` when pyproject
# configures the tool (issue #628), so a gate SKIPS only when it genuinely
# cannot run - and then it is named, never a silent ok. The warning is a
# signal, not a gate - callers should proceed on it (report it, do not stop),
# which is exactly why it needs a THIRD exit code rather than folding into
# `fail`'s 1.
#
# The #769 opt-in reaches the runner as an environment variable, not a CLI flag,
# because this helper invokes whatever CPP checkout is installed. That checkout
# may predate #769: an unknown env var is ignored, while an unknown argparse flag
# is a hard error that prevents the quality gate from running at all.
#
# #804 - a resumed run and the bare `ok` it must not print silently:
#   The runner can auto-resume a failed run from its last completed step. That
#   is correct for a crash (the tree is unchanged) and wrong for a repair (the
#   fix changed the tree, so the step that would exercise it is exactly the
#   one the resume skips). The runner now hashes the tree at persist time and
#   again before honoring a resume: a mismatch discards the stale state and
#   starts fresh, so a repair-resume can no longer print a bare `ok` while
#   carrying a stale result. This helper's job is the case the runner cannot
#   close on its own - no git, or a state file older than this field - where
#   it still resumes (so a non-git target project does not regress) but marks
#   the carry unverified. This helper turns that into `warn`, never a bare
#   `ok`, and warns ONLY on "carried AND NOT verified" - a verified carry
#   (`tree_verified: true`) is a proven-safe crash-resume, not a warning, and
#   must stay silent: this fleet's runs get killed and resumed often, and
#   warning on every legitimate one trains readers to stop reading the line.
#
# Env (test hooks - unset in normal use):
#   FLOW_GATE_CPP_DIR   override the CPP checkout path (set empty to force
#                       "no checkout found" and exercise the fallback)
#   FLOW_GATE_RERUN     set to 0 to disable the #769 targeted re-run and get
#                       the pre-#769 first-failure-is-fail behaviour

set -uo pipefail

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
trap 'printf "FLOW_FINISH_GATE_EXIT=%d\n" "$?" >&2' EXIT

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
            sed -n '2,90p' "$0" | sed 's/^# \{0,1\}//'
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
        exit 4
    fi
    if [[ ! -f Makefile ]]; then
        echo "NOTE: no Makefile here; skipping Makefile completeness check." >&2
        verdict skipped
        exit 4
    fi
    PYTHONPATH="$CPP_DIR:${PYTHONPATH:-}" uv run --project "$CPP_DIR" python -m lib.cicd check --summary
    if [[ $? -eq 0 ]]; then
        verdict ok
        exit 0
    else
        verdict warn
        exit 3
    fi
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
    #
    # WHICH IDS ARE GATES IS READ FROM THE JSON, never restated here (#1147).
    # The "skipped" array carries every skipped step, gate or not, so it has to
    # be filtered to gates - and this line used to do that with a hardcoded
    # alternation, which was a SECOND copy of lib/cicd/steps.py's
    # GATE_STEP_IDS in a language that cannot import it. The copies drifted
    # once already (#890): `security_scan` was added to the Python set while
    # this regex still listed three names, so the id reached the JSON, was
    # filtered out here, and the marker still said `ok`.
    #
    # The alternation is DELETED rather than extended. Adding a fifth name
    # would have left a list for the sixth gate to be omitted from, which is
    # this issue's own defect shape. The runner now emits the derived set, so
    # there is one declaration (`gate=` on the step) and readers follow it.
    # The KEY LINE IS DROPPED before the values are read. The alternation this
    # replaced could not match `"gates"` because it listed only step names; a
    # general `"[a-z_]+"` matches the key as readily as a value, so `gates`
    # itself landed in the set - found by running the parse rather than reading
    # it. A spurious member is not harmless here: it is a name a skipped step
    # could carry, and the filter would then keep a non-gate as a gate.
    # AWK, NOT A SED RANGE, and the reason is a real bug this replaced. A
    # `/"gates": \[/,/\]/` range NEVER ENDS ON ITS OWN START LINE - sed begins
    # looking for the end pattern on the NEXT line - so an empty set, which
    # json.dumps renders INLINE as `"gates": [],`, ran the range on to the next
    # `]` in the document and swallowed the whole `step_details` block. The ids
    # then came back as `step_details id status success`, and the accountability
    # check below duly failed the run for not executing a gate called `status`.
    # Same anchored, shape-aware style as the `reruns` and `coverage` parsers
    # further down, which is what those exist for.
    GATE_IDS=$(awk '
        /^  "gates": \[\],?$/ { exit }
        /^  "gates": \[$/ { in_gates = 1; next }
        in_gates && /^  \][,]?$/ { exit }
        in_gates {
            id = $0
            sub(/^[[:space:]]*"/, "", id)
            sub(/",?$/, "", id)
            if (id != "") print id
        }
    ' "$RUNNER_JSON" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')

    # THE #1155 RECONCILIATION, read beside its sibling and for the same reason
    # (the JSON is removed before the verdict lanes). Three states, and they are
    # deliberately three:
    #
    #   [...]  the manifest DROPPED a gate the built-in plan of this name
    #          declares - it is not in the plan at all, so it never ran and was
    #          never recorded as skipped
    #   []     reconciled, nothing missing
    #   null   NOT APPLICABLE - no built-in plan of this name, so there is
    #          nothing to reconcile against
    #
    # `null` must never render as `[]`. A plan nobody can check would then
    # report exactly what a clean plan reports, which is unscanned reading as
    # clean - the failure this family of guards exists to refuse.
    DROPPED_FIELD_PRESENT=0
    grep -q '"dropped_gates":' "$RUNNER_JSON" 2>/dev/null && DROPPED_FIELD_PRESENT=1
    DROPPED_NOT_APPLICABLE=0
    grep -q '"dropped_gates": null' "$RUNNER_JSON" 2>/dev/null && DROPPED_NOT_APPLICABLE=1
    DROPPED_GATES=$(awk '
        /^  "dropped_gates": (null|\[\]),?$/ { exit }
        /^  "dropped_gates": \[$/ { in_d = 1; next }
        in_d && /^  \][,]?$/ { exit }
        in_d {
            id = $0
            sub(/^[[:space:]]*"/, "", id)
            sub(/",?$/, "", id)
            if (id != "") print id
        }
    ' "$RUNNER_JSON" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')
    # Gates an aggregate already ran (issue #1152), and the prerequisite make
    # stopped at when an aggregate failed. Read here with the rest, while the
    # JSON still exists.
    SUBSUMED_GATES=$(awk '
        /^  "subsumed_gates": \{\},?$/ { exit }
        /^  "subsumed_gates": \{$/ { in_s = 1; next }
        in_s && /^  \}[,]?$/ { exit }
        in_s {
            id = $0
            sub(/^[[:space:]]*"/, "", id)
            sub(/":.*$/, "", id)
            if (id != "") print id
        }
    ' "$RUNNER_JSON" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')
    SUBSUMED_BY=$(awk '
        /^  "subsumed_gates": \{$/ { in_s = 1; next }
        in_s && /^  \}[,]?$/ { exit }
        in_s { v = $0; sub(/^.*": "/, "", v); sub(/",?$/, "", v); print v }
    ' "$RUNNER_JSON" 2>/dev/null | head -1)
    # Gates recorded NOT-RUN: deferred to an aggregate that then failed, so
    # they never ran (issue #1152). Read from the per-step records because that
    # is where the runner puts them.
    NOT_RUN_IDS=$(awk '
        /^  "step_details": \[$/ { in_details = 1; next }
        in_details && /^  \][,]?$/ { exit }
        in_details && /^      "id": "[^"]*",?$/ {
            id = $0
            sub(/^[[:space:]]*"id": "/, "", id)
            sub(/",?$/, "", id)
        }
        in_details && /^      "status": "not-run",?$/ { if (id != "") print id }
    ' "$RUNNER_JSON" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')
    FAILED_PREREQ=$(sed -n 's/^  "failed_prerequisite": "\([^"]*\)",\?$/\1/p' "$RUNNER_JSON" 2>/dev/null | head -1)

    # The plan name, so the not-applicable line can NAME the plan it could not
    # reconcile rather than reporting an anonymous abstention.
    PLAN_NAME=$(sed -n 's/^  "plan": "\([^"]*\)",\?$/\1/p' "$RUNNER_JSON" 2>/dev/null | head -1)

    # Does the runner SAY, at all? Read here, beside the parse and while the
    # JSON still exists - the temp file is removed further down, before the
    # verdict lanes, so a presence test down there reads a deleted file and
    # reports every run as unreadable. Caught by the existing suite, which is
    # the second time in this issue a check placed away from its input answered
    # a question about something that was no longer there.
    GATE_FIELD_PRESENT=0
    grep -q '"gates":' "$RUNNER_JSON" 2>/dev/null && GATE_FIELD_PRESENT=1

    # WHICH STEPS ACTUALLY EXECUTED, read from the per-step record rather than
    # inferred (issue #1147). The runner emits one object per executed step in
    # `step_details`; anchor on that block so the scalar `"id"` keys inside a
    # nested coverage object or a rerun entry are not mistaken for step ids.
    RAN_IDS=$(awk '
        /^  "step_details": \[$/ { in_details = 1; next }
        in_details && /^  \][,]?$/ { exit }
        in_details && /^      "id": "[^"]*",?$/ {
            id = $0
            sub(/^[[:space:]]*"id": "/, "", id)
            sub(/",?$/, "", id)
            print id
        }
    ' "$RUNNER_JSON" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')

    SKIPPED_GATES=""
    for _sg in $(sed -n '/"skipped": \[/,/\]/{ /"skipped": \[/d; p; }' "$RUNNER_JSON" 2>/dev/null \
        | grep -oE '"[a-z_]+"' | tr -d '"'); do
        for _gid in $GATE_IDS; do
            if [[ "$_sg" == "$_gid" ]]; then
                SKIPPED_GATES="${SKIPPED_GATES:+$SKIPPED_GATES }$_sg"
                break
            fi
        done
    done
    # Pull ids only from #769 entries whose outcome is "passed-in-isolation" -
    # the token the runner records for a re-run that greened when the failed ids
    # ran alone. It was "passed" until issue #900; the rename is the point, since
    # passing alone is the signature of a flake AND of an order-dependent real
    # failure, so the record must not claim the first. This match is ANCHORED, so
    # it does not silently keep working on the old token: a drift between the two
    # stops RERUN_PASSED being emitted and the marker reverts to `ok`, which is
    # #900's exact symptom. tests/test_runner.py pins both directions. The runner's
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
        in_entry && /^      "outcome": "passed-in-isolation"[,]?$/ { passed = 1; next }
        in_entry && /^    \}[,]?$/ {
            if (passed && ids) {
                print ids
            }
            in_entry = 0
        }
    ' "$RUNNER_JSON" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')
    # A step killed by its own budget is NOT a step that failed (issue #812).
    # The runner emits it as a distinct top-level field; read it before the
    # JSON is removed. Anchored on the field name rather than on the error
    # prose, which is the string-matching that would drift.
    TIMED_OUT_STEP=$(sed -n 's/^  "timed_out_step": "\([^"]*\)",\?$/\1/p' \
        "$RUNNER_JSON" 2>/dev/null | head -1)
    TIMED_OUT_AFTER=$(sed -n 's/^  "timed_out_after": \([0-9]*\),\?$/\1/p' \
        "$RUNNER_JSON" 2>/dev/null | head -1)
    # A resumed run may carry a step's result from an earlier invocation
    # (issue #838 follow-up) - fine when the runner PROVED the tree hadn't
    # changed since (issue #804, tree_verified), unverifiable otherwise. Same
    # bracket-anchored array pull as SKIPPED_GATES above; step ids are free-
    # form (not limited to lint/test/typecheck the way gates are), so match
    # any quoted token instead of the fixed alternation.
    CARRIED=$(sed -n '/"carried_from_previous_run": \[/,/\]/p' "$RUNNER_JSON" 2>/dev/null \
        | grep -v ':' | grep -oE '"[^"]+"' | tr -d '"' | tr '\n' ' ' | sed 's/ *$//')
    TREE_VERIFIED=0
    if grep -q '"tree_verified": true' "$RUNNER_JSON" 2>/dev/null; then
        TREE_VERIFIED=1
    fi
    # Gates that ran, exited 0, and examined NOTHING (issue #1027). A step's
    # exit code says the tool did not error, never that it looked at anything:
    # `ruff check .` on a tree with no Python files warns on stderr, prints
    # "All checks passed!" on stdout and exits 0. The runner emits the parsed
    # evidence as a top-level "coverage" object keyed by step id; pull the ids
    # whose state is "zero" without needing jq (the validate container has none).
    #
    # Only "zero" is collected. "unknown" is present in the JSON and stays out
    # of the verdict on purpose - it means the tool said nothing measurable,
    # which is true of every lint harness CPP cannot parse, so grading on it
    # would warn on every run of those repos. The distinction is the whole
    # point: "unknown" makes an unproven stage VISIBLE without making it loud.
    ZERO_COVERAGE_GATES=$(awk '
        /^  "coverage": \{$/ { in_cov = 1; next }
        in_cov && /^  \}[,]?$/ { exit }
        in_cov && /^    "[^"]+": \{$/ {
            id = $0
            sub(/^[[:space:]]*"/, "", id)
            sub(/": \{$/, "", id)
            next
        }
        in_cov && /^      "state": "zero"[,]?$/ { if (id != "") print id; next }
    ' "$RUNNER_JSON" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')
    rm -f "$RUNNER_JSON"
    # Print the #769 evidence before verdict precedence is applied: a later
    # failing step or skipped gates are more serious, but must not erase a flake
    # that also occurred earlier in the same run.
    if [[ -n "$RERUN_PASSED_IDS" ]]; then
        echo "RERUN_PASSED: $RERUN_PASSED_IDS"
    fi
    if [[ "$RUNNER_EXIT" -eq 0 ]]; then
        # FAIL CLOSED, and do it FIRST in this lane. A runner too old to emit
        # the field leaves this script unable to tell which skipped steps were
        # gates; the filter then matches nothing and the marker reads `ok`.
        # That is the silent-subset failure #1147 exists to remove, arriving
        # through the fix for it.
        #
        # It sits INSIDE the green lane rather than beside the parse because
        # this is the only lane where the unreadable set can turn into a pass.
        # A non-zero runner already fails on its own cause, and reporting a
        # version problem there would send a reader whose tests just failed
        # looking at the wrong thing.
        #
        # `verdict` PRINTS, it does not exit - every other call site pairs it
        # with an explicit exit. The first cut of this guard did not, so it
        # emitted `fail (gate set unreadable)` and then fell through to
        # `verdict ok; exit 0`: two markers, exit 0, on the exact input this
        # guard was added to catch. Caught by tests/test_flow_finish_gate.py,
        # which reads the LAST marker, and pinned below by a single-marker
        # assertion so a print-without-exit cannot come back silently.
        # PRESENCE, not emptiness. An EMPTY gate set is a legitimate answer -
        # `--plan deploy` resolves to bootstrap/drift/deploy steps and has no
        # quality gate in it at all - so testing `-z "$GATE_IDS"` would fail
        # every run of such a plan while claiming the runner was too old.
        # Conflating the two is the same error one level down as emitting the
        # field conditionally: "this plan has no gates" and "this runner does
        # not say" have to stay distinguishable, and the field's PRESENCE is
        # what carries that. Found by counter-model review (#1147).
        if [[ "$GATE_FIELD_PRESENT" -ne 1 ]]; then
            echo "flow-finish-gate: the runner JSON carries no 'gates' field, so which steps are quality gates could not be determined." >&2
            echo "  This is NOT a pass: a gate set that cannot be read filters nothing, and every skipped gate would go unreported (#1147)." >&2
            echo "  Expect this against a runner older than #1147; re-run with the current lib/cicd." >&2
            verdict "fail (gate set unreadable)"
            exit 1
        fi
        # EVERY DECLARED GATE MUST BE ACCOUNTED FOR: it ran, or it was recorded
        # as skipped. A gate that is in neither list was declared and then
        # silently dropped from the plan, and nothing else in this script can
        # see that - `skipped` is empty, the filter finds nothing, and the
        # marker reads `ok`.
        #
        # THIS IS NOT HYPOTHETICAL AND IT IS WHY THE CHECK EXISTS. `get_plan_steps`
        # prefers `.claude/cicd_tasks.yml` over `BUILTIN_PLANS` while GATE_STEP_IDS
        # is derived from BUILTIN_PLANS alone, so the two populations come from
        # different files with nothing comparing them. Adding `verify` to the
        # built-in finish plan for #1147 left it dead config in this repository:
        # the runner declared five gates, executed four, recorded none as skipped
        # and printed `ok`. The manifest is fixed, but a manifest can drop any
        # gate at any time - and #617 hit the same precedence trap and wrote the
        # warning INTO that manifest, where a reader of this script never sees it.
        # So the check is here, where the verdict is decided.
        #
        # `fail`, NOT `warn`, and the distinction is the reason. #628's
        # `warn (skipped gates: X)` means "could not run, and here is why" - a
        # RECORDED reason, from a runner whose accounting is consistent. This
        # has no reason: the runner declared a gate and then its own two
        # records of what happened to that gate both omit it. A green from an
        # inconsistent runner is the false green this whole chain exists to
        # stop, so it fails closed rather than degrading to a softer verdict.
        # A gate the manifest DROPPED FROM THE PLAN (issue #1155). Distinct
        # from "declared but never ran" below: that one is an inconsistency
        # inside a single run's own accounting, this one is a disagreement
        # between two FILES - `.claude/cicd_tasks.yml` wins over BUILTIN_PLANS,
        # so a manifest can drop a declared gate and, before #1155, nothing
        # compared them. #1147 shipped a green over four of five gates that
        # way. It fails by name, because a dropped gate is silent where a
        # SKIPPED one is loud: a repository that lacks a target should LIST the
        # step and let `skip_if` skip it, which reports #628's warn WITH the
        # reason attached.
        if [[ "$DROPPED_FIELD_PRESENT" -ne 1 ]]; then
            echo "flow-finish-gate: the runner JSON carries no 'dropped_gates' field, so whether this plan dropped a declared gate was NOT checked." >&2
            echo "  Not checked is not clean: re-run with a lib/cicd carrying #1155." >&2
            verdict "fail (reconciliation unavailable)"
            exit 1
        fi
        if [[ "$DROPPED_NOT_APPLICABLE" -eq 1 ]]; then
            echo "flow-finish-gate: gate reconciliation not applicable: no builtin plan named '${PLAN_NAME:-?}', so there is no declaration to compare this plan against (#1155)." >&2
        elif [[ -n "$DROPPED_GATES" ]]; then
            echo "WARNING: this repository's .claude/cicd_tasks.yml DROPPED quality gate(s) the builtin '${PLAN_NAME:-?}' plan declares: $DROPPED_GATES." >&2
            echo "  The manifest WINS over lib/cicd/steps.py, so those gates are not in the plan at all - they did not run and nothing recorded them as skipped." >&2
            echo "  This gate proved nothing about them. Add each id under plans.${PLAN_NAME:-<plan>}.steps; if this repo has no such target, LIST the step anyway and let skip_if skip it, which reports it by name instead of silently (#617, #1147, #1155)." >&2
            verdict "fail (gate dropped from the plan: $DROPPED_GATES)"
            exit 1
        fi

        UNACCOUNTED_GATES=""
        for _gid in $GATE_IDS; do
            _seen=0
            for _rid in $RAN_IDS $SKIPPED_GATES; do
                if [[ "$_gid" == "$_rid" ]]; then _seen=1; break; fi
            done
            [[ "$_seen" -eq 1 ]] || UNACCOUNTED_GATES="${UNACCOUNTED_GATES:+$UNACCOUNTED_GATES }$_gid"
        done
        if [[ -n "$UNACCOUNTED_GATES" ]]; then
            echo "WARNING: the runner DECLARED these quality gates and then neither ran them nor recorded them as skipped: $UNACCOUNTED_GATES. They were dropped from the executed plan, so this gate proved nothing about them - do not read as 'safe to merge'. Check that .claude/cicd_tasks.yml lists each one under its plan: that manifest WINS over lib/cicd/steps.py, so a gate defined there and not referenced is dead config (issues #617, #1147)." >&2
            verdict "fail (declared but never ran: $UNACCOUNTED_GATES)"
            exit 1
        fi
        # Report the DERIVATION by name, never silently (issue #1152). A reader
        # seeing three gates absent from the executed list must be able to see
        # WHY without re-deriving it - and `subsumed` is the one status here
        # that means a gate RAN, so leaving it unsaid would look exactly like
        # the silent omissions #1147 and #1155 exist to refuse.
        # A NOT-RUN GATE CANNOT COEXIST WITH A PASS (issue #1152). `not-run`
        # means a gate was deferred to an aggregate that then failed, so make
        # stopped before reaching it. If the runner nonetheless reports overall
        # success, its own two records disagree - and the reading that lets the
        # run through is the one that says three quality gates were never
        # executed. Fail closed on the disagreement rather than believing the
        # top-level verdict, which is what a gate reading only `success` did.
        if [[ -n "$NOT_RUN_IDS" ]]; then
            echo "WARNING: the runner reported SUCCESS while recording quality gate(s) as NOT RUN: $NOT_RUN_IDS." >&2
            echo "  A gate is recorded not-run when it was deferred to an aggregate that FAILED - make stops at its first failing prerequisite - so these were never executed and nothing proved anything about them." >&2
            echo "  A success verdict and a not-run gate cannot both be true; this gate believes the per-step record (issue #1152)." >&2
            verdict "fail (recorded not-run: $NOT_RUN_IDS)"
            exit 1
        fi
        if [[ -n "$SUBSUMED_GATES" ]]; then
            echo "flow-finish-gate: SUBSUMED: $SUBSUMED_GATES ran as direct prerequisite(s) of 'make ${SUBSUMED_BY:-the aggregate}', which passed - not re-run (issue #1152)."
        fi
        if [[ -n "$SKIPPED_GATES" ]]; then
            echo "WARNING: quality gates did NOT run: $SKIPPED_GATES (no Makefile target and no configured tool). This gate proved nothing about those checks - do not read as 'safe to merge' (issue #628)." >&2
            verdict "warn (skipped gates: $SKIPPED_GATES)"
            exit 3
        fi
        if [[ -n "$ZERO_COVERAGE_GATES" ]]; then
            echo "WARNING: quality gate(s) RAN but a MEASURED PART of them examined NOTHING: $ZERO_COVERAGE_GATES. A green from a check with no input is not evidence about this change - do not read as 'safe to merge'. The runner warning above names what was measured; for a multi-check gate it is that check, not the whole gate (issue #1027)." >&2
            verdict "warn (zero coverage: $ZERO_COVERAGE_GATES)"
            exit 3
        fi
        # A carried step is fine when the runner PROVED the tree hadn't
        # changed (tree_verified) - that is a genuine crash-resume, and
        # warning on it would fire on every ordinary killed-and-resumed run
        # in this fleet, training readers to ignore the line (issue #804).
        # Warn ONLY when something was carried AND that proof is missing -
        # no git, or a state file older than the tree_signature field - which
        # is exactly the case this helper, not the runner, has to catch.
        if [[ -n "$CARRIED" && "$TREE_VERIFIED" -ne 1 ]]; then
            echo "WARNING: step(s) carried a result from an earlier invocation WITHOUT proof the tree was unchanged since: $CARRIED. This gate did not verify those steps against the current tree - do not read as 'safe to merge' until you know why verification was unavailable (issue #804)." >&2
            verdict "warn (carried, unverified: $CARRIED)"
            exit 3
        fi
        if [[ -n "$RERUN_PASSED_IDS" ]]; then
            RERUN_COUNT=$(awk '{ print NF }' <<< "$RERUN_PASSED_IDS")
            echo "WARNING: $RERUN_COUNT test(s) FAILED on the first attempt and PASSED when re-run against only their failed ids (issue #769): $RERUN_PASSED_IDS. The flow is not stopped - but this run is NOT a clean pass: either these are the documented host-state flakes, or you have a real intermittent failure. Never summarize this run as \"tests passed\"." >&2
            verdict "warn (rerun passed: $RERUN_PASSED_IDS)"
            exit 3
        fi
        if [[ "$QUALIFIED" -eq 1 ]]; then
            # Do NOT name a single cause here (issue #939). QUALIFIED is set by
            # the mere PRESENCE of "warnings" in the runner JSON, and that
            # collection carries three different findings: #621 "exited 0 having
            # executed no tests", #838 "SOME invocation executed nothing while
            # the total looked healthy", and #939 "no summary could be parsed
            # from either stream, so the result is UNKNOWN" - and any kind
            # added later. Only the first means no tests executed; the list is
            # illustrative and deliberately NOT repeated in the message, since
            # a message that enumerates causes goes stale the moment a fourth
            # is added. For #939 the suite may have run
            # thousands, and failing to RECOGNIZE a summary establishes nothing
            # about what ran. This line asserted #621 for all of them - a gate
            # stating a fact it had not established, which is the defect class
            # the runner-side fix addresses one layer down.
            #
            # #838 already falsified it before #939 widened the collection. The
            # reason that went unnoticed for the whole life of #838 is that no
            # test asserted anything about this sentence; the property is now
            # pinned in tests/test_flow_finish_gate.py rather than the wording.
            echo "WARNING: the gate passed but the runner QUALIFIED it (see \"warnings\" above) - at least one test step's result is not a clean pass, and the warnings state which. Do not read this as 'safe to merge' until you know why." >&2
            verdict warn
            exit 3
        fi
        verdict ok
        exit 0
    fi
    if [[ -n "$TIMED_OUT_STEP" ]]; then
        # Distinguished from a test failure deliberately. A reader told
        # "FAILED" debugs a suite that never finished; the useful facts are
        # that the step ran out of budget, that this says NOTHING about
        # whether it would have passed, and how to give it more. Still exit 1:
        # an unfinished gate has not shown the tree is good.
        echo "TIMEOUT: step '$TIMED_OUT_STEP' was killed after ${TIMED_OUT_AFTER:-its}s - it did NOT fail, it did not finish." >&2
        echo "  This proves nothing about the tree either way. Do not triage the tests; they were still running." >&2
        echo "  A suite grows every merge and no constant tracks that, so this budget will need raising again:" >&2
        echo "        CPP_GATE_TEST_TIMEOUT=<seconds> <re-run the gate>" >&2
        echo "  If it times out at a budget far above the suite's real cost, suspect a hang rather than growth (issue #812)." >&2
        verdict "fail (timeout: $TIMED_OUT_STEP after ${TIMED_OUT_AFTER:-?}s)"
        exit 1
    fi
    if [[ -n "$FAILED_PREREQ" ]]; then
        # An aggregate has many prerequisites - `verify` has 29 in this repo -
        # so `fail` alone asks the reader to search all of them. make named the
        # one it stopped at; carry it (issue #1152).
        echo "flow-finish-gate: the failing step is an aggregate; make stopped at prerequisite '$FAILED_PREREQ'." >&2
        verdict "fail (at prerequisite $FAILED_PREREQ)"
        exit 1
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
# Stated, never silent (issue #1152). This lane cannot import the Python
# Makefile reader the runner lane derives subsumption with, and adding a second
# reader here would be the duplicate-parser defect this repository keeps
# removing. So it runs every gate - correct, just slower - and SAYS so, because
# a reader comparing the two lanes' timings deserves the reason.
echo "flow-finish-gate: subsumption: not derived in the fallback lane; all gates run." >&2
RAN=0
FAILED=0
SKIPPED_GATES=""
# Initialized explicitly because `set -uo pipefail` is in force above: the
# fallback verdict below reads this unconditionally, and an unset variable
# there aborts the gate rather than reporting one. The runner lane assigns it
# from the JSON before its own read, so the two lanes never share this value.
ZERO_COVERAGE_GATES=""
# What actually executed, and by which route (issue #808). The marker alone
# cannot distinguish a repo where this fallback IS the gate from one where it
# is a fraction of it, and a reader should not have to infer coverage from an
# absence of complaints.
RAN_GATES=""
# The same information as RAN_GATES, as bare ids. RAN_GATES is display text
# ("make lint uv:test") and the #808 aggregate detector needs to MATCH on ids,
# so it gets its own accumulator rather than a parse of the display string.
RAN_GATE_IDS=""
UNRUN_AGGREGATE=""
AGGREGATE_TARGET=""
RERUN_PASSED_IDS=""
UV_OK=0
command -v uv >/dev/null 2>&1 && UV_OK=1

# Zero-coverage markers a NON-test gate prints when it examined nothing
# (issue #1027). The runner lane gets this from lib/cicd/coverage.py via the
# JSON; this fallback lane has no runner and no step_details, and in a
# container it is the ORDINARY path rather than the degraded one - so the
# same question has to be answerable here or the container case, which is
# exactly where #1027 measured the problem, stays blind.
#
# Deliberately only the POSITIVE statements of zero. A tool that says nothing
# about its coverage yields nothing here, matching the Python side's `unknown`:
# warning on silence would fire on every non-Python gate, on every run.
detect_zero_coverage() {
    # $1 = captured combined output of one gate
    awk '
        /^[[:space:]]*warning:[[:space:]]*No Python files found under the given path/ { found = 1 }
        /no issues found in 0 source files/ { found = 1 }
        /checked 0 source files/ { found = 1 }
        /SECURITY_GATE:/ && /secrets-scanned=0([^0-9]|$)/ { found = 1 }
        END { exit !found }
    ' "$1" 2>/dev/null
}

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
        RAN_GATES="${RAN_GATES:+$RAN_GATES }make ${id}"
        RAN_GATE_IDS="${RAN_GATE_IDS:+$RAN_GATE_IDS }${id}"
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
            local gate_output
            gate_output=$(mktemp "${TMPDIR:-/tmp}/flow-finish-gate-cov.XXXXXX")
            make "${id}" 2>&1 | tee "$gate_output"
            [[ "${PIPESTATUS[0]}" -eq 0 ]] || FAILED=1
            if detect_zero_coverage "$gate_output"; then
                ZERO_COVERAGE_GATES="${ZERO_COVERAGE_GATES:+$ZERO_COVERAGE_GATES }${id}"
            fi
            rm -f "$gate_output"
        fi
        RAN=1
    # `-n "$token"` is load-bearing (#1147). `grep -q ""` matches EVERY line, so
    # a gate with no tool equivalent - `verify`, which is a Makefile aggregate -
    # would otherwise fall into this branch on any pyproject.toml at all and run
    # `uv run --extra dev` with no arguments. An empty token means "there is no
    # degraded form of this gate", and the skip below is the honest answer.
    elif [[ "$UV_OK" -eq 1 && -n "$token" ]] && grep -q "${token}" pyproject.toml 2>/dev/null; then
        echo "flow-finish-gate: running fallback gate 'uv run --extra dev ${uvargs}' (no '${id}' Makefile target)"
        RAN_GATES="${RAN_GATES:+$RAN_GATES }uv:${id}"
        RAN_GATE_IDS="${RAN_GATE_IDS:+$RAN_GATE_IDS }${id}"
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
            local gate_output
            gate_output=$(mktemp "${TMPDIR:-/tmp}/flow-finish-gate-cov.XXXXXX")
            # shellcheck disable=SC2086
            uv run --extra dev ${uvargs} 2>&1 | tee "$gate_output"
            [[ "${PIPESTATUS[0]}" -eq 0 ]] || FAILED=1
            if detect_zero_coverage "$gate_output"; then
                ZERO_COVERAGE_GATES="${ZERO_COVERAGE_GATES:+$ZERO_COVERAGE_GATES }${id}"
            fi
            rm -f "$gate_output"
        fi
        RAN=1
    else
        SKIPPED_GATES="${SKIPPED_GATES:+$SKIPPED_GATES }${id}"
    fi
}

# Find a Makefile target whose prerequisites are a SUPERSET of the three gates
# this fallback knows (issue #808). Such a target is the repo's real gate, and
# running three of its nine prerequisites while reporting `ok` is a true
# statement about a fraction of the gate presented as a verdict on the tree.
#
# Derived from the Makefile rather than a hardcoded name like `verify` or
# `check`: a list of names someone has to remember to extend is the enumeration
# this whole ticket is about. The test is structural - does a target depend on
# at least two of lint/test/typecheck AND on something else we did not run.
#
# Line continuations are joined first: this repo's own `verify` spans four
# lines, so a line-at-a-time scan would see one prerequisite and miss five.
detect_aggregate_gate() {
    [[ -f Makefile ]] || return 0
    # $1 = the gate ids this lane actually ran, space separated.
    awk '
        # Join backslash continuations into one logical line.
        { line = line $0
          if (line ~ /\\$/) { sub(/\\$/, " ", line); next }
          print line; line = "" }
        END { if (line != "") print line }
    ' Makefile 2>/dev/null | awk -F: -v ran="$1" '
        # The known-set is DERIVED from what this lane ran, never restated.
        # It used to be the literal lint/test/typecheck - a second hardcoded
        # copy of the gate list in the same file whose first copy is what
        # #1147 deleted, and it went stale the moment `verify` was added: the
        # detector would have called a `verify` prerequisite unrun while this
        # lane was running `make verify` three lines above.
        BEGIN { n = split(ran, r, /[[:space:]]+/); for (i = 1; i <= n; i++) if (r[i] != "") RAN[r[i]] = 1 }
        # Special targets (.PHONY, .DEFAULT_GOAL) list gate names as DATA, not
        # as prerequisites - .PHONY names every phony target in the file, so it
        # trivially "depends on" lint, test and typecheck and matched first.
        # Caught by running the detector against this repo rather than a
        # fixture: the real Makefile has a .PHONY line and a synthetic one
        # would not.
        /^\./ { next }
        # BUFFERED, because the question needs two passes. Pass one expands the
        # ran-set with the prerequisites of targets this lane actually invoked;
        # pass two looks for an aggregate whose prerequisites are not covered.
        # A streaming scan cannot do that: whether `check-all` names an unrun
        # prerequisite depends on whether `verify`, possibly defined LATER in
        # the file, already ran it. Counter-model review found the missing
        # expansion - with `verify: lint test typecheck extra-check` and
        # `check-all: lint test typecheck extra-check`, running `make verify`
        # executes extra-check and the detector still called it unrun, so
        # adding a second aggregate that names the same prerequisites changed
        # the verdict without changing what was verified.
        /^[a-zA-Z0-9_-]+[[:space:]]*:[^=]/ { line[++count] = $0 }
        END {
            # Pass 1: running a target ran its prerequisites.
            #
            # One level deep, deliberately. A transitive walk would need a
            # full dependency graph and cycle handling to answer a question
            # whose remedy is the same either way ("run the aggregate
            # yourself"); one level covers the shape that occurs - an
            # aggregate naming checkers directly - and a deeper chain simply
            # leaves the warning on, which is the safe direction.
            for (i = 1; i <= count; i++) {
                split(line[i], part, ":")
                target = part[1]
                gsub(/[[:space:]]/, "", target)
                if (!(target in RAN)) continue
                n = split(part[2], dep, /[[:space:]]+/)
                for (j = 1; j <= n; j++) if (dep[j] != "") COVERED[dep[j]] = 1
            }
            for (d in COVERED) RAN[d] = 1

            # Pass 2: an aggregate this lane did NOT run, naming prerequisites
            # nothing ran either.
            for (i = 1; i <= count; i++) {
                split(line[i], part, ":")
                target = part[1]
                gsub(/[[:space:]]/, "", target)
                # A target this lane RAN is not an unrun aggregate - running it
                # ran its prerequisites, whatever they are. Without this the
                # #1147 fallback call to `make verify` would be followed by a
                # warning saying the prerequisites of verify "did NOT run
                # here", which is the gate asserting a fact its own previous
                # line falsified.
                if (target in RAN) continue
                known = 0; extra = ""
                n = split(part[2], dep, /[[:space:]]+/)
                for (j = 1; j <= n; j++) {
                    d = dep[j]
                    if (d == "") continue
                    if (d in RAN) { known++ }
                    else { extra = extra (extra == "" ? "" : " ") d }
                }
                # Two of the gates we ran, plus at least one we did not.
                if (known >= 2 && extra != "") {
                    print target "\t" extra
                    exit
                }
            }
        }
    '
}

if [[ -f Makefile || -f pyproject.toml ]]; then
    run_fallback_gate lint "ruff check ." "ruff"
    run_fallback_gate test "pytest" "pytest"
    # Typecheck is a hard step in every shipped CI template, so the fallback
    # runs it too - otherwise a repo that degrades here gets the same
    # local-green-then-CI-red the runner plan had before #617.
    run_fallback_gate typecheck "mypy ." "mypy"
    # `verify` runs HERE TOO (#1147). A gate declared in the finish plan must be
    # either invoked by this lane or named in FALLBACK_UNRUNNABLE_GATES with a
    # reason - tests/test_runner.py asserts it - so leaving it out would have
    # been a decision, not an omission, and the wrong one: this lane runs make
    # targets directly, which is exactly what `verify` is.
    #
    # The degraded lane exists when the runner is unavailable, and that is
    # precisely when a full local verification matters most; a lane that
    # covered three of verify's prerequisites and called itself a gate would
    # reproduce #1147 inside the fallback for it. The empty tool argument says
    # there is no `uv run` equivalent: a repo with no verify target SKIPS, and
    # run_fallback_gate reports the skip by name.
    run_fallback_gate verify "" ""
fi

# Report what actually executed, before any verdict (issue #808). A reader
# should be able to see the coverage rather than infer it from the absence of a
# complaint.
if [[ -n "$RAN_GATES" ]]; then
    echo "flow-finish-gate: gates executed: $RAN_GATES"
fi

# Does this repo define a larger gate we did not run?
if [[ "$RAN" -gt 0 ]]; then
    _aggregate="$(detect_aggregate_gate "$RAN_GATE_IDS")"
    if [[ -n "$_aggregate" ]]; then
        AGGREGATE_TARGET="${_aggregate%%$'\t'*}"
        UNRUN_AGGREGATE="${_aggregate#*$'\t'}"
    fi
fi

if [[ "$RAN" -eq 0 && -z "$SKIPPED_GATES" ]]; then
    echo "WARNING: no deterministic runner and no Makefile/pyproject lint/test/typecheck gates - quality gates SKIPPED." >&2
    verdict skipped
    exit 4
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
    exit 3
fi
if [[ -n "$ZERO_COVERAGE_GATES" ]]; then
    echo "WARNING: quality gate(s) RAN but a MEASURED PART of them examined NOTHING: $ZERO_COVERAGE_GATES. A green from a check with no input is not evidence about this change - do not read as 'safe to merge'. The runner warning above names what was measured; for a multi-check gate it is that check, not the whole gate (issue #1027)." >&2
    verdict "warn (zero coverage: $ZERO_COVERAGE_GATES)"
    exit 3
fi
if [[ -n "$UNRUN_AGGREGATE" ]]; then
    # Same sentence as #628's, for the same reason: this gate proved nothing
    # about those checks. The difference is only how they came to be unrun -
    # #628's could not run, these were never looked for.
    echo "WARNING: this repo's 'make $AGGREGATE_TARGET' also runs: $UNRUN_AGGREGATE. Those did NOT run here - the fallback ran only: $RAN_GATES. This gate proved nothing about them; run 'make $AGGREGATE_TARGET' for the repo's full gate (issue #808)." >&2
    verdict "warn (not run by fallback: $UNRUN_AGGREGATE)"
    exit 3
fi
if [[ -n "$RERUN_PASSED_IDS" ]]; then
    RERUN_COUNT=$(awk '{ print NF }' <<< "$RERUN_PASSED_IDS")
    echo "WARNING: $RERUN_COUNT test(s) FAILED on the first attempt and PASSED when re-run against only their failed ids (issue #769): $RERUN_PASSED_IDS. The flow is not stopped - but this run is NOT a clean pass: either these are the documented host-state flakes, or you have a real intermittent failure. Never summarize this run as \"tests passed\"." >&2
    verdict "warn (rerun passed: $RERUN_PASSED_IDS)"
    exit 3
fi
verdict ok
exit 0
