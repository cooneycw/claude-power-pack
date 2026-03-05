# MCP vs Skills: Decision Boundary Guide

## Overview

This document provides guidance on when to use MCP servers versus Skills in Claude Code, based on token budget considerations, deployment complexity, and use case patterns.

## Quick Decision Tree

```
Is the functionality external/stateful? (API, database, browser)
├─ YES → Use MCP Server
│   └─ Does it need isolation/secrets?
│       ├─ YES → Docker deployment
│       └─ NO → stdio/systemd is fine
│
└─ NO → Is it documentation/guidance?
    ├─ YES → Use Skill
    └─ NO → Is it a simple utility?
        ├─ YES → Use Skill
        └─ NO → Consider MCP if >5 tools needed
```

## When to Use MCP Servers

### ✅ Use MCP When:

1. **External Service Integration**
   - API calls (Gemini, OpenAI, GitHub)
   - Database connections (PostgreSQL, Redis)
   - Browser automation (Playwright)
   - File system operations requiring isolation

2. **Stateful Operations**
   - Session management across conversations
   - Caching/memoization
   - Rate limiting
   - Connection pooling

3. **Security Requirements**
   - API key management
   - Secret isolation
   - SSRF protection
   - Sandboxed execution

4. **Complex Tool Sets**
   - 5+ related tools
   - Shared state between tools
   - Tool orchestration

5. **Reusability Across Projects**
   - Generic functionality (code review, testing)
   - Not project-specific

### 📦 Docker vs stdio/systemd for MCP

**Use Docker when:**
- Multiple environment dependencies
- Need complete isolation
- Deploying to cloud (AWS, Azure)
- Team collaboration (consistent environments)
- Secret management complexity

**Use stdio/systemd when:**
- Simple Python/Node server
- Local development only
- Minimal dependencies
- Fast iteration needed

## When to Use Skills

### ✅ Use Skills When:

1. **Documentation & Guidance**
   - Best practices
   - Workflow patterns
   - Project conventions
   - Architecture decisions

2. **Simple Utilities**
   - Text formatting
   - Template generation
   - Simple calculations
   - File path helpers

3. **Project-Specific Context**
   - Codebase conventions
   - Team workflows
   - Domain knowledge
   - Historical decisions

4. **Token Efficiency Critical**
   - Skills load on-demand (~100 tokens metadata)
   - MCP tools always loaded (500-2000 tokens each)
   - For rarely-used functionality, Skills win

5. **No External Dependencies**
   - Pure logic/guidance
   - No API calls
   - No state management

## Token Budget Policy

### MCP Server Token Costs

| Component | Token Cost | Notes |
|-----------|-----------|-------|
| Tool metadata | 100-200 per tool | Always loaded |
| Tool instructions | 500-2000 per tool | Loaded when relevant |
| Server connection | 200-500 | Per server |
| **Total per server** | **5K-50K** | Depends on tool count |

### Skill Token Costs

| Component | Token Cost | Notes |
|-----------|-----------|-------|
| Skill metadata | ~100 | Always loaded |
| Skill content | 1K-5K | Loaded on-demand |
| **Total per skill** | **1K-5K** | Only when activated |

### Budget Guidelines

**For 200K context window:**
- Reserve 50K for conversation history
- Reserve 50K for code/files
- Allocate 50K for tools/skills
- Keep 50K buffer

**Tool/Skill Mix:**
- 3-5 MCP servers (15K-50K tokens)
- 10-20 Skills (10K-20K tokens when loaded)
- Total: 25K-70K tokens

## Real-World Examples

### Example 1: Code Review

**❌ Bad: Skill-based code review**
```
Problem: Can't call external APIs, no multi-model comparison
Result: Limited to Claude's own analysis
```

**✅ Good: MCP Second Opinion**
```
Benefits:
- Multi-model consultation (Gemini, OpenAI, Claude)
- Agentic tool use (web search, docs)
- Session state management
- Cost tracking
```

### Example 2: Project Conventions

**✅ Good: Skill-based conventions**
```
Benefits:
- Pure documentation
- No external dependencies
- Loads on-demand
- Easy to update
```

