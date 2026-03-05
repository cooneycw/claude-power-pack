---
description: Multi-model evaluation flow for issues, ideas, and architectural decisions
allowed-tools: mcp__second-opinion__get_multi_model_second_opinion, mcp__second-opinion__list_available_models, mcp__second-opinion__get_code_second_opinion
---

# Evaluate Issue

Orchestrate a four-phase evaluation flow using multi-model consultation and structured reasoning to produce a spec-ready artifact.

ARGUMENTS: $ARGUMENTS

---

## Overview

This command runs a structured evaluation pipeline:

```
Phase 1: Multi-Model Divergence Scan
  -> Human Checkpoint #1
Phase 2: Sequential Reasoning (12-15 steps)
  -> Human Checkpoint #2
Phase 3: Multi-Model Validation
  -> Human Checkpoint #3
Phase 4: Spec Output
```

Each phase builds on the previous. Human checkpoints let the user steer.

Domain-specific prompts are provided by the `evaluate` skill, which embeds prompts for 5 domains: architecture, concept, algorithm, ui-design, workflow.

---

## Step 1: Collect Input

Parse ARGUMENTS for any provided context. Then ask the user using AskUserQuestion for any missing information.

### Required Information

**Question 1: Description**

If not provided in ARGUMENTS, ask:
> "Describe the issue, idea, or decision you want to evaluate."

The user should provide a clear description of what needs evaluation. This can be:
- A feature idea or proposal
- An architectural decision with trade-offs
- A workflow or process design
- A concept that needs structured analysis

**Question 2: Domain Type**

Ask the user to select the domain type:

| Option | Label | Description |
|--------|-------|-------------|
| 1 | `architecture` | System design, infrastructure, API design, data modeling |
| 2 | `concept` | Abstract ideas, workflows, processes, business logic |
| 3 | `algorithm` | Data structures, algorithms, performance optimization |
| 4 | `ui-design` | User interface, UX flows, component design |
| 5 | `workflow` | CI/CD, automation, developer experience, tooling |

**Question 3: Feature Name**

Ask:
> "What should the output feature be named? Use kebab-case (e.g., `user-authentication`, `caching-strategy`)"

This determines the output path: `.specify/specs/{feature-name}/`

**Question 4: Artifacts (Optional)**

Ask:
> "Do you have any supporting artifacts? (code snippets, existing specs, mockup descriptions, constraints)"

Options:
- **Yes** -- User provides artifacts (paste or file paths)
- **No** -- Proceed without artifacts

### Assemble Context Block

Combine all inputs into a structured context block for use in subsequent phases:

```
EVALUATION CONTEXT
==================
Description: {user's description}
Domain: {domain type}
Feature: {feature-name}
Artifacts: {any provided artifacts, or "None"}
```

---

## Step 2: Phase 1 -- Multi-Model Divergence Scan

Call `get_multi_model_second_opinion` with:

| Parameter | Value |
|-----------|-------|
| `code` | The full context block from Step 1 |
| `language` | `markdown` |
| `models` | Select 2-3 available models (prefer diverse providers, e.g., `["gemini-3-pro", "codex"]`) |
| `verbosity` | `in_depth` |
| `context` | Use the Phase 1 prompt from the evaluate skill for the selected domain |
| `issue_description` | `"Multi-model divergence scan for: {description}"` |

### Present Results

Display a synthesis showing:

1. **Areas of Agreement** -- Where all models converge
2. **Areas of Divergence** -- Where models disagree or emphasize differently
3. **Key Tensions** -- The most important trade-offs or decision points identified
4. **Risk Flags** -- Concerns raised by any model

Format as a clear summary, not raw model output. Pull out the interesting disagreements.

---

## Step 3: Human Checkpoint #1

Use AskUserQuestion to present:

> "Phase 1 found these key tensions. Which should Phase 2 focus on?"

**Question: Focus Areas** (multiSelect=true)

Present the top 3-4 tensions/themes identified in Phase 1 as options. Include an "All of the above" option.

Also ask:

> "Any additional constraints or preferences to guide the deep analysis?"

