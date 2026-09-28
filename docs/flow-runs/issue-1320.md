# Flow run record - issue #1320

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1320
- Base SHA:          b71e813
- Necessity verdict: Still needed (reframed from #1267 item 5: a gate bypass)
- Approval:          granted
- Approver:          run45 orchestrator (kyle fleet mailbox msgs 2051, 2194 and 2204, on ELI5 draft msg 2047)
- Recorded at:       2026-09-28T16:34:42Z

## Section B evidence
- flow-plan-record.py reconcile restores the committed record for any run; step3-record-guard.sh
  allows an edit on any `Approval: granted`; approve and head-check key on the issue only.
- w1's measurement (#1320 comment 5874224712): compliance merges every plan section in a shared
  record into one planned set, and a second plan trips the first run's stability check.
- PRs: none. dup/super: #1267 item 5 (moved here).

## Section C - the approved plan
1. `scripts/flow-plan-record.py` - run identity minted by reconcile (per-worktree git dir); append-only `## Run <n>` records; approve, compliance, stability, drift and head-check read ONLY the current run's section; legacy record parses as Run 1.
2. `scripts/step3-record-guard.sh` - allow only when the newest section is approved AND carries this run's id; refusal names both run ids.
3. `controls/step3-record-guard/control.json` - new good case (current run approved) and red case (a prior run's approval refuses), red shown on the pre-fix base.
4. `.claude/commands/flow/auto.md` - Step 4 appends a `## Run <n>` section with Run-id, for the record and the as-read snapshot.
5. `codex/skills/flow-auto/reference.md` - regenerated mirror.
6. `docs/agents/flow-plan-record.md` - the run-identity model.
7. `tests/test_flow_plan_record_runs.py` - two runs with different Section C lists; legacy pinned with a real record from main (docs/flow-runs/issue-1289.md).

Scope: ~8 files, ~400 lines. Risks: the guard is a PreToolUse hook, so a bug blocks every
edit in every flow worktree; the transition for in-flight runs (ruling requested, msg 2203).
