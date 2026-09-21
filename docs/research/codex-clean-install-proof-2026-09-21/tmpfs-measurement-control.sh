#!/usr/bin/env bash
# tmpfs-measurement-control.sh - the RED CASE for the HIGH counter-model finding.
#
# clean-host.sh mounts a fresh `--tmpfs /tmp`. Measuring an arm in a SECOND
# invocation therefore destroys anything the arm left under /tmp: an arm that
# cloned to /tmp and installed symlinks from there has every link read as BROKEN,
# and an install under /tmp measures as "(nothing written)" - the harness
# manufacturing the empty result the differential treats as its headline finding.
#
# This runs BOTH shapes over an IDENTICAL filesystem and prints both verdicts, so
# the difference is attributable to the measurement and nothing else.
#
# Expected: same-invocation -> broken=0. Split-invocation -> broken=1.
# If both agree, this control is no longer discriminating and must not be trusted.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SB="$(mktemp -d "${TMPDIR:-/tmp}/cleanhost-tmpfsctl-XXXXXX")"
trap 'rm -rf "$SB"' EXIT
MEASURE='D=/home/clean/.claude/scripts
if [ -d "$D" ] && [ -n "$(ls -A "$D" 2>/dev/null)" ]; then
  for f in "$D"/*; do k=file; [ -L "$f" ] && k=link
    if [ -e "$f" ]; then printf "    %-20s %-5s %6d sha=%s\n" "$(basename $f)" "$k" "$(stat -Lc%s "$f")" "$(sha256sum "$f"|cut -c1-12)"
    else printf "    %-20s %-5s BROKEN -> %s\n" "$(basename $f)" "$k" "$(readlink $f)"; fi; done
  echo "    entries=$(ls $D|wc -l) broken=$(find $D -xtype l|wc -l)"
else echo "    (nothing written)"; fi'
SIM='mkdir -p /tmp/fakecheckout/scripts /home/clean/.claude/scripts
  printf "#!/bin/sh\necho hi\n" > /tmp/fakecheckout/scripts/helper-a.sh
  ln -sf /tmp/fakecheckout/scripts/helper-a.sh /home/clean/.claude/scripts/helper-a.sh'

echo "== SAME invocation (what run-arms.sh does now) =="
"$HERE/clean-host.sh" "$SB" /bin/bash -c "$SIM; $MEASURE"
echo "== SPLIT invocation (the defect) =="
"$HERE/clean-host.sh" "$SB" /bin/bash -c "$SIM" >/dev/null
"$HERE/clean-host.sh" "$SB" /bin/bash -c "$MEASURE"