**❌ Bad: MCP server for conventions**
```
Problem: Wastes tokens, adds complexity
Result: Always loaded, harder to maintain
```

### Example 3: Browser Testing

**✅ Good: MCP Playwright**
```
Benefits:
- Stateful browser sessions
- Screenshot capture
- Complex automation
- Isolation from main process
```

**❌ Bad: Skill-based browser automation**
```
Problem: Can't control browser, no state
Result: Impossible to implement
```

## Migration Patterns

### Converting MCP to Skill

**When to migrate:**
- Tool usage <5% of sessions
- No external dependencies discovered
- Pure documentation/guidance
- Token budget pressure

**How to migrate:**
1. Extract tool instructions to Skill markdown
2. Remove API/state dependencies
3. Test activation patterns
4. Deprecate MCP server

### Converting Skill to MCP

**When to migrate:**
- Need external API calls
- Require state management
- Tool set growing (>3 related tools)
- Security isolation needed

**How to migrate:**
1. Create MCP server scaffold
2. Implement tools with proper state
3. Add API key management
4. Deploy (stdio or Docker)
5. Update Claude config

## Docker Deployment Best Practices

### When Docker Makes Sense

1. **Production Deployments**
   - AWS ECS/Fargate
   - Azure Container Instances
   - Kubernetes clusters

2. **Team Collaboration**
   - Consistent environments
   - Easy onboarding
   - CI/CD integration

3. **Complex Dependencies**
   - Multiple services (PostgreSQL, Redis)
   - System libraries
   - Version conflicts

### Docker Compose Profiles

Use profiles to manage optional services:

```yaml
services:
  mcp-second-opinion:
    profiles: ["core"]
    # Always started
  
  mcp-playwright:
    profiles: ["testing"]
    # Only for testing workflows
  
  mcp-coordination:
    profiles: ["team"]
    # Only for team collaboration
```

**Start specific profiles:**
```bash
docker-compose --profile core up
docker-compose --profile core --profile testing up
```

### Secrets Management in Docker

**❌ Bad: Hardcoded secrets**
```dockerfile
ENV GEMINI_API_KEY=hardcoded-key
```

**✅ Good: Environment variables**
```yaml
services:
  mcp-server:
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
```

**✅ Better: Docker secrets (Swarm/Kubernetes)**
```yaml
services:
  mcp-server:
    secrets:
      - gemini_api_key
secrets:
  gemini_api_key:
    external: true
```

## Decision Checklist

Before implementing new functionality, ask:

- [ ] Does it need external APIs? → MCP
- [ ] Does it need state management? → MCP
- [ ] Is it pure documentation? → Skill
- [ ] Will it be used <10% of sessions? → Skill
- [ ] Does it need 5+ related tools? → MCP
- [ ] Is it project-specific? → Skill
- [ ] Does it need security isolation? → MCP (Docker)
- [ ] Is token budget tight? → Skill
- [ ] Will it be reused across projects? → MCP
- [ ] Is it a simple utility? → Skill

## Monitoring & Optimization

### Track Token Usage

Use `/second-opinion:cost` to monitor:
- Per-session token consumption
- Daily token budgets
- Cost per model

### Optimize MCP Servers

1. **Reduce tool count**: Combine related tools
2. **Lazy loading**: Load instructions on-demand
3. **Caching**: Cache expensive operations
4. **Batching**: Batch API calls

### Optimize Skills

1. **Progressive disclosure**: Split large skills
2. **Activation patterns**: Make triggers specific
3. **Content size**: Keep skills <5K tokens
4. **Metadata**: Write clear, concise descriptions

## References

- [Progressive Disclosure Guide](../../PROGRESSIVE_DISCLOSURE_GUIDE.md)
- [MCP Token Audit Checklist](../../MCP_TOKEN_AUDIT_CHECKLIST.md)
- [MCP Optimization Skill](../skills/mcp-optimization.md)
- [Context Efficiency Skill](../skills/context-efficiency.md)

## Revision History

- 2026-03-05: Initial version (Issue #197)
