"""Health check runner for CI/CD & Verification.

Checks HTTP endpoints and running processes to verify deployment health.
Uses curl for HTTP checks and ss/lsof for process checks - no Python deps.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from typing import Optional

from .config import CICDConfig, HealthEndpoint, ProcessCheck
from .models import HealthCheckEntry, HealthCheckResult


def run_health_checks(
    config: Optional[CICDConfig] = None,
    project_root: Optional[str] = None,
) -> HealthCheckResult:
    """Run all configured health checks.

    Args:
        config: CI/CD config (loaded from project_root if None).
        project_root: Project root for config loading.

    Returns:
        HealthCheckResult with all check entries.
    """
    if config is None:
        config = CICDConfig.load(project_root)

    result = HealthCheckResult()

    # Wait for startup if configured
    if config.health.startup_delay > 0:
        time.sleep(config.health.startup_delay)

    # Run endpoint checks
    for endpoint in config.health.endpoints:
        entry = check_endpoint(endpoint)
        result.checks.append(entry)

    # Run process checks
    for process in config.health.processes:
        entry = check_process(process)
        result.checks.append(entry)

    return result


def check_endpoint(endpoint: HealthEndpoint) -> HealthCheckEntry:
    """Check a single HTTP endpoint using curl.

    Args:
        endpoint: Endpoint configuration.

    Returns:
        HealthCheckEntry with pass/fail and details.
    """
    name = endpoint.name or endpoint.url
    start = time.monotonic()

    curl_path = shutil.which("curl")
    if not curl_path:
        return HealthCheckEntry(
            name=name,
            kind="endpoint",
            passed=False,
            detail="curl not found in PATH",
        )

    try:
        # Use curl to get status code and body
        proc = subprocess.run(
            [
                curl_path,
                "-sf",
                "-o", "/dev/stdout",
                "-w", "\n%{http_code}",
                "--max-time", str(endpoint.timeout),
                endpoint.url,
            ],
            capture_output=True,
            text=True,
            timeout=endpoint.timeout + 2,
        )
        elapsed = (time.monotonic() - start) * 1000

        # Parse output: body lines + last line is status code
        output_lines = proc.stdout.rstrip("\n").rsplit("\n", 1)
        if len(output_lines) == 2:
            body, status_str = output_lines
        elif len(output_lines) == 1:
            # Could be just status code (empty body) or just body (no code)
            try:
                int(output_lines[0])
                body, status_str = "", output_lines[0]
            except ValueError:
                body, status_str = output_lines[0], ""
        else:
            body, status_str = "", ""

        # If curl failed entirely (connection refused, etc.)
        if proc.returncode != 0 and not status_str:
            stderr = proc.stderr.strip()
            detail = stderr if stderr else f"curl exit code {proc.returncode}"
            return HealthCheckEntry(
                name=name,
                kind="endpoint",
                passed=False,
                detail=detail,
                elapsed_ms=elapsed,
            )

        try:
            status_code = int(status_str)
        except (ValueError, TypeError):
            return HealthCheckEntry(
                name=name,
                kind="endpoint",
                passed=False,
                detail="Could not parse HTTP status from curl output",
                elapsed_ms=elapsed,
            )

        # Check status code
        if status_code != endpoint.expected_status:
            return HealthCheckEntry(
                name=name,
                kind="endpoint",
                passed=False,
                detail=f"HTTP {status_code} (expected {endpoint.expected_status})",
                elapsed_ms=elapsed,
            )

        # Check body content if specified
        if endpoint.expected_body and endpoint.expected_body not in body:
            return HealthCheckEntry(
                name=name,
                kind="endpoint",
                passed=False,
                detail=f"Response body missing expected content: {endpoint.expected_body!r}",
                elapsed_ms=elapsed,
            )

        return HealthCheckEntry(
            name=name,
            kind="endpoint",
            passed=True,
            detail=f"HTTP {status_code}",
            elapsed_ms=elapsed,
        )

    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - start) * 1000
        return HealthCheckEntry(
            name=name,
            kind="endpoint",
            passed=False,
            detail=f"Timeout after {endpoint.timeout}s",
            elapsed_ms=elapsed,
        )
    except OSError as e:
        elapsed = (time.monotonic() - start) * 1000
        return HealthCheckEntry(
            name=name,
            kind="endpoint",
            passed=False,
            detail=str(e),
            elapsed_ms=elapsed,
        )


def check_process(process: ProcessCheck) -> HealthCheckEntry:
    """Check that a configured process is alive.

    Dispatches on the single probe method the check names (issue #620):
    ``port`` (ss/lsof), ``systemd_user_unit``, ``systemd_unit``, or
    ``pattern``.

    Args:
        process: Process check configuration.

    Returns:
        HealthCheckEntry with pass/fail and details.
    """
    probe = process.probe
    if probe == "systemd_user_unit":
        return _check_systemd_unit(process, user=True)
    if probe == "systemd_unit":
        return _check_systemd_unit(process, user=False)
    if probe == "pattern":
        return _check_pattern(process)
    return _check_port(process)


def _check_systemd_unit(process: ProcessCheck, user: bool) -> HealthCheckEntry:
    """Check a systemd unit with ``systemctl [--user] is-active <unit>``."""
    unit = process.systemd_user_unit if user else process.systemd_unit
    label = "user unit" if user else "unit"
    name = f"{process.name} ({label} {unit})"
    start = time.monotonic()

    systemctl_path = shutil.which("systemctl")
    if not systemctl_path:
        return HealthCheckEntry(
            name=name,
            kind="process",
            passed=False,
            detail="systemctl not found in PATH",
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    argv = [systemctl_path]
    if user:
        argv.append("--user")
    argv += ["is-active", str(unit)]

    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired:
        return HealthCheckEntry(
            name=name,
            kind="process",
            passed=False,
            detail="Timeout after 5s running systemctl is-active",
            elapsed_ms=(time.monotonic() - start) * 1000,
        )
    except OSError as e:
        return HealthCheckEntry(
            name=name,
            kind="process",
            passed=False,
            detail=str(e),
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    elapsed = (time.monotonic() - start) * 1000
    # `is-active` prints the state on stdout either way and exits 0 only when
    # active, so the exit code is the verdict and stdout is the detail.
    state = proc.stdout.strip() or proc.stderr.strip() or "unknown"
    if proc.returncode == 0:
        return HealthCheckEntry(
            name=name,
            kind="process",
            passed=True,
            detail=f"Unit is {state}",
            elapsed_ms=elapsed,
        )

    return HealthCheckEntry(
        name=name,
        kind="process",
        passed=False,
        detail=f"Unit is {state}",
        elapsed_ms=elapsed,
    )


def _check_pattern(process: ProcessCheck) -> HealthCheckEntry:
    """Check for a running process matching a pattern with ``pgrep -f``."""
    pattern = str(process.pattern)
    name = f"{process.name} (pattern {pattern})"
    start = time.monotonic()

    pgrep_path = shutil.which("pgrep")
    if not pgrep_path:
        return HealthCheckEntry(
            name=name,
            kind="process",
            passed=False,
            detail="pgrep not found in PATH",
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    try:
        proc = subprocess.run(
            [pgrep_path, "-f", pattern],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return HealthCheckEntry(
            name=name,
            kind="process",
            passed=False,
            detail="Timeout after 5s running pgrep",
            elapsed_ms=(time.monotonic() - start) * 1000,
        )
    except OSError as e:
        return HealthCheckEntry(
            name=name,
            kind="process",
            passed=False,
            detail=str(e),
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    elapsed = (time.monotonic() - start) * 1000
    pids = proc.stdout.split()
    if proc.returncode == 0 and pids:
        noun = "process" if len(pids) == 1 else "processes"
        return HealthCheckEntry(
            name=name,
            kind="process",
            passed=True,
            detail=f"{len(pids)} matching {noun} (pid {', '.join(pids)})",
            elapsed_ms=elapsed,
        )

    return HealthCheckEntry(
        name=name,
        kind="process",
        passed=False,
        detail="No process matches the pattern",
        elapsed_ms=elapsed,
    )


def _check_port(process: ProcessCheck) -> HealthCheckEntry:
    """Check if a process is listening on the expected port.

    Uses ss (preferred) or lsof as fallback.
    """
    name = f"{process.name} (port {process.port})"
    start = time.monotonic()

    # Try ss first (Linux standard)
    ss_path = shutil.which("ss")
    if ss_path:
        try:
            proc = subprocess.run(
                [ss_path, "-tlnp"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            elapsed = (time.monotonic() - start) * 1000

            port_str = f":{process.port}"
            for line in proc.stdout.splitlines():
                if port_str in line:
                    return HealthCheckEntry(
                        name=name,
                        kind="process",
                        passed=True,
                        detail=f"Listening on port {process.port}",
                        elapsed_ms=elapsed,
                    )

            return HealthCheckEntry(
                name=name,
                kind="process",
                passed=False,
                detail=f"Nothing listening on port {process.port}",
                elapsed_ms=elapsed,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass  # Fall through to lsof

    # Try lsof fallback (macOS, some Linux)
    lsof_path = shutil.which("lsof")
    if lsof_path:
        try:
            proc = subprocess.run(
                [lsof_path, "-i", f":{process.port}", "-sTCP:LISTEN", "-P", "-n"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            elapsed = (time.monotonic() - start) * 1000

            if proc.returncode == 0 and proc.stdout.strip():
                return HealthCheckEntry(
                    name=name,
                    kind="process",
                    passed=True,
                    detail=f"Listening on port {process.port}",
                    elapsed_ms=elapsed,
                )

            return HealthCheckEntry(
                name=name,
                kind="process",
                passed=False,
                detail=f"Nothing listening on port {process.port}",
                elapsed_ms=elapsed,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

    elapsed = (time.monotonic() - start) * 1000
    return HealthCheckEntry(
        name=name,
        kind="process",
        passed=False,
        detail="Neither ss nor lsof found in PATH",
        elapsed_ms=elapsed,
    )
