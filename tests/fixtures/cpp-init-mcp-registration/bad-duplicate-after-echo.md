```bash
# CPP_MCP_ROUTINES_BEGIN
cpp_register_claude_mcp() {
  if claude mcp add "$@"; then :; else return "$?"; fi
}
cpp_register_codex_mcp() {
  if codex mcp add "$@"; then :; else return "$?"; fi
}
# CPP_MCP_ROUTINES_END
# claude mcp add is documentation here
echo "codex mcp add second-opinion is quoted advice"
echo claude mcp add is unquoted advice
```
```
claude mcp add second-opinion is a non-executable example
```
```bash
echo starting; claude mcp add second-opinion --url http://fixture.invalid/mcp
```
