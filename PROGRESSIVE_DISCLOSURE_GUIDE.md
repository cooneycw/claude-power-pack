# Progressive Disclosure: Efficient Tool Context Management for Claude Code

## Why This Matters

Claude models have finite context windows:
- Claude Sonnet 4.5: 200K tokens
- Each MCP tool definition: 500-2000 tokens
- GitHub MCP alone: ~30K-50K tokens
- A typical 5-server MCP setup: ~55K tokens BEFORE any conversation

**The Problem:** If 30-50% of your context is consumed by tool definitions,
you have proportionally less space for:
- Actual code being analyzed
- Conversation history
- CLAUDE.md and Skills content
- Task context and requirements

**The Solution:** Load tools gradually, on-demand, not all at once.

## The Three-Tier Loading Pattern (from Anthropic Skills)

### Tier 1: Metadata Only (~100 tokens per tool)
- Tool name
- Brief description (1-2 sentences)
- Trigger patterns/keywords

This is enough for the agent to know a tool EXISTS and WHEN to use it.

### Tier 2: Full Instructions (<5K tokens)
- Complete tool documentation
- Usage examples
- Parameter details
- Error handling guidance

Loaded ONLY when the agent determines the tool is relevant to the current task.

### Tier 3: Executable Assets (variable)
- Scripts
- Templates
- Reference files

Loaded ONLY when actively executing the tool.

## Implementation Patterns

### Pattern A: Tool Search Tool (Anthropic's Official Solution)

```python
# Instead of loading all tools upfront:
tools = [tool1, tool2, tool3, ..., tool100]  # 50K+ tokens

# Use a search tool:
tools = [
    tool_search_tool,  # ~500 tokens
    frequently_used_tool_1,  # Always needed
    frequently_used_tool_2,  # Always needed
]
# Other tools discovered on-demand via search
```

**Configuration:**
- Mark tools with `defer_loading: true` in tool definitions
- Keep 2-3 frequently-used tools with `defer_loading: false`
- Agent searches for additional tools as needed

### Pattern B: Skills-Based Architecture

Convert MCP tool procedures into Skills:

**Before (MCP approach):**
```json
{
  "tools": [
    {
      "name": "github_search_code",
      "description": "Search for code in GitHub repositories...",
      // Full schema, examples, etc. = ~2000 tokens
    },
    {
      "name": "github_search_issues",
      // Another ~2000 tokens
    },
    // ... 10 more GitHub tools
  ]
}
// Total: ~24K tokens for GitHub alone
```

**After (Skills approach):**
```markdown
# .claude/skills/github-operations.md
---
name: GitHub Operations
trigger: github, repository, PR, issue, code search
---

# GitHub Operations Skill

When the user needs to interact with GitHub...

[Full instructions load only when triggered]
```
// Metadata: ~100 tokens, Full: ~3K tokens when activated

### Pattern C: MCP Server Consolidation

**Before (20 tools, ~15K tokens):**
- `web_search_tavily`
- `web_search_brave`
- `web_search_kagi`
- `web_search_exa`
- `github_search_code`
- `github_search_issues`
- `github_search_repos`
- ... etc

**After (8 tools, ~6K tokens):**
- `web_search` (with `provider` parameter)
- `github_search` (with `search_type` parameter)
- ... etc

**Consolidation Rules:**
1. Merge tools that differ only by a parameter
2. Use enums for provider/type selection
3. Keep description under 200 characters
4. Remove redundant examples

### Pattern D: Selective MCP Activation

Use `mcpick` or similar tools:

```bash
# Before coding session focused on frontend:
npx mcpick enable playwright devtools
npx mcpick disable github jira supabase

# Before coding session focused on backend:
npx mcpick enable github supabase
npx mcpick disable playwright devtools
```

**Alternative: Claude Code native approach:**
```
/mcp disable github
/mcp enable playwright
```

## Decision Framework

```
┌─────────────────────────────────────────────────────────────┐
│                    TOOL ARCHITECTURE DECISION               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │ What type of capability?      │
              └───────────────────────────────┘
                    │                   │
          External Data/API      Procedural Knowledge
                    │                   │
                    ▼                   ▼
              ┌─────────┐         ┌─────────┐
              │   MCP   │         │  SKILL  │
              └─────────┘         └─────────┘
                    │                   │
                    ▼                   │
        ┌───────────────────┐          │
        │ How many tools?   │          │
        └───────────────────┘          │
           │            │              │
         <10          10+              │
           │            │              │
           ▼            ▼              │
      Load All    Tool Search         │
                    Tool              │
           │            │              │
           └────────────┴──────────────┘
                        │
                        ▼
           ┌───────────────────────────┐
           │ Token budget assessment   │
           │ Use /context to check     │
           └───────────────────────────┘
                        │
              ┌─────────┴─────────┐
              │                   │
           <30% of              >30% of
           context              context
              │                   │
              ▼                   ▼
          Good to go         Consolidate or
                             Convert to Skills
```

## Monitoring & Optimization

### Step 1: Audit Current Token Usage
```
/context
```
Look for:
- MCP servers consuming >10K tokens
- Tools with verbose descriptions
- Redundant tool definitions

### Step 2: Identify Consolidation Opportunities
Questions to ask:
- Are there multiple tools that could share a parameter?
- Are tool descriptions longer than necessary?
- Are there tools never used in typical sessions?

### Step 3: Measure Impact
Before optimization:
- Note token consumption from `/context`
- Track tool selection accuracy (are wrong tools being called?)

After optimization:
- Compare token consumption
- Verify tool selection still works
- Check for missing functionality

## Examples from Production

### Example 1: Scott Spence's MCP Optimization
- Before: 20 tools, ~15K tokens
- After: 8 tools, ~6.5K tokens
- Savings: 8,551 tokens (57%)
- Functionality: Identical

### Example 2: Anthropic Internal Optimization
- Before: 134K tokens in tool definitions
- After: ~8.7K tokens with Tool Search Tool
- Savings: 125K tokens (93%)
- Accuracy: Improved (49% → 74% for Opus 4)

### Example 3: Chrome DevTools MCP → Skills Conversion
- Before: MCP with ~15 tools, heavy token usage
- After: Targeted Skills, lazy loading
- Benefit: Same functionality, dramatically reduced baseline cost

## Sources

- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Anthropic: Skills Explained](https://www.claude.com/blog/skills-explained)
- [Scott Spence: Optimising MCP Server Context Usage](https://scottspence.com/posts/optimising-mcp-server-context-usage-in-claude-code)
