---
description: Show Docker container status, health, and project linkages
allowed-tools: Bash(docker:*), Bash(sg:*), Bash(curl:*), Bash(cat:*), Bash(ls:*), Bash(grep:*), Bash(find:*), Read
---

# /dockers - Docker Container Status

Show a structured overview of running Docker containers, their health, ports, and which projects instantiated them.

## Instructions

When the user invokes `/dockers`, perform these steps:

### Step 1: Check Docker Access

```bash
# Try docker directly, fall back to sg if needed
if docker ps >/dev/null 2>&1; then
    DOCKER_CMD="docker"
elif sg docker -c "docker ps" >/dev/null 2>&1; then
    DOCKER_CMD="sg docker -c docker"
else
    echo "ERROR: Cannot connect to Docker. Ensure Docker is running and user is in the docker group."
    echo "Fix: sudo usermod -aG docker \$USER && newgrp docker"
    exit 1
fi
```

### Step 2: List All Containers

```bash
docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Labels}}' 2>/dev/null || \
sg docker -c "docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Labels}}'"
```

If no containers are running, report:

```
No Docker containers found.

CPP itself ships no containers. The second-opinion MCP server now runs from the
external cooneycw/mcp-second-opinion repo and is reached over the root .mcp.json
streamable-http pointer (localhost or Tailscale). Browser automation is the
upstream @playwright/mcp npx/stdio server (no container; see /cpp:init).
```

### Step 3: Health Check Containers with Exposed Ports

CPP itself ships no containers, so there is no fixed list of MCP ports to probe.
For any running container that publishes a host port, hit its root endpoint
generically to see whether it answers:

```bash
# Probe each published host port from `docker ps` (POSIX-compatible, no bash 4+ maps)
for port in $(docker ps --format '{{.Ports}}' 2>/dev/null | grep -oE '127.0.0.1:[0-9]+|0.0.0.0:[0-9]+' | cut -d: -f2 | sort -u); do
    response=$(curl -sf --max-time 3 "http://127.0.0.1:${port}/" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "port ${port}|reachable|$response"
    else
        echo "port ${port}|no HTTP response|"
    fi
done
```

### Step 4: Detect Project Linkages

Scan for docker-compose.yml files across active projects to determine which project instantiated which containers:

```bash
# Check docker compose project labels on running containers
docker inspect --format '{{.Name}} {{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.service"}}' $(docker ps -q) 2>/dev/null || \
sg docker -c 'docker inspect --format "{{.Name}} {{index .Config.Labels \"com.docker.compose.project\"}} {{index .Config.Labels \"com.docker.compose.service\"}}" $(docker ps -q)'
```

Also scan `~/Projects/*/docker-compose.yml` for projects that define matching service names:

```bash
for f in ~/Projects/*/docker-compose.yml; do
    project_dir=$(dirname "$f")
    project_name=$(basename "$project_dir")
    # Extract service names from docker-compose
    grep -E '^\s+\w.*:$' "$f" 2>/dev/null | sed 's/://;s/^ *//' | while read svc; do
        echo "$svc|$project_name|$project_dir"
    done
done
```

### Step 5: Output

Present a structured report:

```markdown
## Docker Container Status

CPP itself ships no containers. The second-opinion MCP server runs from the
external `cooneycw/mcp-second-opinion` repo (reached over the root `.mcp.json`
streamable-http pointer), and browser automation is the upstream
`@playwright/mcp` npx/stdio server, so neither appears in the Docker table below.

### Containers

| Container | Image | Status | Ports |
|-----------|-------|--------|-------|
| my-app-db | postgres:16 | Up 2 hours | 5432 |

### Summary
- **Total containers:** 1 (1 running)
- **CPP-managed containers:** none (second-opinion is external via .mcp.json; playwright via npx/stdio)
```

### Step 6: Suggest Actions

Based on findings, suggest relevant actions:

- **second-opinion not reachable:** it is no longer a CPP container. Run the external `cooneycw/mcp-second-opinion` server, then point the root `.mcp.json` `second-opinion` entry at it (`http://127.0.0.1:8080/mcp` for localhost, or a Tailscale URL for a remote host).
- **Browser automation missing:** register the upstream server with `/cpp:init`, or `claude mcp add --transport stdio --scope user playwright -- npx -y @playwright/mcp@latest --headless`
- **Stale containers:** `docker rm <name>` for stopped containers from old projects

## Notes

- This command works across all projects - it scans the entire Docker daemon
- Project linkage uses `com.docker.compose.project` labels (set automatically by docker compose)
- Health checks probe the root `/` endpoint of any container that publishes a host port
- Version info is extracted from the health endpoint JSON response when available
- If `sg docker` is needed (docker group not active in shell), the command handles this transparently
