A bundle (`bundle-1/`) whose ledger plans ZERO attempts - attempt-accounting
(skillc records.md:900): "the ledger plans no attempts, so there is nothing
to account for." This is CPP's OWN analogue of #1367's "empty denominator"
control, in #1369's own terms - skillc's `controls/skill-evidence/bad/
empty-skills.json` tests a DIFFERENT, RECORD-level rule (a `skill-evidence`
record's own `skills` list must be non-empty), which #1369 does not restate
at all (it is outside the four BUNDLE rules this gate restates a subset of).
Closes the gap raised by cpp-orch 2026-10-06: registers "empty denominator"
as a committed ADR 0008 case, not only a `tests/test_behavioral_eval.py`
unit test (`test_an_empty_ledger_has_nothing_to_account_for`).
