---
description: Update an existing GitHub issue (title, body, labels, assignees, comments)
allowed-tools: Bash(gh issue edit:*), Bash(gh issue comment:*), Bash(gh issue view:*), Bash(gh auth status:*)
---

# Update GitHub Issue

Modify an existing issue in the claude-power-pack repository.

## Usage

The user should provide an issue number. If not provided, ask for it.

## First: Show Current State

Before making changes, fetch and display the current issue:
```bash
gh issue view NUMBER --repo cooneycw/claude-power-pack
```

## Update Options

Ask the user what they want to update:

1. **Edit title**
2. **Edit body**
3. **Add/remove labels**
4. **Assign/unassign**
5. **Add comment**

### Edit Title

```bash
gh issue edit NUMBER --repo cooneycw/claude-power-pack --title "NEW TITLE"
```

### Edit Body

```bash
gh issue edit NUMBER --repo cooneycw/claude-power-pack --body "NEW BODY"
```

For multiline bodies, use a heredoc:
```bash
gh issue edit NUMBER --repo cooneycw/claude-power-pack --body "$(cat <<'EOF'
## Description

New description content here.

## Details

More details...
EOF
)"
```

### Add Labels

```bash
gh issue edit NUMBER --repo cooneycw/claude-power-pack --add-label "label1,label2"
```

### Remove Labels

```bash
gh issue edit NUMBER --repo cooneycw/claude-power-pack --remove-label "label1"
```

### Assign User

```bash
gh issue edit NUMBER --repo cooneycw/claude-power-pack --add-assignee "username"
gh issue edit NUMBER --repo cooneycw/claude-power-pack --add-assignee "@me"
```

### Unassign User

```bash
gh issue edit NUMBER --repo cooneycw/claude-power-pack --remove-assignee "username"
```

### Add Comment

```bash
gh issue comment NUMBER --repo cooneycw/claude-power-pack --body "Comment text"
```

For multiline comments:
```bash
gh issue comment NUMBER --repo cooneycw/claude-power-pack --body "$(cat <<'EOF'
Thanks for the suggestion!

I'll look into implementing this in the next update.
EOF
)"
```

## Confirmation

Before applying changes:
1. Show what will be changed
2. Ask for confirmation
3. Apply changes
4. Show updated issue state

## Available Labels

- `best-practice` - Best practice suggestions
- `correction` - Documentation corrections
- `feature-request` - Feature requests
- `bug` - Bug reports
- `enhancement` - Enhancements
- `documentation` - Documentation related
- `mcp-server` - MCP Second Opinion issues
- `wontfix` - Won't be fixed
- `duplicate` - Duplicate issue
- `good first issue` - Good for newcomers

## Example Interaction

```
User: /github:issue-update 42

Claude: [Shows current state of issue #42]

What would you like to update?
1. Edit title
2. Edit body
3. Add/remove labels
4. Assign/unassign
5. Add comment

User: 5

Claude: What comment would you like to add?

User: This has been implemented in v1.1.0

Claude: I'll add this comment to issue #42:
"This has been implemented in v1.1.0"

Proceed? (yes/no)

User: yes

[Claude adds comment and confirms]
```
