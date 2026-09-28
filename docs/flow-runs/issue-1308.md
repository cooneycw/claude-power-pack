# Flow run record - issue #1308

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1308
- Base SHA:          7d1ad79
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45 orchestrator (kyle fleet mailbox msg 1819, reply to ELI5 report msg 1818)
- Recorded at:       2026-09-28T11:41:22Z

## Section B evidence
- commits since 2026-09-28T11:34Z touching .woodpecker.yml or scripts/flow-ci-status.sh: none.
- PRs: none (search hit #1212 is merged and unrelated). dup/super: none.
- tests/test_cicd_pipeline.py:429 pins the GENERATOR's template for other repos, not
  CPP's own trigger; test_branch_protection.py pins only the required context.

## Section C - the approved plan
1. `.woodpecker.yml` - when: pull_request, plus push restricted to branch main; reword the :300 comment.
2. `tests/test_ci_trigger.py` - classifier over the top-level when:, tested in three directions on synthetic inputs and against 7d1ad79's real file (red), plus the real file clean; an unknown shape is a violation.

Scope: 2-3 files, ~120 lines. Risks: live acceptance (PR shows only a pull_request
pipeline; the first main push shows a push pipeline) is observable only on CI.
