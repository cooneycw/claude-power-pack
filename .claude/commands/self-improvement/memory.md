# Self-Improvement: Common Memory - Populate the Friction-Knowledge Ledger

Harvest *portable* learnings from the just-finished session into the shared CPP
common-memory store (bucket-2-plus), consulting the dedup/rejection ledger so
nothing already-recorded or already-rejected is re-proposed.

This is the populate/codify half of the grill-me cycle (#426). It is
**consult-not-push, fail-open, and human-confirmed**: it never distributes
config, never auto-applies permission fixes, and degrades to a local
`.claude/learnings.md` if the store is unreachable.

## Scope: what goes where (bucket rules)

| Learning | fix_scope | Destination |
|----------|-----------|-------------|
| Portable knowledge / infra trap (reusable across VMs and repos) | `knowledge` | **Shared store** |
| A repo file change (Makefile target, hook, project `settings.json`, CLAUDE.md directive) | `repo_file` | **git** (local note only) |
| A per-machine `permissions.allow` entry | `permission` | **This machine only** (local note; never shared) |

Only `knowledge` / `infra_trap` learnings enter the shared store. The client
**refuses** to record anything else there.

## Instructions

When the user invokes `/self-improvement:memory` (or the grill-me cycle calls
this routine), perform these steps.

### Step 1: Reachability (fail-open)

```bash
python -m lib.cpp_memory ping
```

- `{"reachable": true}` -> shared store is available; proceed normally.
- `{"reachable": false}` -> **do not stop**. Continue, but every recorded
  learning will land in `.claude/learnings.md` on this machine. Note the
  degraded mode in the final report.

### Step 2: Gather friction signals from the session

Review the current conversation for:

- **permission prompts** the user had to approve (each Bash/tool approval)
- **quality-gate failures / retries** (make verify, lint, tests, CI)
- **red output that was narrated past** instead of resolved
- **manual user interventions / corrections** mid-run
- **infra traps** discovered (host, port, auth, version quirks)
- **portable knowledge** learned that would help on the next run, anywhere

### Step 3: Classify and gate

For each candidate, assign `friction_class` (`permission`, `gate_failure`,
`red_output`, `manual_intervention`, `infra_trap`, `knowledge`) and `fix_scope`
(`repo_file`, `permission`, `knowledge`) per the bucket rules above.

### Step 4: Consult the ledger before proposing (dedup + rejection)

For every **portable** candidate, check whether it is already known and whether
this VM already rejected it:

```bash
python -m lib.cpp_memory query --fingerprint "<fingerprint>"
```

The fingerprint is deterministic from `(friction_class, title)`; the `record`
command returns it, or compute it from `lib.cpp_memory.fingerprint`. Skip any
candidate where `rejected_here` is `true` (do not re-nag).

### Step 5: Confirm, then record

Present the surviving candidates to the user. On confirmation:

- **Portable** -> shared store (falls back to local automatically if down):

  ```bash
  python -m lib.cpp_memory record \
    --class knowledge --scope knowledge \
    --title "<short stable title>" \
    --body "<the reusable knowledge / trap>" \
    --fix "<optional remediation text>" \
    --confidence 0.8 --repo "$(basename "$(git rev-parse --show-toplevel)")"
  ```

- **Non-portable** (permission / repo_file) -> local note only, plus propose the
  real fix in its proper home (git edit for `repo_file`, per-machine
  `settings.json` for `permission`). Never send these to the shared store:

  ```bash
  python -m lib.cpp_memory record --local-only \
    --class permission --scope permission \
    --title "<...>" --body "<...>" --repo "$(git rev-parse --show-toplevel)"
  ```

### Step 6: Apply / reject bookkeeping (optional)

When the user acts on a previously-stored learning on this machine, record it so
other runs and VMs can see the outcome:

```bash
python -m lib.cpp_memory apply  --fingerprint "<fp>" --actor "<user>" --note "<what changed>"
python -m lib.cpp_memory reject --fingerprint "<fp>" --actor "<user>" --note "<why not>"
```

`reject` is what stops a fix from being re-proposed on this VM.

## Output Format

```
Common Memory: Friction Retro
=============================
Store:            reachable | DEGRADED (local .claude/learnings.md)
Signals found:    N  (permission M / gate G / red R / manual U / knowledge K)
Portable -> shared:  P recorded  (D skipped as duplicates, X as rejected-here)
Non-portable -> local/git: L
```

## Notes

- The store is Postgres on a dedicated lab VM; the DSN resolves from
  `CPP_MEMORIES_DSN` env -> local `~/.config/claude-power-pack/secrets/cpp-memories.dsn`
  -> AWS SM `essent-ai` key `CPP_MEMORIES_DSN`. All resolution is fail-open.
- Reference the store host by its Tailscale address so Tailscale-only VMs
  reach it too.
- Provision / re-provision the store with `scripts/memories-db-setup.sh`
  (idempotent; `CPP_MEM_PG_MAJOR` selects the Postgres major, default 17).
