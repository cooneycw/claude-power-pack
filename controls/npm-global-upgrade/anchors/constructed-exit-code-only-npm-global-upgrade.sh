#!/usr/bin/env sh
# CONSTRUCTED ANCHOR - the blind instrument this control exists to distinguish
# itself from. Do not "fix" it; its blindness is the point.
#
# This is the shape `/cpp:update` Step 5d.2 shipped before issue #1022: run the
# global install, and report the lane refreshed. The exit code is not read - the
# pre-fix step did not read it either, which is why `bad-install-failed` is one
# of the inputs this anchor must miss.
#
# It takes the gate's arguments so the control can invoke it identically, and
# ignores everything that would let it tell one case from another: it never reads
# the installed version, never asks the registry what the latest version is, and
# never looks at node. On all five known-bad inputs it exits 0 and says the lane
# was refreshed - the same bytes it produces on the two known-good ones.
set -u

PACKAGE=""
BINARY=""
LABEL=""

while [ $# -gt 0 ]; do
    case "$1" in
        --package) PACKAGE="${2:-}"; shift 2 ;;
        --binary) BINARY="${2:-}"; shift 2 ;;
        --label) LABEL="${2:-}"; shift 2 ;;
        --npm|--node) shift 2 ;;
        --sudo|--skip-install) shift ;;
        *) shift ;;
    esac
done

[ -n "$LABEL" ] || LABEL="$PACKAGE"

npm install -g "$PACKAGE" >/dev/null 2>&1

echo "NPM_UPGRADE_LABEL: $LABEL"
echo "NPM_UPGRADE_PACKAGE: $PACKAGE"
echo "NPM_UPGRADE_BINARY: $BINARY"
echo "NPM_UPGRADE: refreshed $PACKAGE"
exit 0
