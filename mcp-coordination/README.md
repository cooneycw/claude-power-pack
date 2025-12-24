# MCP Coordination Server

Distributed locking and session coordination for Claude Code via Redis.

## Features

- **Distributed Locks**: Prevent concurrent pytest runs, PR conflicts
- **Wave/Issue Hierarchy**: Lock at issue, wave, or wave.issue level
- **Auto-Detection**: Use "work" to lock based on current git branch
- **Session Tracking**: See all active Claude Code sessions
- **Tiered Status**: Active → Idle → Stale → Abandoned
- **Auto-Expiry**: Locks and sessions expire automatically

## Prerequisites

```bash
# Install Redis
sudo apt install redis-server
sudo systemctl enable redis-server
redis-cli ping  # Should return PONG
```

## Installation

```bash
# Create conda environment
conda env create -f environment.yml
conda activate mcp-coordination

# Copy and configure environment
cp .env.example .env

# Start server
./start-server.sh
```

## MCP Tools

### Lock Management

| Tool | Description |
|------|-------------|
| `acquire_lock(lock_name, timeout)` | Acquire distributed lock |
| `release_lock(lock_name)` | Release held lock |
| `check_lock(lock_name)` | Check lock availability |
| `list_locks(pattern)` | List locks matching pattern |

### Session Management

| Tool | Description |
|------|-------------|
| `register_session(metadata)` | Register session for tracking |
| `heartbeat()` | Update session heartbeat |
| `session_status()` | Show all sessions and states |

### Health

| Tool | Description |
|------|-------------|
| `health_check()` | Check Redis connection |

## Lock Naming

```
# Auto-detect from branch
acquire_lock("work")          # issue-42-auth → issue:42
                              # wave-5c.1-feat → wave:5c.1

# Explicit locks
acquire_lock("issue:42")      # Issue-specific
acquire_lock("wave:5c")       # Wave-level
acquire_lock("wave:5c.1")     # Wave + issue
acquire_lock("pytest")        # Resource lock
acquire_lock("pr-create")     # Resource lock
```

## Redis Key Structure

```
claude:locks:issue:{number}       # Issue locks
claude:locks:wave:{id}            # Wave locks
claude:locks:wave:{id}.{issue}    # Wave+issue locks
claude:locks:resource:{name}      # Resource locks (pytest, pr-create)
claude:sessions:{session_id}      # Session data
claude:heartbeat:{session_id}     # Heartbeat (with TTL)
```

## Integration with Claude Code

### Add to ~/.claude.json

```bash
claude mcp add coordination --transport sse --url http://127.0.0.1:8082/sse
```

### Usage Examples

```
# Before running pytest
Use coordination MCP: acquire_lock("pytest", 600)
[run pytest]
Use coordination MCP: release_lock("pytest")

# Before creating PR
Use coordination MCP: acquire_lock("pr-create")
[create PR]
Use coordination MCP: release_lock("pr-create")

# Check who's working
Use coordination MCP: session_status()
```

## Session Status Tiers

| Status | Heartbeat Age | Behavior |
|--------|---------------|----------|
| 🟢 Active | < 5 min | Fully blocked |
| 🟡 Idle | 5 min - 1 hr | Blocked with warning |
| 🟠 Stale | 1 - 4 hr | Override allowed |
| ⚫ Abandoned | > 24 hr | Auto-released |

## Systemd Service (Recommended)

For persistent operation with auto-restart on boot:

### Step 1: Edit Service File for Your Paths

The service file contains hardcoded paths. Edit before copying:

```bash
# View the template
cat deploy/mcp-coordination.service

# Key lines to update:
# - User=YOUR_USERNAME
# - WorkingDirectory=/path/to/claude-power-pack/mcp-coordination
# - ExecStart=/path/to/claude-power-pack/mcp-coordination/start-server.sh --daemon
# - Environment="PATH=/path/to/miniconda3/bin:..."
```

### Step 2: Install and Enable

```bash
# Copy service file
sudo cp deploy/mcp-coordination.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable autostart and start now
sudo systemctl enable mcp-coordination
sudo systemctl start mcp-coordination
```

### Step 3: Verify

```bash
# Check status
systemctl status mcp-coordination

# View logs
journalctl -u mcp-coordination -f

# Test connection
curl -s http://localhost:8082/health || echo "Not responding"
```

### Troubleshooting

```bash
# If service fails to start
journalctl -u mcp-coordination --no-pager -n 50

# Common issues:
# - Redis not running: sudo systemctl start redis-server
# - Wrong paths in service file: sudo systemctl edit mcp-coordination
# - Port in use: check with `lsof -i :8082`
```

## Configuration

See `.env.example` for all configuration options:

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection |
| `SERVER_PORT` | 8082 | MCP server port |
| `DEFAULT_LOCK_TIMEOUT` | 300 | Lock TTL (seconds) |
| `HEARTBEAT_TTL` | 300 | Heartbeat expiry |

## Debugging

```bash
# Check Redis keys
redis-cli KEYS "claude:*"

# View a lock
redis-cli GET "claude:locks:resource:pytest"

# Clear all coordination data (careful!)
redis-cli KEYS "claude:*" | xargs redis-cli DEL
```
