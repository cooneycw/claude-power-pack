---
description: Overview of Second Opinion commands
---

# Second Opinion Commands

Commands for AI-powered code review using multiple LLM models.

## Available Commands

| Command | Description |
|---------|-------------|
| `/second-opinion:start` | Quick review with sensible defaults (file + model + depth) |
| `/second-opinion:models` | Interactive model and depth selection with menus |
| `/second-opinion:help` | This help overview |

## Quick Usage

```bash
# Interactive model selection
/second-opinion:models

# Review specific code
/second-opinion:models "review my auth middleware"
```

## Available Models

| Key | Model | Provider | Best For |
|-----|-------|----------|----------|
| `gemini-3-pro` | Gemini 3.1 Pro | Google | Comprehensive analysis |
| `gemini-2.5-pro` | Gemini 2.5 Pro | Google | Stable, proven |
| `claude-sonnet` | Claude Sonnet 4.6 | Anthropic | Fast, excellent for code review |
| `claude-haiku` | Claude Haiku 4.5 | Anthropic | Fastest Claude, cost-effective |
| `claude-opus` | Claude Opus 4.6 | Anthropic | Most capable Claude |
| `codex` | GPT-5.3 Codex | OpenAI | Default coding model |
| `codex-mini` | GPT-5.2 Codex | OpenAI | Cost-effective coding |
| `o4-mini` | o4-mini | OpenAI | Fast reasoning |
| `o3` | o3 | OpenAI | Advanced reasoning |
| `gpt-5.2` | GPT-5.2 | OpenAI | Latest GPT |
| `gpt-4o` | GPT-4o | OpenAI | Fast multimodal |

## Direct MCP Tool Usage

You can also invoke the MCP tools directly without commands:

- `get_code_second_opinion` - Single-model review (Gemini default)
- `get_multi_model_second_opinion` - Multi-model parallel review
- `list_available_models` - Check which models are configured
- `create_session` / `consult` - Multi-turn conversations

## Requirements

- The external Second Opinion server running: clone and start `cooneycw/mcp-second-opinion`. It is opt-in and is not started or auto-registered by CPP.
- The `second-opinion` MCP server registered in Claude Code, pointing at it. Installing via the plugin does NOT auto-register it, so register it yourself once the server is up:
  - **Plugin install:** `claude mcp add second-opinion --transport http --url http://127.0.0.1:8080/mcp --scope user` (use your Tailscale URL for a remote host).
  - **CPP repo checkout:** the repo-root `.mcp.json` already registers `second-opinion` at project scope (`http://127.0.0.1:8080/mcp` for localhost, or a Tailscale URL).
- At least one API key configured on the server side (GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY). All three recommended for cross-provider comparison.

## Troubleshooting

**`second-opinion ... Failed to connect` or "1 error during load"** on a fresh plugin install is expected until you opt in: the external server is not running and the plugin does not auto-register it. It is benign, the other commands are unaffected. Start the server and register it (below) to clear it.

**Error `-32602: Invalid request parameters`** usually means the server isn't running or `second-opinion` is not registered/pointing at it, not that parameters are wrong.

**Fix:** Make sure the external server is up and `second-opinion` is registered against it:

1. Start the external server from the `cooneycw/mcp-second-opinion` checkout (see that repo's README).
2. Register `second-opinion` as a streamable-http server at the right URL. Plugin install: `claude mcp add second-opinion --transport http --url http://127.0.0.1:8080/mcp --scope user`. CPP repo checkout: confirm the repo-root `.mcp.json` `second-opinion` entry targets the same URL (`http://127.0.0.1:8080/mcp` for localhost, or your Tailscale URL for a remote host).
3. Reload MCP servers in Claude Code (or restart the session) so the registration is picked up.
