"""Domain-specific evaluation prompts and criteria."""

from typing import Optional

DOMAIN_PROMPTS: dict[str, dict[str, str]] = {
    "architecture": {
        "phase1": (
            "Evaluate this architecture proposal. Focus on:\n"
            "- Scalability: Can this handle 10x/100x growth?\n"
            "- Reliability: What are the failure modes and recovery paths?\n"
            "- Security: What attack surfaces exist?\n"
            "- Cost: What are the operational cost implications?\n"
            "- Maintainability: How complex is the operational burden?\n\n"
            "Identify where reasonable architects would disagree on trade-offs."
        ),
        "phase3": (
            "Validate this architecture recommendation against the original proposal.\n"
            "Check for:\n"
            "- Missing non-functional requirements\n"
            "- Unaddressed failure modes\n"
            "- Scalability bottlenecks\n"
            "- Security gaps\n"
            "- Operational complexity concerns"
        ),
        "spec_focus": "system diagrams, API contracts, data models, deployment topology",
    },
    "concept": {
        "phase1": (
            "Evaluate this concept/feature proposal. Focus on:\n"
            "- Feasibility: Is this technically and organizationally achievable?\n"
            "- User Value: Does this solve a real user problem?\n"
            "- Scope: Are the boundaries clear and reasonable?\n"
            "- Competitive Landscape: How does this compare to alternatives?\n"
            "- Risk: What could go wrong?\n\n"
            "Identify where reasonable stakeholders would disagree."
        ),
        "phase3": (
            "Validate this recommendation against the original concept.\n"
            "Check for:\n"
            "- Unaddressed user needs\n"
            "- Scope creep risks\n"
            "- Missing edge cases in user journeys\n"
            "- Business constraint violations\n"
            "- Success metric gaps"
        ),
        "spec_focus": "user stories, acceptance criteria, success metrics, scope boundaries",
    },
    "algorithm": {
        "phase1": (
            "Evaluate this algorithmic approach. Focus on:\n"
            "- Correctness: Does this produce correct results for all inputs?\n"
            "- Performance: What is the time/space complexity?\n"
            "- Edge Cases: What inputs could break it?\n"
            "- Alternatives: What other algorithms solve this problem?\n"
            "- Trade-offs: Memory vs. speed, simplicity vs. optimality\n\n"
            "Identify where the complexity analysis is nuanced or debatable."
        ),
        "phase3": (
            "Validate this algorithmic recommendation.\n"
            "Check for:\n"
            "- Correctness proof gaps\n"
            "- Performance regressions under edge inputs\n"
            "- Memory pressure scenarios\n"
            "- Numerical stability issues\n"
            "- Parallelization opportunities missed"
        ),
        "spec_focus": "complexity analysis, benchmarks, correctness proofs, test vectors",
    },
    "ui-design": {
        "phase1": (
            "Evaluate this UI/UX design proposal. Focus on:\n"
            "- Usability: Is the interaction model intuitive?\n"
            "- Accessibility: Does this meet WCAG standards?\n"
            "- Consistency: Does this fit the existing design system?\n"
            "- Performance: What are the rendering/interaction costs?\n"
            "- Responsiveness: How does this adapt across viewports?\n\n"
            "Identify where design decisions involve subjective trade-offs."
        ),
        "phase3": (
            "Validate this UI design recommendation.\n"
            "Check for:\n"
            "- Accessibility violations (WCAG 2.1 AA)\n"
            "- Inconsistencies with design system\n"
            "- Missing interaction states (loading, error, empty)\n"
            "- Mobile/responsive gaps\n"
            "- Performance impact of proposed components"
        ),
        "spec_focus": "wireframes, interaction flows, component specs, accessibility notes",
    },
    "workflow": {
        "phase1": (
            "Evaluate this workflow/automation proposal. Focus on:\n"
            "- Reliability: What happens when steps fail?\n"
            "- Developer Experience: Is this intuitive to use and debug?\n"
            "- Maintainability: How hard is this to modify over time?\n"
            "- Observability: Can you tell what's happening and diagnose issues?\n"
            "- Integration: How does this fit with existing tools?\n\n"
            "Identify where workflow design trade-offs are most contentious."
        ),
        "phase3": (
            "Validate this workflow recommendation.\n"
            "Check for:\n"
            "- Unhandled failure scenarios\n"
            "- Missing rollback mechanisms\n"
            "- Monitoring and alerting gaps\n"
            "- Documentation debt\n"
            "- Operational runbook completeness"
        ),
        "spec_focus": "pipeline diagrams, runbooks, monitoring requirements, SLOs",
    },
}

VALID_DOMAINS = list(DOMAIN_PROMPTS.keys())


def get_domain_prompt(domain: str, phase: str) -> Optional[str]:
    """Get the domain-specific prompt for a given phase."""
    domain_config = DOMAIN_PROMPTS.get(domain)
    if not domain_config:
        return None
    return domain_config.get(phase)


def get_spec_focus(domain: str) -> str:
    """Get the spec focus areas for a domain."""
    domain_config = DOMAIN_PROMPTS.get(domain, {})
    return domain_config.get("spec_focus", "requirements, user stories, acceptance criteria")
