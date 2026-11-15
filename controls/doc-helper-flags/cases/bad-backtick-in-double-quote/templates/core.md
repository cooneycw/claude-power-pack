# Fixture core (issue #1842)

The helper inside the quoted backtick substitution runs, so its unknown
`--kind` must be reported:

```bash
~/.claude/scripts/mailbox.sh --to o
X="`~/.claude/scripts/mailbox.sh --kind m`"
```
