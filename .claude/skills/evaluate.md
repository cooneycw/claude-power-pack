---
description: "Domain-aware evaluation prompts for multi-model analysis. Provides structured prompts for Phase 1 (divergence scan) and Phase 3 (validation) across 5 domain types."
globs: .claude/commands/evaluate/**
---

# Evaluation Domain Prompts

When the `/evaluate:issue` command is triggered, use these domain-specific prompts to frame the multi-model consultation calls to the second-opinion MCP server directly.

## Domain Types

Valid domains: `architecture`, `concept`, `algorithm`, `ui-design`, `workflow`

## Phase 1 Prompts (Divergence Scan)

### architecture
Evaluate this architecture proposal. Focus on:
- Scalability: Can this handle 10x/100x growth?
- Reliability: What are the failure modes and recovery paths?
- Security: What attack surfaces exist?
- Cost: What are the operational cost implications?
- Maintainability: How complex is the operational burden?

Identify where reasonable architects would disagree on trade-offs.

### concept
Evaluate this concept/feature proposal. Focus on:
- Feasibility: Is this technically and organizationally achievable?
- User Value: Does this solve a real user problem?
- Scope: Are the boundaries clear and reasonable?
- Competitive Landscape: How does this compare to alternatives?
- Risk: What could go wrong?

Identify where reasonable stakeholders would disagree.

### algorithm
Evaluate this algorithmic approach. Focus on:
- Correctness: Does this produce correct results for all inputs?
- Performance: What is the time/space complexity?
- Edge Cases: What inputs could break it?
- Alternatives: What other algorithms solve this problem?
- Trade-offs: Memory vs. speed, simplicity vs. optimality

Identify where the complexity analysis is nuanced or debatable.

### ui-design
Evaluate this UI/UX design proposal. Focus on:
- Usability: Is the interaction model intuitive?
- Accessibility: Does this meet WCAG standards?
- Consistency: Does this fit the existing design system?
- Performance: What are the rendering/interaction costs?
- Responsiveness: How does this adapt across viewports?

Identify where design decisions involve subjective trade-offs.

### workflow
Evaluate this workflow/automation proposal. Focus on:
- Reliability: What happens when steps fail?
- Developer Experience: Is this intuitive to use and debug?
- Maintainability: How hard is this to modify over time?
- Observability: Can you tell what's happening and diagnose issues?
- Integration: How does this fit with existing tools?

Identify where workflow design trade-offs are most contentious.

## Phase 3 Prompts (Validation)

### architecture
Validate this architecture recommendation against the original proposal. Check for:
- Missing non-functional requirements
- Unaddressed failure modes
- Scalability bottlenecks
- Security gaps
- Operational complexity concerns

### concept
Validate this recommendation against the original concept. Check for:
- Unaddressed user needs
- Scope creep risks
- Missing edge cases in user journeys
- Business constraint violations
- Success metric gaps

### algorithm
Validate this algorithmic recommendation. Check for:
- Correctness proof gaps
- Performance regressions under edge inputs
- Memory pressure scenarios
- Numerical stability issues
- Parallelization opportunities missed

### ui-design
Validate this UI design recommendation. Check for:
- Accessibility violations (WCAG 2.1 AA)
- Inconsistencies with design system
- Missing interaction states (loading, error, empty)
- Mobile/responsive gaps
- Performance impact of proposed components

### workflow
Validate this workflow recommendation. Check for:
- Unhandled failure scenarios
- Missing rollback mechanisms
- Monitoring and alerting gaps
- Documentation debt
- Operational runbook completeness

## Spec Focus Areas (by domain)

| Domain | Focus |
|--------|-------|
| architecture | system diagrams, API contracts, data models, deployment topology |
| concept | user stories, acceptance criteria, success metrics, scope boundaries |
| algorithm | complexity analysis, benchmarks, correctness proofs, test vectors |
| ui-design | wireframes, interaction flows, component specs, accessibility notes |
| workflow | pipeline diagrams, runbooks, monitoring requirements, SLOs |
