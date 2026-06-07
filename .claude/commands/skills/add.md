---
description: Install a skill from GitHub or skills.sh into the current project
allowed-tools: Bash(npx:*), Bash(ls:*), Bash(cat:*), Bash(command:*), Bash(which:*)
---

# Install Skill

Install a skill from GitHub or the skills.sh ecosystem into the current project.

## Arguments

- `PACKAGE` (required): Skill package reference. Formats:
  - `owner/repo` - Install all skills from a repo
  - `owner/repo@skill-name` - Install a specific skill
  - `https://github.com/owner/repo` - Full GitHub URL
  - `owner/repo --skill skill-name` - Alternative specific skill syntax

## Flags

- `-g` - Install globally (user-level, available across all projects)
- `-y` - Skip confirmation prompts

---

## Step 1: Validate Input

If no PACKAGE was provided, ask the user what they want to install. Suggest they run `/skills:find` first to discover available skills.

---

## Step 2: Check Prerequisites

```bash
command -v npx >/dev/null 2>&1 && echo "npx available" || echo "npx not found"
```

If npx is not available, tell the user they need Node.js installed and stop.

---

## Step 3: Show What Will Be Installed

Before installing, tell the user what skill will be installed and from which source. If the source is not a well-known publisher (`vercel-labs`, `anthropics`, `microsoft`, `ComposioHQ`), note that the source is third-party and the user should verify they trust it.

---

## Step 4: Install the Skill

Run the install command:

```bash
npx skills add $PACKAGE
```

For global installation (user-level):

```bash
npx skills add $PACKAGE -g -y
```

---

## Step 5: Verify Installation

After installation, check that the SKILL.md file was created:

```bash
ls -la .skills/ 2>/dev/null || ls -la skills/ 2>/dev/null || echo "No skills directory found"
```

Report success or failure to the user.

---

## Step 6: Report

Tell the user:
1. What was installed
2. That the skill will be available in Claude Code sessions for this project
3. Suggest restarting Claude Code if the skill doesn't appear immediately

---

## Notes

- Skills are SKILL.md files that provide Claude Code with procedural knowledge
- Project-level installs go into the current project directory
- Global installs (`-g`) are available across all projects for the user
- This command is safe to run multiple times (idempotent) - existing skills are updated
- Browse available skills at https://skills.sh/
