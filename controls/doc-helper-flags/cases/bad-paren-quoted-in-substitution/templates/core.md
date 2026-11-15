# Fixture core

The unknown flag follows a substitution that holds a `(` inside quotes. A
reader that counts parentheses without reading quotes never sees the
substitution close, swallows the rest of the command and passes this
(#1839, shape 3).

```bash
~/.claude/scripts/mailbox.sh send --to o --body "$(printf '(')" --kind message
```
