# Flow run record - issue #1273

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1273 (PR 2 of the #1272/#1273 docs pair; Nit Store resolver items go to a separate PR)
- Base SHA:          5fd91de
- Necessity verdict: Needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 2247 in reply to ELI5 message 2245
- Recorded at:       2026-09-28T19:40:00Z

## Section B evidence
- All 31 items reproduced on 5fd91de with ref-scoped reads; live unless listed for re-disposition.
- Re-dispositioned (comment only): 3 (triage notes -> #1028/#1047), 12 (latent, 0 instances), 15, 16 (deliberate designs), 19, 26, 27 (no CPP code), 22 (perf only). Items 10 and 28 move to the resolver PR; item 6 was fixed by #1272's PR.

## Section C - the approved plan
1. `lib/cicd/deploy/strategy.py` - from_dict copies before popping, with a regression test
2. `tests/` - from_dict regression; heredoc docstring; requires_git reason; root-relative parametrize ids; mailbox test renamed to what it tests; em dash in test_runner.py
3. `woodpecker/bootstrap-agent-host.sh` - the docker check no longer gates unrelated packages (real-host check owed)
4. `scripts/bash-prep.sh` - em dashes
5. `docs/research/` - forced-claim --selftest probes is-inside-work-tree first (with a red case); class-enumeration :188 corrected
6. `.claude/commands/` - the duplicated sentence in flow/finish.md and flow/auto.md; code_review.md dated model name; retro.md grill-plan references
7. `codex/skills/` - regenerated mirrors
8. `docs/security/dependency-advisory-dispositions.md` - the deleted #918 cite
9. `Makefile` - host-surface prose above its target; battery-in-ci-image prints tool versions
10. `pyproject.toml` - stale mypy exclude
11. `.gitignore` - .coverage entry
12. `docs/scripts.md` - inventory-check EXAMINED includes untracked files
13. `docs/agents/evidence-deleting-idioms.md` - gh pr diff -- <path> returns empty silently
