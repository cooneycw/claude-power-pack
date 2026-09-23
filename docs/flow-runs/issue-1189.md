# Flow run record - issue #1189

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1189 (defect 2 only - see the scope note)
- Base SHA:          250d56f
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          wave orchestrator `claude-improvements-new`
                     (session a9c791f1-8a8d-4b1b-a7b2-c7e181009503), wave
                     `claude-improvements`, mailbox rev 10, scope ruling rev 9
- Recorded at:       2026-09-23T16:35:00Z

## Scope, and what is deliberately NOT here

#1189 carries two defects. This PR delivers the CONSUMER half of defect 2 only.

DEFERRED ON A LANE CONSTRAINT, NOT ON JUDGEMENT - recorded so a successor does
not re-derive whether they were considered:

- **Defect 1**, a `GATE: HOLD`'s reason silently dropped. The fix is in
  `scripts/flow-wave-lexicon.sh`, held by another worker with PR #1212 open and
  unmerged. The mechanism was measured during this run and is sharper than the
  issue states: `:554` harvests continuation lines with a sed matching ONLY list
  shapes (`- x`, `* x`, `1. x`) for EVERY verb, so prose beneath any token is
  dropped. Same HOLD, bullets beneath give a real stored reason; prose beneath
  gives `GATE: HOLD (no reason given)`; both validate clean at 0 errors. HOLD is
  where it bites because `GO-WITH-CONDITIONS` refuses an empty harvest (`:558`)
  and `MERGE: PRIORITY` refuses a missing argument (`:659`), while HOLD has
  neither guard. **The fix is the REFUSAL, not widening the sed** - widening
  would make HOLD accept anything beneath it as a reason, which is a different
  defect.
- **The PRODUCER half of defect 2**, at `scripts/flow-wave-lexicon.sh:533-536` -
  the `^#([0-9]+)` refusal that makes an issueless ruling unformable. Same file,
  same constraint.

Defects 1 and 2 are one problem WITH EACH OTHER - "the ledger's record of a
ruling is narrower than the ruling" - and the coherence is recorded here rather
than in the packaging, because idling half a worker until both halves are
available is a worse trade than shipping the reachable half.

## Section B evidence

Issue filed 2026-09-21T20:57:28Z. Inspected:

- Commits touching `scripts/flow-wave-plan.py`, `scripts/flow-wave-lexicon.sh` or
  `tests/test_flow_wave_plan.py` since filing: **NONE**, out of 23 commits landed
  in that window. The named paths were checked, not the repository generally.
- Merged PRs inspected: #1210, #1213-#1218. None touch the ledger, its schema or
  its reader.
- Duplicate / superseding issues: **none**. A full-text search for "verdict
  ledger" across all states returns #1189 itself; #1014, #1079 and #1084 are
  adjacent wave-record work and none key or read `verdicts.json`; #1129 is closed
  and concerns the control register.

## Section C - the approved plan

Measured first, because the mechanism is worse than the issue states. Same
planner, same issues file, one line different in the ledger:

    numeric-only ledger   -> exit 4, plans normally, hold enforced
    + one slug entry      -> exit 2, "cannot read verdict ledger: invalid
                             literal for int() with base 10: 'journal-false-red'"

`flow-wave-plan.py:376` does `latest[int(e["issue"])] = e`, so ONE unrecordable
ruling makes the planner reject THE WHOLE LEDGER - every other ruling in the file
stops being read with it. The issue describes a gap; what is there is a single
point of failure. It fails LOUD (exit 2, named cause, no plan produced) and
cannot schedule a worker onto a held issue, because it refuses to schedule at
all - less dangerous than a silent wrong answer, and still worth fixing, because
a record whose purpose is to outlive sessions is disabled by one hand-written
line.

 1. `scripts/flow-wave-plan.py` - key the ledger on `subject` rather than
    `int(issue)`. Accept an entry carrying EITHER `issue` (numeric, as today) or
    `subject` (a short slug). Non-numeric subjects are read, retained and IGNORED
    FOR PLANNING - the planner only schedules issues, so a slug ruling can never
    gate one. A malformed entry must not take the ledger down with it, while a
    genuinely unparseable ledger must still refuse: those are different states
    and the change keeps them different.
 2. `tests/test_flow_wave_plan.py` - regression tests. The load-bearing case is
    the measured pair: a ledger carrying a slug entry alongside a numeric hold
    must still enforce the numeric hold, where today it refuses the file. Run RED
    on this code first. A numeric-looking subject must still be treated as
    numeric, so a typo cannot silently become a slug and stop gating its issue.
 3. `controls/flow-wave-plan` - decided at Step 4 against the ADR 0008 bound
    rather than added reflexively.
 4. `docs/flow-runs/issue-1189.md`, `.as-read.md` - run artifacts.

Scope: 1 script, 1 test module, 2 run artifacts, possibly 1 control. Roughly
80-150 lines.

Risks:

- **The shipped half delivers no reachable capability on its own.** With the
  lexicon refusal in place nothing can EMIT a slug ruling, so the new schema is
  exercisable only through a hand-written ledger. That is a genuine input the
  reader already accepts - not a synthetic stand-in - but a reviewer should know
  they are approving a consumer whose producer is still fenced.
- **Consumer-first is required HERE and forbidden on #1084**, and the two will
  look contradictory to a future reader. The discriminator is WHO OWNS THE
  FORMAT: when the format is already defined and in-repo, the reader goes first
  so the writer is safe to land; when the format is owned elsewhere and
  undefined, the reader must wait or it invents the contract. Here the format is
  `verdicts.json`, in-repo and defined, so the reader goes first - landing the
  producer first would emit entries today's planner rejects wholesale, breaking
  every wave on an older checkout until it pulls.
- **The change touches how a ruling is KEYED.** A malformed-entry policy that is
  too tolerant would let a typo'd numeric subject silently become a slug and stop
  gating its issue. The tests pin that a numeric-looking subject stays numeric.

## Not hypothetical

This wave has run two issueless assignments today - S4 (merged) and S7 (assigned)
- and issued binding rulings on both. Neither can be recorded in the verdict
ledger, for exactly the reason this change addresses. Two of today's rulings are
already in the gap.
