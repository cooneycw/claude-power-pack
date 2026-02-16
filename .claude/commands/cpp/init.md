---
description: Interactive setup wizard for Claude Power Pack
allowed-tools: Bash(mkdir:*), Bash(ln:*), Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(cat:*), Bash(cp:*), Bash(uv:*), Bash(claude mcp list:*), Bash(claude mcp add:*), Bash(sudo systemctl:*), Bash(systemctl:*), Bash(command -v:*)
---

# Claude Power Pack Setup Wizard

Interactive wizard to install and configure Claude Power Pack components.

---

## Step 1: Locate CPP Source

Find where claude-power-pack is installed:

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

## Step 2: Detect Current State

Check what's already installed (same logic as `/cpp:status`):

```bash
# Tier 1 checks
COMMANDS_INSTALLED=false
SKILLS_INSTALLED=false
[ -L ".claude/commands" ] || [ -d ".claude/commands" ] && COMMANDS_INSTALLED=true
[ -L ".claude/skills" ] || [ -d ".claude/skills" ] && SKILLS_INSTALLED=true

# Tier 2 checks
SCRIPTS_COUNT=$(ls ~/.claude/scripts/*.sh 2>/dev/null | wc -l)
HOOKS_EXIST=false
[ -f ".claude/hooks.json" ] && HOOKS_EXIST=true

# Tier 3 checks
UV_INSTALLED=false
command -v uv &>/dev/null && UV_INSTALLED=true

# Check for pyproject.toml in each MCP server
MCP_PROJECTS=""
for server in mcp-second-opinion mcp-playwright-persistent; do
  [ -f "$CPP_DIR/$server/pyproject.toml" ] && MCP_PROJECTS="$MCP_PROJECTS $server"
done

MCP_SERVERS=""
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
for server in second-opinion playwright-persistent; do
  echo "$MCP_LIST" | grep -q "$server" && MCP_SERVERS="$MCP_SERVERS $server"
done
```

Report current state to user.

---

## Step 3: Select Installation Tier

Ask the user which tier they want to install using the AskUserQuestion tool:

**Options:**

| Tier | Name | Description |
|------|------|-------------|
| 1 | **Minimal** | Commands + Skills symlinks only |
| 2 | **Standard** | + Scripts, hooks, shell prompt |
| 3 | **Full** | + MCP servers (uv, API keys) |

Default recommendation: **Standard** for most users, **Full** for MCP-powered workflows.

---

## Step 3b: Permission Profile (Tier 2+)

**Only show this step if user selected Tier 2 or Tier 3.**

Claude Code prompts "Allow?" before running tools. You can auto-approve safe operations to reduce interruptions while blocking dangerous commands.

Ask the user which permission profile they want using AskUserQuestion:

**Options:**

| Profile | Description | Best For |
|---------|-------------|----------|
| **Cautious** | Minimal auto-approvals (Read only) | New users, shared machines |
| **Standard** | Common dev tools auto-approved (Recommended) | Most developers |
| **Trusted** | Broad auto-approvals, rely on hooks for safety | Solo developers, power users |
| **Custom** | Choose individual permission categories | Fine-grained control |

### Profile Definitions

**Cautious Profile:**
```json
{
  "permissions": {
    "allow": ["Read", "Glob", "Grep"],
    "deny": ["Bash(rm -rf:*)", "Bash(git push --force:*)"]
  }
}
```

