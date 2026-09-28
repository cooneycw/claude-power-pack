# Flow run record - issue #1272

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1272 (PR 1 of the #1272/#1273 docs pair; the Nit Store resolver items go to a separate PR)
- Base SHA:          5fd91de
- Necessity verdict: Needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 2247 in reply to ELI5 message 2245
- Recorded at:       2026-09-28T19:10:00Z

## Section B evidence
- All 18 items reproduced on 5fd91de with ref-scoped reads; live except the gemma pin (text no longer present) and possibly #992's note (to check).
- Item 1 (nit map duplicated) moves to the resolver PR; item 3 (tier labels) is re-dispositioned to #934.

## Section C - the approved plan
1. `README.md` - #663 as delivered; Dockerfile/hadolint mentions removed; control counts replaced by the commands that derive them
2. `docs/scripts.md` - worktree-remove occupied-but-clean text matched to the script
3. `docs/agents/shared-stash-stack.md` - the checkout --/reset --hard corollary with a backup-patch alternative
4. `.claude/commands/cpp/init.md` - Trusted profile no longer claims safety hooks
5. `.claude/commands/flow/doctor.md` - scripts/hooks no longer claimed as security protection
6. `.claude/commands/flow/register.md` - exact-match with the #985 directory exception; crossSessionInbound claim softened to what is measured
7. `Makefile` - drift-check verify-coverage annotation corrected
8. `lib/creds/ui/app.py` - remediation names `uv sync --extra ui`
9. `.claude/commands/secrets/ui.md` - the same
10. `tests/` - gpt-5.5 prose attributions corrected (CHANGELOG left as history)
11. `.claude/commands/spec/help.md` - pointer to the knowledge-lifecycle retirement rule
12. `codex/skills/` - regenerated mirrors of the changed command documents
