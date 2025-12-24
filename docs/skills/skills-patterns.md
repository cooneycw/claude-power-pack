# Skills System & Activation Patterns

*From Claude Code Best Practices - r/ClaudeCode community wisdom*

## Key Insight from Power Users (685 upvotes)

**From "Claude Code is a Beast":**

**Skills with Pattern Matching:**
- Use hooks to pre-fetch skills for activation
- Skill = prompt injection + hook + pattern matching
- This dramatically improves skill activation rates

**Repository:** https://github.com/diet103/claude-code-infrastructure-showcase

## Improving Skill Activation Rates (214 upvotes)

**From "Claude Code skills activate 20% of the time. Here's how I got to 84%"**

**Problem:** Default skill activation is around 20%

**Solution:**

1. **Detailed, Context-Rich Skills**
   - Include specific examples and patterns
   - Provide detailed guides for your framework
   - More context = better activation

2. **Pattern Matching**
   - Skills need clear trigger patterns
   - Use specific terminology that matches your codebase
   - Make triggers unambiguous

3. **Regular Testing & Refinement**
   - Test skill activation regularly
   - Refine based on what triggers successfully
   - Remove or merge underperforming skills

## Skills Best Practices

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

## Skill Structure

**Effective Skill Pattern:**

```markdown
# Skill Name

Brief description (1-2 sentences)

## When to Use
- Trigger condition 1
- Trigger condition 2

## Instructions
Detailed guidance...

## Examples
Concrete examples...

---
*Triggers: keyword1, keyword2, keyword3*
```

## Security Warning (80 upvotes)

**From "Be careful with people spreading Claude Code Skills as malware on Github":**

**Risk:** Skills can execute arbitrary code

**Protection:**
- Review skills before installing
- Use trusted sources only
- Check skill code, not just description
- Be wary of skills from unknown authors

## Skill Resources

- **Registry:** https://claude-plugins.dev/skills (6000+ public skills)
- **Superpowers plugin:** https://github.com/obra/superpowers
- **Prompt Coach skill** - Analyzes prompt quality

## Infrastructure as Code

**From 685 upvote post:**
- Treat your Claude Code setup like infrastructure
- Version control everything (.claude directory)
- Share reusable patterns across projects

**Community Response:**
> "99% of gripes, questions, and issues faced in this subreddit can be answered with this post"

---

*Triggers: skill activation, skill design, skills patterns, prompt injection*