**Standard Profile (Default):**
```json
{
  "permissions": {
    "allow": [
      "Read", "Glob", "Grep",
      "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
      "Bash(git add:*)", "Bash(git commit:*)", "Bash(git branch:*)",
      "Bash(git checkout:*)", "Bash(git stash:*)", "Bash(git fetch:*)",
      "Bash(ls:*)", "Bash(pwd)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
      "Bash(npm:*)", "Bash(npx:*)", "Bash(uv:*)", "Bash(pip:*)", "Bash(yarn:*)",
      "Bash(python:*)", "Bash(node:*)",
      "Bash(gh issue:*)", "Bash(gh pr list:*)", "Bash(gh pr view:*)",
      "WebFetch(domain:github.com)", "WebFetch(domain:docs.python.org)",
      "Skill(project-next)", "Skill(project-lite)"
    ],
    "deny": [
      "Bash(rm -rf:*)", "Bash(git push --force:*)", "Bash(git reset --hard:*)",
      "Bash(sudo:*)", "Bash(chmod -R:*)"
    ]
  }
}
```

**Trusted Profile:**
```json
{
  "permissions": {
    "allow": [
      "Read", "Glob", "Grep", "Write",
      "Bash(git:*)", "Bash(gh:*)",
      "Bash(npm:*)", "Bash(npx:*)", "Bash(uv:*)", "Bash(pip:*)", "Bash(yarn:*)",
      "Bash(python:*)", "Bash(node:*)",
      "Bash(ls:*)", "Bash(cat:*)", "Bash(mkdir:*)", "Bash(cp:*)", "Bash(mv:*)",
      "Bash(curl:*)", "Bash(wget:*)",
      "WebFetch", "WebSearch",
      "Skill(*)",
      "mcp__second-opinion__*", "mcp__playwright-persistent__*"
    ],
    "deny": [
      "Bash(rm -rf /:*)", "Bash(rm -rf ~:*)", "Bash(rm -rf /home:*)",
      "Bash(git push --force origin main:*)", "Bash(git push --force origin master:*)",
      "Bash(sudo rm:*)", "Bash(mkfs:*)", "Bash(dd if=:*)"
    ]
  }
}
```

### Custom Mode Categories

If user selects "Custom", ask which categories to enable using multi-select:

| Category | Permissions | Default |
|----------|-------------|---------|
| **File Reading** | Read, Glob, Grep | ✓ Enabled |
| **Git (safe)** | git status/diff/log/add/commit/branch/checkout/stash/fetch | ✓ Enabled |
| **Git (all)** | git push/pull/merge/rebase | ○ Disabled |
| **Package Managers** | npm, npx, uv, pip, yarn | ✓ Enabled |
| **Runtimes** | python, node | ✓ Enabled |
| **GitHub CLI (read)** | gh issue, gh pr list, gh pr view | ✓ Enabled |
| **GitHub CLI (write)** | gh pr create, gh pr merge | ○ Disabled |
| **File Writing** | Write tool | ○ Disabled |
| **Web Access** | WebFetch, WebSearch | ○ Disabled |
| **MCP Tools** | All installed MCP servers | ○ Disabled |
| **Skills** | Auto-activate all skills | ✓ Enabled |

### Security Notes

- **Deny rules are always enforced** - Dangerous patterns blocked regardless of profile
- **Hooks provide second layer** - PreToolUse hook validates commands even if auto-approved
- **Trusted profile requires Tier 2** - Won't offer Trusted unless hooks are enabled

---

## Step 4: Show Disclosure

**CRITICAL**: Before making ANY changes, show the user exactly what will be modified.

### Tier 1 Disclosure (Minimal)

```
=== Tier 1: Minimal Installation ===

This will create the following symlinks in your project:

  Symlinks:
    • .claude/commands → {CPP_DIR}/.claude/commands
    • .claude/skills → {CPP_DIR}/.claude/skills

  Disk usage: ~0 MB (symlinks only)

  To undo:
    rm .claude/commands .claude/skills

Proceed? [y/N]
```

### Tier 2 Disclosure (Standard)

