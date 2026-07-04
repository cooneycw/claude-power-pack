---
description: Check Claude Power Pack installation state
allowed-tools: Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(uv:*), Bash(python3:*), Bash(PYTHONPATH=*), Bash(claude mcp list:*), Bash(systemctl:*), Bash(grep:*), Bash(docker ps:*), Bash(docker inspect:*)
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
```

## Step 3: Check Tier 2 (Standard)

Check scripts, hooks, and shell prompt:

```bash
# Check scripts
SCRIPTS_INSTALLED=0
SCRIPTS_TOTAL=0
for script in prompt-context.sh worktree-remove.sh secrets-mask.sh hook-mask-output.sh; do
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

# CPP ships no local MCP server projects. The second-opinion server is external
# (the cooneycw/mcp-second-opinion repo), connected via the root .mcp.json
# streamable-http pointer. Browser automation is upstream @playwright/mcp (npx/stdio).
echo ""
echo "MCP Server Projects:"
echo "  [-] none bundled (second-opinion is external via .mcp.json; playwright via npx/stdio)"

# Check MCP servers registered
echo ""
echo "MCP Servers (Claude Code):"
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
for server in second-opinion playwright; do
  if echo "$MCP_LIST" | grep -q "$server"; then
    echo "  [x] $server: registered"
  else
    echo "  [ ] $server: not registered"
  fi
done
if echo "$MCP_LIST" | grep -q "playwright-persistent"; then
  echo "  [!] playwright-persistent: legacy registration (retired #423) - run /cpp:update to tear down"
fi

# Check Codex MCP registrations
echo ""
echo "MCP Servers (Codex):"
if command -v codex &>/dev/null; then
  CODEX_LIST=$(codex mcp list 2>/dev/null || echo "")
  for server in second-opinion playwright; do
    if echo "$CODEX_LIST" | grep -q "$server"; then
      echo "  [x] $server: registered"
    else
      echo "  [ ] $server: not registered"
    fi
  done
else
  echo "  [ ] Codex CLI: not installed"
fi

# MCP server wiring. CPP no longer runs any MCP server as a local container.
# The second-opinion server is external (cooneycw/mcp-second-opinion) and is reached
# over the root .mcp.json streamable-http pointer (localhost http://127.0.0.1:8080/mcp
# or a Tailscale URL). Report how it is wired rather than probing a CPP-owned port.
echo ""
echo "MCP Server Wiring (.mcp.json):"
if [ -f ".mcp.json" ] && grep -q "second-opinion" .mcp.json 2>/dev/null; then
  SO_URL=$(grep -oE 'https?://[^"[:space:]]+' .mcp.json 2>/dev/null | head -1)
  echo "  [x] second-opinion: registered in .mcp.json (${SO_URL:-external mcp-second-opinion server})"
  if [ -n "$SO_URL" ] && curl -sf --max-time 2 -o /dev/null "$SO_URL" 2>/dev/null; then
    echo "      reachable"
  else
    echo "      [~] not verified reachable - run the external mcp-second-opinion server (localhost or Tailscale)"
  fi
else
  echo "  [ ] second-opinion: not registered in .mcp.json"
  echo "      Run the external cooneycw/mcp-second-opinion server, then point .mcp.json"
  echo "      at it (http://127.0.0.1:8080/mcp for localhost, or a Tailscale URL)."
fi
echo "  [-] playwright: upstream @playwright/mcp over npx/stdio (no port to probe)"

