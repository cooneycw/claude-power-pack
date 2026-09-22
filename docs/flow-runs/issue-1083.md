# Flow run record - issue #1083

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system and it does not graduate.

- Issue:             #1083
- Base SHA:          43286db
- Necessity verdict: Still needed
- Approval:          granted - GO-WITH-CONDITIONS
- Approver:          CPP-improvements-orch (wave claude-improvements, policy
                     rev 4, authority-model orchestrator-only)
- Recorded at:       2026-09-22T13:40:00Z

## Section B evidence

- DEPENDENCIES DISCHARGED BY FACT, not by ruling. The body says "Depends on:
  #1073, and #1080 ... Wait for it." Measured: #1073 CLOSED, #1080 CLOSED.
  #1079 is the open parent wave, as expected.
- THE GAP IS REAL. `.claude/hooks.json` carries one SessionStart notice and two
  PostToolUse masks. Nothing enforces #775.
- THE BOUND, measured from this session's own behaviour: a PreToolUse hook
  matching Write/Edit IS BYPASSED BY BASH REDIRECTION. Every plan record in this
  session was written with `cat > ... <<'RECORD'`, not the Write tool - three
  runs, three records, zero Write calls.
- AND IT IS INSTRUCTED, NOT INCIDENTAL. This session's own operating
  instructions direct file changes through Bash: "make file changes with sed,
  heredocs, or short scripts, rather than using the dedicated Read, Edit, or
  Write tools." The orchestrator found the same steer in other sessions on this
  host. So in THIS fleet the unseen path is the default, not an escape.
- BOOTSTRAP DEADLOCK in the scope as written: the approved-plan record is
  written at Step 4 and writing it IS an edit, so a hook refusing edits without
  a record blocks the write of the record that would unblock it.

## Section C - the approved plan

1. `scripts/step3-record-guard.sh` (new) - a PreToolUse hook. In a flow worktree
   (branch `issue-<N>-<slug>`) with no approved-plan record at
   `docs/flow-runs/issue-<N>.md`, it REFUSES the edit. Refusal is refusal: a
   state it cannot read is refused and said, never allowed. Exactly ONE
   exemption - the record's own path - and the BLOCK MESSAGE names it, so a
   person hitting the block learns why that one path differs.
2. `templates/` - the opt-in shipping surface. Never silently installed: CPP
   ships to other people's projects and a hook that blocks edits must not
   arrive unannounced.
3. `controls/step3-record-guard` (new) - the committed control. The pair: a
   fixture worktree with NO record blocks; the same fixture WITH a record
   allows. The anti-control property is the one that matters - case (i) must
   STOP blocking the moment the record is added, so a hook that blocks
   unconditionally cannot pass. Fixtures are BUILT; never the live worktree.
4. THE BLIND PATH AS A COMMITTED CASE, not a sentence: the same recordless
   fixture written via Bash redirection, with the hook observed NOT to fire,
   registered with that outcome as its expectation. If the harness stops
   steering to Bash, or the hook grows Bash matching, that case CHANGES - and
   the change is the notification. Prose cannot do that.
5. `tests/test_step3_record_guard.py` (new).
6. ADR 0008 row, `.claude/verify-coverage.json` entry, `docs/scripts.md` row -
   the new script owes all three.
7. SEPARATELY COMMITTED: the anti-control sentence into
   `docs/agents/detector-contracts.md` as the third reviewer question, with the
   #1203 evidence as its worked example.

### What this change does NOT claim

It is a FLOOR. It enforces the PRESENCE OF AN ARTIFACT, not the OCCURRENCE OF AN
APPROVAL, and only on the tool paths it matches. Nothing in the hook, the docs,
the ADR row or the PR body may say #775 is now enforced. The full acceptance is
NOT met: meeting it needs /flow:auto to RECORD Step 3 where a hook can read it
before the first edit, which is a command-document change and a different blast
radius. The orchestrator's pre-committed stopping rule was invoked rather than
designed around, and the close report must name what would be required.

The limits must state the worth SEPARATELY for two audiences: near-zero coverage
in this fleet, where Bash-first is the instructed default; genuinely useful where
it ships, because that steer is a property of how this fleet is operated and not
of the hook mechanism. A reader here must not take silence as evidence; a reader
elsewhere should know what they are getting.

### Named risks

1. A hook that blocks edits is the highest-blast-radius artifact in this
   repository. Opt-in is not optional, and the block message must make the state
   RECOVERABLE rather than merely refused.
2. Refuse-when-unreadable is correct and WILL block real work when a record is
   missing for an innocent reason. That cost is accepted deliberately.
3. The record-path exemption is a hole - anything that can write the record can
   write itself an approval. Given the Bash bound it is already subsumed by a
   wider one, so it is not the marginal risk, but it goes in the limits rather
   than being left for a reader to find.
