"""External tool adapter: pip-audit.

Checks Python dependencies for known vulnerabilities (CVEs).
Auto-detected: only runs if pip-audit is installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..models import Finding, ScanResult, Severity


def is_available() -> bool:
    """Check if pip-audit is installed."""
    return shutil.which("pip-audit") is not None


def _is_python_project(project_root: str) -> bool:
    """Check if this is a Python project."""
    root = Path(project_root)
    return any(
        (root / f).exists()
        for f in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile")
    )


def scan(project_root: str) -> ScanResult:
    """Run pip-audit on the project."""
    result = ScanResult()

    if not _is_python_project(project_root):
        result.skipped.append("pip-audit (not a Python project)")
        return result

    if not is_available():
        result.skipped.append("pip-audit not installed (run `uv pip install pip-audit` for Python dependency CVE scanning)")
        return result

    cmd = ["pip-audit", "--format", "json", "--progress-spinner", "off"]

    # Use requirements file if available
    root = Path(project_root)
    req_file = root / "requirements.txt"
    if req_file.exists():
        cmd.extend(["--requirement", str(req_file)])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        result.errors.append("pip-audit timed out after 120 seconds")
        return result
    except FileNotFoundError:
        result.skipped.append("pip-audit not found")
        return result

    # Parse JSON output
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        if proc.returncode != 0:
            result.errors.append(f"pip-audit failed: {proc.stderr[:200]}")
        return result

    vulns = data.get("dependencies", [])
    vuln_count = 0

    for dep in vulns:
        for vuln in dep.get("vulns", []):
            vuln_count += 1
            vuln_id = vuln.get("id", "UNKNOWN")
            fix_version = vuln.get("fix_versions", [])
            fix_str = f"Upgrade to {', '.join(fix_version)}" if fix_version else "No fix available yet"

            result.findings.append(
                Finding(
                    id="PIP_AUDIT_" + vuln_id.replace("-", "_"),
                    severity=Severity.HIGH,
                    title=f"Vulnerable dependency: {dep['name']} ({vuln_id})",
                    file_path="requirements.txt" if req_file.exists() else "pyproject.toml",
                    why=f"{vuln.get('description', 'Known vulnerability in this package version.')}",
                    fix=fix_str,
                    command=f"uv pip install --upgrade {dep['name']}" if fix_version else None,
                    time_estimate="~5 minutes",
                    scanner="pip-audit",
                )
            )

    if not vuln_count:
        result.passed.append("No dependency vulnerabilities found (pip-audit)")

    return result
