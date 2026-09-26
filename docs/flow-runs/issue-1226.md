# Flow run record - issue #1226

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1226
- Base SHA:          5b6c4c64b923769d99c241cc600b0a467f8386f4
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          repository owner (cooneycw), in the invoking session
- Recorded at:       2026-09-26T12:13:30Z

## Section B evidence

- Commits touching `tests/test_codex_skill_resync.py` since filing
  (2026-09-23T17:12Z): none (22 commits on main inspected).
- Commits touching the call sites since filing: 39c8475 (#1252), 2ca9017
  (#1247), c1a60bf (#1231) - line shifts only; all three sites
  (`auto.md:821`, `auto.md:1406`, `finish.md:93`) still use the exact spelling.
- Merged PRs inspected: #1218 and #1225 (the origin, pre-filing); #1212,
  #1230, #1238, #1240, #1243, #1250 (search hits, unrelated). None of the 33
  PRs merged since 2026-09-23 addresses the equality match.
- Duplicate/superseding issues: none (#864 matched on text only).

## Section C - the approved plan

1. `tests/test_codex_skill_resync.py` - add `_is_resync_invocation(line)`
   (strip trailing comment, split on `&&`/`||`/`;`/`|`, accept a command whose
   head is the script, optionally after `bash`/`sh` and `if`/`elif`/`then`/`!`);
   inside the fence walk report a non-comment MENTION that is neither an
   invocation nor an existence test as unexamined (the third state, approved);
   route the fence walk, the reconcile pass and the `:274` count test through
   it; add red-first tests for acceptance 1-3 plus the unknown-mention state
   and a real-site count check.
2. `docs/flow-runs/issue-1226.md` - this plan record.
3. `docs/measurements/counter-model/` - the counter-model review receipt.

Scope: one real file, about 80-120 added lines, all tests. No command document
is touched; the `[ -x ]` existence guards are retained.

Risks: an over-broad recogniser counts the `[ -x ... ]` guard as an invocation
(doubling the count test, falsely gating a correct call) - acceptance-3 tests
guard it and are shown red against an over-broad variant; the third state may
red the tripwire on a harmless future mention, which is the intended direction.
