#!/usr/bin/env bash
# Observe prerequisites with a 3.10-compatible stdlib front end, never uv.
#: NEGATIVE-CONTROL: controls/flow-preflight
set -uo pipefail
trap 'printf "FLOW_PREFLIGHT_BOOTSTRAP_EXIT=%d\n" "$?" >&2' EXIT
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    printf '%s\n' '{"schema":1,"status":"unknown","required_gaps":0,"required_unknown":1,"scope":"unexamined","full_host_ready":null,"selected_checks":[],"unexamined_checks":["gh","uv","cpp_python","user.name","user.email","codex","engine"],"checks":[{"id":"observer_python","status":"unknown","required":true,"message":"Observer requires Python 3.10 or newer; other checks unexamined","remediation":"Provide a compatible bootstrap interpreter without changing project/global pins","evidence":{}}]}'
    exit 3
fi
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/flow-preflight.py" "$@"
exit "$?"
