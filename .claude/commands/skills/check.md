---
description: Check for available skill updates without installing them
allowed-tools: Bash(npx:*), Bash(command:*)
---

# Check Skill Updates

Check which installed skills have updates available, without installing them.

## Instructions

### Step 1: Check Prerequisites

```bash
command -v npx >/dev/null 2>&1 && echo "npx available" || echo "npx not found"
```

If npx is not available, tell the user they need Node.js installed and stop.

---

### Step 2: Check for Updates

```bash
npx skills check
```

Report which skills have updates available and which are current.

If updates are available, suggest running `/skills:update` to install them.
