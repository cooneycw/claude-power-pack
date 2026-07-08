# Contract: Shared Friction-Knowledge Ledger (multi-harness)

Status: stable (issue #557). Consumers: claude-power-pack (this repo) and
codex-power-pack (epic cooneycw/codex-power-pack#67, "Codex friction telemetry
writing to the shared fleet ledger", its epic E writer).

This is the **write/read contract** for the shared Postgres friction ledger so a
second harness (Codex) can feed the same store Claude Code already feeds, with a
stable target that does not depend on CPP-internal implementation details. For
the operator-facing routine (backends, DSN resolution, the consult/record loop)
see `docs/skills/common-memory.md`; this document is the machine contract the
two repos agree on.

## What the ledger is

A fail-open, consult-not-push, human-confirmed store of **portable** CPP
learnings / infra traps across the VM fleet, plus a dedup + rejection ledger so
no machine (or harness) re-proposes an already-rejected fix. It never
distributes config and never auto-applies permission fixes. If it is unreachable,
every write degrades to a local `.claude/learnings.md` note and never blocks a run.

## The write target (stable interface)

Both harnesses write through the **`cpp-memory` CLI** (a thin, harness-neutral
wrapper over `python -m lib.cpp_memory`). This is the contract surface; the SQL
schema below is informative, but the CLI is what a writer should target.

```bash
cpp-memory record \
    --class <knowledge|infra_trap|...> --scope <knowledge|repo_file|permission> \
    --title "<stable title>" --body "<reusable knowledge>" \
    --fix "<optional remediation>" --confidence 0.8 \
    --repo "<source-repo-name>" \
    --harness <claude|codex|shell>
```

- **`--harness`** (issue #557) tags the resulting *sighting* with the producing
  harness. A writer SHOULD pass it explicitly; when omitted it is resolved from
  `CPP_HARNESS`, then auto-detected Claude Code (`CLAUDECODE`), else left NULL.
- **Codex writer (epic E):** pass `--harness codex` OR export `CPP_HARNESS=codex`
  once for the process. That is the entire integration on the tag; everything
  else (dedup, fail-open, bucket-2 guard) is handled by the CLI unchanged.
- The command echoes JSON including `"harness": "<resolved>"`, `"fingerprint"`,
  and `"stored"` (`shared` | `md` | `local-fallback`).

### Canonical harness values

| Value | Producer |
|-------|----------|
| `claude` | Claude Code (CPP retro / memory routines) |
| `codex` | Codex (codex-power-pack telemetry writer) |
| `shell` | plain shell / other scripted caller |

Values are a **convention**, folded to lower-case, NOT enforced by a DB `CHECK`
constraint: an unrecognized harness is still recorded (forward-compatible), and
a NULL/omitted harness is valid (it matches every pre-#557 row). Resolution
lives in `lib/cpp_memory/harness.py` (`resolve_harness`).

## Reading / attribution

```bash
cpp-memory query --fingerprint <fp>
```

returns, among other fields:

```json
{
  "known": true,
  "sightings": 4,
  "sightings_by_harness": {"claude": 3, "codex": 1},
  "rejected_here": false,
  "has_issue": false
}
```

`sightings_by_harness` is the "claude vs codex" split; unattributed (NULL)
sightings bucket under `"unknown"` so the counts always sum to `sightings`.

## Schema (informative)

The tag lives on `sightings` (the per-occurrence provenance rows), alongside the
existing `source_vm` / `source_repo`. It is deliberately NOT on `learnings`: a
single deduplicated learning can be sighted by both harnesses, so harness is a
property of the *occurrence*, not the knowledge.

```sql
-- sightings: one row per "a VM/harness re-encountered this learning"
CREATE TABLE sightings (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learning_id  BIGINT NOT NULL REFERENCES learnings (id) ON DELETE CASCADE,
    source_vm    TEXT NOT NULL,
    source_repo  TEXT,
    harness      TEXT,          -- #557: 'claude' | 'codex' | 'shell'; NULL = unattributed
    seen_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX sightings_harness_idx ON sightings (harness);
```

Canonical DDL: `lib/cpp_memory/sql/schema.sql` (idempotent; the `harness` column
is added with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, so an existing fleet
store upgrades in place). Apply/refresh with `cpp-memory init-db`.

## Invariants a writer can rely on

1. **Fail-open.** Store unreachable or driver missing -> the write returns a
   local-fallback note, never an error. A writer never has to handle store outage
   specially.
2. **Bucket-2 share guard.** The federated store REFUSES non-portable learnings
   (permission / repo_file fixes): those stay per-machine / in git. Only portable
   knowledge / infra traps enter the shared store. This guard raises for a
   non-portable record even while the store is down, so it is a client-side
   contract, not a server check.
3. **Dedup by fingerprint.** `fingerprint = sha256(class | normalized-title)`.
   Re-recording the same learning upserts (no fork) and adds a fresh sighting;
   the harness tag therefore accumulates per occurrence, not per learning.
4. **Backward compatible.** Adding `--harness` / the `harness` column changes no
   existing behavior; omitting the tag reproduces pre-#557 output with the tag
   NULL / `"unknown"`.

## Versioning

This contract is additive-only for the harness dimension. A breaking change to
the CLI record interface or the sightings columns MUST bump a note here and be
coordinated across both repos before either relies on it.

## See also

- `docs/skills/common-memory.md` - operator routine, backends (md|local-pg|remote-pg), DSN.
- `lib/cpp_memory/harness.py` - `resolve_harness` (the resolution order above).
- `lib/cpp_memory/sql/schema.sql` - canonical DDL.
- codex-power-pack epic cooneycw/codex-power-pack#67 - the Codex-side consumer.
