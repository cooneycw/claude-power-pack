"""Step implementations for the deterministic CI/CD runner.

Each step type knows how to execute a specific kind of operation
(shell command, git operation, deploy) with timeout and retry support.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from .state import StepStatus


class StepExecutor(Protocol):
    """Protocol for step execution implementations."""

    id: str
    timeout_seconds: int
    max_attempts: int
    idempotent: bool

    def execute(self, context: dict[str, Any]) -> StepResult: ...


@dataclass
class StepResult:
    """Result of executing a single step."""

    status: StepStatus
    exit_code: int = 0
    output: str = ""
    error: str = ""

    @property
    def success(self) -> bool:
        return self.status == StepStatus.SUCCESS


@dataclass
class StepDef:
    """Definition of a step from the task manifest or built-in plan.

    This is the configuration - StepExecutor handles execution.
    """

    id: str
    command: str
    description: str = ""
    timeout_seconds: int = 600
    max_attempts: int = 1
    backoff_seconds: float = 2.0
    idempotent: bool = True
    skip_if: Optional[str] = None  # shell expression; step skipped if exits 0
    depends_on: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "command": self.command,
            "description": self.description,
            "timeout_seconds": self.timeout_seconds,
            "max_attempts": self.max_attempts,
            "idempotent": self.idempotent,
        }
        if self.env:
            d["env"] = self.env
        return d


class ShellStep:
    """Execute a shell command with timeout and retry support.

    This is the primary step type - most CI/CD operations are shell commands
    (make lint, make test, git push, etc.)
    """

    def __init__(self, step_def: StepDef):
        self.id = step_def.id
        self.command = step_def.command
        self.timeout_seconds = step_def.timeout_seconds
        self.max_attempts = step_def.max_attempts
        self.backoff_seconds = step_def.backoff_seconds
        self.idempotent = step_def.idempotent
        self.skip_if = step_def.skip_if
        self.description = step_def.description
        self.env = step_def.env

    def should_skip(self, context: dict[str, Any]) -> bool:
        """Check if this step should be skipped."""
        if not self.skip_if:
            return False
        try:
            result = subprocess.run(
                self.skip_if,
                shell=True,
                capture_output=True,
                timeout=10,
                cwd=context.get("project_root"),
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def execute(self, context: dict[str, Any]) -> StepResult:
        """Execute the shell command, streaming output live while capturing it.

        Output is teed line-by-line to ``context['output_stream']`` (when
        present) as the child produces it, so a slow-but-progressing command
        (e.g. a large ``pytest`` suite) shows live progress instead of going
        silent until it exits - a slow run is then distinguishable from a real
        hang. Both stdout and stderr are still captured in the StepResult, and
        partial output is preserved on a timeout so the wall-clock kill shows
        *where* the command was rather than discarding everything (issue #537).
        """
        cwd = context.get("project_root")
        env = context.get("env")
        stream = context.get("output_stream")

        if self.env:
            if env is None:
                env = dict(os.environ)
            else:
                env = dict(env)
            env.update(self.env)

        try:
            proc = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # line-buffered so tee'd progress appears promptly
                cwd=cwd,
                env=env,
                start_new_session=True,  # own process group -> whole tree killable on timeout
            )
        except OSError as e:
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=1,
                error=str(e),
            )

        out_chunks: list[str] = []
        err_chunks: list[str] = []
        tee_lock = threading.Lock()

        def _pump(pipe: Any, sink: list[str]) -> None:
            try:
                for line in pipe:
                    sink.append(line)
                    if stream is not None:
                        with tee_lock:
                            stream.write(line)
                            stream.flush()
            finally:
                pipe.close()

        readers = [
            threading.Thread(target=_pump, args=(proc.stdout, out_chunks), daemon=True),
            threading.Thread(target=_pump, args=(proc.stderr, err_chunks), daemon=True),
        ]
        for reader in readers:
            reader.start()

        timed_out = False
        try:
            proc.wait(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._kill_process_tree(proc)

        # Let the reader threads drain buffered output before assembling the
        # result; capped so a child that leaked a pipe to a survivor can't hang.
        for reader in readers:
            reader.join(timeout=5)

        output = "".join(out_chunks)
        error = "".join(err_chunks)

        if timed_out:
            timeout_msg = f"Step timed out after {self.timeout_seconds}s"
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=124,  # standard timeout exit code
                output=output,
                error=f"{error}\n{timeout_msg}".strip() if error else timeout_msg,
            )

        if proc.returncode == 0:
            return StepResult(
                status=StepStatus.SUCCESS,
                exit_code=0,
                output=output,
            )
        return StepResult(
            status=StepStatus.FAILED,
            exit_code=proc.returncode if proc.returncode is not None else 1,
            output=output,
            error=error,
        )

    @staticmethod
    def _kill_process_tree(proc: subprocess.Popen[str]) -> None:
        """Kill a timed-out child and its process group.

        The step runs ``shell=True`` and often spawns children (``make`` ->
        ``pytest``). Killing only the shell leaves those children holding the
        output pipes open, so the reader threads never reach EOF. Signalling the
        whole process group tears the tree down and lets the readers drain.
        """
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    def execute_with_retry(self, context: dict[str, Any]) -> StepResult:
        """Execute with retry policy (exponential backoff)."""
        last_result = StepResult(status=StepStatus.FAILED)
        delay = self.backoff_seconds

        for attempt in range(1, self.max_attempts + 1):
            result = self.execute(context)

            if result.success:
                return result

            last_result = result

            # Don't retry non-idempotent steps
            if not self.idempotent:
                return result

            # Don't sleep after the last attempt
            if attempt < self.max_attempts:
                time.sleep(delay)
                delay = min(delay * 2, 30.0)  # cap backoff at 30s

        return last_result


# Built-in plan definitions for flow commands
# These define the steps that each flow command executes

BUILTIN_PLANS: dict[str, list[StepDef]] = {
    "finish": [
        StepDef(
            id="lint",
            command="make lint",
            description="Run linter",
            timeout_seconds=300,
            max_attempts=1,
            skip_if='! grep -q "^lint:" Makefile 2>/dev/null',
        ),
        StepDef(
            id="test",
            command="make test",
            description="Run tests",
            timeout_seconds=600,
            max_attempts=1,
            skip_if='! grep -q "^test:" Makefile 2>/dev/null',
        ),
        StepDef(
            id="security_scan",
            command=(
                'PYTHONPATH="${HOME}/Projects/claude-power-pack" '
                "python3 -m lib.security gate flow_finish"
            ),
            description="Run security quick scan",
            timeout_seconds=120,
            max_attempts=1,
            skip_if='! PYTHONPATH="${HOME}/Projects/claude-power-pack" python3 -c \'import lib.security\' 2>/dev/null',
        ),
    ],
    "check": [
        StepDef(
            id="lint",
            command="make lint",
            description="Run linter",
            timeout_seconds=300,
            max_attempts=1,
            skip_if='! grep -q "^lint:" Makefile 2>/dev/null',
        ),
        StepDef(
            id="test",
            command="make test",
            description="Run tests",
            timeout_seconds=600,
            max_attempts=1,
            skip_if='! grep -q "^test:" Makefile 2>/dev/null',
        ),
    ],
    "deploy": [
        StepDef(
            id="bootstrap_check",
            command=(
                'PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" '
                "python3 -m lib.cicd.bootstrap check"
            ),
            description="Check admin-only bootstrap dependencies",
            timeout_seconds=30,
            max_attempts=1,
            skip_if="! [ -f .claude/bootstrap.yaml ]",
        ),
        StepDef(
            id="stale_commit_check",
            command=(
                'LOCAL=$(git rev-parse HEAD) && '
                'git fetch origin main --quiet && '
                'REMOTE=$(git rev-parse origin/main) && '
                '[ "$LOCAL" = "$REMOTE" ] || '
                '{ echo "STALE: local=$LOCAL remote=$REMOTE"; exit 1; }'
            ),
            description="Verify HEAD matches origin/main (stale commit guard)",
            timeout_seconds=30,
            max_attempts=1,
            skip_if='[ "$(git branch --show-current)" != "main" ]',
        ),
        StepDef(
            id="security_scan",
            command=(
                'PYTHONPATH="${HOME}/Projects/claude-power-pack" '
                "python3 -m lib.security gate flow_deploy"
            ),
            description="Run security scan before deploy",
            timeout_seconds=120,
            max_attempts=1,
            skip_if='! PYTHONPATH="${HOME}/Projects/claude-power-pack" python3 -c \'import lib.security\' 2>/dev/null',
        ),
        StepDef(
            id="deploy",
            command="make deploy",
            description="Run deployment",
            timeout_seconds=1800,
            max_attempts=1,
            idempotent=False,
        ),
    ],
}


class DeployStep:
    """Execute a deployment with readiness gate and automatic rollback.

    Wraps a DeploymentStrategy to provide:
    1. Deploy via the configured strategy
    2. Poll readiness URL until success threshold or timeout
    3. Automatic rollback if readiness check fails

    Usage:
        config = DeployConfig(strategy="docker_compose", ...)
        step = DeployStep(config)
        result = step.execute(context)
    """

    def __init__(self, config: Optional[Any] = None):
        from .deploy.strategy import DeployConfig, get_strategy

        if config is None:
            config = DeployConfig()
        elif isinstance(config, dict):
            config = DeployConfig.from_dict(config)

        self.config: DeployConfig = config
        self.id = "deploy"
        self.timeout_seconds = config.timeout_seconds
        self.max_attempts = 1
        self.idempotent = False

        self.strategy = get_strategy(config.strategy)

    def execute(self, context: dict[str, Any]) -> StepResult:
        """Execute deploy, check readiness, rollback on failure."""
        from .deploy.strategy import poll_readiness

        # Step 1: Deploy
        deploy_result = self.strategy.deploy(context, self.config)
        if not deploy_result.success:
            return deploy_result

        # Step 2: Readiness gate (if configured)
        if self.config.readiness:
            readiness = poll_readiness(self.config.readiness)
            if not readiness.ready:
                # Step 3: Auto-rollback on readiness failure
                rollback_result = self.strategy.rollback(context, self.config)
                rollback_info = (
                    "rollback succeeded" if rollback_result.success
                    else f"rollback also failed: {rollback_result.error}"
                )
                return StepResult(
                    status=StepStatus.FAILED,
                    exit_code=1,
                    output=deploy_result.output,
                    error=(
                        f"Readiness check failed: {readiness.summary}. "
                        f"Rollback: {rollback_info}"
                    ),
                )

        return deploy_result


def get_plan_steps(plan_name: str, project_root: Optional[str] = None) -> list[StepDef]:
    """Get step definitions for a plan.

    Loads from `.claude/cicd_tasks.yml` manifest if present,
    otherwise falls back to built-in plan definitions.
    """
    from pathlib import Path

    root = Path(project_root) if project_root else Path(".")

    # Try loading from manifest first
    try:
        from .manifest import get_manifest_plan_steps, load_manifest

        manifest = load_manifest(root)
        if manifest is not None and plan_name in manifest.plans:
            return get_manifest_plan_steps(manifest, plan_name)
    except (ImportError, ValueError):
        # Pydantic not installed or manifest invalid - fall back to built-in
        pass

    # Fall back to built-in plans
    if plan_name not in BUILTIN_PLANS:
        available = ", ".join(sorted(BUILTIN_PLANS.keys()))
        raise ValueError(f"Unknown plan: {plan_name}. Available: {available}")
    return BUILTIN_PLANS[plan_name]
