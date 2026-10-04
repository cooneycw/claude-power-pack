---
description: Run quality checks (lint + test + typecheck + security) without committing
allowed-tools: Bash(make:*), Bash(grep:*), Bash(test:*), Bash(python3:*), Bash(PYTHONPATH=*), Bash(git:*), Bash(~/.claude/scripts/flow-finish-gate.sh:*), Read
---

# Flow: Check - Run Quality Gates Without Committing

Run lint, test, typecheck and security checks to verify code quality. Does not commit, push, or create a PR.

Use this to validate your changes before running `/flow:finish`.

## Instructions

When the user invokes `/flow:check`, perform these steps:

### Step 1: Detect Available Checks

```bash
CHECKS_RUN=0
CHECKS_PASS=0
CHECKS_WARN=0
CHECKS_FAIL=0

# Detect security scanner
HAS_SECURITY=false
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/lib/security/__init__.py" ]; then
    CPP_DIR="$dir"
    HAS_SECURITY=true
    break
  fi
done

# Detect Makefile completeness checker
HAS_CICD=false
if [ -n "$CPP_DIR" ] && [ -f "$CPP_DIR/lib/cicd/__init__.py" ]; then
    HAS_CICD=true
fi
```

### Step 2: Run Lint, Tests and Typecheck - with a durable execution record

