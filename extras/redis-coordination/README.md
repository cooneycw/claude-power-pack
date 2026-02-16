# Redis Coordination (Optional Extra)

Distributed locking and session coordination for **teams** running multiple concurrent Claude Code sessions.

> **Most users don't need this.** The default `local` coordination mode (stateless, context from git) is sufficient for solo development. Install this only if you run multiple Claude Code sessions that compete for shared resources.

## When to Use This

| Scenario | Need Redis? |
|----------|-------------|
| Solo dev, one session at a time | No |
| Solo dev, multiple worktrees in parallel | Maybe (file-based scripts suffice) |
| Team with multiple devs using Claude Code | Yes |
| CI/CD with concurrent Claude Code runs | Yes |

## What's Included

### MCP Server (`mcp-server/`)

A FastMCP server providing 8 tools for distributed locking and session tracking via Redis:

| Tool | Description |
|------|-------------|
| `acquire_lock(name, timeout)` | Acquire distributed lock |
| `release_lock(name)` | Release held lock |
| `check_lock(name)` | Check lock availability |
| `list_locks(pattern)` | List locks matching pattern |
| `register_session(metadata)` | Register session for tracking |
| `heartbeat()` | Update session heartbeat |
| `session_status()` | Show all sessions and states |
| `health_check()` | Check Redis connection |

### Shell Scripts (`scripts/`)

File-based coordination scripts (no Redis required):

| Script | Purpose |
|--------|---------|
| `session-lock.sh` | File-based distributed locking |
| `session-register.sh` | Session lifecycle management |
| `session-heartbeat.sh` | Heartbeat daemon |
| `claim-issue.sh` | Issue claiming for session coordination |
| `pytest-locked.sh` | pytest wrapper with lock coordination |

## Prerequisites

For the MCP server only:

```bash
sudo apt install redis-server
sudo systemctl enable redis-server
redis-cli ping  # Should return PONG
```

## Installation

### MCP Server

```bash
cd extras/redis-coordination/mcp-server

# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Configure
cp .env.example .env

# Start
./start-server.sh

# Add to Claude Code
claude mcp add coordination --transport sse --url http://127.0.0.1:8082/sse
```

### Shell Scripts

```bash
# Symlink to ~/.claude/scripts/
ln -sf /path/to/claude-power-pack/extras/redis-coordination/scripts/*.sh ~/.claude/scripts/

# Create coordination directories
mkdir -p ~/.claude/coordination/{locks,sessions,heartbeat}
```

## Configuration

Set your project's coordination mode in `.claude/config.yml`:

```yaml
coordination: redis  # Enables Redis-backed coordination
```

See the [MCP server README](mcp-server/README.md) for detailed configuration, systemd setup, and debugging.
