"""Woodpecker deployment guardrails.

Pre-deploy validation gates that prevent common deployment failures:
- Stale commit protection (HEAD must match remote)
- Deploy lock (flock-based, prevents concurrent deploys on shared Docker hosts)
- Capability-based readiness checks (validate service can actually serve, not just respond)
- docker.sock access audit logging
"""

from __future__ import annotations

import fcntl
import logging
import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional

from ..state import StepStatus
from ..steps import StepResult

logger = logging.getLogger(__name__)

DEPLOY_LOCK_PATH = Path("/tmp/claude-power-pack-deploy.lock")


@dataclass
class CapabilityCheck:
    """A post-readiness capability validation.

    Unlike health checks (HTTP 200), capability checks verify that a
    service can actually perform its function - e.g., has loaded secrets,
    can reach required dependencies, responds to domain-specific probes.
    """

    name: str
    command: str
    timeout_seconds: int = 10

    def run(self, cwd: Optional[str] = None) -> CapabilityResult:
        try:
            proc = subprocess.run(
                self.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=cwd,
            )
            return CapabilityResult(
                name=self.name,
                passed=proc.returncode == 0,
                output=proc.stdout.strip(),
                error=proc.stderr.strip() if proc.returncode != 0 else "",
            )
        except subprocess.TimeoutExpired:
            return CapabilityResult(
                name=self.name,
                passed=False,
                error=f"Timed out after {self.timeout_seconds}s",
            )
        except OSError as e:
            return CapabilityResult(
                name=self.name,
                passed=False,
                error=str(e),
            )


@dataclass
class CapabilityResult:
    name: str
    passed: bool
    output: str = ""
    error: str = ""


def run_capability_checks(
    checks: list[CapabilityCheck],
    cwd: Optional[str] = None,
) -> tuple[bool, list[CapabilityResult]]:
    """Run all capability checks and return aggregate result."""
    if not checks:
        return True, []

    results = [check.run(cwd=cwd) for check in checks]
    all_passed = all(r.passed for r in results)
    return all_passed, results


def check_stale_commit(
    project_root: Optional[str] = None,
    branch: str = "main",
    remote: str = "origin",
) -> StepResult:
    """Verify local HEAD matches the remote branch tip.

    Prevents deploying stale code when the local checkout has drifted
    behind the canonical remote.
    """
    cwd = project_root or os.getcwd()
    git = shutil.which("git")
    if not git:
        return StepResult(
            status=StepStatus.FAILED,
            exit_code=1,
            error="git not found in PATH",
        )

    try:
        subprocess.run(
            [git, "fetch", remote, branch],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return StepResult(
            status=StepStatus.FAILED,
            exit_code=1,
            error=f"Failed to fetch {remote}/{branch}: {e}",
        )

    try:
        local = subprocess.run(
            [git, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        remote_ref = subprocess.run(
            [git, "rev-parse", f"{remote}/{branch}"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return StepResult(
            status=StepStatus.FAILED,
            exit_code=1,
            error=f"Failed to resolve refs: {e}",
        )

    local_sha = local.stdout.strip()
    remote_sha = remote_ref.stdout.strip()

    if local_sha != remote_sha:
        return StepResult(
            status=StepStatus.FAILED,
            exit_code=1,
            output=f"local={local_sha[:12]} remote={remote_sha[:12]}",
            error=(
                f"Stale commit: HEAD ({local_sha[:12]}) does not match "
                f"{remote}/{branch} ({remote_sha[:12]}). "
                f"Run 'git pull {remote} {branch}' before deploying."
            ),
        )

    return StepResult(
        status=StepStatus.SUCCESS,
        exit_code=0,
        output=f"HEAD matches {remote}/{branch} at {local_sha[:12]}",
    )


@contextmanager
def deploy_lock(
    lock_path: Optional[Path] = None,
    timeout_seconds: float = 300,
) -> Generator[None, None, None]:
    """Acquire an exclusive deploy lock to prevent concurrent deploys.

    Uses flock to coordinate on shared Docker hosts where multiple
    pipelines may attempt simultaneous deploys.
    """
    path = lock_path or DEPLOY_LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    lock_file = open(path, "w")
    acquired = False

    try:
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                lock_file.write(f"pid={os.getpid()} time={time.time():.0f}\n")
                lock_file.flush()
                logger.info("Deploy lock acquired: %s", path)
                break
            except BlockingIOError:
                elapsed = time.monotonic() - start
                if elapsed >= timeout_seconds:
                    raise TimeoutError(
                        f"Could not acquire deploy lock at {path} "
                        f"after {timeout_seconds:.0f}s. Another deploy may "
                        f"be in progress."
                    )
                time.sleep(2)

        yield

    finally:
        if acquired:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        lock_file.close()
        logger.info("Deploy lock released: %s", path)


def check_docker_socket(socket_path: str = "/var/run/docker.sock") -> StepResult:
    """Validate docker.sock is accessible and log the access for auditability."""
    if not os.path.exists(socket_path):
        return StepResult(
            status=StepStatus.FAILED,
            exit_code=1,
            error=f"Docker socket not found: {socket_path}",
        )

    if not os.access(socket_path, os.R_OK | os.W_OK):
        return StepResult(
            status=StepStatus.FAILED,
            exit_code=1,
            error=(
                f"Docker socket not accessible: {socket_path}. "
                f"Current user: {os.getenv('USER', 'unknown')} "
                f"(uid={os.getuid()})"
            ),
        )

    logger.info(
        "docker.sock access validated: path=%s user=%s uid=%d pid=%d",
        socket_path,
        os.getenv("USER", "unknown"),
        os.getuid(),
        os.getpid(),
    )

    return StepResult(
        status=StepStatus.SUCCESS,
        exit_code=0,
        output=f"Docker socket accessible: {socket_path}",
    )


def safe_docker_prune(
    project_root: Optional[str] = None,
    lock_path: Optional[Path] = None,
) -> StepResult:
    """Run docker image prune under deploy lock to prevent cache races.

    Concurrent prune operations can remove images that another build
    is actively using. This wraps the prune in the same deploy lock.
    """
    docker = shutil.which("docker")
    if not docker:
        return StepResult(
            status=StepStatus.FAILED,
            exit_code=1,
            error="docker not found in PATH",
        )

    try:
        with deploy_lock(lock_path=lock_path, timeout_seconds=60):
            proc = subprocess.run(
                [docker, "image", "prune", "-f", "--filter", "until=1h"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=project_root,
            )
            if proc.returncode == 0:
                return StepResult(
                    status=StepStatus.SUCCESS,
                    exit_code=0,
                    output=proc.stdout.strip(),
                )
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=proc.returncode,
                output=proc.stdout,
                error=proc.stderr,
            )
    except TimeoutError as e:
        return StepResult(
            status=StepStatus.FAILED,
            exit_code=1,
            error=str(e),
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return StepResult(
            status=StepStatus.FAILED,
            exit_code=1,
            error=f"Docker prune failed: {e}",
        )
