# Fixture core

A comment holds an inline-code backtick, a double quote and a trailing
backslash; the next command's --body names a helper as message text. A reader
that starts after the comment's backtick reads the comment's quote as opening,
the --body quote as closing it, and the helper path in the message as an
invocation, blocking this valid document (counter-model review on #1839).

```bash
~/.claude/scripts/mailbox.sh send --to o
# Use `printf` for the "note \
~/.claude/scripts/mailbox.sh send --to o --body "run ~/.claude/scripts/mailbox.sh --kind m"
```
