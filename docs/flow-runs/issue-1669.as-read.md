<!-- flow-run n=1 id=c8d92c62f366480d8c97981bba088369 -->
## Run 1 - issue #1669 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1669
- Read at:      2026-11-11T18:51:10Z
- updatedAt:    2026-11-11T14:58:26Z   (context only - moves on comments and labels)
- Body digest:  b86c632a678f53af307da914877b2aa773d7791f252bd2cd6d7525e093f3d462   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2223 of 2223 (cap 16384)

### Body as read
Tier: 2

Source: owner-requested methodology review, 2026-11-11, measured on origin/main at 31fe6a69 against the last commit before 2026-09-12. Owner approved filing.

## Outcome
The flow command documents are read in full on every invocation, so their size is a per-run cost in time, tokens and missed instructions. They should hold the steps to execute and nothing else, and a gate should stop them growing back.

Measured word counts (`wc -w`), 60 days ago vs now:

| File | Then | Now |
|---|---|---|
| `.claude/commands/flow/auto.md` | 10,183 | 20,924 |
| `.claude/commands/flow/register.md` | 8,208 | 16,426 |
| `.claude/commands/flow/wave.md` | 6,954 | 11,837 |
| `.claude/commands/flow/finish.md` | 1,791 | 4,753 |

Much of the growth is incident history and rationale written inside the procedure (for example the multi-paragraph #1138 commentary inside the Step 1 code block of `.claude/commands/cpp/update.md`). CLAUDE.md already states the rule for itself: per-item history belongs in the references, not the always-loaded file. A command document is always-loaded for the run that invokes it.

## Acceptance
- Each `.claude/commands/flow/*.md` is at or under a declared word budget. Owner-approved starting targets are the 60-days-ago sizes above; the implementer may argue a different number per file with evidence, but must declare one.
- A word-budget check covers every command document and runs in `make verify`. Closed #724 added a word budget for `CLAUDE.md`; extend that mechanism, do not build a second one.
- Negative control (ADR 0008, this gate lets work through): a committed case with a command file one word over its budget makes the check report the other verdict.
- No executable step is lost: behaviour-preservation is shown the same way #724 showed it.

## Constraint
Rationale and incident history are not deleted, they move to `docs/commands-reference.md` or a linked reference, per the knowledge lifecycle.

## Proposed approach (revisable)
Trim `auto.md` first as the pilot, since it is the largest and most used, then apply the same pass to the others.

## Assumption
That the shorter document performs at least as well. A proposed extra arm on cooneycw/skillc#657 would measure this.


<!-- end of body -->
