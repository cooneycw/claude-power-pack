# Flow run record - issue #1265

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1265
- Base SHA:          b935d64a3c6726d02856a72d2f3fd3977616a6dc
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 2066 in reply to ELI5 message 2065
- Recorded at:       2026-09-28T14:40:00Z

## Section B evidence
- Re-checked on b935d64: items 1 (depth 6 at :334/:401), 2 (EVENTS = parsed only),
  3 (usage sed 2,90p vs Signals :113 / Exit codes :141), 5 (no directive), 6 (auto.md:516
  'treating it as a failure' vs 5 siblings 'making it fatal'), 7 (comment ':232 exits 0';
  pre-fix measured exit 1 via git show c7297c2~1) all reproduce.
- Item 4: a REAL capture (codex-cli 0.158.0, multi_agent enabled) emits item.type
  'collab_tool_call' (tool 'wait'); 'collab_agent_tool_call' was not observed.
- Commits since 2026-09-26 touching these lines: none. Dup/super: none.

## Section C - the approved plan
1. `scripts/delegated-run-check.sh` - iterative uncapped walks; additive DELEGATED_RUN_UNPARSED; usage prints the whole header; corrected comment; collab_tool_call (as captured); NEGATIVE-CONTROL directive
2. `controls/delegated-run-check/` - control with BAD depth-8 and depth-50 errored calls, GOOD sibling, historical anchor (pre-fix script)
3. `docs/decisions/0008-instrument-negative-control-bound.md` - row 13 only
4. `.claude/commands/codex/auto.md` - 'making it fatal', matching the five siblings (+ mirrors)
5. `tests/test_delegated_run_check.py` - regressions for depth, unparsed count, help, first-error-text order, collab type
6. `tests/fixtures/delegated_runs/codex-collab-capture.jsonl` - the real capture

Scope: ~7 files + mirrors, ~250 lines. Risk: walk order (first error text wins) - pinned on both versions.
Control uid-independent; harness untouched.
