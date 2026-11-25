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

## Run 2 - A2 local evidence and pending host observations

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
| Actual pi loader | UNKNOWN / unexecuted | Host fixture batch committed, no pi binary locally; tool inventory unsupported by documented pi 1.6.0 RPC remains unknown separately |
| Syscall reader | local pass | Auth stat, transient write, history descendants, fd-relative escape, no-create verify and record-only package-write opposites; malformed/truncated/omitted child traces unknown |
| Actual syscall observer | UNKNOWN / unexecuted | Host batch traces actual copier/verify separately from pi, then actual synthetic auth-stat/transient-write children; raw records not returned yet |
| Contextual selection / provider / container | UNKNOWN / not covered | Neither disk fidelity nor offline reader controls establish runtime selection or bearer isolation |
| CI provider | pending | No A2 PR or CI yet; separate PR clearance required |

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

Current focused total is 219 passing cases (25 install/concurrency, 32 observer,
162 A1). Two writer processes also both establish real EAGAIN before release,
then publish one complete revision/record for same-package and changed-package-
population inputs. Handshakes and process completion waits are bounded.

Three new registered control families cover actual production installation,
RPC pair reader and syscall reader with GOOD/BAD/UNKNOWN inputs and constructed
anchors. Their provenance is honestly constructed, not a historical fix claim.
Strict control runs pass. Host control self-tests do not upgrade the UNKNOWN
execution rows. Full finish gate, independent review/receipt and PR CI remain
pending; no closing acceptance claim for #1896 is made.

Supplemental documentation contradiction recorded without widening A2:
[shared-ledger primary-lock wording](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7175807297).
