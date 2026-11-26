# #1888 lane and reader evidence

<!-- lanes-demonstrated run=436421200a034ac5ab42a4fe1c242621 plan=c3f199fe2354e95a925ec1dbfbf7ead9f85f22c89f724827de7b4d95704998c5 -->

| Lane | Result | Evidence |
|---|---|---|
| Checkout | passed | Actual CLI from full main-style checkout and real linked worktree in test_actual_cli_build_then_verify_complete_output |
| Harness | passed | Independent Codex parity plus actual AGY 1.5.17 python-packaging consumer, authorized attempt 4 at product 85dd9397; see maintained measurement |
| Driver | not applicable | No flow or delegated-driver instruction change |
| Coordination | not applicable | Core local-lock implementation unchanged; final full gate will use its direct renewing supervisor |
| CI provider | not run | PR not opened; no provider behavior change |
| Project state | passed | Actual CLI builds complete output then detects missing guide; core fixture tests preserve edits and refuse unsafe/colliding output |
| Toolchain version | not run | Host Python only; no matrix claim. AGY probe independently checks 1.5.17 before invoking |
| Clone shape | passed | Main/full and depth-one source clones; linked worktree; historical parity is vendored and does not fetch old Git objects |
| Run location | passed | Both parameters of real CLI test: CPP root and external temporary cwd |
| Gate target | not applicable | No consumer quality-gate runtime selection change |
| Wave role state | not applicable | No role/mailbox registry change |
| Reader: core adapter | passed | Real ExpectedBuild package/member bytes feed actual core refresh/inspect and are rehashed |
| Reader: CLI | passed | Actual subprocess CLI emits real core reports across six shape/cwd combinations |
| Reader: AGY skill invocation | passed | Attempt 4 consumed the real two-member package in an unrelated project with decoys and scratch source/build removed; guide hash/tail matched, fresh missing-guide run reported missing |
| Reader: Codex consumers | passed | Independently loaded historical/current generators with separate parsers compare exact paths/bytes/modes; current generator unchanged |
| Reader: status/shared updater | not covered | #1889-B/#1892/#1893 |

At fcad40b6 the complete focused suite passed 19 tests, and the actual default
Make build/check both reported current for all 18 topics. The approved product
passed 29 focused tests; the final probe/evidence delta passes 31 focused tests.
Registered controls pass 2 GOOD, 3 BAD and
1 UNKNOWN; a blind inspector misses all three BAD inputs.

Regression evidence against the preceding WIP: reference-style/image/HTML
resources were omitted (red), preflight touched a descendant before rejecting
its symlink ancestor (red), and a missing plain guide instruction produced no
error (red). All three cases passed after their respective fixes. These are
new-builder WIP regressions, not claims about code existing on old main.

The Codex negative cases deliberately change the current transform and current
parser independently; each comparison fails. The pinned parser is digest-checked
and loaded from beside the pinned generator. Historical payload comparison has
no unattributed delta at measured umask 022; exact two-generator mode parity
also passes under 002. Missing historical baseline is an error, never a skip.

The probe response oracle accepts exact guide path/hash/tail and rejects wrong
hash, project decoy path, wrong tail, native failure and false missing state.
Its missing-guide positive input requires the guide to be physically absent.
Profile guard tests reject a symlink before touching its descendants.

Live topic acceptance was observed in attempt 4; attempts 1-3 remain UNKNOWN
and are recorded individually in the maintained measurement. The separate probe path and per-case control
seed files instantiate the approved mailbox 40220 probe/control conditions;
they do not widen product scope. No host production adapter is enrolled.

Pass 1 corrections, all accepted: scope is now the canonical package plus
`docs/skills/` and the explicit C4 helper allowlist. Other repository references
route upstream without reading their contents or bundling directories.
spec-driven-dev drops from the reviewed 317 files to 2; all 18 topics have
1-3 members. The bounded-closure GOOD control and three unit regressions ran
red against exact 3066cb85 (closure, system ancestor, snapshot parser binding)
then green after correction. The stderr-help regression ran red on the
extracted unchanged stdout-only check, then green with both streams. The
probe fix is cherry-picked without a separate push from 078e7426. See the
maintained measurement for per-topic counts and all four host attempts.

The final evidence delta imports the exact 5e95f3f7 probe, pinned 1.5.17 help
fixture and argv/environment tests, with no builder/core change. Extra formal
pass 3 is justified by the post-pass-2 probe runtime corrections, new observed
live evidence and the one-run owner exception for keyring exposure. The owner
[ruling](https://github.com/cooneycw/claude-power-pack/issues/1888#issuecomment-7176568634)
applies only to attempt 4, not future reruns. Authentication uses the inherited
user-session keyring. This establishes configuration isolation; it does not
establish credential isolation. No unobserved adapter/runtime capability was upgraded.
