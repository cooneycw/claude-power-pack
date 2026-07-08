Populate and consult the shared CPP common-memory ledger: harvest *portable*
learnings / infra traps from this session into the fleet-wide store, consulting
the dedup/rejection ledger so nothing already-recorded or already-rejected is
re-proposed.

This is consult-not-push, fail-open, and human-confirmed. It never distributes
config and never auto-applies permission fixes. The whole interface is the
`cpp-memory` command (install once with `bash scripts/install-memory-harness.sh`
from the claude-power-pack repo; falls back to
`uv run --no-project --python 3.11 --with 'psycopg[binary]>=3.1' -- python -m lib.cpp_memory`
from that repo root - bare `--with psycopg` has no libpq and misreads as
store-down, #497).

Bucket rules - what may enter the SHARED store:
- Portable knowledge / infra trap (reusable across VMs and repos) -> SHARED
  (`--class knowledge --scope knowledge` or `--class infra_trap`).
- Repo file change (Makefile/hook/settings/doc) -> git; local note only.
- Per-machine permission fix -> this machine only (`--local-only`); never shared.

Steps:
1. `cpp-memory ping` - if not reachable, check `driver_error` first: non-null
   means the psycopg driver failed to load locally (store never contacted; fix
   with `psycopg[binary]`, #497), null means a real store outage. Either way
   continue in degraded mode (writes land in a local `.claude/learnings.md`);
   say which layer failed in your summary.
2. Scan this session for friction signals: permission prompts you needed, gate
   failures/retries, errors narrated-past, manual corrections, infra traps, and
   portable knowledge learned.
3. Classify each. For every portable candidate, dedup first:
   `cpp-memory query --fingerprint <fp>` (record echoes the fingerprint). Skip
   anything with `rejected_here:true`.
4. Ask me to confirm, then record:
   `cpp-memory record --class knowledge --scope knowledge --title "<stable title>"
   --body "<reusable knowledge>" --fix "<optional>" --confidence 0.8
   --repo "<repo-name>"`.
   Non-portable items: `cpp-memory record --local-only ...` AND propose the real
   fix in its proper home. Never send permission/repo_file learnings to the store.
5. When I act on a stored learning here, record the outcome:
   `cpp-memory apply|reject --fingerprint <fp> --actor <me> --note "<why>"`.
6. Promote to work (learnings->issue bridge, #463). If a portable learning is
   actionable (names a concrete fix), record it with `--emit-issue-candidate`;
   when `issue_candidate.should_file` is true, ask me to confirm, then
   `gh issue create` in the repo the fix targets using `issue_candidate.body`
   (it embeds a `<!-- cpp-learning: <fp> -->` marker), then
   `cpp-memory link-issue --fingerprint <fp> --url <issue-url>`. A fix for a
   skill that lives in its own standalone repo (an extracted plugin) files
   there, not where the friction surfaced. Only portable + actionable learnings
   become issues; never local/permission notes. Fail-open: no `gh` or no
   network -> skip filing, keep the codify.

Full routine: docs/skills/common-memory.md in the claude-power-pack repo.
End with a short summary: signals found, recorded-to-shared, skipped-as-dup,
kept-local.
