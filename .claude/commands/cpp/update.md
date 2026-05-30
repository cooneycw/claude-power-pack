---
description: Update Claude Power Pack to the latest version
allowed-tools: Bash(git:*), Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(cat:*), Bash(uv:*), Bash(claude mcp list:*), Bash(sudo systemctl:*), Bash(systemctl:*), Bash(command -v:*), Bash(ln:*), Bash(mkdir:*), Bash(cp:*), Bash(diff:*), Bash(find:*), Bash(grep:*), Bash(curl:*), Bash(ss:*), Bash(docker:*), Bash(make:*), Bash(python3:*), AskUserQuestion
---

# Claude Power Pack Update

Update CPP to the latest version, detect MCP server drift, and offer guided remediation.

---

## Step 1: Locate CPP Source

```bash
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done

if [ -z "$CPP_DIR" ]; then
  echo "ERROR: claude-power-pack not found"
  echo "Please clone it first:"
  echo "  git clone https://github.com/cooneycw/claude-power-pack ~/Projects/claude-power-pack"
  exit 1
fi

echo "Found claude-power-pack at: $CPP_DIR"
```

---

## Step 2: Check Current Version and Remote

```bash
cd "$CPP_DIR"

# Get current version from CHANGELOG.md
CURRENT_VERSION=$(grep -oP '^\#\# \[\K[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md | head -1 || echo "unknown")
CURRENT_COMMIT=$(git rev-parse --short HEAD)
CURRENT_BRANCH=$(git branch --show-current)

echo "Current: v$CURRENT_VERSION ($CURRENT_COMMIT) on $CURRENT_BRANCH"

# Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo ""
  echo "WARNING: Uncommitted changes detected in CPP repo"
  git status --short
  echo ""
  echo "These changes may be overwritten by the update."
fi

# Fetch latest from origin
echo ""
echo "Fetching latest from origin..."
git fetch origin 2>&1

# Compare with remote
BEHIND=$(git rev-list HEAD..origin/$CURRENT_BRANCH --count 2>/dev/null || echo "0")
AHEAD=$(git rev-list origin/$CURRENT_BRANCH..HEAD --count 2>/dev/null || echo "0")

if [ "$BEHIND" -eq 0 ]; then
  echo ""
  echo "Already up to date!"
else
  echo ""
  echo "$BEHIND commit(s) behind origin/$CURRENT_BRANCH"
  echo ""
  echo "New changes:"
  git log --oneline HEAD..origin/$CURRENT_BRANCH
fi
```

Report the version comparison to the user.

---

## Step 3: Pull Updates

**Only if behind remote.** Ask user for confirmation before pulling.

If there are uncommitted changes, warn and ask if they want to stash first.

```bash
cd "$CPP_DIR"

# Stash if needed
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Stashing uncommitted changes..."
  git stash push -m "cpp-update auto-stash $(date +%Y%m%d-%H%M%S)"
fi

# Pull latest
git pull origin $CURRENT_BRANCH

NEW_COMMIT=$(git rev-parse --short HEAD)
NEW_VERSION=$(grep -oP '^\#\# \[\K[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md | head -1 || echo "unknown")
echo ""
echo "Updated: v$CURRENT_VERSION -> v$NEW_VERSION ($NEW_COMMIT)"
```

---

## Step 4: Update Dependencies (Tier 3)

If MCP server venvs exist, sync dependencies to pick up any new packages:

```bash
cd "$CPP_DIR"

for server_dir in mcp-second-opinion mcp-playwright-persistent mcp-nano-banana; do
  if [ -d "$server_dir/.venv" ]; then
    echo ""
    echo "Syncing dependencies for $server_dir..."
    cd "$CPP_DIR/$server_dir"
    uv sync
    echo "Done: $server_dir dependencies updated"
  fi
done
```

---

## Step 5: Detect Deployment Model and Refresh Runtime

Choose exactly one runtime model for this machine. Do not run Docker and
systemd restarts in the same update.

