# Hooks & Automation

*From Claude Code Best Practices - r/ClaudeCode community wisdom*

## Hook System Deep Dive (85 upvotes)

**From "Claude Code hooks confuse everyone at first":**

**Key Resource:** https://github.com/disler/claude-code-hooks-mastery

## Hook Types & Uses

1. **SessionStart** - Load context, setup environment
2. **UserPromptSubmit** - Validate/enrich prompts before sending
3. **ToolUse** - Intercept or modify tool usage
4. **ToolResult** - Process outputs before Claude sees them
5. **SessionEnd** - Cleanup, logging

## Best Practices

- Understand lifecycle to avoid fighting execution flow
- Use hooks for automation, not control
- Keep hooks simple and fast
- Log hook activity for debugging

## Advanced Hook Usage

**Pattern Matching for Skills (from 685 upvote post):**
- Use hooks to pre-fetch relevant skills
- Match patterns in user prompts
- Automatically activate appropriate context

**Editor Integration:**
- Use Ctrl-G hook to launch custom tools
- Extend beyond just opening editor
- Hook into any workflow automation

## Example: Session Start Hook

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "~/.claude/scripts/session-register.sh start"
      }
    ]
  }
}
```

## Example: Prompt Validation Hook

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "type": "command",
        "command": "~/.claude/scripts/validate-prompt.sh"
      }
    ]
  }
}
```

## Hook Lifecycle

```
Session Start
    ↓
SessionStart hooks fire
    ↓
User submits prompt
    ↓
UserPromptSubmit hooks fire
    ↓
Claude processes prompt
    ↓
ToolUse hooks fire (if tool called)
    ↓
Tool executes
    ↓
ToolResult hooks fire
    ↓
Claude responds
    ↓
(repeat for next prompt)
    ↓
Session ends
    ↓
SessionEnd hooks fire
```

## Common Use Cases

1. **Environment Setup**
   - Set environment variables
   - Load project context
   - Initialize development tools

2. **Session Tracking**
   - Register session for coordination
   - Update heartbeat
   - Log activity

3. **Prompt Enhancement**
   - Add context automatically
   - Validate inputs
   - Route to skills

4. **Output Processing**
   - Mask sensitive data
   - Format results
   - Log outputs

## Key Repositories

- **Hooks Mastery:** https://github.com/disler/claude-code-hooks-mastery
- **Infrastructure Showcase:** https://github.com/diet103/claude-code-infrastructure-showcase

---

*Triggers: hooks, automation, hook lifecycle, SessionStart, UserPromptSubmit*
