<!-- flow-run n=1 id=b58c22cac5104b62bcb58f4e25bb10ac -->
## Run 1 - issue #1847 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1847
- Read at:      2026-11-15T20:30:25Z
- updatedAt:    2026-11-15T20:11:02Z   (context only - moves on comments and labels)
- Body digest:  cffe4ecb6ca6ee4a11c29c29cfea27a1ad2ac5cfe4814f21180ed65250dbbbd8   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3134 of 3134 (cap 16384)

### Body as read
Tier: 2

## Outcome

Running the second-model review is one helper call that prints its markers, the way Step 1 of `/flow:auto` is one call to `flow-start-resolve.sh`. Today the review is a script printed inside a command document, and the session has to assemble and run it by hand.

Measured: `.claude/commands/codex/code_review.md` is 6,216 words, of which 3,484 sit inside six fenced `bash` blocks (collect the diff, probe the sandbox, probe the network, withdraw credentials, run codex, relay). To run it on #1846 the session extracted five of those blocks and concatenated them into a scratch script. Nothing checks that a session does this correctly; a dropped block (the credential withdrawal, say) would still produce findings.

Source: observed while running `/flow:auto` on #1846 (2026-11-15), measured on main `f1253b45`. Part of the simplification asked for in [discussion #1830](https://github.com/cooneycw/claude-power-pack/discussions/1830). Related: #1669 (word budgets).

## Constraints

- **The markers and the findings format do not change.** `CODEX_REVIEW_SCOPE`, `CODEX_REVIEW_NETWORK`, `CODEX_REVIEW_LOCAL_CREDENTIALS`, `CODEX_REVIEW_MODEL`, `CODEX_REVIEW_STREAM`, `CODEX_REVIEW_BASE` and the `## Findings` / `## Red cases` shape are read by `counter-model-receipt.py` and by `/flow:auto` Step 6. Rationale: those are other parts' inputs.
- **Every measure the document takes today is still taken.** The network verdict table, the credential withdrawal and the scope probe each exist because of a recorded incident (#1261, #1450, #1458, #1459). Moving them is not removing them.
- **The existing tests keep the failures they detect.** `tests/test_code_review_*.py` read the command document's blocks. They move onto the helper; an assertion about the old document's block layout need not survive the move.
- **It is an extraction.** No new probe, configuration or assurance requirement rides along; whether a review is required at all is #1850's question.
- **The reviewer prompt stays readable in one place**, since #1846 just edited it and later edits will too.

## Acceptance

- [ ] One helper runs the review end to end and prints the markers; `code_review.md` calls it bare.
- [ ] `code_review.md` shrinks by at least the moved shell, and its budget row in `.claude/command-word-budgets.tsv` is lowered to match.
- [ ] `/flow:auto` Step 6 item 1b and the receipt write in 1d read the helper's markers with no hand-carried variables.
- [ ] The network-fence, sandbox-scope, diff-range and cleanup tests pass against the helper, each still red on its known-bad case.
- [ ] One real review run through the helper, with its receipt, cited in the closing report.

## Proposed approach

`scripts/codex-review-run.sh <base> <context> --transcript <file>`, holding the current blocks unchanged, with the prompt in a sibling text file the helper reads. Then register it (verify-coverage, scripts inventory, census) as any new script.

## Assumptions

- The five registrations a new script needs are affordable here. Not checked.
- No consumer repository copies the fenced blocks out of the document. Not checked.



<!-- end of body -->
