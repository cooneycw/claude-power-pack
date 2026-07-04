---
description: Close a GitHub issue with optional comment
allowed-tools: Bash(gh issue close:*), Bash(gh issue comment:*), Bash(gh issue view:*), Bash(gh auth status:*)
---

# Close GitHub Issue

Close an issue in the claude-power-pack repository.

## Usage

The user should provide an issue number. If not provided, ask for it.

## Flow

### Step 1: Verify Issue

First, fetch and display the issue to confirm:
```bash
gh issue view NUMBER --repo cooneycw/claude-power-pack
```

Show:
- Title
- Current state
- Labels
- Brief description

### Step 2: Ask for Closing Comment (Optional)

Ask if the user wants to add a closing comment. Common patterns:

- "Implemented in [commit/PR]"
- "Fixed in v1.x.x"
- "Duplicate of #XX"
- "Won't fix: [reason]"
- "Completed"

### Step 3: Close Reason (Optional)

For tracking purposes, ask about the close reason:
- **Completed** - Issue was resolved
- **Not Planned** - Won't be implemented
- **Duplicate** - Duplicate of another issue

```bash
# Close as completed (default)
gh issue close NUMBER --repo cooneycw/claude-power-pack

# Close as not planned
gh issue close NUMBER --repo cooneycw/claude-power-pack --reason "not planned"
```

### Step 4: Execute

If closing comment provided, add it first:
```bash
gh issue comment NUMBER --repo cooneycw/claude-power-pack --body "COMMENT"
```

Then close:
```bash
gh issue close NUMBER --repo cooneycw/claude-power-pack
```

### Step 5: Confirm

After closing, confirm success and show final state.

## Example Interactions

### Simple Close
```
User: /github:issue-close 42

Claude: [Shows issue #42 details]

This will close issue #42: "Use Plan Mode for complex refactors"

Would you like to add a closing comment? (optional)

User: no

Claude: Close reason?
1. Completed (default)
2. Not Planned
3. Duplicate

User: 1

Claude: Closing issue #42...

Done! Issue #42 has been closed.
```

### Close with Comment
```
User: /github:issue-close 38

Claude: [Shows issue #38 details]

Would you like to add a closing comment?

User: Fixed in commit abc123

Claude: Close reason?
1. Completed (default)
2. Not Planned
3. Duplicate

User: 1

Claude: I'll:
1. Add comment: "Fixed in commit abc123"
2. Close issue #38 as completed

Proceed? (yes/no)

User: yes

Claude: Done! Issue #38 has been closed with your comment.
```

### Close as Duplicate
```
User: /github:issue-close 45

Claude: [Shows issue details]

Would you like to add a closing comment?

User: Duplicate of #42

Claude: Close reason?
1. Completed
2. Not Planned
3. Duplicate

User: 3

Claude: I'll also add the "duplicate" label for tracking.

[Adds label, adds comment, closes issue]

Done! Issue #45 closed as duplicate of #42.
```

## Reopen Option

Mention that issues can be reopened if needed:
```bash
gh issue reopen NUMBER --repo cooneycw/claude-power-pack
```