```
=== Tier 2: Standard Installation ===

This will make the following changes:

  [Tier 1 - Symlinks]
    • .claude/commands → {CPP_DIR}/.claude/commands
    • .claude/skills → {CPP_DIR}/.claude/skills

  [Tier 2 - Scripts] (~/.claude/scripts/)
    • prompt-context.sh       - Shell prompt worktree context
    • worktree-remove.sh      - Safe worktree cleanup
    • secrets-mask.sh         - Output masking filter
    • hook-mask-output.sh     - PostToolUse secret masking
    • hook-validate-command.sh - PreToolUse safety checks

  [Tier 2 - Hooks] (.claude/hooks.json)
    • PreToolUse: block dangerous commands
    • PostToolUse: mask secrets in output

  [Tier 2 - Shell Prompt] (optional)
    • Add worktree context to PS1: [CPP #42] ~/project $

  [Tier 2 - Makefile] (optional)
    • Create starter Makefile with lint, test, deploy targets
    • Used by /flow:finish and /flow:deploy

  Disk usage: ~50 KB

  To undo:
    rm .claude/commands .claude/skills
    rm ~/.claude/scripts/*.sh
    rm .claude/hooks.json
    # Remove PS1 line from ~/.bashrc or ~/.zshrc

Proceed? [y/N]
```

### Tier 3 Disclosure (Full)

```
=== Tier 3: Full Installation ===

This will make the following changes:

  [Tier 1 + 2 - All Standard components]
    (see above)

  [Tier 3 - Python Virtual Environments (uv)] (~150 MB total)
    • mcp-second-opinion/.venv  - Gemini/OpenAI code review (~80 MB)
    • mcp-playwright-persistent/.venv - Browser automation (~70 MB)

  [Tier 3 - Playwright Browsers]
    • Chromium (~150 MB, installed via `uv run playwright install chromium`)

  [Tier 3 - API Keys Required]
    • GEMINI_API_KEY - For mcp-second-opinion (get from https://aistudio.google.com/apikey)
    • OPENAI_API_KEY - Optional, for multi-model comparison

  [Tier 3 - MCP Servers] (added to Claude Code)
    • second-opinion        - port 8080
    • playwright-persistent - port 8081

  [Tier 3 - Configuration Files]
    • mcp-second-opinion/.env

  Disk usage: ~150 MB (venvs) + 150 MB (Chromium)
  Ports used: 8080, 8081

  To undo:
    # Tier 1+2 cleanup (see above)
    rm -rf {CPP_DIR}/mcp-second-opinion/.venv
    rm -rf {CPP_DIR}/mcp-playwright-persistent/.venv
    claude mcp remove second-opinion
    claude mcp remove playwright-persistent

Proceed? [y/N]
```

---

## Step 5: Execute Installation

Execute only the components that aren't already installed.

### Tier 1 Execution

```bash
# Create .claude directory if needed
mkdir -p .claude

# Symlink commands (skip if exists)
if [ ! -L ".claude/commands" ] && [ ! -d ".claude/commands" ]; then
  ln -sf "$CPP_DIR/.claude/commands" .claude/commands
  echo "✓ Commands symlinked"
else
  echo "→ Commands already installed (skipped)"
fi

# Symlink skills (skip if exists)
if [ ! -L ".claude/skills" ] && [ ! -d ".claude/skills" ]; then
  ln -sf "$CPP_DIR/.claude/skills" .claude/skills
  echo "✓ Skills symlinked"
else
  echo "→ Skills already installed (skipped)"
fi
```

### Tier 2 Execution

```bash
# Create scripts directory
mkdir -p ~/.claude/scripts

# Symlink all scripts
for script in "$CPP_DIR"/scripts/*.sh; do
  name=$(basename "$script")
  if [ ! -L ~/.claude/scripts/"$name" ]; then
    ln -sf "$script" ~/.claude/scripts/"$name"
    echo "✓ $name installed"
  else
    echo "→ $name already installed (skipped)"
  fi
done

# Copy hooks.json if not exists
if [ ! -f ".claude/hooks.json" ]; then
  cp "$CPP_DIR/.claude/hooks.json" .claude/hooks.json
  echo "✓ Hooks configured"
else
  echo "→ Hooks already configured (skipped)"
  echo "  Note: You may want to merge with $CPP_DIR/.claude/hooks.json"
fi
```

