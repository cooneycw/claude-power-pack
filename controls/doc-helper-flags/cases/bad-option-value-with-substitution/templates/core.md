# Fixture core

An unknown option whose value is part literal, part substitution. Its name is
known whatever the value holds. A reader that keeps an option name only when
the quote or substitution starts right after `=` drops it and passes this
(counter-model review on #1839).

```bash
~/.claude/scripts/mailbox.sh send --to o --kind=message$(printf '')
```
