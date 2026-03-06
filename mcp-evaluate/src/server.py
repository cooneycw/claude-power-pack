"""
MCP Evaluate Server - Domain-aware multi-model evaluation.

Composite MCP server that orchestrates the second-opinion server to provide
domain-appropriate evaluation across phases: divergence scan, validation,
and spec output generation.

Port: 8083 (default)
Transport: SSE
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from config import Config
from domains import VALID_DOMAINS, get_domain_prompt, get_spec_focus
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

mcp = FastMCP(Config.SERVER_NAME)

# In-memory session store
_sessions: dict[str, dict] = {}


@mcp.custom_route("/", methods=["GET"])
async def root_health_check(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "server": Config.SERVER_NAME,
        "version": Config.SERVER_VERSION,
        "second_opinion_url": Config.SECOND_OPINION_URL,
        "active_sessions": len(_sessions),
    })


async def _call_second_opinion(
    endpoint: str,
    payload: dict,
) -> dict:
    """Call the second-opinion MCP server's HTTP API.

    The second-opinion server exposes tools via MCP over SSE. We call its
    tool endpoints using the MCP client protocol over HTTP.
    """
    url = f"{Config.SECOND_OPINION_URL}/mcp/v1/tools/call"
    async with httpx.AsyncClient(timeout=Config.REQUEST_TIMEOUT) as client:
        response = await client.post(
            url,
            json={"name": endpoint, "arguments": payload},
        )
        response.raise_for_status()
        result = response.json()
        # MCP tool responses have content array
        if "content" in result and isinstance(result["content"], list):
            for item in result["content"]:
                if item.get("type") == "text":
                    import json
                    try:
                        return json.loads(item["text"])
                    except (json.JSONDecodeError, TypeError):
                        return {"raw": item["text"]}
        return result


async def _call_multi_model(
    code: str,
    language: str,
    models: list[str],
    verbosity: str,
    context: str = "",
    issue_description: str = "",
) -> dict:
    """Call get_multi_model_second_opinion on the second-opinion server."""
    return await _call_second_opinion(
        "get_multi_model_second_opinion",
        {
            "code": code,
            "language": language,
            "models": models,
            "verbosity": verbosity,
            "context": context,
            "issue_description": issue_description,
        },
    )


async def _call_list_models() -> dict:
    """Get available models from the second-opinion server."""
    return await _call_second_opinion("list_available_models", {})


def _build_context_block(
    description: str,
    domain: str,
    artifacts: list[str],
) -> str:
    """Build the structured evaluation context block."""
    artifacts_text = "\n".join(f"- {a}" for a in artifacts) if artifacts else "None"
    return (
        f"EVALUATION CONTEXT\n"
        f"==================\n"
        f"Description: {description}\n"
        f"Domain: {domain}\n"
        f"Artifacts:\n{artifacts_text}"
    )


@mcp.tool()
async def evaluate_start(
    description: str,
    domain: str,
    artifacts: Optional[list[str]] = None,
    models: Optional[list[str]] = None,
    context: str = "",
) -> dict:
    """Start a domain-aware multi-model evaluation (Phase 1: Divergence Scan).

    Analyzes an issue, concept, or design decision using multiple LLM models
    with domain-specific prompt framing. Returns areas of agreement, divergence,
    key tensions, and risk flags.

    Args:
        description: The issue, idea, or decision to evaluate.
        domain: Domain type - one of: architecture, concept, algorithm, ui-design, workflow.
        artifacts: Optional supporting materials (code snippets, specs, mockup descriptions).
        models: Model keys to use (default: auto-select 2-3 diverse models).
        context: Additional context or constraints.

    Returns:
        dict with session_id, phase1_analysis, models_used, and cost.
    """
    if domain not in VALID_DOMAINS:
        return {
            "success": False,
            "error": f"Invalid domain '{domain}'. Must be one of: {', '.join(VALID_DOMAINS)}",
        }

    session_id = str(uuid.uuid4())[:8]
    artifacts = artifacts or []

    # Build evaluation context
    context_block = _build_context_block(description, domain, artifacts)
    if context:
        context_block += f"\n\nAdditional Context:\n{context}"

    # Get domain-specific Phase 1 prompt
    domain_prompt = get_domain_prompt(domain, "phase1")

    # Auto-select models if not provided
    if not models:
        try:
            model_info = await _call_list_models()
            available = [
                m["key"]
                for m in model_info.get("available_models", [])
                if m.get("available")
            ]
            # Pick up to 3 diverse models
            models = available[:3] if available else ["gemini-3-pro"]
        except Exception:
            models = ["gemini-3-pro"]

    logger.info(
        f"evaluate_start: session={session_id}, domain={domain}, models={models}"
    )

    # Call multi-model second opinion with domain-aware prompt
    try:
        result = await _call_multi_model(
            code=context_block,
            language="markdown",
            models=models,
            verbosity="in_depth",
            context=domain_prompt,
            issue_description=f"Multi-model divergence scan ({domain}): {description[:200]}",
        )
    except Exception as e:
        logger.error(f"evaluate_start failed: {e}")
        return {
            "success": False,
            "session_id": session_id,
            "error": f"Failed to call second-opinion server: {e}",
        }

    # Store session state for Phase 3
    _sessions[session_id] = {
        "created_at": datetime.now().isoformat(),
        "domain": domain,
        "description": description,
        "context_block": context_block,
        "models": models,
        "phase1_result": result,
        "phase2_reasoning": None,
        "phase3_result": None,
    }

    return {
        "success": True,
        "session_id": session_id,
        "domain": domain,
        "models_used": models,
        "phase1_analysis": result,
        "cost": result.get("total_cost", 0),
    }


@mcp.tool()
async def evaluate_validate(
    session_id: str,
    reasoning_chain: str,
    proposed_approach: str,
) -> dict:
    """Validate a recommendation using multi-model analysis (Phase 3).

    Takes the Phase 2 sequential reasoning output and runs a targeted
    validation against the original proposal using multiple models.
    The reasoning chain provides context so this is NOT a cold repeat
    of Phase 1.

    Args:
        session_id: Session ID from evaluate_start.
        reasoning_chain: The full Phase 2 sequential reasoning output.
        proposed_approach: The synthesized recommendation from Phase 2.

    Returns:
        dict with validation analysis, gaps, risks, and cost.
    """
    session = _sessions.get(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Session '{session_id}' not found. Run evaluate_start first.",
        }

    domain = session["domain"]
    domain_prompt = get_domain_prompt(domain, "phase3")

    # Build validation context that includes Phase 2 reasoning
    validation_context = (
        f"PHASE 2 REASONING CHAIN:\n{reasoning_chain}\n\n"
        f"PROPOSED APPROACH:\n{proposed_approach}\n\n"
        f"VALIDATION INSTRUCTIONS:\n{domain_prompt}"
    )

    logger.info(f"evaluate_validate: session={session_id}, domain={domain}")

    try:
        result = await _call_multi_model(
            code=session["context_block"],
            language="markdown",
            models=session["models"],
            verbosity="detailed",
            context=validation_context,
            issue_description=(
                f"Validate recommendation against original {domain} proposal. "
                f"Identify gaps, risks, and implementation concerns."
            ),
        )
    except Exception as e:
        logger.error(f"evaluate_validate failed: {e}")
        return {
            "success": False,
            "session_id": session_id,
            "error": f"Failed to call second-opinion server: {e}",
        }

    # Update session state
    session["phase2_reasoning"] = reasoning_chain
    session["phase3_result"] = result

    return {
        "success": True,
        "session_id": session_id,
        "domain": domain,
        "validation_analysis": result,
        "cost": result.get("total_cost", 0),
    }


@mcp.tool()
async def evaluate_produce_spec(
    session_id: str,
    evaluation_type: str,
    feature_name: str,
    constitution_path: str = "",
) -> dict:
    """Produce a .specify/ spec artifact from the evaluation (Phase 4).

    Generates spec.md, plan.md, and/or tasks.md filled with content from
    all evaluation phases. Reads the project constitution for alignment.

    Args:
        session_id: Session ID from evaluate_start.
        evaluation_type: Output type - "full" (all 3), "spec", "plan", or "tasks".
        feature_name: Kebab-case feature name for the output directory.
        constitution_path: Optional path to .specify/memory/constitution.md.

    Returns:
        dict with generated file contents (spec_md, plan_md, tasks_md).
    """
    session = _sessions.get(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Session '{session_id}' not found. Run evaluate_start first.",
        }

    if evaluation_type not in ("full", "spec", "plan", "tasks"):
        return {
            "success": False,
            "error": f"Invalid type '{evaluation_type}'. Must be: full, spec, plan, tasks",
        }

    domain = session["domain"]
    spec_focus = get_spec_focus(domain)
    today = datetime.now().strftime("%Y-%m-%d")

    # Read constitution if path provided
    constitution = ""
    if constitution_path:
        try:
            constitution = Path(constitution_path).read_text()
        except Exception:
            logger.warning(f"Could not read constitution at {constitution_path}")

    # Extract content from phases
    phase1 = _format_phase_result(session.get("phase1_result", {}))
    phase2 = session.get("phase2_reasoning", "No Phase 2 reasoning recorded.")
    phase3 = _format_phase_result(session.get("phase3_result", {}))

    result = {
        "success": True,
        "session_id": session_id,
        "feature_name": feature_name,
        "evaluation_type": evaluation_type,
        "files": {},
    }

    if evaluation_type in ("full", "spec"):
        result["files"]["spec.md"] = _generate_spec(
            feature_name, domain, session["description"],
            phase1, phase3, spec_focus, today, constitution,
        )

    if evaluation_type in ("full", "plan"):
        result["files"]["plan.md"] = _generate_plan(
            feature_name, domain, phase2, phase3, spec_focus, today,
        )

    if evaluation_type in ("full", "tasks"):
        result["files"]["tasks.md"] = _generate_tasks(
            feature_name, phase2, today,
        )

    return result


def _format_phase_result(result: dict) -> str:
    """Extract readable text from a multi-model result."""
    if not result:
        return "No analysis available."

    responses = result.get("responses", [])
    if not responses:
        # May be raw text
        return result.get("raw", result.get("analysis", str(result)))

    parts = []
    for resp in responses:
        name = resp.get("display_name", resp.get("model_key", "Unknown"))
        text = resp.get("response", "No response")
        parts.append(f"### {name}\n\n{text}")

    return "\n\n---\n\n".join(parts)


def _generate_spec(
    feature: str, domain: str, description: str,
    phase1: str, phase3: str, focus: str, date: str,
    constitution: str,
) -> str:
    """Generate spec.md from evaluation phases."""
    title = feature.replace("-", " ").title()
    constitution_section = ""
    if constitution:
        constitution_section = (
            f"\n---\n\n## Constitution Alignment\n\n"
            f"Evaluated against project constitution:\n\n"
            f"{constitution[:500]}\n"
        )

    return f"""# Feature Specification: {title}

