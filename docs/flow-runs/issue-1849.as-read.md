<!-- flow-run n=1 id=8dbd4634fefd417c9a8d8f6be523ab4e -->
## Run 1 - issue #1849 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1849
- Read at:      2026-11-15T23:25:41Z
- updatedAt:    2026-11-15T20:11:05Z   (context only - moves on comments and labels)
- Body digest:  5bb2c6d67dffefe012db8e882e73215842b28014904e931866ab529794ea243d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2669 of 2669 (cap 16384)

### Body as read
Tier: 2

## Outcome

A `/flow:auto` run talks to its plan record three times: when it starts, when the plan is approved, and when it finishes. Today it makes eight separate calls plus a hand-written append, and `flow/auto.md` names `flow-plan-record.py` nine times.

Today's sequence: `reconcile`, `read-issue` (Step 1); `begin-run`, a `cat >>` heredoc the session writes by hand, `approve` (Step 4); `drift`, `compliance`, `head-check` (Step 6); plus `declare-salvage` when it applies. Each has its own exit-code paragraph. The hand-written append is the only step with a format rule nothing checks at write time (one backticked path per Section C line), and a wrong format reads as UNKNOWN only at Step 6.

Source: observed while running `/flow:auto` on #1846 (2026-11-15), measured on main `f1253b45`. Part of the simplification asked for in [discussion #1830](https://github.com/cooneycw/claude-power-pack/discussions/1830). Related: #1669 (word budgets).

## Constraints

- **The record's content and file layout do not change**: append-only, one section per run, the as-read snapshot, the approval baseline. Rationale: #1080, #1081, #1082, #1320, and existing records must stay readable.
- **The existing verbs keep working**, because the delegated drivers call five of them (#1809) and #1811 tracks the rest.
- **The record is still written only after approval is granted.** A combined verb must not make it possible to stamp an approval before the plan exists (#775).
- **Each finish-time result stays separately visible**: drift, compliance and head-check answer different questions and must not collapse into one pass/fail.

## Acceptance

- [ ] `start <issue>` does what reconcile plus read-issue do.
- [ ] `approve <issue> --plan <file>` begins the run, appends the plan from the file, validates the Section C line format at once, and stamps the baseline.
- [ ] `finish <issue>` prints the three existing verdict lines.
- [ ] `flow/auto.md` uses the three, and its budget is lowered by what that removes.
- [ ] A malformed Section C line fails at `approve`, shown red on a known-bad plan file at the new entry point, not only in tests of the underlying functions.
- [ ] A wrapper never reports success over a failed or unavailable inner result.
- [ ] The old assembly instructions leave `flow/auto.md` in the same change the wrappers land.

Ordering: after #1850's Tier 1 decision and after #1848.

## Proposed approach

Thin wrappers over the existing functions in `scripts/flow-plan-record.py`; no change to the functions themselves.

## Assumptions

- Validating Section C at approve time does not reject formats existing records rely on. Not checked.



<!-- end of body -->
