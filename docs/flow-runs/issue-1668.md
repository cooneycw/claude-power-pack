# Flow run record - issue #1668

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=b232b9863e2c48d181dab31a3e956db0 -->
## Run 1

- Run-id:            b232b9863e2c48d181dab31a3e956db0
- Run-start:         31fe6a69cf99992c55d75fe8bbac5cbdc651a4a9
- Issue:             #1668
- Base SHA:          31fe6a69cf99992c55d75fe8bbac5cbdc651a4a9
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the repository owner, interactively in the driving session ("approved with those two adjustments")
- Recorded at:       2026-11-11T15:09:23Z

### Section B evidence
- commits: none touching docs/agents/flow-wave-completion.md, its Codex mirror or scripts/flow-wave-completion.py since 2026-11-10T23:40:06Z; origin/main tip 31fe6a69 (#1667) predates the issue; document last changed by 417e8010 (#1660).
- PRs: none merged in cooneycw/claude-power-pack since 2026-11-10.
- dup/super: none (#864 Nit Store and #815 closed, both unrelated).
- Kyle side: cooneycw/kyle#2255 MERGED 2026-11-10; kyle#2220 CLOSED; draft at kyle 29a359dc and Kyle docs/cpp-receipt-adapter.md read.
- this host: no sibling worktree with unpushed commits on these paths; one registered worktree (scratchpad t008/cpp-pin) UNREADABLE, directory gone - unexamined.

### Section C - the approved plan
1. `docs/agents/flow-wave-completion.md` - append one short section on Kyle's role-receipt adapter, adapted from the Kyle draft: existing executable contract, no CPP change; per-role registration before launch; UNKNOWN versus null; same run namespace verified from the coordinator's configuration with a setup identity and wrong-namespace negative; claimed outcome stored separately from measured exit; no deadline extension; not deployed acceptance. Kyle's docs/cpp-receipt-adapter.md named in prose (private repo, no link).

Approved adjustments: (a) the section opens by scoping itself to Kyle-hosted waves - everyone else can skip it, and the filesystem default and generic contract are unchanged; (b) it is framed as a worked example of an external adapter so readers with another store can reuse the pattern.

Scope: 1 authored file plus its generated Codex mirror, about 20 lines. No script, test or control changes.
Risks: overclaiming a deployed adapter; drift from Kyle's contract; referencing a private repository.
