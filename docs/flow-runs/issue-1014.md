# Flow run record - issue #1014

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1014
- Base SHA:          40f771c
- Necessity verdict: Partially addressed
- Approval:          granted (Part 1 of two PRs; Part 2, the registry, waits for #1266 PR A)
- Approver:          run45 orchestrator (fleet mailbox message 2120, replying to the ELI5 report in 2119)
- Recorded at:       2026-09-28T15:40:00Z

## Section B evidence

- Delivered: the exit-code tier - scripts/gate-lib.sh (#1126/c15bbff, #1061/e9a58b6)
  gate_map enforces exactly one verdict on exit 0 and cites #1014/#800.
- Not delivered: docs/agents/detector-contracts.md mentions "unknown" 0 times; the rule
  is restated in flow-wave-registry.sh, flow-wave-mailbox.sh, gate-lib.sh,
  check-consolidation-ledger.py and flow-plan-record.py.
- flow-worktree-guard.sh:71/:112 merges clean, not-applicable and could-not-look into one
  silent exit 0, with no FLOW_* marker. flow-wave-registry.sh:957 `stale other-host`
  (Part 2).

## Section C - the approved plan

1. `docs/agents/detector-contracts.md` - a "The third state: unknown" section: one name with a reason, the two tiers (gate_map exits; STATE BASIS / unknown values), consumer-owned policy with the mailbox example, not-applicable versus unknown, and an instance index including gh-pr-merge's base_contained_now skipped fail-open as a documented policy.
2. `scripts/flow-worktree-guard.sh` - a FLOW_WORKTREE_GUARD marker, and under --strict gate_map exits (good 0, leak 3, unknown 4, not-applicable 5).
3. `.claude/commands/flow/auto.md` - Steps 4 and 6 read the marker; 3 stops, 4 and 5 proceed and report.
4. `.claude/commands/flow/start.md` - the same handling.
5. `tests/test_flow_worktree_guard_verdicts.py` - red cases on 40f771c for not-applicable, unknown, leak and no-leak.
6. `controls/flow-worktree-guard` - the ADR 0008 negative control with a forced-unknown input.
7. `docs/scripts.md` - flow-worktree-guard history line.
8. `docs/flow-runs/issue-1014.md` - this plan record.
9. `docs/flow-runs/issue-1014.as-read.md` - the as-read issue snapshot.

Scope: Part 1 only; generated codex mirrors follow.

Risks: RB changes the guard's exit contract - every caller audited and listed in the PR.

Rulings (message 2120): RA yes (Part 2); RB yes with a caller audit - every caller treats
4 and 5 as proceed-and-report and 3 as stop; two PRs.
