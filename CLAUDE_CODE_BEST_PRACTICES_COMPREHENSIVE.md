# Claude Code Best Practices - Comprehensive Guide

*Compiled from r/ClaudeCode top posts (Past Month - November 2025)*

**Sources:** 100+ top posts from past month, including the #1 post with 685 upvotes

---

## 📑 Table of Contents

1. [Top Tips from Power Users](#top-tips-from-power-users)
2. [Skills System](#skills-system)
3. [CLAUDE.md Optimization](#claudemd-optimization)
4. [Avoiding Context Degradation](#avoiding-context-degradation)
5. [Spec-Driven Development](#spec-driven-development)
6. [MCP Best Practices](#mcp-best-practices)
7. [Hooks & Automation](#hooks--automation)
8. [Session Management](#session-management)
9. [Plan Mode](#plan-mode)
10. [Code Quality & Review](#code-quality--review)
11. [Workflow Patterns](#workflow-patterns)
12. [Common Pitfalls](#common-pitfalls)
13. [Tools & Resources](#tools--resources)

---

## Top Tips from Power Users

### From "Claude Code is a Beast" (685 upvotes, 6 months experience)

**Repository:** https://github.com/diet103/claude-code-infrastructure-showcase

**Key Insights:**

1. **Skills with Pattern Matching**
   - Use hooks to pre-fetch skills for activation
   - Skill = prompt injection + hook + pattern matching
   - This dramatically improves skill activation rates

2. **Multi-Agent Architecture**
   - Layer your agents for different concerns
   - Separate planning from execution
   - Use specialized agents for review

3. **Infrastructure as Code**
   - Treat your Claude Code setup like infrastructure
   - Version control everything (.claude directory)
   - Share reusable patterns across projects

4. **Development Environment Integration**
   - Use pm2 for process management
   - Integrate with your existing dev tooling
   - Make Claude Code part of your environment, not separate

**Community Response:**
- "99% of gripes, questions, and issues faced in this subreddit can be answered with this post"
- Praised as "CLAUDE CODE 101" masterpiece

---

## Skills System

### Improving Skill Activation Rates (214 upvotes)

**From "Claude Code skills activate 20% of the time. Here's how I got to 84%"**

**Problem:** Default skill activation is around 20%

**Solution:**

1. **Detailed, Context-Rich Skills**
   - Include specific examples and patterns
   - Provide detailed guides for SvelteKit, Svelte 5 runes, data flow patterns
   - More context = better activation

2. **Pattern Matching**
   - Skills need clear trigger patterns
   - Use specific terminology that matches your codebase
   - Make triggers unambiguous

3. **Regular Testing & Refinement**
   - Test skill activation regularly
   - Refine based on what triggers successfully
   - Remove or merge underperforming skills

### Skills Best Practices

**From Community Discussion:**

- **Skills = Prompt Injection**
  - At core, skills are just specialized prompts
  - Power comes from combining with hooks and patterns
  - Think of them as reusable context modules

- **Don't Overload**
  - 1-3 well-crafted skills better than 10 mediocre ones
  - Each skill should have clear, distinct purpose
  - Avoid overlap between skills

- **Version Control Skills**
  - Keep skills in git
  - Share successful patterns with team
  - Document what triggers each skill

**Registry:** https://claude-plugins.dev/skills (6000+ public skills)

---

## CLAUDE.md Optimization

### Optimized Prompts (+5-10% on SWE Bench)

**From "Optimized CLAUDE.md prompt instructions" (53 upvotes)**

**Key Finding:** You can significantly improve performance by optimizing CLAUDE.md

**Recommendations:**

1. **Experiment with System Prompts**
   - Don't accept defaults
   - Test different prompt formulations
   - Measure results on your specific use cases

2. **Include Project-Specific Context**
   - Architecture decisions
   - Coding standards
   - Common patterns in your codebase

3. **Be Explicit About Constraints**
   - What NOT to do
   - Token budgets
   - Performance requirements

### CLAUDE.md Tips (30 upvotes)

**From "CLAUDE.md tips" thread:**

1. **Structure Matters**
   - Use clear sections
   - Prioritize most important info at top
   - Use markdown formatting effectively

2. **Include Examples**
   - Show desired code style
   - Provide example workflows
   - Demonstrate edge cases

3. **Set Expectations**
   - Define quality bars
   - Specify test requirements
   - Clarify documentation needs

4. **Update Regularly**
   - CLAUDE.md should evolve with your project
   - Add learnings from mistakes
   - Remove outdated guidance

---

## Avoiding Context Degradation

### "How to avoid claude getting dumber (for real)" (47 upvotes)

**Problem:** Claude Code gets progressively worse during long sessions

**Root Cause:** Conversation compacting

**Solutions:**

1. **Avoid Compacting When Possible**
   - Each compact loses information
   - Start fresh session instead
   - Use git commits as natural break points

2. **Strategic Session Resets**
   - After completing major feature
   - When switching between different areas of codebase
   - If you notice quality degradation

3. **Context Files Instead of Conversation**
   - Store important context in files (CLAUDE.md, docs)
   - Don't rely on conversation history
   - Make context accessible via file reads

4. **Initialization Commands**
   - Use /prepare or similar to load fresh context
   - Keep context loading consistent
   - Document what context is needed for what tasks

---

## Spec-Driven Development

### "Why we shifted to Spec-Driven Development" (107 upvotes)

**Problem:** As features multiply, consistency and quality suffer

**Solution:** Spec-Driven Development (SDD)

**Approach:**

1. **Write Detailed Specs First**
   - Before any code
   - Include edge cases
   - Define success criteria

2. **Review Specs, Not Just Code**
   - Easier to fix design issues before coding
   - Specs are cheaper to iterate than code
   - Gets team alignment early

3. **Use Specs as Reference**
   - Claude can check code against spec
   - Automated verification possible
   - Clear acceptance criteria

4. **Iterate on Specs**
   - Specs are living documents
   - Update based on learnings
   - Version control specs like code

**Tools:**
- GitHub Spec Kit (mentioned but debated in community)
- Custom spec frameworks
- Markdown-based specs in repo

**Debate:** Some users question if SDD frameworks add real value vs overhead
- Works better for teams than solo developers
- May slow down rapid prototyping
- Best for complex, multi-person projects

---

## MCP Best Practices

### Code-Mode: Save >60% in tokens (242 upvotes)

**Repository:** https://github.com/universal-tool-calling-protocol/code-mode

**Key Innovation:** Execute MCP tools via code execution instead of direct calls

**Benefits:**
- 60% token savings
- More efficient MCP usage
- Less context bloat

### One MCP to Rule Them All (95 upvotes)

**From "no more toggling MCPs on/off":**

**Approach:** Use orchestrator MCP that manages other MCPs

**Benefits:**
- Don't need to enable/disable MCPs manually
- Intelligent routing to appropriate MCP
- Cleaner context

**Reference:** https://www.anthropic.com/engineering/code-execution-with-mcp

### MCP Selection

**Top MCPs Mentioned:**

1. **DevTools MCP** - Preferred over Playwright by some
2. **Playwright MCP** - Great for frontend work (but token-heavy)
3. **Context 7** - Context management
4. **Supabase** - Database operations

**Wisdom:**
- "MCP is king of token consumption"
- Choose 1-3 quality MCPs
- Many users prefer direct code over MCP
- MCPs work best with dedicated subagent instructions

### Converting MCP to Skills (175 upvotes)

**From "I've successfully converted 'chrome-devtools-mcp' into Agent Skills":**

**Why Convert:**
- Chrome-devtools-mcp is useful but token-heavy
- Skills can be more targeted and efficient
- Better control over when/how tools activate

**Approach:**
- Extract core functionality
- Create focused skills for specific use cases
- Maintain benefits while reducing token usage

---

## Hooks & Automation

### Hook System Deep Dive (85 upvotes)

**From "Claude Code hooks confuse everyone at first":**

**Key Resource:** https://github.com/disler/claude-code-hooks-mastery

**Hook Types & Uses:**

1. **SessionStart** - Load context, setup environment
2. **UserPromptSubmit** - Validate/enrich prompts before sending
3. **ToolUse** - Intercept or modify tool usage
4. **ToolResult** - Process outputs before Claude sees them
5. **SessionEnd** - Cleanup, logging

**Best Practices:**

- Understand lifecycle to avoid fighting execution flow
- Use hooks for automation, not control
- Keep hooks simple and fast
- Log hook activity for debugging

### Advanced Hook Usage

**Pattern Matching for Skills (from 685 upvote post):**
- Use hooks to pre-fetch relevant skills
- Match patterns in user prompts
- Automatically activate appropriate context

**Editor Integration:**
- Use Ctrl-G hook to launch custom tools
- Extend beyond just opening editor
- Hook into any workflow automation

---

## Session Management

### The Single Most Useful Line (98 upvotes)

**From "The single most useful line for getting what you want from Claude Code":**

```
"Please let me know if you have any questions before making the plan!"
```

**Why It Works:**
- Forces Claude to clarify ambiguities upfront
- Prevents wasted work on wrong assumptions
- Creates dialogue before execution
- Especially powerful in Plan Mode

**Extension:**
- "Tell me if anything is unclear before proceeding"
- "What additional information do you need?"
- "Identify any assumptions you're making"

### When to Reset Sessions

**Patterns from Community:**

1. **Feature-Based** (most common)
   - One session per feature
   - Fresh start after git commit
   - Clear success criteria per session

2. **Time-Based**
   - Every 5-10 messages
   - After 1-2 hours of work
   - When reaching 60% context

3. **Quality-Based**
   - When Claude seems "confused"
   - After multiple failed attempts
   - When suggestions become repetitive

4. **Never Reset** (for some users)
   - If you have good tests and conventions
   - Context degradation less of issue
   - Continuous work style

### Context Management Patterns

**Initialization Context (from multiple sources):**

1. Create `/prepare` command
2. Load from memory bank (markdown files)
3. Include recent git history
4. Load relevant docs

**Memory Bank Structure:**
- Project overview
- Architecture decisions
- Current priorities
- Known issues
- Coding standards

---

## Plan Mode

### Use Plan Mode by Default (72 upvotes)

**From "4 Claude Code CLI tips I wish I knew earlier":**

**Benefits:**
- 20-30% better results
- Reduces wasted prompts
- Creates accountability
- Forces thinking before acting

**Enhanced Plan Mode** (37 upvotes)

**From "I made a better version of Plan Mode":**
- Custom plan mode implementations
- More detailed planning phases
- Integration with issue tracking

**Official Updates:**
- Claude Code 2.0.31 introduced new Plan subagent
- Enhanced subagent capabilities
- Better plan quality

---

## Code Quality & Review

### Production-Ready Software (76 upvotes)

**From "This is how I use the Claude ecosystem to actually build production-ready software":**

**Key Insight:** "You are the issue, not the AI"

**Approach:**

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

### Review Patterns

**Pre-Code Review with GPT-4:**
- Use Codex to verify requirements
- Check for missed details
- Ensure specification compliance

**Self-Review:**
- Ask Claude to review its own code
- Have it identify potential issues
- Explain design decisions

---

## Workflow Patterns

### Parallel Agents (32 upvotes)

**From "Anyone else do this parallel agent hail mary":**

**When:** Stuck on difficult problem

**Approach:**
- Spawn multiple agents with different approaches
- Let them work in parallel
- Pick best solution

**Note:** Token-intensive but surprisingly effective

### tmux as Orchestration (59 upvotes)

**From "Using tmux as a bootleg orchestration system":**

**Setup:**
- Multiple Claude Code sessions in tmux
- Each pane handles different concern
- Cross-session coordination

**Benefits:**
- Separate contexts for separate tasks
- Easy switching between sessions
- Visual organization

### Multi-Instance Setup (39 upvotes)

**From "Run 2 (or even more) instances of Claude Code in parallel":**

**Use Cases:**
- Frontend + Backend simultaneously
- Different branches
- Experimentation vs production work

**Technical:**
- Separate working directories
- Different credential profiles
- Process isolation

---

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

### Warning: Malware in Skills (80 upvotes)

**From "Be careful with people spreading Claude Code Skills as malware on Github":**

**Risk:** Skills can execute arbitrary code

**Protection:**
- Review skills before installing
- Use trusted sources only
- Check skill code, not just description
- Be wary of skills from unknown authors

---

## Tools & Resources

### Essential Tools

**Task Management:**
- Markdown Task Manager: https://reddit.com/r/ClaudeCode/comments/1ot8nh2 (100 upvotes)
- Beads (issue tracker)
- Custom .claude/active/ folder system

**Switching Tools:**
- Clother - Switch between GLM, Kimi, Minimax, Anthropic endpoints
  https://github.com/jolehuit/clother

**Model Alternatives:**
- Gemini 3 Pro via gemini-cli
  https://github.com/forayconsulting/gemini_cli_skill
- Kimi K2 Thinking model integration
- GLM endpoint (but lacks web search)

**Skill Resources:**
- claude-plugins.dev (6000+ skills)
- Superpowers plugin: https://github.com/obra/superpowers
- Prompt Coach skill (analyzes prompt quality)

### Key Repositories

1. **Infrastructure Showcase** (from 685 upvote post)
   https://github.com/diet103/claude-code-infrastructure-showcase

2. **Hooks Mastery**
   https://github.com/disler/claude-code-hooks-mastery

3. **Code-Mode (60% token savings)**
   https://github.com/universal-tool-calling-protocol/code-mode

4. **Chrome DevTools as Skills**
   (converted from MCP - 175 upvotes)

### Official Updates

**Recent Claude Code Releases:**
- 2.0.27 - Claude Code on Web
- 2.0.31 - New Plan subagent
- 2.0.36 - Web enhancements
- 2.0.41 - UX improvements
- 2.0.50 - Latest with enhanced features

**Free Credits:**
- $1000 free usage for Pro/Max on CC Web (temporary)
- Credits reset behavior has been buggy
- May count against weekly limits

---

## Advanced Patterns

### Spec-First → Sandbox → Production

**From 685 upvote post + community:**

1. **Write Spec**
   - Detailed requirements
   - Edge cases
   - Success criteria

2. **Sandbox Testing** (Sonnet)
   - Separate directory for experiments
   - Verify key parts work
   - Try uncertain approaches

3. **Implementation** (Opus for complex, Sonnet for standard)
   - Cut-and-dry based on verified plan
   - Minimal decisions needed
   - Fast execution

4. **Review & Refine**
   - Test against spec
   - Iterate if needed
   - Git commit

### Multi-Repo Management

**From "perfect multi-repo-multi-model Code agent workspace":**

- Separate Claude Code instances per repo
- Model selection based on task type
- Coordination via shared documentation
- Flowchart for decision making

### Progressive Enhancement

**Pattern from Community:**

1. **Claude Prototype** - Get something working
2. **Vibe Code** - Iterate on feel/UX
3. **Freelancer Finish** - Professional polish

**Alternative:** All-Claude if quality standards maintained

---

## Best Practices Summary

### Top 10 Rules

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

### Red Flags

- 🚩 Context >60% and starting new complex feature
- 🚩 Claude giving contradictory advice
- 🚩 Repetitive failures on same task
- 🚩 Ignoring requirements you clearly stated
- 🚩 Taking approaches you explicitly rejected
- 🚩 Installing skills from unknown sources

### Green Flags

- ✅ Claude asks clarifying questions before proceeding
- ✅ Proposes multiple approaches and explains tradeoffs
- ✅ References your existing code patterns
- ✅ Suggests tests for new functionality
- ✅ Explains architectural decisions
- ✅ Admits when uncertain

---

## Model-Specific Notes

### Sonnet 4.5

**Strengths:**
- General purpose
- Good balance of cost/quality
- "Monster" for most tasks

**1M Context vs 200K:**
- Debate in community about actual benefits
- Some users see improvements
- Others see no difference
- May depend on use case

### Haiku 4.5

**When to Use:**
- Burn through limits slower
- Simple, well-defined tasks
- Documentation
- Code review

**Data from Pro user:**
- Significantly better token efficiency
- Acceptable quality for many tasks
- Good for extending weekly limits

### Opus

**When to Use:**
- Complex architectural decisions
- Planning phase
- Novel problems
- When quality > cost

### Alternative Models

**Gemini 3 Pro:**
- Via gemini-cli
- Competitive performance
- Different strengths/weaknesses

**Kimi K2 Thinking:**
- Impressive benchmarks
- Thinking/reasoning model
- Integration available

---

## Community Insights

### On AI-Assisted Development

**From experienced developers:**

> "Seasoned developers *embracing* AI tools, not shrugging them off as 'stupid' or 'a threat'. This is exactly the way."

> "You are the issue, not the AI" - Most complaints about AI code quality stem from unclear requirements

> "Claude is basically the world's dumbest junior engineer" - Set expectations accordingly

### On Learning Curve

**Progression:**
1. Fighting with Claude (week 1-2)
2. Learning to communicate (month 1)
3. Building infrastructure (months 2-3)
4. Optimization and mastery (months 4-6)

**Key Turning Point:** When you stop trying to control Claude and start collaborating

### On Productivity

**Mixed Reports:**

**Positive:**
- 10x productivity on greenfield projects
- Great for prototyping
- Excellent for exploration

**Realistic:**
- Not faster than expert on familiar tasks
- Saves time on unfamiliar tech
- Better for breadth than depth

**The Real Value:**
> "I don't think it writes better code than me... But I can just sit here and watch football and occasionally give direction" - Doing more with less active work

---

## Document Metadata

**Compiled:** November 2025
**Sources:**
- 100+ top posts from r/ClaudeCode (past month)
- 200+ comments analyzed
- Primary source: 685-upvote "Beast" post
- Secondary sources: 214-upvote skills post, 117-upvote best practices collation

**Update Frequency:** This represents November 2025 state of community knowledge. Claude Code evolves rapidly, so check recent posts for latest practices.

**Contributing:** This is a living document. Feel free to add your own learnings and share back with the community.

---

## Acknowledgments

Special thanks to the r/ClaudeCode community contributors:
- u/JokeGold5455 (Beast post)
- u/rm-rf-rm (Best practices collation v2)
- u/spences10 (Skills activation)
- u/daaain (Single most useful line)
- u/cryptoviksant (Avoiding context degradation)
- u/NumbNumbJuice21 (CLAUDE.md optimization)
- u/eastwindtoday (Spec-driven development)
- u/juanviera23 (Code-mode)
- And hundreds of other community members sharing their experiences

---

*End of Guide*

For latest updates, join r/ClaudeCode and sort by "Top" → "This Month"
