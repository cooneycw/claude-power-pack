---
description: List installed skills in the current project
allowed-tools: Bash(ls:*), Bash(find:*), Bash(cat:*), Bash(head:*), Bash(npx:*)
---

# List Installed Skills

Show all skills installed in the current project.

## Instructions

When the user invokes `/skills:list`, check for installed skills:

```bash
echo "=== Project Skills ==="
if [ -d ".skills" ]; then
  find .skills -name "SKILL.md" -exec echo "---" \; -exec head -5 {} \; -exec echo "  File: {}" \;
elif [ -d "skills" ]; then
  find skills -name "SKILL.md" -exec echo "---" \; -exec head -5 {} \; -exec echo "  File: {}" \;
else
  echo "No skills directory found in this project."
fi
```

Also check for user-level (global) skills:

```bash
echo ""
echo "=== Global Skills ==="
if [ -d "$HOME/.skills" ]; then
  find "$HOME/.skills" -name "SKILL.md" -exec echo "---" \; -exec head -5 {} \; -exec echo "  File: {}" \;
else
  echo "No global skills directory found."
fi
```

Present results as a clean summary showing each skill's name, description, and source.

If no skills are installed, suggest running `/skills:find` to discover available skills.
