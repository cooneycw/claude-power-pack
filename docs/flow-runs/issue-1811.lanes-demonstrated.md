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

## Independent review corrections

First review (gpt-6.2-sol) used the canonical committed patch on stdin, with no
reviewer shell: bubblewrap was unavailable. Three findings were accepted:
commented commands fooled the ordering predicate, separate shell fences could
fool the early-compliance pin, and deferred acceptance dispositions lost their
explicit mention. The acceptance prose now says `Record deferred items too.`;
removing four redundant words elsewhere keeps the exact command counts above.

New committed commented-finish and commented-pr inputs reproduced the blind
ordering check before its fix: **5 failed, 9 passed**, including three rendered
prose regressions. The split-compliance input separately reproduced the old
same-shell blind spot: **1 failed**. The fixed predicate reads active literal
lines in bash fences; early compliance must share a block with the preceding
merge-base assignment. This is a narrow document grammar, not a Bash interpreter.

After corrections: **267 focused tests passed in 39.07 seconds**; acceptance
and closing-report suites **102 passed in 2.22 seconds**. Core, budget, parity
and lint rechecked green. Three added fixture files expand the approved
known-bad controls within scope: commented-finish.md, commented-pr.md and
split-compliance.md. The approved plan itself is unchanged; the file-set
variance is reported rather than rewriting it.

Final independent gpt-6.2-sol pass: `None - no defects found.` Both passes were
diff-only, using canonical captured patches with no reviewer shell. The
schema-5 receipt derives codex/gpt-6.1-sol implementer and codex/gpt-6.2-sol
reviewer from their runtime evidence; its artifact binding is captured-patch.


<!-- lanes-demonstrated run=bee480efb058429fb5ae2a452abdbbfe plan=d4a2387090b956f5069c707fafeff835c11b86b8db8abb1078693bddb82498c6 -->

## Friction capture row - run 2

| Lane | Result | Evidence |
|---|---|---|
| Checkout | passed | `tests/test_friction_log.py` main checkout and linked-worktree default-main-buffer cases in focused suite. |
| Harness | passed | `make delegated-core-check` reads actual Claude renders; `make driver-parity-check` generates/reads actual Codex flow-auto mirror; delegated families intentionally unpackaged. |
| Driver | passed | Pre-change regression 3 failed, 39 passed; fixed focused suite 241 passed in 17.77 seconds. Actual renders and canonical flow pointer checked. |
| Project state | passed | Existing friction helper append, absent-buffer/parent creation and fail-open tests passed in focused suite. |
| Run location | passed | Existing helper root, subdirectory and outside-git cases passed in focused suite. |

### Red cases and scope

On unchanged main 25f5066a, real codex/qwen/gemma renders each failed the missing
pre-Step-1 capture assertion: **3 failed, 39 passed** in 11.59 seconds. Committed
good, missing-call, commented-call and after-step-1 excerpts pin the documented
procedure. The optional no-self-approval guard checks all three actual renders;
each deletion mutant raises the expected assertion. This does not claim live
delegated capture completeness. Existing helper tests cover actual JSONL.

### Word counts and old-versus-new audit

The addition is 49 template words. Only Step 1's 117-word upstream-hazard
history becomes 61 words, for **-7 words per driver**, including the approved
amendment: an unresolved ref must never be read as zero.

| Driver | Before | After | Cap |
|---|---:|---:|---:|
| codex | 8689 | 8682 | 8689 |
| qwen | 9903 | 9896 | 9905 |
| gemma | 10512 | 10505 | 10514 |

Instructions retained: use audited resolver, never hand-build (preceding prose
unchanged); resolver creates --no-track with OWN-name upstream; hand-built
origin/main risks a main push (#1221); BOTH Step 4 overrun and Step 7 backstop
use an explicit recorded base and never @{u}; upstream unresolved before first
push; unresolved ref must never be counted as zero. Removed history examples:
full erroneous worktree-add command, bare-push failure, exact unsafe suggested
push command, and rhetorical blind-check explanation. Step 3 and everything
from there onward in the template were compared byte-for-byte to main and are
unchanged. No approval/review/merge/close instruction pays for capture.

The 49-word capture pointer reads the canonical flow:auto friction section;
new actual-render tests follow the real relative target and anchor and inspect
that source for immediate/every-step/success-and-failure triggers, manual
permission-prompt exclusion, fail-open missing-helper and capture-only/retro.
The local command supplies required class/signal and driver/issue/8-step identity.

### Pre-push scan control

Private official gitleaks v8.30.1 Linux archive checksum verified against the
release checksum manifest, no system install. The committed known-bad private-key
fixture was relocated into a private temporary git repository and committed:
`gitleaks detect --log-opts=HEAD` returned **1**, with **1 private-key finding**.
Output was redacted. This controls the same history population used before
push, unlike the existing working-tree-only secret-scan control. Actual branch
history scan is pending; no clean-scan claim yet.

Fixed focused capture, driver-gate, friction-helper, vendor and parity suites: **241 passed in 17.77 seconds**. Lint, core, budgets, parity and typecheck passed; mypy examined 511 source files.
