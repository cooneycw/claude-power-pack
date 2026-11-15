# Fixture core

A shell comment names a helper with a flag it lacks. A commented command never
runs, so the path is comment text. A reader that skips the comment's quotes but
still counts the path inside it as an invocation blocks this valid document
(counter-model review on #1839).

```bash
~/.claude/scripts/mailbox.sh send --to o
# Don't run ~/.claude/scripts/mailbox.sh --kind m
```
