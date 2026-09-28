# Flow run record - issue #1266

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1266 (PR A of two: registry script items 1, 2, 3, 4, 10)
- Base SHA:          ae6faa8504740fc930f0ad7fa915e1dbd1e5889e
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 2114 in reply to ELI5 message 2112
- Recorded at:       2026-09-28T15:40:00Z

## Section B evidence
- Re-checked on ae6faa8: items 1 (CUR read before with_lock, NEW_ENTRY after), 2 (line
  protocol), 3 (--pr empty refused :2408), 4 ($moved issue-only :2451), 5 (no amend verb),
  8/9 (docs silent), 10 (toolchain warning names no checkout :2726) are LIVE.
- 6/7 SUPERSEDED: the Codex-backed flow driver was retired in #1017 (PR #1038, 8324b0b).
- 11/12 DESIGN LIMITS (slate-lanes snapshot window; vantage --pid=host stated bound).

## Section C - the approved plan (PR A)
1. `scripts/flow-wave-registry.sh` - item 1: lane delta from the locked transaction's own before/after snapshot, with a documented test-only pause seam; item 2: refuse a newline in a lane path at input (message shows it escaped); item 3: --clear-pr; item 4: $moved also compares repo identity; item 10: the toolchain warning names the checkout
2. `tests/test_flow_wave_registry.py` - deterministic race regression (forced interleaving via the seam), and regressions for 2, 3, 4, 10, each red on the pre-fix code
3. `controls/flow-wave-registry/` - re-run --strict; extended only if item 1 changes what it exercises

Scope: 2-3 files, ~200 lines. Risk: the registry's concurrency path; the race test is forced, not timed.
PR B (items 5, 8, 9) and the re-disposition comments (6, 7, 11, 12) follow.

## PR B - the approved plan (items 5, 8, 9; appended; stacked on PR A until it merges)
Approver: run45:orch, message 2114 ("approve: PR A ... then PR B (5, 8, 9)") and 2129
("PR B can proceed locally").

4. `scripts/flow-wave-residuals.py` - an `amend` verb: correct a candidate's consequence, evidence or classification with a required reason, append-only history, refused once the wave is closed (close revalidates against the final tree) and on duplicate links
5. `tests/test_flow_wave_residuals.py` - amend regressions (red on the pre-fix code: unknown verb)
6. `.claude/commands/flow/register.md` - item 8: a granted path carries its generated mirrors (codex-skill-sync --list-mirrors); item 9: re-register after a Step-4 scope derivation
7. `.claude/commands/flow/wave.md` - the same two rules where the orchestrator grants lanes
8. `.claude/commands/flow/auto.md` - item 9 at Step 4
