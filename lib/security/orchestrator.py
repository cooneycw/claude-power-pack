"""Security scan orchestrator.

Runs scanner modules, aggregates results, and applies suppressions.
Provides quick, standard, and deep scan modes.
"""

from __future__ import annotations

from .config import SecurityConfig
from .models import Finding, ScanResult
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

    For /security:deep - includes git history analysis.
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


def _gate_message(finding: Finding) -> str:
    """One gate line for *finding*, with enough to act on it (kyle #838).

    Severity and title alone cannot be triaged: five identical HIGH lines for
    "Hardcoded password in source code" leave a reader unable to tell a real
    one from a known-ignorable one without re-deriving the scan, so a genuine
    finding hides among them. The location was never missing - ``Finding``
    carries ``file_path``/``line_number`` and the scanners populate them - it
    was simply not printed.

    ``raw_match`` is deliberately NOT included. It may be the secret itself,
    which is why the model carries ``mask_secret``, and these messages land in
    shared logs and PR bodies. The location is enough to go and look.
    """
    parts = [f"{finding.severity.icon} {finding.severity.label}: {finding.title}"]
    if finding.location:
        parts.append(f"at {finding.location}")
    return " ".join(parts) + f" [{finding.id}]"


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
            messages.append(f"BLOCKED: {_gate_message(finding)}")
            blocked = True
        elif finding.severity in gate.warn_on:
            messages.append(f"WARNING: {_gate_message(finding)}")

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
