<!-- flow-run n=1 id=53f932869aa1490f8ea6227204543f86 -->
## Run 1 - issue #1684 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1684
- Read at:      2026-11-11T20:40:06Z
- updatedAt:    2026-11-11T20:39:12Z   (context only - moves on comments and labels)
- Body digest:  2cae1e0f904a21430a477f2b2be4e3e70d8ecfc7cdc836a5f6be8066a7a974ff   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1494 of 1494 (cap 16384)

### Body as read
Filed on the owner's instruction (2026-11-11, "file it") from a draft by worker kyle-2202 in kyle wave `kyle-cli`; the worker's own filing was refused by its session's permission check.

**Severity: medium.** Observed once, 2026-11-11, kyle PR #2320.

## What happened
- Command: `flow-ci-status.sh <merge-sha> --path <checkout> --event push --fallback-provider-probes --wait 3000`
- It returned at once: `FLOW_CI_EXIT=0`, `FLOW_CI_PIPELINE: 4726`, `FLOW_CI_URL: -`, `FLOW_CI_WAIT: none`, `FLOW_CI_STATUS: unknown`.
- A minute later, without `--wait`: `FLOW_CI_STATUS: running`, URL filled in.
- The same flags earlier that day (kyle PR #2293) gave `FLOW_CI_WAIT: settled` and a terminal status.
- Cause not established. Guess: the read landed before Woodpecker gave the new pipeline a status.

## Why it matters
A lock-hold script that reads exit 0 as "the wait ended" released kyle's merge lock while main's push pipeline was still running. Nothing merged behind it only because two other guards wait on the commit status directly.

## Acceptance (draft)
- With `--wait`, a pipeline that is found but has no readable status is polled until terminal or the deadline.
- Never `unknown` with exit 0 before the deadline. Deadline expiry is non-zero and says so.
- A committed case: a pipeline number with an empty status keeps polling; a blind copy that returns immediately fails the case.
- The `--fallback-provider-probes` path is covered.

Related: #1653 (recorded CI provider lanes), #1677.


<!-- end of body -->
