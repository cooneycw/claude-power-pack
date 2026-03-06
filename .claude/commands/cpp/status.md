---
description: Check Claude Power Pack installation state
allowed-tools: Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(uv:*), Bash(python3:*), Bash(PYTHONPATH=*), Bash(claude mcp list:*), Bash(systemctl:*), Bash(grep:*)
---

# CPP Installation Status

Check the current installation state of Claude Power Pack components.

## Step 1: Detect CPP Source Location

Find where claude-power-pack is installed:

```bash
# Check common locations
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done

if [ -z "$CPP_DIR" ]; then
  echo "ERROR: claude-power-pack not found"
  echo "Expected locations: ~/Projects/claude-power-pack, /opt/claude-power-pack, ~/.claude-power-pack"
fi
```

## Step 2: Check Tier 1 (Minimal)

Check if commands and skills are symlinked:

```bash
# Check commands symlink
if [ -L ".claude/commands" ]; then
  COMMANDS_TARGET=$(readlink -f .claude/commands)
  echo "[x] Commands symlinked → $COMMANDS_TARGET"
elif [ -d ".claude/commands" ]; then
  echo "[~] Commands directory exists (not symlinked)"
else
  echo "[ ] Commands: not installed"
fi

# Check skills symlink
if [ -L ".claude/skills" ]; then
  SKILLS_TARGET=$(readlink -f .claude/skills)
  echo "[x] Skills symlinked → $SKILLS_TARGET"
elif [ -d ".claude/skills" ]; then
  echo "[~] Skills directory exists (not symlinked)"
else
  echo "[ ] Skills: not installed"
fi
```

## Step 3: Check Tier 2 (Standard)

Check scripts, hooks, and shell prompt:

```bash
# Check scripts
SCRIPTS_INSTALLED=0
SCRIPTS_TOTAL=0
for script in prompt-context.sh worktree-remove.sh secrets-mask.sh hook-mask-output.sh hook-validate-command.sh; do
  SCRIPTS_TOTAL=$((SCRIPTS_TOTAL + 1))
  if [ -f ~/.claude/scripts/$script ] || [ -L ~/.claude/scripts/$script ]; then
    SCRIPTS_INSTALLED=$((SCRIPTS_INSTALLED + 1))
  fi
done
echo "Scripts: $SCRIPTS_INSTALLED/$SCRIPTS_TOTAL installed in ~/.claude/scripts/"

# Check hooks.json
if [ -f ".claude/hooks.json" ]; then
  HOOK_COUNT=$(grep -c '"event"' .claude/hooks.json 2>/dev/null || echo "0")
  echo "[x] Hooks configured: $HOOK_COUNT hooks in .claude/hooks.json"
else
  echo "[ ] Hooks: .claude/hooks.json not found"
fi

# Check shell prompt integration (look for prompt-context.sh in bashrc/zshrc)
if grep -q "prompt-context.sh" ~/.bashrc 2>/dev/null || grep -q "prompt-context.sh" ~/.zshrc 2>/dev/null; then
  echo "[x] Shell prompt: configured"
else
  echo "[ ] Shell prompt: not configured"
fi
```

## Step 3b: Check Permission Profile (Tier 2+)

Check auto-approval settings in `.claude/settings.local.json`:

```bash
# Check permission profile
if [ -f ".claude/settings.local.json" ]; then
  # Try to detect profile type from allow rules
  ALLOW_COUNT=$(grep -c '"allow"' .claude/settings.local.json 2>/dev/null || echo "0")

  if grep -q '"Write"' .claude/settings.local.json 2>/dev/null; then
    if grep -q '"Bash(git:\*)"' .claude/settings.local.json 2>/dev/null; then
      PROFILE="Trusted"
    else
      PROFILE="Custom"
    fi
  elif grep -q '"Bash(git status:\*)"' .claude/settings.local.json 2>/dev/null; then
    PROFILE="Standard"
  elif grep -q '"Read"' .claude/settings.local.json 2>/dev/null; then
    if grep -q '"Bash(' .claude/settings.local.json 2>/dev/null; then
      PROFILE="Custom"
    else
      PROFILE="Cautious"
    fi
  else
    PROFILE="Custom"
  fi

  echo "[x] Permission profile: $PROFILE (.claude/settings.local.json)"

  # Count rules
  ALLOW_RULES=$(grep -oE '"[^"]+"\s*,' .claude/settings.local.json 2>/dev/null | wc -l || echo "0")
  DENY_RULES=$(grep -A100 '"deny"' .claude/settings.local.json 2>/dev/null | grep -c '"' || echo "0")
  echo "    Auto-approve rules: ~$ALLOW_RULES"
else
  echo "[ ] Permission profile: not configured"
  echo "    Run /cpp:init to set up auto-approvals"
fi
```

## Step 3c: Check Workstation Tuning (bash-prep)

Check if Linux kernel and swap parameters are optimally configured:

```bash
# Only check on Linux
if [ "$(uname)" = "Linux" ]; then
  echo ""
  echo "Workstation Tuning (bash-prep):"

  TUNING_ISSUES=0

  # Swap
  SWAP_MB=$(awk '/SwapTotal/ { printf "%d", $2 / 1024 }' /proc/meminfo)
  if (( SWAP_MB >= 2048 )); then
    echo "  [x] Swap: ${SWAP_MB} MB"
  else
    echo "  [ ] Swap: ${SWAP_MB} MB (recommended: 2048+ MB)"
    TUNING_ISSUES=$((TUNING_ISSUES + 1))
  fi

  # Swappiness
  VAL=$(sysctl -n vm.swappiness 2>/dev/null || echo "unknown")
  if [ "$VAL" = "10" ]; then
    echo "  [x] vm.swappiness = $VAL"
  else
    echo "  [ ] vm.swappiness = $VAL (recommended: 10)"
    TUNING_ISSUES=$((TUNING_ISSUES + 1))
  fi

  # VFS cache pressure
  VAL=$(sysctl -n vm.vfs_cache_pressure 2>/dev/null || echo "unknown")
  if [ "$VAL" = "50" ]; then
    echo "  [x] vm.vfs_cache_pressure = $VAL"
  else
    echo "  [ ] vm.vfs_cache_pressure = $VAL (recommended: 50)"
    TUNING_ISSUES=$((TUNING_ISSUES + 1))
  fi

  # Inotify watches
  VAL=$(sysctl -n fs.inotify.max_user_watches 2>/dev/null || echo "0")
  if (( VAL >= 524288 )); then
    echo "  [x] fs.inotify.max_user_watches = $VAL"
  else
    echo "  [ ] fs.inotify.max_user_watches = $VAL (recommended: 524288)"
    TUNING_ISSUES=$((TUNING_ISSUES + 1))
  fi

  # Inotify instances
  VAL=$(sysctl -n fs.inotify.max_user_instances 2>/dev/null || echo "0")
  if (( VAL >= 512 )); then
    echo "  [x] fs.inotify.max_user_instances = $VAL"
  else
    echo "  [ ] fs.inotify.max_user_instances = $VAL (recommended: 512)"
    TUNING_ISSUES=$((TUNING_ISSUES + 1))
  fi

  if (( TUNING_ISSUES > 0 )); then
    echo "  Status: $TUNING_ISSUES issue(s) - run: bash ~/.claude/scripts/bash-prep.sh"
  else
    echo "  Status: Optimal"
  fi
fi
```

## Step 4: Check Tier 3 (Full)

Check MCP servers and dependencies:

```bash
# Check uv
if command -v uv &>/dev/null; then
  UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
  echo "[x] uv: $UV_VERSION"
else
  echo "[ ] uv: not installed"
fi

# Check MCP server pyproject.toml files
echo ""
echo "MCP Server Projects:"
for server in mcp-second-opinion mcp-playwright-persistent; do
  if [ -f "$CPP_DIR/$server/pyproject.toml" ]; then
    echo "  [x] $server: pyproject.toml found"
  else
    echo "  [ ] $server: pyproject.toml missing"
  fi
done

# Check MCP servers registered
echo ""
echo "MCP Servers (Claude Code):"
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
for server in second-opinion playwright-persistent; do
  if echo "$MCP_LIST" | grep -q "$server"; then
    echo "  [x] $server: registered"
  else
    echo "  [ ] $server: not registered"
  fi
done

# Check MCP server connectivity and API key status
echo ""
echo "MCP Server Connectivity:"
for entry in "8080:second-opinion" "8081:playwright-persistent"; do
  PORT="${entry%%:*}"
  NAME="${entry#*:}"
  HEALTH_RESPONSE=$(curl -sf --max-time 2 "http://127.0.0.1:${PORT}/" 2>/dev/null)
  if [ -n "$HEALTH_RESPONSE" ]; then
    # Check for no_api_keys status in health response
    if echo "$HEALTH_RESPONSE" | grep -q '"no_api_keys"' 2>/dev/null; then
      echo "  [!] $NAME (port $PORT): reachable but NO API KEYS configured"
      echo "      Create $CPP_DIR/.env with GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY"
      echo "      Then restart: cd $CPP_DIR && make docker-down && make docker-up PROFILE=core"
    else
      echo "  [x] $NAME (port $PORT): reachable"
    fi
  elif ss -tlnp 2>/dev/null | grep -q ":${PORT} " 2>/dev/null; then
    echo "  [~] $NAME (port $PORT): port open (no health endpoint)"
  else
    echo "  [ ] $NAME (port $PORT): not reachable"
  fi
done

# Check .env file for Docker deployments
echo ""
echo "Docker API Keys (.env):"
if [ -f "$CPP_DIR/.env" ]; then
  KEY_COUNT=$(grep -cE '^(GEMINI|OPENAI|ANTHROPIC)_API_KEY=.+' "$CPP_DIR/.env" 2>/dev/null || echo "0")
  if [ "$KEY_COUNT" -gt 0 ]; then
    echo "  [x] $CPP_DIR/.env: $KEY_COUNT API key(s) configured"
    grep -oE '^(GEMINI|OPENAI|ANTHROPIC)_API_KEY=' "$CPP_DIR/.env" 2>/dev/null | while read key; do
      echo "      - ${key%=}"
    done
  else
    echo "  [!] $CPP_DIR/.env exists but contains no API keys"
  fi
else
  echo "  [ ] $CPP_DIR/.env: not found (Docker containers have no API keys)"
  echo "      Run /cpp:init or create manually"
fi

# Check systemd services
echo ""
echo "Systemd Services:"
for service in mcp-second-opinion mcp-playwright-persistent; do
  if systemctl is-enabled $service &>/dev/null; then
    if systemctl is-active $service &>/dev/null; then
      echo "  [x] $service: enabled, running"
    else
      echo "  [~] $service: enabled, stopped"
    fi
  else
    echo "  [ ] $service: not installed"
  fi
done
```

