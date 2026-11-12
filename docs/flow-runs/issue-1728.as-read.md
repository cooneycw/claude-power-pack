<!-- flow-run n=1 id=6bd34a446935429eae493ef142432b74 -->
## Run 1 - issue #1728 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1728
- Read at:      2026-11-12T04:22:53Z
- updatedAt:    2026-11-12T00:34:52Z   (context only - moves on comments and labels)
- Body digest:  e433f9a11333dc3cd7eee18608d71c07c8a047915cda6ebd52375ce4ae1dc033   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2361 of 2361 (cap 16384)

### Body as read
Source: found by a survey agent during #1692 and reproduced on 2026-11-11 at `545267b9` at the wave orchestrator's request. Filed by the session working #1692.

## Problem

`scripts/flow-finish-gate.sh`, `parse_fallback_failed_ids` (the Makefile fallback lane, used when the Python runner cannot start) takes a failed test's id as awk's `$2`, the second whitespace-separated field of a `FAILED ...` line. A parametrised id can contain a space (`test_v[hello world]`), so the id is cut at the space, and two different parametrised failures that share a prefix collapse onto one truncated id.

The Python parser fixed exactly this (`lib/cicd/outcomes.py`, `_PYTEST_FAILED_NODE_ID`: the id runs to the ` - <reason>` separator). The shell copy was not updated.

## Reproduction

Input (three failures):

```
FAILED tests/test_x.py::test_v[hello world] - AssertionError: boom
FAILED tests/test_x.py::test_v[hello there] - AssertionError: boom
FAILED tests/test_x.py::test_plain - assert 1 == 2
```

| Parser | Output |
|---|---|
| shell `parse_fallback_failed_ids` | `tests/test_x.py::test_v[hello tests/test_x.py::test_plain` (2 ids, one truncated) |
| Python `parse_failed_node_ids` | all 3 ids, intact |

## What it affects

- **The cap.** The fallback re-runs failures only when the count of parsed ids is at most `MAX_RERUN_IDS` (25). Merged ids undercount, so a run with more than 25 distinct failures can still be admitted to the re-run.
- **The report.** `RERUN_PASSED:` and the "RE-RUNNING failed id(s)" line name truncated ids that do not exist.
- **Not the selection.** The re-run itself uses pytest's `--last-failed` cache, not these ids, so which tests are re-run is unaffected.

**Severity: low** (my estimate): the verdict path is touched only through the cap, in the fallback lane, for ids containing spaces.

## Acceptance

- The fallback parser returns the same ids as `parse_failed_node_ids` for the input above. Committed red case: that input, failing on the current script.
- A parity test over a shared fixture so the two parsers cannot drift again (this is one of five things the fallback lane duplicates from the Python side; see the fallback-lane proposal on #1692, comment 6810744415).

Under the #1673 freeze this is a defect fix in `scripts/flow-*`, not a feature. It does not change a verdict line or exit code. Refs #1692, #769, #1673.

<!-- end of body -->
