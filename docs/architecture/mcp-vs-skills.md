# MCP vs Skills: Decision Boundary

When adding new functionality to Claude Power Pack, choose between MCP tools and Skills based on these criteria.

## Decision Tree

```
Does the feature need real-time external access (APIs, browsers, databases)?
  YES -> MCP Tool
  NO  -> Does it teach a procedure or workflow?
    YES -> Skill
    NO  -> Does it need to run frequently with low latency?
      YES -> MCP Tool
      NO  -> Skill
```

## Comparison

| Criteria | MCP Tool | Skill |
|----------|----------|-------|
| **Token cost** | Always loaded (~200-2K tokens/tool) | Loaded on demand (~0 idle) |
| **External access** | Yes (APIs, filesystem, network) | No (prompt-only) |
| **Latency** | Fast (direct function call) | None (injected into prompt) |
| **State** | Can maintain state (sessions, caches) | Stateless |
| **Deployment** | Server process (stdio/SSE/Docker) | Markdown file in `.claude/skills/` |
| **Complexity** | Python code, dependencies, tests | Markdown with instructions |
| **Discoverability** | Auto-listed by Claude Code | Triggered by keywords |

## When to Use MCP

- Calling external LLM APIs (Gemini, OpenAI, Anthropic)
- Browser automation (Playwright sessions)
- Diagram rendering (HTML generation, screenshot capture)
- Any operation requiring network I/O or persistent state

## When to Use Skills

- Teaching Claude a workflow (e.g., `/flow:auto`, `/spec:sync`)
- Loading reference documentation on demand
- Domain-specific prompting (e.g., evaluation domain types)
- Procedures that compose existing tools
- Anything that would bloat idle token usage if always loaded

## Token Budget Policy

| Category | Budget | Rationale |
|----------|--------|-----------|
| MCP server (always loaded) | <10K tokens | Per MCP_TOKEN_AUDIT_CHECKLIST |
| Per-tool description | <200 chars | Minimize idle overhead |
| Skill (on demand) | <5K tokens | Only loaded when triggered |
| CLAUDE.md | <30K tokens | Always in context |

## Migration Checklist

Moving functionality from MCP to Skill (or vice versa):

1. Identify whether the feature needs real-time external access
2. Measure current token overhead (`/context`)
3. If converting MCP -> Skill: extract procedure into markdown, remove tool
4. If converting Skill -> MCP: implement as FastMCP tool, add to server
5. Update CLAUDE.md references
6. Verify no functionality lost

## Examples

| Feature | Type | Why |
|---------|------|-----|
| Code review via Gemini | MCP | Calls external Gemini API |
| Browser screenshots | MCP | Controls Chromium process |
| Diagram generation | MCP | Renders HTML, captures images |
| `/evaluate:issue` workflow | Skill | Orchestrates existing MCP tools |
| Best practices loading | Skill | Loads reference docs on demand |
| Security scanning | Skill + lib | Runs local Python modules |
| `/flow:auto` lifecycle | Skill | Composes git + gh + make commands |
