#!/bin/sh
# CONSTRUCTED anchor for controls/capability-readiness (issue #1290).
# Preamble (constructed): take the gate's calling convention and enter the
# project directory the status command ran from.
while [ $# -gt 0 ]; do
    case "$1" in --project-dir) cd "$2" || exit 2; shift 2 ;; *) shift ;; esac
done
# --- BEGIN verbatim .claude/commands/cpp/status.md lines 279-293 at 51dc14d ---
echo ""
echo "MCP Server Wiring (.mcp.json):"
if [ -f ".mcp.json" ] && grep -q "second-opinion" .mcp.json 2>/dev/null; then
  SO_URL=$(grep -oE 'https?://[^"[:space:]]+' .mcp.json 2>/dev/null | head -1)
  echo "  [x] second-opinion: registered in .mcp.json (${SO_URL:-external mcp-second-opinion server})"
  if [ -n "$SO_URL" ] && curl -sf --max-time 2 -o /dev/null "$SO_URL" 2>/dev/null; then
    echo "      reachable"
  else
    echo "      [~] not verified reachable - run the external mcp-second-opinion server (localhost or Tailscale)"
  fi
else
  echo "  [ ] second-opinion: not registered in .mcp.json"
  echo "      Run the external cooneycw/mcp-second-opinion server, then point .mcp.json"
  echo "      at it (http://127.0.0.1:8080/mcp for localhost, or a Tailscale URL)."
fi
# --- END verbatim ---
