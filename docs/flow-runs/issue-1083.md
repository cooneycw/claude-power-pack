# Flow run record - issue #1083

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system and it does not graduate.

- Issue:             #1083
- Base SHA:          250d56f
- Necessity verdict: Partially addressed
- Approval:          granted - items 1-4; the companion reporter approved as a
                     SEPARATE PR with four binding conditions
- Approver:          wave `claude-improvements` orchestrator, session
                     `claude-improvements-new`, mailbox rev 13, acked after the
                     content was held.
- Recorded at:       2026-09-23T16:10:00Z

## THE PRIOR RUN'S RECORD IS SUPERSEDED, NOT DISCARDED

This file previously held the record for PR #1205 (commit 0643349), which shipped
the floor. That run's findings STAND and are carried forward here rather than
overwritten, because they are the reason this run's scope is what it is:

- the gap was real - `.claude/hooks.json` enforced nothing of #775;
- a PreToolUse hook matching Write/Edit IS BYPASSED BY BASH REDIRECTION;
- the bypass is INSTRUCTED, not incidental - sessions are steered to edit through
  the shell;
- there is a BOOTSTRAP DEADLOCK: the approved-plan record is itself an edit, so a
  hook refusing edits without a record blocks the write of the record that would
  unblock it. Solved by exactly one exemption, the record's own path;
- and that run declined to claim #775 was enforced, landing with `Refs #1083`
  rather than a closing keyword.

## Section B evidence

- ONE commit touches the lane since the issue was filed (2026-09-19): 0643349,
  PR #1205. It shipped `scripts/step3-record-guard.sh`,
  `controls/step3-record-guard` (5 cases), `tests/test_step3_record_guard.py`
  (16 tests) and `templates/hooks/step3-record-guard.md`. Not wired into this
  repository's own `hooks.json` - correctly opt-in.
- THE GAP THE ISSUE DESCRIBES IS UNCHANGED at `250d56f`: `.claude/hooks.json`
  carries one SessionStart notice and two PostToolUse masks, and no PreToolUse
  entry at all.
- THE SHIPPED GUARD WAS EXERCISED, not read. Four states, and the first attempt
  at this measurement was WRONG in a way worth recording: it read `$?` after a
  pipe, which reports the pipe's last stage rather than the guard's. Re-run
  without the pipe:

      recordless + Write                 -> exit 2  (BLOCK)
      approved record + Write            -> exit 0  (allow)
      the record's own path, recordless  -> exit 0  (the single exemption)
      recordless + Bash                  -> exit 0  (ALLOW - the bound)

- A CLOSED BLOCKER MEANS DROPPED OR DELIVERED, AND THE WORDS LOOK IDENTICAL.
  The issue body says "Depends on: #1073 ... Wait for it." This run first checked,
  saw CLOSED, and wrote "discharged" - which was wrong. Only `stateReason`
  separates the two:

      #1073  CLOSED  reason=NOT_PLANNED   <- cancelled, not delivered
      #1080  CLOSED  reason=COMPLETED     <- genuinely delivered

  The prior run's record reads "Measured: #1073 CLOSED, #1080 CLOSED". That
  sentence is TRUE and it conflates the two states whose difference is the entire
  point. It is quoted here as the example rather than corrected away.
- THE OBLIGATION INVERTS rather than lapsing. The dependency existed so hook
  delivery would not be built twice, with the second build forced to preserve the
  first's trust roots. With #1073 cancelled there is no second builder, so #1083
  is the sole owner of hook delivery in CPP and later Codex hook work inherits
  ITS trust roots. Two issue comments say so; both were read.
- BOUNDARY CHECKED: a PreToolUse entry in `.claude/hooks.json` is the CLAUDE
  namespace and does not reach `~/.codex/`, so spec boundary B2 stays dormant.

## THE COVERAGE MEASUREMENT, which is why the verdict is not "still needed"

Counted from this session's own transcript, across five delivered issues (#1182,
#1191, #1192, #1151 and the S4 re-sync trigger):

    Bash                         468 calls
    Write + Edit + NotebookEdit    0 calls

The guard matches `Write|Edit|NotebookEdit`. It would have fired ZERO times over
every plan record and every source edit this session made.

ON S4 SPECIFICALLY, where the orchestrator waived Step 3, the layer would have
been inert for TWO independent reasons: the matcher never fires on Bash, AND that
branch was `s4-...` rather than `issue-<N>-<slug>`, so the guard would not have
recognised the worktree as a flow worktree at all. A deterministic layer would
not have stopped the waiver, and would not have stopped this session proceeding
on it.

THE HONEST POSITION, since the issue promises "enforced rather than asserted":
enforced for the tool path nobody here uses, asserted for the one everybody does.
That is an argument about COVERAGE, not about correctness. The hook does what it
says on the paths it matches.

## Section C - the approved plan

1. `controls/step3-record-guard/control.json` - replace the coverage ESTIMATE in
   `limits` with the MEASUREMENT above. The earlier figure is recorded as
   superseded rather than corrected: same direction, two orders of magnitude more
   input.
2. `templates/hooks/step3-record-guard.md` - the same measurement for a consumer,
   plus the TRUST-ROOTS note: hook-delivery trust roots are now this hook's,
   because the issue that was going to own them was cancelled rather than
   delivered, and the B2 boundary stays dormant while this remains in the Claude
   namespace.
3. `docs/flow-runs/issue-1083.md` - this record.
4. `docs/flow-runs/issue-1083.as-read.md` - the as-read snapshot.

Scope: 4 files, approximately 80 lines. Deliberately small: the substantive
remainder is not code.

## What was RULED OUT, and by whom

- (a) MATCHING ARBITRARY SHELL for write syntax - declined by this run and by the
  orchestrator. A candidate list over `>`, `tee`, `sed -i`, `cp` and python
  one-liners is a path-set PREDICTION, the shape #1136 removed, and it would
  refuse on every `> /dev/null`.
- (b) CHANGING THE FLEET'S EDIT STEER so edits go through Write/Edit - not a
  worker's and not an orchestrator's. It is host configuration shared by every
  session on the machine. Put to the owner.
- (c) A POSTTOOLUSE COMPANION that REPORTS the ungated path - approved as a
  SEPARATE PR, with four binding conditions: it never blocks and never returns a
  refusing exit code; it reports UNGATED rather than FAILED, because taking the
  documented path is not a violation; its own control must carry a case that
  renders UNEXAMINED rather than clean; and it is opt-in and not wired here.

Risks: R1 the coverage measurement is from ONE session on ONE host - it is a
measurement of this fleet, not of the hook, and the template says so for a reader
elsewhere. R2 replacing a smaller measurement with a larger one can read as
correcting an error; it is not, and the record says so. R3 the trust-roots note is
a design consequence with no task attached, which is exactly the kind that gets
lost - it goes in the shipped template rather than only in this record.
