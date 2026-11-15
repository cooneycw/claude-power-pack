# Fixture core

A comment holds an inline-code backtick, an apostrophe and a trailing
backslash. A reader that guesses where the command starts by walking back
across the backslash and starting after the last backtick reads the
apostrophe as an open quote, the next invocation as message text, and passes
its --kind (counter-model review on #1839).

```bash
~/.claude/scripts/mailbox.sh send --to o
# Use `printf` in the owner's note \
~/.claude/scripts/mailbox.sh send --kind m
```
