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
cpp-memory record ... --emit-issue-candidate                              # + issue_candidate block (#463)
cpp-memory link-issue --fingerprint <fp> --url <github-issue-url>         # record the filed issue
cpp-memory apply  --fingerprint <fp> --actor <user> --note "<what changed>"
cpp-memory reject --fingerprint <fp> --actor <user> --note "<why not>"     # stops re-proposal
```

`cpp-memory` is a thin wrapper: it self-locates the CPP repo, sets `PYTHONPATH`,
and runs via `uv` (fetching psycopg on demand) or system python3. If neither the
store nor a driver is available, every write falls back to a local note - the
routine never blocks.

## Backends (the mini-tier: md | local-pg | remote-pg)

The store is a **pluggable backend** (issue #472), chosen at `/cpp:init` time
(step 8d) or via `CPP_MEMORIES_BACKEND`. It is **md = best-effort local,
pg = full-fidelity** - not the same feature three ways.

| Tier | Backend | Dedup fidelity | Federation (cross-VM?) | Needs |
|------|---------|----------------|------------------------|-------|
| i | `md` | best-effort (parse `learnings.md`) | **none** - local box only | nothing |
| ii | `local-pg` | full (SQL fingerprint) | **none** - single box | Docker (`postgres:17`) |
| iii | `remote-pg` | full (SQL fingerprint) | **fleet** - shared across VMs | Tailscale DSN |

**Federation is the property that differs** and it is surfaced everywhere
(`cpp-memory ping` reports `backend` + `federation`). Pick a pg tier only if you
need the specific fidelity; pick **iii** if you want fleet sharing. Tiers i and
ii collapse the "global" `is_known` / `rejected_here` to this box.

Per-tier semantics of the four operations:

| Operation | md (i) | local-pg (ii) | remote-pg (iii) |
|-----------|--------|---------------|-----------------|
| **consult** (`is_known`) | parse `learnings.md` for the fingerprint; local only | SQL lookup; local only | SQL lookup; **fleet-wide** |
| **dedup** (`record`) | best-effort: an already-present fingerprint is a no-op (no fork); no sighting ledger | full: upsert on unique fingerprint + a sighting row | full: upsert + sighting (the "N machines hit this" signal) |
| **reject** (`reject`/`rejected_here`) | appended to `.claude/learnings.rejected.jsonl` sidecar, keyed by `(fingerprint, vm)`; local only | `applications` row; per-VM | `applications` row; **per-VM** (reject is per-VM even here; `is_known` is global) |
| **issue bridge** (`link_issue`, #463) | **not tracked** (best-effort: `is_known` reports `issue_url=None`, so the retro re-proposes, human-confirmed) | full `issue_url` first-write-wins | full `issue_url` first-write-wins |

The md backend also accepts **non-portable** notes (permission / repo_file) - it
is the local ledger, so that is where they belong. The bucket-2 **share guard**
(refuse non-portable) applies only to the federated pg store, and the routine's
guard below keeps them local regardless of backend.

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
7. **Promote to work (learnings->issue bridge, #463).** If a portable learning is
   **actionable** (names a concrete fix), record it with `--emit-issue-candidate`;
   when `issue_candidate.should_file` is true, confirm with the user, `gh issue
   create` in the candidate's repo using `issue_candidate.body` (it embeds a
   `<!-- cpp-learning: <fp> -->` marker), then `cpp-memory link-issue` the URL back.
   Route by where the FIX lands, not where the friction surfaced: a fix to a skill
   that lives in its own standalone repo (an extracted plugin) files there.
   Only portable + actionable learnings become issues; dedup is the `issue_url`
   column (first-write-wins) plus the marker; fail-open if `gh` is unavailable.

## Backend selection & DSN / federation

**Backend** resolves in this order: `CPP_MEMORIES_BACKEND` env ->
`~/.config/claude-power-pack/secrets/cpp-memories.backend` -> inferred (a
resolvable DSN implies `remote-pg`, today's fleet default; no DSN implies `md`).
`/cpp:init` step 8d writes the backend file for you.

**DSN** (pg tiers only) resolves fail-open: `CPP_MEMORIES_DSN` env ->
`~/.config/claude-power-pack/secrets/cpp-memories.dsn` ->
AWS SM `essent-ai` key `CPP_MEMORIES_DSN`. The AWS tier is the fleet-federation
mechanism for **remote-pg** - any VM with `essent-ai` access self-configures with
no local file. Reference the store host by its **Tailscale** address so
Tailscale-only VMs reach it.

- **remote-pg (iii):** provision / re-provision the fleet store with
  `scripts/memories-db-setup.sh` (idempotent; `CPP_MEM_PG_MAJOR` selects the
  Postgres major, default 17).
- **local-pg (ii):** `docker compose -f lib/cpp_memory/docker-compose.yml up -d`
  (stock `postgres:17`, host port 5433; default DSN
  `postgresql://cpp_memory:cpp_memory@127.0.0.1:5433/cpp_memory`). See
  `lib/cpp_memory/NOTICE.md` for image attribution.
- **md (i):** no DSN, no container - the ledger is `<repo>/.claude/learnings.md`
  plus the `.claude/learnings.rejected.jsonl` reject sidecar.

## Install (both harnesses)

```bash
bash scripts/install-memory-harness.sh
```

Puts `cpp-memory` on PATH and installs the Codex `/cpp-memory` prompt. Claude
Code discovers `/self-improvement:memory` from the repo automatically.
