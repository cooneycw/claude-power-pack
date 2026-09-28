# Issue #1266 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1266
- Read at:      2026-09-28T15:09:08Z
- updatedAt:    2026-09-26T14:12:41Z   (context only - moves on comments and labels)
- Body digest:  7fd6d763e1571d5c8f08bd0aa3d6afb69b9513994b8b90041f7d05cbcccf5f79   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5811 of 5811 (cap 16384)

## Body as read
**Wave W3B**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S2**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S3** flow-wave-registry.sh register computes lane delta/read-backs outside the write lock, race on concurrent same-owner registration (live; related 1026; found during 1026 counter-model review)
  - evidence: scripts/flow-wave-registry.sh:2253 CUR=... read before with_lock (:2380), NEW_ENTRY read after lock release (:2506) - pattern unchanged; author notes narrow practical exposure
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5740601889
- [ ] **S3** A newline inside a lane path breaks the line-oriented FLOW_WAVE_* output protocol (live; related 1026; found during 1026 counter-model review pass 2)
  - evidence: scripts/flow-wave-registry.sh - output side of FLOW_WAVE_FILES/_DROPPED/_ADDED still unescaped/line-oriented while lane_split's input side (read -r -d "") tolerates embedded newlines; file-wide pre-existing property since #638, not fixed
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5740602429
- [ ] **S3** flow-wave-registry --pr cannot be cleared once the PR merges (live; found during kyle#1210, wave kyle-improvements)
  - evidence: scripts/flow-wave-registry.sh:2348 still `usage_fail "--pr needs a value..."` on an empty --pr; author's own measurement found this does not corrupt the #989 starvation signal
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5796836422
- [ ] **S3** flow-wave-registry keeps stale lane facts when re-registering into a different repo under the same issue number (live; found during issue #1222)
  - evidence: scripts/flow-wave-registry.sh:2391 `$moved` predicate still compares only `$prev.issue != $issue`, no repo-identity comparison
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5813736551
- [ ] **S3** flow-wave-residuals.py has no amend verb; correcting a fact requires mislabeling it 'duplicate' (live; found during orchestrating wave cpp-completion)
  - evidence: scripts/flow-wave-residuals.py:617-677 verb dispatch is only record/close/promote/metrics, no amend/update/correct
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5678062786
- [ ] **S3** flow-driver-capability.sh does not declare flow:auto_codex, routing checks return unknown (live; related 783; found during cpp-completion wave setup)
  - evidence: scripts/flow-driver-capability.sh:190 DRIVERS="flow:auto codex:auto qwen:auto gemma:auto" still omits flow:auto_codex
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5677860629
- [ ] **S3** flow-driver-capability.sh still has no profile for flow:auto_codex, a driver actively used as a wave policy driver (live; related 783; found during orchestrating /flow:wave codex-completion)
  - evidence: Same DRIVERS list at scripts/flow-driver-capability.sh:190 confirmed unchanged; independent re-discovery of idx=50's defect
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5678793393
- [ ] **S3** Lane grants don't implicitly carry a bundled source's generated skill mirrors (partially-delivered; related 1151; found during orchestrating #1132)
  - evidence: scripts/codex-skill-sync.py now has --list-mirrors (#1151, closed) enabling non-mutating enumeration, but register.md/wave.md still have no text stating a granted path implicitly carries its mirrors
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5751411764
- [ ] **S2** Derived-scope issue can't declare its lane at Step 4; no re-register prompt (live; found during #1139, codex-conversion wave)
  - evidence: No text in .claude/commands/flow/register.md or flow/auto.md requiring re-registration after a scope derivation; grep for 're-register'/'derivation'/'creation included' finds no such rule
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750935370
- [ ] **S2** Toolchain-behind warning omits the 'checkout' field naming its own subject, causing mis-attribution (live; related 1029; found during #1068 / PR #1134)
  - evidence: scripts/flow-wave-registry.sh:2637-2672 extracts verdict/behind/upstream/fetch_age_seconds but never a checkout var; message says "this session's CPP toolchain" not the checkout path
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750409421
- [ ] **S3** docs/slate-lanes.json has an inherent one-PR-cycle staleness window by construction (live; related #1047, #1094; found during merging #1103 (issue #1047))
  - evidence: design-limitation finding about a hand-maintained snapshot file referencing its own PR's outcome; no fix proposed, tradeoff unchanged
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5744828177
- [ ] **S3** flow-vantage.sh's host/container signal is defeated by docker run --pid=host (live; related 959; found during counter-model review of PR #1130 / issue #959)
  - evidence: documented as a stated bound in script header and controls/flow-vantage/control.json limits; not a live issue for the measured kyle container (separate pid namespace)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750219070

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).
