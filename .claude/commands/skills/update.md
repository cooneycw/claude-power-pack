---
description: Update all installed skills to their latest versions
allowed-tools: Bash(npx:*), Bash(command:*)
---

# Update Skills

Update all installed skills to their latest versions.

## Instructions

### Step 1: Check Prerequisites

```bash
command -v npx >/dev/null 2>&1 && echo "npx available" || echo "npx not found"
```

If npx is not available, tell the user they need Node.js installed and stop.

---

### Step 2: Update Skills

```bash
npx skills update
```

Report what was updated and what is already at the latest version.

---

## Notes

- This command is safe to run multiple times (idempotent)
- Updates pull the latest SKILL.md content from each skill's source repository
- If a specific skill causes issues after update, reinstall it with `/skills:add`
