"""Committed negative controls for the pip-audit security adapter."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from lib.security.models import Severity
from lib.security.modules import pip_audit


@pytest.fixture(autouse=True)
def _block_real_subprocesses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every test opt in to an explicit subprocess result."""

    def unexpected_subprocess(*args: object, **kwargs: object) -> None:
        pytest.fail(f"unexpected real subprocess call: {args!r} {kwargs!r}")

    monkeypatch.setattr(pip_audit.subprocess, "run", unexpected_subprocess)


def _python_project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    return tmp_path


def _audit_report(*dependencies: dict[str, object]) -> str:
    return json.dumps({"dependencies": list(dependencies)})


class TestPopulationResolution:
    def test_missing_pip_audit_with_requirements_is_unknown(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _python_project(tmp_path)
        (root / "requirements.txt").write_text("alpha==1.0\n", encoding="utf-8")
        run = Mock()
        monkeypatch.setattr(pip_audit.subprocess, "run", run)
        monkeypatch.setattr(pip_audit, "is_available", lambda: False)

        result = pip_audit.scan(str(root))

        run.assert_not_called()
        assert any(
            "UNKNOWN" in error and "requirements.txt" in error
            for error in result.errors
        )
        assert result.passed == []
        assert result.skipped == []

    def test_missing_population_refuses_ambient_audit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _python_project(tmp_path)
        run = Mock()
        monkeypatch.setattr(pip_audit.subprocess, "run", run)
        monkeypatch.setattr(
            pip_audit,
            "is_available",
            lambda: pytest.fail("availability must not be checked without a dependency population"),
        )

        result = pip_audit.scan(str(root))

        run.assert_not_called()
        assert any(
            "UNKNOWN" in error and "ambient Python environment" in error
            for error in result.errors
        )
        assert result.passed == []

    def test_uv_lock_is_exported_and_audited(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _python_project(tmp_path)
        (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
        calls: list[list[str]] = []
        requirement_contents: list[str] = []

        def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(cmd)
            if cmd[0] == "uv":
                return subprocess.CompletedProcess(
                    cmd, 0, stdout="alpha==1.0\nbeta==2.0\n", stderr=""
                )
            requirement_path = Path(cmd[cmd.index("--requirement") + 1])
            requirement_contents.append(requirement_path.read_text(encoding="utf-8"))
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=_audit_report(
                    {"name": "alpha", "version": "1.0", "vulns": []},
                    {"name": "beta", "version": "2.0", "vulns": []},
                ),
                stderr="",
            )

        monkeypatch.setattr(pip_audit.subprocess, "run", fake_run)
        monkeypatch.setattr(pip_audit.shutil, "which", lambda name: f"/mock/bin/{name}")
        monkeypatch.setattr(pip_audit, "is_available", lambda: True)

        result = pip_audit.scan(str(root))

        assert result.errors == []
        assert result.passed and "2 package(s)" in result.passed[0]
        assert "uv.lock" in result.passed[0]
        assert requirement_contents == ["alpha==1.0\nbeta==2.0\n"]
        pip_audit_cmd = next(cmd for cmd in calls if cmd[0] == "pip-audit")
        assert "--requirement" in pip_audit_cmd
        temporary_requirement = Path(pip_audit_cmd[pip_audit_cmd.index("--requirement") + 1])
        assert temporary_requirement.exists() is False

    def test_missing_uv_binary_is_unknown_and_does_not_audit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _python_project(tmp_path)
        (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
        run = Mock()
        monkeypatch.setattr(pip_audit.subprocess, "run", run)
        monkeypatch.setattr(
            pip_audit.shutil,
            "which",
            lambda name: None if name == "uv" else f"/mock/bin/{name}",
        )
        monkeypatch.setattr(
            pip_audit,
            "is_available",
            lambda: pytest.fail("pip-audit availability must not be checked after export failure"),
        )

        result = pip_audit.scan(str(root))

        run.assert_not_called()
        assert any(
            "UNKNOWN" in error and "uv.lock" in error and "uv" in error
            for error in result.errors
        )
        assert result.passed == []

    @pytest.mark.parametrize(
        ("export_result", "message_fragment"),
        [
            (
                subprocess.CompletedProcess(
                    ["uv"], 2, stdout="", stderr="first\nexport failed\n"
                ),
                "export failed",
            ),
            (
                subprocess.CompletedProcess(["uv"], 0, stdout=" \n", stderr=""),
                "empty requirements file",
            ),
        ],
    )
    def test_failed_or_empty_uv_export_is_unknown(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        export_result: subprocess.CompletedProcess[str],
        message_fragment: str,
    ) -> None:
        root = _python_project(tmp_path)
        (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
        run = Mock(return_value=export_result)
        monkeypatch.setattr(pip_audit.subprocess, "run", run)
        monkeypatch.setattr(pip_audit.shutil, "which", lambda name: f"/mock/bin/{name}")

        result = pip_audit.scan(str(root))

        assert any(
            "UNKNOWN" in error and message_fragment in error
            for error in result.errors
        )
        assert all(call.args[0][0] != "pip-audit" for call in run.call_args_list)


class TestAuditVerdicts:
    def test_exit_zero_with_invalid_json_is_unknown(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _python_project(tmp_path)
        (root / "requirements.txt").write_text("alpha==1.0\n", encoding="utf-8")
        run = Mock(
            return_value=subprocess.CompletedProcess(
                ["pip-audit"], 0, stdout="not-json", stderr="diagnostic\nlast stderr line\n"
            )
        )
        monkeypatch.setattr(pip_audit.subprocess, "run", run)
        monkeypatch.setattr(pip_audit, "is_available", lambda: True)

        result = pip_audit.scan(str(root))

        assert result.errors
        assert "exit code 0" in result.errors[0]
        assert "last stderr line" in result.errors[0]
        assert result.passed == []
        assert result.findings == []

    def test_clean_requirements_run_states_denominator(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _python_project(tmp_path)
        (root / "requirements.txt").write_text(
            "alpha==1.0\nbeta==2.0\ngamma==3.0\n", encoding="utf-8"
        )
        report = _audit_report(
            {"name": "alpha", "version": "1.0", "vulns": []},
            {"name": "beta", "version": "2.0", "vulns": []},
            {"name": "gamma", "version": "3.0", "vulns": []},
        )
        monkeypatch.setattr(
            pip_audit.subprocess,
            "run",
            Mock(
                return_value=subprocess.CompletedProcess(
                    ["pip-audit"], 0, stdout=report, stderr=""
                )
            ),
        )
        monkeypatch.setattr(pip_audit, "is_available", lambda: True)

        result = pip_audit.scan(str(root))

        assert result.passed
        assert "3 package(s)" in result.passed[0]
        assert "requirements.txt" in result.passed[0]
        assert result.errors == []

    def test_vulnerability_still_builds_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _python_project(tmp_path)
        (root / "requirements.txt").write_text("unsafe==1.0\n", encoding="utf-8")
        report = _audit_report(
            {
                "name": "unsafe",
                "version": "1.0",
                "vulns": [
                    {
                        "id": "CVE-2026-1234",
                        "fix_versions": ["1.1", "2.0"],
                        "description": "A known test vulnerability.",
                    }
                ],
            }
        )
        monkeypatch.setattr(
            pip_audit.subprocess,
            "run",
            Mock(
                return_value=subprocess.CompletedProcess(
                    ["pip-audit"], 1, stdout=report, stderr=""
                )
            ),
        )
        monkeypatch.setattr(pip_audit, "is_available", lambda: True)

        result = pip_audit.scan(str(root))

        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.id == "PIP_AUDIT_CVE_2026_1234"
        assert finding.severity == Severity.HIGH
        assert finding.file_path == "requirements.txt"
        assert finding.fix == "Upgrade to 1.1, 2.0"
        assert finding.command == "uv pip install --upgrade unsafe"
        assert result.passed == []
