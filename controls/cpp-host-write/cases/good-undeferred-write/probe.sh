#!/usr/bin/env bash
# KNOWN-GOOD: the ordinary path, no defer-set. Separates a working helper from
# one wedged at "refuse everything" - which would score BAD on the bad case
# alone and look identical to a correct helper.
GATE="${1:?gate path required}"
H=$(mktemp -d) || exit 1
trap 'rm -rf "$H"' EXIT
printf 'marker-content\n' > "$H/content.txt"
HOME="$H" bash "$GATE" bashrc-append '# cpp-control-marker' "$H/content.txt"
rc=$?
[ -f "$H/.bashrc" ] || { printf 'cpp-host-write: FAILED to write an undeferred surface\n'; exit 1; }
exit "$rc"
