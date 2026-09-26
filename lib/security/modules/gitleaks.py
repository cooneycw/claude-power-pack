"""External tool adapter: gitleaks.

Runs gitleaks for deep secret detection in code and git history.

A missing binary is reported as UNKNOWN in `result.errors`, never as a skip
(issue #1264, the shape #1044 fixed in pip_audit): a secret scan that did not
run must not leave a summary that reads as clean.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from ..models import Finding, ScanResult, Severity


def is_available() -> bool:
    """Check if gitleaks is installed."""
    return shutil.which("gitleaks") is not None


def scan(project_root: str, include_history: bool = False) -> ScanResult:
    """Run gitleaks on the project."""
    result = ScanResult()

    if not is_available():
        result.errors.append(
            "UNKNOWN: gitleaks is not installed, so no secret scan ran "
            "(run `brew install gitleaks` or see https://github.com/gitleaks/gitleaks)"
        )
        return result

    cmd = [
        "gitleaks", "detect", "--source", project_root,
        "--report-format", "json", "--report-path", "/dev/stdout",
        "--no-banner",
    ]

    if not include_history:
        cmd.append("--no-git")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        result.errors.append("UNKNOWN: gitleaks timed out after 120 seconds")
        return result
    except FileNotFoundError:
        result.errors.append("UNKNOWN: gitleaks binary disappeared before the scan ran")
        return result

    # gitleaks returns exit code 1 when findings exist, 0 when clean
    if proc.returncode == 0:
        label = "code and git history" if include_history else "working tree"
        result.passed.append(f"No secrets found by gitleaks ({label})")
        return result

    # 1 is "findings exist"; anything else is gitleaks failing, and an empty
    # stdout from a failure would otherwise parse to zero findings - a result
    # with no pass and no error, which a summary reads as nothing to report.
    if proc.returncode != 1:
        stderr_lines = proc.stderr.rstrip().splitlines()
        detail = f"; stderr: {stderr_lines[-1]}" if stderr_lines else ""
        result.errors.append(f"UNKNOWN: gitleaks exited {proc.returncode}{detail}")
        return result

    # Exit 1 is ALSO what gitleaks returns for some failures - a nonexistent
    # source, for one - with an empty stdout (counter-model review). Only a
    # report can say secrets were found, so no report is UNKNOWN, not zero.
    if not proc.stdout.strip():
        stderr_lines = proc.stderr.rstrip().splitlines()
        detail = f"; stderr: {stderr_lines[-1]}" if stderr_lines else ""
        result.errors.append(f"UNKNOWN: gitleaks exited 1 with no report{detail}")
        return result

    # Parse JSON output
    try:
        findings = json.loads(proc.stdout)
    except json.JSONDecodeError:
        # gitleaks found issues but output isn't parseable
        result.findings.append(
            Finding(
                id="GITLEAKS_FINDING",
                severity=Severity.CRITICAL,
                title="gitleaks detected secrets (could not parse details)",
                why="gitleaks found secrets but the output format was unexpected.",
                fix="Run `gitleaks detect` manually for details.",
            )
        )
        return result

    if not isinstance(findings, list) or not findings or not all(isinstance(i, dict) for i in findings):
        result.errors.append("UNKNOWN: gitleaks exited 1 but its report held no readable findings")
        return result

    for item in findings:
        secret_val = item.get("Secret", "")
        masked = secret_val[:4] + "****" if len(secret_val) > 4 else "****"

        result.findings.append(
            Finding(
                id="GITLEAKS_" + item.get("RuleID", "UNKNOWN").upper(),
                severity=Severity.CRITICAL,
                title=f"Secret detected: {item.get('Description', 'Unknown')}",
                file_path=item.get("File", ""),
                line_number=item.get("StartLine"),
                why="This secret was detected by gitleaks pattern matching. "
                "If committed, it may be visible in your repository history.",
                fix="Remove the secret from source, rotate the credential, "
                "and load from environment variables.",
                time_estimate="~5 minutes",
                scanner="gitleaks",
                raw_match=masked,
            )
        )

    return result
