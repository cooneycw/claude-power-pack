"""Security scan orchestrator.

Runs scanner modules, aggregates results, and applies suppressions.
Provides quick, standard, and deep scan modes.
"""

from __future__ import annotations

from pathlib import Path

from .config import SecurityConfig
from .models import ScanResult
from .modules import debug_flags, env_files, gitignore, gitleaks, npm_audit, permissions, pip_audit, secrets


def scan_quick(project_root: str, config: SecurityConfig | None = None) -> ScanResult:
    """Quick scan: native scanners only, working tree only.

    Fast, zero-dependency scan suitable for /flow:finish gate.
    """
    if config is None:
        config = SecurityConfig.load(project_root)

    result = ScanResult()

    # Run native modules
    result.merge(gitignore.scan(project_root))
    result.merge(permissions.scan(project_root))
    result.merge(secrets.scan(project_root))
    result.merge(env_files.scan(project_root))
    result.merge(debug_flags.scan(project_root))

    # Apply suppressions
    _apply_suppressions(result, config)

    return result


def scan_full(project_root: str, config: SecurityConfig | None = None) -> ScanResult:
    """Full scan: native + available external tools, working tree only.

    Default mode for /security:scan.
    """
    if config is None:
        config = SecurityConfig.load(project_root)

    # Start with quick scan
    result = scan_quick(project_root, config)

    # Add external tool scans (working tree only)
    result.merge(gitleaks.scan(project_root, include_history=False))
    result.merge(pip_audit.scan(project_root))
    result.merge(npm_audit.scan(project_root))

    # Re-apply suppressions (covers external findings)
    _apply_suppressions(result, config)

    return result


def scan_deep(project_root: str, config: SecurityConfig | None = None) -> ScanResult:
    """Deep scan: everything + git history scanning.

    For /security:deep — includes git history analysis.
    """
    if config is None:
        config = SecurityConfig.load(project_root)

    result = ScanResult()

    # Native modules
    result.merge(gitignore.scan(project_root))
    result.merge(permissions.scan(project_root))
    result.merge(secrets.scan(project_root))
    result.merge(env_files.scan(project_root))
    result.merge(debug_flags.scan(project_root))

    # External tools WITH history
    result.merge(gitleaks.scan(project_root, include_history=True))
    result.merge(pip_audit.scan(project_root))
    result.merge(npm_audit.scan(project_root))

    # Apply suppressions
    _apply_suppressions(result, config)

    return result


def check_gate(result: ScanResult, gate_name: str, config: SecurityConfig | None = None) -> tuple[bool, list[str]]:
    """Check if scan results pass a flow gate.

    Args:
        result: Scan results to evaluate.
        gate_name: Gate to check ("flow_finish" or "flow_deploy").
        config: Security configuration (loads default if None).

    Returns:
        Tuple of (passed, messages).
        passed: True if the gate allows proceeding.
        messages: Warning or error messages to display.
    """
    if config is None:
        config = SecurityConfig._defaults()

    gate = config.gates.get(gate_name)
    if gate is None:
        return True, []

    messages = []
    blocked = False

    for finding in result.findings:
        if finding.severity in gate.block_on:
            messages.append(
                f"BLOCKED: {finding.severity.icon} {finding.severity.label}: {finding.title}"
            )
            blocked = True
        elif finding.severity in gate.warn_on:
            messages.append(
                f"WARNING: {finding.severity.icon} {finding.severity.label}: {finding.title}"
            )

    return not blocked, messages


def _apply_suppressions(result: ScanResult, config: SecurityConfig) -> None:
    """Remove suppressed findings from results."""
    if not config.suppressions:
        return

    original = result.findings[:]
    result.findings = [
        f
        for f in original
        if not any(s.matches(f) for s in config.suppressions)
    ]

    suppressed_count = len(original) - len(result.findings)
    if suppressed_count:
        result.passed.append(f"{suppressed_count} finding(s) suppressed by configuration")
