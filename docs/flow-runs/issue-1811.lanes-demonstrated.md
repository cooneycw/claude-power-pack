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

The final file-only-link addition is 51 template words. Only Step 1's
117-word upstream-hazard history becomes 61 words, for **-5 words per driver**,
including the approved
amendment: an unresolved ref must never be read as zero.

| Driver | Before | After | Cap |
|---|---:|---:|---:|
| codex | 8689 | 8684 | 8689 |
| qwen | 9903 | 9898 | 9905 |
| gemma | 10512 | 10507 | 10514 |

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


### Friction-row independent review correction

The first gpt-6.2-sol diff-only pass accepted the Step 1 instruction audit and
found one detector defect: a renamed canonical policy heading still matched as
a substring although its Markdown anchor had changed. Accepted and fixed.
Committed policy-renamed-heading.md preserves the body and changes only the
heading suffix; its regression failed before the predicate fix (**1 failed**).
A fenced-policy heading mutant likewise demonstrated a pre-fix red (**1 failed**).
The predicate now requires exactly one matching active Markdown heading outside
backtick/tilde fences, then reads its policy body. Actual flow source remains
the reader input, not a stand-in. Corrected focused suite: **243 passed in
21.45 seconds**. New fixture is within the approved controls scope; its one
file-set divergence is reported rather than rewriting the approved plan.


Second independent diff-only pass found two further detector defects: an HTML
comment could hide the entire policy while the predicate credited it, and a
sibling heading could leave the target section empty while supplying its words
later. Both accepted. Committed policy-html-comment.md and
policy-sibling-section.md assert these preconditions; both tests failed on the
pre-fix predicate (**2 failed**). Fixed capture suite: **12 passed in 0.72 seconds**.
The predicate removes HTML comments and limits the body at the next active ATX
heading of equal/higher rank. Its scope is this canonical source's ATX/comment/
fence forms, not a general Markdown renderer. Three reviewer-added fixture
paths now produce a disclosed file-set divergence; the approved plan is intact.
A third pass is requested to review these second-pass corrections before the
single authorized heavy gate. No clean review or full-gate claim is made yet.


### Reader cap and approved test reshaping

Third review found two more defects: an HTML-commented driver preamble still
counted as active, and regex comment stripping hid the real policy after a
literal opener inside an earlier fence. Committed commented-capture.md and
policy-literal-comment.md reproduced both: **2 failed** on the old reader.
The orchestrator stopped special-case parsing and approved the CommonMark
shape plus one escalated fourth pass (mailboxes 36484-36485).

The final driver predicate only checks active pre-Step-1 fenced command and
identity arguments, actual Markdown link target and its unique real heading.
It does not re-derive flow:auto obligations. `tests/test_flow_friction_policy.py`
pins those at their own source section; existing matching tests exercised helper
behavior, installation, exit/census and gitignore, not that source policy.
CommonMark tokens now own heading, HTML and fence structure. Visible inline
text preserves token adjacency; an independently noticed text-joining defect
has a demonstrated pre-fix red (**1 failed**) and corrected source/driver tests.

`markdown-it-py` is directly declared in the dev extra because tests import it.
The same version 4.2.0 was already locked transitively via bandit/rich; uv.lock
changes only the two root metadata references, no package versions. The extra
flow test, five reviewer control files and dependency metadata are disclosed
file-set divergence within the subsequent approvals, not edits to the original
approved plan. Final focused suites: **249 passed in 15.52 seconds**. Lint,
typecheck (512 files), core, parity and budgets passed. Product driver text and
its -7-word counts are unchanged from the approved implementation.


### Final scope reduction after fourth review

Pass 4 found two defects: a promoted capture heading could include Step 1 and
lend a later command to the preamble, and an earlier different heading could
own the same GitHub-style fragment. Both controls were red on the pre-fix code
(**2 failed**). The command/link token range is now bounded strictly before
Step 1, independently of heading rank. The orchestrator removed the anchor
claim rather than adding a slug dependency (mailbox 36504): driver links go to
`../flow/auto.md` and name its Friction Capture (always-on) section. Tests require
the file and one exact real heading; they do not claim fragment ownership.
The slug-collision fixture is retained as a valid file-link case under this
narrowed contract. No github-slugger dependency was added.

Final focused suites: **251 passed in 12.62 seconds**. Final driver and own-flow
checks separately: **18 passed in 1.30 seconds**. Static core, budget, parity,
lint and typecheck (512 files) pass. The fifth review is authorized once as the
hard stop, with reason `pass 4 found range and anchor defects; anchor claim
removed, range bounded by token order`, cp-orch mailbox 36504, raised cap 5.
Any further TEST-only finding is to be deferred with a reason/receipt/Nit Store
record under that ruling; a product-procedure defect must be escalated.


### Final independent-review disposition

