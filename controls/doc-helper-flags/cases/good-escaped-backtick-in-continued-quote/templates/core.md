# Fixture core

A quoted --body holds escaped backticks and continues with a backslash onto a
line holding a helper path. That path is message text. A reader that takes the
escaped backtick for the edge of a code span drops the opening quote and
blocks this valid command (counter-model review on #1839).

```bash
~/.claude/scripts/mailbox.sh send --to o --body "Please run \`example\` \
~/.claude/scripts/mailbox.sh --kind message"
```
