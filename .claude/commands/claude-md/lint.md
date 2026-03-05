---
description: Lint CLAUDE.md for missing CI/CD, Docker, and troubleshooting directives
allowed-tools: Bash(cat:*), Bash(grep:*), Bash(test:*), Bash(ls:*), Bash(PYTHONPATH=*), Bash(python3:*), Read, Glob, Grep
---

# /claude-md:lint — CLAUDE.md Health Check

Audit a project's CLAUDE.md to ensure it includes essential directives for CI/CD protocols, Docker conventions, and troubleshooting workflows.

## Why This Matters

CLAUDE.md governs agent behavior. Without explicit CI/CD directives, Claude Code agents will:
- Run raw `docker compose` instead of `make docker-*` targets
- Debug ad-hoc without following Makefile pipelines
- Skip lint/test gates when troubleshooting
- Make manual fixes that break CI/CD alignment

---

## Step 1: Detect Project Context

```bash
# Check for CLAUDE.md
if [ ! -f "CLAUDE.md" ]; then
    echo "NO CLAUDE.md FOUND"
    echo ""
    echo "This project has no CLAUDE.md. Create one with /project:init or manually."
    exit 1
fi

# Detect framework
HAS_MAKEFILE="no"
HAS_DOCKER="no"
HAS_CICD_YML="no"
FRAMEWORK="unknown"

[ -f "Makefile" ] && HAS_MAKEFILE="yes"
[ -f "Dockerfile" ] || [ -f "docker-compose.yml" ] || [ -f "docker-compose.yaml" ] && HAS_DOCKER="yes"
[ -f ".claude/cicd.yml" ] && HAS_CICD_YML="yes"

# Detect framework from markers
[ -f "pyproject.toml" ] || [ -f "setup.py" ] && FRAMEWORK="python"
[ -f "package.json" ] && FRAMEWORK="node"
[ -f "go.mod" ] && FRAMEWORK="go"
[ -f "Cargo.toml" ] && FRAMEWORK="rust"
```

---

## Step 2: Read and Audit CLAUDE.md

Read the project's CLAUDE.md and check for the presence of each required directive category.

### Required Sections

Check for these directive categories (case-insensitive, flexible matching):

| Category | Check For | Weight |
|----------|-----------|--------|
| **CI/CD Protocol** | Mentions Makefile targets for build/test/deploy | REQUIRED |
| **Troubleshooting Protocol** | Mentions running lint/test before debugging, fixing CI/CD alongside code | REQUIRED |
| **Quality Gates** | Mentions `make lint`, `make test`, `make verify`, or equivalent | REQUIRED |
| **Docker Conventions** | Mentions `make docker-*` targets (only if Docker files exist) | CONDITIONAL |
| **Deployment Protocol** | Mentions `make deploy` or deployment workflow | RECOMMENDED |
| **Available Commands** | Lists Makefile targets or build commands | RECOMMENDED |

### Detection Patterns

For each category, search CLAUDE.md for these patterns:

**CI/CD Protocol** (any of):
- `make lint`, `make test`, `make build`, `make deploy`
- `Makefile target`
- `CI/CD protocol` or `cicd`
- `quality gate`

**Troubleshooting Protocol** (any of):
- `troubleshoot`
- `before debugging`
- `fix.*CI/CD` or `fix.*Makefile` or `fix.*pipeline`
- `root cause`
- `never bypass`

**Quality Gates** (any of):
- `make lint`
- `make test`
- `make verify`
- `quality gate`
- `/flow:finish`

**Docker Conventions** (any of, only checked if Docker files exist):
- `make docker`
- `docker-build`, `docker-up`, `docker-down`
- `not raw.*docker`

**Deployment Protocol** (any of):
- `make deploy`
- `deployment`
- `/flow:deploy`

**Available Commands** (any of):
- A table or list containing `make` targets
- `## Commands` or `## Makefile` or `## Available`

---

## Step 3: Score and Report

Present results as a health report:

