#!/usr/bin/env bash
# Fixture helper for the check-test-binary-guards negative control (issue
# #1407). ISOLATES the quoted-string shape only - no comment-opener text
# anywhere in this file, so this case is load-bearing only for the
# quote-tracking half of `_heredoc_opener_is_live`, never for its comment
# detection. A heredoc-opener-SHAPED token inside a double-quoted usage
# string precedes a REAL jq use that must still be detected as a hard
# requirement.
set -euo pipefail
echo "usage: cat <<'EOF' > file"
printf '{"ok":true}' | jq -r '.ok'
