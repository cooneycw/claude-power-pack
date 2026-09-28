# Flow run record - issue #1313

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1313
- Base SHA:          e04cd02a677fa403576786c811511ef41a150551
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 1930 in reply to ELI5 message 1927
- Recorded at:       2026-09-28T13:30:00Z

## Section B evidence
- Filed 2026-09-28 from a reproduction: delayed stub tee leaks 2/2, control 3/3 clean.
  No commits since touching the runner-JSON path. Prototype (reverted) of the fd-9 fix:
  delayed-tee clean 2/2, existing interrupted-gate test passes.

## Section C - the approved plan
1. `scripts/flow-finish-gate.sh` - open the runner JSON once on fd 9 after mktemp; both pipelines `| tee /dev/fd/9`; close fd 9 before the straight-line rm; trap unchanged
2. `tests/test_flow_finish_gate.py` - the delayed-tee regression (waits by process exit), red on the pre-fix gate; a normal-run content check (runner JSON unchanged pre vs post); existing interrupted-gate test unchanged
3. `codex/skills/` - re-synced mirrors of the bundled gate

Scope: 2 files + mirrors, ~40 lines. Risk: /dev/fd/N availability (Linux, macOS both have it);
path-reads of $RUNNER_JSON unchanged. Touched controls run with --strict.
