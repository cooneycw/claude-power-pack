# Installation Issues Log

Issues encountered during installation of the claude-power-pack MCP servers.

## uv Installation

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management. Install it with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Issue 1: API Keys Not Configured

**Problem**: The Second Opinion MCP server fails because API keys are missing.

**Error**:
```
Missing API key: GEMINI_API_KEY or OPENAI_API_KEY
```

**Solution**: The Second Opinion server is external now - it lives in the
`cooneycw/mcp-second-opinion` repo. Configure its API keys on the server side per
that repo's README, then point this project's root `.mcp.json` `second-opinion` entry
at the running server (`http://127.0.0.1:8080/mcp` for localhost, or a Tailscale URL).

---

*Generated: 2025-12-20*
*Updated: 2026-02-16 - Modernized for uv-first workflow*
*Updated: 2026-07-03 - Removed the Playwright browser-install item; browser automation migrated to the upstream `@playwright/mcp` npx/stdio server in #423 (no CPP-owned server directory)*
*Updated: 2026-07-04 - Second Opinion MCP server extracted to the external cooneycw/mcp-second-opinion repo; connect via the root .mcp.json (#469)*
