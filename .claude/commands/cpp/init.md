---
description: Interactive setup wizard for Claude Power Pack
allowed-tools: Bash(mkdir:*), Bash(ln:*), Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(cat:*), Bash(cp:*), Bash(python3:*), Bash(PYTHONPATH=*), Bash(claude mcp list:*), Bash(claude mcp add:*), Bash(command -v:*), Bash(git:*), Bash(docker:*), Bash(make:*), Bash(sleep:*), Bash(grep:*), Bash(head:*), Bash(touch:*)
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
DOCKER_INSTALLED=false
DOCKER_COMPOSE_INSTALLED=false
DOCKER_COMPOSE_FILE=false
DOCKER_CONTAINERS=""
LEGACY_SYSTEMD_UNITS=""

command -v docker &>/dev/null && DOCKER_INSTALLED=true
if [ "$DOCKER_INSTALLED" = "true" ] && docker compose version &>/dev/null; then
  DOCKER_COMPOSE_INSTALLED=true
fi
[ -f "$CPP_DIR/docker-compose.yml" ] && DOCKER_COMPOSE_FILE=true

if [ "$DOCKER_INSTALLED" = "true" ]; then
  DOCKER_CONTAINERS=$(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -E '^(aws-secrets-agent|mcp-second-opinion|mcp-playwright-persistent)$' || true)
fi

for unit in mcp-second-opinion second-opinion mcp-playwright mcp-playwright-persistent playwright-persistent mcp-evaluate evaluate mcp-coordination coordination; do
  [ -f "/etc/systemd/system/${unit}.service" ] && LEGACY_SYSTEMD_UNITS="$LEGACY_SYSTEMD_UNITS system:${unit}"
  [ -f "$HOME/.config/systemd/user/${unit}.service" ] && LEGACY_SYSTEMD_UNITS="$LEGACY_SYSTEMD_UNITS user:${unit}"
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
| 3 | **Full** | + MCP servers (Docker local builds, API keys) |
| 4 | **CI/CD** | + Build system, health checks, pipelines, containers |
| 5 | **Codex** | + Codex CLI orchestration (cross-model implementation and review) |

