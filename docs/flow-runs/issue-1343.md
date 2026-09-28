# Flow run record - issue #1343

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=3a1cf7af31b5464e8cfe4212fd20eaf4 -->
## Run 1

- Run-id:            3a1cf7af31b5464e8cfe4212fd20eaf4
- Run-start:         75fb4497140b5a0584a19c8761a98e83ce66e612
- Issue:             #1343
- Base SHA:          75fb4497140b5a0584a19c8761a98e83ce66e612
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run48:cpp2-orch (orchestrator), mailbox message 2438 replying to plan 2435
- Recorded at:       2026-09-28T22:10:00Z

### Section B evidence
Reproduced on 75fb449 in a Kyle container. test_helper_orphan_prune.py: 1 failed, 12 passed with CPP_DEFER_SURFACES set; 13 passed with env -u. test_supervise_sweep.py -k outside_its_own: 0 `sleep 300` before, 1 after (PPID 1). The other 15 tests add 0.
No commits since the issue was filed (2026-09-28T21:40Z) touch the four test files. No open PRs touch them. Issues considered: #1268 (parent, open), #864 (nit store), #1132 and #1285 (closed, unrelated). None supersede this one.

### Section C - the approved plan
This run is PR A (items 1 and 2). Item 3 (ROUTED_SURFACES floor, EXEMPT x4 ruling) is a later run on a branch cut after this one merges.

1. `tests/test_supervise_sweep.py` - _cleanup's shared-group branch SIGKILLs the fake daemon's descendants (tests.supervise_reap._descendants), children first, then the parent. New regression test: no descendant survives _cleanup. It fails on the pre-fix _cleanup.
2. `tests/test_helper_orphan_prune.py` - a _host_env helper that strips CPP_DEFER_SURFACES, used at :189, :249 and :265. The tally test sets the ambient variable deliberately with monkeypatch.setenv, so it is a committed, host-independent red case. A new case puts the variable in the block's env explicitly and asserts the DEFERRED tally ("0 removed, 0 already absent, 2 refused or deferred"), with the link surviving. No skip.

Scope: 2 test files, ~60-80 lines, no production code.
Risks: a fork between descendant enumeration and the kill (the fake daemon forks once, at start, so this is not an issue here). The monkeypatch must not leak (it is restored per test).

<!-- flow-run n=2 id=52b8ed5783cc4188bd51d860fa67e477 -->
## Run 2

- Run-id:            52b8ed5783cc4188bd51d860fa67e477
- Run-start:         846431d2145c229e2bac44747aa0780937283a36
- Issue:             #1343
- Base SHA:          846431d2145c229e2bac44747aa0780937283a36
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run48:cpp2-orch (orchestrator), mailbox message 2470 replying to plan delta 2469; EXEMPT x4 ruling in message 2438
- Recorded at:       2026-09-28T22:05:48Z

### Section B evidence
Re-measured on 846431d. `gh issue create` appears in 5 command docs (flow/wave, github/issue-create, qa/test, self-improvement/memory, self-improvement/retro), 0 skill docs, and 14 generated codex/skills mirrors (excluded). No commits in 75fb449..846431d touch tests/test_issue_contract_routing.py, .claude/commands or .claude/skills. PR A of this issue merged as PR #1344 (846431d).

### Section C - the approved plan
This run is PR B (item 3). Items 1 and 2 shipped in PR #1344.

1. `tests/test_issue_contract_routing.py` - ISSUE_CREATE_EXEMPT {path: reason}, one entry each for flow/wave, self-improvement/retro, self-improvement/memory and qa/test. A derived scan of .claude/commands and .claude/skills for `gh issue create`. A floor test: every hit is routed or exempt. A stale-exempt tripwire. A committed red-case fixture: a doc in neither list is reported. A positive control: the real scan finds github/issue-create.md. The docstring names the codex/skills exclusion and the prose-mention friction. The new instrument is proven able to fail by mutations (a) empty scan, (b) EXEMPT treated as routed-for-all, (c) stale tripwire accepting a non-mentioning path.

Scope: 1 test file, ~80-100 lines.
Risks: the literal match is narrow by design; a doc that files issues through gh api or a helper script is not seen, and the docstring says so.
