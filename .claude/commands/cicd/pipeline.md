---
description: Generate CI/CD workflows (GitHub Actions, or self-hosted Woodpecker via provider)
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*), Bash(cat:*), Bash(ls:*), Bash(test:*), Bash(mkdir:*), Read, Write
---

# CI/CD Pipeline Generation

Generate CI/CD workflows from your Makefile targets. Read the explicit project
selection with `python -m lib.cicd provider --path <repo>`. Missing providers are
`unknown` and generation stops. Record one or more registered names with
`python -m lib.cicd pipeline --providers woodpecker,github-actions --record`;
select only the providers the project uses. `--record` preserves unrelated YAML
bytes and refuses a provider-line edit that would discard a comment, naming its
line. A one-run `--providers` override is deliberate and is persisted only with
`--record`. For a hardened self-hosted pipeline
(secret-scan + image-security + runtime-smoke) and to scaffold the Woodpecker
server/agent, use `/cicd:woodpecker` instead.

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
PYTHONPATH="$PWD:$HOME/Projects/claude-power-pack:$PYTHONPATH" uv run --project "$HOME/Projects/claude-power-pack" python -m lib.cicd detect --quiet
```

3. **Generate pipeline** (dry run first):

```bash
PYTHONPATH="$PWD:$HOME/Projects/claude-power-pack:$PYTHONPATH" uv run --project "$HOME/Projects/claude-power-pack" python -m lib.cicd pipeline
```

4. **Review output** with the user. Show the generated workflow YAML.

5. **Check for existing files** before writing:
   - If `.github/workflows/ci.yml` exists, ask before overwriting

6. **Write files** if approved:

```bash
PYTHONPATH="$PWD:$HOME/Projects/claude-power-pack:$PYTHONPATH" uv run --project "$HOME/Projects/claude-power-pack" python -m lib.cicd pipeline --write
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
    providers: [github-actions]   # one or more registered names
    branches:
      main: [lint, test, typecheck, build, deploy]
      pr: [lint, test, typecheck]
    matrix:
      python: ["3.11", "3.12"]
  ```
- Self-hosted Woodpecker: include `woodpecker` in `providers` and see
  `/cicd:woodpecker` + `docs/skills/woodpecker-ci.md` for the hardening stages.
