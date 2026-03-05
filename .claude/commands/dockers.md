---
description: Show Docker container status, health, and project linkages
allowed-tools: Bash(docker:*), Bash(sg:*), Bash(curl:*), Bash(cat:*), Bash(ls:*), Bash(grep:*), Bash(find:*), Read
---

# /dockers — Docker Container Status

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

Start MCP servers with: make docker-up PROFILE=core
Available profiles: core (second-opinion + nano-banana), browser (playwright)
```

### Step 3: Health Check Each MCP Container

For each container with an exposed port, hit the health endpoint:

```bash
# Known MCP server ports and their health endpoints
declare -A MCP_PORTS=(
    ["mcp-second-opinion"]="8080"
    ["mcp-nano-banana"]="8084"
    ["mcp-playwright-persistent"]="8081"
)

for name in "${!MCP_PORTS[@]}"; do
    port="${MCP_PORTS[$name]}"
    response=$(curl -sf --max-time 3 "http://127.0.0.1:${port}/" 2>/dev/null)
    if [ $? -eq 0 ]; then
        # Check for no_api_keys status
        if echo "$response" | grep -q '"no_api_keys"' 2>/dev/null; then
            echo "$name|$port|NO API KEYS|$response"
        else
            echo "$name|$port|healthy|$response"
        fi
    else
        echo "$name|$port|unreachable|"
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

### MCP Servers

| Container | Port | Health | Version | Project | Profile |
|-----------|------|--------|---------|---------|---------|
| mcp-second-opinion | 8080 | healthy | v1.9.0 | claude-power-pack | core |
| mcp-nano-banana | 8084 | healthy | v1.0.0 | claude-power-pack | core |
| mcp-playwright-persistent | 8081 | healthy | — | claude-power-pack | browser |

### Other Containers

| Container | Image | Status | Ports |
|-----------|-------|--------|-------|
| my-app-db | postgres:16 | Up 2 hours | 5432 |

### Summary
- **Total containers:** 4 (3 healthy, 1 running)
- **MCP servers:** 3/3 reachable
- **Profiles active:** core, browser
```

### Step 6: Suggest Actions

Based on findings, suggest relevant actions:

- **No API keys:** Create `.env` in claude-power-pack root with `GEMINI_API_KEY=...`, then `make docker-down && make docker-up PROFILE=core`. Or run `/cpp:init` to configure interactively.
- **Unhealthy containers:** `make docker-down && make docker-up PROFILE=core`
- **Missing profiles:** `make docker-up PROFILE=browser` (if browser not running)
- **No MCP containers:** `make docker-build PROFILE=core && make docker-up PROFILE=core`
- **Stale containers:** `docker rm <name>` for stopped containers from old projects

## Notes

- This command works across all projects — it scans the entire Docker daemon
- Project linkage uses `com.docker.compose.project` labels (set automatically by docker compose)
- Health checks use the root `/` endpoint convention established for all CPP MCP servers
- Version info is extracted from the health endpoint JSON response when available
- If `sg docker` is needed (docker group not active in shell), the command handles this transparently
