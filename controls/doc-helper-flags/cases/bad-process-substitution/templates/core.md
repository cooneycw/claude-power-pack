# Fixture core

The unknown flag follows a process substitution. A reader that opens only
`$(` reads the `)` of `<(...)` as the end of the command and passes this
(counter-model review on #1839).

```bash
~/.claude/scripts/mailbox.sh send --to o --body <(printf x) --kind message
```
