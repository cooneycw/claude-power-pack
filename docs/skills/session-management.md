# Session Management & Plan Mode

*From Claude Code Best Practices - r/ClaudeCode community wisdom*

## The Single Most Useful Line (98 upvotes)

**From "The single most useful line for getting what you want from Claude Code":**

```
"Please let me know if you have any questions before making the plan!"
```

**Why It Works:**
- Forces Claude to clarify ambiguities upfront
- Prevents wasted work on wrong assumptions
- Creates dialogue before execution
- Especially powerful in Plan Mode

**Extensions:**
- "Tell me if anything is unclear before proceeding"
- "What additional information do you need?"
- "Identify any assumptions you're making"

## Avoiding Context Degradation (47 upvotes)

**Problem:** Claude Code gets progressively worse during long sessions

**Root Cause:** Conversation compacting

**Solutions:**

1. **Avoid Compacting When Possible**
   - Each compact loses information
   - Start fresh session instead
   - Use git commits as natural break points

2. **Strategic Session Resets**
   - After completing major feature
   - When switching between different areas of codebase
   - If you notice quality degradation

3. **Context Files Instead of Conversation**
   - Store important context in files (CLAUDE.md, docs)
   - Don't rely on conversation history
   - Make context accessible via file reads

4. **Initialization Commands**
   - Use /prepare or similar to load fresh context
   - Keep context loading consistent
   - Document what context is needed for what tasks

## When to Reset Sessions

**Patterns from Community:**

1. **Feature-Based** (most common)
   - One session per feature
   - Fresh start after git commit
   - Clear success criteria per session

2. **Time-Based**
   - Every 5-10 messages
   - After 1-2 hours of work
   - When reaching 60% context

3. **Quality-Based**
   - When Claude seems "confused"
   - After multiple failed attempts
   - When suggestions become repetitive

4. **Never Reset** (for some users)
   - If you have good tests and conventions
   - Context degradation less of issue
   - Continuous work style

## Context Management Patterns

**Initialization Context (from multiple sources):**

1. Create `/prepare` command
2. Load from memory bank (markdown files)
3. Include recent git history
4. Load relevant docs

**Memory Bank Structure:**
- Project overview
- Architecture decisions
- Current priorities
- Known issues
- Coding standards

## Plan Mode (72 upvotes)

**From "4 Claude Code CLI tips I wish I knew earlier":**

**Benefits:**
- 20-30% better results
- Reduces wasted prompts
- Creates accountability
- Forces thinking before acting

**Enhanced Plan Mode** (37 upvotes)

**From "I made a better version of Plan Mode":**
- Custom plan mode implementations
- More detailed planning phases
- Integration with issue tracking

**Official Updates:**
- Claude Code 2.0.31 introduced new Plan subagent
- Enhanced subagent capabilities
- Better plan quality

## Red Flags

- Context >60% and starting new complex feature
- Claude giving contradictory advice
- Repetitive failures on same task
- Ignoring requirements you clearly stated
- Taking approaches you explicitly rejected

## Green Flags

- Claude asks clarifying questions before proceeding
- Proposes multiple approaches and explains tradeoffs
- References your existing code patterns
- Suggests tests for new functionality
- Explains architectural decisions
- Admits when uncertain

---

*Triggers: session, reset, plan mode, context degradation, compacting*
