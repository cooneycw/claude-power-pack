---
description: View GitHub issue details and comments
allowed-tools: Bash(gh issue view:*), Bash(gh api:*), Bash(gh auth status:*)
---

# View GitHub Issue

View detailed information about a specific issue in claude-power-pack.

## Usage

The user should provide an issue number. If not provided, ask for it.

## Fetch Issue Details

```bash
gh issue view NUMBER --repo cooneycw/claude-power-pack
```

This returns:
- Title
- State (open/closed)
- Author
- Labels
- Assignees
- Created/updated timestamps
- Body content
- Comments

## For More Detail (Comments)

To get comments:
```bash
gh issue view NUMBER --repo cooneycw/claude-power-pack --comments
```

## Output Format

Present the issue in a readable format:

```
## Issue #42: Use Plan Mode for complex refactors

**State:** Open
**Author:** @username
**Labels:** best-practice, enhancement
**Assignees:** None
**Created:** 2025-12-10
**Updated:** 2025-12-12

---

### Description

[Issue body content here]

---

### Comments (2)

**@commenter1** (2025-12-11):
[Comment content]

**@commenter2** (2025-12-12):
[Comment content]
```

## Follow-up Options

After viewing, offer:
1. **Open in browser**: `gh issue view NUMBER --web --repo cooneycw/claude-power-pack`
2. **Add a comment**: `/github:issue-update NUMBER` (then add comment)
3. **Close the issue**: `/github:issue-close NUMBER`
4. **Edit the issue**: `/github:issue-update NUMBER`

## Example Interaction

```
User: /github:issue-view 42

Claude: [Fetches and displays issue #42 details]

Would you like to:
1. Open in browser
2. Add a comment
3. Edit this issue
4. Close this issue
```
