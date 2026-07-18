---
description: Full project scaffolding orchestrator - zero to GitHub repo in one command
allowed-tools: Bash(mkdir:*), Bash(cd:*), Bash(ls:*), Bash(git:*), Bash(gh:*), Bash(uv:*), Bash(npm:*), Bash(cat:*), Bash(test:*), Bash(echo:*), Bash(cp:*), Bash(ln:*), Bash(touch:*), Bash(PYTHONPATH=:*), Read, Write, Glob, Grep, AskUserQuestion, Skill
---

# /project:init - Full Project Scaffolding

Create a new project from zero to pushed GitHub repo in one command.

> **Config scaffolding (CLAUDE.md, skills, hooks)?** Claude Code's native
> **`/init`** (upgraded to an interview-style scaffolder) generates a
> codebase-aware CLAUDE.md and scaffolds skills/hooks - so `/project:init`
> delegates that half to `/init` rather than hand-rolling it. This command is
> the *zero-to-GitHub-repo orchestrator* native `/init` does not provide: repo
> creation and push, framework scaffold, Makefile/CI wiring, CPP toolkit
> install, and spec structure. Run both for a complete bootstrap - this command
> invokes `/init` for you in Step 4.

## Arguments

- `PROJECT_NAME` (required): Name of the project (e.g., `my-awesome-app`)

## Orchestration Flow

```
/project:init my-awesome-app
  Step 1: Validate & create ~/Projects/my-awesome-app
  Step 2: Select framework, generate scaffold
  Step 3: Initialize git, push to GitHub
  Step 4: Makefile/CI (lib/cicd) + CPP toolkit install; delegate CLAUDE.md/skills/hooks to native /init
  Step 5: Initial spec (optional) + issue sync
  Step 6: Summary
```

---

## Step 1: Validate & Create Project Directory

```bash
PROJECT_NAME="$1"

# Validate project name
if [[ ! "$PROJECT_NAME" =~ ^[a-z][a-z0-9-]*$ ]]; then
    echo "ERROR: Project name must be lowercase, start with a letter, and contain only letters, numbers, and hyphens."
    echo "Example: my-awesome-app"
    exit 1
fi

# Check if directory already exists
if [ -d "$HOME/Projects/$PROJECT_NAME" ]; then
    echo "Directory ~/Projects/$PROJECT_NAME already exists."
    echo "Checking state for resume..."
fi
```

If the directory already exists, check what steps have been completed and resume from the first incomplete step:

- Has `pyproject.toml` / `package.json` / `go.mod` / `Cargo.toml`? → Step 2 done.
- Has `.git/`? → Step 3 partially done. Check if GitHub remote exists.
- Has `Makefile` + `.claude/cicd.yml`? → cicd:init done.
- Has `.claude/commands` symlink? → cpp:init done.
- Has `.specify/`? → spec structure already present.

If the directory doesn't exist:

```bash
mkdir -p "$HOME/Projects/$PROJECT_NAME"
cd "$HOME/Projects/$PROJECT_NAME"
echo "Created ~/Projects/$PROJECT_NAME"
```

Report: `Step 1/6: Project directory ready at ~/Projects/{PROJECT_NAME}`

---

## Step 2: Framework Selection & Scaffold

Ask the user which framework to use with `AskUserQuestion`:

**Options:**

| Framework | What's Generated |
|-----------|-----------------|
| **Python (uv)** | `pyproject.toml`, `src/{pkg}/__init__.py`, `tests/conftest.py` |
| **Node.js (npm)** | `package.json`, `src/index.ts`, `tests/` |
| **Go** | `go.mod`, `cmd/main.go`, `internal/` |
| **Rust** | `Cargo.toml`, `src/main.rs` |

### Python Scaffold

```bash
PROJECT_NAME="..."
PKG_NAME=$(echo "$PROJECT_NAME" | tr '-' '_')

# pyproject.toml (PEP 621 + uv)
cat > pyproject.toml << PYEOF
[project]
name = "$PROJECT_NAME"
version = "0.1.0"
description = ""
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.pytest.ini_options]
testpaths = ["tests"]
PYEOF

# Source directory
mkdir -p "src/$PKG_NAME"
cat > "src/$PKG_NAME/__init__.py" << 'INITEOF'
"""$PROJECT_NAME."""

__version__ = "0.1.0"
INITEOF

# Tests
mkdir -p tests
cat > tests/conftest.py << 'TESTEOF'
"""Shared test fixtures."""
TESTEOF

cat > tests/test_placeholder.py << 'TESTEOF'
"""Placeholder test to verify setup."""


def test_import():
    """Verify the package can be imported."""
    import importlib
    mod = importlib.import_module("$PKG_NAME")
    assert hasattr(mod, "__version__")
TESTEOF

# Initialize uv
uv sync
```

