---
description: Update Claude Power Pack to the latest version
allowed-tools: Bash(git:*), Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(cat:*), Bash(uv:*), Bash(claude mcp list:*), Bash(sudo systemctl:*), Bash(systemctl:*), Bash(command -v:*), Bash(ln:*), Bash(mkdir:*), Bash(cp:*)
---

# Claude Power Pack Update

Update CPP to the latest version and optionally upgrade installation tier.

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

# Get current state
CURRENT_COMMIT=$(git rev-parse --short HEAD)
CURRENT_TAG=$(git describe --tags --always 2>/dev/null)
CURRENT_BRANCH=$(git branch --show-current)

echo "Current: $CURRENT_TAG ($CURRENT_COMMIT) on $CURRENT_BRANCH"

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
NEW_TAG=$(git describe --tags --always 2>/dev/null)
echo ""
echo "Updated: $CURRENT_TAG → $NEW_TAG ($NEW_COMMIT)"
```

---

## Step 4: Update Dependencies (Tier 3)

If MCP server venvs exist, sync dependencies to pick up any new packages:

```bash
cd "$CPP_DIR"

for server in mcp-second-opinion mcp-playwright-persistent; do
  if [ -d "$server/.venv" ]; then
    echo ""
    echo "Syncing dependencies for $server..."
    cd "$CPP_DIR/$server"
    uv sync
    echo "✓ $server dependencies updated"
  fi
done
```

---

## Step 5: Restart MCP Servers (if running via systemd)

```bash
for service in mcp-second-opinion mcp-playwright-persistent; do
  if systemctl is-active $service &>/dev/null; then
    echo ""
    echo "Restarting $service..."
    sudo systemctl restart $service
    echo "✓ $service restarted"
  fi
done
```

If servers are not running via systemd, remind the user to restart manually.

---

## Step 6: Detect Current Installation Tier

Determine the user's current tier level so we can offer upgrades:

```bash
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

## Step 7: Offer Tier Upgrade

If the user is not at the highest tier, ask if they want to upgrade using AskUserQuestion:

**Only show this if current tier < 3.**

```
Your current installation: Tier {TIER}

Available upgrades:
  Tier 1 (Minimal): Commands + Skills symlinks
  Tier 2 (Standard): + Scripts, hooks, shell prompt, permission profiles
  Tier 3 (Full): + MCP servers (uv, API keys, systemd)

Would you like to upgrade to a higher tier?
```

**Options:**
- **Keep current tier** - No changes beyond the git pull
- **Upgrade to Tier 2** (if currently Tier 0 or 1)
- **Upgrade to Tier 3** (if currently below Tier 3)

If upgrading, follow the same installation steps as `/cpp:init` for the new tier only.

---

## Step 8: Update Summary

```
=================================
CPP Update Complete
=================================

Version: {OLD_TAG} → {NEW_TAG}
Branch:  {BRANCH}
Tier:    {TIER} {(upgraded from X if applicable)}

Changes pulled:
  {list of new commits}

Dependencies:
  {synced servers or "No MCP venvs to update"}

MCP Servers:
  {restarted services or "Not running via systemd"}

Run /cpp:status for full installation details.
=================================
```

---

## Notes

- This command is safe to run repeatedly (idempotent)
- Uncommitted changes in CPP are auto-stashed before pull
- Symlinked commands/skills are automatically updated by the git pull
- MCP server dependencies are synced if venvs exist
- Running systemd services are automatically restarted
- Use `/cpp:init` instead if you need the full interactive setup wizard