```bash
cd "$CPP_DIR"

DEPLOY_MODEL="venv-only"
DOCKER_READY=false
DOCKER_STACK_PRESENT=false
DOCKER_STACK_CONFIGURED=false
SYSTEMD_ACTIVE=false

if command -v docker &>/dev/null && [ -f "$CPP_DIR/docker-compose.yml" ] && docker compose version &>/dev/null; then
  DOCKER_READY=true

  if docker compose --profile core --profile browser --profile cicd ps --format json 2>/dev/null | grep -q '"Service"'; then
    DOCKER_STACK_PRESENT=true
  elif docker ps -a --format '{{.Names}}' 2>/dev/null | grep -Eq '^(aws-secrets-agent|mcp-second-opinion|mcp-nano-banana|mcp-playwright-persistent|mcp-woodpecker-ci)$'; then
    DOCKER_STACK_PRESENT=true
  fi

  if [ -f "$CPP_DIR/.env" ]; then
    DOCKER_STACK_CONFIGURED=true
  fi
fi

for service in mcp-second-opinion mcp-playwright nano-banana; do
  if systemctl is-active "$service" &>/dev/null || systemctl is-enabled "$service" &>/dev/null; then
    SYSTEMD_ACTIVE=true
    break
  fi
done

if [ "$DOCKER_READY" = "true" ] && { [ "$DOCKER_STACK_PRESENT" = "true" ] || [ "$DOCKER_STACK_CONFIGURED" = "true" ]; }; then
  DEPLOY_MODEL="docker"
elif [ "$SYSTEMD_ACTIVE" = "true" ]; then
  DEPLOY_MODEL="systemd"
fi

echo "Deployment model detected: $DEPLOY_MODEL"
```

### Docker Model

For Docker workstations, rebuild changed images, restart the full MCP stack,
wait for healthchecks, and print the post-update health summary.

```bash
if [ "$DEPLOY_MODEL" = "docker" ]; then
  echo ""
  echo "Refreshing Docker MCP stack..."
  make docker-refresh PROFILE="core browser cicd"
  DOCKER_REFRESH_RC=$?
  if [ "$DOCKER_REFRESH_RC" -ne 0 ]; then
    echo "ERROR: Docker refresh failed or one or more containers are unhealthy."
    exit "$DOCKER_REFRESH_RC"
  fi
fi
```

### Systemd Model

Keep the native systemd path for systemd workstations.

```bash
if [ "$DEPLOY_MODEL" = "systemd" ]; then
  for service in mcp-second-opinion mcp-playwright nano-banana; do
    if systemctl is-active "$service" &>/dev/null; then
      echo ""
      echo "Restarting $service..."
      sudo systemctl restart "$service"
      echo "Done: $service restarted"
    fi
  done
fi
```

### Venv-Only Model

```bash
if [ "$DEPLOY_MODEL" = "venv-only" ]; then
  echo ""
  echo "No Docker containers or systemd services detected."
  echo "Dependencies were synced; start MCP servers manually if needed."
fi
```

Report the chosen model and the health/restart result to the user:

```
Runtime Refresh:
  Model: {docker|systemd|venv-only}
  Docker: rebuilt/restarted/healthy, or skipped
  Systemd: restarted services, or skipped
```

If servers are not managed by Docker or systemd, remind the user to start them manually.

---

## Step 6: MCP Server Drift Detection

After pulling and refreshing the selected runtime, scan for drift between what
the repo ships and what is actually installed/running.

### 6a: Build Inventory

Build two lists - what the repo ships vs what is installed - then compare.

**Repo inventory** - scan for active MCP servers the repo provides:

```bash
cd "$CPP_DIR"

echo "=== Repo MCP Server Inventory ==="

# Active servers from docker-compose.yml (uncommented services with ports)
echo "Docker-compose services:"
grep -E '^\s{2}[a-z].*:$' docker-compose.yml | grep -v '^\s*#' | sed 's/://;s/^ */  /'

echo ""
echo "Service files:"
find . -path '*/deploy/*.service' -type f | sort | while read f; do
  echo "  $f"
done

echo ""
echo "Dockerfiles:"
find . -path '*/deploy/Dockerfile' -type f | sort | while read f; do
  echo "  $f"
done
```

**Installed inventory** - scan what is currently running/registered:

```bash
echo ""
echo "=== Installed MCP Inventory ==="

echo "Docker containers:"
if [ "$DOCKER_READY" = "true" ]; then
  docker compose --profile core --profile browser --profile cicd ps 2>/dev/null || echo "  (unavailable)"
else
  echo "  (docker unavailable)"
fi

echo ""
echo "Systemd services (mcp-* and nano-*):"
systemctl list-units --type=service --all 2>/dev/null | grep -E '(mcp-|nano-|coordination)' || echo "  (none)"

echo ""
echo "Claude MCP registrations:"
claude mcp list 2>/dev/null || echo "  (unavailable)"

echo ""
echo "Listening ports (8080-8089):"
ss -tlnp 2>/dev/null | grep -E ':(808[0-9]|8084)' || echo "  (none)"
```

