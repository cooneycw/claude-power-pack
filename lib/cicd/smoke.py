"""Smoke test runner for CI/CD & Verification.

Executes lightweight smoke tests defined in .claude/cicd.yml.
Each test runs a shell command and checks exit code and optional output patterns.
"""

from __future__ import annotations

import subprocess
import time
from typing import Optional

from .config import CICDConfig, SmokeTest
from .models import SmokeTestEntry, SmokeTestResult


def run_smoke_tests(
    config: Optional[CICDConfig] = None,
    project_root: Optional[str] = None,
) -> SmokeTestResult:
    """Run all configured smoke tests.

    Args:
        config: CI/CD config (loaded from project_root if None).
        project_root: Project root for config loading.

    Returns:
        SmokeTestResult with all test entries.
    """
    if config is None:
        config = CICDConfig.load(project_root)

    result = SmokeTestResult()

    for test in config.health.smoke_tests:
        entry = run_single_test(test)
        result.tests.append(entry)

    return result


def run_single_test(test: SmokeTest) -> SmokeTestEntry:
    """Run a single smoke test.

    Args:
        test: Smoke test configuration.

    Returns:
        SmokeTestEntry with pass/fail and details.
    """
    start = time.monotonic()

    try:
        proc = subprocess.run(
            test.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=test.timeout,
        )
        elapsed = (time.monotonic() - start) * 1000

        output = proc.stdout.strip()
        stderr = proc.stderr.strip()
        passed = True
        detail_parts = []

        # Check exit code
        if proc.returncode != test.expected_exit:
            passed = False
            detail_parts.append(
                f"exit {proc.returncode} (expected {test.expected_exit})"
            )

        # Check expected output if specified
        if test.expected_output:
            if test.expected_output not in output:
                passed = False
                detail_parts.append(
                    f"output missing: {test.expected_output!r}"
                )

        if passed:
            detail = f"exit {proc.returncode}"
        else:
            detail = "; ".join(detail_parts)
            # Append stderr for debugging if available
            if stderr and not passed:
                # Truncate long stderr
                if len(stderr) > 200:
                    stderr = stderr[:200] + "..."
                detail += f" | stderr: {stderr}"

        return SmokeTestEntry(
            name=test.name,
            command=test.command,
            passed=passed,
            exit_code=proc.returncode,
            output=output[:500] if output else "",
            detail=detail,
            elapsed_ms=elapsed,
        )

    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - start) * 1000
        return SmokeTestEntry(
            name=test.name,
            command=test.command,
            passed=False,
            exit_code=-1,
            detail=f"Timeout after {test.timeout}s",
            elapsed_ms=elapsed,
        )
    except OSError as e:
        elapsed = (time.monotonic() - start) * 1000
        return SmokeTestEntry(
            name=test.name,
            command=test.command,
            passed=False,
            exit_code=-1,
            detail=str(e),
            elapsed_ms=elapsed,
        )
