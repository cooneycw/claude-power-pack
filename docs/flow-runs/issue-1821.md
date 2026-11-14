# Flow run record - issue #1821

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=daff6dbf76224a8abff25c94f7c98a1d -->
## Run 1

- Run-id:            daff6dbf76224a8abff25c94f7c98a1d
- Run-start:         d90712eed2523fc2128674a54ffa7923f8bf2c54
- Issue:             #1821
- Base SHA:          d90712eed2523fc2128674a54ffa7923f8bf2c54
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), in-session "approved" reply to the Step 3 report
- Recorded at:       2026-11-14T16:35:43Z

### Section B evidence
- Commits since issue filed (2026-11-14T16:29:40Z) touching scripts/flow-plan-record.py, tests/test_flow_plan_record_lanes.py, controls/flow-plan-record-lanes-verdict: none. Worktree base d90712ee is the reviewed SHA.
- Merged PRs same day: #1808, #1812, #1813, #1814, #1815, #1816, #1817, #1819, #1820 - none change the close-time binding (#1815/#1816 call the same compliance and inherit the defect).
- Related issues: #1695, #1731, #1767, #1809 (closed, built the feature); #1822, #1823 (open siblings, no overlap). No duplicate.

### Section C - the approved plan
Approach: at a successful approve, stamp into the worktree git dir (beside the baseline) the run id, approved-plan digest, whether a lane file existed, the will-test lanes, and the demonstration rows already present. At close, obligations come from that stamp, not the lane file's current state; a row counts only if new or changed since this run's approval. No stamp: a plan owing nothing stays byte-identical; a plan with will-test lanes reads LANES NOT CHECKED with a re-approve remedy.

1. `scripts/flow-plan-record.py` - approve writes the lane stamp; lanes_at_close reads obligations/adoption from it, counts only post-approval rows, not-checked for missing/malformed/foreign stamp or changed plan digest; new stderr notes.
2. `tests/test_flow_plan_record_lanes.py` - red cases (previous-run evidence, lane file deleted after approval, rewritten stale row counts, re-approval rebinds, no-stamp fallback); line-861 test re-specified; combination test approval x close; unusable-at-close test becomes obligations-survive.
3. `controls/flow-plan-record-lanes-verdict/run-case.py` - support evidence written before approval and a lane file deleted after approval.
4. `controls/flow-plan-record-lanes-verdict/control.json` - two new BAD cases and updated limits.
5. `controls/flow-plan-record-lanes-verdict/cases/` - new bad-previous-run-evidence and bad-lane-file-deleted-after-approval case directories.
6. `docs/agents/lanes.md` - At close: obligations from approval, evidence only after it.
7. `docs/agents/flow-plan-record.md` - same in the plan-record background.
8. `docs/scripts/flow-plan-record.md` - #1821 history line.
9. `CHANGELOG.md` - Unreleased entry.

Scope: ~9 files, ~250-400 lines, mostly tests.
Risks: other tests/controls that write the demonstrated file before approval would need edits (would show as divergence and be explained); runs approved by the old helper and closed by the new one read LANES NOT CHECKED until approve is re-run (intended, visible).

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | existing plain-repository and linked-worktree fixtures (make_checkout) rerun with the new cases |
| Harness | not covered | the helper ships unchanged into the Codex flow-auto bundle; no Codex install run exercised |
| Driver | will test | the existing delegated-plan-lanes close tests and controls rerun against the new helper |
| Coordination | not applicable | no Kyle path involved |
| CI provider | not applicable | no CI provider output read |
| Project state | will test | lanes adopted at approval vs never adopted; lane file deleted or damaged after approval |
| Toolchain version | not applicable | no interpreter or uv behaviour changes |
| Clone shape | not applicable | no history or ref reads change |
| Run location | not applicable | the helper still resolves the repository root the same way |
| Gate target | not applicable | not a gate-target path |
| Wave role state | not applicable | no wave registry involved |
