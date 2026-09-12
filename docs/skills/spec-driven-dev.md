# Spec-Driven Development

*From Claude Code Best Practices - r/ClaudeCode community wisdom*

## How this repository applies it

The community material below argues for writing the specification before the code.
CPP takes the principle and sizes it: every change states its **contract** first, and
a full specification is how that contract is expressed when the work warrants one.
Tier 1 and Tier 2 work carries the same contract in a few sentences in the issue body,
with no spec.md, plan.md, or tasks.md; Tier 3 work gets the full pipeline and the issue
references the spec instead of copying it.

What the contract must make legible either way - the intended outcome, constraints with
their rationale, observable acceptance, a proposed approach marked as revisable, and
assumptions worth checking - is defined once in
[the issue contract](../agents/issue-contract.md). Read that before applying the
templates below, which are the Tier 3 shape.

## Why Spec-Driven Development? (107 upvotes)

**From "Why we shifted to Spec-Driven Development":**

**Problem:** As features multiply, consistency and quality suffer

**Solution:** Spec-Driven Development (SDD)

## The SDD Approach

1. **Agree the Contract First**
   - Before any code, at a size proportional to the work
   - Include edge cases
   - Define success criteria as observable outcomes
   - Keep a proposed design labelled as a proposal, so a better one can replace it

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

## Spec-First → Sandbox → Production

**From 685 upvote post + community:**

1. **Write Spec**
   - Detailed requirements
   - Edge cases
   - Success criteria

2. **Sandbox Testing** (use Sonnet)
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

## Tools

- **GitHub Spec Kit** - MIT licensed spec framework
  - https://github.com/github/spec-kit
  - https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/
- Custom spec frameworks
- Markdown-based specs in repo

## Community Debate

**When SDD works best:**
- Complex, multi-person projects
- Features with many edge cases
- When team alignment is critical

**When SDD may be overkill:**
- Solo developers on small features
- Rapid prototyping phase
- Well-understood changes

## Spec Template

```markdown
# Feature: [Name]

## Summary
One-sentence description

## Requirements
- [ ] Requirement 1
- [ ] Requirement 2

## Edge Cases
- Edge case 1: Expected behavior
- Edge case 2: Expected behavior

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Out of Scope
- Thing we're not doing
```

## Integration with Claude Code

For Tier 1 and Tier 2 work:

1. State the contract in the issue body per
   [the issue contract](../agents/issue-contract.md)
2. Ship it with `/flow:auto <issue>`
3. Verify the implementation against the issue's acceptance examples

For Tier 3 work:

1. Create the spec under `.specify/specs/{feature}/` with `/spec:adopt` and the
   upstream `/speckit-*` skills
2. Reference the spec and its governing sections from each issue, rather than
   copying them
3. Ask Claude to verify implementation against the spec
4. Update the spec with learnings, then graduate its durable facts on delivery
   ([knowledge lifecycle](../agents/knowledge-lifecycle.md))

---

*Triggers: spec driven, specification, SDD, planning, requirements, issue contract*
