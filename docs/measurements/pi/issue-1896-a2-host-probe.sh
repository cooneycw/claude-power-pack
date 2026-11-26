#!/usr/bin/env bash
# Fetch this exact file with git show <frozen-sha>:docs/measurements/pi/issue-1896-a2-host-probe.sh.
# Offline fixture observations only. No owner configuration or provider turn.
set -euo pipefail
: "${PI_A2_SOURCE:?reviewed clean candidate checkout required}"
: "${PI_A2_REVISION:?full frozen candidate commit required}"
: "${PI_A2_PYTHON:?absolute compatible interpreter required}"
: "${PI_A2_PI_BIN:?absolute reviewed pi executable required}"
: "${PI_A2_STRACE_BIN:?absolute reviewed strace executable required}"

test "$(git -C "$PI_A2_SOURCE" rev-parse HEAD)" = "$PI_A2_REVISION"
test -z "$(git -C "$PI_A2_SOURCE" status --porcelain --untracked-files=normal)"
"$PI_A2_PYTHON" "$PI_A2_SOURCE/scripts/pi-host-fixture.py" --self-test
"$PI_A2_PYTHON" "$PI_A2_SOURCE/scripts/pi-syscall-audit.py" --self-test

# UNKNOWN exit 4 is a returned observation, never a green or a reason to omit
# the other lane. Keep each exact JSON record and its exit status together.
set +e
"$PI_A2_PYTHON" "$PI_A2_SOURCE/scripts/pi-host-fixture.py" \
  --source "$PI_A2_SOURCE" --revision "$PI_A2_REVISION" \
  --pi-bin "$PI_A2_PI_BIN" --lane rpc --json
pi_a2_rpc_exit=$?
printf 'PI_A2_RPC_EXIT=%s\n' "$pi_a2_rpc_exit"

"$PI_A2_PYTHON" "$PI_A2_SOURCE/scripts/pi-host-fixture.py" \
  --source "$PI_A2_SOURCE" --revision "$PI_A2_REVISION" \
  --strace-bin "$PI_A2_STRACE_BIN" --lane syscalls --json
pi_a2_syscall_exit=$?
printf 'PI_A2_SYSCALL_EXIT=%s\n' "$pi_a2_syscall_exit"
exit 0 # The operator reads paired lane exits; wrapper completion is not acceptance.
