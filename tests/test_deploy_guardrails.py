"""Unit tests for deployment guardrails."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.cicd.deploy.guardrails import (
    CapabilityCheck,
    CapabilityResult,
    check_docker_socket,
    check_stale_commit,
    deploy_lock,
    run_capability_checks,
    safe_docker_prune,
)
from lib.cicd.deploy.strategy import DeployConfig, ReadinessPolicy, poll_readiness


class TestCapabilityCheck:
    def test_passing_check(self):
        check = CapabilityCheck(name="echo-test", command="echo ok")
        result = check.run()
        assert result.passed
        assert result.output == "ok"

    def test_failing_check(self):
        check = CapabilityCheck(name="fail-test", command="exit 1")
        result = check.run()
        assert not result.passed

    def test_timeout(self):
        check = CapabilityCheck(
            name="slow-test", command="sleep 10", timeout_seconds=1
        )
        result = check.run()
        assert not result.passed
        assert "Timed out" in result.error

    def test_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            check = CapabilityCheck(name="pwd-test", command="pwd")
            result = check.run(cwd=tmpdir)
            assert result.passed
            assert tmpdir in result.output


class TestRunCapabilityChecks:
    def test_empty_checks(self):
        ok, results = run_capability_checks([])
        assert ok
        assert results == []

    def test_all_pass(self):
        checks = [
            CapabilityCheck(name="a", command="true"),
            CapabilityCheck(name="b", command="echo hello"),
        ]
        ok, results = run_capability_checks(checks)
        assert ok
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_one_fails(self):
        checks = [
            CapabilityCheck(name="a", command="true"),
            CapabilityCheck(name="b", command="false"),
        ]
        ok, results = run_capability_checks(checks)
        assert not ok
        assert results[0].passed
        assert not results[1].passed


class TestCheckStaleCommit:
    @patch("lib.cicd.deploy.guardrails.shutil.which", return_value=None)
    def test_no_git(self, mock_which: MagicMock):
        result = check_stale_commit()
        assert not result.success
        assert "git not found" in result.error

    @patch("lib.cicd.deploy.guardrails.shutil.which", return_value="/usr/bin/git")
    @patch("lib.cicd.deploy.guardrails.subprocess.run")
    def test_matching_commits(self, mock_run: MagicMock, mock_which: MagicMock):
        sha = "abc123def456"
        mock_run.side_effect = [
            MagicMock(returncode=0),  # fetch
            MagicMock(stdout=f"{sha}\n", returncode=0),  # local rev-parse
            MagicMock(stdout=f"{sha}\n", returncode=0),  # remote rev-parse
        ]
        result = check_stale_commit()
        assert result.success
        assert sha[:12] in result.output

    @patch("lib.cicd.deploy.guardrails.shutil.which", return_value="/usr/bin/git")
    @patch("lib.cicd.deploy.guardrails.subprocess.run")
    def test_stale_commit(self, mock_run: MagicMock, mock_which: MagicMock):
        mock_run.side_effect = [
            MagicMock(returncode=0),  # fetch
            MagicMock(stdout="aaa111\n", returncode=0),  # local
            MagicMock(stdout="bbb222\n", returncode=0),  # remote
        ]
        result = check_stale_commit()
        assert not result.success
        assert "Stale commit" in result.error

    @patch("lib.cicd.deploy.guardrails.shutil.which", return_value="/usr/bin/git")
    @patch("lib.cicd.deploy.guardrails.subprocess.run")
    def test_fetch_timeout(self, mock_run: MagicMock, mock_which: MagicMock):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git fetch", timeout=30)
        result = check_stale_commit()
        assert not result.success
        assert "fetch" in result.error.lower()


class TestDeployLock:
    def test_acquire_and_release(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.lock"
            with deploy_lock(lock_path=lock_path, timeout_seconds=5):
                assert lock_path.exists()

    def test_reentrant_fails(self):
        """A second lock attempt should time out if the first is held."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.lock"
            with deploy_lock(lock_path=lock_path, timeout_seconds=5):
                with pytest.raises(TimeoutError, match="Could not acquire"):
                    with deploy_lock(lock_path=lock_path, timeout_seconds=1):
                        pass  # pragma: no cover


