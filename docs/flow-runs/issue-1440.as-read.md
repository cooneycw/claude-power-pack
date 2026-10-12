<!-- flow-run n=1 id=4ffa755874ca4108a773180147295f3f -->
## Run 1 - issue #1440 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1440
- Read at:      2026-10-12T14:10:25Z
- updatedAt:    2026-10-12T13:46:16Z   (context only - moves on comments and labels)
- Body digest:  05a0e5244991357d804d98ff6a042557faee0ab7277a9299418be75a70231325   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3639 of 3639 (cap 16384)

### Body as read
## Problem

Claude Code's file-based auto-memory (`~/.claude/projects/<project>/memory/*.md`, indexed by `MEMORY.md`) links memories with `[[slug]]`. When a memory is **superseded**, the fix is usually made carefully in that one file — and the memories that *link to it* are left asserting the old rule. Nothing reports this, so the contradiction is found only when a session acts on the stale dependent.

### Observed instance (2026-10-11, kyle master session)

- `cpp-work-needs-host-placement.md` was rewritten on **2026-10-06** with a `**Superseded 2026-10-06.**` header: `host_tmux` is now refused by name (kyle#1363 S3); work runs in containers.
- `kyle-target-sequence.md` (modified **2026-09-19**) still says *"Until stage 3 acceptance passes, Kyle-repo groups are `host_tmux`"* and calls the superseded memory *"the separate, permanent CPP host reason"*. Both are now false.
- `cpp-slate-resume-point.md` (undated in frontmatter) still describes resuming an all-`host_tmux` formation from a host checkout. A session following it literally would be refused at `create_group`, or would work in the wrong repo.
- Secondary: the superseded file's **slug** still reads `needs-host-placement` while its body says the opposite — naming drift that the `MEMORY.md` index title had to paper over.

The supersession was recorded in one node and never reached the nodes that link to it. That propagation gap is the shape most contradictions in this store will take.

## Proposal

A stdlib-only checker (fits beside the other `~/.claude/scripts` helpers) that, for a memory directory:

1. Parses every `*.md` (frontmatter `name`, `description`, `metadata.modified`, body).
2. Builds the `[[slug]]` link graph.
3. Marks a memory **superseded** when its body or description carries a supersession marker (e.g. `Superseded <date>` / `Supersedes`). The marker grammar should be documented so writers can rely on it.
4. Reports **stale dependents**: every memory that links to a superseded memory and is older than the supersession (or has no `modified`, which is reported as `unknown`, never `ok`).
5. Also reports, as separate findings:
   - dangling `[[slug]]` links are **not** errors (the memory convention allows them as "worth writing later") — list them as info only;
   - `MEMORY.md` lines pointing at missing files, and files absent from `MEMORY.md`;
   - slug/filename mismatch with `name:`.
6. Exit codes distinguish *found stale dependents* (1) from *could not read the store* (2) from clean (0) — an unreadable store must not read as clean.

## Negative control (required before trusting it)

Commit a fixture memory directory reproducing the instance above (a superseded node, one older dependent linking to it, one newer dependent, one unrelated node). The checker must:

- **flag** the older dependent → exit 1;
- **not flag** the newer dependent or the unrelated node;
- report exit 2 on an unreadable / empty-by-error directory, not 0.

And a blind variant (e.g. supersession-marker detection disabled) must **miss** the fixture, so the control proves the marker detection is what produces the verdict.

## Out of scope

- Kyle's substrate memory (`memory_search` / `memory_correct`) — a different store with its own steward; a parallel check there belongs in kyle if wanted.
- Semantic contradiction detection between unlinked memories. This issue covers only the link-graph propagation gap, which is mechanical and measurable.

Found while answering an operator question about examining contradictions in memory. Correcting the three stale memories themselves is a separate, local step and not part of this issue.

