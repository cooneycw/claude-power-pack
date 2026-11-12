# Flow run record - issue #1732

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=a71218fb4c8a43dbac263079e3b347b5 -->
## Run 1

- Run-id:            a71218fb4c8a43dbac263079e3b347b5
- Run-start:         c5ac2e52d604adf3d42c3f58335210016f226c48
- Issue:             #1732
- Base SHA:          c5ac2e52
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1732", outbox rev 41, 2026-11-11T22:18:15-05:00
- Recorded at:       2026-11-12T03:20:00Z

### Section B evidence
- a88aafdd (#1719) fixed the KeyError; nothing wires the flag (git grep verify-provenance in Makefile and .woodpecker.yml is empty at c5ac2e52)
- Measured at c5ac2e52: the flag finishes over the real tree, exit 0: 42 controls ok, 78 unverified, 0 MISMATCH; 2m19s on a loaded box
- 45 historical anchors (all with a sha), 67 constructed (14 with no sha key), 10 synthetic, 1 vendored
- CI clones at depth 1, where a historical anchor's commit is absent and reads unverified, the word a constructed anchor gets by design

### Rulings and gate conditions (orchestrator)
- P1: under --verify-provenance --strict an uncomparable historical anchor fails, named with its reason.
- P2: CI runs it on pull_request events only, reusing the deepened clone; not on main pushes; the PR says so. make verify: measure with and without the flag on a quiet box; 60 seconds or less added and it goes in the negative-controls target, more and it gets its own target and the number goes to the orchestrator first.
- P3: a constructed anchor needs no placeholder sha; record that on #1732.
- P4: no coordination issue; the two new strings are stated in the docs page.
- Condition 1: the control's blind anchor is the harness without the flag; verified with --control by name; registrations before the first gate run.
- Condition 2: the real-tree test requires zero uncomparable historical anchors and a compared count at least the number of historical anchors registered, derived.
- Condition 3: read this PR's Woodpecker log and report the compared count; stop if it is not the full count.
- Condition 4: verify-coverage-check output diffed before and after the Makefile edit.
- Condition 5: an uncomparable historical anchor seen only in CI goes to the orchestrator, not to an exemption.
- Condition 6: make lint, make typecheck, make shellcheck read to the end; two review passes.

## Section C - the approved plan
  1. `scripts/check-negative-controls.py` - under --verify-provenance a historical anchor that could not be compared is named with its reason, counted, and fails under --strict; one closing count line
  2. `Makefile` - the negative-controls target passes --verify-provenance, or a separate target if the measured cost exceeds 60 seconds
  3. `.woodpecker.yml` - a pull_request-only step deepens the clone and runs the flag
  4. `controls/check-negative-controls-provenance/control.json` - new control with its runner, cases and blind anchor
  5. `controls/census.md` - the checker's row gains the provenance run
  6. `tests/test_negative_controls_provenance_run.py` - new: the cases, the count line, the real-tree run
  7. `docs/scripts/check-negative-controls.md` - what the flag establishes, its cost, the two new strings, the schema decision
Scope: 7 named files plus the control's runner and case fixtures and any registration file the control checks require.
Risks: the checker is the origin of several controls' anchors; the Makefile annotation is parsed; the unshallow fetch can fail on a network blip.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | The fixture repository is built as a full clone and as a depth-1 clone; the real-tree test runs in a linked worktree and in CI's deepened clone |
| Harness | not applicable | The checker is not bundled into any skill and no install path runs it |
| Driver | not applicable | No driver-facing output |
| Coordination | not applicable | No coordination path |
| CI provider | will test (Woodpecker); not covered (GitHub Actions) | This PR's own pipeline log is read for the compared count; no GitHub Actions run exists here |
| Project state | will test | A tree with no historical anchors: says so and passes |
