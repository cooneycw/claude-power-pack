---
name: Best Practices Dispatcher
description: Routes to topic-specific best practices skills for context efficiency
trigger: best practices, claude code help, how to, tips
---

# Best Practices Dispatcher

This skill routes questions to topic-specific skills for context efficiency.
Instead of loading 25K+ tokens, load only the relevant topic (~3K tokens).

## Available Topic Skills

| Topic | Skill | Triggers |
|-------|-------|----------|
| **Context & Tokens** | `context-efficiency` | context, tokens, optimization, progressive disclosure |
| **Session Management** | `session-management` | session, reset, plan mode, context degradation |
| **MCP Optimization** | `mcp-optimization` | MCP, token consumption, code-mode |
| **Skills Design** | `skills-patterns` | skill activation, skill design, prompt injection |
| **Hooks** | `hooks-automation` | hooks, automation, SessionStart |
| **Spec-Driven Dev** | `spec-driven-dev` | spec driven, specification, SDD, planning |
| **Issue-Driven Dev** | `idd-workflow` | issue driven, worktree, IDD |
| **CLAUDE.md** | `claude-md-config` | CLAUDE.md, configuration, project setup |
| **Code Quality** | `code-quality` | code review, quality, testing, production |
| **Python Packaging** | `python-packaging` | pyproject.toml, PEP 621, PEP 723, setup.py, requirements.txt |

## Routing Logic

When the user asks about best practices:

1. **Identify the topic** from their question
2. **Route to the specific skill** by reading its docs/skills file
3. **If unclear**, ask which topic they need help with

## Quick Reference

**Top 10 Rules:**
1. Use Plan Mode by default
2. Reset sessions frequently
3. Store context in files, not conversations
4. Choose 1-3 quality MCPs
5. Write detailed specs first
6. Use hooks for automation
7. Skills need good activation patterns
8. Review skills before installing
9. Optimize CLAUDE.md for your project
10. Work with Claude's strengths

## Full Reference

For the complete unabridged guide:
- Read `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md`

## Related Resources

- `PROGRESSIVE_DISCLOSURE_GUIDE.md` - Context architecture
- `MCP_TOKEN_AUDIT_CHECKLIST.md` - Token audit steps
- `ISSUE_DRIVEN_DEVELOPMENT.md` - IDD methodology
