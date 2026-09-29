# Flow run record - issue #1350

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=05ee0b65219044f488006adcc31db0ba -->
## Run 1

- Run-id:            05ee0b65219044f488006adcc31db0ba
- Run-start:         1c6a7aa05707848dfc686b7a551fe92acfd578e1
- Issue:             #1350
- Base SHA:          1c6a7aa05707848dfc686b7a551fe92acfd578e1
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run48:cpp2-orch (cpp-wave2 orchestrator), mailbox message 2551 replying to plan 2550
- Recorded at:       2026-09-28T22:53:44Z

### Section B evidence
`_observe` (scripts/check-negative-controls.py:1115) returns GOOD on exit == good_exit before reading output; CONTROL_KEYS (:1257) has no good-side signal. Commits since filing on the touched paths: none. Open PRs touching them: none. Related closed issues (not superseding): #946 (BAD-side signal), #1129, #1259, #1180.

### Section C - the approved plan
1. `scripts/check-negative-controls.py` - optional `good_signal`: exit == good_exit without a match is UNSIGNALLED, at all three _observe call sites; unset is unchanged.
2. `controls/flow-finish-gate-resume/control.json` - good_signal on the carried/unverified warn, plus limits prose.
3. `tests/test_negative_controls.py` - pure _observe cases, and the red case (resume good case without app.py: PASS pre-fix, UNSIGNALLED post-fix; PASS again with a match-any-warn regex).
4. `docs/decisions/0008-instrument-negative-control-bound.md` - dated note on row 63; row 1 unchanged.
5. `docs/scripts.md` - history line for check-negative-controls under #1350.
6. `controls/check-negative-controls/control.json` - AMENDMENT (orchestrator note 1, mailbox 2551): registers case bad-good-exit-wrong-warning and says why in limits.
7. `controls/check-negative-controls/cases/bad-good-exit-wrong-warning/scripts/toy-gate.sh` - AMENDMENT: toy gate whose clean answer is a warn, naming which.
8. `controls/check-negative-controls/cases/bad-good-exit-wrong-warning/controls/toy/control.json` - AMENDMENT: inner control with good_exit 3 and good_signal; its GOOD case warns for another reason.
9. `controls/check-negative-controls/cases/bad-good-exit-wrong-warning/controls/toy/anchors/0000000-toy-gate.sh` - AMENDMENT: blind inner anchor.
10. `controls/check-negative-controls/cases/bad-good-exit-wrong-warning/controls/toy/cases/bad/trip` - AMENDMENT: inner known-bad marker.
11. `controls/check-negative-controls/cases/bad-good-exit-wrong-warning/controls/toy/cases/good/README` - AMENDMENT: says what the inner GOOD case holds.
12. `controls/check-negative-controls/cases/bad-good-exit-wrong-warning/controls/toy/cases/good/otherwarn` - AMENDMENT: the different-warn marker.
Scope: 5 files, ~150 lines. Risks: harness is itself an instrument (run the check-negative-controls* controls and the full target); over-specific regex (anchor on the marker prefix); e2e test runs the real gate (needs make).

#### Section C amendment - 2026-09-28, per orchestrator note 1 (mailbox 2551)
The orchestrator asked whether the harness's own registered controls should gain a case for the new UNSIGNALLED-on-good branch. They can: items 6-12 add `bad-good-exit-wrong-warning` to `controls/check-negative-controls`. Measured: the current harness observes BAD on it; the 3a90f96 anchor reports PASS (misses it, blind as required); mutating `_observe` to ignore good_signal turns that control BLIND.
