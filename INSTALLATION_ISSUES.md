# Installation Issues Log

Issues encountered during installation of the claude-power-pack MCP servers.

## uv Installation

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency management. Install it with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Issue 1: Playwright Browsers Not Installed

**Problem**: Playwright MCP server fails to start because Chromium browser is not installed.

**Error**:
```
playwright._impl._errors.Error: Executable doesn't exist at /home/user/.cache/ms-playwright/chromium-xxx/chrome-linux/chrome
```

**Solution**: Install Playwright browsers:
```bash
cd mcp-playwright-persistent
uv run playwright install chromium
```

---

## Issue 2: API Keys Not Configured

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

## Issue 3: Redis Not Running (Coordination Server)

**Problem**: MCP Coordination server fails because Redis is not available.

**Error**:
```
redis.exceptions.ConnectionError: Error -2 connecting to localhost:6379
```

**Solution**: Install and start Redis:
```bash
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping  # Should return PONG
```

---

*Generated: 2025-12-20*
*Updated: 2026-01-04 - Migrated from conda to uv*
