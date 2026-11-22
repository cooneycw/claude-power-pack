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

Final Run 4 checkpoint cb544e0e: 508 broader tests pass (including real supported
installation), 239 procedure/parity tests pass; pre-fix 78749847 yields 75 failed
and 164 passed. Lint, typecheck, vendor/parity/budgets and import selftest/actual
scan pass again. Independent review pass 2 is clean. Final runtime-derived
receipt 2026-11-21T191918Z-issue-1811.json records two passes, two accepted LOW
findings, none rejected/deferred. Red-case groups across both passes: 10 plus 9
proposed; 9 plus 9 already covered when proposed (the first renewal control was
masked, corrected before pass 2). Final pass's nine groups are all covered.
No product changes followed the clean second review; remaining full finish gate
and exact-head CI are reported separately rather than implied by this evidence.


## Post-child guard pair

<!-- lanes-demonstrated run=03776eb0b3d5448a9ab2d99b0e00cb74 plan=5e74129bebf837f3bd5235f58668c13af39847d2b44cd1dfa7fa5b437efe38ae -->

| Lane | Result | Evidence |
|---|---|---|
| Checkout | pending | Existing worktree guard / ignored-additions temporary layout cases queued. |
| Harness | passed | delegated-core-check matches three actual Claude renders; parity reads generated Codex flow-auto mirror, delegated families intentionally unpackaged. |
| Driver | passed | Actual three main renders red: 3 failed, 4 passed via make test in 0.86 seconds. Inserted guards: 7 passed in 0.89 seconds. Missing and after-first-commit committed cases distinguish broken placement. |
| Project state | pending | Existing ignored-addition cases queued. |

Owner/orchestrator approval mailbox 36767; exact budget conflict rule 36773.
Touched-but-unplanned: templates/delegated-driver-values/codex.md, qwen.md and
gemma.md, approved mailbox 36860. Their FIX_REEXEC slot was split so the shared
guard runs before the delegated-run-check payload read. Codex also tailed the
output first: mailbox 36863 approved closing/reopening only its bash fence to
move the unchanged tail after the shared guard. Qwen/Gemma have no such tail.
No invocation, sandbox, exit capture, payload-check command or flag changed.

