# Knowledge Lifecycle

Specifications are temporary coordination artifacts. They remain authoritative
while requirements are unresolved or implementation is in flight. After
delivery, every durable fact graduates to the narrowest maintained source that
can enforce or explain it. A completed spec must not become a second, drifting
description of the shipped system.

**Distribution is not a second home.** This document is the one writable
authority for the policy below. `scripts/codex-skill-sync.py` bundles a
byte-identical copy of it into generated skills so the link a command body
publishes still resolves once that skill is installed with no claude-power-pack
checkout above it. Those copies are distribution of this file, never a place to
edit: change this document and run `make codex-skills`. The locality check
verifies each copy against this source rather than trusting its path, so an
edited or unowned copy is still reported as duplicated policy.

## Durable homes

| Knowledge in the completed spec | Durable home |
|---------------------------------|--------------|
| Observable behavior and acceptance criteria | Production code plus behavioral tests |
| Types, interfaces, data shape, and machine contracts | Types, schemas, validators, and API definitions |
| Non-obvious local intent or invariant | A nearby comment that explains why, never a restatement of what the code does |
| Consequential, hard-to-reverse trade-off and rejected alternatives | ADR |
| Canonical domain language | `CONTEXT.md` or the configured domain glossary |
| Operational procedure, recovery, or deployment behavior | Runbook and executable checks |
| Public or cross-team contract | Maintained user/API/interface documentation |
| Unimplemented or deliberately deferred requirement | Linked open issue or explicit rejection record |
| A decision that was taken, and what it was taken against | The record of that decision - it does not graduate; see below |

## Records of decisions do not graduate

Everything in the table above is knowledge ABOUT THE SYSTEM, and it graduates to
the narrowest maintained source that can enforce or explain it. A record of a
DECISION is a different kind of thing and the graduation process does not apply
to it.

A `/flow:auto` plan record (`docs/flow-runs/issue-<N>.md`, issue #1080), an
as-read issue snapshot (`docs/flow-runs/issue-<N>.as-read.md`, issue #1081) and a
counter-model receipt (`docs/measurements/counter-model/*.json`, issue #934) are
all of this kind. The as-read snapshot is the clearest case: it states what a run
READ at a moment, which stays true however far the issue moves afterwards - and
the whole point of keeping it is to make that movement visible. Each states what was agreed, or what was reviewed, at a
particular moment and against a particular SHA. That claim does not go stale,
because it is not a claim about how the system behaves now - it is a claim about
what happened, and it stays true.

So:

- **They are never a durable home.** If a plan record contains a fact that
  matters after delivery - an invariant, a rejected alternative, a contract -
  that fact graduates to code, tests, or an ADR like any other. The record keeps
  its own copy as history; the durable home is elsewhere, and the two are not
  expected to agree forever.
- **They are never read as current.** A plan record describes intent formed
  BEFORE the code existed. Read as a description of the shipped system it is
  wrong by construction, which is why each one carries its base SHA and says so
  in its own header.
- **They are not rewritten to stay accurate** (owner ruling, #1048: annotate, do
  not rewrite). A corpus edited to look correct destroys the only thing it was
  keeping - the evidence of what was actually believed at the time.

The risk this section exists to bound is the accumulating one: a directory of
committed statements about the system, written before the code, is a good way to
build exactly the "second, drifting description" this document opens by
forbidding. The answer is not to delete them but to be explicit that they are
history rather than description, and that nothing may cite one as the current
state.

## Graduation process

Graduation is a lifecycle-boundary decision, not routine cleanup. Run
`scripts/knowledge-graduation-check.py` with the completed spec directory, its
explicit mapping record, and the tracker or PR URL where the decision was
reviewed. The mapping record must identify every acceptance criterion, its
durable-home category, and existing artifacts that own it. It must also resolve
every task through a closed issue or an explicit rejection record.

The check fails closed when an acceptance criterion is missing, a mapped local
artifact does not exist, a task is unresolved, review evidence is absent, or an
independently valuable spec is proposed for deletion. Only after a successful
`graduated` decision may the spec be removed from the current tree. Git and the
tracker preserve provenance; `.specify/graduation-ledger.json` tells
`project:next` that the absence is intentional.

A minimal mapping record is JSON:

```json
{
  "version": 1,
  "spec_slug": "completed-feature",
  "state": "graduated",
  "independent_value": "none",
  "acceptance_criteria": [
    {
      "criterion": "The command writes a deterministic result.",
      "durable_home": "code-tests",
      "artifacts": ["scripts/example.py", "tests/test_example.py"]
    }
  ],
  "tasks": [
    {
      "task_id": "T001",
      "resolution": "closed-issue",
      "evidence_url": "https://github.com/owner/repo/issues/1"
    }
  ]
}
```

Allowed `durable_home` values are `code-tests`, `types-schemas`,
`local-intent-comment`, `adr`, `domain-glossary`, `runbook-checks`,
`maintained-docs`, and `issue-or-rejection`. Artifact values are repository
paths or `https://` evidence links. `code-tests` requires both a production
artifact and a test artifact.

`independent_value` is required and is one of `none`, `contractual`,
`regulatory`, `compliance`, `public-protocol`, or `cross-team`. A value other
than `none` must use `state: retained` and name an `owner`. Retention still
requires complete acceptance and task mapping, but the maintained spec remains
in the tree as an owned contract. The ledger records only `graduated` and
`retained`; `active` and `stale` are computed by `project:next`.

Example invocation:

```bash
python3 scripts/knowledge-graduation-check.py \
  .specify/specs/completed-feature \
  --mapping .specify/specs/completed-feature/graduation.json \
  --evidence-url https://github.com/owner/repo/pull/123
```

The checker has no network dependency. Callers provide reviewed tracker URLs;
the checker verifies the local spec, tasks, mapping, artifacts, and ledger
transaction.
