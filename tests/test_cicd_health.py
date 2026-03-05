"""Tests for lib/cicd/health.py and lib/cicd/smoke.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from lib.cicd.config import CICDConfig, HealthEndpoint, ProcessCheck, SmokeTest
from lib.cicd.health import check_endpoint, check_process, run_health_checks
from lib.cicd.models import HealthCheckEntry, HealthCheckResult, SmokeTestEntry, SmokeTestResult
from lib.cicd.smoke import run_single_test, run_smoke_tests


class TestHealthCheckModels:
    """Test HealthCheckResult and HealthCheckEntry."""

    def test_empty_result(self) -> None:
        result = HealthCheckResult()
        assert result.total == 0
        assert result.passed == 0
        assert result.failed == 0
        assert not result.all_passed
        assert "no checks configured" in result.summary_line()

    def test_all_passed(self) -> None:
        result = HealthCheckResult(
            checks=[
                HealthCheckEntry(name="api", kind="endpoint", passed=True),
                HealthCheckEntry(name="db", kind="process", passed=True),
            ]
        )
        assert result.total == 2
        assert result.passed == 2
        assert result.failed == 0
        assert result.all_passed
        assert "2/2" in result.summary_line()

    def test_some_failed(self) -> None:
        result = HealthCheckResult(
            checks=[
                HealthCheckEntry(name="api", kind="endpoint", passed=True),
                HealthCheckEntry(name="db", kind="process", passed=False),
            ]
        )
        assert result.total == 2
        assert result.passed == 1
        assert result.failed == 1
        assert not result.all_passed
        assert "FAILED" in result.summary_line()

    def test_to_dict(self) -> None:
        entry = HealthCheckEntry(
            name="api", kind="endpoint", passed=True, detail="HTTP 200", elapsed_ms=42.5
        )
        d = entry.to_dict()
        assert d["name"] == "api"
        assert d["kind"] == "endpoint"
        assert d["passed"] is True
        assert d["elapsed_ms"] == 42.5


class TestCheckEndpoint:
    """Test check_endpoint function."""

    @patch("lib.cicd.health.shutil.which")
    def test_curl_not_found(self, mock_which: MagicMock) -> None:
        mock_which.return_value = None
        endpoint = HealthEndpoint(url="http://localhost:8080/health")
        result = check_endpoint(endpoint)
        assert not result.passed
        assert "curl not found" in result.detail

    @patch("lib.cicd.health.subprocess.run")
    @patch("lib.cicd.health.shutil.which")
    def test_successful_check(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        mock_run.return_value = MagicMock(
            stdout='{"status":"ok"}\n200',
            stderr="",
            returncode=0,
        )
        endpoint = HealthEndpoint(url="http://localhost:8080/health")
        result = check_endpoint(endpoint)
        assert result.passed
        assert "200" in result.detail

    @patch("lib.cicd.health.subprocess.run")
    @patch("lib.cicd.health.shutil.which")
    def test_wrong_status_code(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        mock_run.return_value = MagicMock(
            stdout="\n500",
            stderr="",
            returncode=0,
        )
        endpoint = HealthEndpoint(url="http://localhost:8080/health", expected_status=200)
        result = check_endpoint(endpoint)
        assert not result.passed
        assert "500" in result.detail

    @patch("lib.cicd.health.subprocess.run")
    @patch("lib.cicd.health.shutil.which")
    def test_expected_body_missing(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        mock_run.return_value = MagicMock(
            stdout='{"status":"error"}\n200',
            stderr="",
            returncode=0,
        )
        endpoint = HealthEndpoint(
            url="http://localhost:8080/health",
            expected_body="ok",
        )
        result = check_endpoint(endpoint)
        assert not result.passed
        assert "missing expected content" in result.detail

    @patch("lib.cicd.health.subprocess.run")
    @patch("lib.cicd.health.shutil.which")
    def test_connection_refused(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/curl"
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="curl: (7) Failed to connect",
            returncode=7,
        )
        endpoint = HealthEndpoint(url="http://localhost:9999/health")
        result = check_endpoint(endpoint)
        assert not result.passed
        assert "Failed to connect" in result.detail

    @patch("lib.cicd.health.subprocess.run")
    @patch("lib.cicd.health.shutil.which")
    def test_timeout(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        import subprocess

        mock_which.return_value = "/usr/bin/curl"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="curl", timeout=5)
        endpoint = HealthEndpoint(url="http://localhost:8080/health", timeout=5)
        result = check_endpoint(endpoint)
        assert not result.passed
        assert "Timeout" in result.detail


class TestCheckProcess:
    """Test check_process function."""

    @patch("lib.cicd.health.shutil.which")
    def test_no_tools_available(self, mock_which: MagicMock) -> None:
        mock_which.return_value = None
        process = ProcessCheck(name="uvicorn", port=8000)
        result = check_process(process)
        assert not result.passed
        assert "Neither ss nor lsof" in result.detail

    @patch("lib.cicd.health.subprocess.run")
    @patch("lib.cicd.health.shutil.which")
    def test_process_found_via_ss(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/ss"
        mock_run.return_value = MagicMock(
            stdout="LISTEN  0  128  *:8000  *:*  users:((\"uvicorn\",pid=1234))\n",
            returncode=0,
        )
        process = ProcessCheck(name="uvicorn", port=8000)
        result = check_process(process)
        assert result.passed
        assert "Listening" in result.detail

    @patch("lib.cicd.health.subprocess.run")
    @patch("lib.cicd.health.shutil.which")
    def test_process_not_found(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/ss"
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        process = ProcessCheck(name="uvicorn", port=8000)
        result = check_process(process)
        assert not result.passed
        assert "Nothing listening" in result.detail


class TestRunHealthChecks:
    """Test run_health_checks orchestrator."""

    def test_no_config(self) -> None:
        config = CICDConfig()
        result = run_health_checks(config=config)
        assert result.total == 0
        assert "no checks configured" in result.summary_line()

    @patch("lib.cicd.health.check_endpoint")
    @patch("lib.cicd.health.check_process")
    def test_with_endpoints_and_processes(
        self, mock_proc: MagicMock, mock_ep: MagicMock
    ) -> None:
        mock_ep.return_value = HealthCheckEntry(
            name="api", kind="endpoint", passed=True
        )
        mock_proc.return_value = HealthCheckEntry(
            name="db", kind="process", passed=True
        )
        config = CICDConfig()
        config.health.endpoints = [
            HealthEndpoint(url="http://localhost:8000/health")
        ]
        config.health.processes = [ProcessCheck(name="postgres", port=5432)]
        result = run_health_checks(config=config)
        assert result.total == 2
        assert result.all_passed


class TestSmokeTestModels:
    """Test SmokeTestResult and SmokeTestEntry."""

    def test_empty_result(self) -> None:
        result = SmokeTestResult()
        assert result.total == 0
        assert "no tests configured" in result.summary_line()

    def test_all_passed(self) -> None:
        result = SmokeTestResult(
            tests=[
                SmokeTestEntry(name="curl test", command="curl -sf ...", passed=True),
            ]
        )
        assert result.all_passed
        assert "1/1" in result.summary_line()

    def test_to_dict(self) -> None:
        entry = SmokeTestEntry(
            name="test", command="echo ok", passed=True, exit_code=0,
            output="ok", detail="exit 0", elapsed_ms=10.2,
        )
        d = entry.to_dict()
        assert d["name"] == "test"
        assert d["passed"] is True
        assert d["exit_code"] == 0


class TestRunSingleTest:
    """Test run_single_test function."""

    @patch("lib.cicd.smoke.subprocess.run")
    def test_successful_test(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="ok\n", stderr="", returncode=0,
        )
        test = SmokeTest(name="echo test", command="echo ok")
        result = run_single_test(test)
        assert result.passed
        assert result.exit_code == 0

    @patch("lib.cicd.smoke.subprocess.run")
    def test_failed_exit_code(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="", stderr="error", returncode=1,
        )
        test = SmokeTest(name="fail test", command="false")
        result = run_single_test(test)
        assert not result.passed
        assert "exit 1" in result.detail

    @patch("lib.cicd.smoke.subprocess.run")
    def test_expected_output_missing(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="wrong output\n", stderr="", returncode=0,
        )
        test = SmokeTest(name="output test", command="echo wrong", expected_output="expected")
        result = run_single_test(test)
        assert not result.passed
        assert "output missing" in result.detail

    @patch("lib.cicd.smoke.subprocess.run")
    def test_timeout(self, mock_run: MagicMock) -> None:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep", timeout=10)
        test = SmokeTest(name="timeout test", command="sleep 100", timeout=10)
        result = run_single_test(test)
        assert not result.passed
        assert "Timeout" in result.detail


class TestRunSmokeTests:
    """Test run_smoke_tests orchestrator."""

    def test_no_config(self) -> None:
        config = CICDConfig()
        result = run_smoke_tests(config=config)
        assert result.total == 0

    @patch("lib.cicd.smoke.run_single_test")
    def test_with_tests(self, mock_run: MagicMock) -> None:
        mock_run.return_value = SmokeTestEntry(
            name="test", command="echo ok", passed=True,
        )
        config = CICDConfig()
        config.health.smoke_tests = [
            SmokeTest(name="test", command="echo ok"),
        ]
        result = run_smoke_tests(config=config)
        assert result.total == 1
        assert result.all_passed