**Permission Profile Configuration**

Based on the profile selected in Step 3b, generate `.claude/settings.local.json`:

```bash
# Generate settings.local.json based on selected profile
# (The profile JSON content is determined by user selection in Step 3b)

if [ ! -f ".claude/settings.local.json" ]; then
  # Write the selected profile to settings.local.json
  cat > .claude/settings.local.json << 'SETTINGS_EOF'
{PROFILE_JSON_CONTENT}
SETTINGS_EOF
  echo "✓ Permission profile configured: {PROFILE_NAME}"
else
  echo "→ settings.local.json exists (skipped)"
  echo "  To reconfigure, delete .claude/settings.local.json and run /cpp:init"
fi

# Add settings.local.json to .gitignore if not already there
if [ -f ".gitignore" ]; then
  if ! grep -q "settings.local.json" .gitignore; then
    echo "" >> .gitignore
    echo "# Claude Code local settings (contains user-specific permissions)" >> .gitignore
    echo ".claude/settings.local.json" >> .gitignore
    echo "✓ Added settings.local.json to .gitignore"
  fi
fi
```

**Profile JSON Templates:**

- **Cautious**: `{"permissions":{"allow":["Read","Glob","Grep"],"deny":["Bash(rm -rf:*)","Bash(git push --force:*)"]}}`

- **Standard**: See Step 3b for full JSON

- **Trusted**: See Step 3b for full JSON

- **Custom**: Build JSON from selected categories

**Shell Prompt Integration (Optional)**

Ask the user if they want shell prompt integration:

```
Would you like to add worktree context to your shell prompt?

This shows [PREFIX #ISSUE] before your prompt, e.g.:
  [CPP #42] ~/Projects/claude-power-pack-issue-42 $

Add to ~/.bashrc? [y/N]
```

If yes:
```bash
# Add to bashrc
echo '' >> ~/.bashrc
echo '# Claude Power Pack - worktree context in prompt' >> ~/.bashrc
echo 'export PS1='\''$(~/.claude/scripts/prompt-context.sh)\w $ '\''' >> ~/.bashrc
echo "✓ Shell prompt configured (restart shell or source ~/.bashrc)"
```

**Makefile Setup (Optional)**

If no Makefile exists in the project root, offer to create one from the template:

```
=== Optional: Makefile ===

The /flow commands use Makefile targets for quality gates and deployment:
  /flow:finish  → runs `make lint` and `make test`
  /flow:deploy  → runs `make deploy`

Create a starter Makefile? [y/N]
```

If yes:
```bash
if [ ! -f "Makefile" ]; then
  cp "$CPP_DIR/templates/Makefile.example" Makefile
  echo "✓ Makefile created from template"
  echo "  Edit targets to match your project's commands"
else
  echo "→ Makefile already exists (skipped)"
fi
```

If no:
```bash
echo "→ Makefile creation skipped"
echo "  You can copy it later: cp $CPP_DIR/templates/Makefile.example Makefile"
```

**Happy CLI Installation (Optional)**

Ask the user if they want to install happy-cli:

```
=== Optional: Happy CLI ===

Happy CLI is an AI coding assistant that complements Claude Code.
https://github.com/slopus/happy-cli

Install happy-cli? [y/N]
```

If yes:
```bash
# Check if already installed
if command -v happy &>/dev/null; then
  echo "→ happy-cli already installed (skipped)"
  happy --version 2>&1 | head -1
else
  echo "Installing happy-cli..."
  npm install -g happy-coder
  if command -v happy &>/dev/null; then
    echo "✓ happy-cli installed"
    echo "  Run 'happy' to complete onboarding"
  else
    echo "⚠ Installation failed - check npm permissions"
    echo "  Try: sudo npm install -g happy-coder"
  fi
fi
echo "✓ /happy-check command available (verify version updates)"
```

