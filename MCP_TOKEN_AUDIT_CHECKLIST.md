# MCP Token Audit Checklist

Use this checklist to optimize your MCP configuration for token efficiency.

## Pre-Session Audit

- [ ] Run `/context` to see current token distribution
- [ ] Identify MCP servers consuming >10K tokens
- [ ] List tools you actually need for this session
- [ ] Disable unnecessary MCP servers

## Per-Server Analysis

For each MCP server, answer:

- [ ] How many tokens does this server consume?
- [ ] How many tools does it expose?
- [ ] Which tools do I use regularly?
- [ ] Which tools could be consolidated?
- [ ] Are descriptions unnecessarily verbose?

## Consolidation Opportunities

Check for these patterns:

- [ ] Multiple search tools → Single tool with `provider` parameter
- [ ] Multiple CRUD tools → Single tool with `operation` parameter
- [ ] Platform-specific tools → Single tool with `platform` parameter
- [ ] Version-specific tools → Single tool with `version` parameter

## Description Optimization

For each tool description:

- [ ] Is it under 200 characters?
- [ ] Does it avoid redundant phrases like "This tool allows you to..."?
- [ ] Does it focus on WHAT not HOW?
- [ ] Are examples in the schema, not description?

## Skills Conversion Candidates

Consider converting to Skills if:

- [ ] Tool primarily teaches a procedure
- [ ] Tool is used infrequently
- [ ] Tool has complex documentation
- [ ] Tool doesn't need real-time external access

## Post-Optimization Verification

- [ ] Run `/context` again to measure improvement
- [ ] Test that consolidated tools still work
- [ ] Verify no functionality was lost
- [ ] Document changes for team

## Target Metrics

| Metric | Target |
|--------|--------|
| Total MCP token overhead | <30K tokens |
| Per-server consumption | <10K tokens |
| Active servers per session | 1-3 |
| Tool description length | <200 chars |

## Quick Reference Commands

```bash
# Check context usage
/context

# Disable MCP server
/mcp disable <server-name>

# Enable MCP server
/mcp enable <server-name>

# List active MCP servers
/mcp list

# Use mcpick for session-specific selection
npx mcpick
```

## Common Token Bloat Patterns

### Pattern 1: Search Provider Explosion
**Before:** 4 separate search tools (Tavily, Brave, Kagi, Exa) = ~8K tokens
**After:** 1 unified search tool with provider parameter = ~2K tokens
**Savings:** 75%

### Pattern 2: Verbose Descriptions
**Before:** "This comprehensive tool allows developers to search through web content using various powerful search engines..."
**After:** "Search web content. Supports multiple providers."
**Savings:** 60%

### Pattern 3: Overlapping Functionality
**Before:** `get_file`, `read_file`, `fetch_file`, `load_file`
**After:** `read_file` (standardized name)
**Savings:** 75%

## Decision Tree

```
Is the tool used in >80% of sessions?
├─ Yes → Keep loaded
└─ No → Is it procedural knowledge?
    ├─ Yes → Convert to Skill
    └─ No → Can it be consolidated?
        ├─ Yes → Merge with similar tools
        └─ No → Enable only when needed
```

## Resources

- [Progressive Disclosure Guide](PROGRESSIVE_DISCLOSURE_GUIDE.md)
- [Context-Efficient Tool Architecture](CLAUDE_CODE_BEST_PRACTICES_COMPREHENSIVE.md#context-efficient-tool-architecture)
- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Scott Spence: MCP Context Optimization](https://scottspence.com/posts/optimising-mcp-server-context-usage-in-claude-code)
