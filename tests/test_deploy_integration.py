"""Integration tests for deploy + readiness gate + rollback scenarios.

These tests verify the full flow through DeployStep using the
DockerComposeStrategy with mocked subprocess calls to simulate
real deployment scenarios.

Note: Both docker_compose.py and strategy.py import subprocess, but Python
shares a single module object. We mock subprocess.run once and use
command-aware side_effect routing for integration tests that need both
compose and curl behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from lib.cicd.deploy.strategy import (
    DeployConfig,
    ReadinessPolicy,
    register_strategy,
)
from lib.cicd.state import StepStatus
from lib.cicd.steps import DeployStep, StepResult


def _is_curl_cmd(args: Any) -> bool:
    """Check if a subprocess call is a curl command."""
    if isinstance(args, list):
        return len(args) > 0 and "curl" in str(args[0])
    if isinstance(args, str):
        return "curl" in args
    return False


class TestDeployReadinessRollbackFlow:
    """Full deploy -> readiness -> rollback integration tests."""

    def _make_context(self, tmp_path: Path) -> dict[str, Any]:
        return {"project_root": str(tmp_path)}

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("subprocess.run")
    def test_full_success_flow(
        self, mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path,
    ):
        """Deploy succeeds, readiness passes -> overall success."""
        compose_calls = []

        def route_cmd(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if _is_curl_cmd(cmd):
                return MagicMock(stdout="200", stderr="", returncode=0)
            compose_calls.append(cmd)
            return MagicMock(stdout="ok", stderr="", returncode=0)

        mock_run.side_effect = route_cmd

        config = DeployConfig(
            readiness=ReadinessPolicy(
                url="http://localhost:8080/health",
                consecutive_successes=2,
                interval_seconds=0.01,
                timeout_seconds=5,
            ),
        )
        step = DeployStep(config)
        result = step.execute(self._make_context(tmp_path))

        assert result.success
        assert result.status == StepStatus.SUCCESS
        # compose should have been called for pull + up
        assert len(compose_calls) == 2

    @patch("subprocess.run")
    def test_deploy_fails_no_rollback(
        self, mock_run: MagicMock, tmp_path: Path,
    ):
        """If deploy itself fails, no rollback is attempted."""
        call_log = []

        def route_cmd(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            call_log.append(cmd)
            return MagicMock(stdout="", stderr="pull failed: auth error", returncode=1)

        mock_run.side_effect = route_cmd

        config = DeployConfig()
        step = DeployStep(config)
        result = step.execute(self._make_context(tmp_path))

        assert not result.success
        # Only pull was called, no rollback
        assert len(call_log) == 1

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("subprocess.run")
    @patch("lib.cicd.deploy.strategy.time.monotonic")
    def test_readiness_timeout_triggers_rollback(
        self, mock_time: MagicMock, mock_run: MagicMock,
        mock_which: MagicMock, tmp_path: Path,
    ):
        """Readiness timeout triggers rollback via strategy."""
        call_count = [0]

        def advancing_time():
            call_count[0] += 1
            return call_count[0] * 10.0

        mock_time.side_effect = advancing_time

        compose_calls = []

        def route_cmd(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if _is_curl_cmd(cmd):
                return MagicMock(stdout="503", stderr="", returncode=0)
            compose_calls.append(cmd)
            return MagicMock(stdout="ok", stderr="", returncode=0)

        mock_run.side_effect = route_cmd

        config = DeployConfig(
            readiness=ReadinessPolicy(
                url="http://localhost:8080/health",
                timeout_seconds=5,
                interval_seconds=0.01,
            ),
        )
        step = DeployStep(config)
        result = step.execute(self._make_context(tmp_path))

        assert not result.success
        assert "Readiness check failed" in result.error
        assert "rollback succeeded" in result.error
        # compose called: pull + up (deploy) + down + up (rollback) = 4
        assert len(compose_calls) == 4

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("subprocess.run")
    @patch("lib.cicd.deploy.strategy.time.monotonic")
    def test_readiness_fails_rollback_also_fails(
        self, mock_time: MagicMock, mock_run: MagicMock,
        mock_which: MagicMock, tmp_path: Path,
    ):
        """When both readiness and rollback fail, error includes both."""
        time_count = [0]

        def advancing_time():
            time_count[0] += 1
            return time_count[0] * 10.0

        mock_time.side_effect = advancing_time

        compose_calls = [0]

        def route_cmd(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if _is_curl_cmd(cmd):
                return MagicMock(stdout="503", stderr="", returncode=0)
            compose_calls[0] += 1
            # First 2 compose calls (pull + up) succeed, 3rd (down for rollback) fails
            if compose_calls[0] <= 2:
                return MagicMock(stdout="ok", stderr="", returncode=0)
            return MagicMock(stdout="", stderr="rollback error", returncode=1)

        mock_run.side_effect = route_cmd

        config = DeployConfig(
            readiness=ReadinessPolicy(
                url="http://localhost:8080/health",
                timeout_seconds=5,
                interval_seconds=0.01,
            ),
        )
        step = DeployStep(config)
        result = step.execute(self._make_context(tmp_path))

        assert not result.success
        assert "rollback also failed" in result.error

    @patch("subprocess.run")
    def test_deploy_with_profiles_and_services(
        self, mock_run: MagicMock, tmp_path: Path,
    ):
        """Profiles and services are passed to docker compose commands."""
        call_log = []

        def route_cmd(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            call_log.append(cmd)
            return MagicMock(stdout="ok", stderr="", returncode=0)

        mock_run.side_effect = route_cmd

        config = DeployConfig(
            profiles=["core", "browser"],
            services=["second-opinion", "playwright"],
        )
        step = DeployStep(config)
        result = step.execute(self._make_context(tmp_path))

        assert result.success
        # Check that profiles were included in the pull command
        pull_cmd = call_log[0]
        assert "--profile" in pull_cmd
        assert "core" in pull_cmd
        assert "browser" in pull_cmd
        assert "second-opinion" in pull_cmd

    @patch("subprocess.run")
    def test_deploy_with_custom_commands(
        self, mock_run: MagicMock, tmp_path: Path,
    ):
        """Custom deploy/rollback commands are used when specified."""
        mock_run.return_value = MagicMock(
            stdout="ok", stderr="", returncode=0,
        )

        config = DeployConfig(
            deploy_command="make deploy-prod",
        )
        step = DeployStep(config)
        result = step.execute(self._make_context(tmp_path))

        assert result.success
        # Should use shell=True for custom command
        assert mock_run.call_count == 1
        assert mock_run.call_args[1].get("shell") is True

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("subprocess.run")
    def test_readiness_recovers_after_initial_failures(
        self, mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path,
    ):
        """Service starts slow but eventually becomes ready."""
        curl_call_count = [0]
        # First 3 curl calls fail, then 3 succeed
        curl_responses = [
            OSError("Connection refused"),
            OSError("Connection refused"),
            OSError("Connection refused"),
            MagicMock(stdout="200", stderr="", returncode=0),
            MagicMock(stdout="200", stderr="", returncode=0),
            MagicMock(stdout="200", stderr="", returncode=0),
        ]

        def route_cmd(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if _is_curl_cmd(cmd):
                idx = curl_call_count[0]
                curl_call_count[0] += 1
                resp = curl_responses[idx]
                if isinstance(resp, Exception):
                    raise resp
                return resp
            return MagicMock(stdout="ok", stderr="", returncode=0)

        mock_run.side_effect = route_cmd

        config = DeployConfig(
            readiness=ReadinessPolicy(
                url="http://localhost:8080/health",
                consecutive_successes=3,
                interval_seconds=0.01,
                timeout_seconds=10,
                backoff_multiplier=1.0,
            ),
        )
        step = DeployStep(config)
        result = step.execute(self._make_context(tmp_path))

        assert result.success

    def test_no_readiness_config_skips_gate(self, tmp_path: Path):
        """Without readiness config, deploy result is returned directly."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="deployed ok", stderr="", returncode=0,
            )

            config = DeployConfig(readiness=None)
            step = DeployStep(config)
            result = step.execute(self._make_context(tmp_path))

            assert result.success
            assert result.output == "deployed ok"


class TestCustomStrategyIntegration:
    """Test that custom strategies work with DeployStep."""

    def test_custom_strategy_full_flow(self, tmp_path: Path):
        """Register and use a custom strategy through DeployStep."""
        deploy_called = False
        readiness_count = [0]

        class MockStrategy:
            name = "mock_test"

            def deploy(self, ctx: dict[str, Any], config: DeployConfig) -> StepResult:
                nonlocal deploy_called
                deploy_called = True
                return StepResult(status=StepStatus.SUCCESS, output="mock deployed")

            def rollback(self, ctx: dict[str, Any], config: DeployConfig) -> StepResult:
                return StepResult(status=StepStatus.SUCCESS)

            def check_readiness(self, ctx: dict[str, Any], config: DeployConfig) -> bool:
                readiness_count[0] += 1
                return readiness_count[0] >= 3

        register_strategy("mock_test", MockStrategy)

        config = DeployConfig(strategy="mock_test")
        step = DeployStep(config)
        result = step.execute({"project_root": str(tmp_path)})

        assert result.success
        assert deploy_called
