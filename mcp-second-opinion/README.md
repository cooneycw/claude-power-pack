# MCP Second Opinion

Gemini-powered code review MCP server for Claude Code.

## Features

- **Code Review**: Get AI-powered second opinions on code issues
- **Multi-Model Support**: Consult multiple LLMs (Gemini, OpenAI Codex, GPT-5.2)
- **Session-Based**: Interactive multi-turn conversations for deeper analysis
- **Visual Analysis**: Support for screenshot/image analysis (Playwright integration)

## Quick Start

```bash
# Start the server (uv handles dependencies automatically)
./start-server.sh

# Or run directly
uv run python src/server.py
```

## Add to Claude Code

```bash
claude mcp add second-opinion --transport sse --url http://127.0.0.1:8080/sse
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Gemini API key |
| `OPENAI_API_KEY` | No | OpenAI API key (for multi-model) |

## MCP Tools

| Tool | Description |
|------|-------------|
| `get_code_second_opinion` | Single-model code review |
| `get_multi_model_second_opinion` | Multi-model parallel review |
| `list_available_models` | Show available LLM models |
| `create_session` | Start interactive session |
| `consult` | Continue session conversation |
| `get_session_history` | View session transcript |
| `close_session` | End session with summary |
| `list_sessions` | Show active sessions |
| `approve_fetch_domain` | Allow URL fetching for domain |
| `revoke_fetch_domain` | Remove domain approval |
| `list_fetch_domains` | Show approved domains |
| `health_check` | Server status |

## License

MIT
