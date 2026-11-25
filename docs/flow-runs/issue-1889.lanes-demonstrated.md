# #1889-A lane and reader evidence

<!-- lanes-demonstrated run=b9ec164e15eb4b14826b3f2a0d09dc16 plan=47f2049b42b802c01cd931073d94e6ebe1fd125b709688a0764b1f5934c3d147 -->

| Lane | Result | Evidence |
|---|---|---|
| Checkout | passed | Actual core/CLI use a main fixture checkout in `test_actual_cli_refresh_then_verify_with_real_report`, and a real linked Git worktree in `test_source_binding_supports_linked_worktree_and_shallow_clone[worktree]` |
| Project state | passed | `test_real_build_install_and_verify`, `test_unmanaged_same_name_target_preserved` and `test_selected_absent_vs_unselected_not_applicable_without_mutation` exercise managed, unmanaged, selected absent and unselected output |
| Clone shape | passed | Main/full fixture clone and `test_source_binding_supports_linked_worktree_and_shallow_clone[shallow]`; dirty/wrong binding reports unknown in `test_dirty_source_and_wrong_build_revision_fail_unknown` |
| Run location | passed | Both parameters of `test_actual_cli_refresh_then_verify_with_real_report`: actual CPP root cwd and external temporary-directory cwd |
| Harness | not run | Production Claude/Codex/AGY and pi adapters are outside A; fixture-only CLI does not establish those installations |
| Driver | not run | No flow/delegated-driver instructions or semantics changed |
| Coordination | not run | No product Kyle path; the local transaction stress itself ran under a real renewing supervisor |
| CI provider | not run | No provider-selection behavior changed; PR CI not started |
| Toolchain version | not run | Host Python 3.11 only; pinned PR CI and a version matrix are not local evidence |
| Gate target | not run | No consumer quality-gate runtime/PATH changes |
| Wave role state | not run | No role or mailbox registry change |
| Reader: fixture CLI | passed | `tests/test_host_update_cli.py` consumes actual core reports/installed trees through the real subprocess CLI |
| Reader: control harness | passed | `make host-update-controls`: 3 GOOD, 5 BAD and 1 UNKNOWN input; constructed anchor misses each BAD, agrees on GOOD, and its blind clean lock result is explicitly declared |
| Reader: pi adapter | not run | Interface and additive manifest helper coordinated; pi A2 awaits completed core review/gate evidence |
| Reader: real adapter/status/drift | not run | Claude/Codex/AGY integrations belong to B and later reader deliveries |

Local focused result: 49 tests passed. The real transaction suite's 12 tests
passed 20 consecutive runs (240 executions) under the full-suite lease
supervisor. Pipe handshakes establish real flock EAGAIN before the other process
is released, and both same-package acquisition orders are tested.

Red evidence: bypassing the lock makes the concurrency handshake fail;
creating a lock during read-only verify makes the exact-tree comparison fail.
Both are committed mutation cases. The inherited GIT_DIR/GIT_WORK_TREE regression
test was run before environment isolation and failed (expected exit 0, observed
unknown 4), then passed with the fix. This is a regression of the initial WIP
implementation, not a claim that the new core existed on the old main branch.
The ignored-source-member regression also failed before the fix (expected
unknown 4, observed success 0). The fixture builder now reads only regular
blobs present in the pinned commit; the complete focused suite then passed.
Two further self-audit cases ran red before correction: a retired absent member
left in the ledger was incorrectly current, and explicit adoption could give
two CPP identities ownership of one package. They now require metadata refresh
and refuse ambiguous cross-identity takeover, respectively; both passed after
the corrections, along with the complete focused suite.

Review pass 1 requested two corrections, both accepted: independent shared
ledger/work serialization and support for system aliases above the approved
root. Four regression instances ran against the exact reviewed `e62b003b`
implementation and all failed: deterministic ledger record loss, shared-ledger
and shared-work process lock handshakes, and a symlinked system ancestor.
All four pass after correction. Additional cases refuse a symlink at/below the
root, descriptor-selected aliases below the fixture anchor, and primary locks
colliding with management data or transaction cleanup. Public signatures remain
unchanged; the pi consumer was notified of the derived management lock paths.

The registered negative-control inputs report exit 1 for stale bytes, missing
members, hand edits, unmanaged collisions and modified orphans; current/no-lock/
safe-prune inputs exit 0, held-lock input exits 4. The blind anchor misses those
five detections, proving the controls are not satisfied by an always-current
verifier. Preservation-oracle failures suppress detector output and are not
counted as successful detection.

## Plan substitution

The planned manual `.claude/verify-coverage.json` entry was unnecessary: the new
fixture Makefile targets already derive the CLI's coverage. The checker rejected
the redundant manual entry as stale, so it was removed. The approved plan record
and its stability digest remain unchanged; the compliance report correctly
names this one planned-but-untouched path. No acceptance item was removed.

## Carried follow-ups

These remain later deliveries, not work folded into A:

- #1888 baseline availability: [Nit record](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7168402700).
- #1888 attributed input changes and explained baseline decisions: [Nit record](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7168403197); compare historical/candidate generators on the same inputs, never silently re-pin.
- #1888 historical parser isolation: [canonical Nit record](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7172824059); the pinned generator must not share the candidate link parser through its module path.
- #1889-B real-adapter same-revision assertion: [canonical Nit record](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7168730806); fixture-adapter success does not discharge it.
