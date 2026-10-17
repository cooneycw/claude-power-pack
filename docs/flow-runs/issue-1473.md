# Flow run record - issue #1473

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=a6e05342fed143889cfe7f7a86eb927e -->
## Run 1

- Run-id:            a6e05342fed143889cfe7f7a86eb927e
- Run-start:         020349564f87d1bd2b86800f9c8e2814fd239b79
- Issue:             #1473
- Base SHA:          020349564f87d1bd2b86800f9c8e2814fd239b79
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the session's user (cooneycw), replying "approved" to the Step 3 report
- Recorded at:       2026-10-17T00:00:00Z

### Section B evidence
- Skip reproduced on 02034956: SKIPPED tests/test_flow_plan_compliance.py:800 "this environment can write a read-only index".
- Commits on origin/main since filing (2026-10-17T11:54:29Z): none (repo-wide and on the two relevant paths).
- Merged PRs inspected: #1463-#1471, all at or before the base; none touch this test.
- Duplicate/superseding issues: none (search hit only #1473 and Nit Store #864).
- Probe: with .git/index.lock present, rev-parse and ls-files --others exit 0; git add -N exits 128.

### Section C - the approved plan
1. `tests/test_flow_plan_compliance.py` - replace the chmod-and-skip fixture in test_a_failed_intent_to_add_is_unknown_not_agreement with a fixture-owned .git/index.lock, asserted precondition (lock exists, direct add -N fails), finally-cleanup, branch-pinning asserts (intent-to-add message, not enumerate message, no agreement), and a corrected docstring.

Scope: small, one test function, no production change.
Risks: the helper later taking the index lock before enumeration would reach a different unknown branch; the not-enumerate assertion makes that red rather than green.
