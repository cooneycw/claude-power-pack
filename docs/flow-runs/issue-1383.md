# Flow run record - issue #1383

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=78cb9a2b9eb54d1ab4513a1e4d1a67c7 -->
## Run 1

- Run-id:            78cb9a2b9eb54d1ab4513a1e4d1a67c7
- Run-start:         cbdf826f239655e5e282749cf47b1e3ad54d8221
- Issue:             #1383
- Base SHA:          cbdf826f
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner (cooneycw), interactive reply "approved" in this session
- Recorded at:       2026-10-06T11:04:33Z

### Section B evidence
none touching scripts/counter-model-receipt.py, scripts/flow-finish-gate.sh or
templates/delegated-driver-core.md since filing (2026-10-06T11:01:27Z). Merged
since filing: #1375, #1376, #1377, #1378, #1381, #1382 - none touches receipts.
Duplicates/superseding: none (#1045 closed, #1084/#1366 unrelated).

### Section C - the approved plan
1. `scripts/counter-model-receipt.py` - delegated direction: --implementer-exec-log (codex stream -> rollout -> codex/<model>) and --reviewer-session-id (Claude transcript -> claude/<model>); direction/implementer_evidence/reviewer_evidence recorded and validated; mixed-direction flags refused; same-model refusal unchanged
2. `tests/test_counter_model_review.py` - delegated write, same-model negative control, mixed flags, missing reviewer session, thread-less stream refused, back-compat
3. `templates/delegated-driver-core.md` - Step 5 records the delegated receipt and stages it (rendered into .claude/commands/{codex,qwen,gemma}/auto.md)
4. `controls/counter-model-enrolment/cases/good-delegated-receipt-at-head/setup.sh` - gate accepts a delegated receipt
5. `docs/decisions/0007-counter-model-review.md` - the property holds in either direction

Scope: ~5 source files, ~250-350 lines. Risks: Qwen/Gemma streams carry no
derivable model, so the writer refuses for those lanes (fail closed, deferred);
delegated lanes' Step 6 does not itself run flow-finish-gate.sh.
