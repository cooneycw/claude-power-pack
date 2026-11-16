# Flow run record - issue #1849

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=8dbd4634fefd417c9a8d8f6be523ab4e -->
## Run 1

- Run-id:            8dbd4634fefd417c9a8d8f6be523ab4e
- Run-start:         716b7c3f556fa98db30101c0cf96c1209b9480c4
- Issue:             #1849
- Base SHA:          716b7c3f556fa98db30101c0cf96c1209b9480c4
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), in-session: "1. yes. 2. approved" (yes = proceed despite the #1850 ordering)
- Recorded at:       2026-11-15T23:29:24Z

### Section B evidence
- commits since filing: 716b7c3f (#1848), 62e928b9 (#1847), 06392d40 (#1846); none adds plan-record wrappers
- merged PRs: #1855, #1854, #1852, #1845, #1843, #1841, #1840; none delivers this
- duplicate/superseding: none; #1811 related (delegated drivers keep old verbs)
- sibling worktree: claude-power-pack-issue-1821-... unpushed commits on scripts/flow-plan-record.py; #1821 closed, its lanes-at-close code on main
- ordering: #1848 satisfied (716b7c3f); #1850 open, owner ruled proceed anyway

### Section C - the approved plan
1. `scripts/flow-plan-record.py` - add `start`, `approve --plan FILE` (validate fully in memory, then begin-run + append + stamp) and `finish` (drift, compliance, head-check, each line visible, worst-of exit); export the composite-verb table; plain `approve` unchanged
2. `scripts/check-driver-parity.py` - expand composite verbs into their constituents, reading the table from flow-plan-record.py
3. `docs/agents/driver-parity.json` - re-pin the flow/auto.md line citations the edit shifts
4. `.claude/commands/flow/auto.md` - Steps 1, 4 and 6 use start / approve --plan / finish; old assembly prose removed
5. `.claude/command-word-budgets.tsv` - lower the flow/auto.md row to the new measured count
6. `tests/test_flow_plan_record_wrappers.py` - red and green cases at the new entry points
7. `tests/test_driver_parity.py` - composite expansion plus a negative control (flow surface without finish fails)
8. `docs/agents/flow-plan-record.md` - document the three verbs and their mapping
9. `docs/scripts/flow-plan-record.md` - #1849 history line

Scope: 9 files, ~350 lines (about half tests).
Risks: widening the parity gate could blind it (item 7 negative control); line-pinned citations (#1851); finish's single exit code is lossy, the per-verdict lines are authoritative; #1850 ordering ruled by the owner.

### Lanes for this change

| Lane | Answer |
|---|---|
| Driver | will test - `/flow:auto` against the delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`) via tests/test_driver_parity.py; live delegated run not covered |
| Checkout | will test - main checkout via the tests' temporary repository; linked worktree via this run's Step 6 `finish` from the branch |
| Harness | will test - Claude install via the test suite; Codex install via `make codex-skills` building the mirror from the changed flow/auto.md; no live Codex run |
| Coordination | not applicable - no coordination path touched |
| CI provider | not applicable - no CI provider path touched |
| Project state | will test - a repository that has adopted a feature's file (lane file present, prior run in the record) and one that has not |
| Toolchain version | not applicable - stdlib only, no toolchain path touched |
| Clone shape | not applicable - no history reads changed |
| Run location | will test - invoked from the CPP root; from another directory not covered (wrappers reuse toplevel()) |
| Gate target | not applicable - no runner change |
| Wave role state | not applicable - no wave path touched |

Reader: the `/flow:auto` session reads the FLOW_PLAN_START / FLOW_PLAN_FINISH lines; tests run the real script.
Reader: scripts/check-driver-parity.py reads flow/auto.md; tests/test_driver_parity.py runs against the real file.
