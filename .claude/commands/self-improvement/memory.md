# Self-Improvement: Common Memory - Populate the Friction-Knowledge Ledger

Harvest *portable* learnings from the just-finished session into the shared CPP
common-memory store (bucket-2-plus), consulting the dedup/rejection ledger so
nothing already-recorded or already-rejected is re-proposed. This is the
populate/codify half of the grill-me cycle (#426).

**Consult-not-push, fail-open, human-confirmed.** Never distributes config, never
auto-applies permission fixes, degrades to a local `.claude/learnings.md` if the
store is down. The full, harness-neutral routine lives in
`docs/skills/common-memory.md` (shared verbatim with the Codex `/cpp-memory`
prompt) - follow it. Quick reference below.

## Scope: what may enter the SHARED store (bucket rules)

| Learning | fix_scope | Destination |
|----------|-----------|-------------|
| Portable knowledge / infra trap | `knowledge` | **Shared store** |
| Repo file change (Makefile/hook/settings/doc) | `repo_file` | **git** (local note only) |
| Per-machine `permissions.allow` entry | `permission` | **This machine only** |

The client refuses to record anything but portable learnings in the shared store.

## Interface (identical for Claude Code, Codex, and shell)

```bash
cpp-memory ping                                   # reachability
cpp-memory query  --fingerprint <fp>              # dedup + rejected-here
cpp-memory record --class knowledge --scope knowledge \
    --title "<stable title>" --body "<reusable knowledge>" \
    --fix "<optional>" --confidence 0.8 --repo "$(basename "$(git rev-parse --show-toplevel)")"
cpp-memory record --local-only --class permission --scope permission ...  # stays local
cpp-memory record ... --emit-issue-candidate                             # + issue candidate (#463)
cpp-memory link-issue --fingerprint <fp> --url <github-issue-url>        # record the filed issue
cpp-memory reject --fingerprint <fp> --actor <user> --note "<why>"        # stops re-proposal
```

If `cpp-memory` is not yet on PATH: `bash scripts/install-memory-harness.sh`, or
run `python -m lib.cpp_memory ...` from the repo root.

## Routine

1. `cpp-memory ping` - if unreachable, continue in degraded mode and note it.
2. Gather friction signals: permission prompts, gate failures/retries, red output
   narrated-past, manual interventions, infra traps, portable knowledge.
3. Classify each `(friction_class, fix_scope)` per the bucket rules.
4. For each portable candidate, `cpp-memory query --fingerprint <fp>`; skip if
   `rejected_here:true`.
5. Confirm with the user, then `cpp-memory record ...` (portable) or
   `--local-only` + propose the real fix in git/settings (non-portable).
6. Record `apply`/`reject` when a stored learning is acted on here.
7. If a portable learning is **actionable** (names a fix), `record ... --emit-issue-candidate`;
   when `should_file` is true, confirm, `gh issue create` (body carries the fingerprint
   marker), then `cpp-memory link-issue` the URL back (learnings->issue bridge, #463).

## Output Format

```
Common Memory: Friction Retro
=============================
Store:            reachable | DEGRADED (local .claude/learnings.md)
Signals found:    N  (permission M / gate G / red R / manual U / knowledge K)
Portable -> shared:  P recorded  (D duplicates, X rejected-here, skipped)
Non-portable -> local/git: L
```
