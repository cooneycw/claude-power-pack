<!-- flow-run n=1 id=05ee0b65219044f488006adcc31db0ba -->
## Run 1 - issue #1350 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1350
- Read at:      2026-09-28T22:51:23Z
- updatedAt:    2026-09-28T22:50:58Z   (context only - moves on comments and labels)
- Body digest:  aa82181f2e879afac86cc28e36a6f7d1206097a98142541588507e12be02e721   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1194 of 1194 (cap 16384)

### Body as read
Promoted from Nit Store #864 (https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5879903280), found by cpp-wave2 w1 while working #1341.

**Outcome:** `controls/flow-finish-gate-resume`'s good case `good-fail-fix-resume` passes only when the gate reports the RESUME signal it exists to test: the carried/unverified warn for the resumed step. Today it passes on exit 3 from ANY warn.

**Why:** during #1341 this case's warn changed from `carried, unverified: security_scan` to `zero coverage: security_scan`, and the control stayed green. A regression in resume behaviour could therefore hide behind any unrelated warn, and the registered negative control would not notice. That is the blind-instrument shape.

**Constraint:** match on the harness's existing expectation mechanism, if `control.json` has one for signal text. Otherwise extend it in the smallest way that the other controls can reuse. Do not loosen any other case.

**Acceptance:**
- A committed input under which the case reports a DIFFERENT warn at exit 3 now fails the control. Show it red on the pre-fix control.
- The real case still passes.
- `check-negative-controls.py --strict` is green.

Refs #1341.

