# Flow run record - issue #1206

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system and it does not graduate.

- Issue:             #1206
- Base SHA:          0643349
- Necessity verdict: Still needed
- Approval:          granted - GO-WITH-CONDITIONS, ruling (a)
- Approver:          CPP-improvements-orch (wave claude-improvements, policy
                     rev 4, authority-model orchestrator-only)
- Recorded at:       2026-09-22T15:05:00Z

## Section B evidence

- THE CAUSE IS CONFIG LOCATION, not matcher shape, and it was isolated by a
  discriminator rather than argued: `.claude/hooks.json` carries a SessionStart
  hook whose output is distinctive ("claude-power-pack is current"). That string
  appears NOWHERE in this session's SessionStart output. What DID appear -
  "CPP install: 2 Codex skill(s) stale" - is printed verbatim by
  ~/.claude/scripts/hook-pending-retro.sh, the USER-LEVEL hook. So the repo's
  SessionStart did not fire either: THE WHOLE FILE IS INERT, not just the mask.
- Config landscape, measured: `.claude/settings.json` ABSENT;
  `.claude/settings.local.json` exists with no hooks key; `.claude/hooks.json`
  exists with SessionStart + PostToolUse and is read by no Claude Code path;
  `~/.claude/settings.json` has PermissionRequest + SessionStart, and those fire.
- MATCHER SHAPE IS NOT ISOLABLE while the file is unread - a shape change inside
  an unread file produces no observable difference in either direction - but it
  becomes live the moment the location is fixed. Hence both, in order.
- THE MASKER ITSELF has a second defect: it interpolates stdin as '''$INPUT'''
  into a Python heredoc. Measured: baseline masks correctly; `$VAR` masks
  correctly; `'''` produces exit 1 with EMPTY STDOUT and a SyntaxError on
  stderr. Per the script's own header, empty stdout means "no change" - so the
  unmasked value passes through. A parse failure is indistinguishable from
  "nothing needed masking".

## Section C - the approved plan

Scoped to THIS REPOSITORY, by the orchestrator's ruling (a).

1. `.claude/settings.json` - register the two hooks at the documented project
   location, in the documented shape (string matcher). Location first, then
   shape; neither alone.
2. `scripts/hook-mask-output.sh` - stop interpolating stdin into Python source.
   A parse failure must not be able to read as "nothing to mask".
3. `controls/hook-mask-output` - the committed pair: a synthetic secret through
   a REAL tool call observed MASKED, and the same with the hook disabled
   observed UNMASKED, with the existing positive control committed alongside.
   CAPABILITY and WIRING are two different facts and only the first was
   provable before this change.
4. `tests/test_hook_mask_output.py`, `README.md` corrected to say what is true.

### What this deliberately does NOT do

IT DOES NOT FIX ANY PROJECT CPP HAS ALREADY INITIALISED. Measured: CPP COPIES
`.claude/hooks.json` into every project it scaffolds - `cpp/init.md:660` and
`project/init.md:378`, the latter with `2>/dev/null || true`, a silent failure
path on top of an ineffective copy - and `cpp/init.md:342-344` ANNOUNCES
"PostToolUse: mask secrets in output" at install time while doing it. So CPP
does not merely copy a dead file; it promises the protection while copying it.

Those three sites are command documents in another role's lane, and the
orchestrator is holding them for an owner decision. NOT TOUCHED AT ALL, not even
to add a comment: a partial edit there is how the next reader concludes it was
handled.

Also belonging to that assignment and not this one: if the hooks move to
`.claude/settings.json`, `update.md:383-401`'s migration keeps rewriting the
DEAD file and never touches the live one - the same defect with the filenames
swapped.

### Named risks

1. This repository will be fixed while every consumer stays broken. That is the
   accepted cost of ruling (a), and the PR body must say so plainly - "this does
   not fix any project CPP has initialised" - not as follow-up work.
2. A control that proves WIRING must actually exercise the harness, not the
   script. A control that only pipes JSON into the masker re-proves capability,
   which was never in doubt, and would be an anti-control for the wiring claim.
3. `~/.claude/settings.json` is the user's host config, it is where the WORKING
   hooks live, and nothing here may write it. A repo fix that rewrote it would
   be the #1198 defect committed deliberately.