Options:
- **No, proceed as-is** -- Continue with identified tensions
- **Yes** -- User provides additional constraints

---

## Step 4: Phase 2 -- Sequential Reasoning

**If `sequentialthinking` MCP tool is available:**

Run sequential thinking iteratively, targeting 12-15 thoughts. Structure the reasoning chain:

| Thoughts | Focus |
|----------|-------|
| 1-3 | **Problem Space** -- Define boundaries, stakeholders, constraints |
| 4-6 | **Options Analysis** -- Enumerate approaches, map to domain type |
| 7-9 | **Trade-off Evaluation** -- Apply focus areas from Checkpoint #1 |
| 10-12 | **Convergence** -- Synthesize toward recommendation |
| 13+ | **Branch if needed** -- Explore alternatives if convergence is weak |

For each thought, call `sequentialthinking` with:
- `thought`: The reasoning step content
- `thoughtNumber`: Current step
- `totalThoughts`: 12 (adjust with `needsMoreThoughts` if needed)
- `nextThoughtNeeded`: true (until final thought)

Use `isRevision` if an earlier assumption proves wrong. Use `branchFromThought` if a fork in reasoning appears.

**If `sequentialthinking` MCP tool is NOT available:**

Perform the same structured reasoning inline, presenting each step visibly:

```
Reasoning Step 1/12: Problem Space
[content]

Reasoning Step 2/12: Problem Space
[content]

...
```

Use the same structure (problem space -> options -> trade-offs -> convergence -> branch).

### Present Results

After completing the reasoning chain, present:

1. **Reasoning Summary** -- The key insights from each phase
2. **Recommended Approach** -- The convergent recommendation
3. **Confidence Level** -- How strongly the reasoning supports the recommendation
4. **Open Questions** -- Unresolved items that need human judgment

---

## Step 5: Human Checkpoint #2

Use AskUserQuestion:

> "Phase 2 reasoning produced this recommendation. How should we proceed?"

Options:
- **Accept and validate** (Recommended) -- Proceed to Phase 3 multi-model validation
- **Redirect** -- Provide new constraints or change focus, then re-run Phase 2
- **Skip validation** -- Go directly to spec output (Phase 4)

If user provides additional constraints, re-run Phase 2 with the new context appended.

---

## Step 6: Phase 3 -- Multi-Model Validation

Call `get_multi_model_second_opinion` with:

| Parameter | Value |
|-----------|-------|
| `code` | The original context block from Step 1 |
| `language` | `markdown` |
| `models` | Same models as Phase 1 (or user-adjusted) |
| `verbosity` | `detailed` |
| `context` | The Phase 3 validation prompt from the evaluate skill for the selected domain, plus the full Phase 2 reasoning chain summary and recommended approach |
| `issue_description` | `"Validate this recommendation against the original proposal. Identify gaps, risks, and implementation concerns."` |

### Present Results

Display:

1. **Validation Summary** -- Do the models agree with the Phase 2 recommendation?
2. **Gaps Identified** -- What did Phase 2 miss?
3. **Implementation Risks** -- Practical concerns for executing the recommendation
4. **Suggested Refinements** -- Model-suggested improvements

---

## Step 7: Human Checkpoint #3

Use AskUserQuestion:

> "Validation complete. What type of spec output should be generated?"

**Question 1: Output Type**

Options:
- **Full spec** (Recommended) -- Generate spec.md + plan.md + tasks.md
- **Spec only** -- Generate just spec.md (requirements and user stories)
- **Plan only** -- Generate just plan.md (technical approach)
- **Tasks only** -- Generate just tasks.md (actionable items)

**Question 2: Confirm Feature Name**

> "Output will be written to `.specify/specs/{feature-name}/`. Confirm or change?"

Options:
- **Confirm: {feature-name}** -- Use the original name
- **Change** -- User provides a new name

---

## Step 8: Phase 4 -- Spec Output

### Check Prerequisites

```bash
if [ ! -d ".specify" ]; then
    echo "Warning: .specify/ not found. Creating it."
    mkdir -p .specify/specs
fi

if [ -d ".specify/specs/{feature-name}" ]; then
    # Directory exists -- warn user
    echo "Note: .specify/specs/{feature-name}/ already exists. Files will be overwritten."
fi

mkdir -p .specify/specs/{feature-name}
```

