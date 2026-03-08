"""Step implementations for the deterministic CI/CD runner.

Each step type knows how to execute a specific kind of operation
(shell command, git operation, deploy) with timeout and retry support.
"""

from __future__ import annotations

import subprocess
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "command": self.command,
            "description": self.description,
            "timeout_seconds": self.timeout_seconds,
            "max_attempts": self.max_attempts,
            "idempotent": self.idempotent,
        }


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
        """Execute the shell command with timeout."""
        cwd = context.get("project_root")
        env = context.get("env")

        try:
            proc = subprocess.run(
                self.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=cwd,
                env=env,
            )

            if proc.returncode == 0:
                return StepResult(
                    status=StepStatus.SUCCESS,
                    exit_code=0,
                    output=proc.stdout,
                )
            else:
                return StepResult(
                    status=StepStatus.FAILED,
                    exit_code=proc.returncode,
                    output=proc.stdout,
                    error=proc.stderr,
                )

        except subprocess.TimeoutExpired as e:
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=124,  # standard timeout exit code
                output=e.stdout or "" if isinstance(e.stdout, str) else "",
                error=f"Step timed out after {self.timeout_seconds}s",
            )
        except OSError as e:
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=1,
                error=str(e),
            )

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
                'PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" '
                "python3 -m lib.security gate flow_finish"
            ),
            description="Run security quick scan",
            timeout_seconds=120,
            max_attempts=1,
            skip_if="! python3 -c 'import lib.security' 2>/dev/null",
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
            id="security_scan",
            command=(
                'PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" '
                "python3 -m lib.security gate flow_deploy"
            ),
            description="Run security scan before deploy",
            timeout_seconds=120,
            max_attempts=1,
            skip_if="! python3 -c 'import lib.security' 2>/dev/null",
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
