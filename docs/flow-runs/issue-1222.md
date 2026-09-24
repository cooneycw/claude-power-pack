# Flow run record - issue #1222

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1222
- Base SHA:          5699ee5
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner (cooneycw), in the invoking session ("Approved")
- Recorded at:       2026-09-24T12:10:00Z

## Section B evidence
- Commits since filing (2026-09-23T16:44Z) on scripts/flow-wave-registry.sh and
  tests/test_flow_wave_registry.py: 5ad99f5 (#1237, watch/wake) only - not the
  release/register lane code.
- Merged PRs since filing inspected: #1246 #1244 #1243 #1240 #1237 #1234 #1231
  #1230 #1229 #1225 #1224 #1223 #1219 #1218 #1217 #1216 #1215 #1214 #1213 #1212
  #1210 #1209 #1199 - none clears lane facts on release/register.
- Duplicate search: none. Open PR #1247 (#972) touches adjacent lines (textual only).
- Acceptance item 4 already holds (starvation_scan is live-only); pinned by a test.
- The `abandoned` suggestion is already served by `stale` (pid-gone); not in scope.

## Section C - the approved plan
1. `scripts/flow-wave-registry.sh` - release moves issue/pr/branch/base/diff/obs_repo/files/overtaken into `released_lane` and blanks the live keys; register resets pr/base/diff/obs_repo/overtaken (unless observed) and files (unless --files) when the previous row names a different non-empty issue; header text.
2. `tests/test_flow_wave_registry.py` - release-clears (red on base), re-register-onto-B (red on base), same-issue re-brief control, released-role-not-starving, stale docstring fix.
3. `.claude/commands/flow/register.md` - one sentence in the Release section.
4. `codex/skills/flow-wave/scripts/flow-wave-registry.sh` - regenerated mirror of item 1.

Scope: small-medium, ~40 script lines, ~90 test lines, ~3 doc lines.
Risks: a re-brief omitting --issue is deliberately not an issue change (nit store); textual rebase against #1247.
