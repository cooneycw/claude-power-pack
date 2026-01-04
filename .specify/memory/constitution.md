# Project Constitution

> Governing principles and development guidelines for this project.
> All specifications, plans, and implementations must align with these principles.

---

## Core Principles

### P1: Context Efficiency First

All tools, documentation, and workflows must optimize for context window efficiency.

- Use progressive disclosure (metadata → instructions → assets)
- Keep tool descriptions under 200 characters
- Fragment large documents into topic-focused modules
- Lazy-load content only when needed

### P2: Issue-Driven Development

Every implementation starts with a GitHub issue and follows IDD workflow.

- Issues organized as: Epic → Wave → Micro-Issue
- Use git worktrees for parallel development
- Branch naming: `issue-{N}-{description}`
- Commits reference issues: `type(scope): Description (Closes #N)`

### P3: Spec-First Implementation

No code without specification. Specifications become the source of truth.

- Write spec.md before any implementation
- Create plan.md after spec review
- Generate tasks.md from plan
- Sync tasks to GitHub issues before coding

### P4: Test-Driven Quality

Tests validate specifications, not just implementations.

- Write tests from acceptance criteria in spec
- Tests must pass independently per feature
- Use pytest with descriptive test names
- No merge without passing tests

### P5: Python for Cross-Platform

Use Python for all scripting that needs to work across platforms.

- Bash scripts only for simple, Linux-only utilities
- Python 3.11+ with type hints
- Use uv for dependency management (pyproject.toml)
- Follow existing `lib/` module patterns

---

## Development Workflow

### Specification Phase
1. Create feature spec using `/spec:create`
2. Define user stories with acceptance criteria
3. Review spec for completeness
4. Clarify any ambiguities

### Planning Phase
1. Create technical plan from spec
2. Define architecture and dependencies
3. Identify risks and mitigations
4. Get plan approval

### Task Breakdown
1. Generate tasks from plan
2. Organize by wave/phase
3. Mark dependencies and parallel tasks
4. Sync to GitHub issues with `/spec:sync`

### Implementation Phase
1. Create worktree for issue
2. Implement following TDD
3. Submit PR with tests
4. Reference spec in PR description

---

## Governance

### Compliance
- All PRs must verify alignment with constitution
- Complexity must be justified with rationale
- Violations require explicit documentation

### Amendments
- Constitution changes require discussion
- Document the change and rationale
- Update all affected specifications

---

## Attribution

This specification workflow is based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License).

Adapted for Claude Code workflows with Issue-Driven Development integration.

---

*Last updated: 2025-12-24*
