---
description: Detect framework and generate/validate Makefile for CI/CD integration
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*), Bash(ls:*), Bash(test:*), Bash(cat:*), Bash(grep:*), Bash(cp:*), Read, Write
---

# /cicd:init - Framework Detection & Makefile Setup

Detect your project's framework and package manager, then generate or validate a Makefile for CPP `/flow` integration.

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
echo "CPP source: $CPP_DIR"
```

---

## Step 2: Detect Framework

Run the framework detector:

```bash
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd detect
```

Report the detection results to the user:
- Framework detected (Python, Node, Go, Rust, Multi, Unknown)
- Package manager detected (uv, pip, npm, yarn, cargo, go, etc.)
- Detected indicator files
- Recommended Makefile targets for this stack

If framework is "Unknown", ask the user which framework to use via AskUserQuestion with options matching the available templates.

---

## Step 3: Check Existing Makefile

```bash
if [ -f "Makefile" ]; then
  echo "Existing Makefile found - running validation..."
  PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd check
else
  echo "No Makefile found - will generate one."
fi
```

### If Makefile exists:
1. Run `python3 -m lib.cicd check` to validate against CPP standards
2. Report the validation results (target coverage, missing targets, issues)
3. If targets are missing, offer to append them:
   - Show what targets would be added
   - Ask user to confirm via AskUserQuestion
   - If confirmed, read the current Makefile, append missing target stubs, write back

### If no Makefile:
1. Select the correct template based on detected framework + package manager:

   | Detection | Template |
   |-----------|----------|
   | Python + uv | `templates/makefiles/python-uv.mk` |
   | Python + pip | `templates/makefiles/python-pip.mk` |
   | Node + npm | `templates/makefiles/node-npm.mk` |
   | Node + yarn | `templates/makefiles/node-yarn.mk` |
   | Go | `templates/makefiles/go.mk` |
   | Rust | `templates/makefiles/rust.mk` |
   | Multi / Unknown | `templates/makefiles/multi.mk` |

2. Copy the template to the project root:
   ```bash
   cp "$CPP_DIR/templates/makefiles/{template}.mk" Makefile
   ```

3. Report what was generated and suggest customization.

---

## Step 4: Generate cicd.yml (if not exists)

If `.claude/cicd.yml` does not exist, generate it from detected defaults:

```bash
if [ ! -f ".claude/cicd.yml" ]; then
  # Get detection result as JSON
  DETECT_JSON=$(PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd detect --json)
fi
```

Generate `.claude/cicd.yml` with:
- Detected framework and package manager (commented out - auto-detection is preferred)
- Build section with required and recommended targets
- Deploy section with placeholder target metadata

Use the `templates/cicd.yml.example` as reference but generate a minimal version with only the relevant sections for the detected framework.

If `.claude/cicd.yml` already exists, skip this step and report "cicd.yml already configured".

---

## Step 5: Report Results

```
=== CI/CD Init Complete ===

Framework:       {detected}
Package Manager: {detected}

Makefile:        {Generated from template | Validated (N/M targets)}
Config:          {.claude/cicd.yml generated | Already exists}

Next Steps:
  1. Review and customize your Makefile targets
  2. Run /cicd:check to validate
  3. /flow:finish will now use `make lint` and `make test`
  4. /flow:deploy will use `make deploy`
```

---

## Notes

- This command is idempotent - safe to run multiple times
- Existing files are never overwritten without user confirmation
- Templates are copied, not symlinked (so you can customize freely)
- Run `/cicd:check` anytime to re-validate your Makefile
