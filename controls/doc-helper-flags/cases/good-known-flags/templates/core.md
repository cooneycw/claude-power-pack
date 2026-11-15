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
