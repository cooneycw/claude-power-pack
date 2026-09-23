# Flow run record - S4: the codex re-sync trigger keys on the DIFF, not the BASE

HISTORICAL RECORD of what was agreed and why, written AFTER the change landed.
It is not a description of the shipped system and it does not graduate.

**Written late, and that is itself the finding.** S4 was owner-directed work with
NO ISSUE NUMBER, so the issue-anchored flow lane wrote no record: the plan-record
path is `docs/flow-runs/issue-<N>.md` and there was no `<N>`. The change merged
as `250d56f` (PR #1218) with its reasoning living only in commit messages, the
PR body, and a session transcript. This file exists because the wave's wind-down
asked what would survive the session ending, and for S4 the honest answer was
"nothing addressable".

- Subject:           the Codex skill mirror re-sync trigger
- Issue:             NONE - owner-directed, scheduled as "S4" by the wave
                     `claude-improvements` orchestrator
- Durable finding:   Nit Store #864 comment 5796792965
- Landed as:         250d56f (PR #1218), base 384672d
- Approver:          wave orchestrator, session `claude-improvements-new`,
                     mailbox rev 11; Step 3 WAIVED explicitly, see below
- Recorded at:       2026-09-23T16:35:00Z (after the merge)

## What was wrong

#1136 replaced a path-pattern condition with a helper that decides for itself by
asking `codex-skill-sync.py --check`. What it did not touch was the condition
WRAPPING that call. All three sites sat inside:

    if [ "$(git rev-list --count HEAD..origin/main)" -gt 0 ]; then

so the helper ran only when the BASE had moved. Mirror drift is caused by
EDITING a file the skills bundle, which is independent of the base. An ordinary
run that edited `scripts/<name>` on a current base never re-synced, and
`make verify` was the only thing that said so - at the cost of a full gate cycle
on the single shared CI agent.

MEASURED, on the same day, by the session that made this change: #1191 staled two
mirrors and #1192 staled four, and NEITHER run had a moved base. The author had
met the hazard on #1191, written it into that PR's body, and still did not
re-sync proactively on #1192 one issue later. Knowing a hazard is not the same as
having a trigger for it.

## The fix, and what it deliberately is not

The helper is called UNCONDITIONALLY at all three sites - `flow/auto.md` Step 6,
`flow/auto.md` Step 7, `flow/finish.md` - and nothing cleverer. It already
decides for itself at a measured 0.14s on a clean tree, so a condition here could
only ever be a worse oracle than the one inside it.

**It is deliberately NOT built on an enumerated path set**, and the temptation was
concrete: `--list-mirrors` (#1151) had shipped an hour earlier and would have
made a path-set trigger easy to write. Two independent reasons, and the second
was not known when the orchestrator ruled:

1. It would be a path-set PREDICTION, which #1136 removed: "the fix is not a
   wider glob - that is a hardcoded universe again, one entry longer."
2. `--list-mirrors` answers the LANE question, not the DRIFT question. For a
   bundled script the two sets coincide; for a command document they diverge -
   editing `auto.md` and `finish.md` put 50 paths in the lane and drifted 2. A
   trigger built on it would have been wrong ON ITS OWN TERMS, not merely
   stylistically regressive.

**The commit travels with the re-sync.** At Step 7 the re-sync is followed by a
commit block staging `codex/skills/`, and the branch is squashed straight after
the push with no further commit step. Moving the re-sync out and leaving the
commit behind would have re-synced and then NOT committed it - so the squash
would carry stale copies, which is precisely the race that block exists to
prevent. A change whose whole purpose is keeping stale mirrors out of a squash,
arranging for exactly that.

**And the same shape bit once more, one layer out.** Step 7's re-gate instruction
read "if the merge above ran", which was complete only while the re-sync lived
INSIDE the merge block. After the move, a resync-only run commits mirrors there,
so that commit could reach the squash unvalidated and unpushed. Found by the
counter-model pass, not by the author. The general form: MOVING CODE OUT OF A
BLOCK SILENTLY ORPHANS EVERY CONDITION THAT WAS READING "we are in that block"
AS A PROXY.

## The tripwire, and its own failure modes

`test_no_call_site_gates_the_resync_on_a_MOVED_BASE` is a STRUCTURAL `if`/`fi`
walk rather than a line scan, because `flow/auto.md` legitimately branches on a
moved base for the MERGE and that must not read as this defect.

RED CASE: it FAILS on the pre-fix tree, naming all three sites by file and line -
`auto.md:1038`, `auto.md:1843`, `finish.md:75`. Three controls sit beside it: it
fires on a constructed gated call, does NOT accuse a re-sync placed correctly
after the block, and IGNORES a base-moved check in a fence that never mentions
`codex-skill`.

The first cut of that tripwire failed in BOTH directions and the counter-model
found it:

- FALSE POSITIVE - `elif` pushed a level belonging to the open `if`, and
  `fi # comment` never popped, so a CORRECTLY placed call read as gated. Neither
  fixture involves this call at all, so a change to the neighbouring merge block
  could have failed the suite.
- FALSE NEGATIVE - a multiline `if` and a `~~~bash` fence hid a REAL base-gated
  call and returned `[]`, byte-identical to "examined and found nothing".

The second is detector-contract question 1 failing INSIDE a tripwire built to
guard that class. The repair is the one that generalises: the walk now
RECONCILES against every invocation in the document and returns what it could not
parse as UNEXAMINED, asserted separately. An empty offender list now means "I
looked at all of them".

One narrowing is stated rather than assumed: the fence walk only inspects blocks
mentioning `codex-skill`, and that CANNOT hide an invocation, because the
invocation's own text contains the string. Its #1136 sibling has no such
guarantee. Pinned by a test so the reasoning is not re-derived.

## Process facts worth surviving

- **Step 3 was WAIVED, explicitly and retroactively.** The orchestrator supplied
  the complete plan as four binding conditions, so there was no worker-proposed
  plan to judge. It recorded the rule that followed: when the orchestrator
  supplies the plan, it must SAY whether Step 3 is waived. The
  necessity/staleness verdict is never waived.
- **This worktree had no claim lock.** `flow-worktree-claim.sh claim` requires
  `--issue`, and issueless work has none. Two of three other issue-anchored
  points bite the same way: `flow-start-resolve.sh` and its renaming verify gate,
  and the `docs/flow-runs/issue-<N>.md` path. `counter-model-receipt.py` does
  NOT - it accepts `--issue S4` and the gate recognised the receipt. Recorded as
  S5; the claim gap is the one with teeth.
- **The branch was pushed before gating**, on the orchestrator's instruction,
  precisely because nothing protected the worktree.
- Every bash fence mentioning `codex-skill` was syntax-checked with `bash -n`
  after relocating a block across an `fi`: 5 blocks, 0 errors. A
  markdown-embedded shell snippet breaks silently there.

## What this does NOT claim

It fixes WHEN the re-sync runs. It does not make mirror drift impossible, it does
not touch what the generator bundles, and it says nothing about the Codex surface
beyond the three call sites named above.
