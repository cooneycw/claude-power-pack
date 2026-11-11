# Flow run record - issue #1669

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=c8d92c62f366480d8c97981bba088369 -->
## Run 1

- Run-id:            c8d92c62f366480d8c97981bba088369
- Run-start:         dca1ac6bdcb8db2410b6238b470290660d1df364
- Issue:             #1669
- Base SHA:          dca1ac6bdcb8db2410b6238b470290660d1df364
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner, in the driving session ("approved", 2026-11-11)
- Recorded at:       2026-11-11T18:57:21Z

### Section B evidence
- Commits since filing (2026-11-11T14:58:26Z): none touching .claude/commands/, scripts/check-claude-md-budget.py, docs/commands-reference.md, Makefile or controls/claude-md-budget. Main moved by dca1ac6b and c230b667, both unrelated.
- Merged PRs since filing: #1676, #1675 - neither touches the flow command documents.
- Duplicate/superseding issues: none. #724 (closed) is the mechanism to extend; #1673 runs after this issue; #1670 and #1671 are siblings.
- This host: the #1670 worktree holds unpushed ae0609a7, which edits flow/auto.md, Makefile and .woodpecker.yml (collision risk, not duplicate work). The stale /tmp t008/cpp-pin worktree was unreadable and is unexamined.

### Section C - the approved plan
Pilot delivery: the gate plus the auto.md trim, with Refs #1669 so the issue stays open for the remaining documents.

1. `scripts/check-claude-md-budget.py` - per-document budget table for every command document and an every-command-document mode; an undeclared document fails; flow/auto.md at 10,183, every other document at its current size as an interim cap
2. `Makefile` - command-docs-budget-check target, wired into make verify
3. `.woodpecker.yml` - run the new target in CI
4. `controls/claude-md-budget/control.json` - register the new mode with two committed cases
5. `controls/claude-md-budget/cases/bad-command-over-budget` - a command file one word over its budget, must report BAD
6. `controls/claude-md-budget/cases/good-command-at-budget` - the same file exactly at budget, must report GOOD
7. `tests/test_check_claude_md_budget.py` - tests for the new mode, including the undeclared-document failure
8. `.claude/commands/flow/auto.md` - trim from 20,924 to at most 10,183 words; every command, exit-code rule and stop condition stays; history and rationale become one-line pointers
9. `docs/reference/flow-auto-rationale.md` - new; the moved history and rationale, by step, linked from auto.md
10. `tests/fixtures/flow-command-steps.fixture` - new; every executable step of the pre-trim auto.md, captured before the trim (the #724 method)
11. `scripts/check-claude-md-behavior.py` - also check that fixture, requiring each step in the command document itself
12. `tests/test_check_claude_md_behavior.py` - tests for that, including a deleted step going red
13. `docs/commands-reference.md` - pointer to the budget rule and the new reference

Also planned, not enumerable before the trim: tests under tests/ that pin prose moved out of auto.md are retargeted to the reference document (32 test files read auto.md; the exact set is found by running the suite and is listed in the PR).

Scope: about 14 named files plus affected tests; roughly 10,000 words leave auto.md.

Risks: collision with #1670's unpushed ae0609a7 on auto.md and Makefile; tests pinning rationale wording need a per-test judgement; interim caps are not final budgets; the issue's 60-day baseline (10,183) differs from a re-measurement (11,211) - hold to 10,183 unless the trim shows a step would be lost, then return with evidence; shorter-performs-as-well is the issue's untested assumption.
