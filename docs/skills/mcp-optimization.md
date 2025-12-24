# MCP Best Practices & Optimization

*From Claude Code Best Practices - r/ClaudeCode community wisdom*

## Code-Mode: Save >60% in tokens (242 upvotes)

**Repository:** https://github.com/universal-tool-calling-protocol/code-mode

**Key Innovation:** Execute MCP tools via code execution instead of direct calls

**Benefits:**
- 60% token savings
- More efficient MCP usage
- Less context bloat

## One MCP to Rule Them All (95 upvotes)

**From "no more toggling MCPs on/off":**

**Approach:** Use orchestrator MCP that manages other MCPs

**Benefits:**
- Don't need to enable/disable MCPs manually
- Intelligent routing to appropriate MCP
- Cleaner context

**Reference:** https://www.anthropic.com/engineering/code-execution-with-mcp

## MCP Selection

**Top MCPs Mentioned:**

1. **DevTools MCP** - Preferred over Playwright by some
2. **Playwright MCP** (`@playwright/mcp`) - Browser automation, UI testing
3. **Context 7** - Context management
4. **Supabase** - Database operations

**Installation Example:**
```bash
# Playwright MCP (official package from Microsoft)
claude mcp add playwright -- npx -y @playwright/mcp@latest
```

**Wisdom:**
- "MCP is king of token consumption"
- Choose 1-3 quality MCPs
- Many users prefer direct code over MCP
- MCPs work best with dedicated subagent instructions

## Converting MCP to Skills (175 upvotes)

**From "I've successfully converted 'chrome-devtools-mcp' into Agent Skills":**

**Why Convert:**
- Chrome-devtools-mcp is useful but token-heavy
- Skills can be more targeted and efficient
- Better control over when/how tools activate

**Approach:**
- Extract core functionality
- Create focused skills for specific use cases
- Maintain benefits while reducing token usage

## When to Convert MCP → Skills

| Scenario | Recommendation |
|----------|----------------|
| Tool provides external data access | Keep as MCP |
| Tool teaches a procedure | Convert to Skill |
| Tool is used in every session | Keep loaded |
| Tool is used occasionally | Lazy load or Skill |
| Tool has verbose description | Optimize or convert |

## Red Flags for Token Bloat

- MCP server consuming >20K tokens
- More than 5 MCP servers enabled simultaneously
- Tool descriptions >500 characters
- Multiple tools with overlapping functionality
- `/context` shows >40% used by tools before work begins

## Optimization Techniques

1. **Consolidate Related Tools**
   ```
   Before: web_search_tavily, web_search_brave, web_search_kagi
   After:  web_search (provider: tavily|brave|kagi)
   ```

2. **Trim Verbose Descriptions**
   ```
   Before (87 tokens): "This tool allows you to search the web..."
   After (12 tokens): "Search the web. Returns titles, URLs, snippets."
   ```

3. **Selective Activation**
   ```bash
   /mcp disable github  # When not doing git work
   /mcp enable playwright  # When doing frontend work
   ```

**Real Results:**
- 20 tools → 8 tools (60% reduction)
- 8,551 tokens saved per session

## Related Resources

- `MCP_TOKEN_AUDIT_CHECKLIST.md` - Token audit checklist
- `mcp-second-opinion/` - Gemini-powered code review MCP
- `mcp-playwright-persistent/` - Persistent browser automation MCP

---

*Triggers: MCP, token consumption, tool optimization, code-mode*
