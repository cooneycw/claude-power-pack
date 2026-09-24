# Flow run record - issue #921

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #921 (half 2 of 2; half 1 shipped as PR #991)
- Base SHA:          c5b1c5e
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          repository owner (cooneycw), in-session, 2026-09-24
- Recorded at:       2026-09-24

## Owner rulings this plan rests on
- Decision 3: the serving hosts do NOT pin their models (not resident between runs).
- Decision 4 follows: no timer / cadence re-probe. A probe is only permitted
  immediately before a delegated call that would load the model anyway, so it
  adds no load the call would not have performed.
- Decision 1: dissolved - #910 fixed by PR #998 (e032a25), exact-name presence check.
- Decision 2 (recent-failure refusal): not decided, not implemented here.

## Section B evidence
- 01b8e13 / PR #991 - half 1 (LANE_SERVE_AT, LANE_SERVE_VALID_FOR, --check-age).
- e032a25 / PR #998 - #910 closed COMPLETED.
- 360e340, 0c11b45, f174be0, 3f09f12 - touched the same files, unrelated.
- Duplicate/superseding issues: none.
- `--check-age` has zero callers in qwen/auto.md and gemma/auto.md at base.

## Section C - the approved plan
1. `.claude/commands/qwen/auto.md` - Step 4 records LANE_SERVE_AT/STATUS; Step 6 age-checks before each fix re-execute; stale/unknown -> one probe immediately before the call; dead/unreachable/unknown stop the fix loop; no timer or free-standing probe.
2. `.claude/commands/gemma/auto.md` - the same, for the gemma lane.
3. `tests/test_lane_serveability.py` - per-lane document tests for the seam; red on the pre-fix main.
4. `CHANGELOG.md` - one entry.
5. `codex/skills/**` - generated mirrors re-synced by the existing script.

Scope: small (two prompt documents, one test file, changelog, generated mirrors).
Risks: the recorded AT/STATUS is carried as literals across steps; if lost, the
age check reports unknown, which falls through to a fresh probe (safe direction).
