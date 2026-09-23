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

---

# Run 2 - issue #1206 Decision 1 (pure removal)

A SECOND run on the same issue, at a different base and a different scope. The
record above is run 1 and is left exactly as it was approved; it does not
graduate and it is not amended here.

- Issue:             #1206, Decision 1
- Base SHA:          86e1c8d
- Necessity verdict: Still needed
- Approval:          granted - GO, scope PURE REMOVAL
- Approver:          CPP-improvements-orch, relaying an OWNER ruling
- Owner authority:   the owner authorised the orchestrator to make these
                     decisions (2026-09-23, direct to this session). The
                     CLAUDE.md line was additionally confirmed by the owner
                     themselves before that grant existed.
- Recorded at:       2026-09-23T00:00:00Z

## The owner's two decisions

DECISION 1 APPROVED - stop asserting a protection that does not exist.
DECISION 2 DECLINED - the hook will NOT be registered.

A third option was put to the owner after they pushed back on merely
documenting a known gap: split the masker and register a high-confidence tier
only (0 false positives on 7 benign samples, 4 of 4 real secrets caught). They
considered it and chose pure removal anyway. **This is a decided scope, not a
capability limit.** No tier, no TODO inviting one, no registration.

## How the claim surfaces were enumerated

The subject is a CLAIM, so enumerating COPY SITES would be the issue's own
defect committed a second time - patching the two files #1206 names leaves the
assertion standing everywhere else. Method, stated so it can be checked:

1. Population from `git ls-files`, never a directory walk, so untracked scratch
   cannot inflate it and an ignored file cannot hide in it.
2. Three independent anchors, unioned rather than intersected, because each one
   alone misses surfaces the others catch: `PostToolUse` (32 files),
   `hook-mask-output` (33), `hooks.json` (28). A file asserting the protection
   in prose without naming the script is caught by the first; a tier check
   keyed on the file's existence is caught only by the third.
3. `mask` alone was measured and REJECTED as the anchor: 145 tracked files,
   almost all of them `lib/creds/` credential masking and `/secrets:*`, a real
   and unrelated subsystem. A population that large would have been read by
   sampling, which is how a surface gets missed.
4. Every hit in the union was then READ IN CONTEXT and classified, because the
   line is not the decision. Three classes: ASSERTS the protection is active
   (in scope), DESCRIBES the script's capability (out of scope - the tool
   survives), or RECORDS history (out of scope - flow-runs, research
   transcripts, CHANGELOG, ADRs, controls and their anchors).

## Section C - the approved plan

Remove the assertion everywhere it is SHIPPED, leave the tool alone.

1. `CLAUDE.md:134` - owner-approved exact edit, nothing replacing the clause.
2. `.claude/commands/cpp/init.md` - the Tier 2 offer text that names masking as
   a reason to install hooks, and the tier display listing the PostToolUse mask.
3. `.claude/commands/cpp/update.md` - Step 4.7's "the PostToolUse secret-masking
   hook is retained", and the stale-PreToolUse block's "the masking hook is
   kept" / "masking untouched".
4. `.claude/commands/flow/doctor.md` - the PostToolUse row in the hook list and
   the mask-output rows in the doctor table.
5. `.claude/commands/cpp/status.md` - the hook-count line that reports masking
   as configured.
6. `.claude/commands/project/init.md` - the copy that ships the declaration into
   every initialised project.
7. `README.md` - the secret-masking bullet and the hooks.json line in the tree.
8. `docs/scripts.md` - the `hook-mask-output` entry, reworded from "PostToolUse
   hook that masks secrets in tool output" to what it now is.

### What survives, deliberately

`scripts/hook-mask-output.sh` STAYS. It works, its four silent-failure paths and
its NUL reconstruction were fixed, and it has a committed control. It remains
usable by `/security:*` against files at rest, where a false positive costs a
glance rather than corrupting a live channel. **Removing the CLAIM is not
removing the TOOL**, and the PR says so explicitly so the next reader does not
delete a working script on the strength of this change.

### Named risks

1. The claim is re-added by someone reading an old doc. Mitigated by the claim
   control below, which fails if the assertion returns.
2. A reader takes this as a verdict that the masker does not work. Mitigated by
   stating the opposite in the PR body and in `docs/scripts.md`.

## Negative control - a CLAIM control, not a behaviour control

The subject is a claim, so the control is the #1083 shape: a test that FAILS if
the assertion returns. `tests/test_hook_mask_output.py` gains a test pinning
that no SHIPPED surface asserts active masking, and it is shown RED against the
current text before the change - which is the whole point, since a claim control
written after the removal would pass on an empty population and prove nothing.

