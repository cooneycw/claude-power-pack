# Issue Contract

An issue is a contract between whoever wants an outcome and whoever delivers it.
The contract fails when everything in it reads as an order. A sentence naming the
goal, a sentence guessing at a design, and a sentence recording an assumption look
identical on the page, so an implementer builds the guess as faithfully as the goal
and has no way to tell which sentences are load-bearing.

This document is the canonical definition of that contract for this repository.
Other surfaces point here; they do not restate it.

## The five distinctions

| Distinction | What it is | How a reader treats it |
|-------------|-----------|------------------------|
| Outcome | The observable state to reach, and why it matters | Binding. Preserve it. |
| Constraint | A boundary the solution must respect, with the rationale behind it | Binding. Challengeable on evidence, never silently dropped. |
| Acceptance | Observable examples showing the outcome was reached | Binding as the evidence standard. |
| Proposed approach | A hypothesis about how to get there | Revisable. Substitute a better one and say so. |
| Assumption | Something believed but unverified | Not binding. An invitation to check. |

**These are distinctions a reader must be able to make, not five mandatory headings
or fields.** A two-sentence issue satisfies this contract when the distinctions are
legible from the sentences themselves. Do not invent an assumption or a proposed
approach to fill a slot: absence is a legitimate answer, and for a routine fix it is
usually the honest one. A form that forces a reporter to prescribe a design
manufactures exactly the blur this contract removes.

## Telling an outcome from a proposal

Substitute a different mechanism. If the sentence still says what the requester
wants, it was an outcome; if it becomes meaningless, it was a proposal.

| Written as | Reads as | Because |
|------------|----------|---------|
| "Remain responsive while processing continues" | Outcome | Survives swapping the queue for threads, streaming, or a smaller payload. |
| "Use a background queue" | Proposed approach | Names a mechanism. Swap it and nothing of the request is left. |
| "Must not add a new runtime dependency" | Constraint | A boundary on any mechanism, not a mechanism. |
| "The cache is probably the bottleneck" | Assumption | Hedged, unverified, and the work does not depend on it being true. |

**The heuristic identifies candidates; it never demotes an explicit requirement.** A
named mechanism can itself be a constraint: "use PostgreSQL, because this has to
integrate with the database we already run and support" names a mechanism and is
binding all the same. Naming a mechanism is what makes a sentence a candidate for
being a proposal, not what makes it one. When a sentence is written as a requirement,
or carries a rationale explaining why that mechanism specifically, it is a constraint
and the substitution test does not apply to it.

An implementer who replaces a proposed approach owes the requester the reason, not
permission - but that holds only while the substitution preserves the agreed outcome
and every constraint, and stays inside the authority and tool permissions the
implementer already has. A better implementation is not authorization to cross a
security, cost, or compatibility boundary: that is a constraint change, and it needs
evidence and agreement before it is made, not an explanation afterwards.

## Constraints and bindingness

A constraint is binding. Its rationale is not what makes it binding; the rationale is
what makes it **challengeable on the merits** rather than by preference.

- **A constraint with no recorded rationale is still a constraint.** Older issues are
  full of them. Preserve it provisionally, treat it as binding, investigate what it
  was protecting, and surface the ambiguity to whoever can answer. Do not downgrade
  it to a proposal because its reason is missing from the page.
- **Reclassifying a constraint requires evidence and agreement.** Evidence that the
  rationale does not hold here, plus whatever agreement the project's authority model
  requires for a consequential change.
- **Record the reclassification where the decision is reviewed** - the plan presented
  at the approval gate, the PR description, or the completion ledger's revisions line.
  Silent reclassification is the failure this section exists to prevent: an agent may
  argue a constraint away, but never quietly treat it as optional.

## How much document

| Tier | Shape of the work | What the contract lives in |
|------|-------------------|----------------------------|
| Tier 1 (surgical) | 1-3 files, single concern | A short issue body. No spec, plan, or tasks files. |
| Tier 2 (considered) | 4-10 files, new model or endpoint | A short issue body. A spec only if uncertainty or coordination warrants one. |
| Tier 3 (architectural) | New subsystem, security boundary, multi-issue effort | An authoritative spec under `.specify/specs/`; the issue links it. |

