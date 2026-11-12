# Flow run record - issue #1691

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=b9b2e411f26c49cfb9cad64d0c009e02 -->
## Run 1

- Run-id:            b9b2e411f26c49cfb9cad64d0c009e02
- Run-start:         ca9189738bbd450033ea0a661c466d6a9cd88963
- Issue:             #1691
- Base SHA:          0bf7ba72
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1691", outbox rev 59, 2026-11-12T00:28:44-05:00
- Recorded at:       2026-11-12T05:35:00Z

### Section B evidence
- No commit on the five wave scripts since filing. Siblings #1693 and #1692 ended at minus 2.5 and minus 2.8 percent
- Survey of 10,675 lines: about 15 lines of dead code, 55 to 70 of exact duplication, 257 of movable history; no dead subcommand or flag, no refusal that has stopped earning its place
- A real process whose main thread exited read stale owner-zombie in the registry and its role was taken over without --force; the mailbox's owner_gone has the same misread
- One wake of watch prints and acknowledges every unread message; the "one message" sentence in three places is wrong
- A re-register naming a different issue resets the file lane by design (#1222); the documents say flatly that --files is preserved

### Rulings and gate conditions (orchestrator)
- Reframed: a correctness fix, an accuracy pass and the small exact tidy; no reduction number is chased. Acceptance amended on the issue.
- PR 1 may land during the wave and changes NO executable line: comments, help headers, the two command documents, the docs pages, docs/scripts.md and two new tests. Each script with comment-only and blank lines stripped is byte-identical to main except the named help-header regions. The four mailbox header lines a test pins stay.
- PR 2 is held until the orchestrator says the wave is at its last merge: the code tidy, the state-Z fix in the registry and the mailbox with real-process tests, and the DROPPED line saying why (one test). Before and after captures for each tidy.
- The RATIFY: spelling is its own issue (#1752). The four not-planned items are listed in one comment on #1691.
- wave.md and register.md: word counts before and after to the orchestrator; no budget raised.
- History moves to the docs pages before it leaves the scripts, in separate commits; conservation checked at each.
- Independent old-versus-new read before review.
- PR 1 queues behind #1726 PR A. make lint, make typecheck, make shellcheck read to the end; two review passes each.

## Section C - the approved plan
  1. `scripts/flow-wave-registry.sh` - PR 1: comments and help header brought in line with the code, history moved out. PR 2: dead function deleted, exact duplicates merged, pid_state state-Z rule, the DROPPED line says why
  2. `scripts/flow-wave-mailbox.sh` - PR 1: the one-message sentence corrected, help header completed, history moved out. PR 2: dead functions deleted, the inline awk replaced, owner_gone state-Z rule
  3. `scripts/flow-wave-lexicon.sh` - PR 1: history moved out. PR 2: dead function deleted
  4. `scripts/flow-wave-plan.py` - PR 1: comment lines that restate the docstring removed
  5. `.claude/commands/flow/wave.md` - the one-message sentence; the lane-reset exception
  6. `.claude/commands/flow/register.md` - the same two corrections
  7. `docs/scripts/flow-wave-registry.md` - receives the moved history
  8. `docs/scripts/flow-wave-mailbox.md` - receives the moved history
  9. `docs/scripts/flow-wave-lexicon.md` - receives the moved history; one misfiled bullet
  10. `docs/scripts.md` - one wrong link
  11. `tests/test_flow_wave_reregister_matrix.py` - new: re-register changing one flag at a time
  12. `tests/test_flow_wave_watch_delivery.py` - new: every unread message is delivered in one wake
  13. `tests/test_flow_owner_zombies.py` - PR 2: a real main-thread-exited process keeps its role and its watch
Scope: 13 files, two PRs.
Risks: this wave runs on these scripts; help text is output; PR 2 flips a liveness verdict from stale to live for one process shape.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | The re-register matrix runs from a main checkout, a linked worktree and a directory outside any repository |
| Harness | will test (Claude install); not covered (Codex install) | The scripts are run through the checkout the install links. No test runs a wave from a Codex bundle |
| Driver | not applicable | No driver-facing output changes in PR 1; PR 2 changes a liveness verdict the same way for every driver |
| Coordination | will test (without Kyle); not covered (with Kyle) | The registry, mailbox and completion tests run without Kyle; the Kyle path is not touched |
| CI provider | not applicable | Nothing provider-dependent |
| Project state | not applicable | No adopted file or record is read |

<!-- flow-run n=2 id=92f82acff32c4d93992af603363fd658 -->
## Run 2

- Run-id:            92f82acff32c4d93992af603363fd658
- Run-start:         4f34005f441b066282d58809b2138f2007bc3819
- Issue:             #1691
- Base SHA:          95f2aa89eee6a3eee5f40a251321bf47ab01ee40
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "#1691 PR 2 plan: APPROVED, Section C as written, with four conditions", outbox rev 113
- Recorded at:       2026-11-12T09:35:00Z

### Section B evidence
- The first change (run 1, PR #1776, merged as 71feea1c) was comments, help and documents only; this is the code half of the same survey.
- #1709 put the same zombie-leader rule in `flow-worktree-claim.sh`; it is the reference for item 11.
- Readers of the registry's or mailbox's owner state in other repositories, searched at their default branches: kyle 1b3d2eb4, skillc 26e686a, kyle-candidate ff510172 - none reads `owner-zombie` or `stale owner` (0 files each; the same search finds `flow-wave-registry` in 4, 76 and 4 files, so it can find something). kyle's mentions are comments, a document and container mount fixtures; skillc's are vendored copies.
- Not in this change, each on the issue with its reason: the items in comment 6815547310, the `self_chain_*` fold, and the DROPPED-line wording (#1762 decides that line). #1752 is separate.

### Rulings and gate conditions (orchestrator)
- Merges last: it changes scripts the wave is running on.
- Item 6: no `| sort -n | head -1` under pipefail; take the minimum in awk or read to the end. Check items 5 and 7 for the same shape. Say in the PR what each script sets.
- Item 11: fails safe both ways; the red case is run on the unchanged scripts first and stated; a test is acceptable where the registry control's anchor does not allow a case; no new control.
- The identity capture for items 1 to 8 must be able to fail: shown red once by changing one printed byte in a scratch copy. It captures every subcommand including the usage-error paths.
- Two review passes at most; a second medium on any one item drops that item. Full suite before the gate.

### Section C - the approved plan
1. `scripts/flow-wave-registry.sh` - items 1, 4, 7, 8: delete `_is_checkout_root`; `close` uses `path_state`; one function each for the unregistered-claim rows and the driver-capability lines; the script directory computed once. Item 9: the two usage lines that say `--files` is preserved. Item 11: `pid_state` counts state Z as dead only for a single-threaded process
2. `scripts/flow-wave-mailbox.sh` - items 2, 5, 6, 8: delete `ackob_count` and `watcher_count`; `send` calls `max_rev`; `oldest_unacked_rev` takes its minimum without a pipe that can be cut short; the script directory computed once at the three identical sites. Item 11: `owner_gone` takes the same thread-count rule
3. `scripts/flow-wave-lexicon.sh` - item 3: delete `lower`
4. `scripts/flow-wave-plan.py` - item 10: one trailing comment
5. `tests/test_flow_wave_owner_liveness.py` - item 11: a zombie leader with a live thread, a single-threaded zombie, an unreadable thread count, for both scripts
6. `tests/test_flow_wave_output_identity.py` - items 1 to 8: every subcommand's output, usage errors included, byte for byte against the scripts as they were
7. `docs/scripts/flow-wave-registry.md` - one line for this change
8. `docs/scripts/flow-wave-mailbox.md` - one line for this change
9. `docs/scripts/flow-wave-lexicon.md` - one line for this change

Scope: about 60 to 80 lines removed or folded in three shell scripts, about 12 added for the liveness rule, two new test files.

Risks: item 11 changes when a role can be taken over, so a wrong thread-count read must fail safe and is tested both ways; items 5 and 7 sit on `send`, `register` and `get`, which a live wave runs every minute; the helpers are linked into every session, so the change is live for the next command after the main checkout updates.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | The identity capture and the liveness tests run the scripts from a main checkout and from a linked worktree |
| Harness | will test (Claude install); not covered (Codex install) | The scripts are run as the installed copies are, through the checkout; no wave is run from a Codex bundle |
| Driver | not applicable | No driver-facing output changes |
| Coordination | will test (without Kyle); not covered (with Kyle) | The registry and mailbox are driven directly in an isolated wave directory; the Kyle path is not touched |
| CI provider | not applicable | No pipeline file or provider call changes |
| Project state | not applicable | No adopted file or record is read |