A removal check against unchanged main dbb485d4 reconstructed all three original
driver byte strings exactly after stripping only the three inserted guard/text
blocks (plus Codex's new closing/opening fence delimiters). No prose was trimmed.
Counts use check-claude-md-budget.py's len(read_text().split()) method:

| Driver | Before | After | Delta | Old cap | New cap |
|---|---:|---:|---:|---:|---:|
| codex | 8669 | 8886 | 217 | 8689 | 8886 |
| qwen | 9883 | 10098 | 215 | 9905 | 10098 |
| gemma | 10492 | 10707 | 215 | 10514 | 10707 |

Raises use owner ruling (f), executable gate step, approved mailbox 36863.
Codex's two extra words are fence delimiters; only exceeded caps were raised.
Driver parity: 24 items, 72 pairs, 0 missing. Budget and lint checks passed.


First independent gpt-6.2-sol captured-patch review accepted two findings:
Step 5 ran after Step 4 had already processed child results, and a command
between a guard invocation and case $? could erase its STOP verdict while the
placement predicate passed. The committed overwritten-status input reproduced
the latter red: **1 failed, 7 passed** in 0.72 seconds. The initial-child
boundary assertion plus that case red: **7 failed, 4 passed** in 0.92 seconds;
the Step 4 region was still byte-identical to unchanged main at that point.

Mailbox 36875 approved identical non-generated Step 4 strict guard insertions
immediately after captured child exit, before all payload/tail/overrun readers.
The existing two-region vendor cannot own the middle of each driver-specific
invocation fence. An equality test prevents these three blocks drifting.
The predicate now binds each invocation directly to case $? in the same bash
block and checks its actual branches; both guards have committed overwritten
status inputs. Corrected cases initially passed **12 tests in 1.24 seconds**.
Step 5's precheckpoint guard and Step 6/7 guards remain.

Extended removal check strips four guard insertions plus Codex fence delimiters
and reconstructs all three original renders byte-for-byte. Final counts so far:
codex 8669 -> 8928 (+259), qwen 9883 -> 10140 (+257), gemma 10492 -> 10749 (+257).
Caps equal those counts under owner ruling (f), mailbox 36875. No existing
command/flag or prose instruction was removed.

The first detached quick run completed exit 0 at 18:56:55Z: **277 passed in
17.26 seconds**; lint/type/binary/budgets/parity, both audits and both registered
worktree controls passed including provenance. Dependency audit: 43 packages,
zero gating findings, two Windows-only pins not audited on Linux. Its tests
started before the final Step 4 correction; corrected-head checks follow.


Pass 2 found adjacent bash fences were concatenated by the test reader, so
a guard and its case $? in different shells were accepted. Mailbox 36895
authorized one pass 3 and a hard stop afterward. Committed split-fence BAD
inputs for both guards failed before the reader correction: **2 failed, 13
passed** in 0.93 seconds. A first delimiter edit rejected the GOOD fixture
(**2 failed, 13 passed** in 0.97 seconds); retaining line breaks around the
separator corrected it: **15 passed in 3.70 seconds**. Lint and type passed.

Final pass 3 found no driver-text defect. Two further TEST-reader limitations
are deferred under mailbox 36895, without executing new mutations after the
hard stop: case-arm presence does not reject an earlier shadowing arm; and
the before-commit position check and valid-block lookup can identify different
command occurrences. Both current driver blocks are correct. Separate records
after resolver verified the open Nit Store (source search):
https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7067714178
https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7067714377

Receipt producer refused the original review transport as UNKNOWN: the exact
diff was appended to prompt prose, not sent as bare diff or in its supported
cpp-review-patch frame. Runtime transcripts are retained unchanged. Escalated
this evidence error to the orchestrator in mailbox 36908; no receipt claim or
additional review until disposition.


Evidence recapture authorized mailbox 36909 counted as pass 4 (raised cap 4),
on the same 13bc0c47 artifact. scripts/codex-review-run.sh supplied the exact
canonical patch and returned CODEX_REVIEW: ran, actual reviewer codex/gpt-6.2-sol,
diff-only, network unverified, local repository credentials absent. A private
PATH shim selected that model and disabled reviewer shell tools; sandbox probes
delegated unchanged. The runtime transcript was never edited.

The new LOW fallback-presence TEST-reader limitation was deferred under the
same hard stop; current driver blocks retain the fallback. Proposed deletion
mutation was not executed. Recorded separately after Nit Store resolver:
https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7067747358
The other recapture finding requested exact-artifact evidence for existing
lane checks; addressed with the final quick run on unchanged product code.

Final quick run on evidence head 6aa7e9e2, whose product content equals reviewed
13bc0c47, completed at 19:06:14Z: **285 passed in 19.02 seconds**. Lint, type
(515 files), binary guards, budgets, vendor/parity, both audits and both worktree
controls including provenance passed. Audit selftests found their planted bad
inputs and accepted clean inputs; dependency audit had zero gating findings
across 43 packages and two Windows-only pins not audited on Linux.

| Promised lane | Final evidence |
|---|---|
| Checkout | Passed: test_a_clean_main_is_NO_LEAK_exit_0 plus registered clean-linked, bad-main-checkout and bad-git-cannot-answer control cases; leak control distinguishes fresh leak from clean/stale overlap. |
| Harness | Passed: make delegated-core-check checks all three actual Claude renders; make driver-parity-check builds/reads actual Codex flow-auto mirror. Delegated families intentionally unpackaged; no live Codex installation claim. |
| Driver | Passed: actual codex/qwen/gemma render tests and equality check; committed missing/late/overwritten-status/split-fence cases distinguish bad input. |
| Project state | Passed: test_clean_repo_is_silent, test_warns_on_ignored_source_file, test_strict_exits_nonzero_on_finding and test_ignored_addition_in_a_linked_worktree_blocks exercise actual helpers in owned repositories. |

Derived schema-5 receipt: accepted 4 (three code/test findings and exact-artifact
lane evidence), rejected 0, deferred 3, passes 4 with cp-orch 36909 escalation.
Pass 3 was substantive; pass 4 recaptured binding after the unframed input
error. No code changed after pass 3. Waiting for #1878 to land before main merge
and this row's full gate.


Administrative merge/restamp, cp-orch mailbox 37075, executed after 37124:
upstream Run 3 and Run 4 were preserved verbatim. Own stable run-id
03776eb0b3d5448a9ab2d99b0e00cb74 moved from original ordinal 3 (interim 4)
to free ordinal 5. Only the own flow-run n marker and Run heading changed in
the plan; reversing that transformation reproduces the original 13bc0c47
plan section byte-for-byte. Section A/B/C body and lane promises are unchanged.
This is the single approved administrative re-approve, not a new substantive
plan or new approval invented by the implementer. Original baseline:
444ad53619e5cdf21878849c2ba9adbd4bf84cfcdd091d2c435c144dc9455df0.
Restamped baseline and own lanes marker:
5e74129bebf837f3bd5235f58668c13af39847d2b44cd1dfa7fa5b437efe38ae.

Merged main 030f280c as d9975273, preserving pre-child and speckit additions.
Template regenerated; stripping only our four insertions and Codex fence
delimiters reconstructs all three NEW main renders exactly. Final measurements
using the checker method, old/main -> merged cap:
codex 9060 -> 9319 (+259), qwen 10274 -> 10531 (+257),
gemma 10883 -> 11140 (+257). Caps equal the merged counts; owner ruling (f).
No pre-existing instruction or other worker's driver change was dropped.


Final-main quick refresh on 1e2b4d6c/main 030f280c completed exit 0 at
20:25:18Z: **437 passed in 42.96 seconds**, including post-child, pre-child
and speckit rendered-driver regressions and actual helper suites. Lint/type,
binary guards, budgets, vendor/parity, both audit selftests/actual and both
worktree controls with provenance passed. Receipt enrolment accepts the
escalated four-pass receipt (private 11). No new review or product fix.


The first final-main full gate on beea5b4c failed at test: **6 failed, 13404
passed, 4 skipped** in 855.98 seconds, finished 20:49:12Z. This is a real
integration red, not a queue timeout. Three pipeline-reader tests mistook Bash
4|5) status alternatives for a command pipeline. Three backstop tests selected
the first Step 7 bash fence, now a guard, and failed before the backstop reader.
Mailbox 37164 authorized only these two existing-reader corrections as gate
feedback; no driver text or deferred-reader fix.

Committed GOOD numeric-case and BAD real-run-pipeline inputs, before correction:
**7 failed, 61 passed** in 20.32 seconds (the six originals plus GOOD). Direct
reader verdicts: before GOOD FAIL/BAD FAIL; after GOOD PASS/BAD FAIL. Numeric
status alternatives are excluded only in active case syntax; a command pipeline
inside such an arm and a numeric-looking alternative outside a case remain
findings. Backstop selection now requires exactly one actual backstop marker
in Step 7, with committed missing/multiple refusal tests and a positive case
that ignores an earlier guard and a same-named Step 8 marker.

Corrected three relevant modules: **89 passed in 6.80 seconds**. Lint and type
(518 files) passed. Both integration files are touched-but-unplanned under
mailbox 37164: tests/test_delegated_lane_failure_detection.py and
tests/test_delegated_overrun_base.py. Driver render bytes/caps unchanged.


Integration quick refresh completed exit 0 at 20:53:50Z on 11dc8164:
**511 passed in 42.52 seconds**,
including both corrected existing readers and all post/pre-child/speckit
checks. Lint/type, budgets, binary guards, vendor/parity and both audits passed.
Both worktree controls passed all GOOD/BAD cases and the blind-anchor checks.
Provenance distinction: historical anchor reports ok; the constructed leak
anchor reports unverified, not a verified historical-provenance claim. This
clarifies earlier shorthand saying both control provenance checks passed.
Receipt enrolment accepts existing four-pass receipt (private 11); mailbox
37164 therefore requires no fifth review for the integration correction.

