# CI/CD Commands

Build, verify, and deploy automation for Claude Code projects.

## Commands

| Command | Purpose |
|---------|---------|
| `/cicd:init` | Detect framework, generate Makefile and cicd.yml |
| `/cicd:check` | Validate Makefile against CPP standards |
| `/cicd:help` | This help page |

## How It Works

```
/cicd:init  →  Detect framework  →  Generate Makefile  →  Generate .claude/cicd.yml
                                          ↓
/cicd:check →  Validate targets  →  Report gaps  →  Suggest fixes
                                          ↓
/flow:finish → make lint + make test      (quality gates)
/flow:deploy → make deploy                (deployment)
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

See `templates/cicd.yml.example` for full documentation.

## Quick Start

```bash
# Detect framework and generate Makefile
/cicd:init

# Validate your Makefile
/cicd:check

# Use with /flow
/flow:finish    # Runs make lint + make test
/flow:deploy    # Runs make deploy
```

## Related

- `/flow:doctor` — Reports Makefile target availability
- `/flow:deploy` — Runs deploy target
- `/self-improvement:deployment` — Analyze deploy failures and improve Makefile
