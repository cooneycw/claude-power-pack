<!-- flow-run n=1 id=2f628282cfa2408e85f767255833e380 -->
## Run 1 - issue #1508 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1508
- Read at:      2026-11-11T21:52:18Z
- updatedAt:    2026-10-26T00:10:29Z   (context only - moves on comments and labels)
- Body digest:  9a2a0a4ea72a00f86bade022e28bb47c5366425880ea05d0fe5ae71eef40b1b5   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2966 of 2966 (cap 16384)

### Body as read
**Type:** scope:task
**Source:** split from #1486 item 6 (flow-ci-status.sh image-pull misclassification), per orchestrator condition: "If you find no real sample within ~30 min, do not map it. File item 6 as its own issue."

## Why

#1486 (absorbed Nit Store comment 6036855188) describes `scripts/flow-ci-status.sh`'s `failure_origin()` classifying a step that fails at Docker image pull as a code failure, since only `clone`-type steps and `exit 75` on a `*-stage` step count as precode. The fix needs a REAL measured sample of what Woodpecker actually reports for a failed image pull (type/exit_code/error), not a guessed shape - mapping a guessed shape to `precode` risks EXCUSING a real code failure (fail-open), which is worse than today's noisy-but-safe over-blaming as "code".

## What I searched (2026-10-20)

Queried the live Woodpecker API directly (`$WOODPECKER_SERVER/api/repos/<id>/pipelines/<n>`, `.workflows[].children[]`) for every `failure`/`error`-status pipeline in the three repos with real CI history:

- **cooneycw/claude-power-pack** (repo 1): 67 failure pipelines scanned, every failed step read.
- **cooneycw/kyle** (repo 17): 33 failure pipelines scanned.
- **cooneycw/skillc** (repo 20): 21 failure pipelines scanned.

~121 failed-pipeline records, every failed step's `name|state|exit_code|error` read. Distinct shapes found:

| exit_code | error | Count | What it is |
|---|---|---|---|
| 1 | null | ~46 | ordinary code/test failure |
| 126 | `Canceled` | ~19 | supersession/cancellation (useful evidence for #1486 items 3/5 instead) |
| 2, 128 | null | 2 | ordinary code failure, different exit code |
| 100 | null | 1 | app-specific exit code (qa-regression-demo) |
| 126 | `Get "http://%2Fvar%2Frun%2Fdocker.sock/...": context deadline exceeded` | 3 | Woodpecker agent -> Docker daemon socket timeout (kyle) |

**No genuine image-pull failure** (no "pull access denied", "manifest unknown", "no such image", registry auth error, or similar) appears anywhere in this sample. The Docker-socket-timeout shape found in kyle's history is a different infrastructure failure (the agent losing contact with its own daemon, not a registry/pull problem) and should not be conflated with it.

## Disposition

Not actioned in #1486. `failure_origin()`'s current behaviour (classify as `code`) is unchanged - noisy (over-blames the change on an image-pull failure) but safe (never excuses a real code failure). Mapping a guessed shape to `precode` without a real sample risks the opposite, fail-open direction, which is strictly worse.

## Acceptance

- A real pipeline run that fails at image pull is captured (type/exit_code/error, repo, pipeline number) - either found by continued search, or the next time one happens live.
- `failure_origin()` maps that measured shape to `precode`, with a committed `controls/flow-ci-status` case built from the real sample.
- Until then, this issue stays open as the pointer; #1486 does not block on it.


<!-- end of body -->
