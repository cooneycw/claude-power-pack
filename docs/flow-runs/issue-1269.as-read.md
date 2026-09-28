# Issue #1269 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1269
- Read at:      2026-09-28T09:56:54Z
- updatedAt:    2026-09-26T14:12:44Z   (context only - moves on comments and labels)
- Body digest:  b5a2e8c16f9094bf615297de17ccb27582616d661528fd91d284ddddd96133b1   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2593 of 2593 (cap 16384)

## Body as read
**Wave W3E**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S3**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S3** counter-model-receipt.py write creates a receipt file the test suite requires tracked, but never stages or warns (live; found during /flow:auto #980 (PR #1065))
  - evidence: scripts/counter-model-receipt.py cmd_write (~L533-585): no `git add`, no untracked-file notice
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5742248694
- [ ] **S3** Counter-model receipt's derived reviewer field has no auditable evidence pointer (no thread_id/exec-log link) (live; related #1048, #1091; found during #1091)
  - evidence: scripts/counter-model-receipt.py build() (~L359-390) records only reviewer/implementer strings; no thread_id or exec-log path field in the schema
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5744072147
- [ ] **S3** _derive_reviewer_from_exec_log takes first regex match over whole rollout, unreproduced (live; related 1109; found during #1109)
  - evidence: scripts/counter-model-receipt.py:220 re.search over full rollout_text, first match used
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5748929792
- [ ] **S3** Subagent (isSidechain) records could supply implementer identity, unchecked (live; related 1109; found during #1109)
  - evidence: scripts/counter-model-receipt.py:234-257 _eligible_assistant_model checks only type==assistant and message.model, no isSidechain guard
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5748930427
- [ ] **S4** Three counter-model reviews ran with no receipt written, undercounting the corpus (live; related 1171; found during #1171)
  - evidence: docs/measurements/counter-model/ has no receipts for PRs behind #1165/#1166/#1162 (pre-#1171); #1171 bounded the new coverage rule to start after that merge rather than backfill, so the historical gap is permanent by design
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5758216821

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).
