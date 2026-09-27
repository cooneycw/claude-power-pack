# Issue #1294 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1294
- Read at:      2026-09-27T17:11:35Z
- updatedAt:    2026-09-27T14:37:05Z   (context only - moves on comments and labels)
- Body digest:  dbccbbd22cb72262f1b32fb03ef86244c95180094da758d67b7810d5478bc561   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2439 of 2439 (cap 16384)

## Body as read
## What happens

`lib/cicd/steps.py` `ShellStep.is_test_step()` searches the step's **command text** with `_TEST_STEP_HINT` (`(?:^|[^a-z])(?:tests?|pytest|jest|vitest|unittest|nose)(?:[^a-z]|$)`). The command for a gate step embeds the CPP checkout's **absolute path**, so any checkout whose path contains a `test` token classifies a non-test step as a test step. The step then needs a parseable test summary, finds none, and is reported `NO TEST OUTCOME PARSED (UNKNOWN, not clean; OUTPUT UNCLASSIFIABLE)`; the finish gate returns `warn` (exit 3) instead of `ok`.

## Measured (found during #1271)

Same SHA, same case (`controls/flow-finish-gate-derivation/cases/good-make-absent`), only the checkout path differs:

| CPP checkout path | typecheck step | gate |
|---|---|---|
| `.../claude-power-pack-issue-1271-test-isolation-leaked-...` | `[PYTEST_WORKERS=unset]` ... `SUCCESS - NO TEST OUTCOME PARSED` | `FLOW_FINISH_GATE: warn` (exit 3) |
| `<scratch>/cpp-copy` (detached worktree at the same HEAD) | `SUCCESS` | `FLOW_FINISH_GATE: ok` |

## Why it matters (why this is an issue, not a nit)

- It **blocks** `make verify` / `flow-finish-gate.sh` for any flow run whose issue slug contains "test" - `issue-N-test-...`, `...-tests-...`, `...-flaky-test-...`: `test_negative_controls.py::test_an_untracked_control_file_refuses_the_green` asserts a clean `--strict` battery as its precondition and goes red, with the `flow-finish-gate-derivation` control reporting `UNSIGNALLED`.
- The verdict depends on a directory name nobody chose for this reason, and CI (a path without the token) can never see it - a green CI coexisting with a deterministic local red.
- Worse in the other direction: a step whose command merely lives under a `tests/` path is promoted to a test step, so its absence-of-summary is judged by rules meant for runners.

## Suggested fix

Classify on the step **id** and the command's **program and arguments**, not on path components: strip absolute paths (or match only whitespace-delimited tokens that are not paths) before applying `_TEST_STEP_HINT`. Red case: a command containing `/x/repo-test-foo/...` for a `typecheck` step must NOT be a test step; `uv run pytest` and a step id `test` must remain test steps.

Found while working #1271 (branch `issue-1271-test-isolation-leaked-supervise-daemons-tests-coup`); that run's local gate was completed from a path-neutral checkout of the same SHA because of this.

