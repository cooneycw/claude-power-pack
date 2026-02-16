"""Novice-friendly output formatter.

Provides detailed explanations with Why/Fix/Command for each finding,
designed for developers who may not have security expertise.
"""

from __future__ import annotations

from ..models import ScanResult, Severity

# ANSI color codes
RED = "\033[0;31m"
YELLOW = "\033[0;33m"
ORANGE = "\033[0;33m"  # Terminal orange = yellow
GREEN = "\033[0;32m"
DIM = "\033[0;90m"
BOLD = "\033[1m"
NC = "\033[0m"

SEVERITY_COLOR = {
    Severity.CRITICAL: RED,
    Severity.HIGH: YELLOW,
    Severity.MEDIUM: ORANGE,
    Severity.LOW: DIM,
}


def format_results(result: ScanResult, verbose: bool = False) -> str:
    """Format scan results for novice-friendly display."""
    lines = []
    lines.append(f"{BOLD}## Security Scan Results{NC}")
    lines.append("")

    # Findings sorted by severity (highest first)
    sorted_findings = sorted(result.findings, key=lambda f: f.severity, reverse=True)

    for finding in sorted_findings:
        color = SEVERITY_COLOR.get(finding.severity, NC)
        lines.append(
            f"{finding.severity.icon} {color}{BOLD}{finding.severity.label}: "
            f"{finding.title}{NC}"
        )
        if finding.location:
            lines.append(f"   File: {finding.location}")
        if finding.why:
            # Wrap why text with indentation
            for i, why_line in enumerate(finding.why.split("\n")):
                prefix = "   Why:  " if i == 0 else "         "
                lines.append(f"{prefix}{why_line}")
        if finding.fix:
            lines.append(f"   Fix:  {finding.fix}")
        if finding.command:
            lines.append(f"   Cmd:  {DIM}{finding.command}{NC}")
        if finding.time_estimate:
            lines.append(f"   Time: {finding.time_estimate}")
        if finding.raw_match and verbose:
            lines.append(f"   Match: {DIM}{finding.raw_match}{NC}")
        lines.append("")

    # Passed checks
    for passed in result.passed:
        lines.append(f"\U0001f7e2 PASS: {passed}")

    # Skipped checks
    for skipped in result.skipped:
        lines.append(f"\u26aa SKIP: {skipped}")

    # Errors
    for error in result.errors:
        lines.append(f"{RED}ERROR: {error}{NC}")

    lines.append("")
    lines.append(
        f"{BOLD}Summary: {result.summary_line()}{NC}"
    )

    if result.has_blockers:
        lines.append(
            f"{RED}Fix the critical issues before creating a PR.{NC}"
        )
    elif result.has_warnings:
        lines.append(
            f"{YELLOW}Consider fixing high-severity issues before deploying.{NC}"
        )
    else:
        lines.append(f"{GREEN}All clear!{NC}")

    return "\n".join(lines)
