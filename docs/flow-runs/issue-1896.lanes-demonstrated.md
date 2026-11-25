# P1-A1 demonstrated lanes

<!-- lanes-demonstrated run=491e55fba4da40ac91d983677dceecde plan=0e27a2e1431353c014742dc6ef7ef80924d4b22cc431bb48c97595782ad5e749 -->

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
