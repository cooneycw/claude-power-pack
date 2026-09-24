# Flow run record - issue #1107

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1107
- Base SHA:          37bd61c30a671f01a9b0c565a777fd636fdb4cbf
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          the owner (cooneycw), in-session, choosing option 2 "build the launch-time refusal instead" over the gate's close recommendation
- Recorded at:       2026-09-24T17:39:31Z

## Section B evidence
Commits since 2026-09-19T20:19:45Z touching the mailbox/registry/register/wave
surfaces: 5ad99f5 (#1228), 84d75e0 (#1222), 2ca9017 (#972), 01ecfd3 (#1190),
13988c5 (#959); 3a70655 (#1095) is the issue's origin. Merged PRs: #1237, #1248,
#1247, #1214, #1130. Superseding/related issues: #1228 (closed), #871 (open),
#1095 (parent), #671 (closed). No duplicate; no `registry-required` in the tree.

The gate's verdict was "No longer needed" (owner-gone exit from #1237 covers the
field failure; supervise is a legacy path). The owner chose the reframed residual,
so the approved plan is the reframing below, not the issue body's daemon-side exit.

## Section C - the approved plan
1. `scripts/flow-wave-mailbox.sh` - `supervise --registry-required` REFUSES AT LAUNCH (non-zero exit, `emit misconfigured`) when `list --wave W --any-live` reads `no-roles-registered`, instead of a daemon-side exit nobody sees
2. `tests/test_flow_wave_mailbox.py` - the issue's three cases: flag + empty wave refused; no flag + same wave supervises (existing test stays green); flag + ended-but-registered wave still reads `no-roles-ended`
3. `.claude/commands/flow/register.md` - one line documenting the flag under the legacy `supervise` paragraph

Scope: 3 files, ~80 lines
Risks: grows a legacy path; refuses a legitimate supervise that launches before register (ordering race); no current consumer.
