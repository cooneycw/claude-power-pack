# P1-A1 demonstrated lanes

<!-- lanes-demonstrated run=491e55fba4da40ac91d983677dceecde plan=cf3f5f27d6b3d32dce08e9c6b2c50d029d36694139cd97a21274852958c1e47c -->

| Lane | Result | Evidence |
|---|---|---|
| Checkout | passed | `tests/test_pi_skill_sync.py::test_source_inventory_in_main_linked_and_shallow_clone` builds the actual main and linked-worktree source layouts |
| Project state | passed | `test_fidelity_never_skips_missing_or_unsafe_expected_package` and `test_foreign_neighbor_not_adopted_or_judged` compare marked, missing-marker, absent and foreign fixture content; no ownership transaction claimed |
| Clone shape | passed | `test_source_inventory_in_main_linked_and_shallow_clone` asserts a real full fixture repository and a shallow single-branch clone produce the same packages |
| Run location | passed | `test_actual_cli_with_external_cwd_and_explicit_home` runs the actual CLI from an unrelated directory; real-repo build test covers source root |
| Gate target | passed | `test_consumer_own_interpreter_and_path` launches the CLI with a new consumer venv interpreter and consumer-only PATH; no consumer quality-gate runner modification |
| Harness | not run | Existing Claude/Codex installs untouched; real pi installed-output RPC belongs to A2 host fixture lane |
| CI provider | not run | No PR CI started; Woodpecker awaits clearance; no GitHub Actions claim |
| Toolchain version | passed | Focused tests ran with container Python 3.11; no version matrix claimed |
| Reader: generic core installation | not run | A2 imports delivered core; no installer/stub runtime use in A1 |
| Reader: skills-check/install-drift | passed | Real builder output feeds both readers in `test_real_pi_bundled_output_and_missing_marker_floor` and `test_pi_reader_consumes_real_builder_output_and_drift`; separate registered controls reject blind subjects |
| Reader: pi skill loader | not run | Delivered-output RPC status UNKNOWN/unexecuted; preparatory fixture observations remain separate |
| Reader: boundary observer | not run | Actual syscall observer status UNKNOWN/unexecuted, A2 host lane; A1 source/path tests are not syscall evidence |
| Reader: contextual selection report | passed | A1 snapshot reports effectiveness unknown in CLI/checker/drift tests; no bounded runtime-selection observation is synthesized |

Scope: P1-A1 only. Focused Make tests, registered opposite controls and pinned
Codex parity ran; full suite and exact-head review/receipt/paired finish gate
remain subsequent steps. The known-bad transform writes changed actual Codex
output and is rejected against the independently built pinned baseline.

File-plan accounting: approval listed case-directory patterns as shorthand;
the file-set helper treats them literally, so materialized `cases/*/case.json`
members appear as declared-scope divergence, not unknown new behavior. The
verify-coverage JSON entry proved unnecessary because Makefile statically
invokes the new script; its derived classification is the source of truth.
The future exact-head receipt is absent until review runs. These differences
must be reported rather than rewriting the approved plan to disguise them.

Pass 1 corrections: five F1/F2/F3 regressions failed before the fix and pass
afterward. The old frozen-output comparison failed under umask 002; the new
same-input/two-generator comparison passes 022/002 and legitimate input evolution,
then rejects the deliberately changed real transform. The actual pinned source
is retained and digest-checked, so this comparison is re-derivable without Git
or network. Full focused suite: 162 passed. No real-pi or syscall acceptance
is added by these corrections.

## Run 2 - A2 local evidence and observed host fixture

Run id `94e96cda99ab4be19bb7068942115d12`; plan approval is mailbox 40218
at `e0c018ea`, binding merged core `adf70c29`. This section does not replace
Run 1's historical marker or claim a helper-generated new approval stamp.

| Lane | Result | Evidence and limit |
|---|---|---|
| Core installation reader | local pass | Real `PiAdapter` calls actual core inspect/refresh with tracked source bytes; native ownership/conflicts, adoption backup, dual-identity refusal and record-only metadata refresh tested |
| Project state | local pass | Unmarked, owned, edited, absent, unreadable and ignored-source fixtures; unknown never becomes current |
| Run location | local pass | Actual CLI from fixture external cwd and HOME with default agent beneath HOME/.pi; home case failed before correction |
| Checkout / clone shape | local pass | Actual source Git binding tested in ordinary checkout, linked worktree and shallow single-branch clone; source revision mismatch/dirty/ignored inputs refuse |
| Lock/concurrency reader | local pass | Each of three real lock files held by a separate pipe-synchronized process; EAGAIN independently established, verify unknown and tree unchanged; absent locks stay absent |
| A1 checker/drift readers | local pass | Existing 162 cases, same-input pinned Codex parity and fresh-build consumers pass after lazy installation imports preserve standalone snapshot deployment |
| RPC pair reader | local pass | Committed populated/bad/unknown raw pairs; shape-only blind anchor misses semantic negatives; source and diagnostic equality checked |
| Actual pi loader | OBSERVED / partial | Rerun 2 at `38041ce1`: all 18 actual installed skills discovered; removal produces finding, restoration returns population; hidden management layout adds no non-topic commands. Tool inventory and skill-loader diagnostic observation remain UNKNOWN |
| Syscall reader | local pass | Auth stat, transient write, history descendants, fd-relative escape, no-create verify and record-only package-write opposites; malformed/truncated/omitted child traces unknown |
| Actual syscall observer | OBSERVED / matches | Rerun 2 at `38041ce1`: 29 normal cases match, auth-stat and transient-write controls find their actual forbidden operations; all 31 expected child exits match, no forced stops, zero aggregate findings/UNKNOWNs and cleanup true |
| Contextual selection / provider / container | UNKNOWN / not covered | Neither disk fidelity nor offline reader controls establish runtime selection or bearer isolation |
| CI provider | failing / correction pending | PR #1910, pipeline 4030 at `3d3f69cd`: root unreadability control unavailable and staged-Git PATH test failure; see CI correction record below |