Default recommendation: **Standard** for most users, **Full** for MCP-powered workflows, **CI/CD** for projects needing build automation, **Codex** for cross-model implementation workflows.

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

  [Tier 3 - Docker Runtime]
    • Requires Docker Engine or Docker Desktop
    • Requires Docker Compose v2 (`docker compose`)
    • Builds local images with `make docker-refresh PROFILE="core browser"`
    • Verifies container health with `make docker-health PROFILE="core browser"`

  [Tier 3 - API Keys] (choose one method)
    Option 1 - AWS Secrets Manager (Recommended):
      • Keys stored in AWS SM, injected at startup via aws-secrets-agent sidecar
      • Only AWS credentials in .env - no application secrets on disk
      • Requires: AWS IAM permissions (secretsmanager:GetSecretValue)
      • See: docs/AWS_SECRETS_SIDECAR.md
    Option 2 - Direct .env file:
      • GEMINI_API_KEY - For mcp-second-opinion (get from https://aistudio.google.com/apikey)
      • OPENAI_API_KEY - Optional, for multi-model comparison

  [Tier 3 - Docker Containers]
    • aws-secrets-agent          - internal port 2773 (AWS SM sidecar)
    • mcp-second-opinion         - host port 8080
    • mcp-playwright-persistent  - host port 8081

  [Tier 3 - Configuration Files]
    • .env (AWS credentials + AWS_TOKEN for sidecar, or direct API keys)

  Disk usage: approximately 2-4 GB for local Docker images, browser dependencies,
  and Docker build cache (varies by host and cache state)
  Ports used: 8080, 8081; 2773 is compose-network internal only

  To undo:
    # Tier 1+2 cleanup (see above)
    cd {CPP_DIR} && make docker-down
    claude mcp remove second-opinion
    claude mcp remove playwright-persistent

Proceed? [y/N]
```

### Tier 4 Disclosure (CI/CD)

```
=== Tier 4: CI/CD Installation ===

This will make the following changes:

  [Tier 1 + 2 + 3 - All Full components]
    (see above)

  [Tier 4A - Build System]
    • Detect project framework and package manager
    • Generate/validate Makefile with standard targets
    • Create .claude/cicd.yml configuration

  [Tier 4B - Health Checks] (optional)
    • Configure endpoint health checks in cicd.yml
    • Configure process port checks

  [Tier 4C - CI/CD Pipeline] (optional)
    • Generate .github/workflows/ci.yml from Makefile targets
    • Include caching, matrix builds, secrets references

  [Tier 4D - Container] (optional)
    • Generate Dockerfile (multi-stage, framework-specific)
    • Generate docker-compose.yml
    • Generate .dockerignore

  Disk usage: ~0 MB (generated files only)

  To undo:
    # Tier 1+2+3 cleanup (see above)
    rm .claude/cicd.yml
    rm .github/workflows/ci.yml
    rm Dockerfile docker-compose.yml .dockerignore

Proceed? [y/N]
```

### Tier 5 Disclosure (Codex)

```
=== Tier 5: Codex Orchestration ===

This will make the following changes:

  [Tier 1 + 2 + 3 + 4 - All CI/CD components]
    (see above)

  [Tier 5 - Codex CLI]
    - Requires: Codex CLI (npm install -g @openai/codex)
    - Requires: OpenAI API key (codex login)
    - Installs: /codex:auto, /codex:exec, /codex:ask, /codex:status, /codex:help commands
    - Optional: Register CPP MCP servers with Codex

  Disk usage: ~0 MB (commands via symlink)

  To undo:
    # Tier 1+2+3+4 cleanup (see above)
    npm uninstall -g @openai/codex

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

**User-Level Flow Allowlist (Optional)**

The project profiles above govern ONE repo. The `/flow:*` commands also run
read-only git/gh plumbing (issue reads, worktree creation, the branch-slug
text pipeline) in EVERY repo, which prompts on every run unless the rules
exist at user level. Offer to merge the CPP allowlist template into
`~/.claude/settings.json`:

```
=== Optional: User-Level Flow Allowlist ===

/flow commands run read-only git/gh plumbing (gh issue view, git fetch,
git worktree, slug pipelines) that triggers a permission prompt on every
run, in every repo, unless allowed at user level.

Merge the CPP read-only allowlist into ~/.claude/settings.json?
(Additive and idempotent - existing settings and rules are preserved.
Rationale and caveats: templates/claude-settings-permissions.md)  [y/N]
```

If yes:

```bash
TEMPLATE="$CPP_DIR/templates/claude-settings-permissions.json"
TARGET="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"
[ -f "$TARGET" ] || echo '{}' > "$TARGET"

BEFORE=$(jq '(.permissions.allow // []) | length' "$TARGET")
jq -s '.[0].permissions.allow = (((.[0].permissions.allow // []) + .[1].permissions.allow) | unique) | .[0]' \
  "$TARGET" "$TEMPLATE" > "$TARGET.tmp" && mv "$TARGET.tmp" "$TARGET"
AFTER=$(jq '.permissions.allow | length' "$TARGET")

echo "✓ Flow allowlist merged into ~/.claude/settings.json ($((AFTER - BEFORE)) new rules, $AFTER total)"
echo "  Note: sed is allowed for the flow slug pipeline; see the template doc for the sed -i caveat."
```

If no:

```bash
echo "→ Flow allowlist skipped"
echo "  Merge later via /cpp:update, or read templates/claude-settings-permissions.md"
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

#### 3a. Docker Prerequisites and Legacy Systemd Warning

Tier 3 is Docker-only. Do not install host runtime dependencies or offer systemd
or native server startup as a fallback. Block Tier 3 if Docker or Docker Compose
is unavailable.

```bash
cd "$CPP_DIR"

if ! command -v docker &>/dev/null; then
  echo "ERROR: Tier 3 requires Docker Engine or Docker Desktop."
  echo "Install Docker, verify 'docker ps' works for your user, then rerun /cpp:init."
  echo "Docker install guide: https://docs.docker.com/get-docker/"
  echo "You can still install Tier 1 or Tier 2 without Docker."
  exit 1
fi

if ! docker compose version &>/dev/null; then
  echo "ERROR: Tier 3 requires Docker Compose v2 ('docker compose')."
  echo "Install the Docker Compose plugin or Docker Desktop, then rerun /cpp:init."
  echo "Compose install guide: https://docs.docker.com/compose/install/"
  echo "You can still install Tier 1 or Tier 2 without Docker Compose."
  exit 1
fi

if [ ! -f "$CPP_DIR/docker-compose.yml" ]; then
  echo "ERROR: docker-compose.yml not found in $CPP_DIR."
  echo "Update claude-power-pack or reclone it, then rerun /cpp:init."
  exit 1
fi

LEGACY_SYSTEMD_UNITS=""
for unit in mcp-second-opinion second-opinion mcp-playwright mcp-playwright-persistent playwright-persistent mcp-evaluate evaluate mcp-coordination coordination; do
  [ -f "/etc/systemd/system/${unit}.service" ] && LEGACY_SYSTEMD_UNITS="$LEGACY_SYSTEMD_UNITS system:${unit}"
  [ -f "$HOME/.config/systemd/user/${unit}.service" ] && LEGACY_SYSTEMD_UNITS="$LEGACY_SYSTEMD_UNITS user:${unit}"
done

if [ -n "$LEGACY_SYSTEMD_UNITS" ]; then
  echo "WARNING: legacy systemd MCP unit files were detected:"
  for item in $LEGACY_SYSTEMD_UNITS; do
    echo "  - $item"
  done
  echo ""
  echo "Run /cpp:update first to migrate or remove legacy systemd units."
  echo "/cpp:init no longer installs, starts, or manages systemd services."
fi

echo "Docker prerequisites satisfied."
```

#### 3b. API Key Configuration

Tier 3 always uses the Docker Compose stack. Do not set or branch on deployment
mode variables; the only API-key choice is AWS Secrets Manager sidecar versus
direct `.env`.

**First, detect AWS Secrets Manager sidecar availability:**

```bash
AWS_SIDECAR_AVAILABLE=false
if [ -f "$CPP_DIR/.env" ] && grep -qE '^AWS_ACCESS_KEY_ID=.+' "$CPP_DIR/.env" 2>/dev/null; then
  AWS_SIDECAR_AVAILABLE=true
fi
```

**If AWS credentials exist, offer the sidecar path (recommended):**

Ask the user which secret injection method they want using AskUserQuestion:

```
=== API Key Configuration ===

Docker deployment uses containers. Choose how MCP servers get their API keys:

  1. AWS Secrets Manager (Recommended)
     Keys stored in AWS Secrets Manager, injected at container startup
     via the aws-secrets-agent sidecar. No plaintext secrets on disk.
     Requires: AWS credentials in .env, secrets pre-created in AWS SM.
     See: docs/AWS_SECRETS_SIDECAR.md

  2. Direct .env file
     Keys written to .env and passed to containers via env_file.
     Simpler setup, but secrets are stored in plaintext on disk.

Which method? [1/2]
```

Only show this choice if `AWS_SIDECAR_AVAILABLE=true`. If
`AWS_SIDECAR_AVAILABLE=false`, skip straight to the direct `.env` path below.

**Path 1: AWS Secrets Manager sidecar**

```bash
if [ "$SECRET_METHOD" = "1" ]; then
  echo ""
  echo "=== AWS Secrets Manager Sidecar Setup ==="
  echo ""
  echo "The sidecar fetches secrets from AWS Secrets Manager at container startup."
  echo "See docs/AWS_SECRETS_SIDECAR.md for full architecture details."
  echo ""

  # Validate AWS connectivity
  echo "Validating AWS credentials and secrets..."
  cd "$CPP_DIR"
  make docker-secrets-check
  SECRETS_CHECK_RC=$?

  if [ "$SECRETS_CHECK_RC" -ne 0 ]; then
    echo ""
    echo "WARNING: AWS secrets check failed."
    echo "You can fix this later and re-run /cpp:init, or switch to direct .env."
    echo ""
    # Ask: continue with sidecar anyway, or fall back to direct .env?
    # If fall back, jump to Path 2.
  fi

  # Ensure AWS_TOKEN (SSRF protection) is set
  if ! grep -qE '^AWS_TOKEN=.+' "$CPP_DIR/.env" 2>/dev/null; then
    echo ""
    echo "AWS_TOKEN is used for SSRF protection on the sidecar."
    echo "Enter an arbitrary token string (or press Enter for a random one):"
    # If empty, generate: AWS_TOKEN=$(openssl rand -hex 16)
    echo "AWS_TOKEN=$AWS_TOKEN" >> "$CPP_DIR/.env"
    echo "Added AWS_TOKEN to .env"
  fi

  echo ""
  echo "MCP server secret mappings (from docker-compose.yml):"
  echo "  mcp-second-opinion  -> AWS_SECRET_NAME=codex_llm_apikeys"
  echo "      Expected keys: GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY"
  echo ""
  echo "To change these mappings, edit the environment section in docker-compose.yml."
  echo ""

  echo ""
  echo "Sidecar configuration complete. Containers will be refreshed after API key setup."
fi
```

**Path 2: Direct .env file**

This path runs when `AWS_SIDECAR_AVAILABLE=false` or the user chose option 2.
It still uses Docker. Do not offer native server startup as a fallback.

Prompt the user for API keys:

```
=== API Key Configuration (Direct .env) ===

MCP Second Opinion requires at least one LLM API key for code review.

Supported providers:
  - GEMINI_API_KEY   (free from https://aistudio.google.com/apikey)
  - OPENAI_API_KEY   (from https://platform.openai.com/api-keys)
  - ANTHROPIC_API_KEY (from https://console.anthropic.com/settings/keys)

Enter your GEMINI_API_KEY (or press Enter to skip):
```

**Write keys to the Docker `.env` file without removing existing AWS entries:**

```bash
ENV_FILE="$CPP_DIR/.env"
touch "$ENV_FILE"

if [ -n "$GEMINI_API_KEY$OPENAI_API_KEY$ANTHROPIC_API_KEY" ]; then
  python3 - "$ENV_FILE" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
keys = ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
updates = {key: os.environ.get(key, "").strip() for key in keys}
updates = {key: value for key, value in updates.items() if value}

lines = path.read_text().splitlines() if path.exists() else []
seen = set()
new_lines = []
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line else ""
    if key in updates:
        new_lines.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        new_lines.append(line)

for key, value in updates.items():
    if key not in seen:
        new_lines.append(f"{key}={value}")

path.write_text("\n".join(new_lines).rstrip() + "\n")
PY

  echo "API keys written to $ENV_FILE"
else
  echo "No API keys provided; $ENV_FILE unchanged."
fi
echo "NOTE: AWS Secrets Manager remains the recommended Docker production path."
echo "See docs/AWS_SECRETS_SIDECAR.md for setup instructions."
```

Optional: Ask for OPENAI_API_KEY and ANTHROPIC_API_KEY for multi-model comparison.

#### 3c. Build, Restart, and Verify Docker Containers

Refresh the Docker stack after either API-key path. This is the only Tier 3
runtime path.

```bash
cd "$CPP_DIR"
make docker-refresh PROFILE="core browser"
DOCKER_REFRESH_RC=$?
if [ "$DOCKER_REFRESH_RC" -ne 0 ]; then
  echo "ERROR: Docker refresh failed or one or more containers are unhealthy."
  exit "$DOCKER_REFRESH_RC"
fi

make docker-health PROFILE="core browser"
DOCKER_HEALTH_RC=$?
if [ "$DOCKER_HEALTH_RC" -ne 0 ]; then
  echo "ERROR: Docker health verification failed."
  exit "$DOCKER_HEALTH_RC"
fi

sleep 5
if docker logs mcp-second-opinion 2>&1 | head -10 | grep -q "Loaded secrets from AWS"; then
  echo "Secrets loaded from AWS Secrets Manager"
fi

echo "Docker containers rebuilt, restarted, and healthy"
```

#### 3d. Register MCP Servers

```bash
# Add MCP servers to Claude Code
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")

if ! echo "$MCP_LIST" | grep -q "second-opinion"; then
  claude mcp add second-opinion --transport sse --url http://127.0.0.1:8080/sse --scope user
  echo "✓ second-opinion MCP registered"
else
  echo "→ second-opinion MCP already registered (skipped)"
fi

if ! echo "$MCP_LIST" | grep -q "playwright-persistent"; then
  claude mcp add playwright-persistent --transport sse --url http://127.0.0.1:8081/sse --scope user
  echo "✓ playwright-persistent MCP registered"
else
  echo "→ playwright-persistent MCP already registered (skipped)"
fi
```

### Tier 4 Execution (CI/CD)

#### 4a. Framework Detection and Makefile

```bash
# Detect framework
echo "Detecting project framework..."
DETECT_JSON=$(PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd detect --json 2>/dev/null || echo "{}")
FRAMEWORK=$(echo "$DETECT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('framework','unknown'))" 2>/dev/null || echo "unknown")
PKG_MGR=$(echo "$DETECT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('package_manager','unknown'))" 2>/dev/null || echo "unknown")
echo "Detected: $FRAMEWORK ($PKG_MGR)"
```

If no Makefile exists, offer to generate one:

```bash
if [ ! -f "Makefile" ]; then
  echo ""
  echo "No Makefile found. Generate one from the detected framework template?"
  # Use AskUserQuestion to confirm
  # If yes:
  PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd detect --generate-makefile
  echo "✓ Makefile generated"
else
  echo "→ Makefile already exists"
  echo "  Run /cicd:check to validate targets"
fi
```

If Makefile exists, run a quick check:

```bash
if [ -f "Makefile" ]; then
  echo ""
  echo "Validating Makefile..."
  PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd check --summary 2>/dev/null || echo "  (validation skipped)"
fi
```

#### 4b. Generate cicd.yml

```bash
if [ ! -f ".claude/cicd.yml" ]; then
  mkdir -p .claude
  # Generate cicd.yml with detected defaults
  if [ -f "$CPP_DIR/templates/cicd.yml.example" ]; then
    cp "$CPP_DIR/templates/cicd.yml.example" .claude/cicd.yml
    echo "✓ .claude/cicd.yml created from template"
    echo "  Edit to configure health checks and smoke tests"
  else
    cat > .claude/cicd.yml << 'CICD_EOF'
build:
  framework: auto
  package_manager: auto
  required_targets: [lint, test]
  recommended_targets: [format, typecheck, build, deploy, clean, verify]

health:
  endpoints: []
  processes: []
  smoke_tests: []
  post_deploy: false
CICD_EOF
    echo "✓ .claude/cicd.yml created with defaults"
  fi
else
  echo "→ .claude/cicd.yml already exists (skipped)"
fi
```

#### 4c. Health Check Configuration (Optional)

Ask the user if they want to configure health checks:

```
=== Optional: Health Checks ===

Configure endpoint health checks for post-deploy verification?

This lets /cicd:health and /flow:deploy verify your services are running.

Example:
  health:
    endpoints:
      - url: http://localhost:8000/health
        name: API Server

Configure health checks? [y/N]
```

If yes, use AskUserQuestion to get endpoint URLs, then update `.claude/cicd.yml`.

#### 4d. CI Pipeline Generation (Optional)

Ask the user if they want to generate a CI pipeline:

```
=== Optional: CI Pipeline ===

Generate a GitHub Actions CI workflow from your Makefile targets?

This creates .github/workflows/ci.yml using `make lint`, `make test`, etc.

Generate CI pipeline? [y/N]
```

If yes:

```bash
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd pipeline --write 2>/dev/null
if [ -f ".github/workflows/ci.yml" ]; then
  echo "✓ .github/workflows/ci.yml generated"
else
  echo "⚠ Pipeline generation failed"
fi
```

#### 4e. Container Generation (Optional)

Ask the user if they want to generate container files:

```
=== Optional: Container Files ===

Generate Dockerfile and docker-compose.yml for your project?

Uses multi-stage builds with framework-specific optimization.

Generate container files? [y/N]
```

If yes:

```bash
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd container --write 2>/dev/null
echo "✓ Container files generated"
```

### Tier 5 Execution (Codex Orchestration)

#### 5a. Check Codex CLI

```bash
echo ""
echo "=== Tier 5: Codex Orchestration ==="
echo ""

if command -v codex &>/dev/null; then
  CODEX_VERSION=$(codex --version 2>/dev/null || echo "unknown")
  echo "[x] Codex CLI: $CODEX_VERSION"
else
  echo "[ ] Codex CLI: not installed"
  echo ""
  echo "Install Codex CLI?"
  echo "  npm install -g @openai/codex"
  echo ""
  # Ask user if they want to install
  # If yes:
  npm install -g @openai/codex
  if command -v codex &>/dev/null; then
    echo "Codex CLI installed"
  else
    echo "WARNING: Codex CLI installation failed"
    echo "  Try: sudo npm install -g @openai/codex"
    echo "  Codex commands will not work until installed"
  fi
fi
```

#### 5b. Run Codex Doctor

```bash
if command -v codex &>/dev/null; then
  echo ""
  echo "Running codex doctor..."
  DOCTOR_OUTPUT=$(codex doctor 2>&1 || true)
  echo "$DOCTOR_OUTPUT"

  if echo "$DOCTOR_OUTPUT" | grep -qi "error\|fail\|missing"; then
    echo ""
    echo "WARNING: codex doctor reported issues. Resolve before using /codex:auto."
  else
    echo "[x] codex doctor: all checks passed"
  fi
fi
```

#### 5c. Verify OpenAI API Key

```bash
if command -v codex &>/dev/null; then
  echo ""
  echo "=== OpenAI API Key ==="

  CODEX_CONFIG="$HOME/.codex/config.toml"
  if [ -f "$CODEX_CONFIG" ] || [ -n "$OPENAI_API_KEY" ]; then
    echo "[x] OpenAI API key: configured"
  else
    echo "[ ] OpenAI API key: not configured"
    echo ""
    echo "Configure with one of:"
    echo "  codex login                    (interactive)"
    echo "  export OPENAI_API_KEY=sk-...   (environment variable)"
    echo ""
    echo "Codex commands require an OpenAI API key to function."
  fi
fi
```

#### 5d. Register MCP Servers with Codex (Optional)

This reuses the logic from Step 7 (Optional Extras) section 8b, but is now part of the Tier 5 flow:

```bash
if command -v codex &>/dev/null; then
  echo ""
  echo "=== Codex MCP Registration ==="
  echo ""
  echo "Register Claude Power Pack MCP servers with Codex?"
  echo "MCP servers expose streamable HTTP at /mcp for Codex compatibility."
  echo ""
  # Ask user if they want to register - use AskUserQuestion
  # If yes:
  CODEX_LIST=$(codex mcp list 2>/dev/null || echo "")

  for entry in "second-opinion:8080" "playwright-persistent:8081"; do
    NAME="${entry%%:*}"
    PORT="${entry#*:}"
    if echo "$CODEX_LIST" | grep -q "$NAME"; then
      echo "-> $NAME already registered with Codex (skipped)"
    else
      if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
        codex mcp add "$NAME" --url "http://127.0.0.1:${PORT}/mcp"
        echo "Registered $NAME with Codex (http://127.0.0.1:${PORT}/mcp)"
      else
        echo "WARNING: $NAME not reachable on port $PORT - skipping Codex registration"
        echo "  Start containers first: make docker-refresh PROFILE=\"core browser\""
      fi
    fi
  done

  echo ""
  echo "Restart Codex for tools to become available."
fi
```

---

## Step 6: Installation Summary

```
=================================
CPP Installation Complete!
=================================

Installed:
  ✓ Tier 1: Commands + Skills symlinked
  ✓ Tier 2: Scripts, hooks, shell prompt
  ✓ Tier 3: Docker MCP stack, API keys
  ✓ Tier 4: CI/CD build system, health checks, pipeline, containers
  ✓ Tier 5: Codex CLI orchestration

Permission Profile: {PROFILE_NAME}
  Auto-approved: {AUTO_APPROVE_SUMMARY}
  Blocked: rm -rf, git push --force, sudo (destructive)
  Settings: .claude/settings.local.json

Secrets:
  Method: {AWS Secrets Manager sidecar | Direct .env}
  Validate: make docker-secrets-check

Deployment:
  Model: Docker (local build)
  Refresh: make docker-refresh PROFILE="core browser"
  Health: make docker-health PROFILE="core browser"
  Update pathway: /cpp:update migrates legacy systemd and refreshes Docker

MCP Servers:
  • second-opinion (port 8080) - Gemini/OpenAI code review
  • playwright-persistent (port 8081) - Browser automation
  • aws-secrets-agent (internal port 2773) - Secret injection sidecar (if AWS SM)

Next Steps:
  1. Verify Docker containers:
     cd {CPP_DIR} && make docker-health PROFILE="core browser"

  2. Restart your shell to apply prompt changes:
     source ~/.bashrc

  3. Verify installation:
     /cpp:status

  4. Try the commands:
     /project-next    - See what to work on
     /spec:help       - Spec-driven development
     /github:help     - Issue management
     /cicd:help       - CI/CD build & verification
     /skills:find     - Discover skills from skills.sh

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

### Docker Not Available
```
ERROR: Tier 3 requires Docker Engine or Docker Desktop.

Install Docker and verify:
  docker ps
  docker compose version

If Docker is not available:
  1. Install manually: https://docs.docker.com/get-docker/
  2. Or skip Tier 3 and use Standard tier only

Skip Tier 3 components? [Y/n]
```

### API Key Not Provided
```
⚠ No GEMINI_API_KEY provided.

MCP Second Opinion will not work without an API key.
You can configure it later by editing: {CPP_DIR}/.env

Continue? [Y/n]
```

---

## Step 7: Optional Extras

After the main installation completes, offer optional extras.

### 8a. Sequential Thinking

```
=== Optional: Sequential Thinking MCP ===

Adds a `sequentialthinking` tool for structured, step-by-step reasoning
with revision and branching. Useful for complex debugging and architecture decisions.

Requires: Node.js 18+ (for npx)
No API keys needed. Runs as stdio subprocess (no port).

Install Sequential Thinking? [y/N]
```

If yes:

```bash
# Check if Node.js is available
if ! command -v npx &>/dev/null; then
  echo "⚠ npx not found. Sequential Thinking requires Node.js 18+."
  echo "  Install Node.js: https://nodejs.org/"
  echo "  Skipping Sequential Thinking."
else
  MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
  if echo "$MCP_LIST" | grep -q "sequential-thinking"; then
    echo "→ sequential-thinking MCP already registered (skipped)"
  else
    claude mcp add --transport stdio --scope user sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking
    echo "✓ Sequential Thinking MCP registered (stdio, user scope)"
  fi
fi
```

If no:
```bash
echo "→ Sequential Thinking skipped"
echo "  Install later: claude mcp add --transport stdio --scope user sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking"
```

### 8b. Codex MCP Registration (optional)

```
=== Optional: Codex MCP Registration ===

Register Claude Power Pack MCP servers with Codex?
This will run `codex mcp add ...` and update Codex configuration.

MCP servers expose streamable HTTP at /mcp for Codex compatibility.
Claude Code continues to use /sse (unchanged).

Register with Codex? [y/N]
```

If yes:

```bash
# Check if Codex CLI is available
if ! command -v codex &>/dev/null; then
  echo "⚠ Codex CLI not found. Skipping registration."
  echo "  Install Codex first, then run the commands in .agents/CODEX_SETUP.md"
else
  CODEX_LIST=$(codex mcp list 2>/dev/null || echo "")

  for entry in "second-opinion:8080" "playwright-persistent:8081"; do
    NAME="${entry%%:*}"
    PORT="${entry#*:}"
    if echo "$CODEX_LIST" | grep -q "$NAME"; then
      echo "-> $NAME already registered with Codex (skipped)"
    else
      # Verify container is reachable before registering
      if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
        codex mcp add "$NAME" --url "http://127.0.0.1:${PORT}/mcp"
        echo "✓ $NAME registered with Codex (http://127.0.0.1:${PORT}/mcp)"
      else
        echo "⚠ $NAME not reachable on port $PORT - skipping Codex registration"
        echo "  Start containers first: make docker-refresh PROFILE=\"core browser\""
      fi
    fi
  done

  echo ""
  echo "Restart Codex for tools to become available."
fi
```

If no:

```bash
echo "-> Codex registration skipped"
# Write setup artifact for manual registration later
mkdir -p .agents
if [ -f "$CPP_DIR/.agents/CODEX_SETUP.md" ]; then
  cp "$CPP_DIR/.agents/CODEX_SETUP.md" .agents/CODEX_SETUP.md
  echo "  Setup commands saved to .agents/CODEX_SETUP.md"
else
  echo "  Register later with: codex mcp add <name> --url http://127.0.0.1:<port>/mcp"
fi
```

### 8c. Workstation Tuning (bash-prep)

```
=== Optional: Workstation Tuning ===

Linux workstation tuning for optimal Claude Code performance:
  • Swap (min(RAM, 4GB)) - prevent OOM kills during heavy sessions
  • vm.swappiness=10 - keep active data in RAM
  • vm.vfs_cache_pressure=50 - cache filesystem metadata
  • fs.inotify.max_user_watches=524288 - prevent watcher failures
  • fs.inotify.max_user_instances=512 - headroom for multiple watchers

Requires sudo. Safe to run multiple times (idempotent).
Persists across reboots via /etc/sysctl.d/ and /etc/fstab.

Apply workstation tuning? [y/N]
```

If yes:

```bash
# Run bash-prep script
if [ -f "$CPP_DIR/scripts/bash-prep.sh" ]; then
  bash "$CPP_DIR/scripts/bash-prep.sh" --apply
else
  echo "⚠ bash-prep.sh not found at $CPP_DIR/scripts/bash-prep.sh"
fi
```

If no:
```bash
echo "→ Workstation tuning skipped"
echo "  Run later: bash ~/.claude/scripts/bash-prep.sh"
echo "  Or check current values: bash ~/.claude/scripts/bash-prep.sh --check"
```

---

## Notes

- This wizard is **idempotent** - safe to run multiple times
- Already-installed components are skipped with a message
- Symlinks are preferred over copies for easier updates
- Run `/cpp:status` anytime to check installation state