<!-- lanes-demonstrated run=886f56f62f81479da3e05c5b76a2b489 plan=8f43b67a87c4b148ae8a05f7a4f3648d9e93a3d21c66180a610ca4b3bd27b35d -->

| Lane | Result | Evidence |
|---|---|---|
| Checkout | passed | tests/test_delegated_nit_store_routing.py executes actual published blocks in main checkout / linked worktree fixture-owned repositories. |
| Harness | passed | Actual Claude install-shaped helper symlink exercised; delegated Codex skills do not exist. Live model obedience not covered. |
| Driver | passed | All three actual rendered delegated documents and existing canonical flow routing tests: 373 related tests passed. |
| Project state | passed | Real resolver with open/absent/ambiguous/transport-failed store and missing installed helper. |
| Toolchain version | passed | Host runtime and restricted PATH without python/python3, absolute test-stub interpreter. Pinned CI result pending, no broader matrix claim. |
| Run location | passed | Actual installed block outside the target, including renamed linked worktree caller. |
| Gate target | passed | Owned consumer repository/isolated PATH; CPP source and generated outputs checked. |
| Reader: generated-command parent | not covered | Presence and scope/order controls only; live model obedience not established. |
| Reader: parity checker | passed | Actual generated documents and updated ledger through tests/test_driver_parity.py. |
| Reader: resolver output consumer | passed | Actual published block and real helper verdict output; subsequent live model branching not covered. |
| Reader: GitHub and closing report | not covered | Fake GitHub network boundary only; controls pin repo/context/refusal/closing-link instructions, not live posting. |

Regression evidence: on current-main pre-fix baseline all 102 new cases failed because retention/routing and the bare call were absent. Same cases passed after the shared-core change. Related resolver/routing/vendor/parity selection: 373 passed. Budget, Bandit live known-bad/clean selftest and undeclared-import planted/clean selftest passed. No unrelated findings recorded at this checkpoint.

Rendered word counts on the integrated base: codex 8768 -> 8966; qwen 9982 -> 10180; gemma 10591 -> 10789. Each delta and cap increase is exactly 198 words for the executable gate step under ruling (f). Counts will be re-derived after final main integration. Full finish gate, review and exact-head CI pending.

Independent review completed on checkpoint 08cb158b: codex/gpt-6-astra against runtime-derived codex/gpt-6.1-sol, no findings. The reviewer independently reproduced 102 failures with pre-fix actual driver documents and 373 passing related tests at HEAD, and checked prior instructions byte-preserved. Generated full-scope runtime-HEAD-bound receipt: docs/measurements/counter-model/2026-11-21T201910Z-issue-1811.json. Eight committed negative procedure controls already cover the review's named malformed-input cases; no additional cases requested. Network open and local credential presence unknown; no live external writes or model-obedience evidence claimed. Full gate and CI remain pending.

Final-main integration administration (approver cp-orch, mailbox 37078 and GO 37235): upstream Runs 3, 4 and 5 preserved verbatim. Only this run's header/marker ordinal changed from 4 to 6 in the record and as-read snapshot; its approved body is unchanged. Per that authority, performed the single header-only administrative re-approve after integration. Preliminary gate at 84a5e1b3 passed (13409 tests passed, 3 skipped); it is signal only, not final merge evidence. Final post-integration gate and enrolment pending.


<!-- lanes-demonstrated run=886f56f62f81479da3e05c5b76a2b489 plan=b390bb7fbf40dd08530e67f319e8ff1c57a0f426d609af6ef700abeb6cf44adf -->

| Lane | Result | Evidence |
|---|---|---|
| Checkout | passed | tests/test_delegated_nit_store_routing.py executes actual published blocks in main checkout / linked worktree fixture-owned repositories. |
| Harness | passed | Actual Claude install-shaped helper symlink exercised; delegated Codex skills do not exist. Live model obedience not covered. |
| Driver | passed | All three actual rendered delegated documents and existing canonical flow routing tests: 373 related tests passed. |
| Project state | passed | Real resolver with open/absent/ambiguous/transport-failed store and missing installed helper. |
| Toolchain version | passed | Host runtime and restricted PATH without python/python3, absolute test-stub interpreter. Pinned CI result pending, no broader matrix claim. |
| Run location | passed | Actual installed block outside the target, including renamed linked worktree caller. |
| Gate target | passed | Owned consumer repository/isolated PATH; CPP source and generated outputs checked. |
| Reader: generated-command parent | not covered | Presence and scope/order controls only; live model obedience not established. |
| Reader: parity checker | passed | Actual generated documents and updated ledger through tests/test_driver_parity.py. |
| Reader: resolver output consumer | passed | Actual published block and real helper verdict output; subsequent live model branching not covered. |
| Reader: GitHub and closing report | not covered | Fake GitHub network boundary only; controls pin repo/context/refusal/closing-link instructions, not live posting. |

After integration with main 34c417f9, repeated the related selection successfully. Budget and both audits/selftests also passed. The rows above apply to the header-only re-approved plan; their evidence and limits remain the same. Final caps: codex 9517, qwen 10729, gemma 11338, exactly +198 each versus integrated main. Receipt enrolment selected the existing receipt (documented receipt disposition, exit 10); no new review pass requested. Final full gate still pending.


<!-- lanes-demonstrated run=6f7f7f0788e9450abfb2e44acad594e8 plan=8e30907014bc8eeb417efb41ff0d0aea21e1e0238665a5b403443701b6688925 -->

## Declare-salvage row D

