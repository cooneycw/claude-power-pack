#!/usr/bin/env bash
# Fixture helper for the check-test-binary-guards negative control (issue
# #1407). Two heredoc-opener-SHAPED tokens that are not real heredocs - one
# inside a quoted usage string, one inside a comment - precede a REAL jq use
# that must still be detected as a hard requirement.
set -euo pipefail
echo "usage: cat <<'EOF' > file"
# see also: cpp-host-write.sh settings-edit ... <<'JQ'
printf '{"ok":true}' | jq -r '.ok'
