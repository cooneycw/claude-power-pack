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
[ -L ".claude/commands" ] || [ -d ".claude/commands" ] && COMMANDS_INSTALLED=true

# Tier 2 checks
SCRIPTS_COUNT=$(ls ~/.claude/scripts/*.sh 2>/dev/null | wc -l)
HOOKS_EXIST=false
[ -f ".claude/hooks.json" ] && HOOKS_EXIST=true

# Tier 3 checks
# CPP no longer runs a Docker MCP stack. Second Opinion is an external
# streamable-http server (its own repo) and playwright runs via npx. The only
# Docker interest here is spotting retired containers that /cpp:update tears down.
DOCKER_INSTALLED=false
LEFTOVER_CONTAINERS=""
LEGACY_SYSTEMD_UNITS=""

command -v docker &>/dev/null && DOCKER_INSTALLED=true

if [ "$DOCKER_INSTALLED" = "true" ]; then
  LEFTOVER_CONTAINERS=$(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -E '^(aws-secrets-agent|mcp-second-opinion|mcp-playwright-persistent)$' || true)
fi

for unit in mcp-second-opinion second-opinion mcp-playwright mcp-playwright-persistent playwright-persistent mcp-evaluate evaluate mcp-coordination coordination; do
  [ -f "/etc/systemd/system/${unit}.service" ] && LEGACY_SYSTEMD_UNITS="$LEGACY_SYSTEMD_UNITS system:${unit}"
  [ -f "$HOME/.config/systemd/user/${unit}.service" ] && LEGACY_SYSTEMD_UNITS="$LEGACY_SYSTEMD_UNITS user:${unit}"
done

MCP_SERVERS=""
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
for server in second-opinion playwright; do
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
| 1 | **Minimal** | Commands symlink only |
| 2 | **Standard** | + Scripts, hooks, shell prompt |
| 3 | **Full** | + MCP servers (external second-opinion + playwright) |
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
      "mcp__second-opinion__*", "mcp__playwright__*"
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
- **Native blocking + sandbox are the first layer** - Claude Code natively auto-blocks destructive git commands and OS-sandboxes filesystem/system operations, even if auto-approved
- **Hooks provide the secret-masking layer** - the PostToolUse hook masks secrets in output (which native tooling does not do)
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

  Disk usage: ~0 MB (symlinks only)

  To undo:
    rm .claude/commands

Proceed? [y/N]
```

### Tier 2 Disclosure (Standard)

```
=== Tier 2: Standard Installation ===

This will make the following changes:

  [Tier 1 - Symlinks]
    • .claude/commands → {CPP_DIR}/.claude/commands

  [Tier 2 - Scripts] (~/.claude/scripts/)
    • prompt-context.sh       - Shell prompt worktree context
    • worktree-remove.sh      - Safe worktree cleanup
    • secrets-mask.sh         - Output masking filter
    • hook-mask-output.sh     - PostToolUse secret masking

  [Tier 2 - Hooks] (.claude/hooks.json)
    • SessionStart: upstream change detection
    • PostToolUse: mask secrets in output

  [Tier 2 - Shell Prompt] (optional)
    • Add worktree context to PS1: [CPP #42] ~/project $

  [Tier 2 - Makefile] (optional)
    • Create starter Makefile with lint, test, deploy targets
    • Used by /flow:finish and /flow:deploy

  Disk usage: ~50 KB

  To undo:
    rm .claude/commands
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

  [Tier 3 - Second Opinion MCP (external server)]
    • The second-opinion server is a SEPARATE project run from its own repo:
      https://github.com/cooneycw/mcp-second-opinion
    • Start it there (localhost or a Tailscale host). It listens on
      http://127.0.0.1:8080/mcp (streamable-http). CPP does not build or run it.
    • API keys (Gemini/OpenAI/Anthropic) are configured in that repo, not here.
    • Inside CPP the shipped root .mcp.json already points Claude Code at that URL
      (project scope). This tier also registers it at USER scope for global use:
        claude mcp add second-opinion --transport http --url http://127.0.0.1:8080/mcp --scope user
      Edit the URL to wherever your server runs (e.g. a Tailscale address).

  [Tier 3 - Browser Automation] (upstream @playwright/mcp, no container)
    • Registers the upstream `@playwright/mcp` server via npx/stdio
    • Requires Node.js 18+ (for npx); Chromium downloads to ~/.cache/ms-playwright
      on first use. No Docker container.

  [Tier 3 - Browser desk pool] (optional, off by default)
    • /browser:session named concurrent sessions over upstream @playwright/mcp
    • Registers playwright-desk-1..N (npx, no custom image) - requires a restart
    • Skip unless you need several logged-in browser sessions at once

  Disk usage: ~1.3 GB for the Chromium browser cache (varies by host and cache
  state). The second-opinion server's own footprint lives in its own repo.
  Ports used: 8080 is the external second-opinion server (not started by CPP)

  To undo:
    # Tier 1+2 cleanup (see above)
    claude mcp remove second-opinion
    claude mcp remove playwright
    # If the browser desk pool was enabled:
    for d in $(python3 -c "import json;print(' '.join(json.load(open('.claude/playwright-pool.json'))['desks']))" 2>/dev/null); do claude mcp remove "$d"; done

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

**Permission-Prompt Census Hook (Optional)**

The retro loop's `permission-prompt` friction class (issue #426) can only be
captured by the harness: a manually approved tool call and an auto-allowed one
are indistinguishable to the model. `scripts/hook-permission-census.sh` (a
`PermissionRequest` hook, installed as a Tier 2 script above) fires when a
permission dialog is shown and appends one risk-rated record to the project's
`.claude/friction.jsonl`, so `/self-improvement:retro` Step 4 gets real input
(issue #482). It is observe-only (never influences the decision) and fail-open.
Registering it edits `~/.claude/settings.json` - the same user-level trust
boundary as the flow allowlist above - so it is offered, not applied silently:

```
=== Optional: Permission-Prompt Census Hook ===

Register the observe-only PermissionRequest census hook in
~/.claude/settings.json? It records each permission prompt (with a derived
allow-rule candidate and a risk tier) to the project's friction ledger so
/self-improvement:retro can propose an allowlist from real data. Never blocks
or alters a permission decision.  [y/N]
```

If yes:

```bash
TARGET="$HOME/.claude/settings.json"
CENSUS_CMD="~/.claude/scripts/hook-permission-census.sh"
mkdir -p "$HOME/.claude"
[ -f "$TARGET" ] || echo '{}' > "$TARGET"

# Idempotent: add the hook only if this exact command is not already registered.
jq --arg cmd "$CENSUS_CMD" '
  .hooks = (.hooks // {})
  | .hooks.PermissionRequest = (.hooks.PermissionRequest // [])
  | if any(.hooks.PermissionRequest[]?; (.hooks // [])[]?.command == $cmd)
    then .
    else .hooks.PermissionRequest += [{"hooks":[{"type":"command","command":$cmd}]}]
    end
' "$TARGET" > "$TARGET.tmp" && mv "$TARGET.tmp" "$TARGET"
echo "✓ PermissionRequest census hook registered in ~/.claude/settings.json"
```

If no:

```bash
echo "→ Permission-prompt census hook skipped"
echo "  Register later via /cpp:update, or read docs/HOST_MANAGED_ARTIFACTS.md"
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

**Spec-Kit CLI Installation (Optional)**

Ask the user if they want to install the official spec-kit CLI (`specify`). This is the
authoring engine behind `/spec:adopt`; installing it now means `/spec:adopt` and the
`/speckit-*` skills work in any project without a first-run install step. This installs
only the CLI - it does NOT scaffold `.specify/` into any project (that stays on-demand
via `/spec:adopt`).

```
=== Optional: Spec-Kit CLI ===

Spec-Kit is GitHub's spec-driven-development toolkit. CPP's /spec:adopt delegates to
its `specify` CLI (constitution -> specify -> clarify -> plan -> tasks).
https://github.com/github/spec-kit

Install the spec-kit CLI? [y/N]
```

If yes:
```bash
# Check if already installed
if command -v specify &>/dev/null; then
  echo "→ spec-kit CLI already installed (skipped)"
  specify version 2>/dev/null | head -1 || true
else
  echo "Installing spec-kit CLI (uv tool)..."
  uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
  if command -v specify &>/dev/null; then
    echo "✓ spec-kit CLI installed"
    echo "  Run /spec:adopt in a project to scaffold spec-kit into it"
  else
    echo "⚠ Installation failed - ensure 'uv' is installed and ~/.local/bin is on PATH"
    echo "  Try: uv tool install specify-cli --from git+https://github.com/github/spec-kit.git"
  fi
fi
echo "✓ /spec:adopt command available (per-project spec-kit scaffold)"
```

If no:
```bash
echo "→ Spec-Kit CLI installation skipped (/spec:adopt installs it on first use)"
```

### Tier 3 Execution

#### 3a. Legacy Runtime Note (informational)

CPP no longer builds or runs a Docker MCP stack, and it no longer manages systemd
MCP units. Tier 3 registers an external second-opinion server plus the upstream
playwright npx server; no containers are built here. If an older install left
legacy systemd MCP units or retired MCP containers (mcp-second-opinion,
aws-secrets-agent, mcp-playwright-persistent) behind, run /cpp:update to tear
them down.

```bash
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
  echo "Run /cpp:update to migrate or remove legacy systemd units and leftover containers."
  echo "/cpp:init no longer installs, starts, or manages systemd services."
fi
```

#### 3b. Second Opinion Server (external)

The second-opinion MCP server is a SEPARATE project. Run it from its own repo -
it is not built or started by CPP:

  https://github.com/cooneycw/mcp-second-opinion

Start the server there (on localhost or a Tailscale host). It listens on
http://127.0.0.1:8080/mcp (streamable-http). API keys (Gemini/OpenAI/Anthropic)
are configured in that repo, not here.

Inside CPP the shipped root `.mcp.json` already points Claude Code at that URL at
project scope. The next step also registers it at user scope for global use.

#### 3c. Register MCP Servers

```bash
# Add MCP servers to Claude Code
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")

# Second Opinion is an external streamable-http server. The repo's root .mcp.json
# already points at it (project scope); this adds a USER-scope registration for
# global / cross-project use. Edit the URL to wherever your server runs (e.g. a
# Tailscale host) if it is not on localhost.
if ! echo "$MCP_LIST" | grep -q "second-opinion"; then
  claude mcp add second-opinion --transport http --url http://127.0.0.1:8080/mcp --scope user
  echo "✓ second-opinion MCP registered (streamable-http, user scope)"
else
  echo "→ second-opinion MCP already registered (skipped)"
fi

# Browser automation is the upstream @playwright/mcp server, registered via
# npx/stdio (no container). Requires Node.js 18+ for npx.
if echo "$MCP_LIST" | grep -q "playwright-persistent"; then
  echo "→ Legacy playwright-persistent registration detected."
  echo "  Run /cpp:update to tear down the retired container/registration (issue #423)."
fi
if ! echo "$MCP_LIST" | grep -qw "playwright"; then
  if command -v npx &>/dev/null; then
    claude mcp add --transport stdio --scope user playwright -- npx -y @playwright/mcp@latest --headless
    echo "✓ playwright MCP (upstream @playwright/mcp) registered"
  else
    echo "⚠ npx not found. Browser automation needs Node.js 18+."
    echo "  Install later: claude mcp add --transport stdio --scope user playwright -- npx -y @playwright/mcp@latest --headless"
  fi
else
  echo "→ playwright MCP already registered (skipped)"
fi
```

#### 3d. Register the browser desk pool (optional, off by default)

The **lease-desk pool** powers `/browser:session` - named **concurrent** browser
sessions over upstream `@playwright/mcp` (issue #421). It is opt-in: it registers
N always-present upstream instances ("desks"), each adding a `browser_*` tool
surface to every session's startup context. Single-session work (`/qa:test`, a
one-off screenshot) does **not** need it.

Ask the user with AskUserQuestion: **"Enable the browser desk pool (named concurrent
sessions)? Adds N upstream playwright-mcp instances via npx."** Default: **No**.

If the user opts in, seed the pool config into the project and register the desks as
stdio MCP servers (upstream via `npx`, no custom image, pinned version):

```bash
# Seed the project's pool config (edit desk count / idle timeout there later).
mkdir -p .claude
if [ ! -f .claude/playwright-pool.json ]; then
  cp "$CPP_DIR/templates/playwright-pool.example.json" .claude/playwright-pool.json
  echo "✓ Seeded .claude/playwright-pool.json"
fi

# Register one MCP server per desk listed in the pool config. Each runs upstream
# @playwright/mcp with --isolated (blank context per lease; session identity lives
# in the portable state file, not the desk).
PW_MCP_VERSION="0.0.77"
DESKS=$(python3 -c "import json; print('\n'.join(json.load(open('.claude/playwright-pool.json'))['desks']))")
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
for desk in $DESKS; do
  if echo "$MCP_LIST" | grep -q "$desk"; then
    echo "→ $desk already registered (skipped)"
  else
    claude mcp add "$desk" --scope user -- npx -y "@playwright/mcp@${PW_MCP_VERSION}" --isolated
    echo "✓ $desk registered (npx @playwright/mcp@${PW_MCP_VERSION} --isolated)"
  fi
done

echo ""
echo "IMPORTANT: restart Claude Code so the playwright-desk-* servers load at startup"
echo "(MCP config is read only at startup; mid-session registration does not take effect)."
echo "Then verify with: /browser:session pool"
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

  for entry in "second-opinion:8080"; do
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
        echo "  Start the external second-opinion server first (see https://github.com/cooneycw/mcp-second-opinion)"
      fi
    fi
  done

  # Browser automation (upstream @playwright/mcp) is stdio/npx, not HTTP.
  if echo "$CODEX_LIST" | grep -qw "playwright"; then
    echo "-> playwright already registered with Codex (skipped)"
  elif command -v npx &>/dev/null; then
    codex mcp add playwright -- npx -y @playwright/mcp@latest --headless
    echo "Registered playwright (upstream @playwright/mcp) with Codex"
  else
    echo "WARNING: npx not found - skipping Codex playwright registration (needs Node.js 18+)"
  fi

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
  ✓ Tier 1: Commands symlinked
  ✓ Tier 2: Scripts, hooks, shell prompt
  ✓ Tier 3: MCP servers (external second-opinion + playwright)
  ✓ Tier 4: CI/CD build system, health checks, pipeline, containers
  ✓ Tier 5: Codex CLI orchestration

Permission Profile: {PROFILE_NAME}
  Auto-approved: {AUTO_APPROVE_SUMMARY}
  Blocked: rm -rf, git push --force, sudo (destructive)
  Settings: .claude/settings.local.json

MCP Servers:
  • second-opinion (external server, http://127.0.0.1:8080/mcp) - Gemini/OpenAI
    code review. Run it from https://github.com/cooneycw/mcp-second-opinion;
    edit the URL for a Tailscale host. Root .mcp.json points at it (project scope).
  • playwright (upstream @playwright/mcp, npx/stdio) - Browser automation

Update pathway:
  /cpp:update pulls CPP and tears down any legacy systemd units or retired MCP
  containers (mcp-second-opinion, aws-secrets-agent, ...) left on this host.

Next Steps:
  1. Verify the second-opinion server is running (from the mcp-second-opinion
     repo) and reachable at http://127.0.0.1:8080/mcp

  2. Restart your shell to apply prompt changes:
     source ~/.bashrc

  3. Verify installation:
     /cpp:status

  4. Try the commands:
     /project-next    - See what to work on
     /spec:help       - Spec-driven development
     /github:help     - Issue management
     /cicd:help       - CI/CD build & verification
     npx skills find  - Discover skills from skills.sh (or /plugin for the marketplace)

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

### Second Opinion Server Not Reachable
```
⚠ The second-opinion server did not answer on http://127.0.0.1:8080/mcp.

It is an EXTERNAL server - start it from its own repo first:
  https://github.com/cooneycw/mcp-second-opinion

If your server runs on a different host (e.g. a Tailscale address), re-register
with the correct URL:
  claude mcp add second-opinion --transport http --url <url> --scope user
```

### npx Not Available (playwright)
```
⚠ npx not found. Browser automation (upstream @playwright/mcp) needs Node.js 18+.

Install Node.js (https://nodejs.org/), then:
  claude mcp add --transport stdio --scope user playwright -- npx -y @playwright/mcp@latest --headless
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

MCP servers expose streamable HTTP at /mcp. Claude Code and Codex both use
the /mcp streamable-http endpoint.

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

  for entry in "second-opinion:8080"; do
    NAME="${entry%%:*}"
    PORT="${entry#*:}"
    if echo "$CODEX_LIST" | grep -q "$NAME"; then
      echo "-> $NAME already registered with Codex (skipped)"
    else
      # Verify the external server is reachable before registering
      if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
        codex mcp add "$NAME" --url "http://127.0.0.1:${PORT}/mcp"
        echo "✓ $NAME registered with Codex (http://127.0.0.1:${PORT}/mcp)"
      else
        echo "⚠ $NAME not reachable on port $PORT - skipping Codex registration"
        echo "  Start the external second-opinion server first (see https://github.com/cooneycw/mcp-second-opinion)"
      fi
    fi
  done

  # Browser automation (upstream @playwright/mcp) is stdio/npx, not HTTP.
  if echo "$CODEX_LIST" | grep -qw "playwright"; then
    echo "-> playwright already registered with Codex (skipped)"
  elif command -v npx &>/dev/null; then
    codex mcp add playwright -- npx -y @playwright/mcp@latest --headless
    echo "✓ playwright (upstream @playwright/mcp) registered with Codex"
  else
    echo "⚠ npx not found - skipping Codex playwright registration (needs Node.js 18+)"
  fi

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

### 8d. Common-Memory Store Backend (mini-tier)

Only offer this when the common-memory feature is in use (Tier 2+ installed the
`cpp-memory` harness). It selects the storage backend for the friction-knowledge
ledger (`lib/cpp_memory`, issue #472). **Federation is the key column** - only
tier iii shares learnings/rejections across VMs; on i and ii the `is_known` /
`rejected_here` check is this-box-only.

```
=== Optional: Common-Memory Store Backend ===

The friction-knowledge ledger can run on one of three backends. Federation
(does a learning recorded here reach OTHER machines?) differs per tier - pick
with that in mind:

  Tier  Backend     Dedup fidelity              Federation (cross-VM sharing?)
  ----  ----------  --------------------------  ------------------------------
  i     md          best-effort (grep/parse)    NO  - local box only
  ii    local-pg    full (SQL fingerprint)      NO  - single box (docker pg)
  iii   remote-pg   full (SQL fingerprint)      YES - shared across the fleet

  i    = zero dependencies; promotes .claude/learnings.md to a real store.
  ii   = full-fidelity dedup on this box; needs Docker (stock postgres:17).
  iii  = the fleet store over Tailscale; DSN from CPP_MEMORIES_DSN / the local
         dsn file / AWS SM (essent-ai). This is today's default on fleet VMs.

Select backend [i/ii/iii, Enter to skip]:
```

Persist the choice to the backend file the client reads
(`resolve_backend()` in `lib/cpp_memory/config.py`):

```bash
BACKEND_FILE="$HOME/.config/claude-power-pack/secrets/cpp-memories.backend"
mkdir -p "$(dirname "$BACKEND_FILE")"

case "$MEM_BACKEND_CHOICE" in
  i|md)
    echo "md" > "$BACKEND_FILE"
    echo "✓ common-memory backend: md (tier i) - local-only, no federation"
    echo "  Ledger: <repo>/.claude/learnings.md  (+ .claude/learnings.rejected.jsonl)"
    ;;
  ii|local-pg)
    echo "local-pg" > "$BACKEND_FILE"
    echo "✓ common-memory backend: local-pg (tier ii) - full dedup, no federation"
    if command -v docker >/dev/null 2>&1; then
      read -r -p "Start the local postgres:17 store now (docker compose up -d)? [y/N] " START_PG
      if [[ "$START_PG" =~ ^[Yy]$ ]]; then
        docker compose -f "$CPP_DIR/lib/cpp_memory/docker-compose.yml" up -d
        echo "  Store on 127.0.0.1:5433 (schema auto-applied on first boot)."
      else
        echo "  Start later: docker compose -f \"$CPP_DIR/lib/cpp_memory/docker-compose.yml\" up -d"
      fi
    else
      echo "⚠ Docker not found - install it, then: docker compose -f \"$CPP_DIR/lib/cpp_memory/docker-compose.yml\" up -d"
    fi
    echo "  Default DSN: postgresql://cpp_memory:cpp_memory@127.0.0.1:5433/cpp_memory"
    ;;
  iii|remote-pg)
    echo "remote-pg" > "$BACKEND_FILE"
    echo "✓ common-memory backend: remote-pg (tier iii) - full dedup, FLEET federation"
    echo "  DSN resolves fail-open: CPP_MEMORIES_DSN -> ~/.config/claude-power-pack/secrets/cpp-memories.dsn -> AWS SM (essent-ai)."
    echo "  Provision a new remote store with scripts/memories-db-setup.sh (idempotent)."
    if bash "$CPP_DIR/scripts/cpp-memory" ping 2>/dev/null | grep -q '"reachable": true'; then
      echo "  Reachability: OK (store answered ping)."
    else
      echo "  Reachability: not reachable yet - set the DSN, then: cpp-memory ping"
    fi
    ;;
  ""|skip|n|N)
    echo "→ Backend selection skipped - the client infers one (DSN present -> remote-pg, else md)."
    ;;
  *)
    echo "⚠ Unrecognized choice '$MEM_BACKEND_CHOICE' - skipped. Re-run /cpp:init to choose."
    ;;
esac
```

Verify with `cpp-memory ping` (its JSON now reports `backend` and `federation`).

---

## Notes

- This wizard is **idempotent** - safe to run multiple times
- Already-installed components are skipped with a message
- Symlinks are preferred over copies for easier updates
- Run `/cpp:status` anytime to check installation state
