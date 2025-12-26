---
description: Check Claude Power Pack installation state
allowed-tools: Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(conda env list:*), Bash(claude mcp list:*), Bash(systemctl:*), Bash(redis-cli:*)
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
for script in prompt-context.sh session-register.sh session-lock.sh session-heartbeat.sh pytest-locked.sh conda-detect.sh secrets-mask.sh hook-mask-output.sh hook-validate-command.sh worktree-remove.sh; do
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

## Step 4: Check Tier 3 (Full)

Check MCP servers and dependencies:

```bash
# Check Redis
if command -v redis-cli &>/dev/null && redis-cli ping 2>/dev/null | grep -q PONG; then
  echo "[x] Redis: running"
elif command -v redis-cli &>/dev/null; then
  echo "[~] Redis: installed but not running"
else
  echo "[ ] Redis: not installed"
fi

# Check conda environments
echo ""
echo "Conda Environments:"
for env in mcp-second-opinion mcp-coordination mcp-playwright; do
  if conda env list 2>/dev/null | grep -q "^$env "; then
    echo "  [x] $env"
  else
    echo "  [ ] $env"
  fi
done

# Check MCP servers registered
echo ""
echo "MCP Servers (Claude Code):"
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
for server in second-opinion coordination playwright-persistent; do
  if echo "$MCP_LIST" | grep -q "$server"; then
    echo "  [x] $server"
  else
    echo "  [ ] $server"
  fi
done

# Check systemd services
echo ""
echo "Systemd Services:"
for service in mcp-second-opinion mcp-coordination mcp-playwright; do
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

## Step 5: Summary

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
  [x] Scripts: 10/10 installed
  [x] Hooks: 5 hooks configured
  [ ] Shell prompt: not configured
  Status: Partial

Tier 3 (Full):
  [x] Redis: running
  [x] mcp-second-opinion: env + registered
  [ ] mcp-coordination: env missing
  [ ] mcp-playwright: not configured
  [ ] Systemd: not installed
  Status: Partial

---------------------------------
Current Level: Tier 2 (Standard)
Missing: Shell prompt, mcp-coordination, mcp-playwright, systemd

Run /cpp:init to complete setup
=================================
```

## Notes

- `[x]` = Fully installed
- `[~]` = Partially installed or needs attention
- `[ ]` = Not installed
- Symlinks are preferred over copied files for easier updates
