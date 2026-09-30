# Flow run record - issue #1357

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=82991e90b13b4d4fb2ddeeb5581ba4ca -->
## Run 1

- Run-id:            82991e90b13b4d4fb2ddeeb5581ba4ca
- Run-start:         e845d6d38b5f9db76ff5d9c89aaa783b0394dae5
- Issue:             #1357
- Base SHA:          e845d6d3
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner (cooneycw), interactive reply "approved"
- Recorded at:       2026-09-30T14:40:00Z

### Section B evidence
- commits since 2026-09-30T14:03Z touching scripts/codex-skill-sync.py, lib/project_next/: none
- merged PRs since filing: #1356 (unrelated changelog)
- duplicate/superseding issues: none (#1285, #534 are adjacent, different)
- sibling worktrees with unpushed commits on these paths: none

### Section C - the approved plan
1. `scripts/codex-skill-sync.py` - detect network-calling helpers in each skill's bundled scripts/libs and emit a Codex escalation bullet
2. `lib/project_next/collect.py` - when CODEX_SANDBOX_NETWORK_DISABLED=1 and a gh command fails, append a sandbox/escalation hint
3. `tests/test_codex_skill_sync.py` - detector red/green cases, and a real-repo pin that project-next carries the bullet
4. `tests/project_next/test_collection.py` - hint present with the env var set, absent without
Scope: 4 files, ~150 lines, plus regenerated codex/skills mirrors.
Risks: text heuristic can miss non-subprocess network calls or false-positive; CODEX_SANDBOX_NETWORK_DISABLED is Codex behaviour that may be renamed.
