# Fixture core

The unknown flag follows a quoted argument that holds a `#` and a `;`. A
gate that cuts the command at punctuation without reading quotes stops before
the flag and passes this (found by counter-model review on #1835).

```bash
~/.claude/scripts/mailbox.sh send --to orchestrator --body "waiting on #1835; sent at noon" --kind message
```
