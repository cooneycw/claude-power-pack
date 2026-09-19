# The closing-report contract

**Canonical. Other surfaces point here; they do not restate it.** (The same rule
[the detector contracts](detector-contracts.md) use, and for the same reason: a
contract restated in seven files is a contract that drifts in seven files.)

Every command that ENDS a run emits a closing report against this contract:

| Surface | What it closes |
|---|---|
| `.claude/commands/flow/auto.md` | the full lifecycle |
| `.claude/commands/codex/auto.md` | a lifecycle delegated to Codex |
| `.claude/commands/qwen/auto.md` | a lifecycle delegated to local Qwen |
| `.claude/commands/gemma/auto.md` | a lifecycle delegated to local Gemma |
| `.claude/commands/flow/finish.md` | a run that ends at the PR |
| `.claude/commands/flow/merge.md` | a run that ends at the merge |

## Why this exists

`/flow:eli5` sets a plain-language bar and sets it **once** - at Step 3, before
any code is written, when the agent is asking permission to begin. Nothing
equivalent applies at the other end, when the work is handed back.

That asymmetry is the whole problem. We are careful to be understood when we
want a **yes**, and careless at the moment the context is largest and the
reader's attention thinnest. Reported by the owner against a summary that was
complete and accurate:

> it's too complicated. if there's a "to-do" list for the owner, it needs to be
> clearly defined so the owner does not miss it in the voluminous context.

Correct-and-dense reads as noise, and a buried action item is a missed one.

## The order is the content

Three sections, in this order. The order is not stylistic - the complaint is
specifically about what gets read first.

### 1. `## TO-DO (owner)` - FIRST, always present

Numbered. Each item names **the decision**, not its background.

**When there is nothing, say so explicitly: `Nothing blocking.`** An omitted
block reads as *forgotten*, not as *none*, and those are different facts. This
is the same rule as a missing denominator reading UNKNOWN rather than clean.

**An item qualifies only if it names a decision that is the owner's to make and
that the run did not and could not make:**

- a choice the run made that the owner would plausibly reverse;
- a gate relaxed, bypassed, or newly excluded;
- a residual with a named consequence (the [#714][714] severity test);
- an action reserved to the owner's authority - promotion, deploy, a policy
  change;
- a finding the run surfaced and did not fix.

**Deliberately excluded.** Listed so the exclusion is auditable rather than a
matter of the drafting agent's taste:

- anything the run did *and verified* - that is evidence, and it belongs in
  section 3;
- a constraint on future work - that is an **FYI**, and it goes on its own line
  outside the block;
- "consider X later", "measure Y" - a thought with no decision attached;
- anything whose answer changes nothing about what happens next.

**An FYI is not a TO-DO.** Padding the block with non-tasks destroys its only
property, which is that everything in it needs the owner.

**There is deliberately no numeric cap.** A cap turns a long list into a hiding
problem rather than a signalling one. The strictness lives in the qualifying
test above; a run emitting eight qualifying items is telling you something true,
and the answer is to look at the run, not to truncate the block.

### 2. `## In plain language`

What was wrong, why it mattered, what is better now.

**Under `/flow:eli5`'s existing Section A floor - cited, never re-authored:**
motivation before mechanics, every technical term glossed on first use, and the
bar that *"someone who has never seen this codebase should finish Section A
understanding what is wrong today and what will be better afterward."* See
[`flow/eli5.md`](../../.claude/commands/flow/eli5.md), Section A.

There is exactly one plain-language standard in this repository and it is that
one. This section applies it at the other end of the run; it does not create a
second.

**On the name.** This section is `## In plain language`, not `## ELI5`. "ELI5"
names the pre-implementation **approval gate**, which this is not - a closing
report approves nothing - and a second thing called ELI5 invites the report to
be read as a second checkpoint. The closing report has a plain-language *layer*;
it is not an ELI5.

### 3. `## Evidence`

Red-case results, gate output, review dispositions, CI, and the run's status
lines (issue, changes, PR, branch, worktree, deploy, verify, friction, location).

**Demoted, never deleted.** This is the half that makes a claim about the
*check* rather than about one run - "the check fails on X and passes on Y" is a
claim about the check; "it passed" is a claim about this run. Brevity is never
bought here.

## Relayed reports

`/codex:auto`, `/qwen:auto` and `/gemma:auto` summarise a run a **fenced model**
performed. The relayer did not write the code and cannot report the
implementer's intent.

So every qualifying category above is derivable from the run's own artifacts -
the diff, gate output, review dispositions, CI status, the issue - and none of
them requires knowing what the implementer meant. A contract a relayer cannot
satisfy would fail on three of seven surfaces.

## What enforces this, and what does not

Stated plainly because the honest answer is split, and because a tripwire's
existence otherwise implies more coverage than it has.

**The pointer is enforced.** `tests/test_closing_report_contract.py` derives the
run-closing surfaces from the tree **by path**, asserts each one declares itself,
and asserts each one carries a markdown link that **resolves** to this file. A
surface that drops its marker, breaks its link, leaves the filename in prose
without a link, or reorders the sections reddens `make verify` and CI.

Coverage is deliberately **not opt-in**: a driver added at
`.claude/commands/<model>/auto.md` becomes a candidate the moment it exists, and
must then declare itself. The first cut of that test discovered candidates by
the very marker it was asserting, which meant a new driver that never opted in
was never checked and everything stayed green - the defect this contract is
about, inside the test written to enforce it. A counter-model found it.

**The derivation has a stated bound.** Candidates are recognised by filename
convention - `auto.md`, `finish.md`, `merge.md` - so a
run-closer named anything else is not caught. That is narrower than "any
document that ends a run", and it is the residual this instrument carries
rather than a gap it hides.

**The body is not enforced. Nothing would notice.** If every surface keeps its
pointer and runs simply stop emitting a `## TO-DO (owner)` block, no test in
this repository can tell. These seven files are **instructions to an agent, not
code** - nothing executes them - and the report is model output rather than a
file, so there is nothing for a checker to inspect. A run that silently drops
the block and one that emits it correctly are indistinguishable from here.

That is a real and un-mitigated gap, not a formality. The nearest thing that
would close it is a checker that EMITS the block mechanically from run
artifacts, which makes it inspectable - specified as the CI anchor in the
[#953 forced-claim prototype][953] and deliberately not built there or here.
Until something like it exists, this contract is enforceable at its pointer and
unenforced in its body.

[714]: https://github.com/cooneycw/claude-power-pack/issues/714
[953]: ../research/forced-claim-prototype-2026-09-15.md
