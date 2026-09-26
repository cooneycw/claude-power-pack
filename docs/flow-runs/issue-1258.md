# Flow run record - issue #1258

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1258
- Base SHA:          8dad5063993826cc742a273fd69532ef4b61f725
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          repository owner (cooneycw), interactive "approved" in the /flow:auto session
- Recorded at:       2026-09-26T16:00:00Z

## Section B evidence
Commits c5b1c5e (#1229), 5699ee5 (#1246), cbe7b1d (#1181, with #1061's gate_exit
migration - delivers item 5 via test_every_verdict_call_is_terminal). PRs #1181,
#1229, #1246, #1159, #1161, #1164, #1167, #1175 (none touch the other defects).
Related closed: #742, #793 (not duplicates). No open duplicate. Items 1+2, 3, 4, 6,
7+8, 9 and 10 reproduce by reading current main; items 7+8 are mis-cited (the
executed path is lib/cicd/steps.py, models.py feeds the detector).

## Section C - the approved plan
1. `scripts/flow-start-resolve.sh` - probe PR before pickup worktree add (MERGED -> skip as shipped, fall to fresh with a free issue-anchored name and SHIPPED_BRANCH; OPEN -> create nothing, CONFIRM_REQUIRED=1, --allow-pickup); unwritable parent -> ignored .claude/worktrees or refuse before -b, delete a branch a failed add created; compose top-level name: before basename
2. `scripts/check-ignored-additions.sh` - exit 3 by default in a linked worktree, advisory in the primary checkout, --advisory forces 0, message states the cost
3. `scripts/flow-finish-gate.sh` - remove RUNNER_JSON in the EXIT trap; relay FAILED_IDS above a fail verdict or say none could be read
4. `lib/cicd/runner.py` - record failed_ids for any failed step whose output parses as pytest with failures
5. `lib/cicd/steps.py` - typecheck fallback runs bare mypy when a mypy config declares files, else mypy .
6. `lib/cicd/models.py` - same scope rule for the detector's generated runner commands
7. `tests/test_flow_start_resolve.py` - red cases: merged-PR branch, open-PR branch, unwritable parent, compose name
8. `tests/test_check_ignored_additions.py` - worktree exits 3, primary exits 0, --advisory exits 0
9. `tests/test_flow_finish_gate.py` - single-marker assertion in _run, no leftover temp file, FAILED_IDS relayed
10. `tests/test_runner.py` - failed_ids on a non-test aggregate step; mypy scope both directions
11. `.claude/commands/flow/auto.md` - ignored-additions guard blocks in a worktree; --allow-pickup and SHIPPED_BRANCH
12. `.claude/commands/flow/finish.md` - same guard wording
13. `docs/scripts.md` - per-script behaviour entries

Scope: ~11 source/doc files plus regenerated codex/skills mirrors, ~400-500 lines.
Risks: item 2 blocks every run if the gate writes an ignored non-scratch file into
the worktree (checked empirically before relying on it); the shipped-branch fresh
fallback creates a second issue-N branch; kyle container copies change only after
install.
