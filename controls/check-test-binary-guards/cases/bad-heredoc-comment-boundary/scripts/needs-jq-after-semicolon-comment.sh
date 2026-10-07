#!/usr/bin/env bash
# Fixture helper for the check-test-binary-guards negative control (issue
# #1407, counter-model finding 1). ISOLATES the comment-opener shape, and
# specifically the `;#` word-boundary case - no quoted-string shape anywhere
# in this file, so this case is load-bearing only for the WORD_BOUNDARY_CHARS
# half of `_heredoc_opener_is_live`'s comment check. `;` is not whitespace,
# but it ends the previous command the same way whitespace ends a previous
# word, so the `#` right after it opens a REAL comment. The heredoc-opener-
# SHAPED token inside that comment must not open a real mask, and the REAL
# jq use after it must still be detected as a hard requirement.
set -euo pipefail
echo ok;# see also: cpp-host-write.sh settings-edit ... <<'JQ'
printf '{"ok":true}' | jq -r '.ok'
