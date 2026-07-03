# Installation Issues Log

Issues encountered during installation of the claude-power-pack MCP servers.

## uv Installation

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management. Install it with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Issue 1: API Keys Not Configured

**Problem**: MCP Second Opinion server fails because API keys are missing.

**Error**:
```
Missing API key: GEMINI_API_KEY or OPENAI_API_KEY
```

**Solution**: Copy the .env.example and add your keys:
```bash
cd mcp-second-opinion
cp .env.example .env
# Edit .env with your API keys
```

---

*Generated: 2025-12-20*
*Updated: 2026-02-16 - Modernized for uv-first workflow*
*Updated: 2026-07-03 - Removed the Playwright browser-install item; browser automation migrated to the upstream `@playwright/mcp` npx/stdio server in #423 (no CPP-owned server directory)*
