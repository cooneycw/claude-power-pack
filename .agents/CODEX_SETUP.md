# Claude Power Pack - Codex MCP Setup

Claude Power Pack MCP servers expose both SSE (`/sse`) and streamable HTTP (`/mcp`) transports.
Codex uses the streamable HTTP endpoint at `/mcp`.

## Prerequisites

1. Docker MCP containers are running and healthy:

   ```bash
   make docker-ps
   # or: curl -sf http://127.0.0.1:8080/ && echo OK
   ```

2. Codex CLI is installed:

   ```bash
   command -v codex && codex mcp list
   ```

## Register MCP Servers with Codex

Run each command to register the corresponding MCP server:

```bash
codex mcp add second-opinion --url http://127.0.0.1:8080/mcp
codex mcp add playwright-persistent --url http://127.0.0.1:8081/mcp
codex mcp add nano-banana --url http://127.0.0.1:8084/mcp
```

## Verify Registration

```bash
codex mcp list
codex mcp get second-opinion
codex mcp get playwright-persistent
codex mcp get nano-banana
```

Restart Codex after registration for tools to become available.

## Remove Registration

```bash
codex mcp remove second-opinion
codex mcp remove playwright-persistent
codex mcp remove nano-banana
```

## Transport Reference

| Server               | Port | Claude Code (SSE)                          | Codex (streamable HTTP)                |
|----------------------|------|--------------------------------------------|----------------------------------------|
| second-opinion       | 8080 | `http://127.0.0.1:8080/sse`               | `http://127.0.0.1:8080/mcp`          |
| playwright-persistent| 8081 | `http://127.0.0.1:8081/sse`               | `http://127.0.0.1:8081/mcp`          |
| nano-banana          | 8084 | `http://127.0.0.1:8084/sse`               | `http://127.0.0.1:8084/mcp`          |

## Notes

- Claude Code and Codex registrations are independent. Registering with one does not affect the other.
- Docker server health (`/`) is separate from MCP registration. A healthy server still needs explicit registration.
- If Codex reports connection errors, verify the container is running and the `/mcp` endpoint responds:

  ```bash
  curl -sf http://127.0.0.1:8080/mcp -X POST -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}},"id":1}'
  ```
