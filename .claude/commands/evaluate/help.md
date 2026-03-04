---
description: Overview of evaluate commands
---

# Evaluate Commands

Multi-model evaluation flow for structured decision-making and spec generation.

## Commands

| Command | Purpose |
|---------|---------|
| `/evaluate:issue` | Full 4-phase evaluation: divergence scan, reasoning, validation, spec output |
| `/evaluate:help` | This help page |

## How It Works

The evaluate flow uses multiple LLM models to analyze an issue or idea from different perspectives, then synthesizes the analysis into spec-ready artifacts.

```
Input (description + domain)
  ↓
Phase 1: Multi-Model Divergence Scan
  → Models analyze independently, surfaces disagreements
  → Human Checkpoint: select focus areas
  ↓
Phase 2: Sequential Reasoning (12-15 steps)
  → Structured problem → options → trade-offs → convergence
  → Human Checkpoint: accept, redirect, or skip
  ↓
Phase 3: Multi-Model Validation
  → Models validate the recommendation against original proposal
  → Human Checkpoint: choose output type
  ↓
Phase 4: Spec Output
  → Generates .specify/specs/{feature}/ (spec.md, plan.md, tasks.md)
```

## Domain Types

| Domain | Best For |
|--------|----------|
| `architecture` | System design, APIs, infrastructure, data models |
| `concept` | Ideas, workflows, business logic, feature proposals |
| `algorithm` | Performance, data structures, optimization |
| `ui-design` | UX flows, components, accessibility |
| `workflow` | CI/CD, automation, tooling, DX |

## Prerequisites

- **Required:** MCP Second Opinion server (provides multi-model consultation)
- **Optional:** Sequential Thinking MCP (enhances Phase 2 reasoning; falls back to inline reasoning if not installed)

## Quick Example

```bash
# Evaluate an architectural decision
/evaluate:issue "Should we use event sourcing or CRUD for the order system?"

# Evaluate a feature concept
/evaluate:issue "Add real-time collaboration to the document editor"

# No arguments — interactive prompts guide you
/evaluate:issue
```

## Output

Generates spec artifacts in `.specify/specs/{feature-name}/`:

```
.specify/specs/{feature-name}/
├── spec.md      ← Requirements, user stories, acceptance criteria
├── plan.md      ← Technical approach, architecture, risks
└── tasks.md     ← Actionable items organized in waves
```

Use `/spec:sync {feature-name}` to create GitHub issues from the generated tasks.

## Cost

Typical evaluation costs $0.10-0.30 depending on model selection and depth. Phase 1 and 3 use multi-model calls; Phase 2 uses sequential reasoning (no external LLM cost if using Sequential Thinking MCP).

## Related Commands

- `/second-opinion:start` — Quick single-file code review
- `/second-opinion:models` — Interactive model selection for reviews
- `/spec:create` — Create blank spec templates (no evaluation)
- `/spec:sync` — Sync generated tasks to GitHub issues
