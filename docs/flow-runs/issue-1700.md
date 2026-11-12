# Flow run record - issue #1700

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=7c7a28fa2c2144e2a12de508f652e2cb -->
## Run 1

- Run-id:            7c7a28fa2c2144e2a12de508f652e2cb
- Run-start:         4f585adf5619414b800489e08b133e56d0c2b4d8
- Issue:             #1700
- Base SHA:          4f585adf5619414b800489e08b133e56d0c2b4d8
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          the owner chose option A, the split, on 2026-11-12 ("A"), relayed by the wave orchestrator (wave cpp-improvement) in mailbox rev 67 to role cpp-1508 at 2026-11-12T01:46:43-05:00: "RATIFY: option A for #1700, by the owner"
- Recorded at:       2026-11-12T07:05:00Z

### Section B evidence
- A first attempt at this issue is preserved unpushed as branch `issue-1700-a-review-that-ran-more-than-3-passes-has-no-truthf` at 54367bc8. It took four counter-model passes: eight findings (seven in the gate half, one in the writer half) plus one from the orchestrator's own read (writer half). Two gate-half findings from pass 4 were never fixed.
- By the owner's ruling the gate half is deferred to #1765 and this run lands the half that reviewed clean, as a new and smaller diff whose review starts at pass 1.
- Measured at 4f585adf with main's gate script and scratch repositories: a five-pass receipt WITH a ruling prints `receipt:` and passes; a five-pass receipt with NO ruling also prints `receipt:` and passes; the validator on this branch accepts the first and refuses the second. The gate does not read the count.
- This record was written after the files were carried over from the held branch, not before the first edit; the carry-over was mechanical (a three-way apply of the held branch's diff for six files, then removal of the gate-side `judge` verb).

### Section C - the approved plan
Conditions attached to the approval: a fresh branch from main, the held branch left as it is; only the writer, validator, documents, the Step 6 wording and their tests; no change to `scripts/flow-finish-gate.sh`, proved by an empty diff against main; the outer bound is one named constant set to 10 with its reason beside it (a receipt already committed in kyle records 9 passes); the Step 6 wording costs zero net words in `auto.md`; "recorded, not authenticated" in those words in both documents; the PR tells the whole history and closes #1700, and says on #1710 which pass-cap rows it closes; two review passes, a third on the orchestrator's word.

1. `scripts/counter-model-receipt.py` - `--passes` above 3 only with `--escalated-by`, `--escalation-ref`, `--raised-cap` and `--extra-pass-reason`; the validator accepts exactly that shape; a blank ruler or reference is refused; a skipped receipt cannot carry an escalation; the outer bound.
2. `tests/test_counter_model_review.py` - the writer's and validator's red cases.
3. `.claude/commands/flow/auto.md` - the Step 6 wording: ask the approver before each further pass.
4. `docs/reference/flow-auto-rationale.md` - the refusal rule and who the approver is.
5. `docs/agents/counter-model-evidence.md` - escalated reviews, the bound, recorded not authenticated, and what the gate does today.
6. `docs/scripts/counter-model-receipt.md` - one line for the script's page.

Scope: about 130 lines of code, 170 of tests, three documents.

Risks: a document left describing the gate half that did not land; the Step 6 wording losing an instruction; a consumer's older validator rejecting an escalated receipt (stated in the evidence document).

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test: pytest on the writer and validator in this linked worktree |
| Harness | will test: command-doc word budget, Codex mirrors and tests/test_codex_skill_sync.py, an independent read of the Step 6 wording; a live Codex run is not covered |
| Driver | not applicable: the wording is read by every driver, and no driver-specific code changes |
| Coordination | not applicable: no wave, mailbox or registry code |
| CI provider | will test: the corpus check and the gate's enrolment mode on this repository's own receipts, unchanged gate script |
| Project state | will test: main's gate measured against an escalated receipt in scratch repositories; kyle, skillc and kyle-candidate receipts re-validated before and after |
