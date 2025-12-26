---
description: Interactive setup wizard for Claude Power Pack
allowed-tools: Bash(mkdir:*), Bash(ln:*), Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(cat:*), Bash(cp:*), Bash(conda env list:*), Bash(conda env create:*), Bash(claude mcp list:*), Bash(claude mcp add:*), Bash(redis-cli:*), Bash(sudo apt install:*), Bash(sudo systemctl:*), Bash(systemctl:*), Bash(playwright install:*), Bash(source:*)
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
REDIS_RUNNING=false
redis-cli ping 2>/dev/null | grep -q PONG && REDIS_RUNNING=true

CONDA_ENVS=""
for env in mcp-second-opinion mcp-coordination mcp-playwright; do
  conda env list 2>/dev/null | grep -q "^$env " && CONDA_ENVS="$CONDA_ENVS $env"
done

MCP_SERVERS=""
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
for server in second-opinion coordination playwright-persistent; do
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
| 2 | **Standard** | + Scripts, hooks, shell prompt, session coordination |
| 3 | **Full** | + MCP servers (Redis, conda envs, API keys) |

Default recommendation: **Standard** for most users, **Full** for multi-session workflows.

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
    • prompt-context.sh      - Shell prompt worktree context
    • session-register.sh    - Session lifecycle management
    • session-lock.sh        - Distributed locking (file-based)
    • session-heartbeat.sh   - Activity tracking
    • pytest-locked.sh       - Coordinated test execution
    • conda-detect.sh        - Environment detection
    • conda-activate.sh      - Activation helper
    • secrets-mask.sh        - Output masking filter
    • hook-mask-output.sh    - PostToolUse secret masking
    • hook-validate-command.sh - PreToolUse safety checks
    • worktree-remove.sh     - Safe worktree cleanup

  [Tier 2 - Hooks] (.claude/hooks.json)
    • SessionStart: conda detection, session registration
    • UserPromptSubmit: heartbeat update
    • PreToolUse: block dangerous commands
    • PostToolUse: mask secrets in output
    • Stop: pause session
    • SessionEnd: cleanup and release locks

  [Tier 2 - Shell Prompt] (optional)
    • Add worktree context to PS1: [CPP #42] ~/project $

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

  [Tier 3 - System Packages] (requires sudo)
    • redis-server (~2 MB installed)
    • Auto-enabled to start on boot

  [Tier 3 - Conda Environments] (~1.5 GB total)
    • mcp-second-opinion  - Gemini/OpenAI code review (~500 MB)
    • mcp-coordination    - Redis-backed locking (~300 MB)
    • mcp-playwright      - Browser automation (~500 MB)

  [Tier 3 - Playwright Browsers]
    • Chromium (~150 MB)

  [Tier 3 - API Keys Required]
    • GEMINI_API_KEY - For mcp-second-opinion (get from https://aistudio.google.com/apikey)
    • OPENAI_API_KEY - Optional, for multi-model comparison

  [Tier 3 - MCP Servers] (added to Claude Code)
    • second-opinion      - port 8080
    • coordination        - port 8082
    • playwright-persistent - port 8081

  [Tier 3 - Configuration Files]
    • mcp-second-opinion/.env
    • mcp-coordination/.env

  Disk usage: ~1.7 GB
  Ports used: 8080, 8081, 8082

  To undo:
    # Tier 1+2 cleanup (see above)
    sudo apt remove redis-server
    conda env remove -n mcp-second-opinion
    conda env remove -n mcp-coordination
    conda env remove -n mcp-playwright
    claude mcp remove second-opinion
    claude mcp remove coordination
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

### Tier 3 Execution

#### 3a. Redis Installation

```bash
# Check if Redis is running
if redis-cli ping 2>/dev/null | grep -q PONG; then
  echo "→ Redis already running (skipped)"
else
  echo "Installing Redis..."
  sudo apt install -y redis-server
  sudo systemctl enable redis-server
  sudo systemctl start redis-server

  # Verify
  if redis-cli ping | grep -q PONG; then
    echo "✓ Redis installed and running"
  else
    echo "⚠ Redis installed but failed to start"
  fi
fi
```

#### 3b. Conda Environments

```bash
# mcp-second-opinion
if ! conda env list | grep -q "^mcp-second-opinion "; then
  echo "Creating mcp-second-opinion environment..."
  cd "$CPP_DIR/mcp-second-opinion"
  conda env create -f environment.yml
  echo "✓ mcp-second-opinion environment created"
else
  echo "→ mcp-second-opinion environment exists (skipped)"
fi

# mcp-coordination
if ! conda env list | grep -q "^mcp-coordination "; then
  echo "Creating mcp-coordination environment..."
  cd "$CPP_DIR/mcp-coordination"
  conda env create -f environment.yml
  echo "✓ mcp-coordination environment created"
else
  echo "→ mcp-coordination environment exists (skipped)"
fi

# mcp-playwright
if ! conda env list | grep -q "^mcp-playwright "; then
  echo "Creating mcp-playwright environment..."
  cd "$CPP_DIR/mcp-playwright-persistent"
  conda env create -f environment.yml
  echo "✓ mcp-playwright environment created"
else
  echo "→ mcp-playwright environment exists (skipped)"
fi
```

#### 3c. Playwright Browser

```bash
# Install Chromium for Playwright
echo "Installing Playwright Chromium browser..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate mcp-playwright
playwright install chromium
echo "✓ Chromium browser installed"
```

#### 3d. API Key Configuration

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

Create .env for coordination:
```bash
cd "$CPP_DIR/mcp-coordination"
cat > .env << EOF
REDIS_URL=redis://localhost:6379/0
SERVER_PORT=8082
LOG_LEVEL=INFO
DEFAULT_LOCK_TIMEOUT=300
HEARTBEAT_TTL=300
EOF
echo "✓ mcp-coordination/.env configured"
```

#### 3e. Register MCP Servers

```bash
# Add MCP servers to Claude Code
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")

if ! echo "$MCP_LIST" | grep -q "second-opinion"; then
  claude mcp add second-opinion --transport sse --url http://127.0.0.1:8080/sse
  echo "✓ second-opinion MCP registered"
else
  echo "→ second-opinion MCP already registered (skipped)"
fi

if ! echo "$MCP_LIST" | grep -q "coordination"; then
  claude mcp add coordination --transport sse --url http://127.0.0.1:8082/sse
  echo "✓ coordination MCP registered"
else
  echo "→ coordination MCP already registered (skipped)"
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
  • Create /etc/systemd/system/mcp-coordination.service
  • Enable services to start automatically on boot

Note: You'll need to manually start MCP servers until reboot,
or run: sudo systemctl start mcp-second-opinion mcp-coordination

Install systemd services? [y/N]
```

If yes:
```bash
# Copy service files
sudo cp "$CPP_DIR/mcp-second-opinion/deploy/mcp-second-opinion.service" /etc/systemd/system/
sudo cp "$CPP_DIR/mcp-coordination/deploy/mcp-coordination.service" /etc/systemd/system/

# Update paths in service files (replace placeholder user)
CURRENT_USER=$(whoami)
sudo sed -i "s/cooneycw/$CURRENT_USER/g" /etc/systemd/system/mcp-second-opinion.service
sudo sed -i "s/cooneycw/$CURRENT_USER/g" /etc/systemd/system/mcp-coordination.service

# Reload and enable
sudo systemctl daemon-reload
sudo systemctl enable mcp-second-opinion mcp-coordination

echo "✓ Systemd services installed and enabled"
echo ""
echo "To start now: sudo systemctl start mcp-second-opinion mcp-coordination"
echo "To check status: systemctl status mcp-second-opinion mcp-coordination"
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
  ✓ Tier 3: Redis, MCP servers, API keys

MCP Servers:
  • second-opinion (port 8080) - Gemini code review
  • coordination (port 8082) - Distributed locking
  • playwright-persistent (port 8081) - Browser automation

Next Steps:
  1. Start MCP servers (if not using systemd):
     cd {CPP_DIR}/mcp-second-opinion && ./start-server.sh &
     cd {CPP_DIR}/mcp-coordination && ./start-server.sh &
     cd {CPP_DIR}/mcp-playwright-persistent && ./start-server.sh &

  2. Restart your shell to apply prompt changes:
     source ~/.bashrc

  3. Verify installation:
     /cpp:status

  4. Try the commands:
     /project-next    - See what to work on
     /spec:help       - Spec-driven development
     /github:help     - Issue management

Documentation:
  • CLAUDE.md - Full reference
  • ISSUE_DRIVEN_DEVELOPMENT.md - IDD workflow
  • /load-best-practices - Community tips

=================================
```

---

## Error Handling

### Conda Not Installed
```
⚠ Conda not found. Tier 3 requires conda for MCP server environments.

Options:
  1. Install Miniconda: https://docs.conda.io/en/latest/miniconda.html
  2. Skip Tier 3 and use Standard tier only

Skip Tier 3 components? [Y/n]
```

### Redis Installation Fails
```
⚠ Redis installation failed.

The coordination MCP server can still work with file-based locking,
but Redis provides better performance for multi-session coordination.

Continue without Redis? [Y/n]
```

### API Key Not Provided
```
⚠ No GEMINI_API_KEY provided.

MCP Second Opinion will not work without an API key.
You can configure it later by editing: {CPP_DIR}/mcp-second-opinion/.env

Continue? [Y/n]
```

---

## Notes

- This wizard is **idempotent** - safe to run multiple times
- Already-installed components are skipped with a message
- Symlinks are preferred over copies for easier updates
- Run `/cpp:status` anytime to check installation state
