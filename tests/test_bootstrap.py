"""Tests for the bootstrap dependency checker."""

from pathlib import Path

import pytest

import lib.cicd.bootstrap as bootstrap
from lib.cicd.bootstrap import (
    BootstrapConfig,
    BootstrapDependency,
    CheckResult,
    built_in_advisories,
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


def _failed_check(dep: BootstrapDependency, _project_root: Path) -> CheckResult:
    return CheckResult(
        name=dep.name,
        satisfied=False,
        description=dep.description,
        remediation=dep.remediation,
        error="Not available",
        advisory=dep.advisory,
    )


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

    def test_advisory_defaults_to_false(self, tmp_project: Path):
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  required-dep:
    description: Required dependency
    check_command: "required-check"
    remediation: "Install it"
""",
        )
        config = BootstrapConfig.load(tmp_project)
        assert config is not None
        assert config.dependencies[0].advisory is False


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

    def test_failing_advisory_does_not_block(
        self, tmp_project: Path, monkeypatch, capsys
    ):
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  optional-dep:
    description: Optional dependency
    check_command: "optional-check"
    remediation: "Install it if needed"
    advisory: true
""",
        )
        monkeypatch.setattr(bootstrap, "check_dependency", _failed_check)

        passed, results = check_all(tmp_project)

        assert passed
        assert len(results) == 1
        assert not results[0].satisfied
        assert results[0].advisory
        assert main(["check", "--project-root", str(tmp_project)]) == 0
        output = capsys.readouterr().out
        assert "WARN" in output
        assert "PASSED" in output
        assert "BLOCKED" not in output

    def test_failing_blocking_dependency_still_blocks(
        self, tmp_project: Path, monkeypatch
    ):
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  required-dep:
    description: Required dependency
    check_command: "required-check"
    remediation: "Install it"
""",
        )
        monkeypatch.setattr(bootstrap, "check_dependency", _failed_check)

        passed, results = check_all(tmp_project)

        assert not passed
        assert len(results) == 1
        assert not results[0].advisory
        assert main(["check", "--project-root", str(tmp_project)]) == 1

    def test_failing_advisory_does_not_mask_blocking_failure(
        self, tmp_project: Path, monkeypatch
    ):
        _write_config(
            tmp_project,
            """
version: "1"
dependencies:
  optional-dep:
    description: Optional dependency
    check_command: "optional-check"
    remediation: "Install it if needed"
    advisory: true
  required-dep:
    description: Required dependency
    check_command: "required-check"
    remediation: "Install it"
""",
        )
        monkeypatch.setattr(bootstrap, "check_dependency", _failed_check)

        passed, results = check_all(tmp_project)

        assert not passed
        assert len(results) == 2
        assert {result.advisory for result in results} == {False, True}
        assert main(["check", "--project-root", str(tmp_project)]) == 1


class TestBuiltInAdvisories:
    @pytest.mark.parametrize("marker", ["pyproject.toml", "requirements.txt"])
    def test_python_project_gets_python3_venv_advisory(
        self, tmp_project: Path, marker: str
    ):
        (tmp_project / marker).write_text("")

        advisories = built_in_advisories(tmp_project)

        assert len(advisories) == 1
        assert advisories[0].name == "python3-venv"
        assert advisories[0].advisory
        assert advisories[0].check_command == 'python3 -c "import ensurepip"'
        assert "uv venv .venv" in advisories[0].remediation
        assert "apt install python3-venv" in advisories[0].remediation

    def test_non_python_project_gets_no_python_advisory(self, tmp_project: Path):
        python_markers = ("pyproject.toml", "requirements.txt", "setup.py")
        assert all(not (tmp_project / marker).exists() for marker in python_markers)

        assert built_in_advisories(tmp_project) == []

    def test_no_config_python_project_still_runs_advisory(
        self, tmp_project: Path, monkeypatch, capsys
    ):
        assert BootstrapConfig.load(tmp_project) is None
        (tmp_project / "pyproject.toml").write_text("")
        monkeypatch.setattr(bootstrap, "check_dependency", _failed_check)

        passed, results = check_all(tmp_project)

        assert passed
        assert [result.name for result in results] == ["python3-venv"]
        assert not results[0].satisfied
        assert results[0].advisory
        assert main(["check", "--project-root", str(tmp_project)]) == 0
        output = capsys.readouterr().out
        assert "Config: \x1b[0;34mnone (only built-in advisories shown)" in output
        assert str(tmp_project / ".claude" / "bootstrap.yaml") not in output


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

    def test_check_report_names_existing_config(
        self, tmp_project: Path, capsys
    ):
        _write_config(
            tmp_project,
            """
version: "1"
dependencies: {}
""",
        )
        config_path = tmp_project / ".claude" / "bootstrap.yaml"
        assert config_path.exists()

        exit_code = main(["check", "--project-root", str(tmp_project)])

        assert exit_code == 0
        output = capsys.readouterr().out
        assert f"Config: \x1b[0;34m{config_path}\x1b[0m" in output
        assert "only built-in advisories shown" not in output

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

    def test_list_command_includes_built_in_advisory(
        self, tmp_project: Path, capsys
    ):
        assert BootstrapConfig.load(tmp_project) is None
        (tmp_project / "requirements.txt").write_text("")

        exit_code = main(["list", "--project-root", str(tmp_project)])

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "python3-venv (advisory)" in output
        assert "No bootstrap dependencies configured." not in output

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
