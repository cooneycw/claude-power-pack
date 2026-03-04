# MCP Evaluate Server

Domain-aware multi-model evaluation MCP server. Orchestrates the second-opinion server to provide structured evaluation across phases with domain-specific prompt framing.

## Architecture

```
Claude Code → mcp-evaluate (port 8083) → mcp-second-opinion (port 8080) → Gemini/OpenAI/Anthropic
```

This server does NOT call LLM APIs directly. It composes the existing second-opinion server with domain-aware prompting and session state management.

## Tools (3)

### evaluate_start

Start Phase 1: Multi-model divergence scan with domain-appropriate prompting.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `description` | string | yes | The issue, idea, or decision to evaluate |
| `domain` | string | yes | `architecture`, `concept`, `algorithm`, `ui-design`, `workflow` |
| `artifacts` | list[str] | no | Supporting materials |
| `models` | list[str] | no | Model keys (auto-selects if not provided) |
| `context` | string | no | Additional constraints |

Returns: `session_id`, Phase 1 multi-model analysis, models used, cost.

### evaluate_validate

Phase 3: Validate the Phase 2 recommendation using targeted multi-model analysis.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | From evaluate_start |
| `reasoning_chain` | string | yes | Phase 2 sequential reasoning output |
| `proposed_approach` | string | yes | Synthesized recommendation |

Returns: Validation analysis, gaps, risks, cost.

### evaluate_produce_spec

Phase 4: Generate `.specify/` artifacts from all evaluation phases.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | From evaluate_start |
| `evaluation_type` | string | yes | `full`, `spec`, `plan`, or `tasks` |
| `feature_name` | string | yes | Kebab-case feature name |
| `constitution_path` | string | no | Path to constitution.md |

Returns: Generated file contents (spec.md, plan.md, tasks.md).

## Prerequisites

- **MCP Second Opinion server** must be running on port 8080
- Python 3.11+
- uv

## Setup

```bash
# Start server
./start-server.sh

# Or with uv directly
uv run python src/server.py
```

### Add to Claude Code

```bash
claude mcp add mcp-evaluate --transport sse --url http://127.0.0.1:8083/sse
```

### Systemd (optional)

```bash
cp deploy/mcp-evaluate.service ~/.config/systemd/user/
systemctl --user enable --now mcp-evaluate
journalctl --user -u mcp-evaluate -f
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_SERVER_HOST` | `127.0.0.1` | Server bind address |
| `MCP_SERVER_PORT` | `8083` | Server port |
| `SECOND_OPINION_URL` | `http://127.0.0.1:8080` | Second opinion server URL |
| `REQUEST_TIMEOUT` | `300` | Timeout for second-opinion calls (seconds) |

## Domain Types

| Domain | Phase 1 Focus | Spec Emphasis |
|--------|--------------|---------------|
| `architecture` | Scalability, reliability, security, cost | API contracts, data models |
| `concept` | Feasibility, user value, scope, risk | User stories, success metrics |
| `algorithm` | Correctness, complexity, edge cases | Benchmarks, test vectors |
| `ui-design` | Usability, accessibility, consistency | Interaction flows, components |
| `workflow` | Reliability, DX, observability | Runbooks, SLOs |
