"""Tests for CI/CD failure pattern analysis."""

import json
from pathlib import Path

import pytest

from lib.cicd.failure_patterns import (
    PatternReport,
    analyze_failure_patterns,
    classify_error,
)


class TestClassifyError:
    def test_shell_compat(self):
        assert classify_error("syntax error near unexpected token `('") == "shell-compat"
        assert classify_error("bash: not found") == "shell-compat"

    def test_implicit_detection(self):
        assert classify_error("fatal: not a git repository") == "implicit-detection"
        assert classify_error("command not found: jq") == "implicit-detection"

    def test_config_drift(self):
        assert classify_error("environment variable DATABASE_URL not set") == "config-drift"
        assert classify_error("missing config file: app.yml") == "config-drift"

    def test_auth_bootstrap(self):
        assert classify_error("permission denied (publickey)") == "auth-bootstrap"
        assert classify_error("unauthorized: token expired") == "auth-bootstrap"
        assert classify_error("credential not found for registry") == "auth-bootstrap"

    def test_dependency_missing(self):
        assert classify_error("ModuleNotFoundError: No module named 'boto3'") == "dependency-missing"
        assert classify_error("ImportError: cannot import name 'foo'") == "dependency-missing"

    def test_resource_contention(self):
        assert classify_error("OSError: [Errno 98] Address already in use") == "resource-contention"
        assert classify_error("lock is held by another process") == "resource-contention"

    def test_unrecognized(self):
        assert classify_error("something totally unrelated happened") is None
        assert classify_error("") is None


class TestAnalyzeFailurePatterns:
    @pytest.fixture
    def project(self, tmp_path: Path) -> Path:
        (tmp_path / ".claude" / "runs").mkdir(parents=True)
        return tmp_path

    def _write_run_state(self, project: Path, run_id: str, records: list[dict]) -> None:
        state = {
            "run_id": run_id,
            "plan_name": "finish",
            "step_records": records,
            "current_index": 0,
            "status": "failed",
        }
        state_file = project / ".claude" / "runs" / f"{run_id}.json"
        state_file.write_text(json.dumps(state))

    def test_no_history(self, project: Path):
        report = analyze_failure_patterns(project)
        assert not report.has_patterns
        assert report.total_failures == 0

    def test_single_failure_below_threshold(self, project: Path):
        self._write_run_state(
            project,
            "finish-abc",
            [
                {"step_id": "lint", "status": "failed", "error": "syntax error near unexpected token"},
            ],
        )
        report = analyze_failure_patterns(project)
        assert not report.has_patterns

    def test_repeated_failures_detected(self, project: Path):
        self._write_run_state(
            project,
            "finish-abc",
            [
                {"step_id": "lint", "status": "failed", "error": "syntax error near unexpected token"},
            ],
        )
        self._write_run_state(
            project,
            "finish-def",
            [
                {"step_id": "deploy", "status": "failed", "error": "bash: not found in container"},
            ],
        )
        report = analyze_failure_patterns(project)
        assert report.has_patterns
        assert len(report.patterns) == 1
        assert report.patterns[0].category == "shell-compat"
        assert report.patterns[0].count == 2
        assert len(report.patterns[0].recommendations) > 0

    def test_multiple_categories(self, project: Path):
        self._write_run_state(
            project,
            "run-1",
            [
                {"step_id": "lint", "status": "failed", "error": "syntax error near unexpected token"},
            ],
        )
        self._write_run_state(
            project,
            "run-2",
            [
                {"step_id": "deploy", "status": "failed", "error": "bash: not found"},
            ],
        )
        self._write_run_state(
            project,
            "run-3",
            [
                {"step_id": "test", "status": "failed", "error": "permission denied (publickey)"},
            ],
        )
        self._write_run_state(
            project,
            "run-4",
            [
                {"step_id": "deploy", "status": "failed", "error": "unauthorized: token expired"},
            ],
        )
        report = analyze_failure_patterns(project)
        assert report.has_patterns
        assert len(report.patterns) == 2
        categories = {p.category for p in report.patterns}
        assert categories == {"shell-compat", "auth-bootstrap"}

    def test_deploy_log_scanning(self, project: Path):
        deploy_log = project / ".claude" / "deploy.log"
        deploy_log.write_text(
            "2026-01-01T00:00:00 | deploy | abc123 | main | 1\n2026-01-02T00:00:00 | deploy | def456 | main | 1\n"
        )
        report = analyze_failure_patterns(project)
        assert report.total_runs_analyzed == 2

    def test_custom_threshold(self, project: Path):
        self._write_run_state(
            project,
            "run-1",
            [
                {"step_id": "lint", "status": "failed", "error": "syntax error near unexpected token"},
            ],
        )
        self._write_run_state(
            project,
            "run-2",
            [
                {"step_id": "deploy", "status": "failed", "error": "bash: not found"},
            ],
        )
        self._write_run_state(
            project,
            "run-3",
            [
                {"step_id": "test", "status": "failed", "error": "[[ : not found in sh"},
            ],
        )
        report = analyze_failure_patterns(project, threshold=3)
        assert report.has_patterns
        assert report.patterns[0].count == 3

    def test_success_records_ignored(self, project: Path):
        self._write_run_state(
            project,
            "run-1",
            [
                {"step_id": "lint", "status": "success", "output": "all good"},
                {"step_id": "test", "status": "failed", "error": "syntax error near unexpected token"},
            ],
        )
        report = analyze_failure_patterns(project)
        assert report.total_failures == 1

    def test_malformed_state_file_skipped(self, project: Path):
        bad_file = project / ".claude" / "runs" / "bad-run.json"
        bad_file.write_text("not valid json{{{")
        report = analyze_failure_patterns(project)
        assert report.total_failures == 0

    def test_empty_error_skipped(self, project: Path):
        self._write_run_state(
            project,
            "run-1",
            [
                {"step_id": "lint", "status": "failed", "error": ""},
            ],
        )
        report = analyze_failure_patterns(project)
        assert report.total_failures == 0

    def test_patterns_sorted_by_count(self, project: Path):
        for i in range(3):
            self._write_run_state(
                project,
                f"shell-{i}",
                [
                    {"step_id": "lint", "status": "failed", "error": "bash: not found"},
                ],
            )
        for i in range(2):
            self._write_run_state(
                project,
                f"auth-{i}",
                [
                    {"step_id": "deploy", "status": "failed", "error": "permission denied"},
                ],
            )
        report = analyze_failure_patterns(project)
        assert report.patterns[0].category == "shell-compat"
        assert report.patterns[0].count == 3
        assert report.patterns[1].category == "auth-bootstrap"
        assert report.patterns[1].count == 2


class TestPatternReport:
    def test_summary_no_patterns(self):
        report = PatternReport(total_runs_analyzed=5, total_failures=1)
        assert "No repeated failure patterns" in report.summary()

    def test_summary_with_patterns(self):
        from lib.cicd.failure_patterns import FailurePattern

        report = PatternReport(
            total_runs_analyzed=10,
            total_failures=4,
            patterns=[
                FailurePattern(
                    category="shell-compat",
                    count=3,
                    recommendations=["Fix shell compat"],
                ),
            ],
        )
        summary = report.summary()
        assert "shell-compat" in summary
        assert "3 occurrences" in summary
        assert "Fix shell compat" in summary
