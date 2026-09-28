# Issue #1308 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1308
- Read at:      2026-09-28T11:40:12Z
- updatedAt:    2026-09-28T11:34:39Z   (context only - moves on comments and labels)
- Body digest:  40362ea7f7459e7d7f28c70b3a0d9fbdf1397ca265c449cc87a0cd7a8d2a453d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2007 of 2007 (cap 16384)

## Body as read
## Problem

`.woodpecker.yml:33-34` triggers the whole pipeline on `event: [push, pull_request]` with no branch filter, so every push to a PR branch runs **twice**: a push pipeline and a pull_request pipeline on the same commit. Measured 2026-09-28 by master:kyle on the public Woodpecker API: CPP pipelines in pairs 2800+2801, 2802+2803, 2804+2805, 2806+2807; 25 CPP pipelines in 3h with up to 4 running at once, on a Woodpecker shared by two groups (8 sessions). The operator: "CI is running hot."

Only `ci/woodpecker/pr/woodpecker` is a required status context (`gh api repos/cooneycw/claude-power-pack/branches/main/protection/required_status_checks` -> contexts `["ci/woodpecker/pr/woodpecker"]`, strict). So the branch push lane gates nothing.

## Proposed change

```yaml
when:
  - event: pull_request
  - event: push
    branch: main
```

Pushes to `main` keep their pipeline (post-merge verification). Branch pushes run only the pull_request pipeline.

## Dependencies checked (orchestrator, run45, on 84f414e..bdbe0fb)

- No step carries its own `when:`; the top-level trigger is the only one.
- `scripts/flow-ci-status.sh` defaults `PREFER_EVENT="push"` (:72) but falls back to any other event on the same SHA (:284-288), so a branch SHA with only a pull_request pipeline is still found. #1262 separately derives the event from required contexts.
- Not checked yet: tests that pin the trigger (candidates: `tests/test_cicd_pipeline.py`, `tests/test_branch_protection.py`, `tests/test_verify_wiring.py`), and the comment at `.woodpecker.yml:~300` that describes the trigger.

## Acceptance

- Config change as above, with any test that pins the trigger updated.
- A committed check that fails if `push` runs on non-main branches again, AND that fails if `push` on `main` is dropped (both directions, each shown red).
- The PR's own pipelines show a single pull_request pipeline for its branch pushes; the first push to main after merge shows a push pipeline (checked and recorded on this issue).