Fifth gpt-6.2-sol diff-only/captured-patch review of 50780eed reported no product
procedure defects. Across five passes, seven findings were accepted/resolved,
zero rejected, and two TEST limitations deferred under cp-orch mailbox 36504's
explicit hard stop/proportional-prevention ruling. No sixth pass or test fixes:

- Quoted parent preamble can satisfy the container-insensitive predicate:
  https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7065290052
- Negated timing instruction can satisfy the own-flow positive substring pins:
  https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7065290255

These final two mutations were reasoned through in diff-only review, not
executed controls. Their deferral counts and reason are recorded in the derived
schema-5 receipt's extra-pass/disposition explanation; current schema has no
separate per-finding reason flag. The resolver verified Nit Store #1725, source
search. All review passes had no reviewer shell; network/credential isolation
was unverified. Final source words remain 8684/9898/10507; product text unchanged
since the fifth reviewed commit.


### CI-discovered import alias correction

Initial PR CI pipeline 3965 on c0b32663 failed undeclared-import-audit: three
module-level `markdown_it` imports did not map to the declared distribution
`markdown-it-py`. Local exact-head reproduction returned 1 with the same three
findings. Per cp-orch mailbox 36524, only the IMPORT_ALIASES table gained
`markdown_it: markdown-it-py`; no audit logic changed. The audit's committed
selftest still detects its planted undeclared requests import and accepts its
clean tree; actual corrected tree audit passes (519 files, 5 names, 0 undeclared).
Lint/type/core/budget/parity quick checks pass. Dependency-audit selftest/audit
were confirmed rc0 by orchestrator on the prior head; this worker's first
foreground invocation timed out and is not counted, so a detached check is
pending. Import changes now include both audits in the quick-check set.

The queued full gate was cleanly cancelled BEFORE its suite started: owned
timeout signalled TERM, durable completion exit143 at 16:05:21Z, job
b32a0435-2898-4b8a-892f-c91b715178a8. It proves no gate result and is not counted.
The corrected head will receive the one authorized replacement full gate.

<!-- lanes-demonstrated run=239ea5cdda114e6d9e1ec9bbb4267b3f plan=96a716edde2df678a72a3b158f5d22c22e7abba01afd3c06ccc43472a90b7023 -->

## Run 3 - speckit-context row

| Lane | Result | Test or observation |
|---|---|---|
| Checkout | passed | Real rendered-block tests own normal Git checkouts and linked worktrees |
| Harness | passed | Fixture HOME stable helper path executes the real checker, including direct source symlink for generated/changed contexts; delegated Codex families remain unpackaged |
| Driver | passed | All three actual generated drivers execute the block and satisfy the documented ordering contract |
| Coordination | not run | Not applicable: no coordination behavior change |
| CI provider | not run | Not applicable: no provider/status reader change |
| Project state | passed | Ordinary absent context, actual rendered source-bearing context, changed source, unavailable checker |
| Toolchain version | not run | No version-policy change; installed runtime exercised, no matrix claim |
| Clone shape | not run | Not applicable: no implementation history dependency |
| Run location | passed | Ordinary real-checker calls from CPP root and fixture target cwd; generated-context calls use --root . from verified fixture main/linked targets |
| Gate target | not run | Not applicable: no finish-runner interpreter policy change |
| Wave role state | not run | Not applicable: no role lifecycle change |
| Reader: speckit checker | passed | Real renderer produces the fetched body; real checker consumes the unique body file and source under target root |
| Reader: parent planning session | not run | Live semantic compliance not claimed; actual generated text and committed missing/late-read controls pin source-read-before-prompt instructions and canonical state reference |
| Reader: parity and procedure tests | passed | Actual run-policy entries and generated commands; removing one driver's call reports exactly that missing pair |

Final actual-driver/parity regressions copied into detached pre-fix main
cd6d2b48: **54 failed in 2.05s**, because context wiring is absent or the parity
rows remain exempt. After the source addition, real helper and broader
vendor/driver/budget suites report **412 passed in 22.23s**. The checker itself
is unchanged. Caller controls exercise failed empty/partial fetch (STOP before
checker), real ordinary/current/changed states, two distinct body files,
allocation failure before fetch, and missing checker reported unchecked rather
than absent. The committed unchecked-fetch control also executes: a failed fetch
falls through to the real checker and falsely returns absent/exit 0, proving the
failure signal differs from an examined ordinary issue.

The procedure controls contain good, unchecked-fetch, fixed-body-file,
commented-checker, missing-checker, missing-source-read and late-source-read
cases. They pin a literal Markdown/Bash procedure grammar, not arbitrary shell
semantics or a live model obeying it. The real-driver tests consume full actual
rendered commands, separately from those small discriminating fixtures.

Words: codex 8669 -> 8768, qwen 9883 -> 9982, gemma 10492 -> 10591, +99 each.
Existing headroom absorbs 20/22/22; caps rise 79/77/77 to exact current counts,
under owner ruling 7065030917 (executable gate step). No unrelated prose grows.
Only the shared core is edited as source; generated regions were written by
make delegated-core-write. Three speckit entries now run, and citation hints
were refreshed by finding their unchanged text in actual generated documents.

