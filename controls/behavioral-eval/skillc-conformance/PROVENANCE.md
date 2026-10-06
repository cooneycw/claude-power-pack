# Provenance

Every `*.json` file under this directory is copied verbatim, byte-for-byte,
from skillc's own committed golden fixtures at commit
`220260356fcaf96b6e5b7355fb3536a84faf8c76` (skillc PR #320, closing #272) -
cited elsewhere in this repository as `2202603`.

Source paths, one family per subdirectory here:

- `ledger-binding/{good,bad}/*` <- skillc `controls/ledger-binding/{good,bad}/*`
- `unique-ids/{good,bad}/*` <- skillc `controls/unique-ids/{good,bad}/*`
- `attempt-accounting/{good,bad}/*` <- skillc `controls/attempt-accounting/{good,bad}/*`
- `lineage/{good,bad}/*` <- skillc `controls/lineage/{good,bad}/*`

## Why this directory exists (issue #1369, gap raised by cpp-orch 2026-10-06)

`scripts/check-behavioral-eval.py` restates a MINIMAL subset of these four
skillc bundle rules by hand rather than importing skillc's own `records.py`/
`checks.py` (owner ruling: #1369's own completion evidence requires "NO
skillc runtime import ... in CPP CI"). Restating by hand is exactly the kind
of drift this repository's own instrument discipline (ADR 0008) warns about:
a hand-restatement can silently stop agreeing with the thing it restates.

CPP-built fixtures (`controls/behavioral-eval/cases/*`) prove CPP's reader
works. They CANNOT prove it still agrees with skillc, because CPP wrote
them to match CPP's own understanding of the rule - the exact failure mode
a restatement is vulnerable to. Only skillc's OWN fixtures, read by CPP's
reader, can show that.

`tests/test_behavioral_eval_skillc_conformance.py` runs
`scripts/check-behavioral-eval.py`'s `_bundle_records` and `_validate_bundle`
over every directory here and asserts the result against a HAND-MAINTAINED
classification: each case is either IN the minimal restated subset (CPP's
reader must agree with skillc's good/bad label) or explicitly OUT of it
(named, with the specific skillc behaviour CPP does not restate - never
silently skipped). Building this classification against these fixtures is
what found two real bugs before they shipped: `_validate_bundle` did not
include `skill-evidence` in its one-record-per-attempt uniqueness check
(skillc `unique-ids/bad/skill-evidence-duplicate`), and it had no exemption
for `reconciliation: unmatched, reason: no-correlating-attempt`, which
skillc's own `good/skill-evidence-no-correlating-attempt` fixture exists to
prove is NOT an altered artifact. Both are fixed in the same change that adds
this directory.

**Re-pin this directory when skillc's bundle rules change.** If a case here
disagrees with its expected classification after a skillc update, that is
the drift this guard exists to surface - re-derive the classification against
the new skillc commit, and update this file's pinned SHA, rather than editing
the test to make it pass.