| Lane | Result | Evidence |
|---|---|---|
| Checkout | passed | tests/test_delegated_salvage.py executes actual conditional block in fixture-owned main checkout and linked worktree. |
| Harness | passed | make delegated-core-check reads actual Claude renders; make driver-parity-check builds/reads generated flow-auto. Delegated meta drivers intentionally unpackaged; no live install claim. |
| Driver | passed | All three actual rendered Step 3s exercised; existing tests/test_flow_plan_record.py, tests/test_flow_plan_record_runs.py and tests/test_flow_plan_compliance.py exercise flow-auto/helper procedure. No live model obedience claim. |
| Project state | passed | New empty/ancestor/invalid/nonancestor/ambient cases plus actual helper/approval records; existing compliance salvage cases. |
| Run location | passed | External consumer fixture roots execute actual block; CPP root runs real renderer/parity/budget checks. |

Reader evidence: actual generated blocks feed the real helper, declaration
record and approval baseline, with fixture-owned identities and an explicit
interpreter. Negative cases abort before the approval sentinel; empty/ambient
cases produce no declaration output and leave the record unchanged. Child
commit fence is unchanged and pinned. Existing helper/compliance suites read
actual salvage records. Rendering/parity/budget read real files. External
install/model behavior remains unexamined.

On unchanged main 34c417f9: **33 failed, 5 passed**; all three new driver
regressions and executed-block cases fail the missing declaration contract.
After implementation: **38 passed**, and broad focused/helper suite
**385 passed in 17.68 seconds**. The detached job recorded exit 0 and successful
completion/notification. Committed good control is accepted; missing, late,
unconditional and child-owned-commit controls are rejected with asserted
negative preconditions. These test a narrow document grammar and actual shell
blocks, not a live parent's interpretation.

Integration correction: the initially approved +93-word block put `|| exit $?`
on the helper line. Actual driver-parity rejected this as a non-plain shell
construct. The helper invocation is now plain, with its status captured and
checked on separate lines; every nonzero still stops with that original
status before approval. This costs +6 words per driver, approved by cp-orch
mailbox 37295. Total **+99 words per driver, executable gate step**, under
owner ruling 7065030917. No checker or stop semantics weakened.

Main-ready mailbox 37307 authorized integration of row A / #1883. Rebased
onto main 2ede561d before minting this run. Only TSV conflicted; rendered
files were regenerated and counted, not chosen from a conflict side.
Exact upstream counts 9517 / 10729 / 11338 become caps/counts
**9616 / 10828 / 11437** for codex / qwen / gemma. Existing upstream run
sections preserved; this late run received next-free ordinal 7, so no
header renumber or administrative re-approval was needed. The original
baseline is 8e30907014bc8eeb417efb41ff0d0aea21e1e0238665a5b403443701b6688925.

No touched-but-unplanned product files. Row E remains in its own untouched
worktree and follows this row's merge. Review, receipt, full finish gate,
push scans and exact-head CI are pending this checkpoint; later evidence will
record their actual results. `--raised-cap` on the receipt writer controls
review-pass escalation, not document word caps; no such escalation is used.


### Row D review pass 1 corrections

The branch review helper measured reviewer `codex/gpt-6.2-sol`, scope
`diff-only`, network `unverified`, credentials `absent`; `CODEX_REVIEW: ran`.
Both LOW findings are accepted and corrected without changing driver text:

- The late declaration fixture also broke the begin-run boundary. It now
  isolates `begin-run -> approve -> declaration`; a separate early fixture
  isolates `declaration -> begin-run -> approve`. The narrow contract asserts
  each boundary separately and requires each fixture to fail for its named
  reason.
- Whole-document commit-command matching could accept permission or text
  outside the child prompt. The checker now locates Step 4's execution fence,
  requires the MUST NOT section and finds the commit/ref prohibition inside
  it. Committed good, permission and outside-prompt controls preserve the
  command phrase while proving the policy distinction.

Before corrections the new controls produced **3 failed, 5 passed**. After
corrections all **42 driver cases passed in 5.68 seconds**. Fixture-only
scope variance: `before-begin-run.md` and `fence-{good,permission,outside-prompt}.md`
under the already approved fixture directory were added to pin these findings.
Approved plan body unchanged; no production helper/fence/policy changes or
further cap increase. A first `make dep-audit` attempt hit the command tool's
10-second limit and is not counted as a pass; rerun will be detached with the
final gate/scans job. The audit's actual Makefile target is `dep-audit`, while
its script and CI step are named dependency-audit.


### Row D review pass 2 corrections and evidence clarification

Pass 2 used the same measured different reviewer model and diff-only scope.
Four LOW findings are accepted. The completed corrections are:

1. Approval-reader evidence now verifies the actual stamped baseline digest
   against the real current run section containing the selected salvage SHA.
   The selected-ancestor case also runs actual compliance, requiring its
   salvage-union diagnostic and agreement. This is a new assertion over real
   helper output, not a claim that the unchanged helper previously failed.
2. Empty selection now starts with only the original base commit, asserted by
   its commit count; no explicit preservation checkpoint exists. Ambient SHA
   contamination uses ordinary history rather than a commit described as
   explicit preservation.
3. `fence-contradiction.md` retains MUST NOT and grants commit permission in the
   same fence. The narrow policy check now rejects commit/push in its permission
   section as well as requiring the prohibition inside the Step 4 prompt.
4. Harness/CPP-root evidence comes from separately executed verification, not
   new shell-regression cases. Existing automated tests actually run in the
   385-case suite include
   `tests/test_delegated_core_vendor.py::test_real_repo_drivers_match_the_canonical_core`,
   `tests/test_delegated_core_vendor.py::test_rendering_the_real_repo_is_idempotent`,
   `tests/test_driver_parity.py::test_repository_driver_parity`, and
   `tests/test_driver_parity.py::test_real_generator_preserves_flow_membership_and_leaves_delegated_families_unpackaged`.
   The Make checks also executed from the CPP root separately. None establishes
   a live installed delegated model run; those remain not covered.

