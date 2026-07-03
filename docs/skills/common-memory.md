# Common Memory - Friction-Knowledge Ledger (harness-neutral)

The canonical routine for populating and consulting the shared CPP common-memory
store. Works from **any** agent harness (Claude Code, Codex, plain shell) because
the entire interface is one command: `cpp-memory` (or `python -m lib.cpp_memory`).

The store consolidates *portable* CPP learnings / infra traps across the VM fleet
(bucket-2-plus) plus a dedup/rejection ledger, so no VM re-proposes an
already-rejected fix. It is **consult-not-push, fail-open, human-confirmed**: it
never distributes config, never auto-applies permission fixes, and degrades to a
local `.claude/learnings.md` if the store is unreachable.

## Scope: what goes where (bucket rules)

| Learning | fix_scope | Destination |
|----------|-----------|-------------|
| Portable knowledge / infra trap (reusable across VMs and repos) | `knowledge` | **Shared store** |
| A repo file change (Makefile target, hook, project `settings.json`, doc) | `repo_file` | **git** (local note only) |
| A per-machine `permissions.allow` entry | `permission` | **This machine only** (local note; never shared) |

The client **refuses** to record anything but portable learnings in the shared
store, from every harness.

## The interface

```bash
cpp-memory ping                                   # reachability (JSON)
cpp-memory query  --fingerprint <fp>              # dedup + rejected-here check
cpp-memory query  --class knowledge --limit 20    # browse
cpp-memory record --class knowledge --scope knowledge \
    --title "<stable title>" --body "<reusable knowledge>" \
    --fix "<optional remediation>" --confidence 0.8 --repo "<repo-name>"
cpp-memory record --local-only --class permission --scope permission ...  # stays local
cpp-memory apply  --fingerprint <fp> --actor <user> --note "<what changed>"
cpp-memory reject --fingerprint <fp> --actor <user> --note "<why not>"     # stops re-proposal
```

`cpp-memory` is a thin wrapper: it self-locates the CPP repo, sets `PYTHONPATH`,
and runs via `uv` (fetching psycopg on demand) or system python3. If neither the
store nor a driver is available, every write falls back to a local note - the
routine never blocks.

## Routine (run after a session / flow run)

1. **Reachability.** `cpp-memory ping`. If `reachable:false`, continue in degraded
   mode (writes land in `.claude/learnings.md`); note it in the report.
2. **Gather friction signals** from the session: permission prompts, quality-gate
   failures/retries, red output narrated-past, manual interventions/corrections,
   infra traps discovered, and portable knowledge learned.
3. **Classify** each into `(friction_class, fix_scope)` per the bucket rules.
4. **Consult before proposing.** For each portable candidate,
   `cpp-memory query --fingerprint <fp>`; skip anything with `rejected_here:true`.
   (`record` echoes the fingerprint; it is deterministic over
   `(friction_class, title)`.)
5. **Confirm, then record.** Portable -> `cpp-memory record ...` (shared, auto
   local-fallback). Non-portable -> `--local-only` note **and** propose the real
   fix in its proper home (git edit / per-machine `settings.json`); never share.
6. **Bookkeeping.** When a stored learning is acted on here, `cpp-memory apply` or
   `reject` so other runs and VMs see the outcome.

## DSN / federation

The DSN resolves fail-open in this order: `CPP_MEMORIES_DSN` env ->
`~/.config/claude-power-pack/secrets/cpp-memories.dsn` ->
AWS SM `essent-ai` key `CPP_MEMORIES_DSN`. The AWS tier is the fleet-federation
mechanism - any VM with `essent-ai` access self-configures with no local file.
Reference the store host by its **Tailscale** address so Tailscale-only VMs reach
it. Provision / re-provision with `scripts/memories-db-setup.sh` (idempotent;
`CPP_MEM_PG_MAJOR` selects the Postgres major, default 17).

## Install (both harnesses)

```bash
bash scripts/install-memory-harness.sh
```

Puts `cpp-memory` on PATH and installs the Codex `/cpp-memory` prompt. Claude
Code discovers `/self-improvement:memory` from the repo automatically.
