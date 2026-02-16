"""Security scanning for Claude Code projects.

Provides novice-friendly vulnerability detection with:
- Native scanners: gitignore, permissions, secrets, env files, debug flags
- External tool adapters: gitleaks, pip-audit, npm audit
- Configurable suppression via .claude/security.yml
- /flow integration as quality gates

Quick Start:
    from lib.security import scan_quick, scan_full, scan_deep

    # Fast native-only scan
    result = scan_quick("/path/to/project")
    print(result.summary_line())

    # Full scan with external tools
    result = scan_full("/path/to/project")

    # Check flow gate
    from lib.security import check_gate
    passed, messages = check_gate(result, "flow_finish")
"""

from .config import SecurityConfig
from .models import Finding, ScanResult, Severity, Suppression
from .orchestrator import check_gate, scan_deep, scan_full, scan_quick

__all__ = [
    # Models
    "Finding",
    "ScanResult",
    "Severity",
    "Suppression",
    # Config
    "SecurityConfig",
    # Orchestrator
    "scan_quick",
    "scan_full",
    "scan_deep",
    "check_gate",
]
