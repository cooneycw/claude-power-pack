# Flow run record - issue #1804

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=08b229d7233b45aba4a0ba269f84ad95 -->
## Run 1

- Run-id:            08b229d7233b45aba4a0ba269f84ad95
- Run-start:         d90712eed2523fc2128674a54ffa7923f8bf2c54
- Issue:             #1804
- Base SHA:          d90712eed2523fc2128674a54ffa7923f8bf2c54
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), in-session, 2026-11-14 ("approved with issue-clearing included")
- Recorded at:       2026-11-14T00:00:00Z

### Section B evidence
Commits since filing on the touched paths: 020c8758 (PR #1805, #1762), which excluded this behaviour. Merged PRs inspected: #1792-#1820; only #1805 touches the register path, #1814 is docs. Related issues: #1222 (closed, origin of legacy rows); #1564, #1260, #683 unrelated. No duplicates.

### Section C - the approved plan
1. `scripts/flow-wave-registry.sh` - register: a released previous row resets files, pr/base/diff/obs_repo and overtaken unless supplied; a supplied observation starts at count 0; omitted --issue on a released row gives ""; repo and grant fields stay.
2. `tests/test_flow_wave_reregister_review_regressions.py` - ruling assertions for omitted/issue-only/full-same/different, pre-1762 anchor still restores (red case), plus an explicit-restatement case.
3. `docs/scripts/flow-wave-registry.md` - replace the "legacy reuse remains unchanged (#1804)" paragraph with the ruling.
4. `CHANGELOG.md` - Unreleased Fixed entry.
5. `.claude/lanes.md` - Wave role state row: the regression test now asserts the ruling, not a characterization.

Scope: 5 files, ~40-80 lines.

Risks: issue clearing goes beyond the ruling's literal field list (approved explicitly); wider registry suites may depend on legacy restore.

### Lanes for this change

| Lane | Answer | How |
|---|---|---|
| Checkout | not applicable | registry state is independent of checkout layout; tests run in a plain fixture cwd |
| Harness | not applicable | shell helper behaviour, identical under Claude and Codex installs |
| Driver | not applicable | registry is driver-neutral; no command-surface change |
| Coordination | not applicable | wave registry is a local file; Kyle not involved |
| CI provider | not applicable | no CI-provider output read |
| Project state | not applicable | no adopted-file feature |
| Toolchain version | not applicable | no new tool or version dependency; jq/bash already required |
| Clone shape | not applicable | no git history read |
| Run location | not applicable | registry path is explicit in tests |
| Gate target | not applicable | no gate runner change |
| Wave role state | will test | values: a released legacy role returning (omitted, same issue, same issue+repo, different issue, explicit restatement) in test_flow_wave_reregister_review_regressions.py; a fresh/live role via the unchanged test_flow_wave_registry.py and cross-product suites. Not tested: a role released under current release (already empty; covered by existing #1222 tests) |
