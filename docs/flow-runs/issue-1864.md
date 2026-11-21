# Flow run record - issue #1864

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=96fbfe91493340acaa867b10231914bc -->
## Run 1

- Run-id:            96fbfe91493340acaa867b10231914bc
- Run-start:         e32c06edfb52175e4a0678fe51a9a6aea56f671d
### Section B evidence
- Read issue #1864 in full via GitHub; no comments at read time.
- Main at read time (from GitHub): e32c06edfb52175e4a0678fe51a9a6aea56f671d.
- Orchestrator approved mailbox plan 36327 in message 36328, 2026-11-21,
  with fail-closed helper lookup, clean paired case and exact interface notice.
- Reader search found the known parse consumer in code_review.md, line 276,
  plus flow command consumers. Kyle/skillc consumers are known externally.

### Section C - the approved plan
1. `scripts/counter-model-receipt.py` - canonical FINDING_KINDS and finding-kinds verb, per-finding classification, additive CLI kind counts.
2. `scripts/codex-review-run.sh` - derive prompt choices from the verb; refuse missing, errored, empty or malformed output before reviewer invocation.
3. `tests/test_counter_model_review.py` - mixed/missing/clean CLI counts and ambiguous, unknown, fenced and heading-boundary cases.
4. `tests/test_codex_review_run.py` - real prompt capture, helper refusal and real paired parser context for extracted stages.
5. `tests/fixtures/counter_model/kinds-mixed.review.md` - mixed recognized kinds.
6. `tests/fixtures/counter_model/kinds-missing.review.md` - legacy finding with no Kind field.
7. `tests/fixtures/counter_model/kinds-clean.review.md` - clean counterpart, zero unstated.
8. `.claude/commands/codex/code_review.md` - document Kind and parse-output contract without duplicating the list.
9. `docs/scripts/counter-model-receipt.md` - parser interface and limitations.
10. `docs/scripts/codex-review-run.md` - paired helper refusal and bundle requirement.
Scope: parse/transcript only; receipt schema remains 5. No Kyle or skillc edits.
Risks: additive parse output and sealed shell hash require consumer re-pins.
Counts cover recognized headings; format-mismatch remains a refusal.
Missing, unknown or repeated Kind fields become unstated, not guessed.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | will test: main checkout in owned clone; linked worktree not applicable because no root discovery changes |
| Harness | will test: Claude install source helper and Codex install generated flow-auto helper bundle parity; live installs not covered |
| Driver | will test: `/flow:auto` deterministic review/parser tests; live delegated drivers not covered |
| Coordination | not applicable: no authority or coordination behavior changed |
| CI provider | not applicable: parsing independent of Woodpecker / GitHub Actions / none recorded |
| Project state | not applicable: no adopted-file lookup changed |
| Toolchain version | will test: host or container's installed versions locally and CI's pinned uv and Python through exact-head CI |
| Clone shape | not applicable: no history behavior changed |
| Run location | will test: invoked from the CPP root through make and from another directory through parse subprocess cwd |
| Gate target | not covered: live consumer interpreter and PATH; helper bundle tests only |
| Wave role state | not applicable: no wave state touched |
| Reader: reviewer model | tested against real output: actual prompt captured by test_finding_kind_prompt_uses_canonical_list; model adherence not covered by deterministic tests |
| Reader: parse CLI | tested against real output: test_finding_kind_cli_counts feeds committed transcripts into actual parse CLI |
| Reader: existing flow commands | reader unchanged: existing COUNTER_MODEL_FINDING and COUNTER_MODEL_REVIEW lines preserved; related tests exercised |
| Reader: Kyle and skillc | not covered: external re-pins coordinated in kyle#2566, skillc#795 and kyle-candidate#23 |
| Reader: receipt writer and validator | reader unchanged: no stored fields changed, schema remains 5 |
| Reader: generated Codex helper bundle | tested against real output: codex-skills build and mirror parity checks; /codex commands excluded from generation |

### Verification and red cases
- New regression cases run on pre-fix API main scripts: 12 failed; fixed: 12 passed.
- Related source-bound review/parser tests: 503 passed after fixture runtime dependency update.
- Committed missing and unknown kinds pin unstated; mixed kinds and clean pair pin recognition and zero.
- Missing/error/empty helper cases refuse; real paired helper accepts and yields prompt choices.
- Run make verify and CPP's scripts/flow-finish-gate.sh, one heavy run at a time,
  with own-slot notification and deadline; report any red without rerun-until-green.
- Different Codex reviewer; derive both identities from retained runtime logs.
- PR body: Closes #1864; line shape COUNTER_MODEL_KIND: <kind> <count>;
  existing output lines unchanged, receipt schema unchanged, helper hash change,
  external coordination issues and #1863 item 2's future kind-rate reader.

