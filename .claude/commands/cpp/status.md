---
description: Check Claude Power Pack installation state
allowed-tools: Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(uv:*), Bash(claude mcp list:*), Bash(systemctl:*)
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
    echo "  [x] $server"
  else
    echo "  [ ] $server"
  fi
done

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
  [ ] Systemd: not installed
  Status: Partial

---------------------------------
Current Level: Tier 2 (Standard)
Missing: Shell prompt, mcp-playwright-persistent, systemd

Run /cpp:init to complete setup
=================================
```

## Notes

- `[x]` = Fully installed
- `[~]` = Partially installed or needs attention
- `[ ]` = Not installed
- Symlinks are preferred over copied files for easier updates
