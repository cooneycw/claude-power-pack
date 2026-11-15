# Fixture core

A comment starts straight after `;`. Its apostrophe and trailing backslash are
comment text. A reader that takes `;#` for one word reads the apostrophe as a
quote opening, the next invocation as message text, and passes this
(counter-model review on #1839).

```bash
~/.claude/scripts/mailbox.sh send --to o;# owner's note \
~/.claude/scripts/mailbox.sh send --kind message
```