### Approved scope amendment - mailbox 36340 and 36346
The orchestrator approved this amendment on 2026-11-21, after inspection
showed the new helper dependency in extracted-stage tests and install paths.
The initial Section C above is retained unchanged as historical approval.
- Additional file: `scripts/flow-helpers-install.sh` - include the required
  parser alongside codex-review-run.sh in the curated repair family.
- Resolve an explicit CM_RECEIPT as given, otherwise the script's realpath
  sibling before existing installed/plugin fallbacks. A lone copy refuses.
- Add source, repair symlink, repair copy, real generated Codex bundle,
  lone symlink and lone copy cases in tests/test_codex_review_run.py.
- Reader: CPP init/update executable-script loops already include both helpers.
- Reader: flow:repair now installs the pair; tested with the actual installer
  in both symlink and copy modes, then actual review-script invocation.
- Reader: Codex flow-auto bundle carries both helpers byte-identically;
  tested by building the real bundle and invoking its actual review script.
- Reader: Kyle session-tooling bundle: not covered here; must ship both
  files together. Explicit CM_RECEIPT is supported; otherwise ship siblings.

### Verification chronology and limits
- Before any product edit, mailbox plan 36327 was approved in 36328.
- Initial 12 kind cases failed against unchanged main scripts, then passed.
- Related tests initially 79 failed / 424 passed because extracted stages
  lacked the paired-helper context. Shared extractor now supplies the real
  parser; 503 related tests then passed.
- Four packaging cases failed on main. The first make verify was already
  running when main scripts were swapped in for that red run. Its evidence
  is invalid: it was explicitly cancelled, exit -15, at 2026-11-21T15:00:11Z.
  Process group 16941 was confirmed gone; no pass is claimed for that run.
- Subsequent red runs use a separate detached worktree under the private
  temporary root. Six packaging cases failed on unchanged main e32c06ed.
- Final expanded related suite: 603 passed in 50.94s. This includes all
  18 new cases, legacy review stages, real installer and permission parity.
- Lint passes. Generated flow-auto parser matches canonical source bytes.
- Runtime HOME, TMPDIR and pytest basetemp use /tmp/c.4GCpzc, not /workspace.

- Binary guard exception: only the new parse subprocess call is exempted,
  since that verb never calls git. The checker remains unchanged and still
  requires guards on git-reaching calls, including
  test_scoped_writer_refuses_when_git_cannot_launch in the same test module.
  Red control: before the narrow call exemption and make guard were added,
  binary-guards-check reported both new unguarded tests and failed.
- Per mailbox 36360 the amended record is not re-stamped: helper docs do
  not document re-approval after an amendment. PLAN_RECORD_STABILITY and
  TOUCHED BUT NOT PLANNED (installer) are reported with authority 36346;
  machine lane status remains NOT CHECKED despite the concrete test evidence.

### CI finding and authorized history correction
Woodpecker pipeline 3960 failed its secret scan before dependent steps ran.
Pinned gitleaks classified the Section B label next to a commit hash as a
credential. The value was a Git revision, not a secret. Mailbox 36375
instructed a branch-history rewrite rather than widening the secret allowlist.
Section B was reworded to remove the false positive; its factual content is
unchanged. The historical stability signal remains disclosed.
The superseded finish job was stopped at 2026-11-21T15:11:58Z with exit -15;
its process group was confirmed gone and its partial run is not gate evidence.
The earlier independent review found no defects, but its runtime HEAD belongs
to the pre-rewrite history. A second review binds the corrected history;
that previous receipt was not retained as current-head evidence.
The exact pinned scanner found one leak before correction and no leaks in a
fresh single-branch clone after correction. Existing stale remote refs in the
working clone retained the superseded commit and still triggered the scanner;
the fresh clone excludes those obsolete refs, like the new CI checkout.

### Review bound to rewritten history
The second review found no defects on checkpoint acf3005dd21b988ffc77ce41e3bc3571e3cb5137.
The receipt writer derived codex/gpt-6.1-sol and codex/gpt-6-astra from
retained runtime session logs. Receipt: docs/measurements/counter-model/2026-11-21T151539Z-issue-1864.json.
It records two total passes, including the superseded pre-rewrite pass.
The reviewer observed kind inputs/refusals and confirmed that code and tests
match the earlier checkpoint; the broad suite was not independently rerun.

### Budget-driven documentation amendment - mailbox 36398
Pipeline 3961 failed command-docs-budget-check: code_review.md had 2726
words against the unchanged cap of 2593, 133 over. This was reproduced
locally before the trim. The superseded runner gate was stopped at
2026-11-21T15:20:18Z, exit -15, process group confirmed gone; no pass claimed.
The added field explanation is now a short Kind/unstated/reference pointer.
The adjacent existing parse-format paragraph was condensed: its flow step,
parser command, Findings heading, clean sentinel and preserve-format
instruction all remain. No existing instruction was removed. Full new
parser detail remains in docs/scripts/counter-model-receipt.md.
The orchestrator authorized pass 3 with reason: pass 3 reviews a
budget-driven doc trim. No code, test or word-cap change is part of this trim.
