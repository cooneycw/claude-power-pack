"""External tool adapter: gitleaks.

Runs gitleaks for deep secret detection in code and git history.
Auto-detected: only runs if gitleaks is installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..models import Finding, ScanResult, Severity


def is_available() -> bool:
    """Check if gitleaks is installed."""
    return shutil.which("gitleaks") is not None


def scan(project_root: str, include_history: bool = False) -> ScanResult:
    """Run gitleaks on the project."""
    result = ScanResult()

    if not is_available():
        result.skipped.append("gitleaks not installed (run `brew install gitleaks` or see https://github.com/gitleaks/gitleaks)")
        return result

    cmd = ["gitleaks", "detect", "--source", project_root, "--report-format", "json", "--report-path", "/dev/stdout", "--no-banner"]

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
        result.errors.append("gitleaks timed out after 120 seconds")
        return result
    except FileNotFoundError:
        result.skipped.append("gitleaks not found")
        return result

    # gitleaks returns exit code 1 when findings exist, 0 when clean
    if proc.returncode == 0:
        label = "code and git history" if include_history else "working tree"
        result.passed.append(f"No secrets found by gitleaks ({label})")
        return result

    # Parse JSON output
    try:
        findings = json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError:
        if proc.returncode == 1:
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