> **Created:** {date}
> **Status:** Evaluated
> **Domain:** {domain}
> **Focus:** {focus}

---

## Overview

{description}

{constitution_section}
---

## Phase 1: Multi-Model Analysis

{phase1}

---

## Phase 3: Validation Results

{phase3}

---

## Requirements

*Derived from evaluation phases. Review and refine.*

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| R1 | *Extract from Phase 1 agreement areas* | Must | Phase 1 |
| R2 | *Extract from Phase 3 gap analysis* | Should | Phase 3 |

---

## Success Criteria

- [ ] All Phase 3 validation gaps addressed
- [ ] Implementation matches Phase 2 recommended approach
- [ ] Tests cover edge cases from Phase 1 divergence points

---

*Generated by mcp-evaluate v{Config.SERVER_VERSION} on {date}*
"""


def _generate_plan(
    feature: str, domain: str, phase2: str, phase3: str,
    focus: str, date: str,
) -> str:
    """Generate plan.md from evaluation phases."""
    title = feature.replace("-", " ").title()
    return f"""# Implementation Plan: {title}

> **Spec:** [spec.md](./spec.md)
> **Created:** {date}
> **Status:** Evaluated
> **Domain:** {domain}

---

## Summary

*Based on Phase 2 sequential reasoning convergence.*

