# Flow run record - issue #1220

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1220
- Base SHA:          c5b1c5edb180db748738878e577809b47d112611
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the session user (cooneycw), replying "approved" to the Step 3 report
- Recorded at:       2026-09-24T09:11:51Z

## Section B evidence
Commits touching .claude/commands/flow/auto.md or tests/test_flow_plan_compliance.py
since 2026-09-23T16:34:45Z: none. Merged PRs inspected: #1230, #1229, #1225, #1224,
#1223, #1219, #1218, #1217, #1216, #1215, #1214, #1213, #1212, #1210, #1209, #1199 -
none alter the Step 6 item 7 block. Duplicate/superseding issues: none (#864 is the
provenance nit store).

## Section C - the approved plan
1. `.claude/commands/flow/auto.md` - Step 6 item 7: enumerate untracked files into a mktemp file (exit status checked; mktemp failure folds into the existing enumerate-unknown), mapfile -d '' from the file, remove it; comment why a variable cannot carry NULs.
2. `tests/test_flow_plan_compliance.py` - regression case with TWO untracked files, one containing a space; asserts divergence and BOTH names; run red on the pre-fix block.
3. `codex/skills/flow-auto/reference.md` - regenerated via scripts/codex-skill-sync.py --write, not hand-edited.
Scope: ~10 lines in the block, ~30 lines of test, regenerated mirror.
Risks: block extraction / unknown-pin meta-test must keep matching; temp file cleanup on every path; space-named file rendering in --name-only output.