### Generate Output Files

Based on the user's selection in Checkpoint #3, generate the appropriate files. Use the `.specify/templates/` templates as the structural base, but fill them with content from the evaluation. Use the spec focus areas from the evaluate skill for the selected domain.

#### spec.md

Fill from the evaluation:
- **Overview**: From Phase 1 synthesis + user description
- **User Stories**: Derived from Phase 2 reasoning (stakeholders -> stories)
- **Acceptance Criteria**: From Phase 3 validation (gaps become criteria)
- **Edge Cases**: From Phase 1 divergence points
- **Requirements**: Consolidated from all phases
- **Status**: `Evaluated`

#### plan.md

Fill from the evaluation:
- **Summary**: Phase 2 recommended approach
- **Technical Context**: Domain-specific choices from Phase 2
- **Architecture**: From Phase 2 options analysis
- **Implementation Phases**: From Phase 2 convergence
- **Risks**: From Phase 3 validation
- **Status**: `Evaluated`

#### tasks.md

Fill from the evaluation:
- **Waves**: Derived from plan.md implementation phases
- **Tasks**: Broken down from each phase
- **Dependencies**: From Phase 2 reasoning chain
- **Checkpoints**: At wave boundaries
- **Status**: `Ready`

### Report Output

```
Phase 4: Spec Output Complete

Created:
  .specify/specs/{feature-name}/
  -- spec.md      <- Requirements from evaluation
  -- plan.md      <- Technical approach
  -- tasks.md     <- Actionable items

Evaluation Summary:
  Models consulted: {count} ({model names})
  Reasoning steps: {N}
  Total cost: ${cost}

Next steps:
  1. Review generated specs in .specify/specs/{feature-name}/
  2. Run /spec:sync {feature-name} to create GitHub issues
  3. Use /flow:start <issue> to begin implementation
```

---

## Domain-Specific Guidance

The domain type influences how each phase focuses its analysis. Refer to the evaluate skill for the full prompt text for each domain.

### architecture
- Phase 1: Focus on scalability, reliability, cost, security trade-offs
- Phase 2: Evaluate component boundaries, data flow, failure modes
- Phase 3: Validate against non-functional requirements
- Spec: Emphasize system diagrams, API contracts, data models

### concept
- Phase 1: Focus on feasibility, user value, competitive landscape
- Phase 2: Evaluate user journeys, edge cases, scope boundaries
- Phase 3: Validate against user needs and business constraints
- Spec: Emphasize user stories, acceptance criteria, success metrics

### algorithm
- Phase 1: Focus on correctness, performance, memory, complexity
- Phase 2: Evaluate algorithmic approaches, data structures, benchmarks
- Phase 3: Validate against performance requirements and edge cases
- Spec: Emphasize complexity analysis, benchmarks, correctness proofs

### ui-design
- Phase 1: Focus on usability, accessibility, consistency, performance
- Phase 2: Evaluate interaction patterns, component hierarchy, state management
- Phase 3: Validate against accessibility standards and UX heuristics
- Spec: Emphasize wireframes, interaction flows, component specs

### workflow
- Phase 1: Focus on reliability, developer experience, maintainability
- Phase 2: Evaluate pipeline stages, failure handling, feedback loops
- Phase 3: Validate against operational requirements
- Spec: Emphasize pipeline diagrams, runbooks, monitoring requirements

---

## Notes

- Uses `language="markdown"` for non-code content in the second-opinion tools (acceptable workaround)
- No separate MCP server required -- works entirely with existing `second-opinion` and optionally `sequential-thinking` tools
- Domain prompts are provided by the evaluate skill (.claude/skills/evaluate.md)
- Each phase takes 30-60 seconds; full evaluation is ~3-5 minutes
- Cost depends on model selection and verbosity; typical run is $0.10-0.30
- If only one model is available, falls back to `get_code_second_opinion` with single-model mode
- The sequential thinking MCP is optional -- if not installed, reasoning is done inline
