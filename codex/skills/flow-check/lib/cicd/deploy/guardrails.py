"""Woodpecker deployment guardrails.

Pre-deploy validation gates that prevent common deployment failures:
- Stale commit protection (HEAD must match remote)
- Deploy lock (flock-based, prevents concurrent deploys on shared Docker hosts)
- Capability-based readiness checks (validate service can actually serve, not just respond)
- docker.sock access audit logging
"""

from __future__ import annotations

import errno
import fcntl
import logging
import os
import shutil
import stat
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional

from ..state import StepStatus
from ..steps import StepResult

logger = logging.getLogger(__name__)

#: The deploy lock. A FIXED, SHARED, WORLD-READABLE PATH, DELIBERATELY - see
#: `docs/security/bandit-finding-dispositions.md` (B108, issue #1113).
#:
#: bandit flags the hardcoded `/tmp` literal, and the two obvious ways to clear
#: that finding both delete the property this lock exists for. Per-uid
#: (`...-{os.getuid()}.lock`) stops excluding the OTHER users the module
#: docstring promises to exclude on a shared Docker host. `tempfile.gettempdir()`
#: reads `$TMPDIR`, so a user with a custom one silently stops participating in
#: the lock - the worst of the three, because nothing would look wrong.
#:
#: A lock in a shared directory is shared on purpose. What is NOT acceptable is
#: opening whatever happens to be sitting at that path, and `_open_lock_file`
#: below is where that is handled instead.
DEPLOY_LOCK_PATH = Path("/tmp/claude-power-pack-deploy.lock")


class LockPathUnsafe(RuntimeError):
    """The deploy lock path is not a plain file we can safely take.

    Raised instead of quietly proceeding, because both cases mean another local
    user has already put something at the path we were about to write.
    """


def _open_lock_file(path: Path):  # type: ignore[no-untyped-def]
    """Open `path` for locking, refusing anything that is not a regular file.

    The pre-#1113 line was `open(path, "w")`, and in a world-writable directory
    that is two distinct hazards, closed here by two distinct flags. Both were
    measured on the old code rather than reasoned about (issue #1113):

    ``O_NOFOLLOW`` - a symlink at the path. Any local user can point
    `/tmp/claude-power-pack-deploy.lock` at a file the deploying user can write,
    and `open(..., "w")` follows it and TRUNCATES the target. Probed on the old
    code: a victim file holding ``precious`` came back holding ``pid=1 time=0``.
    Linux's ``fs.protected_symlinks`` blocks this in the common sticky-directory
    case, but it is a sysctl someone else owns, not a property of this code.

    ``O_NONBLOCK`` + ``S_ISREG`` - a FIFO at the path. ``O_NOFOLLOW`` permits it,
    and opening a FIFO for writing BLOCKS until a reader appears: a deploy that
    HANGS rather than one that fails, which is strictly harder to diagnose.
    Measured on the old code as a 120s pytest-timeout kill inside `open()`.
    Checking the fd we actually got (``fstat``), rather than the path before
    opening it (``lstat``), is what makes this free of a swap-in-between race.

    No ``O_EXCL``: a leftover regular lock file from a previous deploy is the
    NORMAL state on any host that has deployed once, and refusing it would
    refuse every deploy after the first.

    THE CREATION MODE IS ``0o666``, MATCHING ``open(path, "w")`` EXACTLY, and it
    is not a typo (counter-model review, #1113). Hardcoding the more restrictive
    ``0o644`` here looks like hardening and is the opposite: `open(path, "w")`
    requests ``0o666`` and lets the process umask decide, so on a shared-group
    deploy host running ``umask 002`` the lock was created ``0664`` and a SECOND
    deploying user could open it ``O_RDWR``. At ``0o644`` that user gets
    ``EACCES`` and cannot take the lock at all - which breaks the cross-user
    mutual exclusion this whole path exists to preserve, in the name of securing
    it. Requesting ``0o666`` keeps the permission behaviour byte-identical to the
    code this replaced; the hardening is the FLAGS, not the mode.
    """
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(path, flags, 0o666)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EMLINK):
            raise LockPathUnsafe(
                f"deploy lock path {path} is a symlink; refusing to follow it"
            ) from exc
        raise

    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise LockPathUnsafe(
                f"deploy lock path {path} is not a regular file; refusing to use it"
            )
    except BaseException:
        os.close(fd)
        raise

    return os.fdopen(fd, "r+")


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
    lock_file = _open_lock_file(path)
    acquired = False

    try:
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                # `_open_lock_file` does not pass O_TRUNC (see its docstring), so
                # a leftover line from a previous deploy is cleared here instead.
                lock_file.seek(0)
                lock_file.truncate()
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