New empty-history/contradictory-permission checks first returned **7 failed,
2 passed**, then all **43 driver cases passed in 4.76 seconds**. Lint passes.
Only tests/fixtures and this evidence changed; production text/caps remain
+99 words per driver. The extra contradiction fixture is another disclosed
control added under the approved fixture directory. The approved body remains
unchanged; the existing compliance report transparently names extra fixtures
as touched but not planned. No clean-review claim is made. A third review
requires explicit orchestrator approval because the two-pass default is spent.


### Row D final review and recorded limitations

cp-orch mailbox 37365 authorized pass 3 on the corrected head with reviewer
continuity and a hard stop after it. The receipt records the reason and
cp-orch authority in `extra_pass_reason`; escalation flags reserved by the
writer for passes beyond 3 are intentionally omitted. Pass 3 again measured
`codex/gpt-6.2-sol`, diff-only, network unverified, credentials absent. No
product/driver-text defect was reported. Two LOW test-adequacy findings remain,
recorded separately as instructed rather than extending the review loop:

- Explicit-preservation prerequisite/selected-SHA prose is present in the
  driver but not fully pinned by the narrow policy assertions:
  https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7070332671.
- Exact existing case/command references for three variants are in this
  evidence rather than directly linked from the immutable approved lane rows:
  https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7070332869.

Receipt `docs/measurements/counter-model/2026-11-21T223921Z-issue-1811.json`
derives both identities from native runtime evidence, binds the reviewed
artifact and records 3 passes / 6 fixed findings / 2 deferred findings. It is
not a clean-review claim. There is no fourth pass.

The live dependency audit passed: planted vulnerable fixture reported
3 advisories and clean fixture none; actual project examined 43 packages,
0 gating findings and 0 stale suppressions. Two Windows-only packages are
not audited on Linux, stated by the audit. Undeclared-import audit/selftest
passed earlier; repeat before push. Pinned gitleaks 8.30.1 downloaded into a
private temporary root and checksum verified against its release checksums.
Full finish gate and exact-head CI remain pending; their actual results will
be appended after execution. Approval stability remains unchanged; file-set
compliance transparently reports the five added review controls, not agreement.


### Row D finish admission attempt 1

The audited wrapper ran under the normal account HOME with ADDOPTS unset,
private short TMPDIR, current-checkout receipt helper and the real Kyle
admission client. Own-slot job 284d3790-7ba4-446d-b5a4-11a87324b356 published
actual terminal completion and notification successfully.

It did **not** acquire admission within the configured 600 seconds. Queue
position moved from 4 to 1. Exact verdict:
`FLOW_FINISH_GATE: fail (coordination not granted: no grant within 600s, last state queued (kyle-lock exit 10), no gate work started)`
with `FLOW_FINISH_GATE_EXIT=1`.

No lint/test/security/verify gate work started, so this is neither a full-suite
pass nor a product test failure. No product changes are proposed in response.
A new wrapper attempt requires a new own-slot job/ticket and orchestrator
instruction under the one-heavy-run rule; request is for a longer admission
wait, with admission still enforced. No push/PR yet.

Pre-push scan evidence completed before this attempt: undeclared-import audit
and live selftest pass; dependency-audit live positive control detects its
planted advisories and project scan passes with its stated Windows-only
exclusions; gitleaks 8.30.1 (checksum verified) git --log-opts=HEAD scans
1032 commits / about46.35MB and returns0. The same pinned binary, same
repository config and same git --log-opts=HEAD mode were also exercised
against isolated committed copies of existing secret-scan fixtures: relocated
bad-private-key returns1 with a leak diagnostic; good-clean returns0. No
sensitive finding content was printed. Command budgets pass at the exact caps.


### Row D owner-paced cancellation before gate work

Mailbox 37410 authorized a replacement admission attempt with a 3600-second
wait and 90-minute deadline. Own-slot job d901cfc7-47e2-4975-9026-1782b230920b
queued without starting gate work. Mailbox 37423 then relayed the owner rule:
at most one heavy local gate from this group, and no start while load5 > 24.
Observed load5 was 34.53, so the queued attempt was withdrawn.

Cancellation detail: the authority cancelled queued request 1201, but the
waiting `kyle-lock run` client intentionally reacquired under a new request,
1203. The verified owned waiting client was then stopped with SIGTERM and
withdrew that request itself. Authority confirmed it was already cancelled;
subsequent status showed no queued request or holder for this session. No
other holder was signalled. No gate work started. The wrapper reported
`FLOW_FINISH_GATE: fail (coordination supervisor exited 143 and the gate recorded no status)`
and exit1; own-slot terminal completion/notification succeeded. This is an
owner-directed pre-work cancellation, not a product test failure or evidence
of a passing gate.

A passive, self-notifying load watcher waits for load5 <= 24. Before the one
replacement authorized by mailbox 37423, recheck load5, confirm the group has
no other heavy run, and launch with the same admission/deadline parameters.
Admission remains enforced. Apply the same pacing check to row E later.
No push/PR until a permitted gate verdict and final-HEAD scans.


### Row D first admitted full gate and compatibility corrections

Owner-paced launch observed load5 **19.99**, below the owner limit24;
admission granted full-suite request1205, and the real wrapper accepted the
committed native receipt. The security scan examined2984 source files,
blocked0 CRITICAL and warned5 HIGH (existing test fixtures); it continued.
The runner deferred lint/test/typecheck to their direct verify prerequisites.
`make verify` reached its real tests and stopped there:
**70 failed, 13493 passed, 4 skipped in 536.42 seconds**.
Exact wrapper result: `FLOW_FINISH_GATE: fail (at prerequisite test)`, exit1.
No pass, push or CI claim is made.

Diagnosed integration causes and completed corrections:

- Existing `controls/delegated-plan-lanes/run-case.py` rejects a new helper verb
  before exercising any existing approval/compliance/product controls. It now
  accepts only the exact published empty-SHA conditional salvage block, which
  makes no declaration for these fixtures. Selected or malformed blocks remain
  unknown. The committed `unsupported-ambient-block.md` and its test require
  the named unsupported-salvage diagnostic, not merely any nonzero exit.
  Actual selected/invalid salvage execution remains owned by the new shell
  tests; this control does not claim to interpret arbitrary conditions.
