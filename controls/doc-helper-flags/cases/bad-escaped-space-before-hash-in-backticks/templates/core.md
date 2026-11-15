# Fixture core (issue #1842)

The escaped space keeps `#` inside its word, so the `;` after it starts a real
helper call whose unknown `--kind` must be reported:

```bash
~/.claude/scripts/mailbox.sh --to o
X="`printf foo\ #; ~/.claude/scripts/mailbox.sh --kind m`"
```
