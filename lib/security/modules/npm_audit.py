"""External tool adapter: npm audit.

Checks Node.js dependencies for known vulnerabilities.
Auto-detected: only runs if package.json exists and npm is installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..models import Finding, ScanResult, Severity

# Map npm severity to our severity model
NPM_SEVERITY_MAP = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "moderate": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.LOW,
}


def is_available() -> bool:
    """Check if npm is installed."""
    return shutil.which("npm") is not None


def _is_node_project(project_root: str) -> bool:
    """Check if this is a Node.js project."""
    return (Path(project_root) / "package.json").exists()


def scan(project_root: str) -> ScanResult:
    """Run npm audit on the project."""
    result = ScanResult()

    if not _is_node_project(project_root):
        result.skipped.append("npm audit (not a Node.js project)")
        return result

    if not is_available():
        result.skipped.append("npm not installed")
        return result

    # Check for package-lock.json (required for npm audit)
    if not (Path(project_root) / "package-lock.json").exists():
        result.skipped.append("npm audit (no package-lock.json — run `npm install` first)")
        return result

    try:
        proc = subprocess.run(
            ["npm", "audit", "--json"],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        result.errors.append("npm audit timed out after 60 seconds")
        return result
    except FileNotFoundError:
        result.skipped.append("npm not found")
        return result

    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        result.errors.append("npm audit output was not valid JSON")
        return result

    vulnerabilities = data.get("vulnerabilities", {})
    if not vulnerabilities:
        result.passed.append("No dependency vulnerabilities found (npm audit)")
        return result

    for pkg_name, vuln_info in vulnerabilities.items():
        severity_str = vuln_info.get("severity", "low")
        severity = NPM_SEVERITY_MAP.get(severity_str, Severity.LOW)
        fix_available = vuln_info.get("fixAvailable", False)

        result.findings.append(
            Finding(
                id="NPM_AUDIT_" + pkg_name.upper().replace("-", "_").replace("/", "_"),
                severity=severity,
                title=f"Vulnerable dependency: {pkg_name} ({severity_str})",
                file_path="package.json",
                why=f"Known {severity_str} vulnerability in {pkg_name}. "
                f"Range: {vuln_info.get('range', 'unknown')}",
                fix="Run npm audit fix" if fix_available else "Manual upgrade required",
                command="npm audit fix" if fix_available else None,
                time_estimate="~5 minutes",
                scanner="npm-audit",
            )
        )

    return result
