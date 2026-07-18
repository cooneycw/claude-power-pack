---
description: Load full Claude Code best practices documentation (25K tokens)
---

Read and summarize the key points from the full best-practices guide. Resolve it
from the first of these locations that exists (the second covers plugin-only
installs, where the cpp plugin bundles the doc - issue #582):

1. `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md` (CPP repo checkout)
2. `${CLAUDE_PLUGIN_ROOT}/docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md` (plugin install)

**Note:** For context efficiency, consider using topic-specific skills instead:
- `context-efficiency` - Token optimization
- `session-management` - Session & plan mode
- `mcp-optimization` - MCP best practices
- `hooks-automation` - Hook system
- `spec-driven-dev` - SDD workflow
- `idd-workflow` - Issue-driven dev
- `claude-md-config` - CLAUDE.md tips
- `code-quality` - Quality patterns
- `build-deploy` - Makefile, uv, and deployment patterns

Focus on:
1. **Top Tips from Power Users** - Most impactful practices from experienced users
2. **Skills System** - Activation patterns and best practices
3. **CLAUDE.md Optimization** - Optimized prompts and tips
4. **MCP Best Practices** - Token efficiency and selection
5. **Context-Efficient Architecture** - Progressive disclosure principles
6. **Hooks & Automation** - Hook system and advanced usage
7. **Build, Test & Deploy Patterns** - Makefile integration, uv, and retrospective improvement

Provide a concise overview highlighting the most actionable insights from the community.

If the user asks about a specific topic, dive deep into that section.
