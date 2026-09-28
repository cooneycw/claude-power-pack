# Flow run record - issue #1268

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1268 (research pair only; w2 owns the harness/census half)
- Base SHA:          46b0e06
- Necessity verdict: Needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 2178 in reply to ELI5 message 2177
- Recorded at:       2026-09-28T17:40:00Z

## Research pair (w1, items: sweep RED bucket; forced-claim)

### Section B evidence
- Reproduced on 46b0e06: `sweep.py` exits 1 with `FAIL RED eli5-core-drift.sh NOT AUTOMATED (#591's claim)`; tests/test_codex_skill_sync.py invokes that script, so the control is stale, not the sweep.
- Reproduced on 46b0e06: `mutation-probe.py --strict --manifest docs/research/forced-claim-prototype-2026-09-15/control.json` exits 1; collected-nothing, claim-must-be-an-object and tests-added-must-be-a-count are UNCAUGHT (4/7).
- `--selftest` reports a missing pytest as "N/17 cases behaved as registered" with a hard-fail exit.

### Section C - the approved plan
1. `docs/research/class-enumeration-2026-09-15/sweep.py` - the RED bucket control becomes a constructed tree run through the real derive_universe()/closure(); the live GREEN stays; #591's claim retired in a comment naming what falsified it
2. `docs/research/forced-claim-prototype-2026-09-15/forced-claim-check.py` - --selftest resolves the runner once and reports UNAVAILABLE (exit 3) when none can run pytest, with a documented test-only seam
3. `docs/research/forced-claim-prototype-2026-09-15/control.json` - register the new cases
4. `docs/research/forced-claim-prototype-2026-09-15/cases/` - claim-not-an-object, tests-added-bool (and collected-nothing if it can discriminate)

Not wired into CI: the research doc declined promotion deliberately.