Lint, typecheck (515 source files), vendor, budget, driver parity, binary guards,
negative-fixture checks and both import-audit paths (selftest plus real tree)
pass. The import selftest reports its planted import and stays silent on its
clean pair. Refs #1811 only. Merges stay frozen until #1870; after it lands this
branch must merge main, recheck and re-gate before orchestrator merge.


<!-- flow-run n=4 id=f035e5fd6e3149d7936f5326621f165a -->
## Run 4 - pre-child live/claim/stale trio

Approved mailbox 36784, confirmed 36887; base 78749847. Parent checks now run
after approval/before first child; stale check starts Step 6; live guard before
each fix, with claim recheck for uncertain ownership. Confirmed own dirt alone
may be checkpointed then guard rerun clean; unexplained dirt or persistent
suspected stops. Own-only release before deletion; leave-for-review keeps claim.
Nine parity pairs run. Only shared TEMPLATE is edited; renders are generated.

<!-- lanes-demonstrated run=f035e5fd6e3149d7936f5326621f165a plan=bc3b78ae0d6c8f3288490db4b43fe397a4c975d18949e4223512d3fc581e413c -->
| Lane | Result | Evidence |
|---|---|---|
| Checkout | passed | Real fixture-owned main checkout and linked worktree helper calls. |
| Harness | passed | Claude install stable helper path fixture and generated documents; Codex install delegated drivers are intentionally not packaged (not applicable). |
| Driver | passed | /flow:auto (Claude implements) unchanged; delegated drivers (/codex:auto, /qwen:auto, /gemma:auto) actual renders and real parity policy. |
| Coordination | not run | No Kyle/no-Kyle authority behavior change. |
| CI provider | not run | No status/provider logic change. |
| Project state | passed | A repository that has adopted a feature's file or record / one that has not: clean/own-dirty/mixed foreign dirt; self/held claims; current/collision/unknown stale state. |
| Toolchain version | not run | Installed runtime and pinned CI only; no matrix. |
| Clone shape | not run | No new clone/ref-resolution behavior. |
| Run location | passed | Invoked from the CPP root / from another directory: literal target path while helper caller is elsewhere. |
| Gate target | not run | Parent helper checks do not alter runner interpreter selection. |
| Wave role state | not run | No wave lifecycle change. |
| Reader: parent session | not run | Live model compliance; documented ordering/verdict policy is tested against actual rendered text and committed bad cases. |
| Reader: rendered command tests | passed | Execute actual extracted Bash calls against real helpers in fixture-owned repositories. |
| Reader: parity checker | passed | Nine real run-policy entries and one missing-call control per driver/helper. |


Final regression suite on detached pre-fix 78749847: 63 failed, 164 passed.
With the change: 227 focused procedure/parity tests and 496 broader helper/
driver/vendor tests pass. Fourteen committed document inputs distinguish good
from late/missing/commented calls, suspected/held proceed, mixed-dirt sweep,
missing review renewal, foreign release and before-approval/late-stale/late-fix/
late-release ordering. These pin a literal procedure grammar, not arbitrary
shell semantics. Mixed own/foreign execution proves real guard stays suspected;
parent STOP/no-sweep obligation is separately a documented-policy assertion.
The fixture performs no checkpoint in that case: HEAD, index and foreign bytes
remain unchanged. It does not establish live parent compliance. Real helper
suites own held/foreign claim and stale collision/unknown behavior.

Exact words/caps: codex 8768 -> 9060; qwen 9982 -> 10274; gemma 10591 -> 10883
(+292 each), executable gate steps under owner ruling 7065030917. Private copy
of 100 documents passes unchanged and rejects one extra word in each driver
(9061, 10275, 10884). Existing committed budget controls retain bad/good cases.
Lint, typecheck (516 files), vendor, parity, budgets, binary guards, negative
fixture checks and import selftest plus actual tree audit pass. Import selftest
finds its planted import and is silent on the clean pair. No helper behavior
or output format changes. Refs #1811 only; other rows remain outstanding.

Run 4 independent review pass 1 found two LOW test-adequacy findings, both
accepted and addressed. Actual helper commands now execute through a
fixture-owned HOME populated by the supported flow-helpers installer, retaining
the literal tilde path and executable permission check. Missing and
non-executable installed helpers return 127/126 rather than repository-fallback
success. Every negative procedure input now asserts its exact failing-check set;
the missing-renewal input retains the independent quality-gate ordering marker.
These additions fail 13 cases before the test-harness/control corrections
(67 others pass), then all 239 procedure/parity cases pass after correction.
The earlier 496-test broader result remains the pre-review checkpoint result;
final broader verification and review pass 2 follow this correction. No product
procedure or cap changed in response to these test findings.