# Check legacy systemd services
echo ""
echo "Legacy Systemd:"
KNOWN_LEGACY_SYSTEMD_UNITS=$(cat <<'EOF'
mcp-second-opinion
second-opinion
mcp-playwright
mcp-playwright-persistent
playwright-persistent
mcp-evaluate
evaluate
mcp-coordination
coordination
EOF
)
DISCOVERED_LEGACY_SYSTEMD_UNITS="$(
  {
    printf '%s\n' "$KNOWN_LEGACY_SYSTEMD_UNITS"
    find "$HOME/.config/systemd/user" /etc/systemd/system -maxdepth 1 -type f \
      \( -name 'mcp-*.service' -o -name 'nano-*.service' -o -name '*coordination*.service' \) \
      -printf '%f\n' 2>/dev/null || true
    systemctl --user list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
  } | sed 's/\.service$//' | grep -E '^(mcp-|nano-|.*coordination|second-opinion|playwright-persistent|evaluate|coordination)$' | sort -u
)"
LEGACY_SYSTEMD_FOUND=0
for unit in $DISCOVERED_LEGACY_SYSTEMD_UNITS; do
  USER_PATH="$HOME/.config/systemd/user/${unit}.service"
  SYSTEM_PATH="/etc/systemd/system/${unit}.service"

  USER_ACTIVE=$(systemctl --user is-active "$unit" 2>/dev/null || true)
  USER_ENABLED=$(systemctl --user is-enabled "$unit" 2>/dev/null || true)
  if [ -f "$USER_PATH" ] || [ "$USER_ACTIVE" = "active" ] || [ "$USER_ENABLED" = "enabled" ]; then
    LEGACY_SYSTEMD_FOUND=1
    if [ "$USER_ACTIVE" = "active" ]; then
      echo "  [!] user:$unit active, enabled=${USER_ENABLED:-unknown} - run /cpp:update to remove the legacy unit"
    else
      echo "  [~] user:$unit active=${USER_ACTIVE:-inactive}, enabled=${USER_ENABLED:-unknown} - run /cpp:update to remove legacy unit"
    fi
  fi

  SYSTEM_ACTIVE=$(systemctl is-active "$unit" 2>/dev/null || true)
  SYSTEM_ENABLED=$(systemctl is-enabled "$unit" 2>/dev/null || true)
  if [ -f "$SYSTEM_PATH" ] || [ "$SYSTEM_ACTIVE" = "active" ] || [ "$SYSTEM_ENABLED" = "enabled" ]; then
    LEGACY_SYSTEMD_FOUND=1
    if [ "$SYSTEM_ACTIVE" = "active" ]; then
      echo "  [!] system:$unit active, enabled=${SYSTEM_ENABLED:-unknown} - run /cpp:update to remove the legacy unit"
    else
      echo "  [~] system:$unit active=${SYSTEM_ACTIVE:-inactive}, enabled=${SYSTEM_ENABLED:-unknown} - run /cpp:update to remove legacy unit"
    fi
  fi
done
if [ "$LEGACY_SYSTEMD_FOUND" -eq 0 ]; then
  echo "  none (ok)"
fi

# Check orphaned Docker MCP servers (removed from compose but still present as a
# container, mcp-<name>:* image, or claude/codex registration). Driven by the
# curated .claude/deprecated-mcps.yaml list of record (issue #405). This closes
# the blind spot where a removed Docker server kept running unreported.
echo ""
echo "Orphaned Docker MCP (teardown available via /cpp:update):"
if command -v docker &>/dev/null && [ -f "$CPP_DIR/scripts/mcp-drift.py" ]; then
  ORPHAN_MCPS="$(python3 "$CPP_DIR/scripts/mcp-drift.py" --list-orphans 2>/dev/null || true)"
  if [ -n "$ORPHAN_MCPS" ]; then
    while IFS= read -r m; do
      [ -n "$m" ] && echo "  [!] $m: removed from docker-compose.yml but still present - run /cpp:update to tear down"
    done <<< "$ORPHAN_MCPS"
  else
    echo "  none (ok)"
  fi
else
  echo "  skipped (docker or mcp-drift.py unavailable)"
fi
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

## Step 6: Check Tier 5 (Codex Orchestration)

Check Codex CLI installation, configuration, and MCP registrations:

```bash
echo ""
echo "Tier 5 (Codex):"

# Check Codex CLI
if command -v codex &>/dev/null; then
  CODEX_VERSION=$(codex --version 2>/dev/null || echo "unknown")
  echo "  [x] Codex CLI: $CODEX_VERSION"
else
  echo "  [ ] Codex CLI: not installed"
fi

# Check codex doctor
if command -v codex &>/dev/null; then
  DOCTOR_OUTPUT=$(codex doctor 2>&1 || true)
  if echo "$DOCTOR_OUTPUT" | grep -qi "error\|fail\|missing"; then
    echo "  [!] codex doctor: issues detected"
  else
    echo "  [x] codex doctor: passed"
  fi
fi

# Check OpenAI API key
CODEX_CONFIG="$HOME/.codex/config.toml"
if [ -n "$OPENAI_API_KEY" ]; then
  echo "  [x] OpenAI API key: set in environment"
elif [ -f "$CODEX_CONFIG" ]; then
  echo "  [x] OpenAI API key: configured in $CODEX_CONFIG"
else
  echo "  [ ] OpenAI API key: not configured"
fi

# Check Codex MCP registrations
if command -v codex &>/dev/null; then
  CODEX_MCP=$(codex mcp list 2>/dev/null || echo "")
  for server in second-opinion playwright; do
    if echo "$CODEX_MCP" | grep -q "$server"; then
      echo "  [x] Codex MCP: $server registered"
    else
      echo "  [ ] Codex MCP: $server not registered"
    fi
  done
fi

# Check Codex commands available
if [ -d ".claude/commands/codex" ] || [ -L ".claude/commands" ]; then
  CODEX_CMDS=0
  for cmd in auto exec status help; do
    if [ -f ".claude/commands/codex/${cmd}.md" ]; then
      CODEX_CMDS=$((CODEX_CMDS + 1))
    fi
  done
  echo "  [x] Codex commands: $CODEX_CMDS/4 available"
else
  echo "  [ ] Codex commands: not installed"
fi
```

## Step 8: Summary

Based on the checks above, report:

1. **Current tier level** - Which tier is fully installed
2. **MCP wiring** - second-opinion is external (cooneycw/mcp-second-opinion) via `.mcp.json`; there is no CPP-managed container runtime
3. **Missing components** - What needs to be installed
4. **Recommendation** - Suggest running `/cpp:init` if incomplete, or `/cpp:update` if legacy systemd units remain

Example output format:

```
=================================
CPP Installation Status
=================================

Tier 1 (Minimal):
  [x] Commands symlinked
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
  [x] second-opinion: registered (external cooneycw/mcp-second-opinion via .mcp.json)
  [x] playwright: registered (upstream @playwright/mcp, npx/stdio)
  MCP Server Wiring (.mcp.json):
    [x] second-opinion: registered in .mcp.json (http://127.0.0.1:8080/mcp)
    [-] playwright: npx/stdio - no port to probe
  Legacy Systemd:
    none (ok)
  Status: Partial

Tier 4 (CI/CD):
  [x] cicd.yml: configured
  [x] Framework detected: python (uv)
  [x] Makefile: 8 targets
  [ ] CI pipeline: no workflows found
  [ ] Dockerfile: not found
  Status: Partial

Tier 5 (Codex):
  [x] Codex CLI: 0.137.0
  [x] codex doctor: passed
  [x] OpenAI API key: set in environment
  [x] Codex MCP: second-opinion registered
  [x] Codex MCP: playwright registered
  [x] Codex commands: 4/4 available
  Status: Complete

---------------------------------
Current Level: Tier 2 (Standard)
MCP wiring: second-opinion external via .mcp.json (no CPP container runtime)
Missing: Shell prompt, CI pipeline, Dockerfile

Run /cpp:init to complete setup
=================================
```

## Notes

- `[x]` = Fully installed
- `[~]` = Partially installed or needs attention
- `[ ]` = Not installed
- Symlinks are preferred over copied files for easier updates
