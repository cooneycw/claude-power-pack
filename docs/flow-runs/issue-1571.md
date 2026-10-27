# Flow run record - issue #1571

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=08df5709c36340519123a809328bd1e7 -->
## Run 1

- Run-id:            08df5709c36340519123a809328bd1e7
- Run-start:         7f17055c92c053c153d1de1ae818a4bcd4ab8a45
- Issue:             #1571
- Base SHA:          7f17055c92c053c153d1de1ae818a4bcd4ab8a45
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          cooneycw (owner), interactive "approved" in the flow:auto session
- Recorded at:       2026-10-27T11:30:00Z

### Section B evidence
Commits since 2026-10-25T22:41Z on main: 3a8a1fc0 (slice A, #1575), 8ceee357 (slice B, #1579),
unrelated 7f17055c, ad3c37e0, 6a461d27. PRs: #1575, #1579 merged; #1578 closed (replaced by #1579);
no other merged PR (#1556-#1581) touches the guide or help pages. Duplicates/superseding: none for
the guide; #1576 (open) holds the gate-determinism policy question; Nit Store comments 6414884947
and 6415152923. Host: no unpushed commits touching docs/agents or help pages in any worktree;
slice C exists only as origin/wip/1571-c at 804a6e9f (voided review, no full gate).

### Section C - the approved plan
1. `docs/agents/flow-permissions-guide.md` - new ~670-word guide (from 804a6e9f, claims checked against current main)
2. `.claude/commands/flow/help.md` - two-line link to the guide
3. `.claude/commands/cpp/help.md` - two-line link to the guide
4. `codex/skills/flow-help/SKILL.md` - regenerated mirror (source: .claude/commands/flow/help.md)
5. `codex/skills/cpp-help/SKILL.md` - regenerated mirror (source: .claude/commands/cpp/help.md)

Scope: 3 source files plus generated mirrors, ~270 added lines, docs only.
Risks: guide drifts from commands as they change; fresh counter-model findings; issue closes with
ask 3 recorded as revised and ask 5 recorded as cause-unproven.
