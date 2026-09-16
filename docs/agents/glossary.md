# Glossary

Three defined terms, each with the one-line test for whether something is one.
This file exists so that issues, ADRs and review surfaces can use the words
precisely; it defines vocabulary and nothing else. It is not a tier system, not
a process, and not a checker (issue #932; the bound is recorded in
[ADR 0008](../decisions/0008-instrument-negative-control-bound.md)).

## instrument

**Anything whose output is read as evidence.** A test, a gate, a check, a
probe, a preflight, a drift check, a monitor, a report - the kind does not
matter; what matters is that some decision treats its output as a fact about
the world rather than re-establishing that fact itself.

The test: *is there a decision that acts on this thing's verdict?* If nothing
acts on it, it is a record, a filter, an installer or a renderer, not an
instrument. `friction-log.sh` writes a ledger nobody decides on without
reading it - not an instrument. `flow-finish-gate.sh` prints `ok` and the
commit proceeds - an instrument.

An instrument that cannot report the other verdict is not evidence; a green
from a blind instrument and a green from a working one are the same bytes.
The global Negative Control directive requires a committed case that makes an
instrument report the other verdict. **That requirement is bounded**, because
applied to every test function in the tree it is unaffordable, and an
unaffordable rule is applied to whatever is in front of you and skipped
everywhere else:

> An instrument needs a committed negative control when its verdict is
> consumed by a decision that will not independently re-derive the fact.

- A unit test whose failure the surrounding suite would catch does not need
  one. Its green is not individually load-bearing; the suite's is. Whether the
  suite as a whole discriminates is a mutation-testing question, not a
  per-test one.
- A gate that lets work *through* - a finish gate, a preflight, a drift check,
  `make verify` itself - does need one. Nothing downstream re-derives what it
  asserted; that is the entire reason it exists.
- A check whose green is read by a **different session or a different repo**
  always needs one, because the reader cannot see the conditions that produced
  it.

The bound narrows *which instruments need a committed case*. It does not touch
the regression-test rule (a regression test must fail on the pre-fix code; that
costs one run, not a committed case), and it does not say an instrument
outside the bound may be blind - only that proving it is not blind is the
suite's job rather than a per-instrument obligation. The enumeration of what
the bound captures in this repository, with its count, is in ADR 0008.

## harness

**The system of controls around the model**: context files, tools,
permissions, sandboxes, gates, feedback loops, delegation lanes, the CI
pipeline. In this sense CPP *is* a harness; a spec, a skill or a single gate is
one control inside it.

The test: *does it name the whole apparatus, or one artifact in it?* If the
sentence still makes sense with "the CPP tooling as a whole" substituted, it
means the harness. If it names a document, a script or a check, it means a
control, and should say which.

**This word is already taken in this repo for a narrower, older meaning.**
`lib/cpp_memory/harness.py` and `scripts/install-memory-harness.sh` use
*harness* for **which agent CLI produced a friction signal** - the ledger's
`harness` tag (`claude` | `codex` | `shell`, issues #557 / #562), set by
`CPP_HARNESS` or `--harness`. That sense is a provenance label, not a system.
Both senses stay: the ledger tag is a stable write contract for
codex-power-pack and is not renamed. A sentence that could be read either way
must say which it means - "the friction ledger's harness tag" versus "the
harness" - rather than overload the word silently.

**`spec` is not a synonym and is not renamed.** A spec names an artifact (the
durable statement of intent for a piece of work); a harness names a system. A
repo-wide rename of `spec` to `harness` would leave no word for the document,
and it has no red case - no input makes a rename report "this was a mistake" -
so by the directive above it is a change nobody is entitled to make at scale.
`/spec:*`, `.specify/`, and the tiering in `spec/help.md` are unchanged.

## counter-model

**The model that did not implement the change under review.** Stated as a
property of the review, not as a tool name, so that whichever lane implemented
- Claude, Codex, Qwen, Gemma - the counter-model is whichever other one
reviews, and a new lane inherits the term without an edit here.

The test: *did this model write the diff it is reviewing?* If yes, it is the
implementer reviewing itself, whatever it is called. If no, it is the
counter-model. A Claude session reviewing a Codex diff is the counter-model in
codex-power-pack; a Codex review of a Claude diff (`/codex:code_review`, run at
`/flow:auto` Step 6 item 1) is the counter-model here. The reciprocal stage in
codex-power-pack is native to that repo and no CPP edit reaches it
(cooneycw/codex-power-pack#228).

Making the counter-model stage default and giving it its own red case is
issue #934 (ADR 0007), not this glossary.

## Surfaces that route here

- [ADR 0008](../decisions/0008-instrument-negative-control-bound.md) - the
  bound, the carve-out, the escalation, and the enumeration that tests them.
- [The detector contracts](detector-contracts.md) - the two questions asked of
  any instrument in a diff; they apply to instruments inside and outside the
  bound alike.
- The Negative Control section of the host's global directive
  (`~/.claude/CLAUDE.md`) carries the bound in the same words. It is
  host-managed and outside this repository; ADR 0008 quotes the edit.
