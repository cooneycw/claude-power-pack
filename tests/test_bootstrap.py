"""Tests for the bootstrap dependency checker."""

from pathlib import Path

import pytest

from lib.cicd.bootstrap import (
    BootstrapConfig,
    BootstrapDependency,
    check_all,
    check_dependency,
    main,
)


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir()
    return tmp_path


def _write_config(project_root: Path, yaml_content: str) -> None:
    config_path = project_root / ".claude" / "bootstrap.yaml"
    config_path.write_text(yaml_content)


class TestBootstrapConfig:
    def test_load_missing_file(self, tmp_project: Path):
        config = BootstrapConfig.load(tmp_project)
        assert config is None

    def test_load_empty_file(self, tmp_project: Path):
        _write_config(tmp_project, "")
        config = BootstrapConfig.load(tmp_project)
        assert config is None

    def test_load_valid_config(self, tmp_project: Path):
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  iam-role:
    description: IAM role for project isolation
    check_command: "test -f .bootstrap/iam-applied"
    remediation: "Run: make iam-apply"
  secrets:
    description: AWS secrets provisioned
    check_command: "aws secretsmanager describe-secret --secret-id test 2>/dev/null"
    remediation: "Run: python woodpecker/bootstrap-secrets.py"
    timeout_seconds: 15
""",
        )
        config = BootstrapConfig.load(tmp_project)
        assert config is not None
        assert len(config.dependencies) == 2
        assert config.dependencies[0].name == "iam-role"
        assert config.dependencies[0].timeout_seconds == 30
        assert config.dependencies[1].name == "secrets"
        assert config.dependencies[1].timeout_seconds == 15

    def test_load_config_without_check_command_skips(self, tmp_project: Path):
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  bad-dep:
    description: Missing check_command
    remediation: "Do something"
  good-dep:
    description: Has check_command
    check_command: "true"
    remediation: "Run something"
""",
        )
        config = BootstrapConfig.load(tmp_project)
        assert config is not None
        assert len(config.dependencies) == 1
        assert config.dependencies[0].name == "good-dep"


class TestCheckDependency:
    def test_satisfied(self, tmp_project: Path):
        dep = BootstrapDependency(
            name="test",
            description="Always passes",
            check_command="true",
            remediation="N/A",
        )
        result = check_dependency(dep, tmp_project)
        assert result.satisfied
        assert result.error == ""

    def test_not_satisfied(self, tmp_project: Path):
        dep = BootstrapDependency(
            name="test",
            description="Always fails",
            check_command="false",
            remediation="Fix it",
        )
        result = check_dependency(dep, tmp_project)
        assert not result.satisfied
        assert result.remediation == "Fix it"

    def test_timeout(self, tmp_project: Path):
        dep = BootstrapDependency(
            name="slow",
            description="Times out",
            check_command="sleep 10",
            remediation="Speed up",
            timeout_seconds=1,
        )
        result = check_dependency(dep, tmp_project)
        assert not result.satisfied
        assert "timed out" in result.error.lower()

    def test_check_command_with_file(self, tmp_project: Path):
        marker = tmp_project / ".bootstrap-done"
        dep = BootstrapDependency(
            name="marker",
            description="Checks marker file",
            check_command=f"test -f {marker}",
            remediation="Run bootstrap",
        )
        result = check_dependency(dep, tmp_project)
        assert not result.satisfied

        marker.write_text("done")
        result = check_dependency(dep, tmp_project)
        assert result.satisfied


class TestCheckAll:
    def test_no_config(self, tmp_project: Path):
        passed, results = check_all(tmp_project)
        assert passed
        assert results == []

    def test_all_satisfied(self, tmp_project: Path):
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  dep1:
    description: First dep
    check_command: "true"
    remediation: N/A
  dep2:
    description: Second dep
    check_command: "true"
    remediation: N/A
""",
        )
        passed, results = check_all(tmp_project)
        assert passed
        assert len(results) == 2
        assert all(r.satisfied for r in results)

    def test_one_blocked(self, tmp_project: Path):
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  ok-dep:
    description: Passes
    check_command: "true"
    remediation: N/A
  bad-dep:
    description: Fails
    check_command: "false"
    remediation: "Fix this"
""",
        )
        passed, results = check_all(tmp_project)
        assert not passed
        assert len(results) == 2
        blocked = [r for r in results if not r.satisfied]
        assert len(blocked) == 1
        assert blocked[0].name == "bad-dep"

    def test_empty_dependencies(self, tmp_project: Path):
        _write_config(
            tmp_project,
            """
version: "1"
dependencies: {}
""",
        )
        passed, results = check_all(tmp_project)
        assert passed
        assert results == []


class TestCLI:
    def test_check_no_config(self, tmp_project: Path, monkeypatch):
        monkeypatch.chdir(tmp_project)
        exit_code = main(["check"])
        assert exit_code == 0

    def test_check_all_pass(self, tmp_project: Path, monkeypatch):
        monkeypatch.chdir(tmp_project)
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  dep1:
    description: Passes
    check_command: "true"
    remediation: N/A
""",
        )
        exit_code = main(["check"])
        assert exit_code == 0

    def test_check_blocked(self, tmp_project: Path, monkeypatch):
        monkeypatch.chdir(tmp_project)
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  blocker:
    description: Fails
    check_command: "false"
    remediation: "Run bootstrap"
""",
        )
        exit_code = main(["check"])
        assert exit_code == 1

    def test_list_command(self, tmp_project: Path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_project)
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  my-dep:
    description: A dependency
    check_command: "test -f marker"
    remediation: "Run setup"
""",
        )
        exit_code = main(["list"])
        assert exit_code == 0
        output = capsys.readouterr().out
        assert "my-dep" in output

    def test_project_root_flag(self, tmp_project: Path):
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  dep:
    description: Test
    check_command: "true"
    remediation: N/A
""",
        )
        exit_code = main(["check", "--project-root", str(tmp_project)])
        assert exit_code == 0
