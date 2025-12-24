# Code Quality & Review Patterns

*From Claude Code Best Practices - r/ClaudeCode community wisdom*

## Production-Ready Software (76 upvotes)

**From "This is how I use the Claude ecosystem to actually build production-ready software":**

**Key Insight:** "You are the issue, not the AI"

## The Approach

1. **Clear Requirements**
   - Be specific about what you want
   - Include edge cases
   - Define quality standards

2. **Iterative Review**
   - Don't accept first output
   - Ask for improvements
   - Challenge assumptions

3. **Test-Driven**
   - Write tests first
   - Verify behavior
   - Regression protection

4. **Use Multiple Claude Tools**
   - Claude Code for implementation
   - Claude.ai for design discussions
   - Different tools for different phases

## Review Patterns

**Pre-Code Review with GPT-4:**
- Use Codex to verify requirements
- Check for missed details
- Ensure specification compliance

**Self-Review:**
- Ask Claude to review its own code
- Have it identify potential issues
- Explain design decisions

## Common Pitfalls

### Things That Make Claude "Dumber"

1. **Long Sessions Without Reset**
   - Compacting loses information
   - Contradictory context builds up
   - Fresh start often better

2. **Unclear Requirements**
   - Vague prompts = vague results
   - Missing edge cases
   - Assumed knowledge

3. **Fighting Claude's Patterns**
   - Let it use familiar patterns
   - Don't force unusual approaches
   - Work with defaults, not against

4. **Over-Reliance on Conversation History**
   - Put important info in files
   - Don't trust compacted history
   - Document decisions

## Workflow Patterns (32-59 upvotes)

### Parallel Agents
**When:** Stuck on difficult problem

**Approach:**
- Spawn multiple agents with different approaches
- Let them work in parallel
- Pick best solution

**Note:** Token-intensive but surprisingly effective

### tmux as Orchestration
**Setup:**
- Multiple Claude Code sessions in tmux
- Each pane handles different concern
- Cross-session coordination

**Benefits:**
- Separate contexts for separate tasks
- Easy switching between sessions
- Visual organization

### Multi-Instance Setup
**Use Cases:**
- Frontend + Backend simultaneously
- Different branches
- Experimentation vs production work

## Quality Signals

### Red Flags
- Context >60% and starting new complex feature
- Claude giving contradictory advice
- Repetitive failures on same task
- Ignoring requirements you clearly stated
- Taking approaches you explicitly rejected

### Green Flags
- Claude asks clarifying questions before proceeding
- Proposes multiple approaches and explains tradeoffs
- References your existing code patterns
- Suggests tests for new functionality
- Explains architectural decisions
- Admits when uncertain

## Top 10 Rules

1. **Use Plan Mode by default** - Ask Claude to clarify before acting
2. **Reset sessions frequently** - After features, at 60% context, or when quality drops
3. **Store context in files, not conversations** - CLAUDE.md, docs, specs
4. **Choose 1-3 quality MCPs** - More isn't better; efficiency matters
5. **Write detailed specs first** - Especially for complex work
6. **Use hooks for automation** - Pre-fetch skills, validate prompts
7. **Skills need good activation patterns** - Detailed, context-rich, specific triggers
8. **Review skills before installing** - Security risk from untrusted sources
9. **Optimize CLAUDE.md for your project** - Experiment, measure, iterate
10. **Work with Claude's strengths** - Familiar patterns, clear requirements, iterative refinement

---

*Triggers: code review, quality, testing, production ready, best practices*
