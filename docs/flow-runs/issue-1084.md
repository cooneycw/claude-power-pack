# Flow run record - issue #1084

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1084
- Base SHA:          5bed7408efbb213a98bc5662e525d0a934d6053d
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          repository owner (cooneycw), interactive "approved" in the /flow:auto session
- Recorded at:       2026-09-26T00:00:00Z

## Section B evidence
CPP commits on the gate paths since 2026-09-19: dfe98f9 (#1194, half A against
records v1), 2ca9017 (#1247, shellcheck only). skillc: PR #17 (records v1), PR #32
(records v2, refuses v1; Closes skillc#4), PR #33 (Level 1 slug goal + grader,
assembles v2 verified-results; Closes skillc#5), PR #35 (skillc#6). skillc #7, #8,
#9, #10 OPEN. No duplicate or superseding CPP issue. Half B stays in skillc per
owner ruling; this run is Refs #1084, not Closes.

## Section C - the approved plan
1. `scripts/check-behavioral-eval.py` - move the consumer to records v2 (refuse v1 and boolean versions; producer authority; graded_digests; evidence/missing; run_state reason), keep re-derivation, state "checked alone - NOT against any ledger", correct the ABSENT blocker note
2. `controls/behavioral-eval/control.json` - register the v2 case set
3. `controls/behavioral-eval/cases/` - convert existing cases to v2 and add v1-refused, wrong-producer, satisfied-without-evidence, no-graded-digests, boolean-version and a skillc-assembled good case where obtainable without a model
4. `tests/test_behavioral_eval.py` - tests for each new refusal, including the v1 record refused
5. `Makefile` - replace `|| true` with declared-exit-codes-pass, crash-fails; still advisory
6. `.woodpecker.yml` - same crash-vs-verdict change in the CI step

Scope: ~6 source files plus ~15 fixtures, ~250 lines.
Risks: v2 rules are restated by hand in CPP and can drift from skillc (pin the
skillc commit); the CI change turns a gate crash red where it was green.
