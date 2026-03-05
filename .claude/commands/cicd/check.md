---
description: Validate Makefile against CPP standards
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*), Bash(ls:*), Bash(test:*), Bash(cat:*), Bash(grep:*), Read
---

# /cicd:check — Makefile Validation

Validate your project's Makefile against Claude Power Pack standards.

---

## Step 1: Locate CPP Source

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
  exit 1
fi
```

---

## Step 2: Check for Makefile

```bash
if [ ! -f "Makefile" ]; then
  echo "No Makefile found in $(pwd)"
  echo ""
  echo "Create one with:"
  echo "  /cicd:init    — Auto-detect framework and generate"
  echo "  cp $CPP_DIR/templates/Makefile.example Makefile  — Copy starter template"
  exit 1
fi
```

---

## Step 3: Load Configuration

If `.claude/cicd.yml` exists, it overrides default required/recommended targets:

```bash
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd check
```

---

## Step 4: Present Results

The CLI outputs a markdown table. Present it to the user as-is.

The report includes:
- **Target table**: Each target's status (present, MISSING, missing) and notes
- **.PHONY declarations**: How many targets have .PHONY declared
- **Issues**: Any problems found (no Makefile, missing required targets, anti-patterns)
- **Summary**: Overall health status and target coverage

### Interpreting Results

| Status | Meaning |
|--------|---------|
| `present` | Target exists in Makefile |
| `MISSING` | Required target missing — `/flow` commands need this |
| `missing` | Recommended target missing — nice to have |

### Required Targets (used by /flow)

| Target | Used By |
|--------|---------|
| `lint` | `/flow:finish` — runs before commit |
| `test` | `/flow:finish` — runs before commit |

### Recommended Targets

| Target | Purpose |
|--------|---------|
| `format` | Code formatting |
| `typecheck` | Type checking (mypy, tsc, etc.) |
| `build` | Build artifacts |
| `deploy` | Deployment (`/flow:deploy`) |
| `clean` | Remove build artifacts |
| `verify` | Pre-deploy gate (lint + test + typecheck) |
| `troubleshoot` | Diagnostic pass (clean + lint + test) |

---

## Step 5: Suggest Fixes

If there are missing required targets:

```
To fix missing targets, run:
  /cicd:init    — Auto-detect and offer to append missing targets

Or add them manually to your Makefile:

  lint:
  	{framework-appropriate lint command}

  test:
  	{framework-appropriate test command}
```

---

## Notes

- Required targets are what `/flow:finish` looks for
- Recommended targets improve your workflow but aren't blocking
- `.PHONY` declarations prevent conflicts with files named like targets
- Run `/cicd:init` to auto-fix missing targets