- The test skip guard used `any(shutil.which(tool) ...)`, which works at runtime
  but is not recognized by CPP's static binary-guard instrument. It now uses
  explicit `shutil.which("git")` and `shutil.which("bash")` clauses. The
  recognizer itself is unchanged.

After corrections **260 focused tests passed in 18.94 seconds**, covering the
new driver tests, the previously failing delegated-plan-lanes integration and
actual binary-guard suite. Lint passes. An initial focused command was cut off
by the command tool's10-second timeout; the completed result above comes from
its separately prepared own-slot job, not the interrupted run.

Touched-but-unplanned additions: the existing control runner compatibility
change and one named bad fixture/test are necessary integrations of the new
Step3 block. Driver text/helper/schema/caps are unchanged. The genuine native
receipt continues to describe its actual reviewed artifact; these later
compatibility corrections are tested but have no fourth model review, per the
orchestrator's explicit hard stop. The receipt is neither rewritten nor
represented as review of changes made after its report. A new full gate
requires orchestrator instruction and a fresh load5<=24 check.


### Row D authorized delta-only instrument review, pass 4

Mailbox 37518 explicitly raised the review cap to4 because the post-gate
compatibility correction changed an instrument. Scope was only the actual
diff from reviewed head a1ad48a6 to compatibility head1ece1cf6. The branch
helper consumed that canonical patch, measured reviewer codex/gpt-6.2-sol,
diff-only, network unverified and local credentials absent. No fifth pass.

Two LOW findings received explicit dispositions:

- Alternate whitespace can miss the salvage-specific comparison. The current
  generic fallback still rejects the helper invocation. A fixture-owned
  reproduction changed the call to two spaces and actually returned exit3,
  `DELEGATED_PLAN_LANES: unavailable - unsupported helper invocation`, before
  setup. It does not admit or silently omit the unsupported command. Rejected
  as a bypass claim; it changes which unknown diagnostic is selected, not
  unknown versus acceptance.
- A paired comment-only edit control for the exact-template boundary is
  absent. The parser deliberately reports template identity, not semantic
  salvage equivalence. This LOW test-adequacy gap is recorded at
  https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7070914642.

New genuine receipt `2026-11-21T233026Z-issue-1811.json` binds only that delta,
with passes4, raised_cap4, cp-orch authority, mailbox37517 reference and the
actual extra-pass reason. Delta dispositions are0fixed/1rejected/1deferred;
the original main-range receipt retains its6fixed/2deferred findings. Together
they establish what was actually reviewed; no fourth full review of the old
driver text is claimed. No product changes followed the delta review.

A separate supplemental pending-row issue was recorded without touching E:
https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7070887122
(the same loop-based skip marker in E is not statically recognized).

Mailbox37518 authorizes one fresh gate after this review, with freshload5<=24,
no other heavy CPP run, actual admission3600s and90-minute job deadline. The
PR will preserve the full history: gate1 queue timeout; gate2 owner-paced
cancellation before work; gate3 actual70/13493/4 integration failure, now fixed;
gate4 pending actual execution/result. The source and caps remain unchanged.


### Row D gate 4 final result

Own-slot job3e74d1eb-1b56-4b48-a1fe-7b3ba7cf79ab launched at freshload5
**17.26**; no other CPP gate was held/queued. It acquired real full-suite
request1206 and accepted the escalated4-pass delta receipt. It discarded the
old failed resumable state because the tree changed and started fresh.

Actual wrapper verdict: **`FLOW_FINISH_GATE: ok`**, **exit0**. Actual test
summary: **13564 passed, 4 skipped in 512.32 seconds**. The four skip reasons
were not emitted in the retained summary; this does not claim those cases ran.
`make verify` completed, including lint/typecheck as direct prerequisites;
the wrapper reported lint/test/typecheck subsumed by verify, rather than
pretending to execute them again. The deterministic security scan examined
2984 files, blocked0 CRITICAL and warned5 HIGH in existing test fixtures.
Negative controls, renderer, parity, exact word budgets and binary guards
completed under the full verification target. Completion and notification
both succeeded. The gate ran on source/evidence checkpoint b6e27d08; this
later commit changes only this issue's evidence, not tested source.

Verification is bounded by each check's printed population. Existing advisory
skill-coverage and behavioral-eval outputs are not promoted to clean coverage;
behavioral eval explicitly reported inconclusive. Static CI dependency/link
checks retain their stated exclusions. Live installed delegated-model
obedience remains unexamined. File-set compliance still reports seven extra
review/integration paths with its actual divergence verdict; approval stability
and issue-body drift are unchanged. These extra paths are disclosed in the PR,
not hidden by rewriting the approved plan.

Next: rerun the required pre-push budget/import/dependency/gitleaks checks on
this final evidence HEAD, push/open a Refs#1811 PR, and record exact-head CI.
The historical gate failures/cancellation remain preserved above and in the PR.


<!-- lanes-demonstrated run=3e3ef2b0d50a426497c1e7d49cf3b84b plan=f14ffde1f774a448cec82231372da1f01327c4662a24823b7cab8043067accd6 -->

## Finish wrapper row E, final merged-main run

This run was minted, began and received its approved plan on main bc7125e1
BEFORE any product edit or implementation commit. It received ordinal8 and
preserved every upstream run section. This avoids the default run-start scope
limitation documented for D. Original E checkpoint/first review remain
historical on their separate branch.