Lint, test and typecheck run through the audited gate helper's `check` plan,
which asks the CPP runner to keep a record of what IT executed (issue #1366):
per check, its status, exit, timestamps, how much it examined, and any skip or
not-run reason, bound to this HEAD and working-tree content, in
`<git-common-dir>/cpp-evidence/flow-check/`. Without it, a green `/flow:check`
left nothing behind but this report, because the runner's own state file is a
resume file deleted on success. The record is never committed and never inside
the working tree. See `docs/agents/execution-evidence.md` in the CPP checkout.

Invoke it BARE (#581 discipline - the inline `lib.cicd run` shape cannot match
an allowlist rule, issue #613):

```bash
~/.claude/scripts/flow-finish-gate.sh --plan check --evidence flow-check
```

(Exit 127 - helper not installed: suggest `/flow:repair` and fall back to
`${CLAUDE_PLUGIN_ROOT}/scripts/flow-finish-gate.sh`, else the CPP-checkout copy.
Exit 2 with `unknown argument: --evidence` means the installed helper predates
#1366: re-run without `--evidence flow-check` and report that no record was
written.)

The `check` plan is exempt from the counter-model enrolment `/flow:finish`
enforces - `/flow:check` produces no PR (issue #1366, the same reason as Step 5's
check-summary mode). Read one table row per step id (`lint`, `test`,
`typecheck`) from the runner JSON's `step_details`, and count each into
`CHECKS_RUN` / `CHECKS_PASS` / `CHECKS_WARN` / `CHECKS_FAIL`. Use the verdict
marker for the qualifications:

- `FLOW_FINISH_GATE: ok` (exit 0) - every step ran and passed.
- `FLOW_FINISH_GATE: warn (...)` (exit 3) - repeat the qualification verbatim. A
  `skipped gates:` name is a SKIP row and a `zero coverage:` or no-tests name is
  a WARN row - never a PASS.
- `FLOW_FINISH_GATE: fail` (exit 1) - the failing step is a FAIL row.
- `FLOW_FINISH_GATE: skipped` (exit 4) - no runner and no Makefile gates: three
  SKIP rows.

When the runner is unavailable (no CPP checkout, no `uv`) the helper runs the
same three Makefile targets itself and prints `CPP_EXECUTION_EVIDENCE: none` -
the fallback writes no record. The runner prefers a step's Makefile target and
falls back to the configured tool, so a repository with no `lint:` target but a
ruff configuration still runs lint (issue #628). typecheck runs alongside lint
and test because every shipped CI template runs it as a hard step - a check that
omits it reports green on a tree CI will reject (issue #617).

### Step 4: Run Security Quick Scan

```bash
if [[ "$HAS_SECURITY" == "true" ]]; then
    echo "Running: security gate (flow_finish)"
    PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" python -m lib.security gate flow_finish
    SEC_EXIT=$?
    CHECKS_RUN=$((CHECKS_RUN + 1))
    if [[ $SEC_EXIT -eq 0 ]]; then
        CHECKS_PASS=$((CHECKS_PASS + 1))
    elif [[ $SEC_EXIT -eq 2 ]]; then
        # Exit code 2 = warnings only (HIGH findings)
        CHECKS_WARN=$((CHECKS_WARN + 1))
    else
        CHECKS_FAIL=$((CHECKS_FAIL + 1))
    fi
fi
```

### Step 5: Run Makefile Completeness Check (optional)

The audited gate helper owns the `lib.cicd` invocation contract (CPP-checkout
resolution, the `uv` check, the #430 `PYTHONPATH` / `uv run --project` shape -
issue #613). Its `--check-summary` mode is advisory - this step never blocks
the flow regardless of what it exits (issue #1027 gave `ok`/`warn`/`skipped`
their own exit codes - 0/3/4 - so it no longer always exits 0; count by the
printed word below, not by treating any exit as failure). Invoke it BARE
(#581 discipline; on exit 127 the helper is not installed - suggest
`/flow:repair` and count the check as SKIP):

```bash
~/.claude/scripts/flow-finish-gate.sh --check-summary
```

- `FLOW_FINISH_GATE: ok` (exit 0) - count a PASS.
- `FLOW_FINISH_GATE: warn (zero coverage: <gates>)` (exit 3, issue #1027) - the named
  gates ran, exited 0, and a MEASURED PART of them examined NOTHING; count a WARN and
  repeat the runner's warning verbatim, since a check with no input produces a green that
  is not evidence - and for a multi-check gate the measurement names that check, not the
  whole gate.
- `FLOW_FINISH_GATE: warn` (exit 3) - count a WARN (non-blocking); this also means a test
  failed on the first attempt and PASSED when re-run against only its failed ids
  (issue #769) - the ids are on the `RERUN_PASSED:` line above the marker;
  proceed, but report them and never call the run a clean pass.
- `FLOW_FINISH_GATE: skipped` (exit 4) - `lib/cicd` or Makefile unavailable: count a SKIP.

### Step 5b: Guard Against Silently-Ignored New Files (advisory)

A blanket `.gitignore` rule (e.g. `*.json`) can swallow a file you meant to
commit - `git add` no-ops with no error (issue #430, Finding 1). Surface it:

```bash
if [ -n "$CPP_DIR" ] && [ -x "$CPP_DIR/scripts/check-ignored-additions.sh" ]; then
    "$CPP_DIR/scripts/check-ignored-additions.sh"
    IGN_EXIT=$?
    CHECKS_RUN=$((CHECKS_RUN + 1))
    # Exit 3 blocks in a linked worktree (issue #1258): a non-scratch ignored
    # file there was written by this run, and a clean clone will not have it.
    # In the primary checkout the script stays advisory and exits 0.
    if [ "$IGN_EXIT" -eq 0 ]; then
        CHECKS_PASS=$((CHECKS_PASS + 1))
    else
        CHECKS_FAIL=$((CHECKS_FAIL + 1))
    fi
fi
```

### Step 5c: Read the Execution Record

Ask the reader what the record just written supports, rather than restating the
table (issue #1366). Locate it, then verify it - both bare:

```bash
python3 "$CPP_DIR/scripts/execution-evidence-verify.py" latest flow-check
python3 "$CPP_DIR/scripts/execution-evidence-verify.py" <path printed above>
```

The runner also prints the path on stderr as `CPP_EXECUTION_EVIDENCE: <outcome>
<path>`; either source is fine. Skip this step when Step 2 printed
`CPP_EXECUTION_EVIDENCE: none` or ran without `--evidence`, and report
`none`.

- `EXECUTION_EVIDENCE: supported` (exit 0) - repeat its `EXECUTION_EVIDENCE_CLAIM`
  line verbatim. That sentence is the exact claim the record supports, and it
  says what it does NOT attest.
- `not-supported` (exit 3) - list each `EXECUTION_EVIDENCE_REASON`. This is the
  expected answer whenever a check failed, was skipped or examined nothing; it is
  the record agreeing with the table, not a second failure.
- `unknown` (exit 4), or `EXECUTION_EVIDENCE_LATEST: none` - say the run left no
  readable record. Never report it as supported.

The record covers lint, test and typecheck only. Steps 4, 5 and 5b are not in it,
and the report must not imply they are.

### Step 6: Report Results

Present a summary report:

```markdown
## Flow Check Results

| Check | Status | Details |
|-------|--------|---------|
| Lint (`make lint`) | PASS/FAIL/SKIP | All checks passed / 3 errors / No Makefile |
| Tests (`make test`) | PASS/FAIL/SKIP | 211 passed / 2 failed / No Makefile |
| Typecheck (`make typecheck`) | PASS/FAIL/SKIP | No issues / 15 errors / No `typecheck:` target |
| Security scan | PASS/WARN/FAIL/SKIP | Clean / 1 HIGH warning / 1 CRITICAL / lib/security not available |
| Makefile completeness | PASS/WARN/SKIP | 6/6 targets / 1 missing / lib/cicd not available |
| Execution record | supported/not-supported/unknown/none | the reader's claim, or its reasons |

**Summary: {CHECKS_PASS} passed, {CHECKS_WARN} warnings, {CHECKS_FAIL} failed ({CHECKS_RUN} checks run)**
```

Status symbols:
- **PASS** - Check succeeded
- **WARN** - Non-blocking issue found (proceed with caution)
- **FAIL** - Blocking issue found (fix before `/flow:finish`)
- **SKIP** - Check not available (no Makefile, lib not installed)

### Final Message

Based on results:
- **All pass:** "Ready for `/flow:finish`."
- **Warnings only:** "Warnings found but non-blocking. Review before `/flow:finish`."
- **Failures:** "Failing checks must be fixed before `/flow:finish`."

## Notes

- This command never commits, pushes, or modifies tracked files. It writes only
  the runner's resume file under `.claude/runs/` and the execution record under
  the git directory (`cpp-evidence/`), neither of which is part of the tree
- It runs the same checks as `/flow:finish` Step 2, extracted for standalone use
- Lint, test and typecheck are the three steps every shipped CI template runs
  (`templates/workflows/ci-*.yml`, `woodpecker-*.yml`), and the `finish`/`check`
  runner plans carry the same three (issue #617). Keep the sets aligned: a step
  CI runs but the check omits turns this report into a false green
- Use it to validate changes before committing or as a pre-flight check
- The security gate uses the same `.claude/security.yml` configuration as `/flow:finish`