class TestCheckDockerSocket:
    @patch("lib.cicd.deploy.guardrails.os.path.exists", return_value=False)
    def test_missing_socket(self, mock_exists: MagicMock):
        result = check_docker_socket()
        assert not result.success
        assert "not found" in result.error

    @patch("lib.cicd.deploy.guardrails.os.access", return_value=False)
    @patch("lib.cicd.deploy.guardrails.os.path.exists", return_value=True)
    def test_no_access(self, mock_exists: MagicMock, mock_access: MagicMock):
        result = check_docker_socket()
        assert not result.success
        assert "not accessible" in result.error

    @patch("lib.cicd.deploy.guardrails.os.access", return_value=True)
    @patch("lib.cicd.deploy.guardrails.os.path.exists", return_value=True)
    def test_accessible(self, mock_exists: MagicMock, mock_access: MagicMock):
        result = check_docker_socket()
        assert result.success


class TestSafeDockerPrune:
    @patch("lib.cicd.deploy.guardrails.shutil.which", return_value=None)
    def test_no_docker(self, mock_which: MagicMock):
        result = safe_docker_prune()
        assert not result.success
        assert "docker not found" in result.error

    @patch("lib.cicd.deploy.guardrails.shutil.which", return_value="/usr/bin/docker")
    @patch("lib.cicd.deploy.guardrails.subprocess.run")
    def test_successful_prune(self, mock_run: MagicMock, mock_which: MagicMock):
        mock_run.return_value = MagicMock(
            stdout="Deleted: sha256:abc", returncode=0
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.lock"
            result = safe_docker_prune(lock_path=lock_path)
            assert result.success


class TestDeployConfigGuardrails:
    def test_default_guardrails_off(self):
        config = DeployConfig()
        assert config.use_deploy_lock is False
        assert config.stale_commit_check is False
        assert config.safe_prune is False

    def test_from_dict_with_guardrails(self):
        data = {
            "strategy": "docker_compose",
            "use_deploy_lock": True,
            "stale_commit_check": True,
            "safe_prune": True,
        }
        config = DeployConfig.from_dict(data)
        assert config.use_deploy_lock is True
        assert config.stale_commit_check is True
        assert config.safe_prune is True


class TestReadinessPolicyCapabilityChecks:
    def test_default_no_capability_checks(self):
        policy = ReadinessPolicy(url="http://localhost/health")
        assert policy.capability_checks == []

    def test_capability_checks_in_policy(self):
        policy = ReadinessPolicy(
            url="http://localhost/health",
            capability_checks=[
                {"name": "secrets-loaded", "command": "curl -sf http://localhost/ready"},
            ],
        )
        assert len(policy.capability_checks) == 1

    @patch("lib.cicd.deploy.strategy.shutil.which", return_value="/usr/bin/curl")
    @patch("lib.cicd.deploy.strategy.subprocess.run")
    def test_capability_check_blocks_readiness(
        self, mock_run: MagicMock, mock_which: MagicMock
    ):
        """HTTP readiness passes but capability check fails -> not ready."""
        mock_run.return_value = MagicMock(stdout="200", stderr="", returncode=0)

        mock_cap_result = CapabilityResult(name="always-fail", passed=False, error="failed")
        with patch(
            "lib.cicd.deploy.guardrails.run_capability_checks",
            return_value=(False, [mock_cap_result]),
        ):
            policy = ReadinessPolicy(
                url="http://localhost/health",
                consecutive_successes=1,
                interval_seconds=0.01,
                timeout_seconds=2,
                backoff_multiplier=1.0,
                capability_checks=[
                    {"name": "always-fail", "command": "false"},
                ],
            )
            result = poll_readiness(policy, sleep_fn=lambda s: None)
        assert not result.ready
        assert result.last_error is not None
        assert "Capability" in result.last_error