Tiers are defined in `.specify/memory/constitution.md`. When work is specified,
**the issue references the spec and the sections that govern it; it does not copy
them.** A copied spec becomes a second, drifting description of the same
requirement - the same failure the
[knowledge lifecycle](knowledge-lifecycle.md) prevents after delivery.

**The one exception is a machine-generated cache, and it is narrow.** An issue
created by `scripts/speckit-tasks-to-issues.sh` carries a `speckit-context` block:
a bounded extract of the task's declared context, produced by
`scripts/speckit-context.py`. That is a CACHE, not a second authority, and it earns
the exception only by staying all four of these:

- **Bounded.** Only what the task's own `[USn]` tag and the spec's declared
  requirement-to-story mapping select, capped in size. Never the whole spec.
- **Sourced.** It names the authoritative file and the sections to read there, and
  says that the source governs where the two differ.
- **Drift-detectable.** It records digests of the mapped sections and of the source
  file, so a reader can be told the bytes changed rather than discovering it later.
- **Honest about its gaps.** An unresolved mapping or a capped extract is stated as
  incomplete context to resolve, never as an absence of constraints.

A human writing an issue still does not copy the spec: this exception exists because
a generated issue has no author to make the judgement, not because copying became
acceptable.

**Existing issues remain usable.** Read an older issue by inferring these
distinctions from what it says, and surface material ambiguity instead of guessing.
There is no migration: do not reformat issues into this shape, and do not reject work
because its issue predates this document.

## Worked examples

### A routine bug, Tier 1

> Login redirects in a loop after a session expires; the user cannot get back in
> without clearing cookies. Expired sessions should land on `/login` with the
> original destination preserved. `handle_login()` looks like the place, though the
> redirect may be set further up.

Outcome and acceptance are in the first two sentences. `handle_login()` is a proposed
approach and the hedge marks it; an implementer who finds the bug in the router fixes
it there and says so. Nothing is missing from this issue: it has no constraints and no
assumptions worth recording, and inventing some would add nothing.

### A feature with a prescriptive proposed solution, Tier 2

> Exports of more than a few thousand rows block the UI until they finish. Use a
> background queue so the page stays responsive, and show progress. Must not add a
> new infrastructure service - we run one container and intend to keep it that way.

"Stays responsive while the export runs, with visible progress" is the outcome. "Use a
background queue" is a proposal, and the constraint rules out the queue services that
would otherwise be the obvious answer. An implementer who delivers responsiveness with
an in-process worker and a polled progress endpoint has met the contract; the report
says the queue was not used and why. An implementer who adds a broker has violated a
constraint whose rationale is on the page, and needs evidence and agreement first.

### Architectural work, Tier 3

> Implements the tenant-isolation boundary. Authoritative spec:
> `.specify/specs/tenant-isolation/spec.md`, sections "Trust boundary" and
> "Migration order". This issue covers the query-layer half only; the storage half
> is #124. Acceptance is the spec's US2 criteria.

The issue is a pointer with a scope. The spec stays the source of truth, so amending
it does not leave a stale copy in the tracker.

### A legacy constraint with no recorded rationale

> (filed eighteen months ago) Add pagination to the admin list. Do not use the ORM's
> `.count()` here.

The prohibition has no stated reason and the author is long gone. It is still binding.
Preserve it, implement pagination without `.count()`, and surface the ambiguity: "this
issue forbids `.count()` and does not say why - a windowed count is slower here, so
the reason matters. Was this about the lock it takes on the audit table?" If
investigation shows the rationale cannot apply - the table it protected no longer
exists - that is evidence, and the reclassification is recorded in the plan and the
PR. What is never correct is dropping the line because it looks arbitrary.

## Surfaces that route here

`.specify/memory/constitution.md` (P3, P4, and the workflow phases),
`.claude/commands/spec/help.md`, `.claude/commands/github/issue-create.md`,
`.claude/commands/evaluate/issue.md`, `.claude/skills/spec-driven-dev/SKILL.md`,
`docs/skills/spec-driven-dev.md`, and the issue forms under `.github/ISSUE_TEMPLATE/`.

`tests/test_issue_contract_routing.py` checks that those named routes still resolve
and that no retired command reappears as a live instruction on them. It is a fixed
list that fails loudly when one of those surfaces drifts; it does not discover new
surfaces, and it cannot judge whether a constraint was handled correctly. That
judgment is what the worked examples above are for.