## Section D - HELD FOR THE ORCHESTRATOR: the `.claude/hooks.json` disposition

Not decided here. The orchestrator asked for the disposition rather than the
decision, and the premise it was framed on needs one correction first.

**"Nothing reads it" is true of Claude Code and false of CPP.** Claude Code does
not load `.claude/hooks.json` - that is the #1206 defect. But six CPP surfaces
read it, and one of them is not cosmetic:

| site | what it does with the file |
|---|---|
| `cpp/update.md:1864` | `[ -f ".claude/hooks.json" ] && [ "$SCRIPTS_COUNT" -ge 3 ] && TIER=2` |
| `cpp/init.md:133` | `HOOKS_EXIST=true` |
| `cpp/status.md:63-67` | reports "Hooks configured: N hooks" |
| `flow/doctor.md:101-103` | reports its presence and greps it for event names |
| `cpp/init.md:374` | `rm .claude/hooks.json` on uninstall |
| `project/init.md:377` | copies it into each initialised project |

The tier test reads the USER'S project file, not CPP's, so deleting CPP's own
copy does not break an existing install. But pure removal also stops `/cpp:init`
copying it, and then **a newly initialised project can never reach Tier 2** -
its tier-2 predicate can no longer become true. That is a real behavioural
consequence of the delete, and it is not in the issue.

So the disposition question has a second half: if the file goes, does Tier 2
become "scripts only" (`SCRIPTS_COUNT >= 3`), or does the tier ladder lose a
rung? Orchestrator's call. The `.gitignore:57` negation going dead is the
smaller half and follows whichever way that goes.

## Section D - RULED, and what the ruling asked for

The orchestrator ruled both halves of the proposal, relaying the owner's
authority: delete `.claude/hooks.json`, and make Tier 2 scripts-only in the same
change. Three conditions came with it.

**Condition 1 - the tier change needs its OWN evidence.** Met by
`tests/test_cpp_tier_detection.py`, which EXTRACTS the predicate from
`.claude/commands/cpp/update.md` and executes it against a synthetic project and
a fake `HOME`. A copy pasted into the test would pass while `/cpp:update`
shipped something else, so the shipped document is the source.

Measured, not argued:

| predicate | fresh project, 3 scripts, no hooks.json | result |
|---|---|---|
| BEFORE (`-f hooks.json` AND `>= 3`) | run against the same tmpdir | **TIER=1** |
| AFTER (`>= 3` alone) | same tmpdir | **TIER=2** |

The red case is committed too: two named scripts must stay at Tier 1, which is
what makes the passing case a measurement rather than a predicate that is always
true. A fourth test pins the conjunct out of the shipped block directly, since
the behavioural tests would catch its return only while CPP also stopped
shipping the file.

**Condition 2 - keep `cpp/init.md:374`'s `rm .claude/hooks.json`.** Kept, and it
costs nothing. Uninstall must still remove a file an earlier install left
behind, or pure removal strands it on every existing project. `/cpp:update` Step
4.7 now offers the same removal, reworded from "strip the retired PreToolUse
block, masking untouched" to "remove the whole file".

**Condition 3 - no empty `{"hooks": []}`.** Not taken. An empty hooks file that
nothing loads is the same false impression with fewer words.

## What the claim control caught, including its author

Shown RED before the change: **14 lines across 10 files**, saved verbatim. Three
were in no one's enumeration - `.claude/verify-coverage.json:208`,
`scripts/hook-permission-census.sh:150`,
`templates/claude-settings-permissions.md:37` - and they are the argument for a
SHAPE rather than a list of today's phrasings.

It then failed twice more on prose written to explain the removal: a
`flow/doctor.md` sentence that paired the two words in order to DENY the
pairing, and a comment inside the Tier 2 block naming the file it had just
dropped. The first was reworded - the control has no negation carve-out and
should not acquire one. The second was narrowed instead, and deliberately:
matching a comment that explains WHY the conjunct went would force the
explanation out of the document to keep a test green, which is a check deleting
the record of its own reason.

## The two justifications that got STRONGER, not weaker

`templates/claude-settings-permissions.md` and `scripts/hook-permission-census.sh`
both cited the masking hook as context for refusing to allowlist file-dumpers
(`cat`, `head`, `tail`, ...). Removing a protection could have read as weakening
that case. It does the opposite and the text now says so: with nothing masking
anything, the prompt in front of `cat .env` is the only thing between a secret
file and the transcript.

## Section E - what the counter-model review changed, both passes

