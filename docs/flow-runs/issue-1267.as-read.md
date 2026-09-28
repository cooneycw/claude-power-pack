# Issue #1267 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1267
- Read at:      2026-09-28T14:05:11Z
- updatedAt:    2026-09-26T14:12:42Z   (context only - moves on comments and labels)
- Body digest:  54f6e7ce6b65dbb963c6cb34736e98efdb9991ab02d3947a35cf39e1fa8efd64   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3235 of 3235 (cap 16384)

## Body as read
**Wave W3C**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S3**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S3** Plan compliance's mirror_source maps a generated SHA256SUMS manifest to a nonexistent scripts/SHA256SUMS source (live; found during issue #1232 / PR #1238)
  - evidence: The regex bug (`^codex/skills/[^/]+/((?:docs|scripts|lib)/.+)$`) has relocated from auto.md's inline block into scripts/flow-plan-record.py:311 (per #1211/PR #1252) but is unchanged; confirmed still live in the new location (see idx338)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5812196521
- [ ] **S3** Plan compliance's mirror_source cannot derive the source of a mirror bundled under codex/skills/<skill>/.claude/ (live; found during issue #1236 / PR #1240)
  - evidence: scripts/flow-plan-record.py:311 regex only matches docs|scripts|lib paths; a `.claude/` mirror (e.g. project-next-ownership.json) still reports "source could not be derived"
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5812203201
- [ ] **S3** flow-plan-record.py's mirror_source invents a source for generated SHA256SUMS manifests, false-divergence on every bundled-script change (live; found during issue #1211 / PR #1252)
  - evidence: scripts/flow-plan-record.py:311 confirmed: same regex bug ported verbatim from auto.md's old inline block per #1211/PR #1252; same defect as idx322/idx324, just relocated
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5819875153
- [ ] **S3** flow:auto Section C gives no guidance that the counter-model receipt isn't a plannable file, causing false divergence (live; found during issue #1226 / PR #1255)
  - evidence: No mention of excluding the counter-model receipt from Section C found anywhere in .claude/commands/flow/auto.md's plan-writing guidance
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5846284185
- [ ] **S3** docs/flow-runs/issue-<N>.md holds one plan record, so a second flow:auto run overwrites the first approval (live; found during issue #1189 / PR #1233)
  - evidence: .claude/commands/flow/auto.md still addresses the single fixed path `docs/flow-runs/issue-<N>.md`; no per-run suffix scheme found
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5811521167
- [ ] **S3** flow-worktree-claim.sh still requires --issue, blocking a claim for issueless residual work (live; found during issue #1189 / PR #1233)
  - evidence: scripts/flow-worktree-claim.sh:472 `[ -n "$ISSUE_NUM" ] || usage_fail "claim requires --issue <N>"` unchanged
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5811521457

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).
