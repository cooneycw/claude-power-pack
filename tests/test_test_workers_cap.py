"""Tests for pytest worker-cap resolution in CI/CD test steps (issue #640)."""

from __future__ import annotations

import os
import sys
import textwrap
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from lib.cicd.runner import DeterministicRunner
from lib.cicd.steps import ShellStep, StepDef, get_plan_steps


def _isolated_context(monkeypatch: pytest.MonkeyPatch, **env: str) -> dict[str, Any]:
    for key in list(os.environ):
        monkeypatch.delenv(key)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return {"env": dict(env)}


def _relative_interpreter(tmp_path: Path) -> str:
    """A RELATIVE interpreter name for a step command, free of any absolute path.

    ``sys.executable`` is an absolute path this module does not control, and
    ``is_test_step()`` scans the whole COMMAND (see ``_TEST_STEP_HINT``): under a
    flow worktree the interpreter lives at
    ``.../claude-power-pack-issue-N-<slug>/.venv/bin/python3``, so a slug
    containing "test" reclassified a ``lint`` step as a test step and turned the
    gate red for reasons unrelated to the change under review (issue #704).

    An absolute path under ``tmp_path`` is no better: pytest's own temp root is
    ``/tmp/pytest-of-<user>/pytest-<n>/``, which matches on "pytest". Naming
    ``PYTEST_WORKERS`` in the command matches too - which is why the caller reads
    it via ``os.environ`` inside a script whose CONTENT is never scanned. Steps
    run with ``cwd=project_root`` (``lib/cicd/steps.py``), so a relative name in
    that directory reaches the interpreter while keeping every path out of the
    command string.
    """
    (tmp_path / "interp").symlink_to(sys.executable)
    return "./interp"


@pytest.mark.parametrize(
    ("step_env", "host_env", "expected"),
    [
        (
            {"PYTEST_WORKERS": "2"},
            {"CPP_TEST_WORKERS": "3"},
            ("2", "step-env"),
        ),
        (
            {},
            {"PYTEST_WORKERS": "4", "CPP_TEST_WORKERS": "3"},
            ("4", "host-env"),
        ),
        ({}, {"CPP_TEST_WORKERS": "3"}, ("3", "CPP_TEST_WORKERS")),
        ({}, {}, None),
        (
            {"PYTEST_WORKERS": ""},
            {"PYTEST_WORKERS": "4", "CPP_TEST_WORKERS": "3"},
            ("4", "host-env"),
        ),
        (
            {},
            {"PYTEST_WORKERS": "", "CPP_TEST_WORKERS": "3"},
            ("3", "CPP_TEST_WORKERS"),
        ),
        ({}, {"CPP_TEST_WORKERS": ""}, None),
        ({}, {"PYTEST_WORKERS": "", "CPP_TEST_WORKERS": ""}, None),
    ],
)
def test_worker_cap_precedence_and_empty_fallthrough(
    monkeypatch: pytest.MonkeyPatch,
    step_env: dict[str, str],
    host_env: dict[str, str],
    expected: tuple[str, str] | None,
) -> None:
    context = _isolated_context(monkeypatch, **host_env)
    step = ShellStep(StepDef(id="test", command="pytest", env=step_env))

    assert step.resolve_pytest_workers(context) == expected
    resolved_env = step._resolve_env(context)
    if expected is None:
        assert resolved_env is None or "PYTEST_WORKERS" not in resolved_env
    else:
        assert resolved_env is not None
        assert resolved_env["PYTEST_WORKERS"] == expected[0]


def test_manifest_step_env_cap_reaches_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_dir = tmp_path / ".claude"
    manifest_dir.mkdir()
    (manifest_dir / "cicd_tasks.yml").write_text(
        textwrap.dedent(
            """\
            version: "1"
            steps:
              test:
                command: printf '%s' "$PYTEST_WORKERS" > manifest-workers.txt
                env:
                  PYTEST_WORKERS: "2"
            plans:
              finish:
                steps: [test]
            """
        )
    )
    _isolated_context(monkeypatch, CPP_OFFLINE="1", CPP_TEST_WORKERS="9")
    steps = get_plan_steps("finish", project_root=str(tmp_path))

    result = DeterministicRunner(project_root=tmp_path, output=StringIO()).run(
        "finish", step_defs=steps
    )

    assert result.success
    assert (tmp_path / "manifest-workers.txt").read_text() == "2"


