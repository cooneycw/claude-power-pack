<!-- lanes-demonstrated run=d05b7fe3d54a49c7beed965534c89dfa plan=7808b10f2467603864866d22d5ac892e024cccee932cb9fcf81488d5e37779c8 -->

| Lane | Result | Test or observation |
|---|---|---|
| Checkout | passed | 21 targeted tests pass in the isolated main clone and linked worktree /tmp/c.KdgSAI/base with implementation applied; before applying it, all 21 fail on e32c06edfb52175e4a0678fe51a9a6aea56f671d |
| Harness | passed | test_generated_codex_bundle_uses_real_script_and_canonical_contract generates the Codex skill from the Claude source, then executes the bundled report with its bundled canonical contract; make codex-skills and source/mirror inspection completed. No live Claude execution claimed |
| Project state | passed | test_latest_cumulative_receipt_per_issue_not_double_counted and test_missing_receipt_directory_is_unknown exercise adopted and absent sources |
| Run location | passed | test_cli_from_other_directory_reads_real_fixture_output and test_generated_codex_bundle_uses_real_script_and_canonical_contract execute actual reports from external fixture directories |
| Reader: monthly:create and user | passed | Actual Markdown output exercised in the CLI and generated bundle tests; monthly/create source and generated SKILL.md inspected. UNKNOWN is informational and does not block monthly creation |

Pre-fix result: `21 failed in 0.27s` against detached e32c06edfb52 with the new
fixture tests copied into that tree, before its script or command edits were
applied. The feature is absent there: script-dependent cases fail for missing
implementation, and the generated-bundle case fails for the missing canonical
contract bundle. Post-implementation linked-tree result: `21 passed in 0.28s`.

Committed negative control: provenance.json's fix PR #101 has neither line and
is flagged MISSING; #102 has valid canonical lines and is recorded. unreadable.json
reports UNKNOWN with 0/unknown PR coverage, rather than zero escapes. Missing
canonical markers report UNKNOWN. Tests never contact GitHub.

Monthly command: 503 words before, 498 after; budget 503. Its actual generated
Codex bundle contains the report and canonical answer contract.

Counter-model pass 1 (codex/gpt-6-astra) found two medium issues, both accepted:
CRLF answer lines failed canonical matching; the diff lacked fixture-owned
checkout and Claude-install coverage. CRLF body and comment regression cases
both failed against product checkpoint a29354d8 before normalizing line endings
(`2 failed, 21 deselected`), then passed after the fix. The added installation
case creates its own main Git checkout and linked worktree, calls the actual
cpp-host-write.sh link-into operation under separate private HOME directories,
and runs the installed symlinks against their real canonical contract.

Expanded pre-fix-main run: `24 failed in 0.35s` on e32c06edfb52. Current targeted
run: `24 passed in 0.55s`. The binary-boundary exemption remains scoped only to
the existing fixture CLI test; the new installation case has explicit git,
bash and Python guards, with no exemption. No checker implementation changed.

Plan revision approved in orchestrator mailbox #36380: pass 2 found independent
runs discarded by latest-per-issue aggregation, and a malformed search candidate
aborted later candidates while claiming an empty population. Independent runs
now remain separate; cumulative deduplication requires branch plus implementer
session evidence. Historical ambiguity reads UNKNOWN. The real #1691 pair is
committed as fixture data. Malformed candidates stay in the denominator and do
not suppress following readable fixes. Five targeted regression cases failed
on product checkpoint ecdcae5b (`5 failed, 24 deselected in 0.13s`). All 29 tests
fail on pre-feature main (`29 failed in 0.41s`), and the current suite passes
(`29 passed in 0.38s`). The third review is approved only because these fixes
changed counting logic. Further aggregation concerns must use the approved
raw-receipt fallback, not more heuristics.
