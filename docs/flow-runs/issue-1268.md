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

## Harness/census half (w2)

- Approval:   granted for items 1-9 and the three re-dispositions, as one PR based on main after #1276 merges
- Approver:   run45:orch, mailbox message 2234 in reply to ELI5 message 2233

Base SHA: 5fd91de. Every item was reproduced on it by a cheap read before planning (the issue asks for this; some nits are two weeks old).

### ELI5
The negative-control harness and the census it counts against have a set of small blind spots:
- The table parser reads any numbered row anywhere in the ADR.
- Nothing notices two rows with the same number.
- There is no clean way to retire a row.
- Two rows describe their gates wrongly.
- Anchor diagnostics don't say which anchor or case they mean.
- An anchor's `kind` is half-read.
- The CI-dependency check misses the second battery-driving CI step.
- `gate-lib`'s control declares no mutations.

Each fix makes a reader say what it actually saw, and each gets a red case run on 5fd91de.

### Plan (my items)
1. Census rows are scoped to the census TABLE by its header, in ONE function in the shared module that both readers call (S3 row regex; latent: all 110 rows are in the table today).
2. A duplicate census row number is a census-check finding (S3 uniqueness; live gap, no instance today).
3. Anchor diagnostics name the anchor PATH and the CASE, not `sha` (`n/a` for constructed anchors).
4. `anchors[].kind` is validated: historical, constructed or synthetic. Historical requires sha and origin. The kind is reported.
5. `check-control-ci-deps.py` also enumerates the `mutation-probe` CI step as battery-driving.
6. `controls/gate-lib` gains mutations, each checked caught.
7. ADR row 101's consumer names `cpp-host-writes-check`. Row 103's REFUSED wording names every refusal cause the gate has.
8. The two Makefile reasons for excluding `eli5-check` and `tool-risk-check` from `make verify` are rewritten to be true, or the gates are wired in if nothing prevents it.
9. The blind-anchor adaptation in `controls/host-surface-observe` is pinned by a test that fails if a regeneration drops it.

### Proposed re-dispositions (evidence in the PR)
- Hardcoded ADR path: delivered by #1264. The harness resolves through `resolve_adr`, and `ADR_0008` is only the fallback when the rule module can't load. kyle resolves to exactly one file.
- `.gitignore` negation list: a fail-loud detector already covers it (the nit's own "not a live hole").
- Row-number collision magnet: superseded by item 2 plus #1276's subject keying.

### Rulings (message 2234)
- R1: a registered gate that is EXCLUDED and controlled is its own state, `EXCLUDED_CONTROLLED`, named and not failed, and the headline stops calling it "outside the census". Only a registration in NEITHER table fails, pinned with a case where the census gate is bypassed.
- R2: a `Retired` table. Its subjects may name absent files (not STALE); naming a LIVE file is a finding; retired rows sit outside the denominator. The existing gap comment, numbering gap and prose migrate into it in this PR.
- R3: re-disposition as a documented limitation. `expect:uncaught` with reasons is honest, not a false green. No `together` groups.
- R4: `limits` is canonical and `_comment` an accepted alias. UNKNOWN top-level control.json keys are REFUSED, after a scan of every control's top-level keys, listed in the PR. Enabling the refusal must not red a control that passes today.
- Item 8: wire `eli5-check` and `tool-risk-check` into verify only if they are shown to run offline; otherwise write the true reason.
- The out-of-half items are a SECOND PR after this one.
