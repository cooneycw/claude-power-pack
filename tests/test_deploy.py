"""Unit tests for deployment strategies and readiness polling."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from lib.cicd.deploy.docker_compose import DockerComposeStrategy
from lib.cicd.deploy.strategy import (
    DeployConfig,
    ReadinessPolicy,
    ReadinessResult,
    get_strategy,
    poll_readiness,
    register_strategy,
)
from lib.cicd.state import StepStatus
from lib.cicd.steps import DeployStep, StepResult

# --- ReadinessPolicy tests ---


class TestReadinessPolicy:
    def test_defaults(self):
        policy = ReadinessPolicy(url="http://localhost:8080/health")
        assert policy.interval_seconds == 5.0
        assert policy.timeout_seconds == 120.0
        assert policy.consecutive_successes == 3
        assert policy.backoff_multiplier == 1.5
        assert policy.expected_status == 200

    def test_validate_ok(self):
        policy = ReadinessPolicy(url="http://localhost:8080/health")
        assert policy.validate() == []

    def test_validate_empty_url(self):
        policy = ReadinessPolicy(url="")
        errors = policy.validate()
        assert any("url" in e for e in errors)

    def test_validate_bad_interval(self):
        policy = ReadinessPolicy(url="http://localhost/health", interval_seconds=0)
        errors = policy.validate()
        assert any("interval" in e for e in errors)

    def test_validate_bad_consecutive(self):
        policy = ReadinessPolicy(url="http://localhost/health", consecutive_successes=0)
        errors = policy.validate()
        assert any("consecutive" in e for e in errors)

    def test_validate_bad_backoff(self):
        policy = ReadinessPolicy(url="http://localhost/health", backoff_multiplier=0.5)
        errors = policy.validate()
        assert any("backoff" in e for e in errors)


# --- DeployConfig tests ---


class TestDeployConfig:
    def test_defaults(self):
        config = DeployConfig()
        assert config.strategy == "docker_compose"
        assert config.compose_file == "docker-compose.yml"
        assert config.readiness is None
        assert config.profiles == []
        assert config.services == []

    def test_from_dict_basic(self):
        data = {
            "strategy": "docker_compose",
            "compose_file": "docker-compose.prod.yml",
            "profiles": ["core", "browser"],
        }
        config = DeployConfig.from_dict(data)
        assert config.strategy == "docker_compose"
        assert config.compose_file == "docker-compose.prod.yml"
        assert config.profiles == ["core", "browser"]

    def test_from_dict_with_readiness(self):
        data = {
            "strategy": "docker_compose",
            "readiness": {
                "url": "http://localhost:8080/health",
                "consecutive_successes": 5,
                "timeout_seconds": 60,
            },
        }
        config = DeployConfig.from_dict(data)
        assert config.readiness is not None
        assert config.readiness.url == "http://localhost:8080/health"
        assert config.readiness.consecutive_successes == 5
        assert config.readiness.timeout_seconds == 60

    def test_from_dict_extra_keys(self):
        data = {
            "strategy": "docker_compose",
            "custom_key": "custom_value",
        }
        config = DeployConfig.from_dict(data)
        assert config.extra == {"custom_key": "custom_value"}


# --- poll_readiness tests ---


class TestPollReadiness:
    @patch("lib.cicd.deploy.strategy.shutil.which", return_value=None)
    def test_no_curl(self, mock_which: MagicMock):
        policy = ReadinessPolicy(url="http://localhost/health")
        result = poll_readiness(policy)
        assert not result.ready
        assert "curl not found" in (result.last_error or "")

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("lib.cicd.deploy.strategy.subprocess.run")
    def test_immediate_success(self, mock_run: MagicMock, mock_which: MagicMock):
        """3 consecutive 200s should succeed."""
        mock_run.return_value = MagicMock(
            stdout="200",
            stderr="",
            returncode=0,
        )
        policy = ReadinessPolicy(
            url="http://localhost/health",
            consecutive_successes=3,
            interval_seconds=0.01,
            timeout_seconds=5,
        )
        sleeps: list[float] = []
        result = poll_readiness(policy, sleep_fn=lambda s: sleeps.append(s))
        assert result.ready
        assert result.consecutive_ok == 3
        assert result.attempts == 3

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("lib.cicd.deploy.strategy.subprocess.run")
    def test_intermittent_failures(self, mock_run: MagicMock, mock_which: MagicMock):
        """Failures reset consecutive count but don't stop polling."""
        # 200, 503, 200, 200, 200 -> should succeed on 5th attempt
        statuses = ["200", "503", "200", "200", "200"]
        returncodes = [0, 0, 0, 0, 0]
        mock_run.side_effect = [
            MagicMock(stdout=s, stderr="", returncode=r)
            for s, r in zip(statuses, returncodes)
        ]
        policy = ReadinessPolicy(
            url="http://localhost/health",
            consecutive_successes=3,
            interval_seconds=0.01,
            timeout_seconds=5,
            backoff_multiplier=1.0,  # no backoff for test
        )
        result = poll_readiness(policy, sleep_fn=lambda s: None)
        assert result.ready
        assert result.attempts == 5
        assert result.consecutive_ok == 3

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("lib.cicd.deploy.strategy.subprocess.run")
    @patch("lib.cicd.deploy.strategy.time.monotonic")
    def test_timeout(self, mock_time: MagicMock, mock_run: MagicMock, mock_which: MagicMock):
        """Should fail after timeout."""
        # Simulate time advancing past timeout
        call_count = [0]

        def advancing_time():
            call_count[0] += 1
            # Return increasing timestamps to eventually exceed timeout
            return call_count[0] * 10.0  # 10s per call

        mock_time.side_effect = advancing_time
        mock_run.return_value = MagicMock(stdout="503", stderr="", returncode=0)

        policy = ReadinessPolicy(
            url="http://localhost/health",
            timeout_seconds=5,
            interval_seconds=0.01,
        )
        result = poll_readiness(policy, sleep_fn=lambda s: None)
        assert not result.ready

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("lib.cicd.deploy.strategy.subprocess.run")
    def test_connection_refused(self, mock_run: MagicMock, mock_which: MagicMock):
        """OSError during curl should count as failure."""
        mock_run.side_effect = OSError("Connection refused")
        policy = ReadinessPolicy(
            url="http://localhost/health",
            timeout_seconds=0.05,
            interval_seconds=0.01,
            backoff_multiplier=1.0,
        )
        result = poll_readiness(policy, sleep_fn=lambda s: None)
        assert not result.ready
        assert "Connection refused" in (result.last_error or "")

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("lib.cicd.deploy.strategy.subprocess.run")
    def test_curl_timeout(self, mock_run: MagicMock, mock_which: MagicMock):
        """subprocess.TimeoutExpired should count as failure."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="curl", timeout=10)
        policy = ReadinessPolicy(
            url="http://localhost/health",
            timeout_seconds=0.05,
            interval_seconds=0.01,
            backoff_multiplier=1.0,
        )
        result = poll_readiness(policy, sleep_fn=lambda s: None)
        assert not result.ready
        assert "timed out" in (result.last_error or "").lower()

    def test_invalid_policy(self):
        """Invalid policy should return immediately."""
        policy = ReadinessPolicy(url="", timeout_seconds=0)
        result = poll_readiness(policy)
        assert not result.ready
        assert "Invalid policy" in (result.last_error or "")

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("lib.cicd.deploy.strategy.subprocess.run")
    def test_backoff_applied(self, mock_run: MagicMock, mock_which: MagicMock):
        """Sleep intervals should increase with backoff multiplier."""
        mock_run.return_value = MagicMock(stdout="503", stderr="", returncode=0)
        policy = ReadinessPolicy(
            url="http://localhost/health",
            timeout_seconds=0.1,
            interval_seconds=0.01,
            backoff_multiplier=2.0,
        )
        sleeps: list[float] = []
        poll_readiness(policy, sleep_fn=lambda s: sleeps.append(s))

        if len(sleeps) >= 2:
            # Second interval should be 2x the first
            assert sleeps[1] == pytest.approx(sleeps[0] * 2.0)


# --- ReadinessResult tests ---


class TestReadinessResult:
    def test_ready_summary(self):
        result = ReadinessResult(
            ready=True, attempts=5, consecutive_ok=3, elapsed_seconds=12.5
        )
        s = result.summary
        assert "Ready" in s
        assert "5 attempts" in s
        assert "3 consecutive OK" in s

    def test_not_ready_summary(self):
        result = ReadinessResult(
            ready=False, attempts=10, consecutive_ok=1,
            elapsed_seconds=120.0, last_error="Timeout exceeded",
        )
        s = result.summary
        assert "Not ready" in s
        assert "Timeout exceeded" in s


# --- Strategy registry tests ---


class TestStrategyRegistry:
    def test_docker_compose_registered(self):
        strategy = get_strategy("docker_compose")
        assert strategy.name == "docker_compose"
        assert isinstance(strategy, DockerComposeStrategy)

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown deployment strategy"):
            get_strategy("nonexistent_strategy")

    def test_register_custom(self):
        class CustomStrategy:
            name = "custom"
            def deploy(self, ctx: Any, config: Any) -> StepResult:
                return StepResult(status=StepStatus.SUCCESS)
            def rollback(self, ctx: Any, config: Any) -> StepResult:
                return StepResult(status=StepStatus.SUCCESS)
            def check_readiness(self, ctx: Any, config: Any) -> bool:
                return True

        register_strategy("custom", CustomStrategy)
        strategy = get_strategy("custom")
        assert strategy.name == "custom"


# --- DockerComposeStrategy tests ---


class TestDockerComposeStrategy:
    def test_compose_base_cmd_default(self):
        strategy = DockerComposeStrategy()
        config = DeployConfig()
        cmd = strategy._compose_base_cmd(config)
        assert cmd == ["docker", "compose", "-f", "docker-compose.yml"]

    def test_compose_base_cmd_with_profiles(self):
        strategy = DockerComposeStrategy()
        config = DeployConfig(profiles=["core", "browser"])
        cmd = strategy._compose_base_cmd(config)
        assert cmd == [
            "docker", "compose", "-f", "docker-compose.yml",
            "--profile", "core", "--profile", "browser",
        ]

    @patch("lib.cicd.deploy.docker_compose.subprocess.run")
    def test_deploy_custom_command(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            stdout="deployed", stderr="", returncode=0,
        )
        strategy = DockerComposeStrategy()
        config = DeployConfig(deploy_command="make deploy")
        result = strategy.deploy({"project_root": "/tmp"}, config)
        assert result.success
        mock_run.assert_called_once()
        # Should have been called with shell=True for custom command
        assert mock_run.call_args[1].get("shell") is True

    @patch("lib.cicd.deploy.docker_compose.subprocess.run")
    def test_rollback_custom_command(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            stdout="rolled back", stderr="", returncode=0,
        )
        strategy = DockerComposeStrategy()
        config = DeployConfig(rollback_command="docker compose down && docker compose up -d")
        result = strategy.rollback({"project_root": "/tmp"}, config)
        assert result.success

    @patch("lib.cicd.deploy.docker_compose.subprocess.run")
    def test_deploy_failure(self, mock_run: MagicMock):
        # Pull succeeds, up fails
        mock_run.side_effect = [
            MagicMock(stdout="pulled", stderr="", returncode=0),
            MagicMock(stdout="", stderr="error starting", returncode=1),
        ]
        strategy = DockerComposeStrategy()
        config = DeployConfig()
        result = strategy.deploy({"project_root": "/tmp"}, config)
        assert not result.success
        assert result.exit_code == 1

    @patch("lib.cicd.deploy.docker_compose.subprocess.run")
    def test_deploy_pull_failure(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            stdout="", stderr="pull failed", returncode=1,
        )
        strategy = DockerComposeStrategy()
        config = DeployConfig()
        result = strategy.deploy({"project_root": "/tmp"}, config)
        assert not result.success

    @patch("lib.cicd.deploy.docker_compose.subprocess.run")
    def test_deploy_timeout(self, mock_run: MagicMock):
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="docker compose up", timeout=900,
        )
        strategy = DockerComposeStrategy()
        config = DeployConfig()
        result = strategy.deploy({"project_root": "/tmp"}, config)
        assert not result.success
        assert result.exit_code == 124

    @patch("lib.cicd.deploy.docker_compose.subprocess.run")
    def test_check_readiness_running(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            stdout='{"Name":"svc","State":"running"}\n',
            stderr="",
            returncode=0,
        )
        strategy = DockerComposeStrategy()
        config = DeployConfig()
        assert strategy.check_readiness({"project_root": "/tmp"}, config) is True

    @patch("lib.cicd.deploy.docker_compose.subprocess.run")
    def test_check_readiness_not_running(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            stdout='{"Name":"svc","State":"exited"}\n',
            stderr="",
            returncode=0,
        )
        strategy = DockerComposeStrategy()
        config = DeployConfig()
        assert strategy.check_readiness({"project_root": "/tmp"}, config) is False


# --- DeployStep tests ---


class TestDeployStep:
    @patch("lib.cicd.deploy.docker_compose.subprocess.run")
    def test_deploy_without_readiness(self, mock_run: MagicMock):
        """Deploy succeeds without readiness config."""
        mock_run.return_value = MagicMock(
            stdout="ok", stderr="", returncode=0,
        )
        config = DeployConfig(readiness=None)
        step = DeployStep(config)
        result = step.execute({"project_root": "/tmp"})
        assert result.success

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("lib.cicd.deploy.strategy.subprocess.run")
    @patch("lib.cicd.deploy.docker_compose.subprocess.run")
    def test_deploy_with_readiness_success(
        self, mock_compose_run: MagicMock, mock_curl_run: MagicMock,
        mock_which: MagicMock,
    ):
        """Deploy + readiness both succeed."""
        # compose pull + up succeed
        mock_compose_run.return_value = MagicMock(
            stdout="ok", stderr="", returncode=0,
        )
        # curl returns 200
        mock_curl_run.return_value = MagicMock(
            stdout="200", stderr="", returncode=0,
        )
        config = DeployConfig(
            readiness=ReadinessPolicy(
                url="http://localhost:8080/health",
                consecutive_successes=2,
                interval_seconds=0.01,
                timeout_seconds=5,
            ),
        )
        step = DeployStep(config)
        result = step.execute({"project_root": "/tmp"})
        assert result.success

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("lib.cicd.deploy.strategy.subprocess.run")
    @patch("lib.cicd.deploy.docker_compose.subprocess.run")
    @patch("lib.cicd.deploy.strategy.time.monotonic")
    def test_deploy_readiness_fails_triggers_rollback(
        self, mock_time: MagicMock, mock_compose_run: MagicMock,
        mock_curl_run: MagicMock, mock_which: MagicMock,
    ):
        """Readiness failure triggers automatic rollback."""
        # Simulate time advancing past timeout
        call_count = [0]
        def advancing_time():
            call_count[0] += 1
            return call_count[0] * 10.0
        mock_time.side_effect = advancing_time

        # compose commands succeed (deploy + rollback)
        mock_compose_run.return_value = MagicMock(
            stdout="ok", stderr="", returncode=0,
        )
        # curl always returns 503
        mock_curl_run.return_value = MagicMock(
            stdout="503", stderr="", returncode=0,
        )

        config = DeployConfig(
            readiness=ReadinessPolicy(
                url="http://localhost:8080/health",
                timeout_seconds=5,
                interval_seconds=0.01,
            ),
        )
        step = DeployStep(config)
        result = step.execute({"project_root": "/tmp"})

        assert not result.success
        assert "Readiness check failed" in result.error
        assert "rollback succeeded" in result.error

    def test_deploy_step_from_dict(self):
        """DeployStep can be created from a dict config."""
        config_dict = {
            "strategy": "docker_compose",
            "compose_file": "docker-compose.yml",
            "profiles": ["core"],
        }
        step = DeployStep(config_dict)
        assert step.config.strategy == "docker_compose"
        assert step.config.profiles == ["core"]
        assert step.id == "deploy"
        assert step.idempotent is False
