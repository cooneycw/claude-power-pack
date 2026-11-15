# Fixture core

A quoted `--body` continues onto the next line with a backslash. The helper
path on the second line is still inside that quote: message text, not a second
invocation. A reader that restarts its quote state at each physical line reads
it as a command and reports `--kind` (#1839, shape 2).

```bash
~/.claude/scripts/mailbox.sh send --to o --body "Please run \
~/.claude/scripts/mailbox.sh --kind message"
```
