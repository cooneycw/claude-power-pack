# Lane evidence for issue #1811

<!-- lanes-demonstrated run=15008b78315749218f268bf83d96d4c1 plan=860116b04bde5c6c808b29577a45a48d0eaa91c05824090b4548784b4ced3c91 -->

| Lane | Result | Evidence |
|---|---|---|
| Harness | passed | `make delegated-core-check` checks the actual Claude command renders. `make driver-parity-check` builds and reads the real Codex flow-auto mirror; delegated families intentionally unpackaged. |
| Driver | passed | Actual codex/qwen/gemma render regressions: pre-change 6 failed, 3 fixture cases passed; post-change focused suite 320 passed. `make driver-parity-check`: 24 items, 72 pairs, 0 missing. Static membership/order only, no live delegation. |
| Project state | passed | Actual-render verdict checks distinguish present, absent STOP and unverified STOP; focused wrapper/run tests cover helper behavior for adopted/missing run records. |

## Regression and control evidence

`PYTEST_WORKERS=1 PYTEST_ADDOPTS='tests/test_delegated_plan_finish.py -q' make test`
on unchanged main command documents: **6 failed, 3 passed**. Failures asserted
missing post-publication finish and its verdict handling for all three drivers.
Committed missing-finish and finish-before-PR render inputs are rejected by the
ordering predicate; the good-finish excerpt is accepted. The fixture tests
assert each bad precondition before exercising the predicate.

After rendering, the same regression plus driver parity, plan-record wrappers,
plan-record runs, delegated-core vendor and delegated-plan-lanes tests:
**320 passed in 60.89 seconds**. Core, command budgets, driver parity and lint
passed separately. One earlier focused invocation was terminated by its command
timeout and is not counted as evidence.

## Word accounting and old-versus-new read

Caps unchanged. Exact split-based counts before/after:

| Driver | Before | After | Cap | Delta |
|---|---:|---:|---:|---:|
| codex | 8689 | 8689 | 8689 | 0 |
| qwen | 9903 | 9903 | 9905 | 0 |
| gemma | 10512 | 10512 | 10514 | 0 |

The two repeated acceptance paragraphs used 207 words. Their replacement uses
112 words; the new finish item uses 95 words. Every instruction was compared:

| Original obligation | Retained instruction |
|---|---|
| Account for material items before closing reference | Account for every material acceptance item before selecting a closing reference |
| Demonstrated, revised with evidence or recorded transfer permits closure | Same three dispositions; surrounding ACCEPTANCE_COMPLETE selection unchanged |
| Deferred or unresolved items must be accounted for in PR prose | Every material item gets ordinary-prose accounting; unresolved work uses Refs |
| Incomplete work uses Refs in commit, PR title and body | All three surfaces explicitly retained |
| Partial delivery is mergeable but must not close promise | Explicitly says partial delivery remains mergeable but never closes issue |
| No incidental close keyword even in illustrations | Explicit prohibition and helper exits 5/7 retained |
| Inspect earlier branch commits and PR text yourself | Same git-log command and manual PR read retained |
| Squash may derive from those sources | Explicitly retained |
| Helper passes explicit PR subject/body | Explicitly retained with #655 reference |
| Check actual sources before assuming rewrite | Explicitly retained |
| Canonical rule is issue-contract.md | Same reference retained |

The existing Step 5 lane-question Nit Store finding is unchanged and remains
recorded at https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7040701785.