## Step 5: Check Tier 4 (CI/CD)

Check CI/CD build system, health checks, pipeline, and container configuration:

```bash
echo ""
echo "Tier 4 (CI/CD):"

# Check cicd.yml
if [ -f ".claude/cicd.yml" ]; then
  echo "  [x] cicd.yml: configured"
else
  echo "  [ ] cicd.yml: not found"
fi

# Check framework detection
if [ -n "$CPP_DIR" ] && [ -f "$CPP_DIR/lib/cicd/__init__.py" ]; then
  FRAMEWORK=$(PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd detect --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('framework','unknown')} ({d.get('package_manager','unknown')})\")" 2>/dev/null || echo "detection unavailable")
  echo "  [x] Framework detected: $FRAMEWORK"
else
  echo "  [ ] Framework detection: lib/cicd not available"
fi

# Check Makefile
if [ -f "Makefile" ]; then
  TARGET_COUNT=$(grep -cE '^[a-zA-Z_-]+:' Makefile 2>/dev/null || echo "0")
  echo "  [x] Makefile: $TARGET_COUNT targets"
else
  echo "  [ ] Makefile: not found"
fi

# Check CI workflow
if [ -f ".github/workflows/ci.yml" ] || [ -f ".github/workflows/ci.yaml" ]; then
  echo "  [x] CI pipeline: .github/workflows/ci.yml"
elif ls .github/workflows/*.yml 2>/dev/null | head -1 > /dev/null 2>&1; then
  WF_COUNT=$(ls .github/workflows/*.yml 2>/dev/null | wc -l)
  echo "  [~] CI pipeline: $WF_COUNT workflow(s) found (no ci.yml)"
else
  echo "  [ ] CI pipeline: no workflows found"
fi

# Check Dockerfile
if [ -f "Dockerfile" ]; then
  echo "  [x] Dockerfile: present"
else
  echo "  [ ] Dockerfile: not found"
fi

# Check docker-compose
if [ -f "docker-compose.yml" ] || [ -f "docker-compose.yaml" ]; then
  echo "  [x] docker-compose: present"
else
  echo "  [ ] docker-compose: not found"
fi
```

## Step 6: Summary

Based on the checks above, report:

1. **Current tier level** - Which tier is fully installed
2. **Missing components** - What needs to be installed
3. **Recommendation** - Suggest running `/cpp:init` if incomplete

Example output format:

```
=================================
CPP Installation Status
=================================

Tier 1 (Minimal):
  [x] Commands symlinked
  [x] Skills symlinked
  Status: Complete

Tier 2 (Standard):
  [x] Scripts: 5/5 installed
  [x] Hooks: 2 hooks configured
  [x] Permission profile: Standard
      Auto-approve rules: ~22
  [ ] Shell prompt: not configured
  Status: Partial

Tier 3 (Full):
  [x] uv: 0.5.x
  [x] mcp-second-opinion: pyproject.toml + registered
  [ ] mcp-playwright-persistent: not configured
  MCP Connectivity:
    [x] second-opinion (port 8080): reachable
    [ ] playwright-persistent (port 8081): not reachable
  [ ] Systemd: not installed
  Status: Partial

Tier 4 (CI/CD):
  [x] cicd.yml: configured
  [x] Framework detected: python (uv)
  [x] Makefile: 8 targets
  [ ] CI pipeline: no workflows found
  [ ] Dockerfile: not found
  Status: Partial

---------------------------------
Current Level: Tier 2 (Standard)
Missing: Shell prompt, mcp-playwright-persistent, systemd, CI pipeline, Dockerfile

Run /cpp:init to complete setup
=================================
```

## Notes

- `[x]` = Fully installed
- `[~]` = Partially installed or needs attention
- `[ ]` = Not installed
- Symlinks are preferred over copied files for easier updates
