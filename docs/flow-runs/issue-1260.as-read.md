# Issue #1260 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1260
- Read at:      2026-09-27T10:38:41Z
- updatedAt:    2026-09-26T14:12:34Z   (context only - moves on comments and labels)
- Body digest:  60f439f46ffe186fb294ca39aba3defb48ef7dad010ec1b28b70cf60588ec8e7   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4931 of 4931 (cap 16384)

## Body as read
**Wave W1C**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S1**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S1** flow-wave-mailbox.sh send --body - stores the literal dash and reports delivered success (live; found during cooneycw/kyle#1284, wave kyle-revisions)
  - evidence: scripts/flow-wave-mailbox.sh:2015-2083 --body "$2" taken literally; [ -n "$BODY" ] guard passes for BODY="-", no stdin-marker handling
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750143816
- [ ] **S1** supervise daemon's mkdir -p recreates the wave dir, hiding the evidence its wave is gone (live; related 1116; found during #1116 / PR #1119)
  - evidence: scripts/flow-wave-mailbox.sh:1870 mkdir -p "$WAVE_DIR" runs on every verb including inner re-arm at :2668
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5749711071
- [ ] **S1** Wave roster exempts orchestrator from lane-overlap checks by role name regardless of a declared file lane (live; found during wave codex-conversion, holding #1126 / PR #1131)
  - evidence: scripts/flow-wave-registry.sh:3742-3745 `if [ "$r" = "orchestrator" ]; then EXEMPT_ROLES=...; continue; fi` unconditional, ignores r_files
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750282910
- [ ] **S2** flow-wave-registry.sh list creates the wave mailbox dir it reports on (live; found during /flow:register worker-D --wave kyle-improvements)
  - evidence: scripts/flow-wave-mailbox.sh:2053 `mkdir -p "$WAVE_DIR"` runs unconditionally before verb dispatch, for list/watch/read alike (same code path confirmed at idx=284)
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5764030715
- [ ] **S2** flow-wave-registry.sh list creates the wave it queries (duplicate finding of idx=267) (live; found during wave claude-improvements, worker-A)
  - evidence: Same code path as idx=267: scripts/flow-wave-mailbox.sh:2053 unconditional mkdir -p on every verb including list
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5775231286
- [ ] **S2** flow-wave-registry read_registry treats an unreadable registry file as an empty one (live; found during issue #1107, counter-model review pass 2)
  - evidence: scripts/flow-wave-registry.sh:863 unchanged: `if [ -s "$REG_FILE" ]; then cat ...; else echo '{}'; fi` -- EACCES and missing/0-byte both read as `{}`
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5819204261
- [ ] **S2** watch_state_of renders armed (not no-wake) when watcher session lineage is unknown (live; found during counter-model review of PR #1237 / issue #1228)
  - evidence: scripts/flow-wave-mailbox.sh watch_state_of(): `case "$sess" in 0) echo no-wake ;; esac` only triggers on a confirmed 0; any other value including unknown falls through to armed/stale. Deferred deliberately per ADR 0009 per the finding's own text.
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5811737647
- [ ] **S2** flow-wave-mailbox.sh supervisor defers SIGTERM/SIGINT until its current --timeout watch call returns (live; related #1033; found during #1033 live reproduction)
  - evidence: scripts/flow-wave-mailbox.sh:2863 trap 'log_event ...; exit 0' TERM INT guards a loop whose blocking call is still `bash "$0" watch --peek --timeout "$TIMEOUT"`; structure unchanged, not re-timed here
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5744013970
- [ ] **S2** Stand-down report claims watch stopped and lane released when both were still live (unverified; found during post-shutdown scan of wave kyle-improvements (owner request))
  - evidence: scripts/flow-wave-mailbox.sh has owner-death exit logic for the `supervise` daemon (L2810,2881, issue #814) but no equivalent found for the bare `watch` verb the report describes; could not locate a stand-down self-probe in a quick scan
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5799140058

## Negative control (ADR 0008)

`send --body -` with stdin must deliver the stdin text, or refuse; it must never report success on a literal `-`. Running `list` or `supervise` against a deleted wave must leave it deleted and report it absent. An unreadable registry must read as unknown, not empty. An orchestrator with a declared lane that overlaps a worker must be flagged.

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).
