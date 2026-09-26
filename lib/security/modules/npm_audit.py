"""External tool adapter: npm audit.

Checks Node.js dependencies for known vulnerabilities.

A project with no package.json, or no package-lock.json, is skipped as not
auditable. A Node project whose audit could not run - npm missing, a failed or
unparseable audit - is UNKNOWN in `result.errors`, never a skip or a pass (issue #1264, the
shape #1044 fixed in pip_audit).
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
        result.errors.append(
            "UNKNOWN: npm is not installed, so package.json dependencies were not audited"
        )
        return result

    # Check for package-lock.json (required for npm audit)
    if not (Path(project_root) / "package-lock.json").exists():
        result.skipped.append("npm audit (no package-lock.json - run `npm install` first)")
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
        result.errors.append("UNKNOWN: npm audit timed out after 60 seconds")
        return result
    except FileNotFoundError:
        result.errors.append("UNKNOWN: npm binary disappeared before the audit ran")
        return result

    # An empty stdout used to parse as `{}` and fall through to "no
    # vulnerabilities found" - a crashed audit reported as a clean one.
    stderr_lines = proc.stderr.rstrip().splitlines()
    detail = f"; stderr: {stderr_lines[-1]}" if stderr_lines else ""
    if not proc.stdout.strip():
        result.errors.append(
            f"UNKNOWN: npm audit produced no report (exit {proc.returncode}{detail})"
        )
        return result
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        result.errors.append(
            f"UNKNOWN: npm audit output was not valid JSON (exit {proc.returncode}{detail})"
        )
        return result
    # The SHAPE is checked, not just the key (counter-model review): a null or
    # list `vulnerabilities` read as empty passed as clean, and a non-empty list
    # raised AttributeError below.
    # npm audit exits 0 clean and 1 on findings; any other exit, or a signal,
    # is a failure even when it printed report-shaped JSON first (counter-model
    # review, pass 2).
    if proc.returncode not in (0, 1):
        result.errors.append(
            f"UNKNOWN: npm audit exited {proc.returncode}, so its report is not a verdict{detail}"
        )
        return result

    vulnerabilities = data.get("vulnerabilities") if isinstance(data, dict) else None
    if (
        not isinstance(data, dict)
        or "error" in data
        or not isinstance(vulnerabilities, dict)
        or not all(isinstance(info, dict) for info in vulnerabilities.values())
    ):
        result.errors.append(
            f"UNKNOWN: npm audit did not return a vulnerability report (exit {proc.returncode})"
        )
        return result

    if not vulnerabilities:
        if proc.returncode == 1:
            result.errors.append(
                "UNKNOWN: npm audit exited 1 (findings) but reported no vulnerabilities"
            )
            return result
        # Say HOW MANY were examined: "nothing found" and "nothing to look at"
        # otherwise print the same line (counter-model review, pass 2).
        metadata = data.get("metadata")
        dependencies = metadata.get("dependencies") if isinstance(metadata, dict) else None
        total = dependencies.get("total") if isinstance(dependencies, dict) else None
        if not isinstance(total, int) or isinstance(total, bool):
            examined = "dependency count not reported"
        elif total == 0:
            examined = "0 dependencies examined - nothing was audited"
        else:
            examined = f"{total} dependencies examined"
        result.passed.append(f"No dependency vulnerabilities found (npm audit; {examined})")
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