| Lane | Result | Evidence |
|---|---|---|
| Checkout | passed | test_delegated_finish_gate.py actual generated bare calls execute the real wrapper in main-checkout and linked-worktree consumer fixtures. |
| Harness | passed | Actual Claude renders, test_delegated_core_vendor.py real-repo/idempotent rendering cases and test_driver_parity.py generated flow-auto parity cases in801suite; live installs unexamined, delegated meta commands intentionally unpackaged. |
| Driver | passed | All three actual Step6 documents, real wrapper suite, current pre/post-child guard suites and real wrapper helper/controls in801suite; no live model obedience. |
| Coordination | passed | Existing wrapper tests include test_coordination_supervises_full_gate_once_only_when_enabled, test_coordination_refusal_starts_no_gate_work and other admission cases. Deterministic authority is stubbed; actual admission is pending own full gate. |
| Project state | passed | Real receipt writer rejects stale review bytes after committed implementation fix and accepts fresh review; existing wrapper enrolled/unenrolled cases, including test_enrolment_names_the_receipt_for_this_head_not_the_oldest. |
| Run location | passed | Actual bare calls from external consumer roots; CPP-root make delegated-core-check/driver-parity-check and their real-tree tests. |
| Gate target | not run | Partial: rendered consumer fallback cases pass; four real target-PATH/independent-venv probe cases now pass separately. Own CPP full gate is pending, so the full lane is not yet demonstrated. No consumer version matrix. |

Reader evidence is the actual generated call and actual wrapper/receipt-writer
output, with deliberately faulty installs clearly identified for no-verdict
and interruption scenarios. Narrow policy pins check the instructions a
parent receives, not an agent's real decision. Output records must be one
complete unambiguous verdict with matching exit; committed controls include
prefixed lookalikes, conflicts, status mismatch and trailer-only output.
Missing-verdict and stale-receipt policy fixtures are rejected; the good one
is accepted. Reader/producer formats are unchanged. External consumers and
live model obedience remain unexamined.

Current-main red before source edits: **60 failed, 9 passed**. After the
wrapper replacement: **69 passed in1.89seconds**. Initial broad current-row
integration then returned **6 failed,795 passed**: sibling placement checks
used the semantic boundary instructions `Run quality gates:` and `Re-run
quality gates`. The sibling guards themselves were intact. Restoring those
instructions in the wrapper preface and renewed-review tail cost net0 words;
no test instrument or guard was weakened. Final broad integration:
**801 passed in29.28seconds**, covering wrapper, current pre/post-child,
plan-lanes, renderer/parity and static binary-guard suites. Lint/render/parity
and all command budgets pass.

The source edit is surgical: old direct runner/fallback prefix and RUNNER_EXIT
retry/report tail only. Current stale guard, fix live/claim checks,
post-child guard and FIX_PAYLOAD_CHECK remain; Step8 is unchanged. Per-driver
word delta **+173**, an **executable gate step** under owner ruling7065030917:
+138 originally approved, +35 interruption/unambiguous-output corrections.
Current exact caps/counts: codex9789, qwen11001, gemma11610.

The latent static skip-guard issue from
https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7070887122
is addressed by explicit git/bash/make `shutil.which` clauses, validated by
the actual binary-guard suite. The output JSON fixture has one exact ignore
negation, planned explicitly and following existing CPP fixture precedent;
no wildcard ignore policy changes. No touched-but-unplanned product files.

Historical E review pass1 measured gpt-6.2-sol/diff-only and found four issues:
interruption precedence for missing verdict, ambiguous output assertions,
lane evidence limits and old progress-line consumer inventory. The present
source/tests correct the first two; this plan/evidence names exact existing
lane tests and external limits, and its Reader table records progress-consumer
search sensitivity and external coverage limits. The reserved pass2 now
reviews the complete current-main artifact; no silent cap reset.

Next: commit this source/evidence checkpoint, derive the different-model
runtime receipt after reserved pass2, then one owner-paced full finish gate
(normalHOME/ADDOPTSunset/shortprivateTMPDIR, actual admission, freshload5<=24,
no other group heavy gate, own-slot deadline). Final-head scans, Refs#1811 PR,
independent GraphQL references check after each body edit and exact-head CI
follow; cp-orch handles merge and final issue disposition.


### Row E reserved review pass 2 corrections

The current-main review helper measured reviewer codex/gpt-6.2-sol,
diff-only, network unverified and local credentials absent. It returned one
MEDIUM and two LOW test-adequacy findings; all three are accepted:

- Rendered prompts did not pin rejection of ambiguous/mismatched/unknown,
  interrupted or admission-refused results. The real rendered-policy check now
  requires the unambiguous-record instruction and explicit STOP/remedy rules
  in all three actual Step6 sections. `accepts-conflicting-status.md` retains
  all four valid verdict/status labels while permitting conflicts/mismatch,
  and must be rejected.
- Invocation extraction found any bare wrapper block and returned a constant.
  It now reads the operative `Run quality gates:` segment before verdict
  admission, requires its sole Bash block to be the bare audited helper,
  rejects the legacy direct route/fallback there and returns the actual
  extracted command. `mixed-route.md` keeps an active old runner and a dormant
  bare-wrapper example, and must be rejected.
- The Gate target row was prematurely marked passed. It is now not-run with
  explicit partial evidence until the own CPP full gate succeeds. Separately,
  existing real tests
  `test_runner_target_path.py::test_bare_python_uses_the_target_callers_interpreter`
  and `test_the_runners_own_interpreter_stays_in_cpp` passed all four parameter
  cases in1.97seconds. They create a real independent target venv and PATH and
  execute the shipped CPP_RUN array plus real runner on an owned custom plan;
  they do not claim to execute a full finish plan or a version matrix.

New committed prompt controls first returned **2 failed** with the old
checking functions. Corrected full driver suite: **71 passed in2.39seconds**;
lint passes. Production driver text/caps/helper formats did not change.
The two additional prompt fixtures are a disclosed review-control scope
variance; the approved plan body stays unchanged. Source/evidence will be
committed before requesting review authority beyond the spent two-pass cap.
No full gate has run in E yet; D's passing gate is not borrowed as E evidence.


### Row E authorized final review pass 3

