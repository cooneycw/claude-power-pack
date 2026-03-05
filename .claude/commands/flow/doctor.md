---
description: Diagnose flow workflow setup and environment
allowed-tools: Bash(git:*), Bash(gh:*), Bash(command:*), Bash(test:*), Bash(ls:*), Bash(readlink:*), Bash(grep:*), Bash(make:*), Bash(python3:*), Bash(PYTHONPATH=*), Read
---

# Flow: Doctor — Diagnose Workflow Environment

Check that the environment is properly configured for the `/flow` workflow.

## Instructions

When the user invokes `/flow:doctor`, run all diagnostic checks and present a single report.

### Step 1: Environment Prerequisites

Check required tools:

```bash
# git
git --version 2>/dev/null && echo "PASS" || echo "FAIL"

# gh CLI
gh --version 2>/dev/null && echo "PASS" || echo "FAIL"

# gh authentication
gh auth status 2>/dev/null && echo "PASS" || echo "FAIL"

# uv (optional but recommended)
uv --version 2>/dev/null || echo "NOT_FOUND"
```

### Step 2: Git Repository State

```bash
# In a git repository?
git rev-parse --show-toplevel 2>/dev/null || echo "NOT_A_REPO"

# Remote origin configured?
git remote get-url origin 2>/dev/null || echo "NO_REMOTE"

# Default branch
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'

# User identity
git config user.name 2>/dev/null || echo "NOT_SET"
git config user.email 2>/dev/null || echo "NOT_SET"
```

### Step 3: Makefile Targets

```bash
# Makefile exists?
if [ -f "Makefile" ]; then
  # List standard targets (lint, test, deploy, format, etc.)
  grep -E '^[a-zA-Z_-]+:' Makefile | sed 's/:.*//' | sort
else
  echo "NO_MAKEFILE"
fi
```

Report which of these standard targets exist: `lint`, `test`, `format`, `deploy`.

**If no Makefile found:** Detect the framework and suggest the matching template:

```bash
# Only if CPP lib is available
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir/lib/cicd" ]; then CPP_DIR="$dir"; break; fi
done

if [ -n "$CPP_DIR" ] && [ ! -f "Makefile" ]; then
  DETECTED=$(PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -c "
from lib.cicd.detector import detect_framework
info = detect_framework('.')
print(f'{info.framework.value}:{info.package_manager.value}')
" 2>/dev/null)
  echo "Detected: $DETECTED"
fi
```

Use the detection result to suggest the specific template file in the Actions Needed section (e.g., `django-uv.mk` for Django projects, `python-uv.mk` for Python+uv).

### Step 4: Hooks Configuration

```bash
# hooks.json exists?
if [ -f ".claude/hooks.json" ]; then
  # Check for expected hooks
  grep -l "SessionStart\|PreToolUse\|PostToolUse" .claude/hooks.json
fi
```

Check for the three expected hook types:
- **SessionStart**: Upstream change detection
- **PreToolUse (Bash)**: Dangerous command blocking via `hook-validate-command.sh`
- **PostToolUse (Bash/Read)**: Secret masking via `hook-mask-output.sh`

### Step 5: Scripts Availability

Check that core scripts exist in `~/.claude/scripts/`:

```bash
for script in prompt-context.sh worktree-remove.sh hook-mask-output.sh hook-validate-command.sh secrets-mask.sh; do
  if [ -x "$HOME/.claude/scripts/$script" ]; then
    echo "PASS $script"
  elif [ -f "$HOME/.claude/scripts/$script" ]; then
    echo "WARN $script (not executable)"
  else
    echo "FAIL $script"
  fi
done
```

### Step 6: Active Worktrees

```bash
git worktree list
```

For each worktree (skip main), check:
- Branch name and linked issue number
- Uncommitted changes (`git -C <path> status --porcelain | wc -l`)
- Unpushed commits (`git -C <path> rev-list --count origin/main..HEAD 2>/dev/null`)

### Step 7: GitHub Integration

