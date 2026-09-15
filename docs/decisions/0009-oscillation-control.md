# ADR 0009: Oscillation Control - a two-sided change must name what would move it back

- Status: Accepted
- Date: 2026-09-15
- Issue: #936
- Supersedes: nothing
- Related: [ADR 0008](0008-instrument-negative-control-bound.md) (the structural
  sibling - that one governs instruments, this one governs the knobs those
  instruments are set with; they are stated as a pair deliberately, because one
  is memorable because of the other), #937 (a two-sided call that was escalated
  before a procedure existed to receive it), #935 (the gitleaks allowlist, row
  3 of the corpus below).

## TL;DR

Some choices run down the middle of opposing trade-offs, and a project swings
between them. **Before shipping a two-sided change, name the observation that
would move it back, and commit it beside the setting.** If you cannot name one,
it is not a decision - it is a preference, and it will oscillate.

A change carrying any tell is **not landed on a worker's own judgement**; it
goes to the orchestrator, who reports every such call to the owner at wave
close.

## The pattern

In the owner's words, an approach choice inherently

> runs down the middle of two trade-offs, and we inevitably oscillate back and
> forth to each side in a futile attempt to satisfy diametrically opposing
> desires.

**The failure is not that either swing is wrong.** Each is locally correct: it
fixes the pain actually present. The failure is that the pain on the *other*
side is invisible at the moment of the fix, because it is not currently being
felt - it was fixed last time. The rationale explaining why the knob was where
it was gets overwritten by the move that replaces it.

## Why this is the sibling of the negative-control rule

ADR 0008 says: before you ship an instrument, name the input that makes it
report the OTHER verdict. If you cannot name one, the instrument is blind.

This says the same thing about a policy choice. Same epistemics, different
object - one governs instruments, the other governs their settings.

## The tells

A two-sided change is identifiable *before* it lands. Any of these is a
positive:

- it adjusts a **threshold, timeout, tolerance, retry count, or exit-code
  policy**;
- it adds an **allowlist, exclusion, skip, or carve-out** entry;
- it makes a check **more permissive or more strict without changing what the
  check measures**;
- its justification has the form **"X was too Y"** - too noisy, too strict, too
  slow, too chatty;
- **strongest and most checkable:** the diff touches a line whose adjacent
  comment, docstring, or ADR exists specifically to explain why it is set that
  way. A rationale is a fossil of the last swing. Editing the setting without
  answering the rationale is the oscillation, mechanically.

**What is NOT two-sided:** changing what a check *measures* is ordinary
iteration. Widening a model-presence check so it stops matching a mere prefix
changes the question being asked; it does not move a knob. The distinction has
to live in the tells or the rule is unusable.

## The escalation rule

**Owner ruling, 2026-09-15:** a change carrying any tell goes to the
**orchestrator** where a wave holds one - not to the owner per incident. The
owner receives a **consolidated summary at wave close**: what was changed,
which way, and the reversal trigger committed with it.

Routing every threshold edit to the owner makes asking slow, and the moment
asking is slow people stop asking - which is this control's own failure mode
arriving through the front door.

The worker sees one side: the failure in front of them, which is real. Whoever
holds the history of the previous swing can see both. **Escalation is how the
invisible side gets a representative in the room.**

## Where the trigger is recorded

**Beside the setting. Not in a PR description.** A PR body is not read by the
next person to touch the line, which is exactly why the rationale comments this
repository keeps finding are the only surviving record of the previous swing.

## The detector

`scripts/check-oscillation.py` derives knob moves from git history and reports
any knob whose direction **reversed**. Changed twice is not the signature;
changed *back* is.

**It reports. It does not fail the build.** A blocking detector that flags
every threshold edit gets switched off, and switching it off is itself an
oscillation - performed by the control built to prevent oscillation. A finding
exits 0.

That is deliberately not the same as an exit code that cannot fail:

| verdict | exit | about |
|---|---|---|
| `found` / `none` | 0 | the knobs |
| `unknown` | 3 | **this run's ability to look** |

A population of zero is `unknown`, never `none`. "I examined 400 knob changes
and none reversed" and "I examined nothing" are different facts and do not
share a word or an exit code.

