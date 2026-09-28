#!/bin/sh
# Runs one capability-readiness case (issue #1290).
#
# A case is a SITUATION - a home, a project's MCP configuration and, for the
# flow case, an installed CPP checkout with its origin - which cannot be
# committed as files (a nested repository is not tracked, and a closed port
# must be closed NOW). So each case commits a one-word `scenario` and this
# wrapper builds it in a fresh temporary directory:
#
#   healthy         empty home (flow not installed: disabled), and a project
#                   `.mcp.json` whose second-opinion is a stdio MCP server
#                   written here that answers initialize + tools/list
#   closed-port     the same project shape as the shipped `.mcp.json`
#                   (`${SECOND_OPINION_URL:-http://127.0.0.1:<port>}/mcp`), with
#                   nothing listening on <port>
#   missing-helper  a CPP checkout (this repository's scripts/, commands and
#                   CLAUDE.md, committed to a bare origin and cloned so its
#                   freshness is `current`), installed into the home through the
#                   real entry points, then one installed helper deleted
#
# The gate is a .py and the anchor a .sh; both take the same argv. Output and
# exit status are the gate's own.
set -u
gate="$1"
case_dir="$2"
repo=$(pwd)

for tool in bash git python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "CAPABILITY_READINESS_CONTROL: unavailable - $tool is not installed"
        exit 2
    fi
done
scenario=$(cat "$case_dir/scenario" 2>/dev/null) || scenario=""

work=$(mktemp -d) || exit 2
trap 'rm -rf "$work"' EXIT
home="$work/home"
project="$work/project"
checkout_arg=""

build() {
    mkdir -p "$home" "$project" || return 1
    case "$scenario" in
        healthy)
            cat > "$work/fake_mcp.py" <<'PY'
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        out = {"jsonrpc": "2.0", "id": msg["id"], "result": {"serverInfo": {"name": "fake"}}}
    elif msg.get("method") == "tools/list":
        out = {"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": [{"name": "t"}]}}
    else:
        continue
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()
PY
            printf '{"mcpServers": {"second-opinion": {"type": "stdio", "command": "python3", "args": ["%s"]}}}\n' \
                "$work/fake_mcp.py" > "$project/.mcp.json" ;;
        closed-port)
            port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()') || return 1
            # Precondition: nothing listens there.
            python3 -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1',$port)) else 1)" || return 1
            # The literal ${SECOND_OPINION_URL:-...} is the shipped .mcp.json form, not a shell expansion.
            # shellcheck disable=SC2016
            printf '{"mcpServers": {"second-opinion": {"type": "http", "url": "${SECOND_OPINION_URL:-http://127.0.0.1:%s}/mcp"}}}\n' \
                "$port" > "$project/.mcp.json" ;;
        missing-helper)
            q=--quiet
            g() { git -c user.email=c@x.invalid -c user.name=c "$@"; }
            mkdir -p "$work/seed/.claude" &&
            cp -R "$repo/scripts" "$work/seed/scripts" &&
            cp -R "$repo/.claude/commands" "$work/seed/.claude/commands" &&
            cp "$repo/CLAUDE.md" "$work/seed/CLAUDE.md" &&
            g init $q --initial-branch=main "$work/seed" &&
            g -C "$work/seed" add -A &&
            g -C "$work/seed" commit $q -m one &&
            g init $q --bare --initial-branch=main "$work/origin.git" &&
            g -C "$work/seed" push $q "$work/origin.git" main &&
            g clone $q "$work/origin.git" "$work/checkout" || return 1
            for helper in flow-helpers-install.sh cpp-commands-link.sh; do
                env -u FLOW_HELPERS_HOME -u FLOW_HELPERS_SOURCE -u CPP_COMMANDS_LINK_HOME \
                    -u CLAUDE_PLUGIN_ROOT HOME="$home" \
                    bash "$work/checkout/scripts/$helper" || return 1
            done
            rm "$home/.claude/scripts/flow-stale-check.sh" &&
            [ ! -e "$home/.claude/scripts/flow-stale-check.sh" ] || return 1
            checkout_arg="$work/checkout" ;;
        *) return 1 ;;
    esac
}
if ! build >/dev/null 2>&1; then
    echo "CAPABILITY_READINESS_CONTROL: unavailable - could not build scenario '$scenario'"
    exit 2
fi

case "$gate" in
    *.py) interp="python3" ;;
    *) interp="sh" ;;
esac
if [ -n "$checkout_arg" ]; then
    env -u SECOND_OPINION_URL HOME="$home" "$interp" "$gate" --home "$home" \
        --project-dir "$project" --checkout "$checkout_arg" --timeout 8
else
    env -u SECOND_OPINION_URL HOME="$home" "$interp" "$gate" --home "$home" \
        --project-dir "$project" --timeout 8
fi
