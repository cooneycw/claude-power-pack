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

### P3: Contract-First Implementation

No code without an agreed contract. The contract states the intended outcome, the
constraints that bound it and why, and what observable result counts as done.

- Express the contract in the issue body for Tier 1 and Tier 2 work
- Escalate to a full `.specify/` specification when uncertainty or coordination
  warrants it, and for all Tier 3 work; the issue then references that spec
  rather than copying it
- Separate the intended outcome from a proposed approach: the outcome is
  binding, the approach is a revisable hypothesis
- Constraints remain binding without a stated rationale; challenge one with
  evidence and record the decision, never silently reclassify it
- The canonical definition is [the issue contract](../../docs/agents/issue-contract.md)

### P4: Test-Driven Quality

Tests validate the agreed outcome, not just implementations.

- Write tests from the acceptance criteria in the issue contract or its spec
- Tests must pass independently per feature
- Use pytest with descriptive test names
- No merge without passing tests

### P5: Python for Cross-Platform

Use Python for all scripting that needs to work across platforms.

- Bash scripts only for simple, Linux-only utilities
- Python 3.11+ with type hints
- Use uv for dependency management (pyproject.toml)
- Follow existing `lib/` module patterns

### P6: Infrastructure Resilience

After two or more failures from the same root cause, propose systemic hardening - not just symptom fixes.

- Recognize repeated failure patterns as systemic problems
- Propose explicit contracts and validation gates over implicit detection
- Suggest canary validation before fleet-wide rollout
- Prevent classes of failures, not just instances

### P7: Proportional response

Match ceremony to scope. The cost of governance process must not exceed
the cost of the change it governs. Default to the lightest sufficient
process and escalate only when analysis reveals the need.

---

## Development Workflow

### Contract Phase (all tiers)
1. State the intended outcome and why it matters
2. Record material constraints with their rationale
3. Give observable acceptance examples
4. Mark any proposed approach as revisable, and name assumptions worth checking

The issue body carries this for Tier 1 and Tier 2 work. See
[the issue contract](../../docs/agents/issue-contract.md).

### Specification Phase (Tier 3, or when uncertainty warrants it)
1. Author with `/spec:adopt` and the upstream `/speckit-*` skills
2. Define user stories with acceptance criteria
3. De-risk ambiguity and check cross-artifact consistency
4. Create the technical plan, architecture, dependencies, risks, and mitigations
5. Get plan approval

### Task Breakdown
1. Generate tasks from plan
2. Organize by wave/phase
3. Mark dependencies and parallel tasks
4. Create GitHub issues with `scripts/speckit-tasks-to-issues.sh`

### Implementation Phase
1. Create worktree for issue
2. Implement following TDD
3. Submit PR with tests
4. Reference the governing contract in the PR description - the issue, or the
   spec it points to

---

## Governance

### Governance Tiers

- **Tier 1 (Surgical):** 1-3 files, single concern. Branch, ELI5+approval,
  implement+test, PR. No spec. The tier dials down spec ceremony, not the
  approval gate - ELI5 is never auto-approved at any tier (issue #775).
- **Tier 2 (Considered):** 4-10 files, new model/endpoint. Branch, ELI5+
  approval, implement+test, PR.
- **Tier 3 (Architectural):** New subsystem, security boundary, multi-issue.
  Full .specify/ pipeline + ELI5 + implement + PR.

Dialing spec ceremony down does not dial the contract down: work at every tier
states its outcome, constraints, and acceptance. Only where that contract lives
changes. See [the issue contract](../../docs/agents/issue-contract.md).

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

*Last updated: 2026-09-12*
