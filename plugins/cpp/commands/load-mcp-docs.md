---
description: Load MCP Second Opinion server documentation
---

The MCP Second Opinion server is external: it lives in the `cooneycw/mcp-second-opinion`
repo and is connected to this project through the root `.mcp.json` streamable-http pointer
(localhost `http://127.0.0.1:8080/mcp` or a Tailscale URL). Summarize the available tools
and usage patterns from what is reachable here:

1. Read: `README.md` (MCP Second Opinion section) for the setup and connection model.
2. Inspect the live `mcp__second-opinion__*` tool definitions exposed by the connected
   server (e.g. `list_available_models`, `get_code_second_opinion`,
   `get_multi_model_second_opinion`, `create_session`, `consult`). For full server
   internals, see the external `cooneycw/mcp-second-opinion` repository.

Provide an overview of:
- The 10 available tools and their purposes
- Key features (Gemini 3 Pro, multi-turn sessions, agentic tool use)
- Cost tracking and limits
- Security features (SSRF protection, domain approval)
- Best practices for using the MCP server
- Playwright integration for web debugging

Format the response as a concise reference guide.