There are four ways to fail to look, and they share the verdict and the exit
code but not their `OSCILLATION_REASON`: `not-a-git-repository`,
`range-unresolvable` (git refused the range - `HEAD~200` on a shorter history),
`range-empty` (the range resolved and holds no commits) and `no-knob-changes`
(a real history with no knob edits in it). That split is the #953 convention
applied one level down: a different CONCLUSION earns a new verdict, the same
conclusion reached for a different cause earns a reason field. They were folded
together at first, and a reader chasing a refused range would have gone looking
for knobs that were never the problem.

**The population is derived from history; there is no knob list.** A hardcoded
list of the knobs worth watching is a coverage enumeration, and this repository
has repeatedly found those stale. A knob introduced next month is watched from
its first edit.

Its two committed cases are in `controls/check-oscillation`: a knob that
reversed (must be found) and one tightened monotonically (must *not* be). The
second is the one that matters - a detector flagging every threshold edit is
noise, and noise gets disabled.

**What it cannot see, stated rather than discovered later.** Knob extraction is
regex over diff hunks, and the scope is numeric settings and whole-line exit
codes. Every limit below is a MISS, never a wrong attribution - the standing
trade, because a finding that names the wrong line costs a reader more than a
finding that never arrives, and a reporting detector that cries wolf gets
ignored, which is how this control fails.

- A setting expressed as anything but a number - an enum, a flag name, a
  duration string, **allowlist membership** - is outside it entirely. Adding
  `"foo"` to an allowlist and later removing it produces no moves at all.
  `tests/test_oscillation_control.py` pins that as a property so the claim
  cannot quietly return.
- A knob renamed, or moved to another file, starts a new series; an
  oscillation spanning the move is missed.
- `exit N` is recognised only as a whole line, so a guarded
  `[[ -n $x ]] && exit 3` is not seen. The alternative matched every sentence
  of prose discussing exit codes, and this repository's documentation discusses
  them constantly.
- A unit-bearing value (`--timeout 1m`) is not read as a number. Read as one,
  `1m`, `60s`, `2m` become 1, 60, 2 and a duration that stayed equal then grew
  reports as a reversal.
- Two sites changed inside ONE hunk collapse into one, so the second hides the
  first. Across commits they are separated: moves are threaded into continuous
  per-site chains (the value a move starts from is the value the previous move
  landed on), which is what stops `first(timeout=60 -> 30)` pairing with an
  unrelated `second(timeout=10 -> 20)`. Two sites that genuinely pass through
  the same value can still be threaded together.
- History is walked `--first-parent --diff-merges=first-parent`, which is the
  integrated branch's own story - not the interleaving of both sides of every
  merge, which made two branches moving a shared base in opposite directions
  render as a swing neither performed.

That list is the honest shape of the thing: the tells in this ADR are broader
than any parser, exactly as ADR 0008's bound is broader than
`check-negative-controls`. **The detector is a floor under the directive, not a
substitute for it** - which is why the escalation rule, not the detector, is the
part of this ADR that carries the weight.

## This control is subject to its own rule

**Its reversal trigger, committed here before shipping** (owner ruling,
2026-09-15):

> If a worker escalates and the answer is "just do it" three times running, the
> tell list is too wide. Narrow it to the strongest tell - editing a line whose
> adjacent comment, docstring, or ADR exists to explain why it is set that way
> - and drop the rest.

The detector's own `--window` threshold carries a trigger beside it in the
source, for the same reason.

## Scope

**This is not a process tier.** One directive, one escalation rule, one
detector. If it grows a workflow, it has gone wrong and the trigger above has
fired.

**The directive half is not in this repository.** It belongs in the owner's own
standing-instructions file (`~/.claude/CLAUDE.md`), which is outside this repo
and is theirs; the text is put to them rather than written on the strength of a
ticket. What lands here is this ADR, the detector, and its controls.

Note also that kyle#1176 records that file is **not mounted into Kyle's session
containers**, so a directive alone does not reach the default placement there -
which is part of why the detector exists rather than the rule alone.

## Consequences

- Two-sided calls slow down by one message to the orchestrator.
- The record of *why* a setting sits where it does survives the next person to
  move it, because the trigger is next to the setting rather than in a merged
  PR body.
- The detector will report knobs whose reversal was deliberate and correct.
  That is expected: it reports, a human reads, and the reversal trigger is what
  makes the reading cheap.
