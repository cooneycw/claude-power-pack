# Flow run record - issue #1709

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=8e32b81e25864259ada028521eeac5ca -->
## Run 1

- Run-id:            8e32b81e25864259ada028521eeac5ca
- Run-start:         a88aafddcd0676cf5c454141ba2aadac88754687
- Issue:             #1709
- Base SHA:          a88aafddcd0676cf5c454141ba2aadac88754687
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1709", outbox rev 32, 2026-11-11T21:17:33-05:00
- Recorded at:       2026-11-12T02:30:00Z

### Section B evidence
- commits since filing: 0dea8c26 (#1693) touched worktree-remove.sh comments and help only; none on flow-worktree-claim.sh or flow-worktree-sweep.sh
- duplicate/superseding issues: #1605 closed (zombie fix, PR #1635, commit 8151c53c)
- Row 710 measured against the real zombie on this host (pid 2186472): current main reads stale (owner-zombie); the copy skillc pins (85e9b03a) reads held, identity matched. 8151c53c is not an ancestor of skillc's or kyle's pin. The report came from an older copy.
- Found on the way: a live process whose main thread exited reads state Z and is called stale (owner-zombie) on main. Measured with a real process (num_threads 2, kill -0 succeeds).

### Rulings and gate conditions (orchestrator)
- R1: the thread-count condition (1c) goes in this PR.
- R2: the same misread in flow-wave-registry.sh is recorded on #1691 (comment 6812445610), not fixed here.
- R3: coordination issues filed before merge: kyle #2361, skillc #706, kyle-candidate #9. Link all three in the PR and on #1709.
- R4: row 607 is closed by 606's fix.
- Condition 1: a test per flip, and one table-driven test that no claim state turns held, foreign or unknown into stale.
- Condition 2: the sweep acts on exactly three stale reasons; every reason word is enumerated with its sweep outcome, and a made-up reason defaults to skip.
- Condition 3: stale-proven claim with an untracked file, and with an unpushed commit, are kept; --steal never appears in the sweep's call.
- Condition 4: retry the live Codex probe with a longer bound; otherwise write not covered (live Codex).
- Condition 5: the real main-thread-exited process and the real zombie both run in the gate.
- Condition 6: over-hold under a shared app-server is documented with how to clear it.
- Condition 7: make lint, make typecheck; two review passes; name the direction property in the review context. No push without the slot.

## Section C - the approved plan
  1. `scripts/flow-worktree-claim.sh` - Codex owner pid by walking to the nearest ancestor named codex when CLAUDE_PID is unset and CODEX_THREAD_ID is set; session falls back to CODEX_THREAD_ID; state Z with more than one thread is a live process
  2. `scripts/flow-worktree-sweep.sh` - a locked worktree whose claim is stale for owner-exited, owner-zombie or recycled-pid goes on to the existing five conditions; every other answer stays skip locked
  3. `tests/test_flow_worktree_claim.py` - Codex owner cases, the direction property, the multi-thread Z case
  4. `tests/test_flow_owner_zombies.py` - real zombie owner lets worktree-remove.sh proceed without --steal; real main-thread-exited process stays held
  5. `tests/test_worktree_sweep.py` - stale-proven claim cases, every reason word, the made-up reason, kept cases
  6. `docs/scripts/flow-worktree-claim.md` - the Codex owner rule, the thread-count rule, the over-hold and how to clear it
  7. `docs/scripts/flow-worktree-sweep.md` - which claims the sweep looks past
Scope: 7 files, about 45 lines of shell, about 220 lines of test. One PR.
Risks: matching the process name codex is a guess about one harness's tree, and a miss leaves today's behaviour; the sweep now removes worktrees it used to leave, only when the owner is proven gone and all five existing conditions hold.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | Claims exist only on linked worktrees; every claim and sweep test builds one. The main checkout cannot be locked and keeps answering unsupported |
| Harness | will test (Claude: real; Codex: simulated tree) | Claude: this session's own claims. Codex: the parent-chain walk against a fabricated /proc tree, plus one live codex exec probe if it can be made to run; otherwise not covered (live Codex) |
| Driver | not covered | A delegated driver runs the helper under the Claude session; no live delegated run |
| Coordination | not covered | What identity variables Kyle's containers export is not visible from here; asked in kyle #2361, skillc #706, kyle-candidate #9 |
| CI provider | not applicable | Nothing provider-dependent |
| Project state | not applicable | No adopted file or record is read |
