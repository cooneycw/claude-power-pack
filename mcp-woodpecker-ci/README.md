# MCP Woodpecker CI

Woodpecker CI pipeline management and monitoring MCP server for Claude Code.

## Tools

| Tool | Description |
|------|-------------|
| `health_check` | Verify connectivity to Woodpecker CI |
| `list_repos` | List all repos the API token can access |
| `lookup_repo` | Find a repo by owner/name |
| `list_pipelines` | List recent pipelines for a repo |
| `get_pipeline` | Get pipeline details with workflow steps |
| `create_pipeline` | Trigger a new pipeline on a branch |
| `cancel_pipeline` | Cancel a running pipeline |
| `approve_pipeline` | Approve a blocked pipeline |
| `get_pipeline_logs` | Get decoded logs for a pipeline step |

## Configuration

The server resolves credentials in this order:

1. **Environment variables** (direct):
   - `WOODPECKER_URL` - Woodpecker server URL (e.g. `https://woodpecker.example.com`)
   - `WOODPECKER_API_TOKEN` - API token from Woodpecker UI

2. **AWS Secrets Manager** (auto-fetch):
   - `AWS_SECRET_NAME` - Secret name (default: `essent-ai`)
   - `AWS_REGION` - Region (default: `us-east-1`)
   - Reads `WOODPECKER_HOST` and `WOODPECKER_API_TOKEN` keys from the secret

## Running

### Docker (recommended)

```bash
# From claude-power-pack root:
make docker-up PROFILE=cicd
```

### Native

```bash
./start-server.sh
# Or with stdio transport:
./start-server.sh --stdio
```

## Port

- Default: `8085`
- Override: `MCP_SERVER_PORT=8085`
- SSE endpoint: `http://127.0.0.1:8085/sse`
- Health check: `http://127.0.0.1:8085/`