If no:
```bash
echo "→ Happy CLI installation skipped"
```

### Tier 3 Execution

#### 3a. Install uv and Sync Dependencies

```bash
# Check if uv is installed
if ! command -v uv &>/dev/null; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  echo "✓ uv installed"
else
  echo "→ uv already installed ($(uv --version))"
fi

# Sync dependencies for each MCP server
for server in mcp-second-opinion mcp-playwright-persistent; do
  if [ ! -d "$CPP_DIR/$server/.venv" ]; then
    echo "Creating virtual environment for $server..."
    cd "$CPP_DIR/$server"
    uv sync
    echo "✓ $server venv created"
  else
    echo "→ $server venv exists (skipped)"
  fi
done
```

#### 3b. Playwright Browser

```bash
# Install Chromium for Playwright
echo "Installing Playwright Chromium browser..."
cd "$CPP_DIR/mcp-playwright-persistent"
uv run playwright install chromium
echo "✓ Chromium browser installed"
```

#### 3c. API Key Configuration

Prompt the user for API keys:

```
=== API Key Configuration ===

MCP Second Opinion requires a Gemini API key for code review functionality.

Get your API key from: https://aistudio.google.com/apikey

Enter your GEMINI_API_KEY (or press Enter to skip):
```

If provided, write to .env:
```bash
cd "$CPP_DIR/mcp-second-opinion"
cat > .env << EOF
GEMINI_API_KEY=$GEMINI_API_KEY
MCP_SERVER_HOST=127.0.0.1
MCP_SERVER_PORT=8080
ENABLE_CONTEXT_CACHING=true
CACHE_TTL_MINUTES=60
EOF
echo "✓ mcp-second-opinion/.env configured"
```

Optional: Ask for OPENAI_API_KEY for multi-model comparison.

#### 3d. Register MCP Servers

```bash
# Add MCP servers to Claude Code
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")

if ! echo "$MCP_LIST" | grep -q "second-opinion"; then
  claude mcp add second-opinion --transport sse --url http://127.0.0.1:8080/sse
  echo "✓ second-opinion MCP registered"
else
  echo "→ second-opinion MCP already registered (skipped)"
fi

if ! echo "$MCP_LIST" | grep -q "playwright-persistent"; then
  claude mcp add playwright-persistent --transport sse --url http://127.0.0.1:8081/sse
  echo "✓ playwright-persistent MCP registered"
else
  echo "→ playwright-persistent MCP already registered (skipped)"
fi
```

---

## Step 6: Systemd Services (Optional)

After Tier 3 completes, offer systemd setup:

```
=== Optional: Systemd Services ===

Would you like to install systemd services for auto-start on boot?

This will:
  • Create /etc/systemd/system/mcp-second-opinion.service
  • Enable service to start automatically on boot

Note: You'll need to manually start MCP servers until reboot,
or run: sudo systemctl start mcp-second-opinion

Install systemd services? [y/N]
```

If yes:
```bash
# Copy service files
sudo cp "$CPP_DIR/mcp-second-opinion/deploy/mcp-second-opinion.service" /etc/systemd/system/

# Update paths in service files (replace placeholder user)
CURRENT_USER=$(whoami)
sudo sed -i "s/cooneycw/$CURRENT_USER/g" /etc/systemd/system/mcp-second-opinion.service

# Reload and enable
sudo systemctl daemon-reload
sudo systemctl enable mcp-second-opinion

echo "✓ Systemd services installed and enabled"
echo ""
echo "To start now: sudo systemctl start mcp-second-opinion"
echo "To check status: systemctl status mcp-second-opinion"
```

---

## Step 7: Installation Summary

