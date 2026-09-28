#!/bin/sh
# Case runner for controls/flow-wave-registry-takeover (#1014 Part 2).
#
# THE INSTRUMENT IS THE TAKEOVER GUARD. `register` on a role someone else holds
# must refuse unless the holder is PROVEN gone or the operator says --force.
# The finding is that refusal: exit 1 with the gate's own `FLOW_WAVE: refused`
# verdict. A taken role is `FLOW_WAVE: registered`, exit 0.
#
# IT DECIDES NOTHING ABOUT THE ANSWER. Each case directory holds a registry.json
# recorded by the real helper, plus an optional `args` file carrying extra
# register flags (`--force`). Neither names the verdict it expects; swap in a
# gate that reads a remote owner as `stale` and the same runner sees a takeover.
#
# THE PINS. This host is `testhost`. pid 9999 is ALIVE here - and it is the pid
# the remote fixtures record, so a gate that consulted the LOCAL process table
# for a remote entry would read it `live` and refuse for the wrong reason. The
# fixed gate refuses on basis `other-host`; the runner does not check the basis,
# because the harness scores the verdict, and tests/test_flow_wave_registry.py
# pins the basis. pid 8888 (the same-host holder) is dead.
set -u
case_dir="$1"
gate="$2"

T=$(mktemp -d) || { echo "FLOW_WAVE_TAKEOVER_CONTROL: unavailable - no tmpdir" >&2; exit 3; }
mkdir -p "$T/reg" || { rm -rf "$T"; exit 3; }
cp "$case_dir/registry.json" "$T/reg/registry.json" || { rm -rf "$T"; exit 3; }
extra=""
[ -f "$case_dir/args" ] && extra=$(cat "$case_dir/args")

# shellcheck disable=SC2086 # $extra is a deliberate word list of flags
out=$(env FLOW_WAVE_REGISTRY_DIR="$T/reg" \
          FLOW_WAVE_SOCK_DIR="$T/socks" \
          FLOW_WAVE_HOST=testhost \
          FLOW_WAVE_LIVE_PIDS="4242:9999" \
          FLOW_WAVE_PID_STARTTIMES="4242=w-4242:9999=w-9999" \
          FLOW_WAVE_NOW=1700000100 \
          CLAUDE_PID=4242 CLAUDE_CODE_SESSION_ID=control \
          bash "$gate" register w1 --wave cpp --socket uds:/tmp/control.sock $extra 2>&1)
status=$?
rm -rf "$T"

verdict=$(printf '%s\n' "$out" | sed -n 's/^FLOW_WAVE: //p' | tail -1)

# A crash is NOT a detection: only the gate's own refusal verdict counts (#946).
if [ "$status" -eq 1 ] && [ "$verdict" = "refused" ]; then
    echo "FLOW_WAVE_TAKEOVER_CONTROL: finding - the registry refused to take a role whose holder is not proven gone"
    exit 1
fi
if [ "$status" -eq 0 ] && [ "$verdict" = "registered" ]; then
    exit 0
fi
echo "FLOW_WAVE_TAKEOVER_CONTROL: unavailable - register exited $status with verdict '${verdict:-none}'" >&2
exit 3
