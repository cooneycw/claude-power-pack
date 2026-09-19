"""External tool adapter: pip-audit.

Checks Python dependencies for known vulnerabilities (CVEs).
Auto-detected: only runs if pip-audit is installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
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


def _export_uv_requirements(project_root: str) -> tuple[Path | None, str | None]:
    """Export uv's locked dependency population to a temporary requirements file."""
    if shutil.which("uv") is None:
        return None, "UNKNOWN: uv.lock could not be exported because `uv` is not installed"

    cmd = [
        "uv",
        "export",
        "--format",
        "requirements-txt",
        "--no-hashes",
        "--all-extras",
        "--all-groups",
        "--frozen",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return (
            None,
            "UNKNOWN: uv.lock could not be exported because `uv export` timed out after 60 seconds",
        )
    except FileNotFoundError:
        return None, "UNKNOWN: uv.lock could not be exported because the `uv` binary disappeared"

    if proc.returncode != 0:
        stderr_lines = proc.stderr.rstrip().splitlines()
        detail = f": {stderr_lines[-1]}" if stderr_lines else ""
        return None, f"UNKNOWN: uv.lock could not be exported (`uv export` exit {proc.returncode}){detail}"

    if not proc.stdout.strip():
        return None, "UNKNOWN: uv export produced an empty requirements file for uv.lock"

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix="cpp-pip-audit-",
            suffix=".txt",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(proc.stdout)
    except OSError as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        return None, f"UNKNOWN: uv.lock export could not be written to a temporary file: {exc}"

    return temporary_path, None


def scan(project_root: str) -> ScanResult:
    """Run pip-audit on the project."""
    result = ScanResult()

    if not _is_python_project(project_root):
        result.skipped.append("pip-audit (not a Python project)")
        return result

    root = Path(project_root)
    req_file = root / "requirements.txt"
    uv_lock = root / "uv.lock"
    temporary_requirement: Path | None = None

    if req_file.exists():
        population_source = "requirements.txt"
        requirement_path = req_file
        finding_file_path = "requirements.txt"
    elif uv_lock.exists():
        temporary_requirement, export_error = _export_uv_requirements(project_root)
        if export_error is not None:
            result.errors.append(export_error)
            return result
        assert temporary_requirement is not None
        population_source = "uv.lock (via `uv export`)"
        requirement_path = temporary_requirement
        finding_file_path = "uv.lock"
    else:
        result.errors.append(
            "UNKNOWN: no requirements.txt or uv.lock dependency population was found; "
            "refusing to fall back to auditing the ambient Python environment"
        )
        return result

    if not is_available():
        if temporary_requirement is not None:
            temporary_requirement.unlink(missing_ok=True)
        result.errors.append(
            f"UNKNOWN: pip-audit is not installed, so {population_source} was not audited "
            "(run `uv pip install pip-audit`)"
        )
        return result

    cmd = [
        "pip-audit",
        "--format",
        "json",
        "--progress-spinner",
        "off",
        "--requirement",
        str(requirement_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        result.errors.append("UNKNOWN: pip-audit timed out after 120 seconds")
        return result
    except FileNotFoundError:
        result.errors.append(
            "UNKNOWN: pip-audit binary disappeared before the dependency population was audited"
        )
        return result
    finally:
        if temporary_requirement is not None:
            temporary_requirement.unlink(missing_ok=True)

    # Parse JSON output
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        stderr_lines = proc.stderr.rstrip().splitlines()
        detail = f"; stderr: {stderr_lines[-1]}" if stderr_lines else ""
        result.errors.append(
            f"pip-audit returned invalid JSON (UNKNOWN; exit code {proc.returncode}{detail})"
        )
        return result

    deps = data.get("dependencies", [])
    vuln_count = 0

    for dep in deps:
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
                    file_path=finding_file_path,
                    why=f"{vuln.get('description', 'Known vulnerability in this package version.')}",
                    fix=fix_str,
                    command=f"uv pip install --upgrade {dep['name']}" if fix_version else None,
                    time_estimate="~5 minutes",
                    scanner="pip-audit",
                )
            )

    if not vuln_count:
        result.passed.append(
            f"No dependency vulnerabilities found in {len(deps)} package(s) "
            f"(pip-audit, via {population_source})"
        )

    return result
