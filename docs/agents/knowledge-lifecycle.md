# Knowledge Lifecycle

Specifications are temporary coordination artifacts. They remain authoritative
while requirements are unresolved or implementation is in flight. After
delivery, every durable fact graduates to the narrowest maintained source that
can enforce or explain it. A completed spec must not become a second, drifting
description of the shipped system.

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
