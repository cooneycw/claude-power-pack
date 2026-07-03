Populate and consult the shared CPP common-memory ledger: harvest *portable*
learnings / infra traps from this session into the fleet-wide store, consulting
the dedup/rejection ledger so nothing already-recorded or already-rejected is
re-proposed.

This is consult-not-push, fail-open, and human-confirmed. It never distributes
config and never auto-applies permission fixes. The whole interface is the
`cpp-memory` command (install once with `bash scripts/install-memory-harness.sh`
from the claude-power-pack repo; falls back to `python -m lib.cpp_memory` from
that repo root).

Bucket rules - what may enter the SHARED store:
- Portable knowledge / infra trap (reusable across VMs and repos) -> SHARED
  (`--class knowledge --scope knowledge` or `--class infra_trap`).
- Repo file change (Makefile/hook/settings/doc) -> git; local note only.
- Per-machine permission fix -> this machine only (`--local-only`); never shared.

Steps:
1. `cpp-memory ping` - if not reachable, continue in degraded mode (writes land
   in a local `.claude/learnings.md`); say so in your summary.
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

Full routine: docs/skills/common-memory.md in the claude-power-pack repo.
End with a short summary: signals found, recorded-to-shared, skipped-as-dup,
kept-local.
