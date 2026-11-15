# Fixture core

The helper runs inside a `$(...)` substitution; `--kind` belongs to the outer
`echo`, written after the substitution closes. A reader that keeps going past
the helper's own `)` credits `echo`'s flag to the helper (#1839, shape 1).

```bash
echo $(~/.claude/scripts/mailbox.sh send --to o --body b) --kind
```
