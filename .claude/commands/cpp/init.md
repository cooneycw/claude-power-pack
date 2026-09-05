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

# Tier 2 checks (count every linked helper, not just .sh - issue #669)
SCRIPTS_COUNT=$(find ~/.claude/scripts -maxdepth 1 -type l 2>/dev/null | wc -l)
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
| 6 | **Local Qwen** | + Local-model orchestration via Ollama-served Qwen (zero API cost, private) |
| 7 | **Local Gemma** | + Second local-model lane via Ollama-served Gemma 4 on a GPU box (zero API cost, private, faster) |

Default recommendation: **Standard** for most users, **Full** for MCP-powered workflows, **CI/CD** for projects needing build automation, **Codex** for cross-model implementation workflows, **Local Qwen** or **Local Gemma** for zero-cost/private local-model implementation.

Tier 6 is optional and additive: it layers on Tier 1 (commands symlink) and
does not require Tiers 2-5, though it reuses the Codex CLI binary as a
harness if Tier 5 already installed it.

Tier 7 is likewise optional and additive, and independent of Tier 6: a
different model, a different harness (OpenCode), a different env var, and its
own config block. Installing both is supported and needs no coordination -
pick Tier 7 when a GPU box is available (markedly faster) or when a second,
non-Qwen local opinion is wanted.

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

