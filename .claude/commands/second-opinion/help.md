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

- `get_code_second_opinion` — Single-model review (Gemini default)
- `get_multi_model_second_opinion` — Multi-model parallel review
- `list_available_models` — Check which models are configured
- `create_session` / `consult` — Multi-turn conversations

## Requirements

- MCP Second Opinion server configured (stdio recommended, or SSE on port 8080)
- At least one API key configured (GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)
- All three recommended for cross-provider comparison

## Troubleshooting

**Error `-32602: Invalid request parameters`** usually means the server isn't running, not that parameters are wrong.

**Fix:** Switch from SSE to stdio transport (auto-starts the server):

```bash
claude mcp remove second-opinion
claude mcp add second-opinion --transport stdio -- uv run --directory /path/to/claude-power-pack/mcp-second-opinion python src/server.py --stdio
```

**Diagnose configuration:**

```bash
cd /path/to/claude-power-pack/mcp-second-opinion
./start-server.sh --diagnose
```
