<!-- flow-run n=1 id=9ba4688537ad4b78ad8dd1981c6c7481 -->
## Run 1 - issue #1848 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1848
- Read at:      2026-11-15T22:41:18Z
- updatedAt:    2026-11-15T20:11:03Z   (context only - moves on comments and labels)
- Body digest:  47a17dd77169004a67a25e9b3458287b805c77188c9150d1f26ae140a4411b5a   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2798 of 2798 (cap 16384)

### Body as read
Tier: 2

## Outcome

`/flow:auto` stops restating what its helpers already say. When a helper stops a run, the document's instruction is one rule: relay the helper's own line and never override it. The helper's output carries the meaning and the next action.

Measured in `.claude/commands/flow/auto.md` (10,410 words, exactly on its budget):

- about 35 lines explain individual helper exit codes (`gh-pr-merge.sh` 3 to 12, `worktree-remove.sh` 4 to 8, the finish gate's five verdicts, the worktree guard's four).
- "exit 127" appears 15 times: the same fallback (plugin copy, then the checkout copy, then tell the user to run `/flow:repair`) is written out at nearly every helper call.

This is the rule from discussion #1830 applied to the document itself: prose comes out when a check already guards the same mistake. It also buys room. On #1846 a four-line edit had to be word-neutral because the file has no words to spare.

Source: observed while running `/flow:auto` on #1846 (2026-11-15), measured on main `f1253b45`. Part of the simplification asked for in [discussion #1830](https://github.com/cooneycw/claude-power-pack/discussions/1830). Related: #1669 (word budgets).

## Constraints

- **No stop is lost.** Every exit that stops a run today still stops it. A helper whose output does not already name the remedy gets that line added before the prose is removed, never after. Rationale: #1669 recorded 21 instructions lost in an earlier trim.
- **"Never retry with an override yourself" stays in the document**, once, since it is an instruction to the session and no helper can enforce it.
- **The delegated drivers are handled in the same change or explicitly left**, because `driver-parity-check` compares the surfaces.
- **The budget goes down, not sideways.** The freed words are returned by lowering the row in `.claude/command-word-budgets.tsv`.

## Acceptance

- [ ] The missing-helper fallback is stated once in `flow/auto.md` and referenced, not repeated.
- [ ] Each per-exit-code bullet is either removed (the helper prints the meaning and remedy, shown by a test of the helper's output) or kept with a one-line reason why the helper cannot say it.
- [ ] An independent old-versus-new instruction read finds no **accidentally** lost instruction, as #1669 requires for a trim. An instruction withdrawn on purpose is listed separately with the owner's authority for it (#1846, #1850); the read must not preserve an obsolete obligation by default.
- [ ] The `flow/auto.md` budget is lowered by the amount removed.

## Proposed approach

Start with `gh-pr-merge.sh` and `worktree-remove.sh`, which have the longest tables, and do the finish gate last.

## Assumptions

- Each helper already prints a marker line per stop. True for the ones read on #1846; not checked for all.



<!-- end of body -->
