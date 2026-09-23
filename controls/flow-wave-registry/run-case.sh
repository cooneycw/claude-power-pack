#!/bin/sh
# Case runner for controls/flow-wave-registry (#1190).
#
# WHY AN ADAPTER AT ALL. `list` exits 0 whether or not it reports an overlap -
# the roster is advisory and an advisory that changed exit codes would abort
# every `set -euo pipefail` caller (#674). The control harness scores a finding
# by EXIT CODE, so something has to turn "the roster said the words" into an
# exit status. That is all this does.
#
# IT DECIDES NOTHING ABOUT THE ANSWER. It greps for the gate's OWN warning text
# and never for a role, a path, or a verdict the case supplies - the case
# directories contain a registry.json and nothing else, so no case can name the
# answer it expects. Swap in a blind gate and the same grep finds nothing.
set -u
case_dir="$1"
gate="$2"

T=$(mktemp -d) || { echo "FLOW_WAVE_REGISTRY_CONTROL: unavailable - no tmpdir" >&2; exit 3; }
mkdir -p "$T/reg" || { rm -rf "$T"; exit 3; }
cp "$case_dir/registry.json" "$T/reg/registry.json" || { rm -rf "$T"; exit 3; }

# The pins match how the fixture was recorded: same host, same live pids, same
# start-time witnesses. Liveness is keyed on all three, and a pair that reads
# `stale` is exempt from every pairwise check - which would make this control
# pass by examining nothing.
out=$(env FLOW_WAVE_REGISTRY_DIR="$T/reg" \
          FLOW_WAVE_SOCK_DIR="$T/socks" \
          FLOW_WAVE_HOST=testhost \
          FLOW_WAVE_LIVE_PIDS="4242:9999" \
          FLOW_WAVE_PID_STARTTIMES="4242=w-4242:9999=w-9999" \
          FLOW_WAVE_NOW=1700000000 \
          CLAUDE_PID=1 CLAUDE_CODE_SESSION_ID=control \
          bash "$gate" list --wave cpp 2>&1)
status=$?
rm -rf "$T"

# A gate that fell over is NOT a detection. Distinguish it from a finding, or a
# crash on a BAD case scores as "caught it" (#946).
if [ "$status" -ne 0 ]; then
    echo "FLOW_WAVE_REGISTRY_CONTROL: unavailable - the roster exited $status" >&2
    exit 3
fi

if printf '%s\n' "$out" | grep -q 'overlapping FILE LANES'; then
    echo "FLOW_WAVE_REGISTRY_CONTROL: finding - the roster reported overlapping FILE LANES"
    exit 1
fi
exit 0
