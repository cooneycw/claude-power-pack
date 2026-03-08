---
description: Generate GitHub Actions CI/CD workflows
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*), Bash(cat:*), Bash(ls:*), Bash(test:*), Bash(mkdir:*), Read, Write
---

# CI/CD Pipeline Generation

Generate GitHub Actions CI/CD workflows from your Makefile targets.

## Steps

1. **Check for task manifest** - if `.claude/cicd_tasks.yml` exists, use it to inform pipeline generation:

```bash
if [ -f ".claude/cicd_tasks.yml" ]; then
    echo "Found cicd_tasks.yml manifest - pipeline will use manifest-defined steps"
    # The manifest defines plan steps (lint, test, deploy, etc.) with exact commands.
    # Pipeline generation should use these commands instead of defaults.
fi
```

When a manifest is present, the generated pipeline YAML should:
- Use the exact commands from the manifest's step definitions
- Include timeout values from the manifest
- Respect skip_if conditions as conditional steps
- Fall back to `make <target>` for steps not in the manifest

2. **Detect framework** using `lib/cicd`:

```bash
PYTHONPATH="$PWD/lib:$HOME/Projects/claude-power-pack/lib:$PYTHONPATH" python3 -m lib.cicd detect --quiet
```

3. **Generate pipeline** (dry run first):

```bash
PYTHONPATH="$PWD/lib:$HOME/Projects/claude-power-pack/lib:$PYTHONPATH" python3 -m lib.cicd pipeline
```

4. **Review output** with the user. Show the generated workflow YAML.

5. **Check for existing files** before writing:
   - If `.github/workflows/ci.yml` exists, ask before overwriting

6. **Write files** if approved:

```bash
PYTHONPATH="$PWD/lib:$HOME/Projects/claude-power-pack/lib:$PYTHONPATH" python3 -m lib.cicd pipeline --write
```

7. **Report results**:

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