Eleven findings across two passes, all MEDIUM, all accepted, none rejected or
deferred. Receipt `2026-09-23T165616Z-issue-1206.json`, reviewer
`codex/gpt-6-astra` derived from the exec-log thread id. Two passes is the
documented ceiling, so pass 2's findings were fixed WITHOUT a third review.

**Six of the eleven were defects in the instruments, not in the removal.** The
prose sweep itself was largely sound; what kept failing was the thing measuring
it. Worth recording, because the instrument is the artifact nobody reviews:

| pass | finding | what it was |
|---|---|---|
| 1 | Step 4.7 detection | keyed on the RETIRED hook's name, so it could not see the file CPP itself shipped - a promise (`/cpp:status` now points users at it) with no mechanism |
| 1 | masker header | the claim survived in the body of the file whose title I had just corrected |
| 1 | read failures discarded | population counted PATHS, not READS: 400 unopened files reported zero offenders |
| 1 | walk could not attribute | an untracked local note, or a user's own opted-in `settings.local.json`, read as a CPP regression |
| 1 | same-line JSON grep | a registration wrapped by a formatter passed untouched |
| 2 | window wrong BOTH ways | missed a 4-line claim AND fused two unrelated bullets into one |
| 2 | test tested a copy | the regression test drove its own walker; stubbing the production scanner left it green |
| 2 | unreadable new surface | the broad scan's aggregate threshold absorbed it and the narrow scan never visits it |
| 2 | standalone call read as registration | flagged the retained file-at-rest use this change exists to preserve |
| 2 | ignored leftover read as regression | contradicted this PR's own migration path, inside the same PR |

**The pattern across both passes:** every one of my repairs was correct about
the thing it was aimed at and wrong about something adjacent. The fixed-size
window is the clearest - added in pass 1 to catch a wrapped claim, it was too
narrow for a four-line one and too wide for two bullets, simultaneously. Size
was never the dial; the UNIT was. A claim is a sentence.

**Three times the control caught its own author**, which is the part worth
keeping: prose written to explain the removal, a comment naming the file the
Tier 2 block had just dropped, and a comment describing failure semantics in
terms of "by the time a PostToolUse hook runs" inside a script that is no longer
one. A control with no negation carve-out catches the person most motivated to
write around it.

---

# Run 3 - issue #1206, the two claims #1224 missed

A THIRD run on the same issue. Runs 1 and 2 above are left exactly as approved.

- Issue:             #1206, Decision 1 remainder
- Base SHA:          99670b5
- Necessity verdict: Partially addressed
- Approval:          granted ("approved"), with the two open questions taken at
                     their proposed defaults: (a) delete the CLAUDE.md:10
                     sentence, (b) cpp/init.md:209 routed to the Nit Store
- Approver:          the owner, directly in this session
- Recorded at:       2026-09-23T21:55:00Z

## Section B evidence

Commits since filing touching the claim surfaces: 658d971 (#1208), 86e1c8d
(#1199), e1379c7 (#1224). Merged PRs: #1208, #1209, #1224. Duplicates or
superseding issues: none open (#439 and #598 are closed and historical).

Every item in the owner-ruling list is on main at 99670b5. Two claims are not:

- `.claude/commands/cpp/help.md:56` - `**Hooks**: Security (command validation,
  output masking)`, which /cpp:help prints to every user. The claim control
  missed it: no "PostToolUse", no dispatch token, and the file is not in
  CLAIM_BEARING.
- `CLAUDE.md:10` - "Output masking does not protect response text." It predates
  #1224 (411968e6, 2026-08-16) and implies that output masking exists.

## Section C - the approved plan (run 3)

Items for this run, restated in prose so the Section C parser, which reads
run 1's section, is not given a second list:

- cpp/help.md - the Hooks bullet now says what Tier 2 actually offers: optional,
  default-N user-level hooks, with no safety claim.
- codex/skills/cpp-help/reference.md - regenerated mirror, never hand-edited.
- CLAUDE.md - the sentence at line 10 is deleted and the NEVER directive is kept.
- tests/test_hook_mask_output.py - help.md is added to CLAIM_BEARING, plus a
  third shape (hooks paired with output masking as a feature). Red case: the
  old help.md:56 text is flagged. Negative case: the doctor.md at-rest helper
  row is not flagged.

Scope: 4 files plus one mirror, about 40 lines. Risk: the new shape could
false-positive on a description of the at-rest tool; the committed negative
case guards that. Out of scope: cpp/init.md:209 ("rely on hooks for safety"),
routed to the Nit Store.
