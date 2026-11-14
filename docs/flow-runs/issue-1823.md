# Flow run record - issue #1823

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=5a0c6451735d4d52bdf8a2014b16e670 -->
## Run 1

- Run-id:            5a0c6451735d4d52bdf8a2014b16e670
- Run-start:         d90712eed2523fc2128674a54ffa7923f8bf2c54
- Issue:             #1823
- Base SHA:          d90712ee (to be advanced by merging origin/main once #1821 and #1822 land, before the first implementation edit)
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (the user of this interactive session, "approved", 2026-11-14), refusal-at-approval option
- Recorded at:       2026-11-14T17:20:00Z

### Section B evidence
Commits on main since filing (2026-11-14T16:29:41Z): none (main at d90712ee). Merged PRs since filing: none.
Issues inspected: #1821 (open, rewrites lanes_at_close; its bound_rows still counts any non-empty cell), #1822 (open, phrase-boundary answer matcher), #1695, #1731, #1767, #1809 (closed, built the lane feature), #1725 (Nit Store). No duplicate or superseding issue.
Host scan: no unpushed sibling commits touching scripts/flow-plan-record.py or docs/agents/lanes.md.

### Section C - the approved plan
1. `scripts/flow-plan-record.py` - result rows `| Lane | Result | Evidence |` with states passed / failed / not run / refused as expected (phrase-boundary match); only passed / refused as expected with non-empty evidence count; owed = will test + will refuse lanes (stamp v2 records the answer per lane, v1 read as all will test); verdict line shape unchanged, per-lane reason on stderr; approval refuses a will test row naming none of the lane's listed values
2. `tests/test_flow_plan_record_lanes.py` - red and good cases for TODO state, passed without reference, will refuse without evidence, failed / not run reported, will test with no values refused
3. `controls/flow-plan-record-lanes-verdict/control.json` - register the new verdict cases
4. `controls/flow-plan-record-lanes/control.json` - register the new approval case
5. `controls/delegated-codex-plan-lanes/cases/close-every-lane-demonstrated/demonstrated.md` - three-column rows
6. `controls/delegated-qwen-plan-lanes/cases/close-every-lane-demonstrated/demonstrated.md` - three-column rows
7. `controls/delegated-gemma-plan-lanes/cases/close-every-lane-demonstrated/demonstrated.md` - three-column rows
8. `tests/fixtures/lanes/plan-complete.md` - will test rows name values
9. `tests/test_lanes_contract.py` - fixtures adjusted where needed
10. `tests/test_flow_auto_plan_gate.py` - fixtures adjusted where needed
11. `tests/test_delegated_plan_lanes.py` - fixtures adjusted where needed
12. `docs/agents/lanes.md` - result table format, states, evidence, values on will test rows
13. `docs/agents/flow-plan-record.md` - what counts at close
14. `docs/scripts/flow-plan-record.md` - behaviour entry
15. `templates/delegated-driver-core.md` - result row format line
16. `.claude/commands/codex/auto.md` - re-vendored driver core
17. `.claude/commands/qwen/auto.md` - re-vendored driver core
18. `.claude/commands/gemma/auto.md` - re-vendored driver core
19. `.claude/commands/flow/eli5.md` - a will test row names the values it covers
20. `CHANGELOG.md` - Unreleased entry

New control case directories under `controls/flow-plan-record-lanes-verdict/cases/` (bad-result-state-todo, bad-passed-no-reference, bad-will-refuse-no-evidence) and `controls/flow-plan-record-lanes/cases/` (bad-will-test-names-no-values), and the good-case files those controls already hold, are part of items 3 and 4.

Scope: about 20 files, roughly 450-600 lines, mostly tests and control cases.
Risks: value matching is wording-sensitive (mitigated by normalizing backticks, parentheses and case, and listing the values in the refusal); refusal at approval may slow plans (owner chose refusal); must be built on #1821 and #1822 after they merge.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test - linked worktree (test temp repos and controls); main checkout not tested, the check reads files at toplevel() |
| Harness | will test - Claude install; Codex install not covered (mirrors built by make codex-skills, no live Codex run) |
| Driver | will test - `/flow:auto` via helper tests and delegated drivers via recorded delegated-plan-lanes controls; live delegated run not covered |
| Coordination | not applicable - no coordination path touched |
| CI provider | not applicable - no CI provider path touched |
| Project state | will test - a repository that has adopted a feature's file and one that has not (silence preserved) |
| Toolchain version | not applicable - no toolchain path touched |
| Clone shape | not applicable - no history reads changed |
| Run location | not applicable - toplevel() resolution unchanged |
| Gate target | not applicable - no runner change |
| Wave role state | not applicable - no wave path touched |

Reader: PLAN_COMPLIANCE verdict line - /flow:auto Step 6, delegated drivers, Kyle sessions after re-pin; shape unchanged. Reader: approve refusal - plan authors in every driver; new reason; Kyle note on kyle#2348. Reader: demonstrated file - only this helper.
