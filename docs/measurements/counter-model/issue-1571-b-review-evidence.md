# Issue 1571-B review history

Primary canonical receipt: `2026-10-26T101632Z-issue-1571.json` records only actual T3 at source head `16b034b2e51b44db0cbe8027720cb88644a49b95`, with zero findings and five static adverse-input categories already represented in maintained tests. It does not assert one whole-final-tree review. `scope: full` describes filesystem capability, and `network: open` means no mechanical network fence. Ordinary service credentials were withdrawn; repository credentials were absent. Each call had its own unchanged HEAD/index/status/content/mode/symlink snapshots.

[Full review history](../counter-model-evidence/issue-1571-b-review-history.json) preserves original incomplete passes 1/2, all eight old-head PASS3 reports and all three targeted reports, actual threads/models/times, assigned pieces, output availability audits, hashes and worker execution proof. Availability is separate from semantic reading. Earlier sandbox/interrupted probes supplied no coverage. Historical pending dispositions are retained verbatim and superseded by the explicit current dispositions.

Eight serial actual Astra PASS3 calls reviewed approved base `3a8a1fc028fd678524446760c5ff0200f5f84050` to `cbfa3e85fd78628ef2cb1c28e4e6b434cd5b04a8`: 34 paths, 84 pieces, four findings. All were accepted and fixed in `16b034b2`. Three further explicitly authorized serial actual Astra calls reviewed only the fix delta: 15 paths (14 direct, one derived mirror), 34 pieces, no findings. Each reviewer declared its own scope COMPLETE. Root accepted results in message 10230. No inherited early-pass completeness or global clean verdict is claimed.

| Finding | Current disposition | Targeted coverage |
|---|---|---|
| B2 LOW CPP population | Fixed independent five-init/two-auto fenced invocation census before command assertions; four adverse cases | T2 |
| B4 MEDIUM target pin | Fixed bounded nonblocking descriptor observation and real Runner regressions; five BAD/five GOOD registered controls and blind anchor | T1/T2 |
| B7 LOW census attribution | Fixed AST decoder/restoration versus entrypoint ordering and AST sentinel versus actual Runner attribution; generated mirror | T3 |
| B8 MEDIUM host observation | Fixed same real snapshotted calls stdout/code validation, full seven-check population and engine missing, actual no-output exit-1 negative | T3 |

Canonical finding records: [B2](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6410844581), [B7](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6411312607), [B8](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6411425329). B4 issue 1577 was administratively closed as not planned by root/master because it concerned unmerged B; that closure was not a fix claim. The fix is in this branch.

Worker evidence includes genuine pre-fix five population/observation failures, three pin refusals failing versus three positive cases passing, then 150 focused passes, registered control positive/negative agreement and blinded misses, quality checks, and pinned scanner known-bad/history checks. Reviewers did not execute these. Original gate at `4cb4022f` remains FAILED: seven failed, 8587 passed, three skipped; downstream controls did not run. Its original logs/status/state/hash are retained. Fresh full gate on an evidence-only descendant of `16b034b2` is authorized but has no result yet. This evidence commit changes no product source.

## Post-review derived anchor correction

The first fresh gate on evidence-only descendant `4fc78ee409a86421c506fd6002d79af89e197ea7` failed: one failed, 8630 passed, three skipped in 372.83 seconds. `tests/test_regenerate_blind_anchor.py::test_a_the_real_committed_anchor_matches_the_real_gate` found the host observer constructed anchor missing the current four-line `flow-preflight.sh` invocation classification. The full log remains externally preserved with SHA-256 `85d1e0f3207b2436c7cc7ae73270599b4d406d505711d2ea396d43f45f422a07`; downstream controls were not run. This does not replace the earlier failed gate.

After root/master assessment, the standard `regenerate-blind-anchor.py host-surface-observe --write` regenerated only those four lines and the registered anchor digest. The stored blind patch, root adaptation, production source and canonical review receipt were unchanged. This post-review derived change was not reviewed by Astra; master message 10240 authorized root assessment instead of another model pass.

The real old anchor check failed with exit 1 before regeneration; the exact check passed with exit 0 after it. All 50 existing regenerator and host observer tests passed, including the regenerator's mutated-gate drift, idempotent regeneration and patched-context refusal cases. The registered host control rejected `bad-understated` with exit 1, accepted `good-declared` with exit 0, and the constructed blind anchor missed the known-bad input. Constructed provenance remains reported as unverified. Lint, Markdown checks and eleven project-next ownership pins passed. No fresh full gate after this derived correction has run; root assessment is pending.
