# Fixture core

Every flag here is one the named helper accepts, or one this gate must not
attribute to the helper at all.

```bash
~/.claude/scripts/mailbox.sh send --to orchestrator --from worker --body "still waiting"
~/.claude/scripts/mailbox.sh send \
  --to orchestrator --from "$(git rev-parse --show-toplevel)" \
  --body "a substitution's flags belong to git"
~/.claude/scripts/mailbox.sh send --to a --body b | grep --count sent
~/.claude/scripts/preflight.sh --json --repo . --harness auto
```

Inline too: `~/.claude/scripts/mailbox.sh send --to x --body y` then `--kind` in prose.

A flag-like word inside a quoted argument is the argument's text, not a flag:

```bash
~/.claude/scripts/mailbox.sh send --to orchestrator --body "please drop --kind message; see #1835"
```

A helper path inside a quoted argument is message text, not a second
invocation, and its flag-like words are not checked:

```bash
~/.claude/scripts/mailbox.sh send --to orchestrator --body "run ~/.claude/scripts/mailbox.sh --kind message yourself"
```