```bash
# Can list issues?
gh issue list --limit 1 --json number 2>/dev/null && echo "PASS" || echo "FAIL"

# Can list PRs?
gh pr list --limit 1 --json number 2>/dev/null && echo "PASS" || echo "FAIL"
```

### Step 7b: CI/CD Readiness

Check CI/CD configuration and tooling. This section is **optional** — skip entirely if `lib/cicd` is not available.

```bash
# Locate CPP source for lib/cicd
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done
```

If `CPP_DIR` is found, run these checks:

```bash
# 1. cicd.yml config file
[ -f ".claude/cicd.yml" ] && echo "PASS cicd.yml" || echo "MISSING cicd.yml"

# 2. Framework detection
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd detect --quiet 2>/dev/null

# 3. Makefile completeness (uses lib/cicd check)
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd check --summary 2>/dev/null

# 4. Health check configuration
grep -q "endpoints:" .claude/cicd.yml 2>/dev/null && echo "PASS health endpoints" || echo "MISSING health endpoints"
grep -q "smoke_tests:" .claude/cicd.yml 2>/dev/null && echo "PASS smoke tests" || echo "MISSING smoke tests"

# 5. CI pipeline files
[ -f ".github/workflows/ci.yml" ] || [ -f ".woodpecker.yml" ] && echo "PASS CI pipeline" || echo "MISSING CI pipeline"

# 6. Dockerfile (optional)
[ -f "Dockerfile" ] && echo "PASS Dockerfile" || echo "OPTIONAL Dockerfile"
```

If `CPP_DIR` is not found, skip this entire section and note in the report:
```
CI/CD Readiness: skipped (lib/cicd not available)
```

### Step 7c: MCP Server Connectivity

Check whether MCP servers are reachable on their expected ports:

```bash
echo ""
echo "MCP Server Connectivity:"

MCP_ISSUES=0
for entry in "8080:second-opinion" "8081:playwright-persistent"; do
  PORT="${entry%%:*}"
  NAME="${entry#*:}"
  if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "  [x] $NAME (port $PORT): reachable"
  elif ss -tlnp 2>/dev/null | grep -q ":${PORT} " 2>/dev/null; then
    echo "  [~] $NAME (port $PORT): port open (no /health endpoint)"
  else
    echo "  [ ] $NAME (port $PORT): not reachable"
    MCP_ISSUES=$((MCP_ISSUES + 1))
  fi
done

if (( MCP_ISSUES > 0 )); then
  echo "  Status: $MCP_ISSUES server(s) not reachable"
else
  echo "  Status: All MCP servers reachable"
fi
```

### Step 8: Generate Report

Output a single diagnostic report in this format:

```markdown
## Flow Doctor — {repo}

### Environment

| Check | Status | Details |
|-------|--------|---------|
| git | ✅ | v2.43.0 |
| gh CLI | ✅ | v2.62.0 |
| gh auth | ✅ | Logged in as {user} |
| uv | ✅ | v0.5.14 |

### Repository

| Check | Status | Details |
|-------|--------|---------|
| Git repo | ✅ | claude-power-pack |
| Remote | ✅ | github.com/cooneycw/claude-power-pack |
| User identity | ✅ | {name} <{email}> |

### Workflow Readiness

| Check | Status | Details |
|-------|--------|---------|
| Makefile | ✅/⚠️/❌ | Targets: lint, test, deploy / Not found |
| hooks.json | ✅/❌ | 3 hooks configured / Not found |
| validate-command hook | ✅/❌ | ~/.claude/scripts/hook-validate-command.sh |
| mask-output hook | ✅/❌ | ~/.claude/scripts/hook-mask-output.sh |
| prompt-context.sh | ✅/❌ | Shell prompt context |
| worktree-remove.sh | ✅/❌ | Safe worktree removal |
| secrets-mask.sh | ✅/❌ | Output masking filter |

### MCP Server Connectivity

| Server | Port | Status | Details |
|--------|------|--------|---------|
| second-opinion | 8080 | ✅/⚠️/❌ | Reachable / Port open (no /health) / Not reachable |
| playwright-persistent | 8081 | ✅/⚠️/❌ | Reachable / Port open (no /health) / Not reachable |

### Active Worktrees

| Worktree | Issue | Branch | Status |
|----------|-------|--------|--------|
| ../{repo}-issue-42 | #42 | issue-42-fix-auth | 3 dirty, 1 unpushed |
| ../{repo}-issue-55 | #55 | issue-55-add-tests | Clean |

*No worktrees* → "No active worktrees. Run `/flow:start <issue>` to begin."

### GitHub Integration

| Check | Status |
|-------|--------|
| List issues | ✅/❌ |
| List PRs | ✅/❌ |

### CI/CD & Verification

*(Only shown when lib/cicd is available. If not available, show: "CI/CD Readiness: skipped (lib/cicd not available — install CPP for CI/CD features)")*

| Check | Status | Details |
|-------|--------|---------|
| .claude/cicd.yml | ✅/❌ | Config file present / missing |
| Framework detected | ✅ | Python (uv) / Node (npm) / etc. |
| Makefile completeness | ✅/⚠️ | 6/7 targets (typecheck missing) |
| Health endpoints | ✅/⚠️ | 2 configured / Not configured |
| Smoke tests | ✅/⚠️ | 3 configured / Not configured |
| CI pipeline | ✅/❌ | .github/workflows/ci.yml / Not found |
| Dockerfile | ⚠️ | Not configured (optional) |

### Actions Needed

(Only if there are failures or warnings)

1. ❌ **Makefile missing** — Create a Makefile with `lint`, `test`, and `deploy` targets for `/flow:finish` and `/flow:deploy`. Run `/cicd:init` to auto-generate from a stack-specific template, or copy one manually:
   - Python (uv): `cp ~/Projects/claude-power-pack/templates/makefiles/python-uv.mk Makefile`
   - Python (pip): `cp ~/Projects/claude-power-pack/templates/makefiles/python-pip.mk Makefile`
   - Django (uv): `cp ~/Projects/claude-power-pack/templates/makefiles/django-uv.mk Makefile`
   - Node (npm): `cp ~/Projects/claude-power-pack/templates/makefiles/node-npm.mk Makefile`
   - Node (yarn): `cp ~/Projects/claude-power-pack/templates/makefiles/node-yarn.mk Makefile`
   - Go: `cp ~/Projects/claude-power-pack/templates/makefiles/go.mk Makefile`
   - Rust: `cp ~/Projects/claude-power-pack/templates/makefiles/rust.mk Makefile`
   - Monorepo: `cp ~/Projects/claude-power-pack/templates/makefiles/multi.mk Makefile`
2. ❌ **worktree-remove.sh not found** — Run: `ln -sf ~/Projects/claude-power-pack/scripts/worktree-remove.sh ~/.claude/scripts/`
3. ⚠️ **uv not installed** — Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
4. ❌ **cicd.yml missing** — Run `/cicd:init` to auto-detect framework and generate configuration
5. ⚠️ **Makefile gaps** — Run `/cicd:check` for details or `/cicd:init` to add missing targets
6. ❌ **No CI pipeline** — Run `/cicd:pipeline` to generate GitHub Actions or Woodpecker CI config
7. ⚠️ **No health endpoints** — Add `health.endpoints` to `.claude/cicd.yml` for post-deploy verification
8. ⚠️ **No smoke tests** — Add `health.smoke_tests` to `.claude/cicd.yml` for post-deploy testing
9. ⚠️ **MCP server(s) not reachable** — Start servers: `cd mcp-second-opinion && ./start-server.sh` (or use stdio transport)

*All checks passed!* → "Environment is ready for `/flow` workflow."
```

## Status Symbols

- ✅ = Check passed
- ⚠️ = Optional/non-critical issue
- ❌ = Required check failed — action needed

## Notes

- This is a read-only diagnostic — it never modifies anything
- `uv` is recommended but not required (⚠️ if missing, not ❌)
- Makefile is recommended but not required (⚠️ if missing)
- Scripts and hooks are ❌ if missing since they provide security protection
- Keep the report concise — one table per section, actions at the end
