"""Docker Compose deployment strategy.

Handles deploy, rollback, and readiness checking for services
managed by docker compose. This is the primary deployment strategy
for Claude Power Pack MCP servers.
"""

from __future__ import annotations

import subprocess
from typing import Any

from ..state import StepStatus
from ..steps import StepResult
from .strategy import DeployConfig, register_strategy


class DockerComposeStrategy:
    """Deploy via docker compose with optional profiles and services."""

    name = "docker_compose"

    def _compose_base_cmd(self, config: DeployConfig) -> list[str]:
        """Build the base docker compose command with file and profiles."""
        cmd = ["docker", "compose", "-f", config.compose_file]
        for profile in config.profiles:
            cmd.extend(["--profile", profile])
        return cmd

    def deploy(self, context: dict[str, Any], config: DeployConfig) -> StepResult:
        """Pull images and start/restart services.

        Uses `docker compose up -d` with optional profiles and services.
        If a custom deploy_command is set in config, uses that instead.
        """
        cwd = context.get("project_root")
        env = context.get("env")

        if config.deploy_command:
            return self._run_shell(config.deploy_command, cwd=cwd, env=env,
                                   timeout=config.timeout_seconds)

        base = self._compose_base_cmd(config)
        # Pull first, then up
        pull_cmd = base + ["pull"]
        if config.services:
            pull_cmd.extend(config.services)

        pull_result = self._run_cmd(pull_cmd, cwd=cwd, env=env, timeout=300)
        if not pull_result.success:
            return pull_result

        up_cmd = base + ["up", "-d", "--remove-orphans"]
        if config.services:
            up_cmd.extend(config.services)

        return self._run_cmd(up_cmd, cwd=cwd, env=env,
                             timeout=config.timeout_seconds)

    def rollback(self, context: dict[str, Any], config: DeployConfig) -> StepResult:
        """Roll back by stopping and restarting services.

        If a custom rollback_command is set, uses that instead.
        Default: docker compose down + up (forces fresh start).
        """
        cwd = context.get("project_root")
        env = context.get("env")

        if config.rollback_command:
            return self._run_shell(config.rollback_command, cwd=cwd, env=env,
                                   timeout=config.timeout_seconds)

        base = self._compose_base_cmd(config)

        # Down first
        down_cmd = base + ["down"]
        if config.services:
            down_cmd.extend(config.services)
        down_result = self._run_cmd(down_cmd, cwd=cwd, env=env, timeout=120)
        if not down_result.success:
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=down_result.exit_code,
                output=down_result.output,
                error=f"Rollback failed during 'down': {down_result.error}",
            )

        # Up again
        up_cmd = base + ["up", "-d"]
        if config.services:
            up_cmd.extend(config.services)
        return self._run_cmd(up_cmd, cwd=cwd, env=env,
                             timeout=config.timeout_seconds)

    def check_readiness(self, context: dict[str, Any], config: DeployConfig) -> bool:
        """Check if all target services are running and healthy.

        Uses `docker compose ps` to verify service status.
        """
        cwd = context.get("project_root")
        env = context.get("env")

        base = self._compose_base_cmd(config)
        ps_cmd = base + ["ps", "--format", "json"]
        if config.services:
            ps_cmd.extend(config.services)

        try:
            proc = subprocess.run(
                ps_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=cwd,
                env=env,
            )
            if proc.returncode != 0:
                return False

            # docker compose ps --format json outputs one JSON object per line
            # Check that all services are "running"
            output = proc.stdout.strip()
            if not output:
                return False

            import json
            for line in output.splitlines():
                try:
                    svc = json.loads(line)
                    state = svc.get("State", "").lower()
                    if state != "running":
                        return False
                except (json.JSONDecodeError, AttributeError):
                    return False

            return True

        except (subprocess.TimeoutExpired, OSError):
            return False

    def _run_cmd(
        self,
        cmd: list[str],
        cwd: Any = None,
        env: Any = None,
        timeout: int = 600,
    ) -> StepResult:
        """Run a command list and return StepResult."""
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
            )
            if proc.returncode == 0:
                return StepResult(
                    status=StepStatus.SUCCESS,
                    exit_code=0,
                    output=proc.stdout,
                )
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=proc.returncode,
                output=proc.stdout,
                error=proc.stderr,
            )
        except subprocess.TimeoutExpired as e:
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=124,
                output=e.stdout or "" if isinstance(e.stdout, str) else "",
                error=f"Command timed out after {timeout}s",
            )
        except OSError as e:
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=1,
                error=str(e),
            )

    def _run_shell(
        self,
        command: str,
        cwd: Any = None,
        env: Any = None,
        timeout: int = 600,
    ) -> StepResult:
        """Run a shell command string and return StepResult."""
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
            )
            if proc.returncode == 0:
                return StepResult(
                    status=StepStatus.SUCCESS,
                    exit_code=0,
                    output=proc.stdout,
                )
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=proc.returncode,
                output=proc.stdout,
                error=proc.stderr,
            )
        except subprocess.TimeoutExpired as e:
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=124,
                output=e.stdout or "" if isinstance(e.stdout, str) else "",
                error=f"Command timed out after {timeout}s",
            )
        except OSError as e:
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=1,
                error=str(e),
            )


# Auto-register on import
register_strategy("docker_compose", DockerComposeStrategy)