```
=================================
CPP Installation Complete!
=================================

Installed:
  ✓ Tier 1: Commands + Skills symlinked
  ✓ Tier 2: Scripts, hooks, shell prompt
  ✓ Tier 3: uv, MCP servers, API keys

Permission Profile: {PROFILE_NAME}
  Auto-approved: {AUTO_APPROVE_SUMMARY}
  Blocked: rm -rf, git push --force, sudo (destructive)
  Settings: .claude/settings.local.json

MCP Servers:
  • second-opinion (port 8080) - Gemini/OpenAI code review
  • playwright-persistent (port 8081) - Browser automation

Next Steps:
  1. Start MCP servers (if not using systemd):
     cd {CPP_DIR}/mcp-second-opinion && ./start-server.sh &
     cd {CPP_DIR}/mcp-playwright-persistent && ./start-server.sh &

  2. Restart your shell to apply prompt changes:
     source ~/.bashrc

  3. Verify installation:
     /cpp:status

  4. Try the commands:
     /project-next    - See what to work on
     /spec:help       - Spec-driven development
     /github:help     - Issue management

Change Permissions Later:
  • Edit .claude/settings.local.json directly
  • Or delete it and run /cpp:init to reconfigure

Documentation:
  • CLAUDE.md - Full reference
  • ISSUE_DRIVEN_DEVELOPMENT.md - IDD workflow
  • /load-best-practices - Community tips

=================================
```

---

## Error Handling

### uv Not Installed
```
⚠ uv not found. Tier 3 requires uv for MCP server environments.

Installing uv automatically...
  curl -LsSf https://astral.sh/uv/install.sh | sh

If automatic installation fails:
  1. Install manually: https://docs.astral.sh/uv/
  2. Or skip Tier 3 and use Standard tier only

Skip Tier 3 components? [Y/n]
```

### API Key Not Provided
```
⚠ No GEMINI_API_KEY provided.

MCP Second Opinion will not work without an API key.
You can configure it later by editing: {CPP_DIR}/mcp-second-opinion/.env

Continue? [Y/n]
```

---

## Step 8: Optional — Redis Coordination (Teams Only)

After the main installation completes, offer this add-on:

```
=== Optional: Redis Coordination ===

Do you run multiple concurrent Claude Code sessions that need to coordinate?
(e.g., team development, parallel issue work with shared resources)

Most users do NOT need this — the /flow workflow is stateless and conflict-free.

Install Redis Coordination? [y/N]
```

If yes, install from `extras/redis-coordination/`:

```bash
# Install Redis
if ! redis-cli ping 2>/dev/null | grep -q PONG; then
  echo "Installing Redis..."
  sudo apt install -y redis-server
  sudo systemctl enable redis-server
  sudo systemctl start redis-server
fi

# Symlink coordination scripts
for script in "$CPP_DIR"/extras/redis-coordination/scripts/*.sh; do
  name=$(basename "$script")
  ln -sf "$script" ~/.claude/scripts/"$name"
  echo "✓ $name installed"
done

# Setup MCP Coordination server
cd "$CPP_DIR/extras/redis-coordination/mcp-server"
uv sync

# Create .env
cat > .env << EOF
REDIS_URL=redis://localhost:6379/0
SERVER_PORT=8082
LOG_LEVEL=INFO
DEFAULT_LOCK_TIMEOUT=300
HEARTBEAT_TTL=300
EOF

# Register MCP server
claude mcp add coordination --transport sse --url http://127.0.0.1:8082/sse

echo "✓ Redis Coordination installed"
echo "  Start: cd $CPP_DIR/extras/redis-coordination/mcp-server && ./start-server.sh"
echo "  Docs:  $CPP_DIR/extras/redis-coordination/README.md"
```

If no:
```bash
echo "→ Redis Coordination skipped (not needed for solo development)"
```

---

## Notes

- This wizard is **idempotent** - safe to run multiple times
- Already-installed components are skipped with a message
- Symlinks are preferred over copies for easier updates
- Run `/cpp:status` anytime to check installation state
