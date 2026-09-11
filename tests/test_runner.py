"""Tests for the deterministic CI/CD runner."""

import os
import re
import shutil
import subprocess
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.cicd.runner import (
    MAX_RERUN_IDS,
    DeterministicRunner,
    RunResult,
    _build_step_env,
    _is_offline,
    _project_python_floor,
    run_plan,
)
from lib.cicd.state import RunState, StepRecord, compute_tree_signature
from lib.cicd.steps import _CPP_ROOT, BUILTIN_PLANS, GATE_STEP_IDS, ShellStep, StepDef


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory for runner tests."""
    return tmp_path


requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not available (e.g. Woodpecker validate container)"
)


def _git_repo(root: Path) -> Path:
    """Init a git repo at ``root`` with one commit, so write-tree has a base."""
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "--allow-empty", "-q", "-m", "init"],
        cwd=root,
        check=True,
    )
    return root


class TestDeterministicRunner:
    def test_successful_run(self, tmp_project: Path):
        steps = [
            StepDef(id="lint", command="echo 'lint ok'", timeout_seconds=30),
            StepDef(id="test", command="echo 'test ok'", timeout_seconds=30),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        assert result.success
        assert result.steps_completed == 2
        assert result.steps_total == 2
        assert result.failed_step is None

        # State file should be cleaned up on success
        runs_dir = tmp_project / ".claude" / "runs"
        if runs_dir.exists():
            assert len(list(runs_dir.glob("*.json"))) == 0

    def test_failed_step_halts(self, tmp_project: Path):
        steps = [
            StepDef(id="lint", command="echo 'lint ok'", timeout_seconds=30),
            StepDef(id="bad_step", command="exit 1", timeout_seconds=30),
            StepDef(id="test", command="echo 'test ok'", timeout_seconds=30),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        assert not result.success
        assert result.failed_step == "bad_step"
        assert result.steps_completed == 1  # only lint completed
        assert result.steps_total == 3

        # State file should exist for resume
        runs_dir = tmp_project / ".claude" / "runs"
        state_files = list(runs_dir.glob("*.json"))
        assert len(state_files) == 1

    def test_resume_from_failed(self, tmp_project: Path):
        # First run: fail at step 2
        steps = [
            StepDef(id="lint", command="echo 'lint ok'", timeout_seconds=30),
            StepDef(id="bad_step", command="exit 1", timeout_seconds=30),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result1 = runner.run("check", step_defs=steps)
        assert not result1.success
        run_id = result1.run_id

        # Fix the step and resume
        fixed_steps = [
            StepDef(id="lint", command="echo 'lint ok'", timeout_seconds=30),
            StepDef(id="bad_step", command="echo 'fixed'", timeout_seconds=30),
        ]

        # Auto-resume: run same plan again - should find failed state
        result2 = runner.run("check", step_defs=fixed_steps)
        assert result2.success
        assert result2.run_id == run_id  # same run, resumed

    def test_explicit_resume(self, tmp_project: Path):
        steps = [
            StepDef(id="step1", command="echo ok", timeout_seconds=30),
            StepDef(id="step2", command="exit 1", timeout_seconds=30),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result1 = runner.run("test_plan", step_defs=steps)
        assert not result1.success

        # Manually update the state to fix the command (simulate code fix)
        state = RunState.load(result1.run_id, tmp_project)
        state.status = "running"
        state.save(tmp_project)

        # Resume will try to load "test_plan" from built-in plans, which won't exist.
        # This verifies the resume mechanism loads state correctly.
        # In production, the manifest would provide the steps.
        try:
            runner.resume(result1.run_id)
        except ValueError:
            pass  # Expected: "test_plan" is not a built-in plan

    def test_skip_condition(self, tmp_project: Path):
        steps = [
            StepDef(
                id="optional_step",
                command="echo 'should not run'",
                timeout_seconds=30,
                skip_if="true",  # always skip
            ),
            StepDef(id="required_step", command="echo 'must run'", timeout_seconds=30),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        assert result.success
        assert result.steps_completed == 2

        # Verify the optional step was skipped (check via run - state cleaned up)
        # The step should not have produced output

    def test_timeout(self, tmp_project: Path):
        steps = [
            StepDef(id="slow", command="sleep 10", timeout_seconds=1),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        assert not result.success
        assert result.failed_step == "slow"
        assert "timed out" in (result.error or "")

    def test_retry_on_failure(self, tmp_project: Path):
        # Create a file that tracks attempts
        counter_file = tmp_project / "attempt_counter"
        counter_file.write_text("0")

        # Command that fails twice then succeeds
        cmd = (
            f"count=$(cat {counter_file}); "
            f"count=$((count + 1)); "
            f"echo $count > {counter_file}; "
            f"[ $count -ge 3 ]"
        )

        steps = [
            StepDef(
                id="flaky",
                command=cmd,
                timeout_seconds=30,
                max_attempts=3,
                backoff_seconds=0.1,
            ),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        assert result.success
        assert int(counter_file.read_text().strip()) == 3

    def test_run_result_dict(self):
        result = RunResult(
            success=False,
            run_id="check-abc123",
            plan_name="check",
            steps_completed=1,
            steps_total=3,
            failed_step="test",
            error="FAIL: test_foo",
        )
        d = result.to_dict()
        assert d["success"] is False
        assert d["failed_step"] == "test"
        assert d["plan"] == "check"

    def test_empty_plan(self, tmp_project: Path):
        steps: list[StepDef] = []
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("empty", step_defs=steps)
        assert result.success
        assert result.steps_completed == 0

    def test_log_output(self, tmp_project: Path):
        output = StringIO()
        steps = [
            StepDef(id="echo", command="echo hello", timeout_seconds=30),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=output)
        runner.run("check", step_defs=steps)

        log = output.getvalue()
        assert "echo" in log
        assert "SUCCESS" in log

    def test_env_sanitized_in_child(self, tmp_project: Path):
        """Runner strips PYTHONPATH so child steps don't inherit runner imports."""
        env_file = tmp_project / "captured_env.txt"
        steps = [
            StepDef(
                id="capture_env",
                command=f'echo "PYTHONPATH=${{PYTHONPATH:-UNSET}}" > {env_file}',
                timeout_seconds=30,
            ),
        ]
        with patch.dict(os.environ, {"PYTHONPATH": "/fake/runner/lib"}):
            runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
            result = runner.run("check", step_defs=steps)

        assert result.success
        content = env_file.read_text()
        assert "PYTHONPATH=UNSET" in content

    def test_uv_cache_dir_defaulted(self, tmp_project: Path):
        """Runner defaults UV_CACHE_DIR when not already set."""
        env_file = tmp_project / "uv_cache.txt"
        steps = [
            StepDef(
                id="capture_uv",
                command=f'echo "$UV_CACHE_DIR" > {env_file}',
                timeout_seconds=30,
            ),
        ]
        env_without_uv = {k: v for k, v in os.environ.items() if k != "UV_CACHE_DIR"}
        with patch.dict(os.environ, env_without_uv, clear=True):
            runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
            result = runner.run("check", step_defs=steps)

        assert result.success
        assert env_file.read_text().strip() == "/tmp/uv-cache"

    def test_step_level_env_override(self, tmp_project: Path):
        """Step-level env vars merge on top of context env."""
        env_file = tmp_project / "step_env.txt"
        steps = [
            StepDef(
                id="with_env",
                command=f'echo "$MY_STEP_VAR" > {env_file}',
                timeout_seconds=30,
                env={"MY_STEP_VAR": "from_step"},
            ),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        assert result.success
        assert env_file.read_text().strip() == "from_step"


class TestShellStepStreaming:
    """Live-streaming + partial-output-on-timeout behavior (issue #537)."""

    def test_output_teed_live_to_stream(self, tmp_project: Path):
        """Child stdout is teed to the runner stream, not only captured at exit."""
        stream = StringIO()
        step = ShellStep(StepDef(id="emit", command="echo hello-stream", timeout_seconds=30))
        result = step.execute({"project_root": str(tmp_project), "output_stream": stream})

        assert result.success
        assert "hello-stream" in result.output        # captured in the result
        assert "hello-stream" in stream.getvalue()     # AND streamed live

    def test_no_stream_is_backwards_compatible(self, tmp_project: Path):
        """Without an output_stream the step still captures output (pure capture)."""
        step = ShellStep(StepDef(id="emit", command="echo captured-only", timeout_seconds=30))
        result = step.execute({"project_root": str(tmp_project)})

        assert result.success
        assert "captured-only" in result.output

    def test_timeout_preserves_partial_output(self, tmp_project: Path):
        """A wall-clock timeout keeps output produced before the hang."""
        stream = StringIO()
        step = ShellStep(
            StepDef(id="slow", command="echo partial-line; sleep 30", timeout_seconds=1)
        )
        result = step.execute({"project_root": str(tmp_project), "output_stream": stream})

        assert not result.success
        assert result.exit_code == 124
        assert "timed out" in result.error
        # The line printed before the sleep is NOT discarded - it shows where it hung.
        assert "partial-line" in result.output
        assert "partial-line" in stream.getvalue()

    def test_stderr_still_captured(self, tmp_project: Path):
        """stderr remains captured separately in the error field on failure."""
        step = ShellStep(
            StepDef(id="fail", command="echo oops 1>&2; exit 3", timeout_seconds=30)
        )
        result = step.execute({"project_root": str(tmp_project)})

        assert not result.success
        assert result.exit_code == 3
        assert "oops" in result.error


class TestRerunFailedTests:
    @staticmethod
    def _first_fails_then(summary: str) -> str:
        return (
            "if [ -f rerun-marker ]; then "
            f"printf '{summary}\\n'; "
            "else : > rerun-marker; "
            "printf '=== 1 failed, 2 passed in 0.01s ===\\n'; "
            "printf 'FAILED tests/a.py::t1 - AssertionError: first attempt\\n'; "
            "exit 1; fi"
        )

    def test_off_by_default(self, tmp_project: Path) -> None:
        step = StepDef(
            id="test",
            command=(
                "printf x >> counter; "
                "printf '=== 1 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; exit 1"
            ),
            timeout_seconds=30,
        )
        result = DeterministicRunner(
            project_root=tmp_project, output=StringIO()
        ).run("check", step_defs=[step])

        assert not result.success
        assert (tmp_project / "counter").read_text() == "x"
        assert result.reruns == []
        assert "reruns" not in result.to_dict()

    def test_rerun_passes_and_preserves_first_attempt_counts(
        self, tmp_project: Path
    ) -> None:
        step = StepDef(
            id="test",
            command=self._first_fails_then("=== 1 passed in 0.01s ==="),
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])

        assert result.success
        assert result.to_dict()["reruns"][0]["outcome"] == "passed"
        assert result.reruns[0]["ids"] == ["tests/a.py::t1"]
        assert result.tests["test"]["failed"] == 1
        assert result.tests["test"]["passed"] == 2
        assert result.reruns[0]["first_attempt"] == result.tests["test"]
        assert result.reruns[0]["rerun"]["passed"] == 1
        assert "RE-RAN AND PASSED: tests/a.py::t1 (1 id)" in log.getvalue()
        assert "completed successfully" not in log.getvalue()

    def test_rerun_sees_pytest_addopts(
        self, tmp_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        command = (
            "if [ -f rerun-marker ]; then "
            "printf '%s' \"${PYTEST_ADDOPTS:-}\" > rerun-addopts; "
            "printf '=== 1 passed in 0.01s ===\\n'; "
            "else : > rerun-marker; "
            "printf '=== 1 failed in 0.01s ===\\n'; "
            "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; exit 1; fi"
        )
        step = StepDef(id="test", command=command, timeout_seconds=30)
        monkeypatch.setenv("PYTEST_ADDOPTS", "-q")
        result = DeterministicRunner(
            project_root=tmp_project, output=StringIO(), rerun_failed=True
        ).run("check", step_defs=[step])

        assert result.success
        addopts = (tmp_project / "rerun-addopts").read_text()
        assert addopts.startswith("-q ")
        assert "--last-failed" in addopts
        assert "--last-failed-no-failures none" in addopts

    def test_genuine_failure_still_fails_after_one_rerun(
        self, tmp_project: Path
    ) -> None:
        step = StepDef(
            id="test",
            command=(
                "printf x >> counter; "
                "printf '=== 1 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; exit 1"
            ),
            timeout_seconds=30,
        )
        result = DeterministicRunner(
            project_root=tmp_project, output=StringIO(), rerun_failed=True
        ).run("check", step_defs=[step])

        assert not result.success
        assert result.reruns[0]["outcome"] == "failed"
        assert (tmp_project / "counter").read_text() == "xx"

    def test_inconclusive_rerun_keeps_original_failure(
        self, tmp_project: Path
    ) -> None:
        step = StepDef(
            id="test",
            command=self._first_fails_then("=== no tests ran in 0.01s ==="),
            timeout_seconds=30,
        )
        result = DeterministicRunner(
            project_root=tmp_project, output=StringIO(), rerun_failed=True
        ).run("check", step_defs=[step])

        assert not result.success
        assert result.reruns[0]["outcome"] == "inconclusive"
        assert result.reruns[0]["rerun"]["executed"] == 0

    def test_non_test_step_is_never_rerun(self, tmp_project: Path) -> None:
        step = StepDef(
            id="lint",
            command="printf x >> counter; exit 1",
            timeout_seconds=30,
        )
        result = DeterministicRunner(
            project_root=tmp_project, output=StringIO(), rerun_failed=True
        ).run("check", step_defs=[step])

        assert not result.success
        assert (tmp_project / "counter").read_text() == "x"
        assert result.reruns == []

    def test_zero_reported_failures_is_not_rerun(self, tmp_project: Path) -> None:
        step = StepDef(
            id="test",
            command=(
                "printf x >> counter; "
                "printf '=== 3 passed in 0.01s ===\\n'; exit 1"
            ),
            timeout_seconds=30,
        )
        result = DeterministicRunner(
            project_root=tmp_project, output=StringIO(), rerun_failed=True
        ).run("check", step_defs=[step])

        assert not result.success
        assert (tmp_project / "counter").read_text() == "x"
        assert result.reruns == []

    def test_more_than_cap_is_not_rerun(self, tmp_project: Path) -> None:
        failed_lines = "\\n".join(
            f"FAILED tests/a.py::test_{idx} - AssertionError"
            for idx in range(MAX_RERUN_IDS + 1)
        )
        step = StepDef(
            id="test",
            command=(
                "printf x >> counter; "
                f"printf '=== {MAX_RERUN_IDS + 1} failed in 0.01s ===\\n'; "
                f"printf '{failed_lines}\\n'; exit 1"
            ),
            timeout_seconds=30,
        )
        result = DeterministicRunner(
            project_root=tmp_project, output=StringIO(), rerun_failed=True
        ).run("check", step_defs=[step])

        assert not result.success
        assert (tmp_project / "counter").read_text() == "x"
        assert result.reruns == []

    def test_run_plan_honours_env_opt_in(
        self, tmp_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = RunResult(success=True, run_id="run", plan_name="check")
        with patch("lib.cicd.runner.DeterministicRunner") as runner_class:
            runner_class.return_value.run.return_value = result
            monkeypatch.setenv("CPP_GATE_RERUN_FAILED", "1")

            assert run_plan("check", str(tmp_project), json_output=False) == 0

        assert runner_class.call_args.kwargs["rerun_failed"] is True

    @pytest.mark.parametrize("value", ["0", "true", "yes", "2"])
    def test_run_plan_ignores_other_env_values(
        self,
        tmp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
        value: str,
    ) -> None:
        result = RunResult(success=True, run_id="run", plan_name="check")
        with patch("lib.cicd.runner.DeterministicRunner") as runner_class:
            runner_class.return_value.run.return_value = result
            monkeypatch.setenv("CPP_GATE_RERUN_FAILED", value)

            assert run_plan("check", str(tmp_project), json_output=False) == 0

        assert runner_class.call_args.kwargs["rerun_failed"] is False


class TestBuildStepEnv:
    def test_strips_pythonpath(self):
        with patch.dict(os.environ, {"PYTHONPATH": "/runner/lib", "HOME": "/home/test"}):
            env = _build_step_env()
            assert "PYTHONPATH" not in env
            assert env["HOME"] == "/home/test"

    def test_defaults_uv_cache_dir(self):
        env_without_uv = {k: v for k, v in os.environ.items() if k != "UV_CACHE_DIR"}
        with patch.dict(os.environ, env_without_uv, clear=True):
            env = _build_step_env()
            assert env["UV_CACHE_DIR"] == "/tmp/uv-cache"

    def test_preserves_explicit_uv_cache_dir(self):
        with patch.dict(os.environ, {"UV_CACHE_DIR": "/custom/cache"}):
            env = _build_step_env()
            assert env["UV_CACHE_DIR"] == "/custom/cache"

    def test_strips_parent_venv_leakage(self):
        """Inherited VIRTUAL_ENV / PYTHONHOME must not reach child steps (#534)."""
        with patch.dict(
            os.environ,
            {"VIRTUAL_ENV": "/parent/.venv", "PYTHONHOME": "/parent/home"},
        ):
            env = _build_step_env()
            assert "VIRTUAL_ENV" not in env
            assert "PYTHONHOME" not in env

    def test_pins_uv_python_to_project_floor(self, tmp_path: Path):
        """UV_PYTHON defaults to the target project's requires-python floor (#534)."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nrequires-python = ">=3.12"\n'
        )
        env_without = {k: v for k, v in os.environ.items() if k != "UV_PYTHON"}
        with patch.dict(os.environ, env_without, clear=True):
            env = _build_step_env(tmp_path)
            assert env["UV_PYTHON"] == "3.12"

    def test_uv_python_explicit_wins(self, tmp_path: Path):
        """An explicit UV_PYTHON is never overridden by the derived floor."""
        (tmp_path / "pyproject.toml").write_text('requires-python = ">=3.11"\n')
        with patch.dict(os.environ, {"UV_PYTHON": "3.13"}):
            env = _build_step_env(tmp_path)
            assert env["UV_PYTHON"] == "3.13"

    def test_no_uv_python_when_floor_unknown(self, tmp_path: Path):
        """No pyproject / no requires-python -> UV_PYTHON left unset, not guessed."""
        env_without = {k: v for k, v in os.environ.items() if k != "UV_PYTHON"}
        with patch.dict(os.environ, env_without, clear=True):
            env = _build_step_env(tmp_path)  # empty dir
            assert "UV_PYTHON" not in env

    def test_build_step_env_is_pure_no_offline_probe(self):
        """_build_step_env must not materialize CPP_OFFLINE (stays network-free)."""
        env_without = {k: v for k, v in os.environ.items() if k != "CPP_OFFLINE"}
        with patch.dict(os.environ, env_without, clear=True):
            env = _build_step_env()
            assert "CPP_OFFLINE" not in env


class TestSandboxHelpers:
    def test_project_python_floor_parses_requires_python(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('requires-python = ">=3.11,<3.14"\n')
        assert _project_python_floor(tmp_path) == "3.11"

    def test_project_python_floor_missing_pyproject(self, tmp_path: Path):
        assert _project_python_floor(tmp_path) is None

    def test_project_python_floor_none_root(self):
        assert _project_python_floor(None) is None

    def test_is_offline_honors_env_override(self):
        with patch.dict(os.environ, {"CPP_OFFLINE": "1"}):
            assert _is_offline() is True
        with patch.dict(os.environ, {"CPP_OFFLINE": "0"}):
            assert _is_offline() is False

    def test_offline_flag_skips_network_step(self, tmp_project: Path):
        """With CPP_OFFLINE=1 the deploy stale-commit (git fetch) step skips (#534)."""
        stale = {s.id: s for s in BUILTIN_PLANS["deploy"]}["stale_commit_check"]
        step = ShellStep(stale)
        ctx_offline = {"project_root": str(tmp_project), "env": {"CPP_OFFLINE": "1"}}
        assert step.should_skip(ctx_offline) is True


class TestStepDefinitionsSandboxAware:
    """The security/import steps derive PYTHONPATH from the CPP checkout, not a
    hardcoded ${HOME} path that breaks under a sandbox / alternate checkout (#534)."""

    def test_finish_security_scan_dehardcoded(self):
        step = {s.id: s for s in BUILTIN_PLANS["finish"]}["security_scan"]
        assert "Projects/claude-power-pack" not in step.command
        assert "Projects/claude-power-pack" not in (step.skip_if or "")
        assert step.env.get("PYTHONPATH") == _CPP_ROOT

    def test_deploy_bootstrap_check_path_fixed(self):
        """bootstrap_check previously pointed PYTHONPATH at .../lib (wrong for
        -m lib.cicd.bootstrap); it now derives the parent-of-lib root."""
        step = {s.id: s for s in BUILTIN_PLANS["deploy"]}["bootstrap_check"]
        assert step.command == "python3 -m lib.cicd.bootstrap check"
        assert step.env.get("PYTHONPATH") == _CPP_ROOT

    @pytest.mark.skipif(shutil.which("sh") is None, reason="requires sh")
    @pytest.mark.parametrize(
        "marker", ["pyproject.toml", "requirements.txt", "setup.py"]
    )
    def test_deploy_bootstrap_check_runs_for_python_project_without_config(
        self, tmp_project: Path, marker: str
    ):
        config_path = tmp_project / ".claude" / "bootstrap.yaml"
        assert not config_path.exists()
        (tmp_project / marker).write_text("")
        step = ShellStep(
            {s.id: s for s in BUILTIN_PLANS["deploy"]}["bootstrap_check"]
        )

        assert (
            step.should_skip({"project_root": str(tmp_project), "env": {}}) is False
        )

    @pytest.mark.skipif(shutil.which("sh") is None, reason="requires sh")
    def test_deploy_bootstrap_check_skips_without_config_or_python_markers(
        self, tmp_project: Path
    ):
        relevant_files = (
            ".claude/bootstrap.yaml",
            "pyproject.toml",
            "requirements.txt",
            "setup.py",
        )
        assert all(not (tmp_project / path).exists() for path in relevant_files)
        step = ShellStep(
            {s.id: s for s in BUILTIN_PLANS["deploy"]}["bootstrap_check"]
        )

        assert (
            step.should_skip({"project_root": str(tmp_project), "env": {}}) is True
        )

    def test_deploy_security_scan_dehardcoded(self):
        step = {s.id: s for s in BUILTIN_PLANS["deploy"]}["security_scan"]
        assert "Projects/claude-power-pack" not in step.command
        assert step.env.get("PYTHONPATH") == _CPP_ROOT

    def test_cpp_root_is_parent_of_lib(self):
        """_CPP_ROOT must be the parent of lib/ so `-m lib.security` resolves."""
        assert (Path(_CPP_ROOT) / "lib" / "security").exists() or (
            Path(_CPP_ROOT) / "lib"
        ).is_dir()


class TestPlansCoverCITemplates:
    """The `finish` gate's contract is that a green gate means a green CI, so its
    make-target steps must cover every `make <target>` the shipped CI templates
    run. `typecheck` was missing for months: the plan reported ok, the PR opened,
    and CI went red on a step the local gate never ran (issue #617, hit twice in
    agentic-poker). These tests pin the invariant, not just the one missing step."""

    CI_TEMPLATES = (
        "templates/workflows/ci-python.yml",
        "templates/workflows/ci-node.yml",
        "templates/workflows/woodpecker-python.yml",
        "templates/workflows/woodpecker-node.yml",
    )

    @staticmethod
    def _make_targets(plan_name: str) -> set[str]:
        """The Makefile targets a plan invokes (`make X`, anywhere in the step
        command). The #628 gate steps embed `make <target>` inside a
        make-or-`uv run` fallback (`if grep ...; then make lint; else uv ...`),
        so a plain ``startswith('make ')`` no longer sees them - the invariant is
        that the plan still runs the CI target when the Makefile has it, wherever
        it sits in the command."""
        pat = re.compile(r"\bmake\s+([A-Za-z0-9_.-]+)")
        return {
            target
            for step in BUILTIN_PLANS[plan_name]
            for target in pat.findall(step.command)
        }

    def _ci_targets(self) -> set[str]:
        """Every `make <target>` the shipped CI templates run."""
        targets: set[str] = set()
        for rel in self.CI_TEMPLATES:
            path = Path(_CPP_ROOT) / rel
            if not path.is_file():
                continue
            for line in path.read_text().splitlines():
                stripped = line.strip().lstrip("-").strip()
                if stripped.startswith("run:"):
                    stripped = stripped[len("run:") :].strip()
                if stripped.startswith("make "):
                    targets.add(stripped.split()[1])
        return targets

    def test_ci_templates_are_readable(self):
        """Guard the guard: an empty set would make the coverage test vacuous."""
        assert self._ci_targets(), "no `make` targets parsed from the CI templates"

    def test_finish_plan_covers_every_ci_make_target(self):
        missing = self._ci_targets() - self._make_targets("finish")
        assert not missing, (
            f"CI runs make targets the 'finish' plan never runs: {sorted(missing)}. "
            "A gate that omits a hard CI step reports green on a tree CI rejects (#617)."
        )

    def test_check_plan_covers_every_ci_make_target(self):
        missing = self._ci_targets() - self._make_targets("check")
        assert not missing, (
            f"CI runs make targets the 'check' plan never runs: {sorted(missing)} (#617)."
        )

    @pytest.mark.parametrize("plan_name", ["finish", "check"])
    def test_typecheck_step_present_and_guarded(self, plan_name: str):
        """The skip_if guard is what makes shipping this by default safe: a repo
        with no `typecheck:` target AND no configured mypy skips it, but one that
        configures mypy in pyproject now runs it via `uv run` (issue #628)."""
        step = {s.id: s for s in BUILTIN_PLANS[plan_name]}.get("typecheck")
        assert step is not None, f"'{plan_name}' plan has no typecheck step (#617)"
        # Prefers the Makefile target, falls back to the pyproject-configured tool.
        assert "make typecheck" in step.command
        assert "uv run --extra dev mypy" in step.command
        # Skips ONLY when neither a Makefile target nor mypy config exists (#628).
        assert step.skip_if is not None
        assert '! grep -q "^typecheck:" Makefile 2>/dev/null' in step.skip_if
        assert "mypy" in step.skip_if
        assert step.max_attempts == 1

    def test_typecheck_skips_when_no_target_and_no_tool(self, tmp_project: Path):
        """No Makefile target and no pyproject mypy config -> the gate skips (#628)."""
        (tmp_project / "Makefile").write_text("lint:\n\techo lint\n")
        step = ShellStep({s.id: s for s in BUILTIN_PLANS["finish"]}["typecheck"])
        assert step.should_skip({"project_root": str(tmp_project), "env": {}}) is True

    def test_typecheck_runs_when_pyproject_configures_mypy(self, tmp_project: Path):
        """pyproject configures mypy but there is no Makefile at all: the gate no
        longer skips - it falls back to `uv run --extra dev mypy` (issue #628)."""
        (tmp_project / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n")
        step = ShellStep({s.id: s for s in BUILTIN_PLANS["finish"]}["typecheck"])
        assert step.should_skip({"project_root": str(tmp_project), "env": {}}) is False

    def test_typecheck_runs_when_makefile_has_target(self, tmp_project: Path):
        (tmp_project / "Makefile").write_text("typecheck:\n\techo typecheck\n")
        step = ShellStep({s.id: s for s in BUILTIN_PLANS["finish"]}["typecheck"])
        assert step.should_skip({"project_root": str(tmp_project), "env": {}}) is False

    def test_typecheck_runs_before_security_scan(self):
        """Order matters for the report: the cheap deterministic gates run first,
        so a type error is surfaced before the security scan's output buries it."""
        ids = [s.id for s in BUILTIN_PLANS["finish"]]
        assert ids.index("typecheck") < ids.index("security_scan")
        assert ids.index("test") < ids.index("typecheck")


class TestFinishGateFallbackParity:
    """scripts/flow-finish-gate.sh's Makefile fallback (used when uv or the CPP
    checkout is unavailable) must run every gate the plan it degrades from runs -
    otherwise the #617 false green survives on every repo that lands in the
    fallback. Since #628 each gate is invoked through a generic helper that
    prefers the Makefile target, falls back to `uv run --extra dev`, and skips
    (warn) only when neither exists."""

    def test_fallback_runs_every_finish_plan_gate(self):
        gate = Path(_CPP_ROOT) / "scripts" / "flow-finish-gate.sh"
        if not gate.is_file():
            pytest.skip("flow-finish-gate.sh not present in this checkout")
        body = gate.read_text()
        gate_ids = [s.id for s in BUILTIN_PLANS["finish"] if s.id in GATE_STEP_IDS]
        assert gate_ids, "the finish plan defines no gate steps - test is vacuous"
        # The generic helper prefers the target, falls back to uv, records failure.
        assert 'grep -q "^${id}:" Makefile 2>/dev/null' in body
        assert 'make "${id}" || FAILED=1' in body
        assert "uv run --extra dev ${uvargs} || FAILED=1" in body
        for gid in gate_ids:
            assert f"run_fallback_gate {gid} " in body, (
                f"fallback never runs the '{gid}' gate (#617/#628)"
            )


class TestSkippedSuiteReporting:
    """A test step that exits 0 having executed nothing must not be reported as a
    bare SUCCESS (issue #621). pytest exits 0 when every test skips, so the plan
    used to report `completed successfully` for a gate that proved nothing - the
    agentic-poker run where the 66 skipped tests were the acceptance tests for
    the change being gated. Counts are surfaced; exit status is unchanged."""

    def _steps(self, summary: str):
        # A fake test step: echoes a runner summary line, exits 0 - exactly the
        # shape the bug rides on.
        return [StepDef(id="test", command=f"echo '{summary}'", timeout_seconds=30)]

    def test_all_skipped_run_is_qualified_not_bare_success(self, tmp_project: Path):
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        result = runner.run("check", step_defs=self._steps("== 66 skipped in 0.42s =="))

        # Still a success - the fix surfaces the hole, it does not invent a gate.
        assert result.success
        assert result.tests["test"]["skipped"] == 66
        assert result.tests["test"]["executed"] == 0
        assert result.warnings, "an all-skipped test step must record a warning"
        assert "executed NO tests" in result.warnings[0]

        text = log.getvalue()
        assert "NO TESTS RAN" in text
        assert "completed WITH WARNINGS" in text
        assert "completed successfully" not in text

    def test_no_tests_ran_is_also_qualified(self, tmp_project: Path):
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=self._steps("== no tests ran in 0.01s =="))
        assert result.success
        assert result.warnings

    def test_counts_are_surfaced_when_tests_did_run(self, tmp_project: Path):
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        result = runner.run(
            "check", step_defs=self._steps("== 312 passed, 66 skipped in 55.69s ==")
        )
        assert result.success
        assert result.tests["test"] == {
            "passed": 312,
            "failed": 0,
            "skipped": 66,
            "errors": 0,
            "executed": 312,
            "framework": "pytest",
            # Additive (kyle issue #838): one summary parsed, none of them
            # empty. The gate helper reads this dict, so the shape is pinned
            # here deliberately rather than left to drift.
            "invocations": 1,
            "empty_invocations": 0,
        }
        # Some tests DID run, so this is a real green - no warning, no
        # "WITH WARNINGS" banner, but the counts are visible either way.
        assert not result.warnings
        text = log.getvalue()
        assert "test: SUCCESS (312 passed, 66 skipped)" in text
        assert "completed successfully" in text

    def test_an_empty_invocation_warns_even_when_the_total_ran(
        self, tmp_project: Path
    ):
        """A step running the runner TWICE, where one invocation collected
        nothing (kyle issue #838).

        This is the case #621's guard exists for and could not see. The total
        executed 102, so `nothing_ran` is False and the original warning stays
        silent - while half the gate proved nothing. Summing the summaries
        alone does not fix it: the honest total is still 102 and still not
        zero. The guard has to know that an INVOCATION was empty.

        DO NOT DELETE THIS AS REDUNDANT WITH THE AGGREGATION TESTS. It is the
        only thing separating this fix from the simplification a reviewer
        would reasonably propose - "just sum the summaries". It was observed
        red TWICE during development: once against the old last-wins parser,
        and again after aggregation was working correctly, where the counts
        were already right (`invocations: 2, empty_invocations: 1`) and
        `warnings` was still empty. That second red is the whole point. An
        aggregate-only implementation reports 4,218 honestly, passes every
        other test in this file, looks complete, and ships #621's guard as
        blind as it was before any of this.
        """
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)

        result = runner.run(
            "check",
            step_defs=self._steps(
                "== no tests ran in 0.01s ==\n== 102 passed in 5.00s =="
            ),
        )

        assert result.success
        assert result.tests["test"]["executed"] == 102
        assert result.tests["test"]["invocations"] == 2
        assert result.tests["test"]["empty_invocations"] == 1
        assert result.warnings, (
            "an invocation that executed nothing must be reported even when "
            "the step's total is healthy (kyle issue #838)"
        )
        assert "1 of 2" in result.warnings[0]

    def test_suite_that_skips_nothing_is_unchanged(self, tmp_project: Path):
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        result = runner.run("check", step_defs=self._steps("== 312 passed in 55.69s =="))
        assert result.success
        assert not result.warnings
        assert "WITH WARNINGS" not in log.getvalue()
        assert "warnings" not in result.to_dict()

    def test_non_test_step_carries_no_counts(self, tmp_project: Path):
        steps = [
            StepDef(id="lint", command="echo '== 9 skipped in 0.1s =='", timeout_seconds=30),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)
        assert result.success
        assert result.tests == {}
        assert not result.warnings

    def test_counts_persist_to_state_on_failure(self, tmp_project: Path):
        steps = [
            StepDef(
                id="test",
                command="echo '== 2 failed, 8 passed, 3 skipped in 1.0s =='; exit 1",
                timeout_seconds=30,
            ),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        assert not result.success
        assert result.tests["test"]["failed"] == 2
        state = RunState.load(result.run_id, tmp_project)
        assert state.summary()["steps"][0]["tests"]["skipped"] == 3

    def test_state_file_without_tests_field_still_loads(self, tmp_project: Path):
        """State written before #621 (no `tests` key) must still resume."""
        legacy = {
            "step_id": "test",
            "status": "success",
            "exit_code": 0,
            "output": "",
            "error": None,
            "started_at": None,
            "finished_at": None,
            "attempt": 1,
            "max_attempts": 1,
        }
        record = StepRecord.from_dict(dict(legacy))
        assert record.tests is None


class TestSkippedGateReporting:
    """A quality gate (lint/test/typecheck) that skip_if-skipped verified nothing
    about the change, so the runner must not print a bare `completed
    successfully` - it names the skipped gates and carries them in
    RunResult.skipped_steps for flow-finish-gate.sh to surface as `warn`
    (issue #628). A skipped NON-gate step (security_scan) is a legitimate skip
    and must NOT trip the warning."""

    @staticmethod
    def _always_skip(step_id: str) -> StepDef:
        # skip_if 'true' always skips - mimics a Makefile-less repo with the tool
        # unconfigured (the real skip_if resolves to the same outcome there).
        return StepDef(id=step_id, command="false", skip_if="true", timeout_seconds=30)

    @staticmethod
    def _always_run(step_id: str) -> StepDef:
        return StepDef(id=step_id, command="true", timeout_seconds=30)

    def test_skipped_gates_qualify_the_run(self, tmp_project: Path):
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        result = runner.run(
            "check",
            step_defs=[
                self._always_skip("lint"),
                self._always_skip("test"),
                self._always_skip("typecheck"),
            ],
        )
        # A skip is exit 0 - the fix surfaces the hole, it does not invent a gate.
        assert result.success
        assert result.skipped_steps == ["lint", "test", "typecheck"]
        assert result.to_dict()["skipped"] == ["lint", "test", "typecheck"]

        text = log.getvalue()
        assert "completed WITH WARNINGS" in text
        assert "SKIPPED GATES: lint, test, typecheck" in text
        assert "completed successfully" not in text

    def test_all_gates_run_is_bare_success(self, tmp_project: Path):
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        result = runner.run(
            "check",
            step_defs=[self._always_run(i) for i in ("lint", "test", "typecheck")],
        )
        assert result.success
        assert result.skipped_steps == []
        assert "skipped" not in result.to_dict()

        text = log.getvalue()
        assert "completed successfully" in text
        assert "WITH WARNINGS" not in text

    def test_non_gate_skip_does_not_warn(self, tmp_project: Path):
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        result = runner.run(
            "finish",
            step_defs=[self._always_run("lint"), self._always_skip("security_scan")],
        )
        assert result.success
        # The skip is recorded, but security_scan is not a gate - no false green.
        assert result.skipped_steps == ["security_scan"]

        text = log.getvalue()
        assert "completed successfully" in text
        assert "SKIPPED GATES" not in text

    def test_skipped_gate_and_no_tests_both_named(self, tmp_project: Path):
        """When a gate skips AND a test step ran nothing (#621), the closing line
        carries both qualifiers, not just one."""
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        result = runner.run(
            "check",
            step_defs=[
                StepDef(
                    id="test",
                    command="echo '== 66 skipped in 0.4s =='",
                    timeout_seconds=30,
                ),
                self._always_skip("typecheck"),
            ],
        )
        assert result.success
        assert result.skipped_steps == ["typecheck"]
        assert result.warnings  # the #621 no-tests warning
        text = log.getvalue()
        assert "SKIPPED GATES: typecheck" in text
        assert "#621" in text


class TestResumedRunReportsWhatActuallyRan:
    """The runner must record where THIS invocation began (issue #838 f/u).

    ``TestCarriedOverStepsAreMarked`` in test_runner_state.py pins the summary
    rendering; this pins the half that feeds it. Without ``_executed_from`` the
    marking has nothing to key on, so both are needed and neither is redundant:
    a summary that can mark correctly, given a number nobody supplies, marks
    nothing.
    """

    def test_a_resumed_run_records_the_step_it_started_at(self, tmp_project: Path):
        steps = [
            StepDef(id="lint", command="echo 'lint ok'", timeout_seconds=30),
            StepDef(id="bad_step", command="exit 1", timeout_seconds=30),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        first = runner.run("check", step_defs=steps)
        assert not first.success

        fixed = [
            StepDef(id="lint", command="echo 'lint ok'", timeout_seconds=30),
            StepDef(id="bad_step", command="echo 'fixed'", timeout_seconds=30),
        ]
        second = runner.run("check", step_defs=fixed)
        assert second.success

        # The resume began at step 2 (index 1), so lint did NOT run this time.
        assert runner._executed_from == 1

        # Read from the RESULT, not from state: a successful run deletes its
        # state file, which is precisely why this detail has to be captured
        # before cleanup rather than loaded back afterwards.
        assert second.carried_from_previous_run == ["lint"]
        lint = second.step_details[0]
        assert lint["status"] == "success"
        assert lint["carried_from_previous_run"] is True, (
            "lint succeeded in the FIRST invocation and was not re-run here. "
            "Reporting it identically to a step that just passed is how a "
            "stale lint result was carried across a tree change (#838 f/u)."
        )

    def test_the_state_file_is_gone_on_success_so_detail_must_be_captured(
        self, tmp_project: Path
    ):
        """Pins WHY the capture happens before cleanup.

        This is the constraint that made the obvious implementation - read the
        state back in run_plan and annotate it - a silent no-op on exactly the
        green resumed run it was written for. Without this test the next person
        reverts the capture as redundant and the feature quietly stops working
        on the success path while every unit test still passes.
        """
        steps = [StepDef(id="only", command="echo ok", timeout_seconds=30)]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)
        assert result.success

        with pytest.raises(FileNotFoundError):
            RunState.load(result.run_id, tmp_project)
        assert result.step_details, (
            "a successful run must carry its own step detail - there is no "
            "state file left to read it from"
        )

    def test_a_fresh_run_starts_at_zero_and_marks_nothing(self, tmp_project: Path):
        """The guard rail: every step of a from-scratch run really did run."""
        steps = [StepDef(id="only", command="echo ok", timeout_seconds=30)]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)
        assert result.success
        assert runner._executed_from == 0
        assert result.carried_from_previous_run == []
        for entry in result.step_details:
            assert "carried_from_previous_run" not in entry

    def test_the_resume_names_the_steps_it_will_not_run(self, tmp_project: Path):
        """The human half. The JSON marking serves a reader parsing it; the log
        line serves the far more common reader who is watching the gate scroll
        past and has no reason to suspect anything."""
        steps = [
            StepDef(id="lint", command="echo 'lint ok'", timeout_seconds=30),
            StepDef(id="bad_step", command="exit 1", timeout_seconds=30),
        ]
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        runner.run("check", step_defs=steps)

        fixed = [
            StepDef(id="lint", command="echo 'lint ok'", timeout_seconds=30),
            StepDef(id="bad_step", command="echo 'fixed'", timeout_seconds=30),
        ]
        resume_log = StringIO()
        runner2 = DeterministicRunner(project_root=tmp_project, output=resume_log)
        runner2.run("check", step_defs=fixed)

        text = resume_log.getvalue()
        assert "will NOT run in this invocation" in text
        assert "lint" in text


class TestATimeoutIsNotAFailure:
    """A step killed by its budget must not report as a step that failed (#812).

    Measured cause: the `test` step's budget was 600s while kyle's `make test`
    needed ~620s — the first pytest invocation alone took 457s and the
    Playwright half another ~160s. The step was killed at 91% of the second and
    reported FAILED, so the gate said a suite was broken when it had simply not
    finished. Someone triaging that debugs tests that were still running.

    Note the budget is per STEP, not per invocation: one step's command may run
    pytest several times, and a number sized by watching one of them is wrong by
    construction. That is how 600 came to be under the real cost.

    Raising the number does not fix this - it only moves the cliff, because a
    suite grows every merge and no constant tracks that. What fixes it is that
    the two outcomes are now distinguishable.
    """

    def test_a_timed_out_step_is_reported_as_a_timeout_not_a_failure(
        self, tmp_project: Path
    ):
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        result = runner.run(
            "check",
            step_defs=[StepDef(id="test", command="sleep 5", timeout_seconds=1)],
        )
        assert not result.success
        assert result.timed_out_step == "test"
        assert result.timed_out_after == 1

        text = log.getvalue()
        assert "TIMED OUT" in text
        assert "FAILED (exit" not in text, (
            "reporting a timeout as FAILED is the defect - it sends a reader to "
            "debug a suite that never finished (#812)"
        )

    def test_the_timeout_reaches_the_json_the_gate_parses(self, tmp_project: Path):
        """A field that never reaches the report cannot be acted on, however
        carefully it was set. `to_dict` is the gate's only view of the run, and
        omitting it there was a real bug in the first draft of this change."""
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run(
            "check",
            step_defs=[StepDef(id="test", command="sleep 5", timeout_seconds=1)],
        )
        payload = result.to_dict()
        assert payload["timed_out_step"] == "test"
        assert payload["timed_out_after"] == 1

    def test_a_genuine_failure_is_still_a_failure(self, tmp_project: Path):
        """The guard rail. A change that called everything a timeout would pass
        the assertions above while destroying the distinction they exist for."""
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        result = runner.run(
            "check",
            step_defs=[StepDef(id="test", command="exit 1", timeout_seconds=30)],
        )
        assert not result.success
        assert result.timed_out_step is None
        assert "timed_out_step" not in result.to_dict()
        assert "FAILED (exit 1)" in log.getvalue()
        assert "TIMED OUT" not in log.getvalue()

    def test_the_targeted_rerun_does_not_fire_for_a_timeout(self, tmp_project: Path):
        """#769 re-runs a step against only its FAILED ids. A timed-out step has
        no failed ids - it has an unfinished run - so re-running it burns the
        budget again and can only time out a second time."""
        log = StringIO()
        runner = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        )
        runner.run(
            "check",
            step_defs=[StepDef(id="test", command="sleep 5", timeout_seconds=1)],
        )
        assert "RE-RUNNING" not in log.getvalue()


class TestTestStepBudgetIsConfigurable:
    """The budget must be raisable without editing the source (#812).

    Nobody edits a vendored file mid-incident, and an edit does not survive an
    update. The number will be wrong again as the suite grows, so the escape
    hatch is part of the fix rather than a convenience.
    """

    def test_the_env_override_is_used(self, monkeypatch):
        from lib.cicd.steps import _test_step_timeout

        monkeypatch.setenv("CPP_GATE_TEST_TIMEOUT", "42")
        assert _test_step_timeout() == 42

    def test_a_nonsense_override_falls_back_rather_than_crashing(self, monkeypatch):
        """Fail-safe, not fail-closed: a typo'd budget must not stop the gate
        running, and must not silently become zero (which would time out
        instantly and look like a hung suite)."""
        from lib.cicd.steps import DEFAULT_TEST_STEP_TIMEOUT, _test_step_timeout

        for bad in ("not-a-number", "", "0", "-5"):
            monkeypatch.setenv("CPP_GATE_TEST_TIMEOUT", bad)
            assert _test_step_timeout() == DEFAULT_TEST_STEP_TIMEOUT

    def test_the_default_exceeds_the_cost_that_caused_this_issue(self):
        """600s was already under the ~620s the suite needed when #812 was
        filed. A default that is wrong on the day it ships is the bug."""
        from lib.cicd.steps import DEFAULT_TEST_STEP_TIMEOUT

        assert DEFAULT_TEST_STEP_TIMEOUT > 620


@requires_git
class TestResumeDiscardsWhenTreeChanged:
    """Issue #804: resume is correct for a crash (tree unchanged) and wrong
    for a repair (tree changed - the usual reason to resume at all). The
    runner now tells them apart by comparing compute_tree_signature() at
    persist time and at resume time, rather than assuming a resume is always
    a crash.
    """

    def _steps(self, test_cmd: str) -> list[StepDef]:
        return [
            StepDef(id="lint", command="echo 'lint ok'", timeout_seconds=30),
            StepDef(id="test", command=test_cmd, timeout_seconds=30),
        ]

    def test_discards_and_reruns_every_step_when_the_tree_changed(
        self, tmp_project: Path
    ):
        """The core #804 regression pin.

        Proving invalidation alone is not enough - a test that only checks
        the state file is gone would pass against an implementation that
        discards the state and then somehow still skips a step. This asserts
        three things: the signatures actually differ (negative-fixture
        precondition), the resumable state was discarded rather than
        resumed, and 'lint' - step 1, the one a real repair loop almost
        always edits - actually RE-EXECUTED in the second invocation.
        """
        _git_repo(tmp_project)
        (tmp_project / "src.py").write_text("x = 1\n")

        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        before_sig = compute_tree_signature(tmp_project)
        first = runner.run("finish", step_defs=self._steps("exit 1"))
        assert not first.success

        # The "fix": edit the same tracked file a repair loop would touch,
        # and make the failing step pass - the same observable facts a real
        # source-level fix produces.
        (tmp_project / "src.py").write_text("x = 2  # fixed\n")
        after_sig = compute_tree_signature(tmp_project)
        # Precondition: this fixture is only a valid negative case if the
        # tree actually changed. Assert that BEFORE trusting anything the
        # discard logic does with it.
        assert before_sig is not None and after_sig is not None
        assert before_sig != after_sig

        runner2 = DeterministicRunner(project_root=tmp_project, output=log)
        second = runner2.run("finish", step_defs=self._steps("echo 'test ok'"))

        assert second.success
        assert second.carried_from_previous_run == [], (
            "lint must NOT be carried - the tree changed since it last ran"
        )
        lint_entry = next(s for s in second.step_details if s["id"] == "lint")
        assert lint_entry.get("carried_from_previous_run") is not True
        assert "executed_in_this_run" not in lint_entry, (
            "a step that genuinely re-ran this invocation carries neither "
            "marking - see TestCarriedOverStepsAreMarked in test_runner_state.py"
        )
        first_line = log.getvalue().splitlines()[0]
        assert first_line.startswith("Starting plan"), (
            f"first line must read 'Starting plan', never 'Resuming failed "
            f"run' - a resumed-looking first line on a run that actually "
            f"re-ran everything is the exact false signal #804 is about; "
            f"got: {first_line!r}"
        )
        assert "Discarding resumable run" in log.getvalue()

    def test_resumes_and_carries_lint_when_the_tree_is_unchanged(
        self, tmp_project: Path
    ):
        """The crash-safety regression guard - the mirror of the test above.

        If this stops passing, the #804 fix removed the feature the issue
        explicitly says not to break: a genuine crash (nothing about the
        tree changed) must still resume, still carry the untouched step's
        result, and must NOT re-run it.
        """
        _git_repo(tmp_project)

        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        before_sig = compute_tree_signature(tmp_project)
        first = runner.run("finish", step_defs=self._steps("exit 1"))
        assert not first.success

        # Simulated crash: NOTHING about the tree changes between attempts.
        after_sig = compute_tree_signature(tmp_project)
        # Precondition: this fixture is only a valid positive case if the
        # tree genuinely did not change.
        assert before_sig is not None and after_sig is not None
        assert before_sig == after_sig

        runner2 = DeterministicRunner(project_root=tmp_project, output=log)
        second = runner2.run("finish", step_defs=self._steps("echo 'test ok'"))

        assert second.success
        assert second.carried_from_previous_run == ["lint"]
        assert second.tree_verified is True
        lint_entry = next(s for s in second.step_details if s["id"] == "lint")
        assert lint_entry["carried_from_previous_run"] is True
        assert lint_entry["executed_in_this_run"] is False
        assert "Resuming failed run" in log.getvalue()
        assert "Discarding resumable run" not in log.getvalue()

    def test_falls_back_to_unconditional_resume_when_unverifiable(
        self, tmp_project: Path
    ):
        """No git repo -> compute_tree_signature() returns None on both
        sides -> today's pre-#804 behavior (resume unconditionally), so a
        non-git target project does not regress. tree_verified=False is the
        signal flow-finish-gate.sh's fallback check depends on."""
        # Deliberately NOT a git repo.
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        first = runner.run("finish", step_defs=self._steps("exit 1"))
        assert not first.success

        runner2 = DeterministicRunner(project_root=tmp_project, output=log)
        second = runner2.run("finish", step_defs=self._steps("echo 'test ok'"))

        assert second.success
        assert second.carried_from_previous_run == ["lint"]
        assert second.tree_verified is False
        assert "Discarding resumable run" not in log.getvalue()
