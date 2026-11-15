# Flow run record - issue #1848

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=9ba4688537ad4b78ad8dd1981c6c7481 -->
## Run 1

- Run-id:            9ba4688537ad4b78ad8dd1981c6c7481
- Run-start:         62e928b9bfaf8631c63634552b25df756ac8d149
- Issue:             #1848
- Base SHA:          62e928b9
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner (cooneycw), in-session reply "approved" to the Section C plan
- Recorded at:       2026-11-15T22:30:00Z

### Section B evidence
Commits since filing touching the paths: 06392d40 (#1846, prose only), 62e928b9 (#1847, codex-review blocks moved out); neither touches the exit-code bullets, cleanup table or fallback text. Merged PRs since filing: #1854, #1852, #1845, #1843, #1841, #1840 - none addresses this. Duplicate/superseding issues: none (#1849 and #1850 are downstream; #1851 related, not a prerequisite). Sibling worktrees: no unpushed commits touching flow/auto.md, gh-pr-merge.sh or worktree-remove.sh.

### Section C - the approved plan
1. `.claude/commands/flow/auto.md` - one helper-resolution rule replaces the repeated exit-127 fallback (call sites keep only their no-copy disposition); Step 7 gh-pr-merge per-exit bullets 3-11 collapse to one relay-the-CLEAN-STOP rule (keep exit 12, ALREADY_MERGED, markers, genuine-failure, a never-discard line for exit 9); Step 7b worktree-remove table and bullets collapse to relay + never override; finish-gate and worktree-guard verdicts kept with a one-line reason.
2. `.claude/command-word-budgets.tsv` - lower flow/auto.md by the measured cut, with a #1848 header note.
3. `docs/agents/driver-parity.json` - move the 9 flow/auto.md citation line numbers to their new positions; text unchanged.
4. `tests/fixtures/flow-command-steps.fixture` - retire exit-rule-0003..0013 with named reasons (owner-authorised withdrawal of the document's wording, not of the stops).
5. `tests/test_gh_pr_merge.py` - assert each stop exit's remedy line is printed (exits 3, 4, 5, 6, 7, 9, 10, 11).
6. `tests/test_worktree_remove_occupied.py` - assert each refusal's remedy line is printed (exits 4, 5, 6, 7, 8).

Scope: 6 files, ~250-400 words out of flow/auto.md, ~100 lines of fixture/parity/test change.
Risks: an instruction lost in the trim (mitigated by the independent old-vs-new read and remedy-line tests); citation line shifts (caught by driver-parity-check); worktree-remove exit-6 text says "stash" against flow's never-stash rule (keep one never-stash line; nit store the helper text).
Lanes: Driver - will test (driver-parity-check, test_driver_parity.py: flow:auto vs codex/qwen/gemma); Harness - will test (make codex-skills + mirror tests: Claude install / Codex install); Checkout, Coordination, CI provider, Project state, Toolchain version, Clone shape, Run location, Gate target, Wave role state - not applicable (no helper behaviour changes).
Reader: sessions reading flow/auto.md and its Codex mirror; check-driver-parity.py (citations); check-claude-md-behavior.py (step fixture); check-claude-md-budget.py (budget row).

### Lanes for this change

| Lane | Answer | Values / reason |
|---|---|---|
| Checkout | not applicable | no helper behaviour changes; prose and tests only |
| Harness | will test | Claude install / Codex install: `make codex-skills` builds the flow/auto mirror; mirror tests check it |
| Driver | will test | `/flow:auto` / delegated drivers: `make driver-parity-check` and `tests/test_driver_parity.py` |
| Coordination | not applicable | no coordination path touched |
| CI provider | not applicable | no CI helper touched |
| Project state | not applicable | no adopted file or record changes |
| Toolchain version | not applicable | no toolchain dependency |
| Clone shape | not applicable | no history reads added |
| Run location | not applicable | no invocation path changes |
| Gate target | not applicable | no gate runner change |
| Wave role state | not applicable | no wave registry change |
| Reader: sessions reading flow/auto.md and its Codex mirror | will test | the step fixture check and the independent old-versus-new read |
| Reader: check-driver-parity.py | will test | reads the moved citations; `make driver-parity-check` |
| Reader: check-claude-md-behavior.py | will test | reads the fixture retirements; its check runs in `make verify` |
| Reader: check-claude-md-budget.py | will test | reads the lowered row; `make command-docs-budget-check` |
