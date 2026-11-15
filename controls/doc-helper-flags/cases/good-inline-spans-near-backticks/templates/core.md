# Fixture core (issue #1842)

In prose a backtick is a span edge: run `~/.claude/scripts/mailbox.sh --to o`
and never pass `--kind`. Say "`~/.claude/scripts/mailbox.sh --body b`" and
`--kind` is still prose.

```bash
echo "`~/.claude/scripts/mailbox.sh --to o`" --kind m
~/.claude/scripts/mailbox.sh --to o --body "see \`~/.claude/scripts/mailbox.sh --kind m\`"
X="`printf ok # ~/.claude/scripts/mailbox.sh --kind m`"
```