Mailbox37562 authorized one final continuity pass on ad843bc9 because pass2
changed instrument controls; no fourth pass. The helper measured reviewer
codex/gpt-6.2-sol, diff-only, network unverified, credentials absent. It
reported no product/driver-text or MEDIUM-or-higher defect. Final LOW items:

- The extraction test can still accept a dormant wrapper if an active legacy
  directive is placed before its selected text marker. Current driver text
  has no such route. This residual test-adequacy gap is recorded per ruling:
  https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7071460595.
- Existing-suite lane coverage and actual own-CPP admission/gate results must
  remain distinct from added regression coverage. Named existing cases and
  actual801/4 results are already recorded; own admission/full-gate results
  will be appended only after execution. Live install/model limits remain.
  This is a pending verification/evidence follow-up within this task, not a
  claim that the pending gate passed or that unchanged tests were re-reviewed.

Receipt `2026-11-22T001829Z-issue-1811.json` derives implementer
codex/gpt-6.1-sol and reviewer codex/gpt-6.2-sol from their actual native
runtime logs, binds the full current-main artifact, and records3passes with
authority/reason in the parser-allowed extra-pass field. Seven earlier
findings were fixed; two LOW items are recorded as remaining at review time.
It is not a clean-review claim. No product/test code changed after this
review; only this issue's evidence and the genuine receipt are added.

Next is the single authorized own-checkout full gate under actual admission,
after freshload5<=24 and no other heavy CPP run, with3600s admission wait and
90-minute own-slot deadline. Gate target stays not-run/partial until that
result. No source changes are proposed to chase the LOW final control gap.


### Row E full gate 1 and launch-inventory integration correction

Own-slot job f4583654-b9c8-428e-9d71-0c698ccf3705 launched at actualload5
**3.05**, with no other CPP holder/queue. It acquired real full-suite
request1211, accepted the native3-pass receipt and executed the full plan.
Actual result: **`FLOW_FINISH_GATE: fail (at prerequisite test)`**, exit1;
**2 failed,13633 passed,4 skipped in460.62seconds**. The two failures were
`test_all_target_launchers_have_captured_path_policy` and
`test_committed_inventory_matches_the_actual_source_and_generated_population`.
No push or pass claim follows this result.

Cause: removing the four old direct runner sites (three commands plus the
shared template) makes `templates/` legitimately empty of direct lib.cicd
launches. The existing population assertion demanded a launch in every source
root, and its committed measured table still listed those removed sites.

Correction is limited to the existing inventory test and measured report:
`templates` remains in SCAN_ROOTS, all rows remain classified and checked for
handoff errors, and the other three previously required non-generated roots
remain nonempty requirements. The known committed missing-handoff, repaired
and unclassified fixtures now run at five independently literal root paths,
including templates and generated skills. Removing templates from the scanner
would make its bad probe disappear and fail that test; it is not a zero-scan
exception. The scanner classifier itself is unchanged. The current generated
inventory has134 rows,0template rows,20captured source rows and22captured
generated rows; its four obsolete inline rows were removed, with the original
24/22 historical numbers clearly distinguished from the maintained table.

Focused validation: **147 passed in6.00seconds**, including the previously
failing launch-inventory checks, all five-root bad/good/unclassified controls
and71finish-driver cases. Lint passes. An initial10-second tool cutoff was
not counted as completed evidence; the retained result is the completed run.

Touched-but-unplanned integration files are
`tests/test_cicd_launch_handoff.py` and
`docs/measurements/runner-target-path-1801.md`, in addition to the two disclosed
review-control fixtures. These are necessary consequences of removing inline
launches; no helper, driver text, verdict or word cap changed. The approved
plan is unchanged. Because an inventory instrument changed after the final
review, the new delta needs explicit orchestrator disposition before another
full gate. The genuine receipt remains bound to its actual reviewed artifact;
no later change is represented as already model-reviewed. No review4 or new
full gate is launched without authority.


### Row E root-population controls required before delta review

Mailboxes37575/37577 authorize the narrow inventory correction, one scoped
review pass4 and then one paced full gate. Before review they require both a
bad template-launch control and missing/unreadable-root refusal.

(a) Existing committed `bad-missing.md` is injected into each of five literal
roots, including templates, and must yield one detected missing-handoff error;
its repaired and unclassified partners retain their distinct results. These
five-root controls pass. The roots are independently literal in the controls,
so removing templates from SCAN_ROOTS cannot remove its test population too.

(b) New committed `root-populations.tsv` declares existing-empty (accepted),
missing (unavailable) and unreadable (unavailable) cases. Forty valid neighbor
launches satisfy the other population requirements and a matching inventory
record removes unrelated failure causes. The new cases exercise the actual
population test and actual recorded-inventory reader, as well as the scanner.
The directory-read PermissionError precondition is asserted; mode000 uses real
permission denial when effective, with deterministic os.scandir fault injection
when privileges bypass mode bits. This is explicit error-path evidence, not a
claim about access restrictions in every environment.

Before the complete-root fix, new controls reported **2failed/1passed**.
After the correction, **8boundary controls passed**. A separately copied blind
variant changed only complete_inventory's delegation back to the sparse mode;
with the final strengthened controls it again reported **2failed/1passed**
(missing/unreadable did not refuse, empty accepted). The genuine current code
reports **150focused tests passed in3.58seconds**, including these controls,
the inventory report and71driver cases. Lint passes. This is not a full-gate
rerun.

Complete reads now walk every declared directory without rglob's silent
permission suppression and fail by name for an unavailable source root.
The canonical population check and recorded-inventory comparison both use
that complete reader. The existing small classification fixtures explicitly
use their partial-population reader; the launch classifier/MATCH rules and
other populated-root requirements are unchanged. Current full source output
still has134rows and the same regenerated report.

One additional committed TSV fixture is disclosed integration scope variance.
The approved plan is unchanged. No driver text/helper/word cap changes. This
completed delta, including the error-path controls, is ready for the explicitly
authorized continuity review4 from ad843bc9; no fifth pass is authorized.
