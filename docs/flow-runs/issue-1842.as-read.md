<!-- flow-run n=1 id=340655a894e34a9e8efa02ff06c23a38 -->
## Run 1 - issue #1842 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1842
- Read at:      2026-11-15T18:13:59Z
- updatedAt:    2026-11-15T17:58:33Z   (context only - moves on comments and labels)
- Body digest:  f7dfcf05d55c11a76359807c680bc61986f65670dcd4ee1bda1debe95589e407   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1467 of 1467 (cap 16384)

### Body as read
## Problem

`scripts/check-doc-helper-flags.py` (the `make verify` / Woodpecker `doc-helper-flags-check` gate) reads a helper path inside a **quoted backtick substitution** as message text, so an unknown flag on it passes unchecked.

```bash
~/.claude/scripts/mailbox.sh --to o
X="`~/.claude/scripts/mailbox.sh --kind m`"
```

- main before #1839's PR: exit 1, `UNKNOWN_FLAG ... mailbox.sh --kind` (correct)
- after #1839's PR (fence-forward reader): exit 0 (wrong: the backticked helper runs)

Cause: `lex()`'s double-quote branch opens a nested command on `$(`, `<(`, `>(` only, never on an unescaped backtick. Before the fence-forward rework, `command_start` started reading after the last backtick, which hid this gap by accident.

Found by the fifth counter-model review run on #1839 (MEDIUM). Shipped with the PR on the owner's call; no live document uses this shape today (`grep -rnE '"[^"]*\`~/\.claude/scripts/' .claude/commands .claude/skills templates` finds nothing).

## Acceptance

- [ ] An unescaped backtick opens a nested-command level in `lex()` (inside double quotes, at the command level and inside `$(...)`), closed by the next unescaped backtick; a helper path inside it is an invocation.
- [ ] A committed BAD case under `controls/doc-helper-flags/` with the input above, red on the current gate first.
- [ ] A test in `tests/test_check_doc_helper_flags.py` that fails on the current gate.
- [ ] Live gate per-invocation flag lists unchanged.


<!-- end of body -->