```markdown
## CLAUDE.md Lint Report

**Project:** {project name from directory}
**Framework:** {detected framework}
**Makefile:** {yes/no}
**Docker:** {yes/no}
**cicd.yml:** {yes/no}

### Directive Coverage

| Category | Status | Details |
|----------|--------|---------|
| CI/CD Protocol | PASS/FAIL | {what was found or missing} |
| Troubleshooting Protocol | PASS/FAIL | {what was found or missing} |
| Quality Gates | PASS/FAIL | {what was found or missing} |
| Docker Conventions | PASS/FAIL/SKIP | {what was found, or "No Docker files"} |
| Deployment Protocol | PASS/WARN | {what was found or missing} |
| Available Commands | PASS/WARN | {what was found or missing} |

### Score: {N}/6 ({percentage}%)

### {HEALTHY / NEEDS ATTENTION / UNHEALTHY}
```

**Scoring:**
- PASS on REQUIRED = 1 point each (3 total)
- PASS on CONDITIONAL (Docker) = 1 point if applicable, auto-PASS if no Docker
- PASS on RECOMMENDED = 1 point each (2 total)
- **HEALTHY:** 5-6 points
- **NEEDS ATTENTION:** 3-4 points
- **UNHEALTHY:** 0-2 points

---

## Step 4: Generate Fix Suggestions

For each FAIL or WARN, provide the exact text block to add to CLAUDE.md.

### If CI/CD Protocol is FAIL:

```markdown
**Add to CLAUDE.md:**

## CI/CD Protocol

- Use Makefile targets for all build, test, and deploy operations
- Never run raw build commands — use `make lint`, `make test`, `make build`, `make deploy`
- The Makefile is the single source of truth for project commands
- If a Makefile target is missing for your operation, ADD the target rather than running raw commands
```

### If Troubleshooting Protocol is FAIL:

```markdown
**Add to CLAUDE.md:**

## Troubleshooting Protocol

- Before debugging manually, run `make lint` and `make test` to surface known issues
- When fixing errors, fix BOTH the application code AND the CI/CD process (Makefile, Dockerfile, docker-compose.yml)
- After any fix, verify through the full pipeline: `make verify`
- Never bypass quality gates — if `make lint` or `make test` fails, fix the root cause
- Use `make troubleshoot` for a single-command diagnostic pass (clean + lint + test)
```

### If Quality Gates is FAIL:

```markdown
**Add to CLAUDE.md:**

## Quality Gates

| Target | Purpose | When to Run |
|--------|---------|-------------|
| `make lint` | Run linter | Before every commit |
| `make test` | Run tests | Before every commit |
| `make verify` | Full check (lint + test + typecheck) | Before deployment |
| `make troubleshoot` | Diagnostic pass (clean + lint + test) | When debugging issues |
```

### If Docker Conventions is FAIL (and Docker files exist):

```markdown
**Add to CLAUDE.md:**

## Docker Conventions

- Build images: `make docker-build` (not raw `docker build`)
- Start services: `make docker-up` (not raw `docker compose up`)
- Stop services: `make docker-down`
- View logs: `make docker-logs`
- Check status: `make docker-ps`
- If Docker errors occur, check Dockerfile and docker-compose.yml alongside application code
```

### If Deployment Protocol is WARN:

```markdown
**Add to CLAUDE.md:**

## Deployment

- Deploy: `make deploy` (runs verify first)
- The deploy target should be customized in the Makefile for your environment
- Post-deploy: run `/cicd:health` to verify endpoints
```

### If Available Commands is WARN:

```markdown
**Add to CLAUDE.md:**

## Available Makefile Targets

Run `make help` or see the Makefile for all targets. Key targets:

| Target | Purpose |
|--------|---------|
| `make lint` | Run linter |
| `make test` | Run tests |
| `make verify` | Full quality gate |
| `make deploy` | Deploy (after verify) |
| `make clean` | Remove build artifacts |
| `make troubleshoot` | Diagnostic pass |
```

---

## Step 5: Offer to Apply Fixes

After presenting the report, ask:

1. **Apply all fixes** — Add all missing sections to CLAUDE.md
2. **Apply selectively** — Choose which sections to add
3. **View only** — Just see the report, make changes manually

If the user chooses to apply:
- Read the current CLAUDE.md
- Append missing sections at an appropriate location (after existing conventions, before detailed/reference sections)
- Show the diff of what was added

---

## Notes

- This command is read-only by default — it only modifies CLAUDE.md if the user opts in
- Patterns are intentionally flexible — projects can phrase directives differently
- Docker section is only checked if Dockerfile or docker-compose.yml exists
- Run this after `/project:init` or `/cicd:init` to verify completeness
- Pair with `/cicd:check` for full project health: `/cicd:check` validates the Makefile, `/claude-md:lint` validates the CLAUDE.md
