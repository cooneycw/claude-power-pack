---
description: Generate GitHub Actions CI/CD workflows
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*), Bash(cat:*), Bash(ls:*), Bash(test:*), Bash(mkdir:*), Read, Write
---

# CI/CD Pipeline Generation

Generate GitHub Actions CI/CD workflows from your Makefile targets.

## Steps

1. **Detect framework** using `lib/cicd`:

```bash
PYTHONPATH="$PWD/lib:$HOME/Projects/claude-power-pack/lib:$PYTHONPATH" python3 -m lib.cicd detect --quiet
```

2. **Generate pipeline** (dry run first):

```bash
PYTHONPATH="$PWD/lib:$HOME/Projects/claude-power-pack/lib:$PYTHONPATH" python3 -m lib.cicd pipeline
```

3. **Review output** with the user. Show the generated workflow YAML.

4. **Check for existing files** before writing:
   - If `.github/workflows/ci.yml` exists, ask before overwriting

5. **Write files** if approved:

```bash
PYTHONPATH="$PWD/lib:$HOME/Projects/claude-power-pack/lib:$PYTHONPATH" python3 -m lib.cicd pipeline --write
```

6. **Report results**:

```
## CI Pipeline Generated

Framework: {framework} ({package_manager})

Files created:
  .github/workflows/ci.yml - CI pipeline with lint, test, build

Triggers: push to main, pull requests
Targets:  make lint, make test, make typecheck (if available)

To view: cat .github/workflows/ci.yml
```

## Notes

- Workflows use `make <target>` as steps (not direct tool commands)
- This keeps CI in sync with local development commands
- Caching is included for package managers (uv, npm, cargo, go)
- Matrix builds are configured from `.claude/cicd.yml` if present
- Configure pipeline settings in `.claude/cicd.yml`:
  ```yaml
  pipeline:
    provider: github-actions
    branches:
      main: [lint, test, typecheck, build, deploy]
      pr: [lint, test, typecheck]
    matrix:
      python: ["3.11", "3.12"]
  ```
