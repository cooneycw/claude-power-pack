<!-- flow-run n=1 id=01c876d2223847e588c20aaf5f3a1766 -->
## Run 1 - issue #1839 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1839
- Read at:      2026-11-15T12:17:59Z
- updatedAt:    2026-11-15T11:44:48Z   (context only - moves on comments and labels)
- Body digest:  f2353654c481757e7eec0298c874651bcf8516cf71b742a7f0942e2bc4a50186   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2488 of 2488 (cap 16384)

### Body as read
## What is wrong

`scripts/check-doc-helper-flags.py` (new in the PR for #1835) reads the command after each `~/.claude/scripts/<helper>` path with a small hand-written shell lexer. The third counter-model review pass (Codex, on the #1835 branch) found three inputs it gets wrong. None occurs in any live document today (the gate is green on the tree), so they were deferred rather than fixed on #1835, where the review pass cap was reached.

1. **False failure: outer flags after a substitution.** `echo $(~/.claude/scripts/mailbox.sh send --to o --body b) --kind` reports `mailbox.sh --kind`. Reading continues past the substitution's closing `)`, so `echo`'s flag is attributed to the helper. Location: `command_words` (around line 149).
2. **False failure: a quoted message continued onto the next line.** `--body "Please run \` continued onto a line holding `~/.claude/scripts/mailbox.sh --kind message"` reports an unknown flag. `inside_quote` restarts its quote state at each physical line (around line 170), so a helper path inside the continued quoted argument reads as a second invocation.
3. **Missed defect: a `(` inside quotes within a substitution.** `~/.claude/scripts/mailbox.sh send --to o --body "$(printf '(')" --kind message` passes. `strip_substitutions` (around line 77) counts parentheses without reading quotes, so the depth never returns to zero and the rest of the command, including `--kind`, is swallowed.

## Why it matters

The gate runs in `make verify` and the Woodpecker `doc-helper-flags-check` step. Shapes 1 and 2 would block every merge over valid documentation until someone rephrases the document. Shape 3 lets the defect class #1835 was filed for through. Each pass of review found new shapes in this lexer, which suggests the remedy is one quote- and substitution-aware tokenizer shared by all three functions, not three local patches.

## Suggested fix

Replace `strip_substitutions`, `inside_quote` and `command_words` with one tokenizer that tracks quote and `$(...)` nesting across `\` continuations, stops at the helper's own substitution boundary, and is used both to find invocations and to read their words. Commit each input above as a control case under `controls/doc-helper-flags/` (1 and 2 GOOD, 3 BAD) and show each red on the current gate first.

Found while working #1835 (counter-model review pass 3; receipt under `docs/measurements/counter-model/` on that PR).

🤖 Generated with [Claude Code](https://claude.com/claude-code)


<!-- end of body -->
