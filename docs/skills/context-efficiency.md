# Context Efficiency & Token Optimization

*From Claude Code Best Practices - r/ClaudeCode community wisdom*

## The Token Budget Reality

**Anthropic's Data (from official engineering blog):**

| Scenario | Token Consumption |
|----------|-------------------|
| Traditional tool loading (100 tools) | ~77K tokens |
| With Tool Search Tool | ~8.7K tokens |
| **Savings** | **85%** |

**Tool Selection Accuracy Impact:**

| Model | Without Tool Search | With Tool Search |
|-------|---------------------|------------------|
| Opus 4 | 49% | 74% |
| Opus 4.5 | 79.5% | 88.1% |

## Progressive Disclosure Principle

**Definition:** Load tool context in stages, not all at once.

**Three-Tier Pattern:**
1. **Tier 1 - Metadata** (~100 tokens): Name + brief description
2. **Tier 2 - Instructions** (<5K tokens): Full documentation when relevant
3. **Tier 3 - Assets** (variable): Scripts/files only when executing

This is how Anthropic's Skills system works internally.

## Practical Application

**For MCP Users:**
1. Use `/context` to audit token consumption
2. Disable unused MCP servers per session
3. Consolidate similar tools (4 search providers → 1 with parameter)
4. Keep descriptions under 200 characters

**For Skills Users:**
1. Structure skills for lazy loading
2. Put detailed instructions in body, not metadata
3. Use clear trigger patterns
4. Let the system load full content only when matched

**For Large Tool Libraries (10+ tools):**
1. Consider Tool Search Tool pattern
2. Mark infrequently-used tools as `defer_loading: true`
3. Keep only essential tools loaded by default

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

## MCP Token Optimization Techniques

**From Scott Spence's Production Optimization:**

1. **Consolidate Related Tools**
   ```
   Before: web_search_tavily, web_search_brave, web_search_kagi
   After:  web_search (provider: tavily|brave|kagi)
   ```

2. **Trim Verbose Descriptions**
   ```
   Before (87 tokens): "This tool allows you to search the web using
   various search engines. It supports multiple providers and returns
   results in a structured format with titles, URLs, and snippets..."

   After (12 tokens): "Search the web. Returns titles, URLs, snippets."
   ```

3. **Standardize Parameter Names**
   - Use `query` not `search_term`
   - Use `limit` not `max_results`
   - Use `provider` not `engine`

4. **Selective Activation**
   ```bash
   # Use mcpick for session-specific server selection
   npx mcpick

   # Or use Claude Code native commands
   /mcp disable github  # When not doing git work
   /mcp enable playwright  # When doing frontend work
   ```

**Real Results:**
- 20 tools → 8 tools (60% reduction)
- 8,551 tokens saved per session
- Same functionality maintained

## Related Resources

- `PROGRESSIVE_DISCLOSURE_GUIDE.md` - Comprehensive architecture guidance
- `MCP_TOKEN_AUDIT_CHECKLIST.md` - Step-by-step token audit

---

*Triggers: context, tokens, optimization, token budget, progressive disclosure*