Red-first evidence: both initial install/verify acceptance cases failed on the
unchanged A1 CLI, which had neither operation. During implementation the
omitted-cloned-child regression failed with an incorrect `matches` result;
after correction it is UNKNOWN and has a committed opposite descriptor.
The HOME canonical-install regression failed with trusted-config refusal
before the canonical-root correction and passes afterward. Existing inverse
root/source/history negatives still discriminate.
The credential-alias regression failed when a literal auth-file probe was
normalized into an ordinary source path; it now remains a finding, and the
committed auth-stat descriptor retains that opposite alias input.

Initial focused total was 219 passing cases (25 install/concurrency, 32 observer,
162 A1). Two writer processes also both establish real EAGAIN before release,
then publish one complete revision/record for same-package and changed-package-
population inputs. Handshakes and process completion waits are bounded.

Three new registered control families cover actual production installation,
RPC pair reader and syscall reader with GOOD/BAD/UNKNOWN inputs and constructed
anchors. Their provenance is honestly constructed, not a historical fix claim.
Strict control runs pass. Host control self-tests alone do not upgrade execution
rows; the actual paired rerun evidence below does. Full finish gate, independent receipt and PR CI remain
pending; no closing acceptance claim for #1896 is made.

Supplemental documentation contradiction recorded without widening A2:
[shared-ledger primary-lock wording](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7175807297).

Pass 1 review at `a48687ae` requested one MEDIUM correction: real Python/Git
traces contain poll and other descriptor multiplexing operations which the
reader treated as unsupported. Both new Python/Git-shaped GOOD/BAD regressions
failed on that reviewed reader before the fix. Descriptor-aware handling now
accepts the GOOD trace and reports the forbidden-fd twin; unresolvable fds stay
UNKNOWN. Current observer total is 40 passed. The hidden management-directory
expectation and frozen-design primary-lock rename are explicit in Run 2 and
the host protocol. No host execution evidence has been added by this correction.

### Accepted host rerun 2 and remaining scope

[Rerun 2](../measurements/pi/2026-11-25-a2-host-rerun-2.md) at reviewed code
`38041ce14b8fb0d5f5f231a10236e199c057771b` ran on the host during
2026-11-25T23:49:08Z through 23:49:50Z, Python 3.12.3 / pi 1.6.0 / strace 6.8.
The author verified the forwarded sanitized summary digest
`7549d721678b229a50a25a090b881f3885e6e2bbe9848c04f403cfed89283f6a`, script
hashes and all returned per-case verdict/exit/blocker fields. The actual RPC
pair/removal/restoration responses were independently fed to the reader.
Full raw syscall traces remain host-only; this author did not replay them.

The actual syscall lane is OBSERVED: GOOD=matches and seeded BAD=finding.
The preceding 28 unresolved notes cleared, supporting the runtime-allowance
cascade diagnosis. This covers the explicit copier/verifier fixture operations,
not pi startup credential isolation or all possible runtime contexts. The
[initial](../measurements/pi/2026-11-25-a2-host-initial.md) and
[first rerun](../measurements/pi/2026-11-25-a2-host-rerun.md) remain nonpassing.

The actual pi loader discovery/removal/restoration/project-shadow observations
are OBSERVED. RPC has zero findings and two standing UNKNOWNs: no supported
built-in-tool inventory RPC and no skill-loader warning channel in RPC stderr.
Equal stderr covers runtime/extension/provider/flag diagnostics only. Those
two rows remain #1896 work; contextual effectiveness, owner validation and
provider/container behavior remain unclaimed. Any A2 PR uses Refs #1896.