def test_builtin_shaped_test_step_uses_host_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolated_context(monkeypatch, CPP_OFFLINE="1", CPP_TEST_WORKERS="5")
    output_file = tmp_path / "builtin-workers.txt"
    step = StepDef(
        id="test",
        command=f'printf "%s" "$PYTEST_WORKERS" > "{output_file}"',
    )

    result = DeterministicRunner(project_root=tmp_path, output=StringIO()).run(
        "check", step_defs=[step]
    )

    assert result.success
    assert output_file.read_text() == "5"


def test_builtin_shaped_bare_pytest_step_resolves_host_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _isolated_context(monkeypatch, CPP_TEST_WORKERS="5")
    step = ShellStep(StepDef(id="quality", command="pytest"))

    assert step.resolve_pytest_workers(context) == ("5", "CPP_TEST_WORKERS")
    resolved_env = step._resolve_env(context)
    assert resolved_env is not None
    assert resolved_env["PYTEST_WORKERS"] == "5"


def test_runner_logs_test_cap_but_not_non_test_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolated_context(monkeypatch, CPP_OFFLINE="1", CPP_TEST_WORKERS="6")
    output = StringIO()
    steps = [
        StepDef(id="lint", command="true"),
        StepDef(id="test", command="true"),
        StepDef(id="typecheck", command="true"),
    ]

    result = DeterministicRunner(project_root=tmp_path, output=output).run(
        "check", step_defs=steps
    )

    assert result.success
    running_lines = [line for line in output.getvalue().splitlines() if "running..." in line]
    assert "[PYTEST_WORKERS=6 via CPP_TEST_WORKERS]" in running_lines[1]
    assert "PYTEST_WORKERS" not in running_lines[0]
    assert "PYTEST_WORKERS" not in running_lines[2]


def test_runner_logs_unset_for_test_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolated_context(monkeypatch, CPP_OFFLINE="1")
    output = StringIO()

    result = DeterministicRunner(project_root=tmp_path, output=output).run(
        "check", step_defs=[StepDef(id="test", command="true")]
    )

    assert result.success
    assert "running... () [PYTEST_WORKERS=unset]" in output.getvalue()


def test_non_test_step_never_receives_injected_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolated_context(monkeypatch, CPP_OFFLINE="1", CPP_TEST_WORKERS="7")
    output_file = tmp_path / "lint-workers.txt"
    capture_script = tmp_path / "capture_env.py"
    capture_script.write_text(
        "import os\n"
        f"from pathlib import Path\nPath({str(output_file)!r}).write_text("
        "os.environ.get('PYTEST_WORKERS', 'unset'))\n"
    )
    step = StepDef(
        id="lint",
        command=f"{_relative_interpreter(tmp_path)} capture_env.py",
    )

    # Precondition guard (issue #704, the convention adopted in #697): this
    # fixture constructs a NEGATIVE condition - a step that must NOT be seen as
    # a test step - indirectly, via a command string. Assert the condition holds
    # before exercising the runner, so a future absolute path smuggled into the
    # command fails here, naming the real cause, instead of surfacing further
    # down as an unrelated-looking "assert '7' == 'unset'".
    assert not ShellStep(step).is_test_step(), (
        "step 'lint' must classify as a NON-test step. If its command above shows "
        "an ABSOLUTE path, this fixture is at fault - the command may contain no "
        "path and must not name PYTEST_WORKERS (#704). Otherwise is_test_step() "
        "itself regressed."
    )

    result = DeterministicRunner(project_root=tmp_path, output=StringIO()).run(
        "check", step_defs=[step]
    )

    assert result.success
    assert output_file.read_text() == "unset"
