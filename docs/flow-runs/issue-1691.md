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
