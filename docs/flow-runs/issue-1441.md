# Flow run record - issue #1441

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=cec17c1df5d84556af7b80f67613d13e -->
## Run 1

- Run-id:            cec17c1df5d84556af7b80f67613d13e
- Run-start:         50261ddd1b76a042dd0bf868a869e04b67e5b27f
- Issue:             #1441
- Base SHA:          50261ddd
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), interactive reply "approved" in this session
- Recorded at:       2026-10-12T15:40:00Z

### Section B evidence
commits: none on origin/main since 2026-10-12T14:17:56Z. PRs: none merged since filing.
dup/super: #1071 (closed, repo-level precedent); nit #864 comments 5751638070,
5805176605, 5680393259, 5740510212 (all FIXED, unrelated to host files).

### Section C - the approved plan
1. `scripts/codex-global-agents.py` - new; --check (report-only verdicts current|stale|hand-edited|unmanaged|absent|unknown, exits 0/3/4) and --write [--adopt] building ~/.codex/AGENTS.md from ~/.claude/CLAUDE.md plus ~/.codex/AGENTS.local.md; lists AGENTS.md above repo roots; --home for sandboxing
2. `tests/test_codex_global_agents.py` - new; verdicts, write refusal, adopt backup, extras, idempotence, workspace listing
3. `controls/codex-global-agents/control.json` - new committed negative control with BAD stale/hand-edited cases, GOOD fresh case, synthetic anchor
4. `docs/decisions/0008-instrument-negative-control-bound.md` - census row
5. `docs/scripts.md` - inventory entry
6. `Makefile` - codex-global-agents (utility) and codex-global-agents-check (excluded, host-local)
7. `.claude/commands/cpp/status.md` - Tier 5 reports the verdict and fix command
8. `codex/skills/cpp-status/SKILL.md` - regenerated mirror of item 7

Scope: 8 files + generated mirror, ~450 lines.
Risks: Codex global-file size limit vs a much larger CLAUDE.md; Claude-specific rules added later reach Codex; synthetic anchor.
Revisions vs issue text (approved): extras are host-local (~/.codex/AGENTS.local.md), not CPP-tracked; building is opt-in, not wired into /cpp:init or /cpp:update.