Latest local observer suite: 95 passed, including three residual regressions
run RED before fixes. All six targeted control families pass; A2 has 79
descriptors (21 install, 9 RPC, 49 syscall). Code review pass 4 approved
`38041ce1`, with the owner-raised cap 7 at
[the #1896 ruling](https://github.com/cooneycw/claude-power-pack/issues/1896#issuecomment-7178021233).
The docs-only evidence delta and A2 receipt are subsequent review steps; the
direct paired finish gate and PR CI remain pending. No issue closure claimed.

### PR and CI harness correction

The direct self-supervised finish gate at receipt head `953c428e` returned
paired ok/exit 0: 13,856 tests passed, four skipped, 144 control families PASS.
Main `12b39ceb` was then merged without rebasing into `3d3f69cd`; the two
inventory conflicts retained both pi and Antigravity entries. Inventory/census
and link checks passed, and the reviewer posted an exact-head merge-only
APPROVE on [PR #1910](https://github.com/cooneycw/claude-power-pack/pull/1910).

Fresh [root CI pipeline 4030](https://woodpecker.essent-ai.com/repos/1/pipeline/4030/1)
was RED: validate had 13,772 passes, 120 skips and one failure because the PATH
test discarded staged Git; negative-controls rejected the unreadable case's
case-specific unavailable result. This is actual root RED evidence at the
unchanged head, not fakeroot. The approved correction only adjusts the control
runner's fixture identity and the test's discovered Git directory. The SAME
unprivileged child proves PermissionError before exec of the real CLI;
UNKNOWN remains the subject's verdict and preservation oracles stay intact.

Current local checks: 26 install/concurrency passes plus one explicit root-only
regression skip, 95 observer passes, and all three A2 control families PASS.
The privileged root regression and fresh PR CI remain pending; no local skip
is root GREEN. This change needs pass 5 within the owner's cap 7. Product pi
adapter/core/observer code and the accepted host fixture claims are unchanged.

## Run 3 - pi partial-refresh opt-in

Run `00d2c06f8a804352acd60178d59eb6cc`, base merged main `b1cd1f16`.
Orchestrator 40994 approves the separate branch; #1897 remains frozen.

| Lane / reader | Result | Evidence and limit |
|---|---|---|
| Checkout / clone shape | observed locally | Separate linked worktree with full history; fixture owns a standalone source Git repository. No new shallow-runtime claim |
| Project state | passed locally | Full 18-topic source, foreign boot without CPP ownership and absent safe topics; all 17 safe topics become exact/current while boot stays unchanged |
| Actual CLI / ledger | passed locally | Actual install/verify exit 1/non-current, only boot conflicts; exact fresh members and ledger hashes/source/revision for safe topics |
| Neutral default policy | passed locally | Explicit false-policy fixture preserves safe stale topic and ledger; opt-in arm progresses and remains non-current |
| Global integrity | passed locally | Cross-identity claim still refuses all writes; core implementation unchanged |
| Run location | passed locally | Root Make invokes actual CLI in external fixture cwd with fixture HOME/agent |
| Toolchain | observed locally | Installed Python/uv/Make/Git; focused 103 passed, one existing real-root-only skip. No matrix claim |
| CI provider / paired gate | pending | Woodpecker PR CI, independent review/receipt and direct paired finish gate still required |
| Runtime discovery / owner behavior | not newly covered | No pi process or owner action; two historical #1896 measurements remain UNKNOWN |

The [follow-up measurement](../measurements/pi/issue-1896-partial-refresh.md)
records the actual pre-opt-in failure, fixed positive and fixture correction.
All basetemps were removed after retaining necessary evidence under workspace.

<!-- lanes-demonstrated run=00d2c06f8a804352acd60178d59eb6cc plan=10f9500fb59eddaf18657dc56d9c5746f599d7d0b6ee1afdf8f2a67ff93b9578 -->

| Lane | Result | Test or observation |
|---|---|---|
| Checkout | passed | Separate linked worktree; full-topic CLI regression materializes a tracked source snapshot in a fixture-owned standalone repository |
| CI provider | not run | Woodpecker PR CI awaits review, receipt, paired gate and PR creation; no CI pass claimed at this checkpoint |
| Project state | passed | `test_full_topics_preserve_foreign_boot_and_install_other_seventeen`: foreign boot remains unchanged, 17 safe absent topics install; focused owned/edited cases also pass |
| Toolchain version | passed | Installed container Python/uv/Make/Git ran 103 focused cases; pinned CI-image execution remains pending CI, with no matrix claim |
| Clone shape | passed | Local `git rev-parse --is-shallow-repository` is false; paired gate will use this full-history checkout. Shallow runtime behavior is not newly covered |
| Run location | passed | Make from CPP root and actual CLI from external fixture cwd in `test_full_topics_preserve_foreign_boot_and_install_other_seventeen` |
| Reader: pi CLI report | passed | Actual install and verifier both exit 1/non-current; verifier reports only boot conflicts with all 18 expected topics |
| Reader: ownership ledger | passed | Actual safe-topic records equal fresh member hashes/modes/source/revision, boot is absent from CPP ownership, verify leaves ledger bytes unchanged |
| Reader: neutral-core default | passed | `test_explicit_default_policy_and_opt_in_copy_have_distinct_partial_policy`: explicit false arm preserves safe stale content and entire ledger, opt-in arm progresses |