### Node.js Scaffold

```bash
PROJECT_NAME="..."

cat > package.json << PKGEOF
{
  "name": "$PROJECT_NAME",
  "version": "0.1.0",
  "description": "",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "lint": "eslint src/",
    "test": "vitest run",
    "dev": "tsx watch src/index.ts"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "vitest": "^2.0.0"
  }
}
PKGEOF

cat > tsconfig.json << TSEOF
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
TSEOF

mkdir -p src tests
echo 'console.log("Hello from $PROJECT_NAME");' > src/index.ts
cat > tests/placeholder.test.ts << 'TESTEOF'
import { describe, it, expect } from 'vitest';

describe('placeholder', () => {
  it('passes', () => {
    expect(true).toBe(true);
  });
});
TESTEOF

npm install
```

### Go Scaffold

```bash
PROJECT_NAME="..."
# Ask user for module path or default to github.com/USER/PROJECT_NAME
MODULE_PATH="github.com/$(gh api user --jq '.login')/$PROJECT_NAME"

cat > go.mod << GOEOF
module $MODULE_PATH

go 1.22
GOEOF

mkdir -p cmd internal
cat > cmd/main.go << 'GOEOF'
package main

import "fmt"

func main() {
	fmt.Println("Hello from $PROJECT_NAME")
}
GOEOF
```

### Rust Scaffold

```bash
PROJECT_NAME="..."

cat > Cargo.toml << RUSTEOF
[package]
name = "$PROJECT_NAME"
version = "0.1.0"
edition = "2021"

[dependencies]
RUSTEOF

mkdir -p src
cat > src/main.rs << 'RUSTEOF'
fn main() {
    println!("Hello from $PROJECT_NAME");
}
RUSTEOF
```

### .gitignore (all frameworks)

Generate a `.gitignore` appropriate for the selected framework. Use templates from GitHub's gitignore collection or create a sensible default.

**Python:**
```
__pycache__/
*.py[cod]
.venv/
dist/
build/
*.egg-info/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
.env
.claude/settings.local.json
```

**Node:**
```
node_modules/
dist/
build/
.next/
coverage/
.env
.claude/settings.local.json
```

**Go:**
```
bin/
coverage.out
.env
.claude/settings.local.json
```

**Rust:**
```
target/
.env
.claude/settings.local.json
```

Report: `Step 2/6: {Framework} scaffold created`

---

## Step 3: Git & GitHub

```bash
# Initialize git
git init

# Configure git user if not set globally
if ! git config user.name &>/dev/null; then
    echo "Git user.name not configured. Please set it:"
    # Ask user for name and email, or use gh auth info
    GH_USER=$(gh api user --jq '.login' 2>/dev/null)
    GH_EMAIL=$(gh api user --jq '.email // empty' 2>/dev/null)
    # Fall back to asking
fi

# Initial commit
git add .
git commit -m "Initial project scaffold

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

Ask the user about repository visibility using `AskUserQuestion`:

**Options:**
- **Private (Recommended)** - Only you and collaborators can see the repo
- **Public** - Anyone can see the repo

```bash
VISIBILITY="--private"  # or "--public" based on user choice

# Create GitHub repo and push
gh repo create "$PROJECT_NAME" $VISIBILITY --source=. --push
```

If `gh repo create` fails (e.g., repo name taken), report the error and suggest alternatives.

Report: `Step 3/6: Git initialized, pushed to github.com/{user}/{PROJECT_NAME}`

---

## Step 4: CPP Setup (Orchestrate Sub-Commands)

Run each sub-command in sequence. These are orchestrated directly - NOT by invoking `/skill` (which would require user interaction for each one). Instead, execute the same logic as each command but non-interactively with sensible defaults.

### 4a: Makefile Generation (from lib/cicd)

The `lib/cicd` library can detect the framework and generate a Makefile:

```bash
# Locate CPP source
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
    if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
        CPP_DIR="$dir"
        break
    fi
done

if [ -z "$CPP_DIR" ]; then
    echo "WARNING: claude-power-pack not found. Skipping cicd:init."
else
    # Generate Makefile from detected framework
    if [ ! -f "Makefile" ]; then
        PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -c "
