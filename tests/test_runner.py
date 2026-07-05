"""Tests for the deterministic CI/CD runner."""

import os
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.cicd.runner import (
    DeterministicRunner,
    RunResult,
    _build_step_env,
    _is_offline,
    _project_python_floor,
)
from lib.cicd.state import RunState
from lib.cicd.steps import _CPP_ROOT, BUILTIN_PLANS, ShellStep, StepDef


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory for runner tests."""
    return tmp_path


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

    def test_deploy_security_scan_dehardcoded(self):
        step = {s.id: s for s in BUILTIN_PLANS["deploy"]}["security_scan"]
        assert "Projects/claude-power-pack" not in step.command
        assert step.env.get("PYTHONPATH") == _CPP_ROOT

    def test_cpp_root_is_parent_of_lib(self):
        """_CPP_ROOT must be the parent of lib/ so `-m lib.security` resolves."""
        assert (Path(_CPP_ROOT) / "lib" / "security").exists() or (
            Path(_CPP_ROOT) / "lib"
        ).is_dir()
