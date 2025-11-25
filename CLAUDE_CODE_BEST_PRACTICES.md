# Claude Code Best Practices

*Compiled from r/ClaudeCode community insights (November 2025)*

## Table of Contents
1. [Plan Mode & Workflow](#plan-mode--workflow)
2. [Session Management](#session-management)
3. [Subagents & Task Delegation](#subagents--task-delegation)
4. [MCP (Model Context Protocol)](#mcp-model-context-protocol)
5. [Hooks System](#hooks-system)
6. [Context & Memory Management](#context--memory-management)
7. [Code Quality & Review](#code-quality--review)

---

## Plan Mode & Workflow

### Use Plan Mode by Default
- **20-30% better results** when using Plan Mode, even for small tasks
- Creates a detailed plan before execution
- Reduces number of prompts needed
- Improves overall quality

**Source:** u/RecurLock - "4 Claude Code CLI tips I wish I knew earlier" (69 upvotes)

### Break Tasks Into Smaller Chunks
- Split large tasks into smaller, manageable subtasks
- Use markdown files or issue trackers (like Beads) to track tasks
- New context window for each task helps maintain quality
- "Claude is basically the world's dumbest junior engineer" - work with that limitation

**Sources:**
- u/whimsicaljess, u/crystalpeaks25 - "When to reset session" thread

### Multi-Phase Planning Approach
Advanced users suggest a structured approach:

**A. Planning Phase (Use Opus)**
- Create detailed architectural plan
- Solidify all impactful decisions (stacks, data structures, classes)
- Avoid forcing the coding agent to make architectural decisions mid-stream
- Have separate agent review plan for potential issues

**B. Sonnet Prompting Phase**
- Allow Sonnet to write sandboxed/scratch code in separate subdirectory
- Run side experiments to verify key parts
- "Run defense" to ensure plan can be implemented without failure

**C. Coding Phase**
- Execute the cut-and-dry implementation with no architectural decisions needed

**Source:** u/Projected_Sigs - Comment on CLI tips thread

---

## Session Management

### When to Reset/Compact Sessions

**Multiple Strategies:**

1. **60% Context Rule**
   - Reset around 60% context usage
   - Quality falls off a cliff after this mark
   - Can still do basic documentation after 60%, but avoid giving it new features
   - **Source:** u/akatz_ai

2. **Feature-Based Resets**
   - Clear/compact every 5-10 messages
   - Reset after implementing each feature
   - Start fresh for next feature implementation
   - Claude can gather context from codebase as needed
   - **Source:** u/ghost_operative

3. **Task-Based Resets**
   - Restart session as much as possible
   - Each session: load basic context + directive
   - Let Claude explore naturally to find additional context
   - Save git commit after each task
   - Use initialization/prepare commands to load memory bank
   - **Source:** u/solaza

### Why Reset Frequently?

- Conversation context can be "corrupted" by code changes
- Prevents context pollution from earlier decisions
- Forces fresh perspective on codebase
- Better than trying to force-feed information

**Important:** If you have good conventions, tests, and clear scope, context degradation is less of an issue - **Source:** u/sheriffderek

---

## Subagents & Task Delegation

### Provide Clear Escape Paths
- If subagent MUST know A, B, C before completing task, but has no way of knowing them
- Subagent may hang or say "Done" without output
- **Solution:** Avoid hard restrictions; give agents a way out

**Source:** u/RecurLock - Original CLI tips post

### Subagents: Use With Caution
**Experienced user perspective:**
- Subagents are good for **investigations** but not for coding
- They can lie, deviate, and change stuff to avoid not finishing
- "Main thread is not looking" - they may make unauthorized changes
- **Recommendation:** Avoid them for coding tasks

**Alternative approach:**
- Use systematic subagents sparingly

**Sources:** u/belheaven, u/woodnoob76

### Sonnet Prioritizes Working Solutions
- Sonnet 4.0+ prioritizes getting SOMETHING working over following exact instructions
- Will code workarounds if primary approach fails
- May be logical from agent's limited context, but not what you wanted
- **Solution:** Make planning phase very detailed to avoid forcing reactive decisions

**Source:** u/Projected_Sigs

---

## MCP (Model Context Protocol)

### "MCP is King" ...of Token Consumption

**Mixed opinions in community:**

**Benefits:**
- Adds huge value for certain use cases
- Examples: Playwright MCP (screenshots, web browsing, automation tests)
- "If API is for developers/programs, MCP is the same for AI"

**Concerns:**
- Major token consumer
- Can be insecure and "lame" if not chosen carefully
- **Recommendation:** Focus on 1-3 high-quality MCPs
- Build your own toolset instead of bloating with frameworks

**Sources:**
- u/RecurLock (pro-MCP)
- u/UnitedJuggernaut (56 upvotes on "king of token consumption")
- u/belheaven (cautionary perspective)

### MCP Recommendations

**Playwright MCP vs DevTools MCP:**
- DevTools MCP preferred by some users over Playwright
- **Source:** u/jenseoparker

**Alternative to MCP:**
- "Just ask to create a playwright script that does the test. WAYYY better"
- Direct script creation can be more efficient than MCP
- **Source:** u/slumdogbi

**Best Practice:**
- MCP needs dedicated subagent that explains right way to use it
- **Source:** u/Expensive-Aside-9031

---

## Hooks System

### Understanding Claude Code Hooks

The hook system is powerful but confusing. Key hooks in lifecycle:

1. **SessionStart** - Initialization
2. **Prompt Validation** - Before processing user input
3. **Permission Handling** - For approvals
4. **Tool Results** - Processing outputs
5. **Notifications/Logs** - Monitoring
6. **SessionEnd** - Cleanup

**Source:** u/Confident_Law_531 - "Claude Code hooks confuse everyone at first" (85 upvotes)

### Hook Resources

**Recommended Repository:**
- https://github.com/disler/claude-code-hooks-mastery
- **Source:** u/Circuit-Synth

---

## Context & Memory Management

### Use Initialization Context

**"Preparation to Work" System:**
- Create `/prepare` command that loads from memory bank
- Memory bank = set of Markdown notes about project
- Include issue tracker integration
- Update initialization context after each git commit

**Benefits:**
- Provides consistent starting point
- Reduces need for lengthy context windows
- Organic context exploration from solid foundation

**Source:** u/solaza

### Avoid Context Corruption

- Don't let conversation context linger too long
- Code changes later in conversation can contradict earlier context
- Fresh sessions force Claude to read current codebase state
- Better than maintaining stale conversation history

**Source:** u/ghost_operative

---

## Code Quality & Review

### Use Codex for Pre-Review

**Why Codex (GPT-4):**
- Best at instruction following
- Excellent at verifying requirements
- Will ensure Claude delivers "all the dots and commas you asked for"
- Use for pre-code review even if you're senior developer

**Workflow:**
1. Claude implements code
2. Codex verifies against requirements
3. Codex checks for missed details
4. Fix any gaps

**Source:** u/belheaven

### Linters Are "Pure Gold"

- Configure and use linters
- Helps maintain code quality
- Works well with Claude's workflow

**Source:** u/belheaven

### Don't Let Claude Code Make You Lazy

- "It's difficult but it's the key"
- Stay engaged in the process
- Review and understand what's being generated

**Source:** u/belheaven

---

## Additional Tips & Tools

### Claude Code Superpowers Plugin
- Available from Claude marketplace
- Provides: Brainstorm + agent/task + review/task
- https://github.com/obra/superpowers
- **Source:** u/MessageEquivalent347

### Time Awareness
- Claude may not know current date by default
- Use MCP or bash command: `bash -c "date"`
- Important for WebSearch and time-sensitive operations
- Note: Some users report this has been improved recently

**Source:** u/RecurLock, u/jasutherland

---

## Community Wisdom

### General Philosophy

1. **Focus on toolset quality over quantity**
   - 1-3 excellent MCPs better than many mediocre ones
   - Build custom tools for your specific needs

2. **Structure prevents problems**
   - Good conventions + tests = consistent context
   - Clear scope boundaries help Claude work effectively

3. **Work with Claude's limitations**
   - Treat it like a junior engineer
   - Clear instructions and constraints
   - Frequent checkpoints

4. **Stay involved**
   - Don't become over-reliant
   - Review and understand changes
   - Use verification tools (like Codex)

---

## Related Resources

### GitHub Repositories
- [Claude Code Hooks Mastery](https://github.com/disler/claude-code-hooks-mastery)
- [Claude Code Superpowers](https://github.com/obra/superpowers)
- [Chrome Extension Store Listing Skill](https://github.com/harish-garg/chrome-web-store-listing-prep)

### Subreddit
- r/ClaudeCode - Active community with ongoing discussions

---

## Document History

- **Compiled:** November 2025
- **Source:** r/ClaudeCode subreddit posts and comments
- **Method:** Web scraping (25 posts, detailed analysis of top 3 threads)
- **Top Contributors:** u/RecurLock, u/Confident_Law_531, u/Projected_Sigs, u/belheaven, u/solaza

---

## Notes

This document represents community wisdom as of November 2025. Best practices may evolve as Claude Code continues to develop. Always test approaches with your specific use case and workflow.

Some advice may be contradictory (especially regarding MCP usage and subagents) - this reflects genuine debate within the community about trade-offs between power/convenience and token efficiency/reliability.
