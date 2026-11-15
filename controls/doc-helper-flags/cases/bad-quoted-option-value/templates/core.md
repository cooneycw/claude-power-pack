# Fixture core

The unknown option's VALUE is quoted. A gate that drops every word with a
quoted part never sees `--kind` here (counter-model review on #1835).

```bash
~/.claude/scripts/mailbox.sh send --to orchestrator --kind="message" --body "still waiting"
```