from lib.cicd.makefile import generate_makefile
content = generate_makefile('.')
print(content)
" > Makefile
        echo "Generated Makefile from detected framework"
    fi

    # Create .claude/cicd.yml config
    mkdir -p .claude
    if [ ! -f ".claude/cicd.yml" ]; then
        cp "$CPP_DIR/templates/cicd.yml.example" .claude/cicd.yml 2>/dev/null || true
        echo "Created .claude/cicd.yml"
    fi
fi
```

### 4b: CPP Init (symlinks)

```bash
if [ -n "$CPP_DIR" ]; then
    mkdir -p .claude

    # Symlink commands
    if [ ! -L ".claude/commands" ] && [ ! -d ".claude/commands" ]; then
        ln -sf "$CPP_DIR/.claude/commands" .claude/commands
        echo "Symlinked .claude/commands"
    fi

    # Symlink skills
    if [ ! -L ".claude/skills" ] && [ ! -d ".claude/skills" ]; then
        ln -sf "$CPP_DIR/.claude/skills" .claude/skills
        echo "Symlinked .claude/skills"
    fi

    # Copy hooks.json
    if [ ! -f ".claude/hooks.json" ]; then
        cp "$CPP_DIR/.claude/hooks.json" .claude/hooks.json 2>/dev/null || true
        echo "Copied hooks.json"
    fi
fi
```

### 4c: Config Scaffold (delegate to native /init)

Do NOT hand-roll CLAUDE.md, skills, or hooks. Delegate this half to Claude Code's
native `/init`, which interviews the project and generates a codebase-aware
CLAUDE.md (and scaffolds skills/hooks) far better than a fixed template. CPP then
layers its CI/CD governance directives on top so nothing is lost.

1. **Run native `/init`** to scaffold the config files. Invoke it with the `Skill`
   tool (`skill: "init"`). It reads the framework scaffold from Step 2 and the
   Makefile from Step 4a to produce a project-aware CLAUDE.md.

   - If a CLAUDE.md already exists (resumed run), skip `/init` - it is only for the
     initial scaffold.
   - In a fully non-interactive context where `/init` cannot run, write a minimal
     CLAUDE.md stub (project name + one-line overview) so Step 4d and later steps
     have something to build on; `/claude-md:lint` below fills in the governance
     directives regardless.

2. **Ensure CPP CI/CD governance directives.** Native `/init` does not know CPP's
   Makefile-first protocol, quality-gates table, or troubleshooting workflow. Run
   the `/claude-md:lint` command against the freshly generated CLAUDE.md and apply
   its recommendations so the file includes:

   - **CI/CD Protocol** - Makefile targets are the single source of truth; never
     run raw build/test/deploy commands.
   - **Troubleshooting Protocol** - run `make lint`/`make test` before manual
     debugging; fix app code AND the CI/CD process; verify via `make verify`.
   - **Quality Gates** table - `make lint`, `make test`, `make verify`,
     `make troubleshoot`.
   - **Docker Conventions** (only if a Dockerfile / docker-compose is present) -
     `make docker-*` targets over raw `docker` commands.

The net effect: `/init` owns the config-scaffold generation (its native job), and
CPP owns the governance overlay - no duplicated CLAUDE.md template to maintain.

### 4d: Spec Init

```bash
if [ ! -d ".specify" ]; then
    mkdir -p .specify/memory .specify/specs .specify/templates .specify/scripts

    # Create constitution template
    DATE=$(date +%Y-%m-%d)
    cat > .specify/memory/constitution.md << CONSTEOF
# Project Constitution

> Governing principles for $PROJECT_NAME.
> All specifications and implementations must align with these principles.

---

## Core Principles

### P1: {First Principle}

{Description of the principle and how it guides development.}

### P2: {Second Principle}

{Description of the principle and how it guides development.}

---

## Development Workflow

1. Write specification before code
2. Review spec for completeness
3. Create technical plan
4. Break into tasks
5. Sync tasks to issues
6. Implement with tests

---

*Created: $DATE*
CONSTEOF

    # Copy templates if CPP source is available
    if [ -n "$CPP_DIR" ] && [ -d "$CPP_DIR/.specify/templates" ]; then
        cp "$CPP_DIR/.specify/templates/"*.md .specify/templates/ 2>/dev/null || true
    fi

    echo "Initialized .specify/"