---

## Phase 2: Reasoning Chain

{phase2}

---

## Validation Findings (Phase 3)

{phase3}

---

## Technical Context

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Domain | {domain} | {focus} |

---

## Risks

*Extracted from Phase 3 validation.*

| Risk | Mitigation |
|------|------------|
| *Extract from Phase 3 risks* | *Extract mitigations* |

---

*Generated by mcp-evaluate v{Config.SERVER_VERSION} on {date}*
"""


def _generate_tasks(feature: str, phase2: str, date: str) -> str:
    """Generate tasks.md from Phase 2 reasoning."""
    title = feature.replace("-", " ").title()
    return f"""# Tasks: {title}

> **Plan:** [plan.md](./plan.md)
> **Created:** {date}
> **Status:** Ready

---

## Reasoning-Derived Tasks

*The following task structure is derived from the Phase 2 sequential reasoning chain.
Review and adjust before syncing to GitHub issues.*

{phase2}

---

## Issue Sync

Use `/spec:sync {feature}` to create GitHub issues from these tasks.

| Wave | Tasks | Issue | Status |
|------|-------|-------|--------|
| Wave 1 | *Review Phase 2* | - | pending |

---

*Generated by mcp-evaluate v{Config.SERVER_VERSION} on {date}*
"""


def main():
    """Main entry point for the MCP server."""
    logger.info(f"Starting {Config.SERVER_NAME} v{Config.SERVER_VERSION}")
    logger.info(f"Transport: SSE on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
    logger.info(f"Second Opinion URL: {Config.SECOND_OPINION_URL}")

    mcp.run(
        transport="sse",
        host=Config.SERVER_HOST,
        port=Config.SERVER_PORT,
    )


if __name__ == "__main__":
    main()