### 6b: Detect Drift

Compare the inventories and classify each finding. Use the following logic:

**Known repo servers** (from docker-compose.yml, not commented out):
- `mcp-second-opinion` (port 8080, profile: core)
- `mcp-nano-banana` (port 8084, profile: core)
- `mcp-playwright-persistent` (port 8081, profile: browser)
- `mcp-woodpecker-ci` (port 8085, profile: cicd)

**Deprecated servers** (commented out in docker-compose.yml):
- `mcp-evaluate` (deprecated - absorbed into /evaluate:issue skill)

**For each known repo server**, check:
1. Is there a Docker container running/healthy?
2. Is there a systemd service installed? (`systemctl is-enabled <name>`)
3. Is it registered in `claude mcp list`?
4. Is the port listening?
5. If systemd service exists, does it match the repo version? (diff the files)

**For each installed systemd service matching mcp-* or coordination**, check:
1. Does a corresponding deploy/*.service file exist in the repo?
2. If not, it is **orphaned** - repo no longer ships it.

Build a drift report table:

```
MCP Server Drift Report
========================

Server                    Repo    Docker    Systemd   MCP Reg   Port    Status
----------------------------------------------------------------------------
mcp-second-opinion        yes     healthy   active    yes       8080    OK / STALE SERVICE
mcp-nano-banana           yes     healthy   none      no        8084    NOT REGISTERED
mcp-playwright-persistent yes     healthy   active    yes       8081    OK / STALE SERVICE
mcp-woodpecker-ci         yes     healthy   none      yes       8085    OK
mcp-coordination          no      none      active    yes       8082    ORPHANED
mcp-evaluate              depr.   none      none      no        --      OK (deprecated)
```

Status classifications:
- **OK** - repo server is installed, registered, and running
- **STALE SERVICE** - installed but systemd unit differs from repo version
- **NEW - NOT INSTALLED** - repo ships it but it is not installed
- **ORPHANED** - installed/running but repo no longer ships it
- **NOT RUNNING** - installed but service/container is not active
- **UNHEALTHY** - Docker container is running but healthcheck is failing
- **NOT REGISTERED** - running but not in `claude mcp list`

Present the drift report table to the user.

### 6c: Check for Docker Availability

```bash
if command -v docker &>/dev/null; then
  echo ""
  echo "Docker: available ($(docker --version 2>/dev/null | head -1))"
  if docker compose version &>/dev/null 2>&1; then
    echo "Docker Compose: available"
  fi
  DOCKER_AVAILABLE=true
else
  DOCKER_AVAILABLE=false
fi
```

---

## Step 7: Guided Remediation

For each drift finding, offer the user actionable options using AskUserQuestion.

**Only show this if drift was detected.** If everything is clean, skip to Step 8.

### For NEW servers (in repo, not installed):

Ask the user per server:

```
mcp-nano-banana is available in the repo but not installed.
  - Port: 8084
  - Docker profile: core
  - Purpose: Diagram generation + PowerPoint creation
```

Options:
- **Install via systemd** - Copy service file, enable, start, register with claude mcp
- **Install via Docker** - Will be included in `make docker-refresh PROFILE="core browser cicd"` (if Docker model is active)
- **Skip** - Do not install now

If they choose systemd:
1. Copy the service file: `sudo cp $CPP_DIR/<server>/deploy/<name>.service /etc/systemd/system/`
2. Adjust paths if needed (replace `%h` with actual home dir for system services)
3. `sudo systemctl daemon-reload`
4. `sudo systemctl enable --now <name>`
5. Register: `claude mcp add --scope user --transport sse <name> http://127.0.0.1:<port>/sse`
6. Sync venv if needed: `cd $CPP_DIR/<server> && uv sync`

### For ORPHANED services (installed but removed from repo):

Ask the user per service:

```
mcp-coordination is running but has been removed from the repo.
```

Options:
- **Remove** - Stop service, disable, remove service file, unregister from claude mcp
- **Keep** - Leave it running (user may have a custom setup)

If they choose remove:
1. `sudo systemctl stop <name>`
2. `sudo systemctl disable <name>`
3. `sudo rm /etc/systemd/system/<name>.service`
4. `sudo systemctl daemon-reload`
5. `claude mcp remove <name>` (if registered)

### For STALE service files:

Show the meaningful differences (ignore comment-only changes). Ask:

```
mcp-second-opinion service file differs from repo version.
Key differences:
  - Installed uses hardcoded paths, repo uses %h placeholders
  - Installed has ProtectHome/ProtectSystem sandboxing, repo does not
  - [other diffs]
```

Options:
- **Update** - Replace service file with repo version (adjusting %h to actual paths for system services), reload, restart
- **Keep current** - Leave installed version as-is

If they choose update:
1. Back up: `sudo cp /etc/systemd/system/<name>.service /etc/systemd/system/<name>.service.bak`
2. Copy new version: `sudo cp $CPP_DIR/<server>/deploy/<name>.service /etc/systemd/system/`
3. Adjust `%h` to actual home directory path (for system-level services)
4. `sudo systemctl daemon-reload`
5. `sudo systemctl restart <name>`

### For NOT REGISTERED servers (running but not in claude mcp list):

```
mcp-nano-banana is running on port 8084 but not registered with Claude Code.
```

Options:
- **Register** - `claude mcp add --scope user --transport sse <name> http://127.0.0.1:<port>/sse`
- **Skip** - Leave unregistered

---

## Step 8: Detect Current Installation Tier

Determine the user's current tier level so we can offer upgrades:

```bash
cd "$CPP_DIR"

# Tier 1 checks
TIER=0

# Commands + Skills
if [ -L ".claude/commands" ] || [ -d ".claude/commands" ]; then
  if [ -L ".claude/skills" ] || [ -d ".claude/skills" ]; then
    TIER=1
  fi
fi

# Tier 2: scripts + hooks
SCRIPTS_COUNT=0
for script in prompt-context.sh worktree-remove.sh secrets-mask.sh hook-mask-output.sh hook-validate-command.sh; do
  [ -f ~/.claude/scripts/$script ] || [ -L ~/.claude/scripts/$script ] && SCRIPTS_COUNT=$((SCRIPTS_COUNT + 1))
done
[ -f ".claude/hooks.json" ] && [ "$SCRIPTS_COUNT" -ge 3 ] && TIER=2

# Tier 3: MCP servers
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
if echo "$MCP_LIST" | grep -q "second-opinion"; then
  TIER=3
fi
```

---

## Step 9: Offer Tier Upgrade

If the user is not at the highest tier, ask if they want to upgrade using AskUserQuestion:

**Only show this if current tier < 3.**

```
Your current installation: Tier {TIER}

Available upgrades:
  Tier 1 (Minimal): Commands + Skills symlinks
  Tier 2 (Standard): + Scripts, hooks, shell prompt, permission profiles
  Tier 3 (Full): + MCP servers (Docker or systemd, uv, API keys)

Would you like to upgrade to a higher tier?
```

**Options:**
- **Keep current tier** - No changes beyond the git pull
- **Upgrade to Tier 2** (if currently Tier 0 or 1)
- **Upgrade to Tier 3** (if currently below Tier 3)

If upgrading, follow the same installation steps as `/cpp:init` for the new tier only.

---

## Step 10: Update Summary

```
=================================
CPP Update Complete
=================================

Version: v{OLD_VERSION} -> v{NEW_VERSION}
Commit:  {OLD_COMMIT} -> {NEW_COMMIT}
Branch:  {BRANCH}
Tier:    {TIER} {(upgraded from X if applicable)}

Changes pulled:
  {list of new commits, or "Already up to date"}

Dependencies:
  {synced servers or "No MCP venvs to update"}

Runtime:
  Model: {docker|systemd|venv-only}
  {Docker containers rebuilt/restarted/healthy, systemd services restarted, or venv-only no restart}

MCP Drift:
  {drift summary - e.g. "1 new server installed, 1 orphan removed, 2 service files updated"
   or "No drift detected - all servers in sync"}

Run /cpp:status for full installation details.
=================================
```

---

## Notes

- This command is safe to run repeatedly (idempotent)
- Uncommitted changes in CPP are auto-stashed before pull
- Symlinked commands/skills are automatically updated by the git pull
- MCP server dependencies are synced if venvs exist
- Docker workstations rebuild and restart containers with `make docker-refresh PROFILE="core browser cicd"` and fail if healthchecks fail
- Running systemd services are automatically restarted on systemd-model machines
- MCP drift detection compares repo state against Docker containers, installed systemd services, claude mcp registrations, and listening ports
- Orphaned services (removed from repo) are flagged for cleanup
- New servers are offered for installation via systemd or Docker
- Stale service files are diffed and can be updated with backup
- mcp-evaluate is recognized as deprecated and not flagged as missing
- Use `/cpp:init` instead if you need the full interactive setup wizard