fi
```

Report: `Step 4/6: CPP setup complete - Makefile, CPP toolkit, CLAUDE.md (via native /init) + governance, .specify/`

---

## Step 5: Initial Spec (Mandatory)

Create an initial feature specification for the project. This step is mandatory to
ensure every project starts with a spec-driven foundation. The spec can be minimal
and refined later.

Ask the user with `AskUserQuestion`:

**Question:** "What is the first feature or MVP for this project? (Enter a name or press enter to use the project name)"

Use the project name as the default feature name if the user doesn't provide one.

```bash
FEATURE_NAME="$PROJECT_NAME"
mkdir -p ".specify/specs/$FEATURE_NAME"

# Create spec.md, plan.md, tasks.md from templates or minimal stubs
cat > ".specify/specs/$FEATURE_NAME/spec.md" << SPECEOF
# Feature Specification: $FEATURE_NAME

## Overview

{Brief description of the project's first feature or MVP.}

## User Stories

### US1: {Story Title}
**As a** {role}, **I want** {capability}, **So that** {benefit}.

**Acceptance Criteria:**
- [ ] {Criterion}

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | {Requirement} | Must |

## Success Criteria
- [ ] All acceptance criteria met
- [ ] Tests passing
SPECEOF

cat > ".specify/specs/$FEATURE_NAME/plan.md" << PLANEOF
# Implementation Plan: $FEATURE_NAME

## Summary
{Technical approach}

## Architecture
{Component design}

## Dependencies
| Package | Purpose |
|---------|---------|

## Phases
| Phase | Tasks | Dependencies |
|-------|-------|--------------|
PLANEOF

cat > ".specify/specs/$FEATURE_NAME/tasks.md" << TASKEOF
# Tasks: $FEATURE_NAME

## Format
\`[ID] [P?] [Story] Description\`

## Wave 1: Foundation
- [ ] **T001** [US1] {First task}

## Issue Sync
| Task | Issue | Status |
|------|-------|--------|
TASKEOF

echo "Created spec: .specify/specs/$FEATURE_NAME/"
```

Then ask: "Sync tasks to GitHub issues now?"
- **Yes** → run `./scripts/speckit-tasks-to-issues.sh`
- **Skip** → sync later

Report: `Step 5/6: Initial spec created` or `Step 5/6: Skipped`

---

## Step 6: Final Commit & Summary

```bash
# Stage all new CPP/spec files
git add .
git diff --cached --stat

# Commit the CPP setup
git commit -m "chore: add CPP setup, Makefile, and spec structure

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

# Push
git push origin main
```

Report the final summary:

```
Project created: {PROJECT_NAME}

  Directory:  ~/Projects/{PROJECT_NAME}
  GitHub:     github.com/{user}/{PROJECT_NAME} (private)
  Framework:  {Framework} ({PackageManager})
  Makefile:   lint, test, build, deploy, clean, verify
  CPP:        Commands + Skills + Hooks
  Spec:       .specify/ initialized

Next steps:
  cd ~/Projects/{PROJECT_NAME}
  /project:next              # See recommended actions
  /spec:adopt                # Adopt official spec-kit for feature specs (optional)
  /flow:start {N}            # Start working on an issue
```

---

## Error Handling

At each step, if something fails:

```
/project:init stopped at Step N/6: {Step Name}

  Failed: [description]
  Fix:    [suggestion]

  To resume: /project:init {PROJECT_NAME}
  (Idempotent - completed steps will be skipped)
```

Key failure scenarios:
- **Invalid project name:** Stop at Step 1 with format guidance
- **Directory exists with work:** Resume from first incomplete step
- **gh not authenticated:** Stop at Step 3, suggest `gh auth login`
- **Repo name taken on GitHub:** Suggest alternative name or link to existing
- **CPP source not found:** Skip Step 4 with warning, still complete other steps
- **uv/npm not installed:** Warn but continue (user can install deps later)

## Notes

- This command is **idempotent** - safe to run again if interrupted
- Each step checks for prior completion before executing
- The scaffold is minimal - just enough to start coding
- Framework detection from `lib/cicd` is reused for Makefile generation
- Config scaffolding (CLAUDE.md, skills, hooks) is **delegated to native `/init`**
  (Step 4c); CPP keeps only the governance overlay via `/claude-md:lint`. CPP does
  not maintain its own CLAUDE.md template
- The repo-bootstrap steps (cicd:init Makefile, cpp:init toolkit install) are
  executed inline with sensible defaults, not via interactive `/skill`; native
  `/init` is the one exception, invoked so it can run its interview
