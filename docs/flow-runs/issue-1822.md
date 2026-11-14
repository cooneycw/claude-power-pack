# Flow run record - issue #1822

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=65a8a34dbc4446b7a3badbd42e7396b6 -->
## Run 1

- Run-id:            65a8a34dbc4446b7a3badbd42e7396b6
- Run-start:         d90712eed2523fc2128674a54ffa7923f8bf2c54
- Issue:             #1822
- Base SHA:          d90712ee
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), in-session reply "approved"
- Recorded at:       2026-11-14T17:10:00Z

### Section B evidence
No commits to templates/delegated-driver-core.md, scripts/flow-plan-record.py or .claude/commands since the issue was created (2026-11-14T16:29Z); base d90712ee. Merged PR #1704 introduced lanes (not a duplicate). No duplicate or superseding issues (search returned only #1822).

### Section C - the approved plan
1. `scripts/flow-plan-record.py` - add lane_answer(cell) matching a LANE_ANSWERS phrase only at a word boundary; use it in answered() and will_test_lanes(); refusal text says "is one of"
2. `templates/delegated-driver-core.md` - offer exactly will test / will refuse / not applicable / not covered; a lane needing a decision goes to the owner before approval, never into the table
3. `.claude/commands/codex/auto.md` - re-rendered via make delegated-core-write
4. `.claude/commands/qwen/auto.md` - re-rendered
5. `.claude/commands/gemma/auto.md` - re-rendered
6. `tests/test_lanes_contract.py` - import LANE_ANSWERS from the helper; contract test comparing answers offered by rendered drivers, template and /flow:eli5 to LANE_ANSWERS; red cases (offers needs a decision, drops will refuse)
7. `tests/test_flow_plan_record_lanes.py` - red cases not applicablewhatever / will testing; accept cases will test - via X, not applicable: reason, backticked will refuse
8. `controls/flow-plan-record-lanes/cases/bad-answer-runs-past-the-phrase/lanes.md` - committed BAD case lane file
9. `controls/flow-plan-record-lanes/cases/bad-answer-runs-past-the-phrase/section.md` - committed BAD case section
10. `controls/flow-plan-record-lanes/control.json` - register the new case

Scope: small (~10 files, 3 generated renders).
Risks: an already-approved record whose answer ran straight into letters reads unanswered / not-will-test at close (intended; compliance is advisory); the contract test parses prose sentences, so rewording breaks it (deliberate).

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | not applicable | string matching only |
| Harness | not covered | codex mirrors rebuilt by make codex-skills in the gate; no live Codex run |
| Driver | will test | contract test checks all three rendered delegated drivers plus the template |
| Coordination | not applicable | no Kyle path touched |
| CI provider | not applicable | no CI helper touched |
| Project state | will test | the no-lane-file GOOD control case still runs |
| Toolchain version | not applicable | pure Python re |
| Clone shape | not applicable | no history access |
| Run location | not applicable | no cwd logic |
| Gate target | not applicable | no runner changes |
| Wave role state | not applicable | no wave code |

Reader: the helper's refusal message (agents running approve; control detect_signal prefix "unanswered" unchanged) and the driver command text (delegated planners).
