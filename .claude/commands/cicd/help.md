# CI/CD Commands

Build, verify, and deploy automation for Claude Code projects.

## Commands

| Command | Purpose |
|---------|---------|
| `/cicd:init` | Detect framework, generate Makefile and cicd.yml |
| `/cicd:check` | Validate Makefile against CPP standards |
| `/cicd:health` | Run health checks (endpoints + processes) |
| `/cicd:smoke` | Run smoke tests from cicd.yml |
| `/cicd:pipeline` | Generate GitHub Actions CI/CD workflows |
| `/cicd:container` | Generate Dockerfile and docker-compose.yml |
| `/cicd:infra-init` | Scaffold IaC directory with tiered structure (foundation/platform/app) |
| `/cicd:infra-discover` | Generate cloud resource discovery script for IaC import |
| `/cicd:infra-pipeline` | Generate CI/CD pipelines for infrastructure tiers with approval gates |
| `/cicd:help` | This help page |

## How It Works

```
/cicd:init      →  Detect framework  →  Generate Makefile  →  Generate .claude/cicd.yml
                                              ↓
/cicd:check     →  Validate targets  →  Report gaps  →  Suggest fixes
                                              ↓
/flow:finish    → make lint + make test       (quality gates)
/flow:deploy    → make deploy                 (deployment)
                                              ↓
/cicd:health    →  Check endpoints  →  Check processes  →  Report status
/cicd:smoke     →  Run smoke tests  →  Check results    →  Report pass/fail
                                              ↓
/cicd:pipeline  →  Read Makefile targets  →  Generate .github/workflows/ci.yml
/cicd:container →  Detect framework       →  Generate Dockerfile + docker-compose.yml
```

## Supported Frameworks

| Framework | Package Managers | Template |
|-----------|-----------------|----------|
| Python | uv, pip | `python-uv.mk`, `python-pip.mk` |
| Node.js | npm, yarn | `node-npm.mk`, `node-yarn.mk` |
| Go | go | `go.mk` |
| Rust | cargo | `rust.mk` |
| Multi-language | any | `multi.mk` |

## Standard Makefile Targets

| Target | Required | Used By |
|--------|----------|---------|
| `lint` | Yes | `/flow:finish` |
| `test` | Yes | `/flow:finish` |
| `format` | No | Manual / IDE |
| `typecheck` | No | `/cicd:check` reports |
| `build` | No | Build artifacts |
| `deploy` | No | `/flow:deploy` |
| `clean` | No | Cleanup |
| `verify` | No | Pre-deploy gate (lint + test + typecheck) |
| `troubleshoot` | No | Diagnostic pass (clean + lint + test) |

## Configuration

Optional `.claude/cicd.yml` overrides detection defaults:

```yaml
build:
  required_targets: [lint, test]
  recommended_targets: [format, typecheck, build, deploy, clean, verify]
deploy:
  default_target: deploy
  targets:
    deploy:
      description: "Deploy to production"
      requires_confirmation: true
```

### Health & Smoke Configuration

```yaml
health:
  endpoints:
    - url: http://localhost:8000/health
      name: API Server
      expected_status: 200
      timeout: 5
  processes:
    - name: uvicorn
      port: 8000
  smoke_tests:
    - name: API responds
      command: "curl -sf http://localhost:8000/health"
      expected_exit: 0
    - name: CLI version
      command: "python -m myapp --version"
      expected_output: "v\\d+\\.\\d+"
```

See `templates/cicd.yml.example` for full documentation.

## Quick Start

```bash
# Detect framework and generate Makefile
/cicd:init

# Validate your Makefile
/cicd:check

# Run health checks (after services are running)
/cicd:health

# Run smoke tests
/cicd:smoke

# Use with /flow
/flow:finish    # Runs make lint + make test
/flow:deploy    # Runs make deploy
```

## Infrastructure as Code

Three-tier IaC model with separate pipelines and approval gates:

```
/cicd:infra-init      →  Scaffold infra/ directory  →  foundation/ + platform/ + app/
                                    ↓
/cicd:infra-discover  →  Audit cloud resources  →  Generate terraform import commands
                                    ↓
/cicd:infra-pipeline  →  Generate per-tier workflows  →  Approval gates for foundation
```

Supported IaC providers: Terraform (default), Pulumi, Bicep
Supported clouds: AWS, Azure, GCP

Configuration in `.claude/cicd.yml`:

```yaml
infrastructure:
  provider: terraform
  cloud: aws
  state_backend:
    type: s3
    bucket: my-tf-state
    lock: true
  tiers:
    foundation:
      approval_required: true
    platform:
      approval_required: false
    app:
      approval_required: false
```

## Related

- `/claude-md:lint` — Audit CLAUDE.md for CI/CD and troubleshooting directives
- `/flow:doctor` — Reports Makefile target availability
- `/flow:deploy` — Runs deploy target
- `/self-improvement:deployment` — Analyze deploy failures and improve Makefile