This will create the following symlinks (issue #663 - symlinks are the
CANONICAL command surface: they follow `git pull` atomically, so the executed
command text can never drift from the checkout):

  User scope (every session on this host):
    • ~/.claude/commands/<family> → {CPP_DIR}/.claude/commands/<family>
      (per-family links via scripts/cpp-commands-link.sh - your own files in
       ~/.claude/commands/ are preserved; a name collision with your own
       content is reported as foreign and never touched)

  Project scope (this project only):
    • .claude/commands → {CPP_DIR}/.claude/commands

  Disk usage: ~0 MB (symlinks only)

  To undo:
    rm .claude/commands
    # user scope: remove the per-family symlinks (only ones pointing into a
    # CPP checkout's .claude/commands/):
    ~/.claude/scripts/cpp-commands-link.sh --check   # lists what is linked

  Note: if the retired /plugin marketplace families are still installed
  (#662 / ADR 0005), the cached copies coexist with these symlinks - uninstall
  them (`/plugin uninstall <family>@cpp`) so sessions read only the current
  text.

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

  [Tier 2 - Tmux Auto-Start] (optional)
    • Add tmux auto-start to ~/.bashrc
    • Each new terminal tab opens its own tmux session
    • Skipped inside existing tmux sessions and non-interactive shells

  [Tier 2 - Makefile] (optional)
    • Create starter Makefile with lint, test, deploy targets
    • Used by /flow:finish and /flow:deploy

  Disk usage: ~50 KB

  To undo:
    rm .claude/commands
    find ~/.claude/scripts -maxdepth 1 -type l -delete   # CPP installs symlinks only
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

### Tier 6 Disclosure (Local Qwen)

```
=== Tier 6: Local Qwen Orchestration ===

This will make the following changes:

  [Tier 1 - Commands symlink]
    (see above; Tiers 2-5 are NOT required for this tier)

  [Tier 6 - Local Qwen]
    - Requires: Qwen Code CLI as the agentic harness
      (npm install -g @qwen-code/qwen-code)
      NOTE: no cloud API key is needed - the harness talks straight to Ollama
    - Requires: an Ollama server with the Qwen model, either on this machine
      (ollama pull qwen3.8:27b + tuned qwen3.8-code tag) or reachable over the
      network (QWEN_OLLAMA_URL)
    - Installs: /qwen:auto, /qwen:exec, /qwen:status, /qwen:help commands

  Disk usage: ~0 MB (commands via symlink); the model itself is ~17 GB
  and lives on the serving machine only.

  To undo:
    # Tier 1 cleanup (see above)
    # On the serving machine, optionally: ollama rm qwen3.8-code qwen3.8:27b

Proceed? [y/N]
```

### Tier 7 Disclosure (Local Gemma)

```
=== Tier 7: Local Gemma Orchestration ===

This will make the following changes:

  [Tier 1 - Commands symlink]
    (see above; Tiers 2-6 are NOT required for this tier)

  [Tier 7 - Local Gemma]
    - Requires: OpenCode CLI as the agentic harness
      (npm install -g opencode-ai)
      NOTE: no cloud API key is needed - the harness talks straight to Ollama
    - Requires: an Ollama server with the Gemma model, either on this machine
      (ollama pull gemma4:31b-it-qat + tuned 64K gemma4-code tag) or reachable
      over the network (GEMMA_OLLAMA_URL)
    - Writes: ~/.config/opencode/opencode.json - adds a 'gemma-ollama'
      provider (native /api/chat) and a 'gemma-implementer' agent profile
      whose permission rules deny git/gh/deploy commands and out-of-directory
      writes. An existing file is merged into, never overwritten.
    - Installs: /gemma:auto, /gemma:exec, /gemma:status, /gemma:help commands

  Disk usage: ~0 MB (commands via symlink); the model itself is ~18 GB
  and lives on the serving machine only.

  To undo:
    # Tier 1 cleanup (see above)
    # Remove the gemma-ollama provider and gemma-implementer agent blocks
    #   from ~/.config/opencode/opencode.json
    # On the serving machine, optionally: ollama rm gemma4-code gemma4:31b-it-qat

Proceed? [y/N]
```

---

## Step 5: Execute Installation

Execute only the components that aren't already installed.

### Tier 1 Execution

**User scope first (issue #663):** per-family symlinks into
`~/.claude/commands/` serve the command surface to every session on this
host and follow `git pull` atomically. The helper owns the safety rules
(replaces only symlinks it created, never a user's file or dir) - do not
re-implement it inline. Call it BARE (the #581 allowlist rule matches the
stable path); on exit 127 fall back to `"$CPP_DIR/scripts/cpp-commands-link.sh"`:

```bash
~/.claude/scripts/cpp-commands-link.sh
```

`foreign` lines in its output are the user's own content winning a name
collision - report them, never "fix" them. If a retired `/plugin`
marketplace cache still carries CPP families (#662 / ADR 0005), tell the user to
run `/plugin uninstall <family>@cpp` for each so sessions stop reading the
stale cached copies.

**Project scope (optional, this project only):**

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

# Symlink all executable helpers, regardless of extension (issue #669: the
# old *.sh-only glob skipped flow-wave-plan.py, so its shipped allow rule in
# templates/claude-settings-permissions.json pointed at a nonexistent path).
# The executability gate skips non-executable .py library files, directories,
# and __pycache__.
for script in "$CPP_DIR"/scripts/*; do
  [ -f "$script" ] && [ -x "$script" ] || continue
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

**Session-Open Reminders (Optional, opt-in)**

`scripts/hook-pending-retro.sh` (a `SessionStart` hook, installed as a Tier 2
script above) prints up to TWO advisory lines at session open, each independent
of the other:

1. **Pending retro material** - `.claude/friction.jsonl` signals (actionable vs
   the bulk permission-prompt census, counted separately) plus any uncodified
   `Status: proposed` learnings, pointing at `/self-improvement:retro` (#530).
2. **Retired CPP marketplace cache** - which families still remain under
   `~/.claude/plugins/cache/cpp/`, via `scripts/install-drift.sh` (#622/#662),
   so the host can migrate them with `/plugin uninstall <family>@cpp` before
   #663 restores the canonical symlink tier.

It only SURFACES; it never codifies, and it is silent when there is nothing to
report. It is deliberately NOT shipped in `.claude/hooks.json`, so it never turns
itself on; registering it edits `~/.claude/settings.json` (the user-level trust
boundary), so it is offered, not applied - default N:

```
=== Optional: Session-Open Reminders (opt-in) ===

Register the session-open reminder in ~/.claude/settings.json? It prints one
advisory line when pending friction signals or uncodified learnings exist (run
/self-improvement:retro), and one when a retired CPP marketplace cache is still
pending uninstall (#662/#663). Surfaces only - never codifies, never blocks.
Silent when there is nothing to report.  [y/N default N]
```

If yes:

```bash
TARGET="$HOME/.claude/settings.json"
RETRO_CMD="~/.claude/scripts/hook-pending-retro.sh"
mkdir -p "$HOME/.claude"
[ -f "$TARGET" ] || echo '{}' > "$TARGET"

# Idempotent: add the hook only if this exact command is not already registered
# (tolerant of both the {hooks:[...]} group shape and a bare {command} entry).
jq --arg cmd "$RETRO_CMD" '
  .hooks = (.hooks // {})
  | .hooks.SessionStart = (.hooks.SessionStart // [])
  | if any(.hooks.SessionStart[]?; (.command == $cmd) or ((.hooks // [])[]?.command == $cmd))
    then .
    else .hooks.SessionStart += [{"hooks":[{"type":"command","command":$cmd}]}]
    end
' "$TARGET" > "$TARGET.tmp" && mv "$TARGET.tmp" "$TARGET"
echo "✓ Session-open retro reminder registered in ~/.claude/settings.json"
```

If no:

```bash
echo "→ Pending-retro reminder skipped (default)"
echo "  Enable later via /cpp:update"
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

**Tmux Auto-Start (Optional)**

Ask the user if they want tmux to start automatically in new terminal tabs:

```
=== Optional: Tmux Auto-Start ===

Start tmux automatically when opening a new terminal tab?

Each tab gets its own independent tmux session. Skipped inside existing
tmux sessions and non-interactive shells (scripts, cron, Claude Code).

Requires: tmux installed (apt install tmux)

Add to ~/.bashrc? [y/N]
```

If yes:
```bash
# Check if tmux is installed
if ! command -v tmux &>/dev/null; then
  echo "⚠ tmux not found. Install it first:"
  echo "  sudo apt install tmux"
  echo "  Skipping tmux auto-start."
else
  # Check if already configured
  if grep -q 'tmux new-session' ~/.bashrc 2>/dev/null; then
    echo "→ tmux auto-start already in ~/.bashrc (skipped)"
  else
    cat >> ~/.bashrc << 'TMUX_EOF'

# Claude Power Pack - tmux auto-start
if command -v tmux &>/dev/null && [ -z "$TMUX" ] && [[ $- == *i* ]]; then
    tmux new-session
fi
TMUX_EOF
    echo "✓ tmux auto-start configured (restart shell or source ~/.bashrc)"
  fi
fi
```

If no:
```bash
echo "→ Tmux auto-start skipped"
echo "  Add later by appending to ~/.bashrc:"
echo '  if command -v tmux &>/dev/null && [ -z "$TMUX" ] && [[ $- == *i* ]]; then tmux new-session; fi'
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
echo "✓ /cpp:happy-check command available (verify version updates)"
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

# Tavily web search/extract/crawl/map is the upstream tavily-mcp server,
# registered via npx/stdio (no container). Requires Node.js 20+ and a
# TAVILY_API_KEY in the environment. API key is stored in AWS Secrets Manager
# (claude-power-pack/mcp-keys).
if ! echo "$MCP_LIST" | grep -qw "tavily"; then
  if command -v npx &>/dev/null; then
    if [ -n "$TAVILY_API_KEY" ]; then
      claude mcp add tavily --transport stdio --scope user -e TAVILY_API_KEY="$TAVILY_API_KEY" -- npx -y tavily-mcp@latest
      echo "✓ tavily MCP (upstream tavily-mcp) registered"
    else
      echo "⚠ TAVILY_API_KEY not set. Get a key from https://app.tavily.com/home"
      echo "  Then: claude mcp add tavily --transport stdio --scope user -e TAVILY_API_KEY=tvly-... -- npx -y tavily-mcp@latest"
    fi
  else
    echo "⚠ npx not found. Tavily MCP needs Node.js 20+."
    echo "  Install later: claude mcp add tavily --transport stdio --scope user -e TAVILY_API_KEY=... -- npx -y tavily-mcp@latest"
  fi
else
  echo "→ tavily MCP already registered (skipped)"
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

#### 5e. Install CPP Codex Skills (issue #575)

The repo's `codex/skills/` holds a generated, CI-gated skill dir per CPP
command (`codex-skills-check`) - but until #575 nothing in `/cpp:init` or
`/cpp:update` copied it to `~/.codex/skills/`, so a freshly initialized Codex
tier had the MCP servers registered and **not one CPP skill installed**. The
observed state on the primary box was `~/.codex/skills/` containing only
`.system`.

The installer replaces each managed skill dir wholesale and prunes managed
orphans at the destination, so a skill CPP has dropped stops loading. Ownership
is decided by the GENERATED marker: hand-curated skill dirs, skills the user
wrote, and dotted runtime state such as `.system` are never touched.

```bash
if command -v codex &>/dev/null; then
  echo ""
  echo "=== Installing CPP Codex Skills ==="
  python3 "$CPP_DIR/scripts/codex-skill-sync.py" --install \
    || echo "WARNING: codex skill install failed (continuing)"
fi
```

Init only ever INSTALLS. Teardown of retired surfaces belongs to `/cpp:update`
Step 7.9, which asks before moving anything - a first-time init has no history
to reconcile.

#### 5f. Wire the Common-Memory Harness (issue #575)

`scripts/install-memory-harness.sh` links `scripts/cpp-memory` onto `PATH` and
installs the hand-authored Codex `/cpp-memory` prompt. Its header has always
said it is safe to re-run from `/cpp:update`, but no step ever invoked it, so
`cpp-memory` was missing from `PATH` unless run by hand. The Tier 2 symlink
loop now also links `scripts/cpp-memory` into `~/.claude/scripts/` (it links
every executable helper since issue #669), but that dir is not on `PATH` -
this harness remains the canonical `PATH` install. Idempotent.

```bash
bash "$CPP_DIR/scripts/install-memory-harness.sh" \
  || echo "WARNING: memory harness install failed (continuing)"
```

### Tier 6 Execution (Local Qwen Orchestration)

Only run when the user selected Tier 6. This tier layers on Tier 1 only; do
not force Tiers 2-5 first. Ask whether this machine SERVES the model or
CONSUMES a remote server before running the checks.

#### 6a. Verify the Qwen Code CLI Harness (no API key needed)

```bash
echo ""
echo "=== Tier 6: Local Qwen Orchestration ==="
echo ""

if command -v qwen &>/dev/null; then
  QWEN_CLI_VERSION=$(qwen --version 2>/dev/null || echo "unknown")
  echo "[x] Qwen Code CLI harness: $QWEN_CLI_VERSION"
  if ! qwen --help 2>&1 | grep -q -- "--output-format"; then
    echo "[!] This Qwen Code version lacks headless stream-json support"
    echo "    Upgrade: npm install -g @qwen-code/qwen-code"
  fi
else
  echo "[ ] Qwen Code CLI: not installed (required as the local-model harness)"
  echo "    NOTE: /qwen:* talks straight to Ollama - no cloud API key is required"
  # Ask user if they want to install; if yes:
  npm install -g @qwen-code/qwen-code
fi

# Flag the retired Codex-harness env var if still set (issue #745)
if [ -n "$QWEN_CODEX_PROFILE" ]; then
  echo "[~] QWEN_CODEX_PROFILE is set but no longer used (Codex harness retired,"
  echo "    issue #745). Remote machines need only QWEN_OLLAMA_URL. Unset it."
fi
```

#### 6b. Verify the Ollama Server and Model

```bash
QWEN_ENDPOINT="${QWEN_OLLAMA_URL:-http://127.0.0.1:11434}"
QWEN_MODEL="${QWEN_MODEL:-qwen3.8-code:latest}"

if curl -sf --max-time 5 "$QWEN_ENDPOINT/api/version" > /dev/null; then
  echo "[x] Ollama reachable at $QWEN_ENDPOINT"
else
  echo "[ ] Ollama NOT reachable at $QWEN_ENDPOINT"
  echo "    Serving machine: install and start Ollama (brew install ollama on macOS),"
  echo "    bind to the network with OLLAMA_HOST=0.0.0.0:11434 for LAN/tailnet use."
  echo "    Consumer machine: set QWEN_OLLAMA_URL=http://<serving-ip>:11434"
fi

if curl -sf --max-time 5 "$QWEN_ENDPOINT/api/tags" 2>/dev/null | grep -q "${QWEN_MODEL%%:*}"; then
  echo "[x] Model present: $QWEN_MODEL"
else
  echo "[ ] Model '$QWEN_MODEL' missing"
  echo "    On the serving machine:"
  echo "      ollama pull qwen3.8:27b"
  echo "      printf 'FROM qwen3.8:27b\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.7\nPARAMETER top_p 0.8\n' | ollama create qwen3.8-code -f -"
fi
```

#### 6c. Remote Access (consumer machines only)

No harness config file is needed for a remote Ollama server. Only offer to
persist the endpoint when `QWEN_ENDPOINT` is not
`http://127.0.0.1:11434`, or when the user said this machine consumes a
remote server. If the user identified it as a consumer but the endpoint is
still the localhost default, ask for the actual serving endpoint first and
use that value. Do not offer this on the serving machine: the localhost
default already works there, and a hardcoded export is a liability. This
closes the fresh-shell persistence gap tracked in issue #755.

Choose the rc file from the user's shell: `~/.zshrc` when `$SHELL` ends in
`zsh`, otherwise `~/.bashrc`:

```bash
case "${SHELL##*/}" in
  zsh) QWEN_RC="$HOME/.zshrc"; QWEN_RC_DISPLAY="~/.zshrc" ;;
  *) QWEN_RC="$HOME/.bashrc"; QWEN_RC_DISPLAY="~/.bashrc" ;;
esac
```

Show the actual `QWEN_ENDPOINT` and selected rc file in this prompt, not
placeholders:

```
=== Optional: Persist Qwen Endpoint ===

Remote Qwen commands need this setting in every fresh shell. I can add:
  # Claude Power Pack - Qwen serving endpoint (issue #755)
  export QWEN_OLLAMA_URL=${QWEN_ENDPOINT}

Add to ${QWEN_RC_DISPLAY}? [y/N]
```

If yes:
```bash
if grep -q 'QWEN_OLLAMA_URL' "$QWEN_RC" 2>/dev/null; then
  echo "-> QWEN_OLLAMA_URL already in $QWEN_RC_DISPLAY (skipped)"
else
  printf '\n# Claude Power Pack - Qwen serving endpoint (issue #755)\nexport QWEN_OLLAMA_URL=%s\n' "$QWEN_ENDPOINT" >> "$QWEN_RC"
  echo "✓ QWEN_OLLAMA_URL saved in $QWEN_RC_DISPLAY"
  echo "  Restart the shell or source $QWEN_RC_DISPLAY"
fi
```

If no:
```bash
echo "-> QWEN_OLLAMA_URL persistence skipped"
echo "  Add these exact lines to $QWEN_RC_DISPLAY later:"
printf '# Claude Power Pack - Qwen serving endpoint (issue #755)\nexport QWEN_OLLAMA_URL=%s\n' "$QWEN_ENDPOINT"
```

`/qwen:auto`, `/qwen:exec`, and `/qwen:status` derive the harness endpoint
from it (`$QWEN_OLLAMA_URL/v1` via `--openai-base-url`). If the user still
has a `QWEN_CODEX_PROFILE` export or a `[model_providers.qwen-local]` block
in `~/.codex/config.toml` from the retired Codex harness (issue #745), advise
removing them - a leftover `wire_api = "chat"` provider block hard-errors
every modern Codex invocation, including unrelated `/codex:*` commands.

#### 6d. Smoke Test (optional)

```bash
QWEN_ENDPOINT="${QWEN_OLLAMA_URL:-http://127.0.0.1:11434}"
timeout 600 qwen --openai-base-url "$QWEN_ENDPOINT/v1" --openai-api-key ollama \
  --auth-type openai -m "$QWEN_MODEL" \
  --approval-mode plan --output-format text \
  "Reply with exactly: QWEN-HARNESS-OK" < /dev/null 2>&1 | tail -3
```

A local 27B model takes minutes for a first turn (model load + prompt eval);
warn the user before running and offer to skip.

#### 6e. Always-On Second Opinion (optional)

The external mcp-second-opinion server (v2.3.0+) supports a keyless `ollama`
provider and an `ALWAYS_CONSULT_MODELS` list: models merged into EVERY
second-opinion consultation, so the local Qwen weighs in on every review at
zero cost. Offer to enable it:

```bash
# Check whether the running server already supports it
SO_HEALTH=$(curl -sf --max-time 5 "${SECOND_OPINION_URL:-http://127.0.0.1:8080}/" > /dev/null 2>&1 && echo up || echo down)
echo "second-opinion server: $SO_HEALTH"
```

- Server v2.3.0+ defaults are already always-on: `qwen-local` is in
  `DEFAULT_MODELS` and `ALWAYS_CONSULT_MODELS`, pointing at
  `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`) with model
  `OLLAMA_MODEL` (default `qwen3.8-code:latest`).
- If the second-opinion server runs on a DIFFERENT machine than the Qwen
  server, set `OLLAMA_BASE_URL=http://<qwen-serving-ip>:11434` in the
  server's environment (launchd plist or .env) and restart it.
- To disable the always-on behavior: `ALWAYS_CONSULT_MODELS=""` in the
  server's environment.
- Verify with the server's `health_check` tool: `always_consult_models`
  should list `qwen-local` and `ollama_configured` should be true.

### Tier 7 Execution (Local Gemma Orchestration)

Only run when the user selected Tier 7. It is independent of Tier 6: different
model, harness, env var, and config block.

#### 7a. Verify the OpenCode Harness (no API key needed)

```bash
echo ""
echo "=== Tier 7: Local Gemma Orchestration ==="
echo ""

if command -v opencode &>/dev/null; then
  echo "[x] OpenCode harness: $(opencode --version 2>/dev/null)"
else
  echo "[ ] OpenCode CLI: not installed (required as the local-model harness)"
  echo "    NOTE: /gemma:* talks straight to Ollama - no cloud API key is required"
  npm install -g opencode-ai
fi
```

#### 7b. Verify the Ollama Server and Model

```bash
GEMMA_ENDPOINT="${GEMMA_OLLAMA_URL:-http://127.0.0.1:11434}"
GEMMA_MODEL="${GEMMA_MODEL:-gemma4-code:latest}"

if curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/version" > /dev/null; then
  echo "[x] Ollama reachable at $GEMMA_ENDPOINT"
else
  echo "[ ] Ollama NOT reachable at $GEMMA_ENDPOINT"
  echo "    Serving machine: start it ('ollama serve') and retry."
  echo "    Consumer machine: set GEMMA_OLLAMA_URL=http://<serving-host>:11434"
  echo "    Shared-GPU host: another VM may currently hold the card."
fi

if curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/tags" 2>/dev/null | grep -q "${GEMMA_MODEL%%:*}"; then
  echo "[x] Model present: $GEMMA_MODEL"
else
  echo "[ ] Model '$GEMMA_MODEL' missing"
  echo "    On the serving machine:"
  echo "      ollama pull gemma4:31b-it-qat"
  echo "      printf 'FROM gemma4:31b-it-qat\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.2\n' > /tmp/Modelfile.gemma4-code"
  echo "      ollama create gemma4-code -f /tmp/Modelfile.gemma4-code"
  echo "    Then confirm 'ollama ps' still reports 100% GPU: the 64K context"
  echo "    bump costs VRAM, and one layer spilling to CPU collapses throughput."
fi
```

The `num_ctx` bump is not optional tuning. Ollama's 32K default silently
truncates long agent transcripts mid-run - no error, the model just loses the
start of its own session.

#### 7b.1 Persist the Gemma Endpoint (consumer machines only)

Only offer to persist the endpoint when `GEMMA_ENDPOINT` is not
`http://127.0.0.1:11434`, or when the user said this machine consumes a
remote server. If the user identified it as a consumer but the endpoint is
still the localhost default, ask for the actual serving endpoint first and
use that value. Do not offer this on the serving machine: the localhost
default already works there, and a hardcoded export is a liability.

This matters specifically for Gemma because the OpenCode provider's
`baseURL` is the literal `{env:GEMMA_OLLAMA_URL}`. OpenCode resolves it at
invocation time, so an unset variable does not preserve a discovered remote
endpoint - the lane silently addresses localhost (issue #755).

Choose the rc file from the user's shell: `~/.zshrc` when `$SHELL` ends in
`zsh`, otherwise `~/.bashrc`:

```bash
case "${SHELL##*/}" in
  zsh) GEMMA_RC="$HOME/.zshrc"; GEMMA_RC_DISPLAY="~/.zshrc" ;;
  *) GEMMA_RC="$HOME/.bashrc"; GEMMA_RC_DISPLAY="~/.bashrc" ;;
esac
```

Show the actual `GEMMA_ENDPOINT` and selected rc file in this prompt, not
placeholders:

```
=== Optional: Persist Gemma Endpoint ===

Remote Gemma commands need this setting in every fresh shell. I can add:
  # Claude Power Pack - Gemma serving endpoint (issue #755)
  export GEMMA_OLLAMA_URL=${GEMMA_ENDPOINT}

Add to ${GEMMA_RC_DISPLAY}? [y/N]
```

If yes:
```bash
if grep -q 'GEMMA_OLLAMA_URL' "$GEMMA_RC" 2>/dev/null; then
  echo "-> GEMMA_OLLAMA_URL already in $GEMMA_RC_DISPLAY (skipped)"
else
  printf '\n# Claude Power Pack - Gemma serving endpoint (issue #755)\nexport GEMMA_OLLAMA_URL=%s\n' "$GEMMA_ENDPOINT" >> "$GEMMA_RC"
  echo "✓ GEMMA_OLLAMA_URL saved in $GEMMA_RC_DISPLAY"
  echo "  Restart the shell or source $GEMMA_RC_DISPLAY"
fi
```

If no:
```bash
echo "-> GEMMA_OLLAMA_URL persistence skipped"
echo "  Add these exact lines to $GEMMA_RC_DISPLAY later:"
printf '# Claude Power Pack - Gemma serving endpoint (issue #755)\nexport GEMMA_OLLAMA_URL=%s\n' "$GEMMA_ENDPOINT"
```

#### 7c. Install the Provider and the Mechanical Fence

CPP ships both blocks as `templates/opencode-gemma.json`. Merge them into the
user's OpenCode config; never overwrite an existing file, which may hold their
own providers and agents.

```bash
OC_CONFIG="$HOME/.config/opencode/opencode.json"
mkdir -p "$(dirname "$OC_CONFIG")"

PYTHONPATH= python3 - "$CPP_DIR/templates/opencode-gemma.json" "$OC_CONFIG" <<'PYEOF'
import json, sys, pathlib
tmpl_path, cfg_path = sys.argv[1], pathlib.Path(sys.argv[2])
tmpl = json.loads(pathlib.Path(tmpl_path).read_text())
cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
cfg.setdefault("$schema", tmpl["$schema"])
for section in ("provider", "agent"):
    cfg.setdefault(section, {}).update(tmpl[section])
cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"[x] merged gemma-ollama provider + gemma-implementer agent into {cfg_path}")
PYEOF
```

Two things are being installed here, and the second is the safety-critical one:

- **`gemma-ollama` provider** - pinned to the `ai-sdk-ollama` npm package,
  which speaks Ollama's NATIVE `/api/chat`. Do not switch it to
  `@ai-sdk/openai-compatible`, even though that is what OpenCode's own docs
  suggest for Ollama: the `/v1` shim silently discards tool calls once the
  system prompt passes ~1,600 tokens (ollama/ollama#14958), and OpenCode's
  agentic prompt measures ~6,900. The lane would fail as prose, not as an
  error. `baseURL` is left as the literal `{env:GEMMA_OLLAMA_URL}` so one
  config works on the serving machine and every consumer machine.
- **`gemma-implementer` agent** - the MECHANICAL FENCE. OpenCode has no
  `--sandbox` flag, so these permission rules are what stop a wandering local
  model from running the lifecycle itself: ref-modifying git, all `gh`,
  deploy/docker/kubectl/terraform, webfetch/websearch, and writes outside the
  run directory are denied. `/gemma:auto` and `/gemma:exec` both refuse to run
  without it.

#### 7d. Smoke Test (recommended)

This is the check that actually proves the native-API path works, because it
runs a real `opencode run` and therefore inherits the full system prompt. A
bare curl probe passes on both `/v1` and `/api/chat` and proves nothing.

```bash
SMOKE_DIR=$(mktemp -d)
echo "probe" > "$SMOKE_DIR/probe.txt"
GEMMA_OLLAMA_URL="$GEMMA_ENDPOINT" timeout 120 opencode run \
  --dir "$SMOKE_DIR" \
  -m "gemma-ollama/${GEMMA_MODEL%%:*}" \
  --agent gemma-implementer --format json --auto \
  "List the files in the current directory using your tools." 2>&1 | grep -c '"type":"tool_use"'
rm -rf "$SMOKE_DIR"
```

A count of 1 or more means tool calling survives the full harness. Zero is the
`/v1` signature - re-check the provider block from 7c. Run `/gemma:status` for
the full diagnosis.

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
  ✓ Tier 6: Local Qwen orchestration (optional - only if selected)
  ✓ Tier 7: Local Gemma orchestration (optional - only if selected)

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
     /project:next    - See what to work on
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
  • /cpp:load-best-practices - Community tips

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
