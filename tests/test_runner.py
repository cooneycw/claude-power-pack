"""Tests for the deterministic CI/CD runner."""

import os
import re
import shutil
import stat
import subprocess
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.cicd.runner import (
    MAX_RERUN_IDS,
    RERUN_PASSED_IN_ISOLATION,
    DeterministicRunner,
    RunResult,
    _build_step_env,
    _ensure_private_dir,
    _is_offline,
    _project_python_floor,
    run_plan,
)
from lib.cicd.state import RunState, StepRecord, compute_tree_signature
from lib.cicd.steps import (
    _CPP_ROOT,
    BUILTIN_PLANS,
    FALLBACK_UNRUNNABLE_GATES,
    GATE_STEP_IDS,
    ShellStep,
    StepDef,
)


def _expected_uv_cache_dir() -> Path:
    """The per-uid cache path `_build_step_env` must default to (issue #1113).

    Derived the same way the runner derives it rather than spelled out, so this
    helper cannot pin a path the code stopped using. The PROPERTIES - uid in the
    name, under the temp dir, stable across calls - are asserted separately in
    TestBuildStepEnv; this is only the equality the older tests already made.
    """
    return Path(tempfile.gettempdir()) / f"uv-cache-{os.getuid()}"


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory for runner tests."""
    return tmp_path


requires_make = pytest.mark.skipif(
    shutil.which("make") is None, reason="requires make on PATH"
)


def _not_run_ids(result) -> list[str]:
    """Gate ids the run recorded NOT-RUN, read the way the shell reads them.

    `flow-finish-gate.sh` takes these from the per-step records, so the tests
    ask the same question of the same artifact rather than a field invented for
    their convenience.
    """
    return sorted(
        d["id"] for d in result.step_details if d.get("status") == "not-run"
    )


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
        assert env_file.read_text().strip() == str(_expected_uv_cache_dir())

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

    def test_a_failure_is_named_even_with_reruns_off(self, tmp_project: Path) -> None:
        """Issue #1258: "1 failed" without an id cannot be acted on.

        Ids were read only on the re-run path, so with re-runs off - or a step
        the re-run does not apply to - the JSON carried a count and no name,
        and the only way to learn which test failed was another full run.
        """
        step = StepDef(
            id="test",
            command=(
                "printf '=== 1 failed, 3 passed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; exit 1"
            ),
            timeout_seconds=30,
        )
        result = DeterministicRunner(
            project_root=tmp_project, output=StringIO()
        ).run("check", step_defs=[step])

        assert not result.success
        assert result.reruns == []
        assert result.to_dict()["tests"]["test"]["failed_ids"] == ["tests/a.py::t1"]

    def test_too_many_failures_to_rerun_are_still_named(self, tmp_project: Path) -> None:
        ids = [f"tests/a.py::t{i}" for i in range(30)]
        lines = "".join(f"printf 'FAILED {i} - E\\n'; " for i in ids)
        step = StepDef(
            id="test",
            command=f"printf '=== 30 failed in 0.01s ===\\n'; {lines}exit 1",
            timeout_seconds=30,
        )
        result = DeterministicRunner(
            project_root=tmp_project, output=StringIO(), rerun_failed=True
        ).run("check", step_defs=[step])

        assert result.reruns == []  # over MAX_RERUN_IDS: no re-run
        assert result.to_dict()["tests"]["test"]["failed_ids"] == ids

    def test_an_unnameable_failure_says_so_rather_than_omitting_the_field(
        self, tmp_project: Path
    ) -> None:
        step = StepDef(
            id="test",
            command="printf '=== 1 failed in 0.01s ===\\n'; exit 1",
            timeout_seconds=30,
        )
        result = DeterministicRunner(
            project_root=tmp_project, output=StringIO()
        ).run("check", step_defs=[step])

        assert result.to_dict()["tests"]["test"]["failed_ids"] == []

    def test_a_passing_test_step_carries_no_failed_ids(self, tmp_project: Path) -> None:
        step = StepDef(
            id="test", command="printf '=== 3 passed in 0.01s ===\\n'", timeout_seconds=30
        )
        result = DeterministicRunner(
            project_root=tmp_project, output=StringIO()
        ).run("check", step_defs=[step])

        assert "failed_ids" not in result.to_dict()["tests"]["test"]

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
        assert (
            result.to_dict()["reruns"][0]["outcome"] == "passed-in-isolation"
        ), "the record must name what was established, not a cause (issue #900)"
        assert result.reruns[0]["ids"] == ["tests/a.py::t1"]
        assert result.tests["test"]["failed"] == 1
        assert result.tests["test"]["passed"] == 2
        assert result.reruns[0]["first_attempt"] == result.tests["test"]
        assert result.reruns[0]["rerun"]["passed"] == 1
        assert "RE-RAN AND PASSED: tests/a.py::t1 (1 id)" in log.getvalue()
        assert "completed successfully" not in log.getvalue()

    def test_a_passing_rerun_does_not_claim_a_flake(
        self, tmp_project: Path
    ) -> None:
        """Issue #900: the re-run cannot establish the cause, so it must not name one.

        The re-run changes TWO variables at once - when it ran, and what ran
        before it. A flake is explained by the first, an order-dependent real
        failure by the second, and passing alone is the signature of both. The
        line used to read "first attempt was a flake", which is a conclusion the
        experiment cannot support and the one that did the damage: an
        order-dependent failure in kyle survived weeks of being cleared by it.
        """
        step = StepDef(
            id="test",
            command=self._first_fails_then("=== 1 passed in 0.01s ==="),
            timeout_seconds=30,
        )
        log = StringIO()
        DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])
        text = log.getvalue()

        assert "first attempt was a flake" not in text, (
            "the runner is asserting a cause its experiment cannot establish "
            "(issue #900)"
        )
        # The narrower claim it CAN support.
        assert "pass when run alone" in text
        # And the alternative it must not exclude.
        assert "order-dependent" in text

    def test_the_runner_line_does_not_defuse_the_gate_warning(self) -> None:
        """The two surfaces must agree that the cause is undetermined (#900).

        `flow-finish-gate.sh` has reported `warn (rerun passed: ...)` since #769
        landed, and its wording already offers both causes - so the gate was never
        the problem. The runner's line printed FIRST, named one cause
        confidently, and therefore read as the explanation for the warning below
        it. The warn was not missing; it was defused.

        This asserts the property across both surfaces rather than in one, so a
        future edit that makes either of them confident again fails here. It reads
        source text on purpose: the runner line is only reachable by executing a
        re-run, the shell line only by driving the gate, and the defect is that
        the two DISAGREE - which is a property of the pair, not of either run.

        What it does not prove: that any human read either line, or that the
        orderings are as described at a terminal. It pins the wording, which is
        the part that regressed.
        """
        runner_src = (Path(_CPP_ROOT) / "lib" / "cicd" / "runner.py").read_text()
        gate = Path(_CPP_ROOT) / "scripts" / "flow-finish-gate.sh"
        if not gate.is_file():
            pytest.skip("flow-finish-gate.sh not present in this checkout")
        gate_src = gate.read_text()

        assert "RE-RUN PASSED IN ISOLATION" in runner_src, (
            "the runner's re-run message has been reworded - update this test, "
            "but keep it: it is the only thing pinning the two surfaces together"
        )
        # Deliberately NO `"first attempt was a flake" not in runner_src` here.
        # It was written, and it failed on its first run - against the COMMENT
        # above the fix, which quotes the old claim to explain what changed. That
        # is #821's self-matching shape occurring inside the guard written for
        # #900: the pattern was inside the text doing the matching.
        #
        # Scoping the search to non-comment lines would work and is the wrong
        # trade: it buys a weaker version of a check that already exists in the
        # right place. `test_a_passing_rerun_does_not_claim_a_flake` asserts the
        # phrase is absent from the EMITTED LOG, which is what actually reaches a
        # reader - source prose does not. Absence-in-source and absence-in-output
        # are two questions, and only the second one matters here.
        # Each surface must offer the alternative rather than settle on one cause.
        assert "order-dependent" in runner_src
        assert "real intermittent failure" in gate_src, (
            "flow-finish-gate.sh no longer offers the non-flake cause"
        )

    def test_the_rerun_token_matches_what_the_gate_greps(self) -> None:
        """One token in two languages, pinned in BOTH directions (issue #900).

        `flow-finish-gate.sh` cannot import `lib.cicd`, so the token is duplicated
        into an awk regex. That regex is ANCHORED - `/^      "outcome": "..."$/` -
        which makes the drift silent in the worst direction: the gate stops
        emitting `RERUN_PASSED`, the warning never prints, and the marker reverts
        to `ok` for a run that failed and was rescued. That is #900's exact
        symptom restored by a rename that only half-landed.

        Both directions fail here:

          * the runner records a token the gate does not match -> rescued runs
            silently report `ok`;
          * the gate matches a token the runner never emits -> the same, and the
            matcher looks maintained while matching nothing.

        Deliberately parsed from each source rather than compared to a literal
        third copy: a test holding its own copy of the value under test proves
        only that the copy matches itself, which is how the 9-entry HELPERS copy
        sat green beside a 13-entry array (#677).
        """
        gate = Path(_CPP_ROOT) / "scripts" / "flow-finish-gate.sh"
        if not gate.is_file():
            pytest.skip("flow-finish-gate.sh not present in this checkout")

        matched = re.findall(
            r'"outcome": "([a-z-]+)"\[,\]\?\$/', gate.read_text()
        )
        assert matched, (
            "could not find the rerun-outcome match in flow-finish-gate.sh's awk "
            "block - if it was rewritten, update this parser; do NOT drop the "
            "assertion, which is the only thing keeping the two equal (#900)"
        )
        assert set(matched) == {RERUN_PASSED_IN_ISOLATION}, (
            f"flow-finish-gate.sh greps for {sorted(set(matched))} but the runner "
            f"records {RERUN_PASSED_IN_ISOLATION!r}. A mismatch makes the gate "
            f"report `ok` for a run that was rescued by a re-run (issue #900)."
        )

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

    # --- issue #915: grade the retry on the NAMED IDS, not the invocation ----
    #
    # The retry re-runs the whole test target, so ANY unrelated failure in it
    # made the gate announce "the failure reproduces" and name the retried id -
    # an id that had passed. Observed in kyle #1176: the retried id passed, a
    # different test failed in the other phase because a commit landed in
    # another repository between the two invocations, and the verdict named the
    # innocent test while the real breakage went unnamed.

    @staticmethod
    def _first_fails_then_other_fails() -> str:
        """First attempt fails on t1; the re-run passes t1 and fails t2 instead.

        This is the shape #915 describes: the retried id did NOT reproduce, and
        the invocation still exited non-zero for an unrelated reason.
        """
        return (
            "if [ -f rerun-marker ]; then "
            "printf '=== 1 failed, 1 passed in 0.01s ===\\n'; "
            "printf 'FAILED tests/b.py::t2 - AssertionError: different test\\n'; "
            "exit 1; "
            "else : > rerun-marker; "
            "printf '=== 1 failed, 2 passed in 0.01s ===\\n'; "
            "printf 'FAILED tests/a.py::t1 - AssertionError: first attempt\\n'; "
            "exit 1; fi"
        )

    def test_a_different_failure_is_not_reported_as_the_original_reproducing(
        self, tmp_project: Path
    ) -> None:
        """The #915 defect: an innocent id named as reproducing."""
        step = StepDef(
            id="test", command=self._first_fails_then_other_fails(), timeout_seconds=30
        )
        log = StringIO()
        result = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])

        assert not result.success, "a new failure is still a failure"
        assert result.reruns[0]["outcome"] == "new-failures", result.reruns
        text = log.getvalue()
        # Cross-model review on #915: "did NOT reproduce" was itself an
        # overclaim - absence from the failed set is not evidence of passing.
        assert "not among the re-run's reported failures" in text, text
        assert "UNKNOWN" in text, "reproduction status must be stated as unknown"
        assert "did NOT reproduce" not in text, text
        assert "points outside" not in text, (
            "a changed failing set does not establish an external cause"
        )
        assert "tests/b.py::t2" in text, "the ACTUAL failure must be named"
        assert result.reruns[0]["appeared"] == ["tests/b.py::t2"]
        assert result.reruns[0]["unobserved"] == ["tests/a.py::t1"]
        assert "the failure reproduces" not in text, (
            "the retried id passed - claiming it reproduced points a reader at "
            f"an innocent test while hiding the real one:\n{text}"
        )

    def test_the_retried_id_reproducing_is_still_reported_as_reproducing(
        self, tmp_project: Path
    ) -> None:
        """The narrowing must not swallow the true positive it sits next to."""
        step = StepDef(
            id="test",
            command=(
                "printf '=== 1 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; exit 1"
            ),
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])

        assert not result.success
        assert result.reruns[0]["outcome"] == "failed", result.reruns
        assert "the failure reproduces: tests/a.py::t1" in log.getvalue()

    def test_a_rerun_failure_with_no_readable_ids_is_not_called_reproduced(
        self, tmp_project: Path
    ) -> None:
        """Third state, kept apart from both others.

        The invocation failed and nothing could be attributed to it. That is not
        evidence the original reproduced, and it is not a new-failure finding
        either - it is UNKNOWN, and says so. Same membership floor the rest of
        this codebase applies: could-not-tell is its own answer.
        """
        step = StepDef(
            id="test",
            command=(
                "if [ -f rerun-marker ]; then "
                "printf 'make: *** [test] Error 2\\n'; exit 2; "
                "else : > rerun-marker; "
                "printf '=== 1 failed, 2 passed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; "
                "exit 1; fi"
            ),
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])

        assert not result.success
        assert result.reruns[0]["outcome"] == "failed-unattributed", result.reruns
        assert "UNKNOWN" in log.getvalue()
        assert "the failure reproduces" not in log.getvalue()

    # --- cross-model review findings on #915 (Codex, pass 1) ------------------

    def test_a_reproduction_reported_only_on_stderr_still_counts(
        self, tmp_project: Path
    ) -> None:
        """F1: `parse(out) or parse(err)` read one stream and dropped the other.

        The re-run reports a NEW id on stdout and the RETRIED id on stderr. The
        first cut saw only stdout, concluded the retried id had not reproduced,
        and emitted `new-failures` with the reproduction sitting unread on
        stderr.
        """
        step = StepDef(
            id="test",
            command=(
                "if [ -f rerun-marker ]; then "
                "printf '=== 2 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/b.py::t2 - AssertionError\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n' >&2; "
                "exit 1; "
                "else : > rerun-marker; "
                "printf '=== 1 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; "
                "exit 1; fi"
            ),
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])

        assert not result.success
        assert result.reruns[0]["outcome"] == "failed", result.reruns
        assert result.reruns[0]["reproduced"] == ["tests/a.py::t1"]
        assert result.reruns[0]["appeared"] == ["tests/b.py::t2"]
        assert "the failure reproduces: tests/a.py::t1" in log.getvalue()

    def test_new_failures_are_named_even_when_the_original_reproduces(
        self, tmp_project: Path
    ) -> None:
        """F3: the mixed case dropped `appeared` from verdict and record."""
        step = StepDef(
            id="test",
            command=(
                "if [ -f rerun-marker ]; then "
                "printf '=== 2 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; "
                "printf 'FAILED tests/b.py::t2 - AssertionError\\n'; "
                "exit 1; "
                "else : > rerun-marker; "
                "printf '=== 1 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; "
                "exit 1; fi"
            ),
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])

        assert result.reruns[0]["outcome"] == "failed", result.reruns
        assert result.reruns[0]["reproduced"] == ["tests/a.py::t1"]
        assert result.reruns[0]["appeared"] == ["tests/b.py::t2"], (
            "the new failure must be in the structured record too"
        )
        text = log.getvalue()
        assert "the failure reproduces: tests/a.py::t1" in text
        assert "tests/b.py::t2" in text, f"the new failure must be NAMED:\n{text}"

    def test_a_collection_error_on_rerun_does_not_claim_the_original_passed(
        self, tmp_project: Path
    ) -> None:
        """F2/F4: an unexecuted retried id is UNOBSERVED, not "did not reproduce".

        A collection error in another module aborts the re-run before the
        retried id ever runs. `ERROR tests/x.py` parses as a failing id, the
        retried id is absent from the set, and the first cut said it "did NOT
        reproduce" and that the change "points outside the tree" - two claims
        the detector cannot support.
        """
        step = StepDef(
            id="test",
            command=(
                "if [ -f rerun-marker ]; then "
                "printf 'ERROR tests/x.py - ImportError: boom\\n'; "
                "printf '=== 1 error in 0.01s ===\\n'; exit 2; "
                "else : > rerun-marker; "
                "printf '=== 1 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; "
                "exit 1; fi"
            ),
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])

        assert result.reruns[0]["outcome"] == "new-failures", result.reruns
        assert result.reruns[0]["unobserved"] == ["tests/a.py::t1"]
        assert result.reruns[0]["appeared"] == ["tests/x.py"]
        text = log.getvalue()
        assert "UNKNOWN" in text, text
        assert "did NOT reproduce" not in text, text
        assert "points outside" not in text, text
        assert "cause undetermined" in text, text

    def test_parametrized_ids_sharing_a_prefix_are_not_confused(
        self, tmp_project: Path
    ) -> None:
        """Codex pass 2 on #915: two distinct parametrized ids that share every
        byte before a space must not be graded as one id reproducing.

        `test_value[hello world]` fails first; the re-run fails
        `test_value[hello there]` instead. Truncation at the space made both
        `test_value[hello` - a false reproduction with nothing recorded as new.
        """
        step = StepDef(
            id="test",
            command=(
                "if [ -f rerun-marker ]; then "
                "printf '=== 1 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::test_value[hello there] - AssertionError\\n'; "
                "exit 1; "
                "else : > rerun-marker; "
                "printf '=== 1 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::test_value[hello world] - AssertionError\\n'; "
                "exit 1; fi"
            ),
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])

        rec = result.reruns[0]
        assert rec["outcome"] == "new-failures", rec
        assert rec["reproduced"] == [], rec
        assert rec["unobserved"] == ["tests/a.py::test_value[hello world]"], rec
        assert rec["appeared"] == ["tests/a.py::test_value[hello there]"], rec
        assert "the failure reproduces" not in log.getvalue()

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
            assert env["UV_CACHE_DIR"] == str(_expected_uv_cache_dir())

    # --- B108: the default must not be a uid-independent shared path (#1113) ---
    #
    # `/tmp/uv-cache` is guessable and world-writable, so any local user can
    # create it first and own what uv then reads back out of it - a package
    # cache is executable content. Unlike the deploy lock next door, a cache
    # has no cross-process contract to preserve, so the per-uid path costs
    # nothing and the finding goes away for real.
    #
    # These fail on the pre-#1113 literal: it carries no uid.

    def test_default_uv_cache_dir_is_uid_scoped(self):
        env_without_uv = {k: v for k, v in os.environ.items() if k != "UV_CACHE_DIR"}
        with patch.dict(os.environ, env_without_uv, clear=True):
            cache = Path(_build_step_env()["UV_CACHE_DIR"])
        assert str(os.getuid()) in cache.name, (
            f"{cache} is shared across every user on the host"
        )
        assert cache.parent == Path(tempfile.gettempdir())

    def test_private_dir_creates_it_0700_and_owned_by_us(self):
        target = Path(tempfile.mkdtemp()) / "cache"
        assert _ensure_private_dir(target) == target
        assert stat.S_IMODE(target.stat().st_mode) == 0o700
        assert target.stat().st_uid == os.getuid()

    def test_private_dir_accepts_an_existing_directory_of_ours(self):
        """The half that must NOT fire: a cache is reused every run.

        A validator that refused a directory it created last time would make
        every run a cold download, and nothing else would go red.
        """
        target = Path(tempfile.mkdtemp()) / "cache"
        _ensure_private_dir(target)
        (target / "artifact").write_text("cached")
        assert _ensure_private_dir(target) == target
        assert (target / "artifact").read_text() == "cached"

    def test_private_dir_refuses_a_symlink(self):
        """The hazard the uid suffix does NOT close (counter-model, #1113).

        `/tmp/uv-cache-<uid>` is as pre-creatable as `/tmp/uv-cache`; a uid in
        the name says who should own it, not who does. This is the check that
        makes the disposition's claim true.
        """
        tmp = Path(tempfile.mkdtemp())
        (tmp / "elsewhere").mkdir()
        link = tmp / "cache"
        link.symlink_to(tmp / "elsewhere")
        with pytest.raises(RuntimeError, match="symlink"):
            _ensure_private_dir(link)

    def test_private_dir_refuses_a_directory_owned_by_someone_else(self):
        """The foreign-owner case, with `lstat` stubbed to report another uid.

        Creating a genuinely foreign-owned directory needs a second uid, which
        a unit test does not have. Stubbing the stat is honest about what is
        being exercised - the BRANCH, not the kernel - and the symlink test
        above covers a real on-disk hostile shape.
        """
        target = Path(tempfile.mkdtemp()) / "cache"
        target.mkdir(mode=0o700)
        real = Path.lstat

        def foreign(self):  # noqa: ANN001
            st = real(self)
            if self == target:
                return os.stat_result(
                    (st.st_mode, st.st_ino, st.st_dev, st.st_nlink,
                     os.getuid() + 1, st.st_gid, st.st_size,
                     int(st.st_atime), int(st.st_mtime), int(st.st_ctime))
                )
            return st

        with patch.object(Path, "lstat", foreign):
            with pytest.raises(RuntimeError, match="owned by uid"):
                _ensure_private_dir(target)

    def test_build_step_env_refuses_a_hijacked_cache(self, tmp_path: Path):
        """End to end: the refusal reaches the caller, not just the helper.

        A validator nothing calls is the failure this test exists to catch -
        `_build_step_env` is the only path that actually hands `uv` the value.
        """
        hostile = tmp_path / "hostile"
        (tmp_path / "real").mkdir()
        hostile.symlink_to(tmp_path / "real")
        env_without_uv = {k: v for k, v in os.environ.items() if k != "UV_CACHE_DIR"}
        with patch.dict(os.environ, env_without_uv, clear=True):
            with patch("lib.cicd.runner._default_uv_cache_dir", return_value=hostile):
                with pytest.raises(RuntimeError, match="symlink"):
                    _build_step_env()

    def test_private_dir_refuses_a_world_writable_directory_we_own(self):
        """Ownership is not exclusivity (counter-model, second pass).

        `mkdir(mode=0o700, exist_ok=True)` applies the mode only when it
        CREATES the directory. A pre-existing 0777 cache - an older run under a
        permissive umask - is owned by us and writable by everyone, which is
        the entire hazard, and the owner check alone waves it through.
        """
        target = Path(tempfile.mkdtemp()) / "cache"
        target.mkdir(mode=0o777)
        os.chmod(target, 0o777)  # defeat umask, which would have trimmed it
        with pytest.raises(RuntimeError, match="writable by other users"):
            _ensure_private_dir(target)

    def test_an_explicit_cache_override_does_not_touch_the_default(self):
        """`setdefault` evaluates its argument eagerly (counter-model, 2nd pass).

        With the default written as `env.setdefault(k, _ensure_private_dir(...))`
        a hijacked DEFAULT cache aborted every run - including runs that had
        explicitly chosen a different, safe cache and would never have used the
        default. That contradicts `_build_step_env`'s stated contract that an
        explicit caller env always wins.
        """
        calls: list[str] = []

        def exploding_default():
            calls.append("evaluated")
            raise RuntimeError("the default cache is hijacked")

        with patch.dict(os.environ, {"UV_CACHE_DIR": "/custom/cache"}):
            with patch("lib.cicd.runner._default_uv_cache_dir", exploding_default):
                env = _build_step_env()
        assert env["UV_CACHE_DIR"] == "/custom/cache"
        assert not calls, "the default cache was resolved despite an explicit override"

    def test_default_uv_cache_dir_is_stable_across_calls(self):
        """A cache that moved every call would not be a cache.

        The half that must NOT fire: `tempfile.mkdtemp()` would clear the
        bandit finding too, and would silently turn every run into a cold
        download. Nothing else in the suite would go red.
        """
        env_without_uv = {k: v for k, v in os.environ.items() if k != "UV_CACHE_DIR"}
        with patch.dict(os.environ, env_without_uv, clear=True):
            first = _build_step_env()["UV_CACHE_DIR"]
            second = _build_step_env()["UV_CACHE_DIR"]
        assert first == second

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

    def test_deploy_security_step_dehardcoded(self):
        """Renamed with its subject (#1155): the deploy plan's security step is
        `deploy_security_scan`, not `security_scan`. The PROPERTY is unchanged -
        no hardcoded checkout path, PYTHONPATH from _CPP_ROOT."""
        step = {s.id: s for s in BUILTIN_PLANS["deploy"]}["deploy_security_scan"]
        assert "Projects/claude-power-pack" not in step.command
        assert step.env.get("PYTHONPATH") == _CPP_ROOT

    def test_the_deploy_plan_runs_the_DEPLOY_security_policy(self):
        """THE COMMITTED RED CASE for the rename that was refused (#1155).

        `flow_deploy` blocks on CRITICAL and HIGH; `flow_finish` blocks on
        CRITICAL only (lib/security/config.py). The manifest's `steps:`
        namespace is FLAT, so `security_scan` there is already the FINISH scan -
        which is why pointing the deploy plan at that id, the first-cut
        "alignment", would have silently stopped HIGH findings blocking a
        deploy. That is a security downgrade wearing a rename's clothes, and
        nothing asserted the command, so nothing would have failed.

        Asserted for BOTH resolution paths, because they are different code:
        the built-in plan, and the plan this repository's manifest actually
        resolves to. A test covering only the built-in would pass while the
        manifest served the wrong scan.
        """
        from lib.cicd.steps import get_plan_steps

        builtin = {s.id: s for s in BUILTIN_PLANS["deploy"]}
        gate_steps = [s for s in builtin.values() if s.gate]
        assert len(gate_steps) == 1, f"expected one deploy gate, got {gate_steps}"
        assert "flow_deploy" in gate_steps[0].command
        assert "flow_finish" not in gate_steps[0].command

        repo_root = Path(__file__).resolve().parent.parent
        resolved = get_plan_steps("deploy", project_root=str(repo_root))
        resolved_gates = [s for s in resolved if s.gate]
        assert resolved_gates, (
            "the resolved deploy plan has no gate step - the manifest and the "
            "built-in plan disagree on the id, which is what #1155 reconciles"
        )
        for step in resolved_gates:
            assert "flow_deploy" in step.command, (
                f"the resolved deploy plan's gate {step.id!r} runs "
                f"{step.command!r}. `flow_finish` blocks on CRITICAL only, so "
                f"serving it here stops HIGH findings blocking a deploy (#1155)"
            )

        # THIRD SUBJECT: the plan `generate_manifest` EMITS (#1160). The first
        # two cover what this repository runs; neither can see what CPP hands a
        # project it scaffolds. That path had the defect: the generated deploy
        # plan referenced `security_scan`, which in a generated manifest is the
        # FINISH scan, so every scaffolded project's deploy gate blocked on
        # CRITICAL only. Two subjects passed while it was live.
        import tempfile

        from lib.cicd.manifest import generate_manifest, get_manifest_plan_steps

        scratch = tempfile.mkdtemp()
        (Path(scratch) / "pyproject.toml").write_text("[tool.ruff]\n")
        generated = generate_manifest(scratch)
        generated_gates = [
            st for st in get_manifest_plan_steps(generated, "deploy") if st.gate
        ]
        assert generated_gates, (
            "a generated deploy plan has no gate step - the generator and the "
            "builtin declaration disagree, which is what #1155 reconciles"
        )
        for step in generated_gates:
            assert "flow_deploy" in step.command, (
                f"a GENERATED deploy plan's gate {step.id!r} runs "
                f"{step.command!r}. Every project CPP scaffolds would block on "
                f"CRITICAL only, so a HIGH finding would not stop its deploy "
                f"(#1160)"
            )

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
        """Every finish gate is either run by the fallback or NAMED as unrunnable.

        Until #890 this read "every gate is run by the fallback", which was true
        only because the two questions GATE_STEP_IDS is consulted for happened to
        agree. They are different questions - "did skipping this prove nothing?"
        (runner.py, #628) and "must the degraded lane run this?" (here, #617) -
        and `security_scan` is the first without being the second. Absence is no
        longer a passing state: a gate the fallback does not invoke has to be
        declared unrunnable, with a reason.
        """
        gate = Path(_CPP_ROOT) / "scripts" / "flow-finish-gate.sh"
        if not gate.is_file():
            pytest.skip("flow-finish-gate.sh not present in this checkout")
        body = gate.read_text()
        gate_ids = [s.id for s in BUILTIN_PLANS["finish"] if s.id in GATE_STEP_IDS]
        assert gate_ids, "the finish plan defines no gate steps - test is vacuous"
        # The generic helper prefers the target, falls back to uv, records failure.
        #
        # Asserted as TWO facts per lane rather than one literal line: since
        # issue #1027 the non-test lanes pipe through `tee` so their output can
        # be inspected for a zero-coverage statement, which means the invocation
        # and the failure-recording are no longer on the same line. Pinning the
        # old single literal would now fail for a formatting reason while saying
        # nothing about whether the lane still runs the gate or still records a
        # failure - the two properties this test exists for. `PIPESTATUS[0]` is
        # named explicitly because it is the load-bearing part: with a pipe in
        # play, a bare `||` would read `tee`'s status and the lane would record
        # success for every failing gate.
        assert 'grep -q "^${id}:" Makefile 2>/dev/null' in body
        assert 'make "${id}" 2>&1 | tee' in body
        assert "uv run --extra dev ${uvargs} 2>&1 | tee" in body
        assert body.count('[[ "${PIPESTATUS[0]}" -eq 0 ]] || FAILED=1') == 2, (
            "both non-test fallback lanes must grade on the COMMAND's exit "
            "status, not the tee's"
        )
        for gid in gate_ids:
            if f"run_fallback_gate {gid} " in body:
                continue
            reason = FALLBACK_UNRUNNABLE_GATES.get(gid, "")
            assert reason.strip(), (
                f"the fallback never runs the '{gid}' gate and nothing says why "
                f"(#617/#628/#890). Either add `run_fallback_gate {gid} ` to "
                f"flow-finish-gate.sh, or add {gid!r} to FALLBACK_UNRUNNABLE_GATES "
                f"with the reason no degraded form of it exists."
            )

    def test_no_stale_fallback_exemption(self):
        """An exemption for a gate that no longer exists is a claim about nothing.

        The mirror of the assertion above: without this, deleting a gate would
        leave its exemption behind, quietly widening what the next reader thinks
        the fallback is allowed not to run.
        """
        for gid in FALLBACK_UNRUNNABLE_GATES:
            assert gid in GATE_STEP_IDS, (
                f"FALLBACK_UNRUNNABLE_GATES names {gid!r}, which is not a gate in "
                f"any plan - remove the stale exemption"
            )


class TestBothStreamsReachTheRunnerDecisions:
    """Issue #939 end to end: the merged summary drives three real decisions.

    `_parse_tests` fed retry eligibility, #621's `nothing_ran` guard and #900's
    re-run verdict from ONE stream while claiming both. These cases pin the
    decisions rather than the parser - the parser's own cases live in
    tests/test_cicd_outcomes.py::TestBothStreamsAreMerged.

    Every case here puts a REAL summary on stdout and the contradicting one on
    stderr. A case with an empty stdout would pass against the pre-fix code,
    because `parse(out) or parse(err)` fell through correctly when stdout said
    nothing at all - it is not a regression test for this defect.
    """

    def test_failures_on_stderr_are_retried_despite_a_passing_stdout_summary(
        self, tmp_project: Path
    ) -> None:
        """THE #939 red case at the decision it breaks: retry eligibility.

        runner.py gates the #769 targeted re-run on
        `outcome.failed + outcome.errors > 0`. Pre-fix the outcome was the
        stdout summary alone - 3 passed, 0 failed - so this step failed, had a
        readable failing id on stderr, and was never re-run.
        """
        step = StepDef(
            id="test",
            command=(
                "printf '=== 3 passed in 0.01s ===\\n'; "
                "printf '=== 1 failed in 0.01s ===\\n' >&2; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n' >&2; "
                "exit 1"
            ),
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])

        assert not result.success
        assert result.reruns, (
            "the failing id was readable on stderr and the step was eligible "
            "for the #769 re-run; pre-fix the stdout summary hid it and "
            "result.reruns was empty"
        )
        assert result.reruns[0]["ids"] == ["tests/a.py::t1"]
        assert result.tests["test"]["failed"] == 1
        assert result.tests["test"]["passed"] == 3
        assert result.tests["test"]["summary_streams"] == ["stdout", "stderr"]

    def test_a_rerun_reads_its_counts_from_both_streams(
        self, tmp_project: Path
    ) -> None:
        """#900's verdict path, reading the merged re-run counts (issue #939).

        The re-run reports 2 passed on stdout and 1 passed on stderr - three
        real executions, no empty invocation, so the verdict is legitimately
        `passed-in-isolation` and the only question is whether the COUNTS are
        complete. Pre-fix the stdout summary won and the record said 2,
        discarding a third of the re-run.

        THIS CASE REPLACES an earlier one that put "no tests ran" on stdout and
        a passing summary on stderr and expected `passed-in-isolation`. That
        expectation was wrong and Codex caught it: when one invocation executed
        nothing, the retried id cannot be shown to be among those that ran, so
        the honest verdict is inconclusive. That scenario now lives in
        test_an_unrelated_passing_suite_cannot_clear_the_original_failure,
        asserting inconclusive - which is also why this case deliberately has
        no empty invocation, or it would assert the merge through a path that
        stops before the counts matter.
        """
        step = StepDef(
            id="test",
            command=(
                "if [ -f rerun-marker ]; then "
                "printf '=== 2 passed in 0.01s ===\\n'; "
                "printf '=== 1 passed in 0.01s ===\\n' >&2; "
                "else : > rerun-marker; "
                "printf '=== 1 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; "
                "exit 1; fi"
            ),
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])

        assert result.reruns[0]["outcome"] == RERUN_PASSED_IN_ISOLATION
        assert result.reruns[0]["rerun"]["passed"] == 3, (
            "pre-fix the stdout summary won and the record said 2"
        )
        assert result.reruns[0]["rerun"]["summary_streams"] == ["stdout", "stderr"]

    def test_an_unrelated_passing_suite_cannot_clear_the_original_failure(
        self, tmp_project: Path
    ) -> None:
        """A re-run that executed none of the retried ids must stay inconclusive.

        Found by Codex reviewing this change, and it is a regression THIS
        change introduced. The re-run reports pytest "no tests ran" on stdout
        and an unrelated passing jest suite on stderr. Merged, the total looks
        healthy - `nothing_ran` is False - so the runner would record
        `passed-in-isolation` against a pytest id that was never executed and
        return success. Before the merge the empty pytest summary won outright
        and the run read inconclusive: the right verdict for the wrong reason.

        `any_invocation_empty` is what keeps it right for the right reason.
        """
        step = StepDef(
            id="test",
            command=(
                "if [ -f rerun-marker ]; then "
                "printf '=== no tests ran in 0.01s ===\\n'; "
                "printf 'Tests:       2 passed, 2 total\\n' >&2; "
                "else : > rerun-marker; "
                "printf '=== 1 failed in 0.01s ===\\n'; "
                "printf 'FAILED tests/a.py::t1 - AssertionError\\n'; "
                "exit 1; fi"
            ),
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(
            project_root=tmp_project, output=log, rerun_failed=True
        ).run("check", step_defs=[step])

        assert result.reruns[0]["outcome"] == "inconclusive", (
            "an unrelated suite passing says nothing about the retried id"
        )
        assert result.reruns[0]["outcome"] != RERUN_PASSED_IN_ISOLATION
        assert "RE-RUN INCONCLUSIVE" in log.getvalue()

    def test_an_empty_invocation_on_the_other_stream_still_warns(
        self, tmp_project: Path
    ) -> None:
        """#621's guard, extended to the stream dimension (issue #939).

        One invocation collected nothing and the other passed 5, split across
        the streams. The merge must not silence #621: the total ran something,
        so `nothing_ran` is False, and `any_invocation_empty` is what keeps the
        warning alive.
        """
        step = StepDef(
            id="test",
            command=(
                "printf '=== no tests ran in 0.01s ===\\n'; "
                "printf '=== 5 passed in 0.01s ===\\n' >&2"
            ),
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(project_root=tmp_project, output=log).run(
            "check", step_defs=[step]
        )

        assert result.success
        assert result.warnings, "#621's guard must survive the merge"
        assert "executed NO tests" in " ".join(result.warnings)
        assert result.tests["test"]["empty_invocations"] == 1
        assert result.tests["test"]["invocations"] == 2


class TestUnparsedTestOutcomeReadsUnknown:
    """Issue #952 via #939: a parse that examined nothing is UNKNOWN, not clean.

    A test step that exited 0 and whose output yielded no recognizable summary
    used to log a bare SUCCESS and add no `tests` entry at all. Silence and a
    clean result were indistinguishable to flow-finish-gate.sh, which reads
    `warnings`.
    """

    def test_unparseable_test_output_is_reported_as_unknown(
        self, tmp_project: Path
    ) -> None:
        step = StepDef(
            id="test",
            command="printf 'ok 1 - something\\nok 2 - something else\\n'",
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(project_root=tmp_project, output=log).run(
            "check", step_defs=[step]
        )

        assert result.success
        assert result.warnings
        assert "UNKNOWN, not clean" in " ".join(result.warnings)
        assert "completed successfully" not in log.getvalue()

    def test_unparseable_output_on_stderr_alone_is_also_unknown(
        self, tmp_project: Path
    ) -> None:
        """The stdout case above passed while this one was blind (Codex, #939).

        `ShellStep.execute` dropped `error` from a SUCCESS StepResult, so an
        exit-0 step that wrote only to stderr reached the guard with BOTH
        fields empty and was reported as a clean bare success - while the
        byte-identical output on stdout was correctly reported UNKNOWN. The
        guard's own blind spot, in the same shape as the defect this ticket
        fixes, and the stdout-only case could not see it.
        """
        step = StepDef(
            id="test",
            command="printf 'ok 1 - something\\n' >&2",
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(project_root=tmp_project, output=log).run(
            "check", step_defs=[step]
        )

        assert result.success
        assert result.warnings, "stderr-only output must reach the guard too"
        assert "UNKNOWN, not clean" in " ".join(result.warnings)

    def test_an_unknown_result_is_not_reported_as_executed_no_tests(
        self, tmp_project: Path
    ) -> None:
        """The plan summary must not convert UNKNOWN into a #621 claim.

        `warnings` now carries three different findings and the summary line
        used to assert #621's - "a test step executed no tests" - for any of
        them. For unparseable output that is simply false: the suite may have
        executed thousands. Failing to RECOGNISE a summary cannot establish
        that nothing ran.

        Found by Codex reviewing this change. The string was pinned by no test
        at all, which is why #838 had already falsified it without anyone
        noticing.
        """
        step = StepDef(
            id="test",
            command="printf 'ok 1 - something\\nok 2 - another\\n'",
            timeout_seconds=30,
        )
        log = StringIO()
        result = DeterministicRunner(project_root=tmp_project, output=log).run(
            "check", step_defs=[step]
        )

        text = log.getvalue()
        assert result.warnings
        assert "executed no tests" not in text, (
            "the runner did not establish that - it failed to parse a summary"
        )
        assert "UNKNOWN, not clean" in " ".join(result.warnings)
        assert "WITH WARNINGS" in text

    def test_a_test_step_that_printed_nothing_is_still_a_bare_success(
        self, tmp_project: Path
    ) -> None:
        """The bound on the warning above, pinned so it cannot quietly widen.

        A step that produced NO output is not a suite whose result is unknown -
        there is nothing to be unknown about - and #628/#890 pinned that shape
        as a bare success. A warning that fires on the normal case is one
        nobody reads, so this is the negative half of the pair.
        """
        step = StepDef(id="test", command="true", timeout_seconds=30)
        log = StringIO()
        result = DeterministicRunner(project_root=tmp_project, output=log).run(
            "check", step_defs=[step]
        )

        assert result.success
        assert not result.warnings
        assert "UNKNOWN" not in log.getvalue()


def _run_test_step(
    tmp_project: Path, command: str, unsupported_runner: str | None = None
):
    step = StepDef(
        id="test",
        command=command,
        timeout_seconds=30,
        unsupported_runner=unsupported_runner,
    )
    log = StringIO()
    result = DeterministicRunner(project_root=tmp_project, output=log).run(
        "check", step_defs=[step]
    )
    return result, log.getvalue()


# One specimen per cause. Printed with `printf` so the fixture is the output a
# runner would produce, not a value handed to the code under test.
_SUPPORTED_EMPTY_CMD = (
    "printf '============ test session starts ============\\n"
    "collected 3 items\\nKilled\\n'"
)
_UNCLASSIFIABLE_CMD = "printf 'ok 1 - something\\nok 2 - another\\n'"


class TestUnparsedCausesAreDistinct:
    """Issue #977: UNKNOWN stays, and its causes are separated in DETAIL.

    The ruling: a supported runner that came back empty is a per-run alarm, an
    output nobody can classify is an unmeasured fact, and a runner the project
    DECLARED unsupported is a recorded decision that may be quiet. The first
    two share one verdict (UNKNOWN, warn) and differ only in wording - and
    nothing downstream reads the wording, so the difference is pinned here.
    """

    def test_the_two_warning_causes_produce_different_text(
        self, tmp_project: Path
    ) -> None:
        """THE CONTROL the ruling asked for: a collapse of the causes goes red.

        Asserting each wording separately would stay green if both branches
        were edited into the same sentence; asserting they DIFFER is what
        catches it.
        """
        empty, empty_log = _run_test_step(tmp_project, _SUPPORTED_EMPTY_CMD)
        unclassified, unclassified_log = _run_test_step(
            tmp_project, _UNCLASSIFIABLE_CMD
        )

        assert len(empty.warnings) == 1 and len(unclassified.warnings) == 1
        # Both remain UNKNOWN - the verdict is shared, only DETAIL differs.
        for w in (empty.warnings[0], unclassified.warnings[0]):
            assert "UNKNOWN, not clean" in w
        assert empty.warnings[0] != unclassified.warnings[0]
        assert "supported runner pytest was recognised" in empty.warnings[0]
        assert "could not be classified" in unclassified.warnings[0]
        # Neither is allowed to call itself "unsupported": that word belongs
        # to a declaration, and inferring it is what the ruling forbids.
        for w in (empty.warnings[0], unclassified.warnings[0]):
            assert "declared unsupported" not in w
        assert "PYTEST CAME BACK EMPTY" in empty_log
        assert "OUTPUT UNCLASSIFIABLE" in unclassified_log

    def test_a_declared_runner_is_quiet_but_not_called_clean(
        self, tmp_project: Path
    ) -> None:
        result, log = _run_test_step(
            tmp_project, _UNCLASSIFIABLE_CMD, unsupported_runner="tap harness"
        )

        assert result.success
        assert not result.warnings, "a recorded decision may be quiet"
        assert "TEST OUTCOME NOT MEASURED" in log
        assert "declared unsupported: tap harness" in log
        assert "test" not in result.tests, "no counts were measured"

    def test_the_declaration_is_what_silences_it(self, tmp_project: Path) -> None:
        """Negative half of the test above: the same output, undeclared, warns."""
        result, _ = _run_test_step(tmp_project, _UNCLASSIFIABLE_CMD)
        assert result.warnings

    def test_a_declaration_cannot_mute_a_supported_runner_gone_silent(
        self, tmp_project: Path
    ) -> None:
        """The alarm the warning exists for survives a (stale) declaration."""
        result, _ = _run_test_step(
            tmp_project, _SUPPORTED_EMPTY_CMD, unsupported_runner="go test"
        )

        assert len(result.warnings) == 1
        warning = result.warnings[0]
        assert "UNKNOWN, not clean" in warning
        assert "supported runner pytest was recognised" in warning
        assert "does not silence a runner CPP supports" in warning

    def test_a_declared_step_whose_output_parses_uses_the_counts_and_notes_it(
        self, tmp_project: Path
    ) -> None:
        """A measurement beats a declaration, and the gap is logged, not warned."""
        result, log = _run_test_step(
            tmp_project,
            "printf '==== 3 passed in 0.10s ====\\n'",
            unsupported_runner="go test",
        )

        assert result.success
        assert result.tests["test"]["passed"] == 3, "the measurement is used"
        assert not result.warnings
        assert "counts come from a parsed pytest summary" in log
        assert "(go test), if any, is NOT measured" in log

    def test_a_mixed_step_is_not_told_its_declaration_is_wrong(
        self, tmp_project: Path
    ) -> None:
        """Counter-model finding: a neighbouring pytest suite proves nothing
        about the declared Go runner, so it must not produce a per-run warning
        telling the author to remove the declaration."""
        result, log = _run_test_step(
            tmp_project,
            "printf 'ok  \\texample.com/pkg\\t0.012s\\n"
            "==== 3 passed in 0.10s ====\\n'",
            unsupported_runner="go test",
        )

        assert not result.warnings
        assert "remove it" not in log
        assert "is NOT measured" in log

    def test_application_output_cannot_override_a_declaration(
        self, tmp_project: Path
    ) -> None:
        """Counter-model finding, pass 2, end to end."""
        result, _ = _run_test_step(
            tmp_project,
            "printf 'collected 3 items from queue\\nall checks passed\\n'",
            unsupported_runner="shell harness",
        )
        assert not result.warnings

    def test_an_uncorroborated_signature_does_not_override_a_declaration(
        self, tmp_project: Path
    ) -> None:
        """Counter-model finding: any harness can print `PASS src/app.test.ts`.

        It names jest in DETAIL when nothing is declared, but it is not strong
        enough to turn a recorded decision back into a per-run warning.
        """
        cmd = "printf 'PASS src/app.test.ts\\nall done\\n'"
        declared, declared_log = _run_test_step(
            tmp_project, cmd, unsupported_runner="shell harness"
        )
        undeclared, _ = _run_test_step(tmp_project, cmd)

        assert not declared.warnings
        assert "declared unsupported: shell harness" in declared_log
        # The same weak signature still sets the undeclared DETAIL.
        assert len(undeclared.warnings) == 1
        assert "supported runner jest was recognised" in undeclared.warnings[0]

    def test_an_undeclared_parsed_suite_carries_no_declaration_warning(
        self, tmp_project: Path
    ) -> None:
        result, _ = _run_test_step(
            tmp_project, "printf '==== 3 passed in 0.10s ====\\n'"
        )
        assert not result.warnings


class TestClassifyUnparsed:
    """The narrow recogniser behind the supported-empty cause (issue #977)."""

    @pytest.mark.parametrize(
        ("text", "framework"),
        [
            ("===== test session starts =====\nplatform linux\n", "pytest"),
            ("collected 12 items\n", "pytest"),
            ("Test Suites: 1 failed, 1 total\n", "jest"),
            ("PASS src/app.test.ts\n", "jest"),
            ("FAIL  src/app.test.js (5 ms)\n", "jest"),
            ("Ran 4 tests in 0.002s\n", "unittest"),
        ],
    )
    def test_supported_signatures_are_recognised(self, text: str, framework: str) -> None:
        from lib.cicd.outcomes import classify_unparsed

        found = classify_unparsed(text)
        assert found is not None and found[0] == framework

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "ok 1 - something\nok 2 - else\n1..2\n",  # TAP
            "ok  \texample.com/pkg\t0.012s\n",  # go test
            "test result: ok. 3 passed; 0 failed; 0 ignored\n",  # cargo test
            "all good\n",
        ],
    )
    def test_foreign_output_is_unclassifiable_not_supported(self, text: str) -> None:
        from lib.cicd.outcomes import classify_unparsed

        assert classify_unparsed(text) is None

    @pytest.mark.parametrize(
        "text",
        ["collected 5 items / 2 deselected / 3 selected\n", "collected 1 item\n"],
    )
    def test_pytest_collection_lines_are_corroborated(self, text: str) -> None:
        from lib.cicd.outcomes import classify_unparsed

        found = classify_unparsed(text, corroborated_only=True)
        assert found is not None and found[0] == "pytest"

    def test_application_output_that_starts_like_pytest_is_not_pytest(self) -> None:
        """Counter-model finding, pass 2: a prefix match let this override."""
        from lib.cicd.outcomes import classify_unparsed

        assert classify_unparsed("collected 3 items from queue\n") is None

    def test_a_bare_pass_line_is_not_corroborated(self) -> None:
        from lib.cicd.outcomes import classify_unparsed

        text = "PASS src/app.test.ts\n"
        assert classify_unparsed(text) == ("jest", "PASS src/app.test.ts")
        assert classify_unparsed(text, corroborated_only=True) is None
        assert classify_unparsed(
            "Test Suites: 1 failed, 1 total\n", corroborated_only=True
        ) is not None


class TestManifestCarriesTheDeclaration:
    """The declaration is configured on the manifest step (issue #977)."""

    def test_round_trip_into_the_step_def(self) -> None:
        from lib.cicd.manifest import StepModel, step_model_to_step_def

        step = step_model_to_step_def(
            "test", StepModel(command="go test ./...", unsupported_runner=" go test ")
        )
        assert step.unsupported_runner == "go test"

    def test_absent_means_nothing_declared(self) -> None:
        from lib.cicd.manifest import StepModel, step_model_to_step_def

        step = step_model_to_step_def("test", StepModel(command="make test"))
        assert step.unsupported_runner is None

    def test_an_empty_declaration_is_refused(self) -> None:
        from pydantic import ValidationError

        from lib.cicd.manifest import StepModel

        with pytest.raises(ValidationError):
            StepModel(command="go test ./...", unsupported_runner="  ")


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
            # The denominator (issue #939/#952). The gate helper reads this
            # dict, and `312 passed` derived from stdout alone is a different
            # claim from `312 passed` derived from both streams - so the
            # streams that produced the counts are pinned beside them rather
            # than left for a reader to assume.
            "summary_streams": ["stdout"],
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


class TestGateDeclarationIsExhaustive:
    """Every builtin step declares whether skipping it proves nothing (issue #890).

    Deriving GATE_STEP_IDS from the step definitions makes one failure mode
    impossible - a gate cannot be declared and then left out of the set, because
    there is no second place to update. It does NOT make the other one
    impossible: `StepDef.gate` defaults to False, so a new step that never
    mentions `gate=` is silently a non-gate, which is exactly the shape that hid
    `security_scan` for three releases.

    Deriving cannot close that; only an exhaustive classification can. This class
    is it. A step in neither bucket fails, and so does an exemption for a step
    that no longer exists - so the set of things this repository has decided
    about stays equal to the set of things there are to decide about.

    Per docs/agents/detector-contracts.md, what a green run here does NOT prove:

      * It does not prove a classification is CORRECT, only that one was made
        deliberately. `DECLARED_NON_GATES` is a record of judgements, and a wrong
        judgement recorded with a reason still passes. That is the honest limit:
        a test can force the question to be asked, not answer it.
      * It covers BUILTIN_PLANS only. A step from a task manifest is classified
        by whatever the manifest says and is invisible here.
    """

    #: Steps whose skip proves nothing was missed, with the reason. A step is in
    #: this dict or it declares `gate=True`; being in neither is a failure, not a
    #: default. Reasons are load-bearing - an entry without one is a bare
    #: assertion that the next reader cannot check.
    DECLARED_NON_GATES: dict[str, str] = {
        "bootstrap_check": (
            "advisory. It reports on dependency and bootstrap advisories rather "
            "than verifying the change, and its skip_if fires when the repo has "
            "no recognisable dependency manifest at all - a repo shape, not a "
            "missing verification."
        ),
        "stale_commit_check": (
            "skipping is designed-normal, and the design is the point: skip_if is "
            "'not on main, or CPP_OFFLINE'. Off main there is nothing to be stale "
            "against, and offline the git fetch cannot reach the remote, so the "
            "skip reports a situation rather than an unverified dimension (#534)."
        ),
        "deploy": (
            "the action the plan exists to perform, not a check on it. It has no "
            "skip_if at all, so a 'skipped deploy' is not a state the runner can "
            "reach - and if it ever became one, that is a failed deploy to report, "
            "not a gate that proved nothing."
        ),
    }

    def _all_builtin_steps(self):
        return [(plan, step) for plan, steps in BUILTIN_PLANS.items() for step in steps]

    def test_every_builtin_step_is_classified(self):
        unclassified = sorted(
            {
                f"{plan}:{step.id}"
                for plan, step in self._all_builtin_steps()
                if not step.gate and step.id not in self.DECLARED_NON_GATES
            }
        )
        assert not unclassified, (
            "these builtin steps declare neither `gate=True` nor a reason for not "
            f"being one: {unclassified}. A step that skips silently while the run "
            "reports success is the #628 false green; decide which it is and say "
            "so (issue #890). `gate=` defaults to False, so omitting it is not a "
            "decision - it is the absence of one."
        )

    def test_no_stale_non_gate_declaration(self):
        """The mirror: an exemption for a step nobody runs any more.

        Without this the dict only grows, and a reader cannot tell a live
        judgement from a fossil.
        """
        live = {step.id for _, step in self._all_builtin_steps()}
        stale = sorted(set(self.DECLARED_NON_GATES) - live)
        assert not stale, (
            f"DECLARED_NON_GATES names steps no builtin plan defines: {stale}"
        )

    def test_every_non_gate_declaration_carries_a_reason(self):
        for step_id, reason in self.DECLARED_NON_GATES.items():
            assert reason.strip(), f"{step_id} is exempted with no reason given"

    def test_the_classifier_can_fire(self):
        """Positive control: an unclassified step IS detected.

        Without this the exhaustiveness assertion could be green because the
        check never fires, which is the defect it exists to prevent, one level up.
        """
        rogue = StepDef(id="a_new_unclassified_step", command="true")
        assert not rogue.gate, "the default must remain False, or this proves nothing"
        unclassified = [
            step.id
            for step in [rogue]
            if not step.gate and step.id not in self.DECLARED_NON_GATES
        ]
        assert unclassified == ["a_new_unclassified_step"]

    def test_no_step_id_is_declared_both_ways(self):
        """GATE_STEP_IDS is keyed by ID, and ids repeat across plans.

        A derived set keyed on id would silently resolve a disagreement between
        two declarations of the same id - "gate here, not there" becomes "gate
        everywhere" with nobody told. Make the disagreement fail instead of
        resolving it.

        The worked example used to be `security_scan`, which was in both
        `finish` and `deploy`. Since #1155 it is not: the deploy step is
        `deploy_security_scan`, because ids must be globally unique once
        gate-ness INHERITS by id into manifest-resolved steps. The invariant is
        unchanged and is the reason inheritance by id is safe at all, so the
        test stays; only its example is gone, and no builtin id repeats across
        plans today. That is not something to assert here - this test must keep
        working the day one does.
        """
        by_id: dict[str, set[bool]] = {}
        for _, step in self._all_builtin_steps():
            by_id.setdefault(step.id, set()).add(step.gate)
        conflicted = sorted(sid for sid, vals in by_id.items() if len(vals) > 1)
        assert not conflicted, (
            f"these ids are declared a gate in one plan and not in another: "
            f"{conflicted}. GATE_STEP_IDS is keyed by id, so one of the two "
            f"declarations would be silently ignored."
        )

    def test_security_scan_is_a_gate(self):
        """The #890 pin, written as a LITERAL rather than derived from the set.

        The test this replaces asked "are the ids in GATE_STEP_IDS handled?" and
        derived its expectations from the same set whose contents were the
        defect, so a missing gate was invisible to it. Naming the id here is the
        point: this assertion cannot be satisfied by the set agreeing with itself.
        """
        assert "security_scan" in GATE_STEP_IDS
        assert {"lint", "test", "typecheck", "security_scan"} <= GATE_STEP_IDS


class TestSkippedGateReporting:
    """A quality gate that skip_if-skipped verified nothing about the change, so
    the runner must not print a bare `completed successfully` - it names the
    skipped gates and carries them in RunResult.skipped_steps for
    flow-finish-gate.sh to surface as `warn` (issue #628). A skipped NON-gate
    step is a legitimate skip and must NOT trip the warning.

    THE RULE CHANGED HERE, AND THE OLD ONE IS WORTH KNOWING (#628 -> #890).

    This docstring used to read "A skipped NON-gate step (security_scan) is a
    legitimate skip and must NOT trip the warning", and the test below used
    `security_scan` by name as its worked example. That was a deliberate #628
    exemption, not an oversight, and it rested on a CATEGORICAL reading: a gate
    is one of the three #617 quality gates, and the security scan is not one of
    them.

    #890 reverses it, on the ground that the category is not the question this
    set is consulted for. The question is what a SKIP MEANS, and
    `security_scan`'s skip_if is `! python3 -c 'import lib.security'` - it skips
    exactly when the scanner is NOT INSTALLED. That is the same thing #628 says
    about a skipped lint or test: the gate verified nothing. A containerised
    session has no CPP checkout, so before this it could run its finish gate,
    skip the security scan, and report a bare `ok` with no mention of it.

    The two readings agree for lint/test/typecheck and disagree only here, which
    is why the exemption looked right for three releases.

    It does not make the warn permanent noise: PYTHONPATH points at the CPP
    checkout wherever it is, so the step RUNS for any target repo while CPP is
    reachable and skips only when it is not.

    `stale_commit_check` is the non-gate exemplar now - its skip_if is "not on
    main, or offline", so skipping it is designed-normal and proves nothing was
    missed. That is what a legitimate non-gate skip looks like."""

    @staticmethod
    def _always_skip(step_id: str, *, gate: bool) -> StepDef:
        # skip_if 'true' always skips - mimics a Makefile-less repo with the tool
        # unconfigured (the real skip_if resolves to the same outcome there).
        #
        # `gate` IS DECLARED BY THE CALLER AND HAS NO DEFAULT (#1155). The runner
        # used to decide gate-ness by looking the id up in GATE_STEP_IDS, so
        # these fixtures could stay silent and the test distinguished a gate
        # from a non-gate by NAME. Since #1155 the declaration travels on the
        # step, and that is the whole point of the issue - so the fixture has to
        # say which it is, and the test's subject becomes "a skipped step
        # DECLARED a gate qualifies the run", which is the runner behaviour
        # actually under test. Whether `typecheck` is in fact a gate is a
        # different question, owned by the BUILTIN_PLANS declarations and
        # TestGateDeclarationIsExhaustive.
        #
        # No default, deliberately: a default would let a new call site omit it
        # and silently test the non-gate path while reading like the gate one.
        return StepDef(
            id=step_id, command="false", skip_if="true", timeout_seconds=30, gate=gate
        )

    @staticmethod
    def _always_run(step_id: str, *, gate: bool = True) -> StepDef:
        # Defaults True: every call site here runs a real quality gate, and the
        # steps that RAN are not what any assertion in this class turns on.
        return StepDef(id=step_id, command="true", timeout_seconds=30, gate=gate)

    def test_skipped_gates_qualify_the_run(self, tmp_project: Path):
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        result = runner.run(
            "check",
            step_defs=[
                self._always_skip("lint", gate=True),
                self._always_skip("test", gate=True),
                self._always_skip("typecheck", gate=True),
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
            step_defs=[
                self._always_run("lint"),
                # The non-gate exemplar: declared NOT a gate, so its skip is
                # designed-normal and must not qualify the run.
                self._always_skip("stale_commit_check", gate=False),
            ],
        )
        assert result.success
        # The skip is recorded, but this step is not a gate - no false green.
        assert result.skipped_steps == ["stale_commit_check"]

        text = log.getvalue()
        assert "completed successfully" in text
        assert "SKIPPED GATES" not in text

    def test_a_skipped_security_scan_now_qualifies_the_run(self, tmp_project: Path):
        """The #890 regression, asserted on BEHAVIOUR rather than on set membership.

        A containerised session has no CPP checkout, so `import lib.security`
        fails and the step skips. Before #890 that run printed a bare `completed
        successfully`: the gate had verified nothing about the change's security
        and said nothing about it.
        """
        log = StringIO()
        runner = DeterministicRunner(project_root=tmp_project, output=log)
        result = runner.run(
            "finish",
            step_defs=[
                self._always_run("lint"),
                self._always_skip("security_scan", gate=True),
            ],
        )
        assert result.success, "a skip is exit 0 - this surfaces the hole, it does not invent a failure"
        assert result.skipped_steps == ["security_scan"]

        text = log.getvalue()
        assert "completed WITH WARNINGS" in text
        assert "SKIPPED GATES: security_scan" in text
        assert "completed successfully" not in text

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
                self._always_skip("typecheck", gate=True),
            ],
        )
        assert result.success
        assert result.skipped_steps == ["typecheck"]
        assert result.warnings  # the #621 no-tests warning
        text = log.getvalue()
        assert "SKIPPED GATES: typecheck" in text

        # Assert on the CLOSING LINE rather than anywhere in the log (#939).
        # This read `"#621" in text`, which the issue tag in the warning body
        # satisfies from somewhere else entirely - so it could pass while the
        # closing line had dropped the qualifier the test exists to protect.
        closing = next(
            line for line in text.splitlines() if "completed WITH WARNINGS" in line
        )
        assert "SKIPPED GATES: typecheck" in closing
        assert "qualification" in closing, (
            "the closing line must still name the test-step qualifier "
            "alongside the skipped gate, not drop one of the two"
        )
        # The CAUSE is named by the warning itself, not asserted generically by
        # the closing line: `warnings` carries #621, #838 and #939 findings and
        # only #621 means "executed no tests" (issue #939).
        assert "executed NO tests" in " ".join(result.warnings)
        assert "#621" in " ".join(result.warnings)


class TestResumeSettlesDeferredGates:
    """A resume must settle what the failed run left open (issue #1166).

    The failed run deferred lint/test/typecheck into `verify` and recorded them
    NOT_RUN when verify failed - honest, because make stops at its first failing
    prerequisite. The resume re-runs only verify, which now passes, and before
    #1166 those three records still said `not-run`: `flow-finish-gate.sh`
    refuses a success carrying one (#1152) and reported
    `fail (recorded not-run: lint test typecheck)`. A genuinely green retry
    rejected, naming gates that did run.

    SETTLED FROM A FRESH DERIVATION, NEVER FROM THE PERSISTED MAP. The record
    carries `not_run_reason` naming the aggregate, so the relationship is
    reconstructable - and reconstructing it is the false green these tests
    exist to refuse, because the fix may have changed the Makefile.
    """

    @staticmethod
    def _plan(makefile_lists_lint: bool, lint_ok: bool):
        """The finish shape in miniature: three gates, an aggregate, a scan."""
        prereqs = "lint test typecheck" if makefile_lists_lint else "test typecheck"
        return prereqs, lint_ok

    @requires_make
    def test_a_green_retry_settles_the_not_run_records_as_subsumed(self, tmp_path):
        """Fail at the aggregate, fix the tree, resume: the three must settle.

        Measured on 9162b8e: verify passes on the resume, the runner returns
        success, and lint/test/typecheck are still `not-run` - so the gate
        refuses the pass. Here they end `subsumed`, and `security_scan` is NOT
        re-run, because it already succeeded.
        """
        (tmp_path / "Makefile").write_text(
            "lint:\n\t@true\ntest:\n\t@true\ntypecheck:\n\t@true\n"
            "verify: lint test typecheck\n\t@exit 1\n"
        )
        steps = [
            StepDef(id="lint", command="make lint", gate=True, timeout_seconds=60),
            StepDef(id="test", command="make test", gate=True, timeout_seconds=60),
            StepDef(id="typecheck", command="make typecheck", gate=True, timeout_seconds=60),
            StepDef(id="security_scan", command="echo scanned", gate=True, timeout_seconds=60),
            StepDef(id="verify", command="make verify", gate=True, timeout_seconds=60),
        ]
        runner = DeterministicRunner(project_root=tmp_path, output=StringIO())
        first = runner.run("finish", step_defs=steps)
        assert not first.success, "verify must fail in phase 1"
        assert _not_run_ids(first) == ["lint", "test", "typecheck"], (
            f"the failed run must record the three as not-run, got "
            f"{_not_run_ids(first)}"
        )

        # FIX THE TREE. The Makefile still lists all three, so the resumed
        # derivation agrees with the failed one and they re-defer.
        (tmp_path / "Makefile").write_text(
            "lint:\n\t@true\ntest:\n\t@true\ntypecheck:\n\t@true\n"
            "verify: lint test typecheck\n\t@true\n"
        )
        second = runner.run("finish", step_defs=steps)
        assert second.success, "the retry is green and must be reported so"
        assert _not_run_ids(second) == [], (
            f"a success cannot carry a not-run record - the gate refuses it "
            f"(#1152). Got {_not_run_ids(second)}"
        )
        assert sorted(second.subsumed_gates) == ["lint", "test", "typecheck"]

        by_id = {d["id"]: d for d in second.step_details}
        assert by_id["security_scan"]["carried_from_previous_run"] is True, (
            "security_scan passed in phase 1 and must not be re-run by the "
            "resume; replaying a gate must not drag its neighbours back in"
        )

    @requires_make
    def test_a_gate_the_resumed_tree_no_longer_subsumes_is_REPLAYED(self, tmp_path):
        """The path where settling from the persisted map is a FALSE GREEN.

        Phase 1's Makefile lists lint under verify; lint is broken and verify
        fails, so lint is recorded not-run naming verify. Phase 2's Makefile no
        longer lists lint - the "fix" removed it - and lint is still broken.

        Settling from the persisted map records lint `subsumed` by a verify that
        does not run it, and reports ok: a check recorded as passed that nothing
        executed. Re-deriving finds lint unsubsumed, REPLAYS it, and it fails.
        """
        (tmp_path / "Makefile").write_text(
            "lint:\n\t@exit 1\ntest:\n\t@true\n"
            "verify: lint test\n\t@true\n"
        )
        steps = [
            StepDef(id="lint", command="make lint", gate=True, timeout_seconds=60),
            StepDef(id="test", command="make test", gate=True, timeout_seconds=60),
            # A SUCCEEDING, NON-DEFERRED STEP BETWEEN THE GATES AND THE
            # AGGREGATE. Without it `current_index` never advances past the
            # deferred gates, the resume re-enters them by accident, and this
            # test passes on the UNFIXED code - measured. The real finish plan
            # has exactly this shape (security_scan sits between typecheck and
            # verify), which is why the defect is reachable there.
            StepDef(id="security_scan", command="echo scanned", gate=True, timeout_seconds=60),
            StepDef(id="verify", command="make verify", gate=True, timeout_seconds=60),
        ]
        runner = DeterministicRunner(project_root=tmp_path, output=StringIO())
        first = runner.run("finish", step_defs=steps)
        assert not first.success
        assert "lint" in _not_run_ids(first)

        # THE TREE LEAVES lint BEHIND. verify no longer runs it; lint is still
        # broken. Nothing is going to run lint unless lint runs.
        (tmp_path / "Makefile").write_text(
            "lint:\n\t@exit 1\ntest:\n\t@true\n"
            "verify: test\n\t@true\n"
        )
        second = runner.run("finish", step_defs=steps)
        assert not second.success, (
            "lint is broken and no aggregate runs it any more, so the resume "
            "must REPLAY it and fail. Reporting success here is the false "
            "green that settling from the persisted map produces."
        )
        assert second.failed_step == "lint"
        assert "lint" not in second.subsumed_gates

    @requires_make
    def test_a_replayed_step_uses_its_ORIGINAL_step_def(self, tmp_path):
        """Replay runs the StepDef the plan declares, env included.

        THE CANARY IS `env`, NOT THE COMMAND, and that is forced rather than
        stylistic: to be deferred at all the command must be byte-equal to
        `make lint` (#1165 recognises by equality with its producer), so a
        command decorated to leave a marker is never subsumed and never
        deferred - it just runs in phase 1, and the test passes having exercised
        nothing. Measured: an earlier draft did exactly that. `env` rides along
        with the StepDef without changing the command's bytes, so it can prove
        the ORIGINAL definition was used and still reach the deferred path.
        """
        (tmp_path / "Makefile").write_text(
            "lint:\n\t@echo \"$$REPLAY_CANARY\" > canary.txt\n\t@exit 1\n"
            "test:\n\t@true\nverify: lint test\n\t@true\n"
        )
        steps = [
            StepDef(
                id="lint",
                command="make lint",
                gate=True,
                timeout_seconds=60,
                env={"REPLAY_CANARY": "original-stepdef"},
            ),
            StepDef(id="test", command="make test", gate=True, timeout_seconds=60),
            StepDef(id="security_scan", command="echo scanned", gate=True, timeout_seconds=60),
            # THE AGGREGATE CARRIES THE SAME env, and it has to. #1165 refuses
            # to subsume a prerequisite whose step declares a different
            # environment from the aggregate's - the same command under a
            # different env is not the same check - so an env set on lint alone
            # makes lint UNSUBSUMABLE and it simply runs in phase 1, testing
            # nothing. Measured: that is what the first draft did.
            StepDef(
                id="verify",
                command="make verify",
                gate=True,
                timeout_seconds=60,
                env={"REPLAY_CANARY": "original-stepdef"},
            ),
        ]
        runner = DeterministicRunner(project_root=tmp_path, output=StringIO())
        first = runner.run("finish", step_defs=steps)
        assert not first.success
        assert "lint" in _not_run_ids(first), "lint must be DEFERRED, not run, in phase 1"

        # The aggregate's own run of the lint target wrote the file with an
        # empty canary (the verify step carries no such env). Remove it, so what
        # the assertion reads can only have come from the replayed step.
        (tmp_path / "canary.txt").unlink(missing_ok=True)
        (tmp_path / "Makefile").write_text(
            "lint:\n\t@echo \"$$REPLAY_CANARY\" > canary.txt\n\t@exit 1\n"
            "test:\n\t@true\nverify: test\n\t@true\n"
        )
        second = runner.run("finish", step_defs=steps)
        assert not second.success and second.failed_step == "lint"
        canary = (tmp_path / "canary.txt")
        assert canary.is_file(), "the replayed lint must actually have run"
        assert canary.read_text().strip() == "original-stepdef", (
            "the replayed step must carry the env from the StepDef the plan "
            f"declares, not a reconstruction. Got {canary.read_text()!r}"
        )

    @requires_make
    def test_a_FAILED_replay_is_reopened_by_the_NEXT_resume(self, tmp_path):
        """The false green this fix introduced, and the review caught.

        Reopening only NOT_RUN records left a hole exactly where replay had
        just made one reachable: a replayed step that FAILS is recorded FAILED
        below the frontier, which is not NOT_RUN, so the next resume skipped it
        entirely. Measured on the first draft of this fix - fail at verify,
        drop lint from its prerequisites, let the replayed lint fail, and the
        THIRD invocation returned success=True with lint still recorded
        `failed` and still broken.

        Worse than the defect #1166 reports: that one REJECTED a green retry,
        this one ACCEPTS a red tree. A repair for a false negative that
        produces a false positive has moved the problem, not fixed it.
        """
        from lib.cicd.steps import StepDef

        def makefile(verify_prereqs, lint_ok):
            (tmp_path / "Makefile").write_text(
                f"lint:\n\t@{'true' if lint_ok else 'exit 1'}\n"
                f"test:\n\t@true\nsecurity_scan:\n\t@true\n"
                f"verify: {verify_prereqs}\n\t@true\n"
            )

        steps = [
            StepDef(id="lint", command="make lint", gate=True, timeout_seconds=60),
            StepDef(id="test", command="make test", gate=True, timeout_seconds=60),
            StepDef(id="security_scan", command="echo scanned", gate=True, timeout_seconds=60),
            StepDef(id="verify", command="make verify", gate=True, timeout_seconds=60),
        ]
        runner = DeterministicRunner(project_root=tmp_path, output=StringIO())

        makefile("lint test", lint_ok=False)
        assert not runner.run("finish", step_defs=steps).success

        # The tree drops lint from verify; lint is still broken, so the replay
        # runs it and it fails.
        makefile("test", lint_ok=False)
        second = runner.run("finish", step_defs=steps)
        assert not second.success and second.failed_step == "lint"

        # THE THIRD INVOCATION. Nothing has been fixed, so nothing may pass.
        third = runner.run("finish", step_defs=steps)
        assert not third.success, (
            "lint is still broken and no aggregate runs it. A resume that "
            "skips a FAILED replay reports success over a red tree."
        )
        assert third.failed_step == "lint"

        # And when it IS fixed, the run goes green without re-running the
        # neighbour that already passed.
        makefile("test", lint_ok=True)
        fourth = runner.run("finish", step_defs=steps)
        assert fourth.success
        assert fourth.carried_from_previous_run == ["security_scan"], (
            "a successful replay must not drag settled neighbours back in - "
            "the frontier may never retreat. Got "
            f"{fourth.carried_from_previous_run}"
        )

    @requires_make
    def test_a_settled_record_carries_no_stale_failure_reason(self, tmp_path):
        """`status: subsumed` and `not_run_reason: verify failed` cannot both hold.

        A re-deferred gate arrives at `mark_step_subsumed` carrying the reason
        the PREVIOUS run recorded, and leaving it attached publishes two
        accounts of one gate in `step_details` - one of them describing a run
        that has since been superseded. Measured before the fix.
        """
        from lib.cicd.steps import StepDef

        def makefile(verify_ok):
            (tmp_path / "Makefile").write_text(
                "lint:\n\t@true\ntest:\n\t@true\nsecurity_scan:\n\t@true\n"
                f"verify: lint test\n\t@{'true' if verify_ok else 'exit 1'}\n"
            )

        steps = [
            StepDef(id="lint", command="make lint", gate=True, timeout_seconds=60),
            StepDef(id="test", command="make test", gate=True, timeout_seconds=60),
            StepDef(id="security_scan", command="echo scanned", gate=True, timeout_seconds=60),
            StepDef(id="verify", command="make verify", gate=True, timeout_seconds=60),
        ]
        runner = DeterministicRunner(project_root=tmp_path, output=StringIO())
        makefile(verify_ok=False)
        assert not runner.run("finish", step_defs=steps).success
        makefile(verify_ok=True)
        second = runner.run("finish", step_defs=steps)
        assert second.success

        for entry in second.step_details:
            if entry.get("status") == "subsumed":
                assert "not_run_reason" not in entry, (
                    f"{entry['id']} is subsumed and still carries "
                    f"{entry.get('not_run_reason')!r} - two accounts of one gate"
                )

    @requires_make
    def test_a_resume_whose_aggregate_fails_AGAIN_keeps_the_records(self, tmp_path):
        """Failing twice must read exactly like failing once.

        A GUARD, NOT A REGRESSION TEST, and labelled so deliberately: it passes
        on 9162b8e too, because there the records are never touched and here
        they are re-deferred and then re-marked - same observable either way.
        Its red case is this FIX going wrong (settling a record the retry never
        earned), not the old code. Calling it a regression test would be a name
        claiming more than the assertion does.
        """
        (tmp_path / "Makefile").write_text(
            "lint:\n\t@true\ntest:\n\t@true\nverify: lint test\n\t@exit 1\n"
        )
        steps = [
            StepDef(id="lint", command="make lint", gate=True, timeout_seconds=60),
            StepDef(id="test", command="make test", gate=True, timeout_seconds=60),
            # A SUCCEEDING, NON-DEFERRED STEP BETWEEN THE GATES AND THE
            # AGGREGATE. Without it `current_index` never advances past the
            # deferred gates, the resume re-enters them by accident, and this
            # test passes on the UNFIXED code - measured. The real finish plan
            # has exactly this shape (security_scan sits between typecheck and
            # verify), which is why the defect is reachable there.
            StepDef(id="security_scan", command="echo scanned", gate=True, timeout_seconds=60),
            StepDef(id="verify", command="make verify", gate=True, timeout_seconds=60),
        ]
        runner = DeterministicRunner(project_root=tmp_path, output=StringIO())
        assert not runner.run("finish", step_defs=steps).success
        second = runner.run("finish", step_defs=steps)
        assert not second.success
        assert _not_run_ids(second) == ["lint", "test"], (
            "a retry that fails again leaves the not-run records standing, "
            f"exactly as a fresh run does. Got {_not_run_ids(second)}"
        )

    @requires_make
    def test_a_tree_that_left_the_grammar_between_runs_replays_everything(
        self, tmp_path
    ):
        """The resumed derivation goes through the same grammar check (#1165).

        A Makefile that acquires a conditional between the failure and the
        resume is outside the grammar, so it subsumes NOTHING - and every
        open record must replay rather than settle.
        """
        (tmp_path / "Makefile").write_text(
            "lint:\n\t@true\ntest:\n\t@true\nverify: lint test\n\t@exit 1\n"
        )
        steps = [
            StepDef(id="lint", command="make lint", gate=True, timeout_seconds=60),
            StepDef(id="test", command="make test", gate=True, timeout_seconds=60),
            # A SUCCEEDING, NON-DEFERRED STEP BETWEEN THE GATES AND THE
            # AGGREGATE. Without it `current_index` never advances past the
            # deferred gates, the resume re-enters them by accident, and this
            # test passes on the UNFIXED code - measured. The real finish plan
            # has exactly this shape (security_scan sits between typecheck and
            # verify), which is why the defect is reachable there.
            StepDef(id="security_scan", command="echo scanned", gate=True, timeout_seconds=60),
            StepDef(id="verify", command="make verify", gate=True, timeout_seconds=60),
        ]
        runner = DeterministicRunner(project_root=tmp_path, output=StringIO())
        assert not runner.run("finish", step_defs=steps).success

        (tmp_path / "Makefile").write_text(
            "lint:\n\t@true\ntest:\n\t@true\n"
            "ifeq (1,1)\nverify: lint test\nendif\n\t@true\n"
        )
        second = runner.run("finish", step_defs=steps)
        assert second.subsumed_gates == {}, (
            "a tree outside the grammar subsumes nothing, on a resume as on a "
            f"fresh run. Got {second.subsumed_gates}"
        )
        assert _not_run_ids(second) == [], (
            "and nothing may stay not-run: those gates were replayed"
        )


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


class TestNonTestStageCoverage:
    """A non-test gate must carry what it examined, not just {id, status} (#1027).

    The reported defect: `lint`, `typecheck` and `security_scan` emitted
    `{id, status}` and nothing else, so `status: "success"` was returned both by
    a stage that examined the whole tree and by one that examined nothing. Only
    the `test` step carried the "it ran and was not empty" assertion.

    The commands below echo REAL tool output - captured from ruff 0.15.4, mypy
    and `python -m lib.security gate` on this host - rather than a shape written
    to match the parser.
    """

    def test_a_stage_that_examined_nothing_warns(self, tmp_project: Path):
        steps = [
            StepDef(
                id="security_scan",
                command=(
                    "echo 'SECURITY_GATE: flow_finish PASS (blocked=0 warned=0; "
                    "secrets-scanned=0 skipped-checks=3; blocks-on=CRITICAL warns-on=HIGH)'"
                ),
                timeout_seconds=30,
            ),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        # The step still PASSES - coverage is advisory and never changes status.
        assert result.success
        assert result.coverage["security_scan"]["state"] == "zero"
        assert any(
            "examined NO" in w and "security_scan" in w for w in result.warnings
        ), result.warnings

    def test_a_stage_that_examined_something_does_not_warn(self, tmp_project: Path):
        """The half that catches a blind detector.

        A parser reporting `zero` for everything would satisfy the test above
        and warn on every real run, which is how a warning stops being read.
        """
        steps = [
            StepDef(
                id="typecheck",
                command="echo 'Success: no issues found in 47 source files'",
                timeout_seconds=30,
            ),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        assert result.success
        assert result.coverage["typecheck"]["state"] == "covered"
        assert result.coverage["typecheck"]["units"] == 47
        assert not result.warnings, result.warnings

    def test_a_silent_stage_is_unknown_and_does_not_warn(self, tmp_project: Path):
        """Silence reads UNKNOWN, and UNKNOWN is recorded without being loud.

        This is the deliberate bound: warning here would fire on every lint
        harness CPP cannot parse, on every run. Recording it is still the fix -
        the reader sees an unproven stage instead of a bare success.
        """
        steps = [
            StepDef(id="lint", command="echo 'All checks passed!'", timeout_seconds=30),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        assert result.success
        # An EXPLICIT unknown record, not an absent key (cross-model review).
        # This test previously asserted the absence, which is the bare
        # {id, status} shape #1027 exists to replace - so it pinned the defect
        # rather than the fix, and the module docstring's promise that an
        # unmeasurable stage reports `unknown` was contradicted by the producer.
        assert result.coverage["lint"]["state"] == "unknown"
        assert result.coverage["lint"]["units"] is None
        assert not result.warnings, result.warnings

    def test_coverage_is_not_parsed_for_a_test_step(self, tmp_project: Path):
        """`tests` already answers this question for a test step.

        Answering it twice in two shapes would leave a reader unsure which one
        the gate consults, so coverage is scoped to non-test steps.
        """
        steps = [
            StepDef(
                id="test",
                command=(
                    "echo 'Success: no issues found in 47 source files' && "
                    "echo '3 passed in 0.01s'"
                ),
                timeout_seconds=30,
            ),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        assert result.success
        assert result.coverage == {}, "a test step's answer is `tests`, not `coverage`"
        assert result.tests["test"]["passed"] == 3

    def test_coverage_reaches_step_details_and_the_json(self, tmp_project: Path):
        """A field the gate cannot read cannot be acted on (the #812 lesson)."""
        steps = [
            StepDef(
                id="typecheck",
                command="echo 'Success: no issues found in 12 source files'",
                timeout_seconds=30,
            ),
        ]
        runner = DeterministicRunner(project_root=tmp_project, output=StringIO())
        result = runner.run("check", step_defs=steps)

        entry = next(e for e in result.step_details if e["id"] == "typecheck")
        assert entry["coverage"]["units"] == 12
        assert result.to_dict()["coverage"]["typecheck"]["units"] == 12


@requires_git
class TestCarriedZeroCoverageSurvivesResume:
    """A zero-coverage verdict earned before a crash must survive the resume.

    Cross-model review finding (#1027). `coverage` and `warnings` are rebuilt
    empty on every invocation and were only populated from the resume index
    onward, so a lint stage that examined NOTHING, followed by a transient
    failure, followed by a clean resume on a verified-unchanged tree, kept its
    evidence in `step_details` and lost it from the top-level roll-up the shell
    gate actually reads. The completed run then reported `ok`/0 - #1027's own
    false green, restored by resume, for the very stage #1027 is about.

    The tree is deliberately UNCHANGED between attempts, so the #804 carry is
    verified and the resume is the genuine crash-recovery path rather than a
    discard.
    """

    def _steps(self, test_cmd: str) -> list[StepDef]:
        return [
            # A non-test gate that states, in real ruff wording, that it had
            # no input.
            StepDef(
                id="lint",
                command=(
                    "echo 'warning: No Python files found under the given path(s)' >&2; "
                    "echo 'All checks passed!'"
                ),
                timeout_seconds=30,
            ),
            StepDef(id="test", command=test_cmd, timeout_seconds=30),
        ]

    def test_a_carried_zero_coverage_step_still_warns_after_resume(
        self, tmp_project: Path
    ):
        _git_repo(tmp_project)
        log = StringIO()

        before_sig = compute_tree_signature(tmp_project)
        first = DeterministicRunner(project_root=tmp_project, output=log).run(
            "finish", step_defs=self._steps("exit 1")
        )
        assert not first.success
        assert first.coverage["lint"]["state"] == "zero", (
            "precondition: the first attempt must actually have recorded the "
            "zero-coverage fact this test is about carrying"
        )

        # Simulated crash: nothing about the tree changes.
        after_sig = compute_tree_signature(tmp_project)
        assert before_sig is not None and after_sig is not None
        assert before_sig == after_sig

        second = DeterministicRunner(project_root=tmp_project, output=log).run(
            "finish", step_defs=self._steps("echo 'test ok'")
        )

        assert second.success
        assert second.carried_from_previous_run == ["lint"], (
            "precondition: lint must be CARRIED, not re-executed - otherwise "
            "this test passes for the wrong reason"
        )
        assert second.tree_verified is True
        # The roll-up the shell gate greps, not just step_details.
        assert second.coverage["lint"]["state"] == "zero"
        assert second.to_dict()["coverage"]["lint"]["state"] == "zero"
        assert any("examined NO" in w for w in second.warnings), second.warnings
        assert any("carried from an earlier invocation" in w for w in second.warnings)

    def test_a_carried_covered_step_does_not_manufacture_a_warning(
        self, tmp_project: Path
    ):
        """The other half: the rebuild must not warn about a healthy carry."""
        _git_repo(tmp_project)
        log = StringIO()
        steps = lambda cmd: [  # noqa: E731
            StepDef(
                id="typecheck",
                command="echo 'Success: no issues found in 12 source files'",
                timeout_seconds=30,
            ),
            StepDef(id="test", command=cmd, timeout_seconds=30),
        ]
        first = DeterministicRunner(project_root=tmp_project, output=log).run(
            "finish", step_defs=steps("exit 1")
        )
        assert not first.success

        second = DeterministicRunner(project_root=tmp_project, output=log).run(
            "finish", step_defs=steps("echo 'test ok'")
        )
        assert second.success
        assert second.carried_from_previous_run == ["typecheck"]
        assert second.coverage["typecheck"]["units"] == 12
        # Scoped to COVERAGE warnings: the `test` step here echoes no parseable
        # summary, so #952's pre-existing UNKNOWN guard fires on it. Asserting
        # `not second.warnings` would make this test fail for a reason that has
        # nothing to do with the carry it is pinning.
        assert not [w for w in second.warnings if "examined NO" in w], second.warnings

    def test_a_carried_partially_empty_step_still_warns_after_resume(
        self, tmp_project: Path
    ):
        """The `covered`-with-an-empty-invocation carry (review, second pass).

        Rebuilding only the `zero` state dropped this one: a stage with one
        empty and one populated invocation is `covered`, so across a resume its
        warning vanished while the equivalent live run kept it - the same
        roll-up hole, one state over.
        """
        _git_repo(tmp_project)
        log = StringIO()
        steps = lambda cmd: [  # noqa: E731
            StepDef(
                id="typecheck",
                command=(
                    "echo 'Success: no issues found in 0 source files'; "
                    "echo 'Success: no issues found in 20 source files'"
                ),
                timeout_seconds=30,
            ),
            StepDef(id="test", command=cmd, timeout_seconds=30),
        ]
        first = DeterministicRunner(project_root=tmp_project, output=log).run(
            "finish", step_defs=steps("exit 1")
        )
        assert not first.success
        assert first.coverage["typecheck"]["state"] == "covered"
        assert first.coverage["typecheck"]["empty_invocations"] == 1, (
            "precondition: the first attempt must record the partially-empty fact"
        )

        second = DeterministicRunner(project_root=tmp_project, output=log).run(
            "finish", step_defs=steps("echo 'test ok'")
        )
        assert second.success
        assert second.carried_from_previous_run == ["typecheck"]
        assert second.coverage["typecheck"]["empty_invocations"] == 1
        assert any(
            "invocations examined NOTHING" in w for w in second.warnings
        ), second.warnings




class TestSubsumedGates:
    """A gate an aggregate already runs is not run twice (issue #1152).

    `make verify` here lists `lint test typecheck` among its prerequisites, so
    the finish plan executed those three twice: 390.77s against 233.44s for the
    same coverage. The remedy must not weaken what the gate proves, and the two
    ways it could are what these tests pin.
    """

    @staticmethod
    def _tree(tmp_path, makefile: str):
        (tmp_path / "Makefile").write_text(makefile)
        return tmp_path

    def test_the_subsumed_set_on_this_repository_is_exactly_the_three(self):
        """THE PARSER PIN, from the consumer side (#1152).

        The derivation reads this repository's own `verify:` rule through the
        canonical Makefile reader - the one `check-ci-coverage.py` loads - and
        that reader now feeds two instruments. Pinning it from here rather than
        by testing the parser directly means a parser change that silently
        drops prerequisites fails as a CHANGE IN WHAT IS DEDUPLICATED, which is
        the consequence anyone would care about.

        The count is asserted too. `lib/cicd/makefile.py::parse_makefile` returns
        9 of these 29 - it stops at the first physical line and takes the
        trailing backslash as a dependency (#1162) - and it would have been
        RIGHT BY LUCK for the subsumed set, because lint, test and typecheck all
        sit on that first line. A set assertion alone would not have caught the
        wrong parser being used; the count does.
        """

        from lib.cicd.steps import get_plan_steps, subsumed_gate_ids

        root = Path(__file__).resolve().parent.parent
        steps = get_plan_steps("finish", project_root=str(root))
        subsumed, _refusals = subsumed_gate_ids("finish", steps, str(root))

        assert set(subsumed) == {"lint", "test", "typecheck"}
        assert set(subsumed.values()) == {"verify"}

        # THE PIN MOVED FROM THE TEXT TO MAKE (#1165). It used to read this
        # repository's `verify:` rule with the canonical TEXTUAL parser, and a
        # textual reader cannot evaluate `ifeq` - so it names prerequisites make
        # will never run, which is precisely how a broken lint passed as a
        # `subsumed` gate. The count is still the tripwire; the authority is now
        # the thing that will actually run them.
        from lib.cicd.steps import make_prerequisites

        prereqs = make_prerequisites(str(root), "verify")
        assert prereqs is not None, "make could not be asked what `verify` runs"
        assert len(prereqs) == 31, (
            f"make reports {len(prereqs)} prerequisites for this repository's "
            f"`verify` rule, not 31. If the Makefile genuinely changed, update "
            f"the number; if it did not, something changed what make RESOLVES - "
            f"a conditional, an include, or a variable - and the subsumed set "
            f"moved with it (#1165)"
        )
        assert "\\" not in prereqs, "make never yields a line continuation as a prerequisite"

    @requires_make
    def test_subsumed_is_asserted_only_when_the_aggregate_PASSES(self, tmp_path):
        """The committed case for the condition this issue turns on (#1152).

        `make` stops at its first failing prerequisite. When verify fails at
        lint, test and typecheck were never reached - so recording them as
        `subsumed` would claim they ran and passed inside an aggregate that
        stopped before them. That is a false green produced by the COST fix,
        which is the one outcome this change was not allowed to have.
        """
        import io

        from lib.cicd.runner import DeterministicRunner

        root = self._tree(
            tmp_path,
            "lint:\n\t@echo BROKEN; exit 1\n"
            "test:\n\t@echo test ran\n"
            "typecheck:\n\t@echo typecheck ran\n"
            "security_scan:\n\t@true\n"
            "verify: lint test typecheck\n\t@echo verify ran\n",
        )
        result = DeterministicRunner(
            project_root=root, output=io.StringIO()
        ).run("finish")

        assert result.success is False
        assert result.to_dict()["subsumed_gates"] == {}, (
            "an aggregate that FAILED cannot have run the gates deferred to it"
        )
        by_id = {e["id"]: e for e in result.step_details}
        for gate in ("lint", "test", "typecheck"):
            assert by_id[gate]["status"] == "not-run"
            assert "verify failed" in by_id[gate]["not_run_reason"]
        # make named the prerequisite it stopped at, so the report does too -
        # `verify` has 29 of them and "verify failed" searches all 29.
        assert result.failed_prerequisite == "lint"
        assert by_id["lint"]["not_run_reason"].endswith("at prerequisite lint")

    @requires_make
    def test_a_gate_the_aggregate_does_not_LIST_still_runs(self, tmp_path):
        """THE RED CASE. `verify:` names test and typecheck but NOT lint, and
        lint is broken. The gate must still run lint and red.

        This is what a subsumption rule gets wrong when it assumes the presence
        of a `verify:` target covers the three, instead of DERIVING which ones
        it names. Under that assumption lint is skipped, verify never runs it,
        and the gate reports ok over a broken lint.
        """
        import io

        from lib.cicd.runner import DeterministicRunner
        from lib.cicd.steps import get_plan_steps, subsumed_gate_ids

        root = self._tree(
            tmp_path,
            "lint:\n\t@echo LINT IS BROKEN; exit 1\n"
            "test:\n\t@echo test ran\n"
            "typecheck:\n\t@echo typecheck ran\n"
            "security_scan:\n\t@true\n"
            "verify: test typecheck\n\t@echo verify ran\n",
        )
        steps = get_plan_steps("finish", project_root=str(root))
        subsumed, _refusals = subsumed_gate_ids("finish", steps, str(root))
        assert "lint" not in subsumed, "lint is not a prerequisite of this verify"

        result = DeterministicRunner(
            project_root=root, output=io.StringIO()
        ).run("finish")
        assert result.success is False
        assert result.failed_step == "lint"

    @requires_make
    def test_no_aggregate_means_nothing_is_subsumed(self, tmp_path):
        """The guard rail, and the bare-repository case.

        With no `verify:` target there is nothing to derive from, so all four
        gates run exactly as before - by construction rather than by a special
        case. A derivation that returned a non-empty map here would be skipping
        gates on the strength of a target that does not exist.
        """
        from lib.cicd.steps import get_plan_steps, subsumed_gate_ids

        root = self._tree(
            tmp_path, "lint:\n\t@true\ntest:\n\t@true\ntypecheck:\n\t@true\n"
        )
        steps = get_plan_steps("finish", project_root=str(root))
        assert subsumed_gate_ids("finish", steps, str(root))[0] == {}

    @requires_make
    def test_step_details_carry_wall_time(self, tmp_path):
        """The evidence channel this issue's verdict rests on (#1152).

        The runner published no timing at all, so every before/after figure had
        to be measured outside the gate and no later reader could check the
        claim against the artifact that made it.
        """
        import io

        from lib.cicd.runner import DeterministicRunner

        root = self._tree(
            tmp_path,
            "lint:\n\t@true\ntest:\n\t@true\ntypecheck:\n\t@true\n"
            "security_scan:\n\t@true\n",
        )
        result = DeterministicRunner(
            project_root=root, output=io.StringIO()
        ).run("finish")
        executed = [
            e for e in result.step_details if e["status"] == "success"
        ]
        assert executed, "nothing ran, so there is no timing to assert"
        for entry in executed:
            assert "duration_seconds" in entry
            assert isinstance(entry["duration_seconds"], float)


    @requires_make
    def test_the_failure_result_carries_per_step_records(self, tmp_path):
        """step_details on the FAILURE path too (issue #1152).

        It was set only on the success result, so a run that failed inside an
        aggregate published no per-step records at all - and the `not-run` rows
        naming what never ran are exactly what a reader needs THERE. A reader
        told only "verify failed" has 29 prerequisites to search.
        """
        import io

        from lib.cicd.runner import DeterministicRunner

        root = self._tree(
            tmp_path,
            "lint:\n\t@echo BROKEN; exit 1\n"
            "test:\n\t@true\ntypecheck:\n\t@true\nsecurity_scan:\n\t@true\n"
            "verify: lint test typecheck\n\t@true\n",
        )
        result = DeterministicRunner(
            project_root=root, output=io.StringIO()
        ).run("finish")

        assert result.success is False
        assert result.step_details, (
            "a failed run published no per-step records, so the not-run rows "
            "that name what never ran are invisible to every reader (#1152)"
        )
        assert {e["id"] for e in result.step_details} >= {"lint", "verify"}


    def test_a_gate_past_a_continuation_line_is_still_derived(self, tmp_path):
        """The parser pin that actually pins the CONSUMER (counter-model review).

        The repository-wide count above catches a truncating parser only
        because this repository happens to have 29 prerequisites; it does not
        prove `subsumed_gate_ids` uses the good one, since lint, test and
        typecheck all sit on the first physical line and a first-line-only
        parser would return them anyway.

        Here `typecheck` sits AFTER a backslash continuation. A parser that
        stops at the first physical line - which is exactly what
        lib/cicd/makefile.py::parse_makefile does (#1162) - derives {lint, test}
        and silently leaves typecheck running on its own. That is not a
        correctness failure, but it is the tell that the wrong reader is wired
        in, and this is the assertion that catches it.
        """
        from lib.cicd.steps import get_plan_steps, subsumed_gate_ids

        root = self._tree(
            tmp_path,
            "lint:\n\t@true\ntest:\n\t@true\ntypecheck:\n\t@true\n"
            "security_scan:\n\t@true\n"
            "verify: lint test \\\n\ttypecheck\n\t@true\n",
        )
        steps = get_plan_steps("finish", project_root=str(root))
        subsumed, _refusals = subsumed_gate_ids("finish", steps, str(root))
        assert set(subsumed) == {"lint", "test", "typecheck"}, (
            f"derived {sorted(subsumed)} from a rule whose third gate is past a "
            f"line continuation - a reader that stops at the first physical "
            f"line returns {{lint, test}} (#1162)"
        )

    @requires_make
    def test_an_aggregate_that_subsumes_test_still_qualifies_an_empty_suite(
        self, tmp_path
    ):
        """#621 must survive subsumption (counter-model review, post-merge).

        `is_test_step()` reads the id and the command, and `make verify` names
        neither pytest nor test - so deferring `test` to it removed the
        empty-suite qualification outright. MEASURED on the merged code: a
        target printing "0 passed, 66 skipped" inside a green `make verify`
        produced `tests: {}` and `warnings: []`, and the gate reported ok.

        That is #621's own false green, reintroduced by a COST fix - the one
        thing #1152 was not allowed to do. An aggregate now inherits the need
        to parse a test summary from whatever it subsumes.
        """
        import io

        from lib.cicd.runner import DeterministicRunner

        root = self._tree(
            tmp_path,
            "lint:\n\t@true\n"
            'test:\n\t@echo "== 0 passed, 66 skipped in 0.1s =="\n'
            "typecheck:\n\t@true\nsecurity_scan:\n\t@true\n"
            "verify: lint test typecheck\n\t@true\n",
        )
        result = DeterministicRunner(
            project_root=root, output=io.StringIO()
        ).run("finish")

        assert result.success is True
        assert result.tests, "the aggregate's test summary was not parsed at all"
        assert any("executed NO tests" in w for w in result.warnings), (
            f"a suite that ran nothing inside a green aggregate produced "
            f"warnings {result.warnings} - #621's qualification is gone"
        )

    def test_failure_attribution_prefers_the_terminal_outer_diagnostic(self):
        """A nested make failure must not be named as the cause.

        `search` took the first match anywhere in the combined streams, so a
        recipe tolerating a nested failure - or a fixture exercising one -
        printed `make[1]: *** [...] Error 1` first and the helper named that
        target. Naming a neighbour is the "a wrong name is worse than none"
        this function's own docstring warns about.
        """
        from lib.cicd.runner import _failing_prerequisite

        noisy = (
            "make[1]: *** [fixtures/Makefile:7: expected-failure] Error 1\n"
            "other output\n"
            "make: *** [Makefile:121: lint] Error 1\n"
        )
        assert _failing_prerequisite(noisy) == "lint"
        # A nested diagnostic is still used when the outer make printed none -
        # some of the information beats none of it.
        assert (
            _failing_prerequisite("make[1]: *** [M:9: typecheck] Error 2")
            == "typecheck"
        )
        assert _failing_prerequisite("nothing matchable here") is None

    @requires_make
    def test_an_inactive_conditional_prerequisite_is_not_subsumed(self, tmp_path):
        """THE #1165 FALSE GREEN. `verify: lint` inside `ifeq (1,0)`.

        A textual reader cannot evaluate the conditional, so it reports lint as
        a prerequisite of verify. Subsumption then marks lint covered, `make
        verify` runs without it, and a BROKEN LINT passes as a `subsumed` gate.
        Measured on the pre-fix derivation, this exact tree:

            SUBSUMED: lint, test, typecheck ran as prerequisite(s) of `verify`
            FLOW_FINISH_GATE: ok

        over a lint that exits 1 and that nothing ran. Asking make instead -
        `make -p -n` reports `verify: test typecheck` - leaves lint unsubsumed,
        so it runs on its own and reds the gate.
        """
        import io

        from lib.cicd.runner import DeterministicRunner
        from lib.cicd.steps import make_prerequisites

        root = self._tree(
            tmp_path,
            "lint:\n\t@echo BROKEN; exit 1\n"
            "test:\n\t@true\ntypecheck:\n\t@true\nsecurity_scan:\n\t@true\n"
            "ifeq (1,0)\nverify: lint\nendif\n"
            "verify: test typecheck\n\t@true\n",
        )
        from lib.cicd.steps import makefile_grammar_refusal

        # SINCE OPTION B the query never runs here: `ifeq` is outside the
        # positive grammar, so the makefile is refused BEFORE `make -p -n`
        # and nothing is subsumed. The gate reds for a stronger reason than
        # it used to - not "make said test and typecheck" but "this makefile
        # is not one I can be sure about".
        refusal = makefile_grammar_refusal(str(root))
        assert refusal is not None and "a conditional" in refusal, refusal
        assert make_prerequisites(str(root), "verify") is None

        result = DeterministicRunner(
            project_root=root, output=io.StringIO()
        ).run("finish")
        assert result.success is False
        assert result.failed_step == "lint"
        assert "lint" not in result.to_dict()["subsumed_gates"]

    @requires_make
    def test_a_step_that_does_not_run_the_prerequisite_is_not_subsumed(self, tmp_path):
        """The second #1165 finding: a matching ID is not a matching command.

        `verify: lint` says make runs the TARGET `lint`. It says nothing about
        what this plan's step called `lint` runs - and a manifest may configure
        it to run something else entirely. Suppressing that step on the strength
        of an unrelated Makefile rule reports a check as passed that never ran.

        The refusal is reported BY NAME WITH THE COMMAND, so the duplicate run
        explains itself and the allowlist grows from evidence.
        """
        from lib.cicd.steps import get_plan_steps, subsumed_gate_ids

        root = self._tree(
            tmp_path,
            "lint:\n\t@true\ntest:\n\t@true\ntypecheck:\n\t@true\n"
            "security_scan:\n\t@true\nverify: lint test typecheck\n\t@true\n",
        )
        (root / ".claude").mkdir()
        (root / ".claude" / "cicd_tasks.yml").write_text(
            'version: "1"\n'
            "steps:\n"
            "  lint:\n    command: ruff check --select=E501 .\n"
            "  test:\n    command: make test\n"
            "  typecheck:\n    command: make typecheck\n"
            "  verify:\n    command: make verify\n"
            "plans:\n  finish:\n    steps: [lint, test, typecheck, verify]\n"
        )
        steps = get_plan_steps("finish", project_root=str(root))
        subsumed, refusals = subsumed_gate_ids("finish", steps, str(root))

        assert "lint" not in subsumed
        assert {"test", "typecheck"} <= set(subsumed)
        assert any("ruff check" in r and "lint" in r for r in refusals), refusals

    @requires_make
    def test_an_include_puts_a_makefile_outside_the_grammar_and_SAYS_SO(self, tmp_path):
        """The bound is far wider than the hazards it is written for (#1192).

        `-include` of an optional env file is ordinary project configuration,
        not recursive make and not a flag-sensitive conditional - and it is
        refused all the same, so such a repository pays every gate twice and
        #1152's dedup never reaches it.

        Paired with the conforming case below, which is what makes this a
        verdict rather than the output of a function that always refuses.
        """
        from lib.cicd.steps import get_plan_steps, subsumed_gate_ids

        root = self._tree(
            tmp_path,
            "-include $(COMPOSE_ENV_FILE)\n\n"
            "lint:\n\t@true\ntest:\n\t@true\ntypecheck:\n\t@true\n"
            "verify: lint test typecheck\n\t@true\n",
        )
        (root / ".claude").mkdir()
        (root / ".claude" / "cicd_tasks.yml").write_text(
            'version: "1"\n'
            "steps:\n"
            "  lint:\n    command: make lint\n"
            "  test:\n    command: make test\n"
            "  typecheck:\n    command: make typecheck\n"
            "  verify:\n    command: make verify\n"
            "plans:\n  finish:\n    steps: [lint, test, typecheck, verify]\n"
        )
        steps = get_plan_steps("finish", project_root=str(root))
        subsumed, refusals = subsumed_gate_ids("finish", steps, str(root))

        assert subsumed == {}, "an include must suppress subsumption entirely"
        assert any("an include" in r for r in refusals), refusals
        assert any("outside the grammar" in r for r in refusals), refusals

    @requires_make
    def test_a_conforming_makefile_is_NOT_refused(self, tmp_path):
        """THE NEGATIVE CONTROL for the case above.

        Without it, a grammar check that refused everything would satisfy the
        include test perfectly while making subsumption dead for every tree.
        """
        from lib.cicd.steps import get_plan_steps, subsumed_gate_ids

        root = self._tree(
            tmp_path,
            "lint:\n\t@true\ntest:\n\t@true\ntypecheck:\n\t@true\n"
            "verify: lint test typecheck\n\t@true\n",
        )
        (root / ".claude").mkdir()
        (root / ".claude" / "cicd_tasks.yml").write_text(
            'version: "1"\n'
            "steps:\n"
            "  lint:\n    command: make lint\n"
            "  test:\n    command: make test\n"
            "  typecheck:\n    command: make typecheck\n"
            "  verify:\n    command: make verify\n"
            "plans:\n  finish:\n    steps: [lint, test, typecheck, verify]\n"
        )
        steps = get_plan_steps("finish", project_root=str(root))
        subsumed, refusals = subsumed_gate_ids("finish", steps, str(root))

        assert {"lint", "test", "typecheck"} <= set(subsumed)
        assert not any("outside the grammar" in r for r in refusals), refusals

    def test_the_refusal_REACHES_to_dict(self):
        """A field that never reaches the JSON cannot be acted on (#812, #1192).

        The refusals were computed and logged and never serialised, so the
        shell gate could not see them however carefully they were phrased.
        """
        from lib.cicd.runner import RunResult

        result = RunResult(
            success=True,
            run_id="r1",
            plan_name="finish",
            steps_completed=1,
            steps_total=1,
            subsumption_refusals=["the makefile is outside the grammar (line 1: an include)"],
        )
        payload = result.to_dict()

        assert "subsumption_refusals" in payload
        assert any("an include" in r for r in payload["subsumption_refusals"])

    def test_NOT_DERIVED_and_NOTHING_REFUSED_are_not_the_same_bytes(self):
        """Three states, like `dropped_gates` and for the same reason (#1192).

        `resume` on an already-finished run reports a stored status and never
        derives subsumption at all. Defaulting that to `[]` would have the field
        claim a look nobody took - which is the exact conflation this field
        exists to remove, committed inside the fix for it.
        """
        from lib.cicd.runner import RunResult

        def payload(**kw):
            return RunResult(
                success=True, run_id="r", plan_name="finish",
                steps_completed=1, steps_total=1, **kw
            ).to_dict()

        not_derived = payload()
        derived_clean = payload(subsumption_refusals=[])

        assert not_derived["subsumption_refusals"] is None
        assert derived_clean["subsumption_refusals"] == []
        assert not_derived["subsumption_refusals"] != derived_clean["subsumption_refusals"]

    @requires_make
    def test_the_query_does_not_inherit_the_OUTER_make(self, monkeypatch):
        """A derivation run from inside a make recipe asks the same question.

        A parent make exports its own variables to everything it runs, and
        `make verify` running this very suite is exactly that case. Measured
        with `MAKEFLAGS=w` and `MAKELEVEL=1` in the environment: the query's
        make announced `Entering directory`, the recursion guard fired, and
        subsumption turned OFF for a makefile squarely inside the grammar - the
        whole saving gone in the nested case, silently, while every gate still
        ran. Failing safe is not the same as being right.

        Caught only by the FULL suite: every targeted run of these tests was
        serial and outside make, where the variables are absent. The green from
        a narrower run said nothing about the environment the gate meets.
        """
        from lib.cicd.steps import (
            get_plan_steps,
            reset_make_prerequisite_cache,
            subsumed_gate_ids,
        )

        root = Path(__file__).resolve().parent.parent
        monkeypatch.setenv("MAKEFLAGS", "w")
        monkeypatch.setenv("MAKELEVEL", "1")
        monkeypatch.setenv("MFLAGS", "-w")
        reset_make_prerequisite_cache()
        covered, _ = subsumed_gate_ids(
            "finish", get_plan_steps("finish", project_root=str(root)), str(root)
        )
        assert set(covered) == {"lint", "test", "typecheck"}, (
            "an outer make's exported flags must not change what the query is "
            f"asked; got {covered}"
        )

    def test_THIS_repository_is_inside_the_grammar(self):
        """The measurement that decides whether option B is option D (#1165).

        Subsumption exists to save ~157s on THIS repository's gate run. If
        CPP's own Makefile falls outside the grammar, the feature refuses here
        too and the whole thing is dead weight - so the fact is pinned rather
        than assumed. Measured at b3bf666 and on this branch: inside, with the
        one interesting line being `.DEFAULT_GOAL := lint`, an assignment whose
        name begins with a dot.

        IF THIS TEST FAILS, the Makefile gained a construct outside the set -
        an include, a conditional, a `$(shell)` assignment. That is not
        automatically wrong, but it turns subsumption OFF for this repository,
        and the choice should be made deliberately rather than discovered as a
        slower gate. Do not widen the grammar to make this pass.
        """
        from lib.cicd.steps import makefile_grammar_refusal

        root = Path(__file__).resolve().parent.parent
        refusal = makefile_grammar_refusal(str(root))
        assert refusal is None, (
            f"CPP's own Makefile is now OUTSIDE the subsumption grammar: {refusal}. "
            f"Subsumption is therefore disabled for this repository and `make verify`'s "
            f"gates will run twice. See docs/scripts.md (#1165, option B)."
        )

    def test_the_grammar_is_a_closed_positive_set(self, tmp_path):
        """What is ALLOWED is listed; everything else refuses, by construction.

        Two counter-model passes produced fifteen findings against a derivation
        that named FORBIDDEN constructs, because such a list can only contain
        what somebody already thought of. These cases are therefore not the
        specification - the four allowed shapes are - but they pin that the
        shapes which actually bit us fall outside it, and that the ordinary
        makefile does not.
        """
        from lib.cicd.steps import makefile_grammar_refusal

        def refusal_for(text):
            (tmp_path / "Makefile").write_text(text)
            return makefile_grammar_refusal(str(tmp_path))

        inside = [
            ("a plain rule and recipe", "lint:\n\t@true\nverify: lint\n\t@true\n"),
            (".PHONY", ".PHONY: lint verify\nlint:\n\t@true\n"),
            ("a plain assignment", "PY = python3\nlint:\n\t@true\n"),
            ("a dotted special", ".DEFAULT_GOAL := lint\nlint:\n\t@true\n"),
            ("a comment", "# a comment\nlint:\n\t@true\n"),
            (
                "a continued prerequisite list",
                "lint:\n\t@true\ntest:\n\t@true\nverify: lint \\\n\ttest\n\t@true\n",
            ),
        ]
        for label, text in inside:
            assert refusal_for(text) is None, f"{label} must be INSIDE the grammar"

        outside = [
            ("an include", "include other.mk\nlint:\n\t@true\n", "an include"),
            ("a conditional", "ifeq (1,0)\nverify: lint\nendif\n", "a conditional"),
            ("a define", "define X\nY\nendef\n", "a define block"),
            ("a pattern rule", "%.o: %.c\n\t@true\n", "a pattern rule"),
            ("a double-colon rule", "verify:: test\n", "a double-colon rule"),
            ("an export", "export FOO = 1\n", "an export directive"),
            (
                "a $(shell) assignment",
                "STAMP := $(shell date)\nlint:\n\t@true\n",
                "$(shell",
            ),
            (
                "an $(eval) assignment",
                "X := $(eval Y)\nlint:\n\t@true\n",
                "$(eval",
            ),
            (
                "a recursive make in a value",
                "SUB = $(MAKE) -C sub\nlint:\n\t@true\n",
                "$(MAKE)",
            ),
            (
                "MAKEFLAGS in a value",
                "F := $(MAKEFLAGS)\nlint:\n\t@true\n",
                "MAKEFLAGS",
            ),
            (
                "a target-specific variable",
                "verify: CHECKS = lint\nverify: test\n",
                "does not recognise",
            ),
            (
                "an escaped hash in a rule",
                "verify: lint\\#aux test\n",
                "backslash escape",
            ),
            (
                "an escaped space in a rule",
                "verify: lint\\ aux test\n",
                "backslash escape",
            ),
        ]
        for label, text, expected in outside:
            refusal = refusal_for(text)
            assert refusal is not None, f"{label} must be OUTSIDE the grammar"
            assert expected in refusal, f"{label}: {refusal!r} must name {expected!r}"
            assert refusal.startswith("line "), f"{label}: {refusal!r} must name the line"

    def test_a_recognised_command_is_EQUAL_to_its_producer(self, tmp_path):
        """Recognition is equality with `gate_conditional_command`, not a regex.

        The regex it replaced carried two findings: `\\s` spans newlines, so
        `make\\nlint` satisfied the direct form, and the conditional form
        matched a PREFIX, so trailing shell after `fi` rode along and executed.
        Equality against the one producer closes both by construction - there
        is no pattern left to be clever about.
        """
        from lib.cicd.steps import command_runs_make_target, gate_conditional_command

        (tmp_path / "Makefile").write_text("lint:\n\t@true\n")
        root = str(tmp_path)

        generated = gate_conditional_command("lint", "uv run --extra dev ruff check .")
        assert command_runs_make_target(generated, "lint", root)
        assert command_runs_make_target("make lint", "lint")
        assert command_runs_make_target("make  lint", "lint"), "horizontal space folds"

        for rejected in (
            "make typecheck",
            "ruff check .",
            "make lint && rm -rf /",
            "make lint; exit 1",
            "make\nlint",
            generated + "; exit 1",
            generated.replace("; fi", "; fi\nexit 1"),
            'if grep -q "^lint:" Makefile; then make lint; else true\nfi\nexit 1\n#; fi',
        ):
            assert not command_runs_make_target(rejected, "lint", root), rejected

        # The fallback slot is the only freedom, and it cannot chain.
        assert not command_runs_make_target(
            gate_conditional_command("lint", "true; exit 1"), "lint", root
        )

    @requires_make
    def test_a_makeflags_sensitive_makefile_is_refused(self, tmp_path):
        """The query IS make flags, so a tree reading them cannot be asked.

        Naming the goal fixed `MAKECMDGOALS`; nothing fixes `MAKEFLAGS` while
        the query needs `-p -n`. Measured (counter-model round 2): with
        `verify: lint` under `ifneq (,$(findstring n,$(MAKEFLAGS)))` the query
        returned `['test', 'lint']` and `make verify` ran only test - the
        conditional false green, keyed on the query itself.
        """
        from lib.cicd.steps import make_prerequisites, reset_make_prerequisite_cache

        (tmp_path / "Makefile").write_text(
            "lint:\n\t@exit 1\ntest:\n\t@true\n"
            "ifneq (,$(findstring n,$(MAKEFLAGS)))\nverify: lint\nendif\n"
            "verify: test\n\t@true\n"
        )
        reset_make_prerequisite_cache()
        assert make_prerequisites(str(tmp_path), "verify") is None

    @requires_make
    def test_a_recursive_make_child_database_is_refused(self, tmp_path):
        """`-n` does not suppress a recipe line containing `$(MAKE)`.

        So the query RUNS the children, and a child's `-p` dump precedes the
        parent's. Measured: a parent whose rule is `verify: test` returned
        `['lint']` - read out of a subdirectory's makefile. Crediting a
        neighbour's target as coverage is the defect this issue is about,
        arriving through make rather than through text.
        """
        from lib.cicd.steps import make_prerequisites, reset_make_prerequisite_cache

        child = tmp_path / "sub"
        child.mkdir()
        (child / "Makefile").write_text("lint:\n\t@true\nverify: lint\n\t@true\n")
        (tmp_path / "Makefile").write_text(
            "lint:\n\t@exit 1\ntest:\n\t@$(MAKE) -C sub verify\nverify: test\n\t@true\n"
        )
        reset_make_prerequisite_cache()
        assert make_prerequisites(str(tmp_path), "verify") is None

    @requires_make
    def test_an_odd_named_target_variable_is_skipped_not_read_as_prerequisites(
        self, tmp_path
    ):
        """The assignment guard keys on `=`, not on the variable's NAME.

        Keying on the name meant any name outside the character class walked
        past it: measured, `verify: CHECK/LIST = lint` returned
        `['CHECK/LIST', '=', 'lint']`. An assignment is SKIPPED rather than
        refused - make itself keeps looking for the rule, and so does this.
        """
        from lib.cicd.steps import make_prerequisites, reset_make_prerequisite_cache

        (tmp_path / "Makefile").write_text(
            "lint:\n\t@exit 1\ntest:\n\t@true\n"
            "verify: CHECK/LIST = lint\nverify: test\n\t@true\n"
        )
        reset_make_prerequisite_cache()
        from lib.cicd.steps import makefile_grammar_refusal

        # REFUSED BY THE GRAMMAR now, one step earlier: a target-specific
        # variable is not a rule, a recipe, an assignment or `.PHONY`, so
        # it is not a line the grammar recognises and the file is never
        # queried. The parser behaviour below is kept as the regression.
        refusal = makefile_grammar_refusal(str(tmp_path))
        assert refusal is not None and "does not recognise" in refusal, refusal
        assert make_prerequisites(str(tmp_path), "verify") is None

    @requires_make
    def test_an_escaped_hash_in_a_prerequisite_refuses_the_rule(self, tmp_path):
        """`verify: lint\\#aux` is ONE file, and cutting at `#` invents `lint`.

        Measured: the reader returned `['lint']` - a target that does not
        exist, which would suppress a real step called `lint`.
        """
        from lib.cicd.steps import make_prerequisites, reset_make_prerequisite_cache

        (tmp_path / "Makefile").write_text(
            "lint\\#aux:\n\t@true\ntest:\n\t@true\nverify: lint\\#aux test\n\t@true\n"
        )
        reset_make_prerequisite_cache()
        assert make_prerequisites(str(tmp_path), "verify") is None

    @requires_make
    def test_an_escaped_space_credits_only_names_make_declares_as_rules(
        self, tmp_path
    ):
        """The one ambiguity no parser can resolve, closed from the other side.

        `make -p` prints `verify: lint\\ aux test` as `verify: lint aux test`
        with the escape GONE, so one file named `lint aux` and two files named
        `lint` and `aux` are byte-identical there. The RULES are not ambiguous:
        the dump carries `lint aux:` and no `lint:`. So a prerequisite is
        credited only when the database declares it as a rule in its own right
        (counter-model round 2).
        """
        from lib.cicd.steps import (
            StepDef,
            make_prerequisites,
            reset_make_prerequisite_cache,
            subsumed_gate_ids,
        )

        (tmp_path / "Makefile").write_text(
            "lint\\ aux:\n\t@true\ntest:\n\t@true\nverify: lint\\ aux test\n\t@true\n"
        )
        reset_make_prerequisite_cache()
        # REFUSED BY THE GRAMMAR before the query: the escape survives the
        # continuation join and a rule line carrying one is outside the set.
        # The declares-a-rule check below remains the second layer, for a
        # file that is inside the grammar and still ambiguous in the dump.
        from lib.cicd.steps import makefile_grammar_refusal

        refusal = makefile_grammar_refusal(str(tmp_path))
        assert refusal is not None and "backslash escape" in refusal, refusal
        assert make_prerequisites(str(tmp_path), "verify") is None
        plan = [
            StepDef(id="lint", command="make lint", gate=True),
            StepDef(id="test", command="make test", gate=True),
            StepDef(id="verify", command="make verify", gate=True),
        ]
        reset_make_prerequisite_cache()
        covered, refusals = subsumed_gate_ids("finish", plan, str(tmp_path))
        assert covered == {}, "the grammar refused this file; nothing is subsumed"
        assert any("backslash escape" in r for r in refusals), refusals

    @requires_make
    def test_a_step_environment_that_differs_from_the_aggregate_is_not_subsumed(
        self, tmp_path
    ):
        """The same command in a different environment is a different check.

        Measured (counter-model round 2): a `verify` step carrying
        `env={"SKIP_LINT": "1"}`, over a makefile that drops lint under that
        variable, reported lint as covered with NO refusal - while standalone
        lint failed. The query is now asked in the aggregate's environment, and
        a prerequisite step declaring a different one is refused by name.
        """
        from lib.cicd.steps import StepDef, reset_make_prerequisite_cache, subsumed_gate_ids

        (tmp_path / "Makefile").write_text(
            "lint:\n\t@exit 1\ntest:\n\t@true\n"
            "ifndef SKIP_LINT\nverify: lint\nendif\nverify: test\n\t@true\n"
        )
        plan = [
            StepDef(id="lint", command="make lint", gate=True),
            StepDef(id="test", command="make test", gate=True),
            StepDef(id="verify", command="make verify", gate=True, env={"SKIP_LINT": "1"}),
        ]
        reset_make_prerequisite_cache()
        covered, refusals = subsumed_gate_ids("finish", plan, str(tmp_path))
        # TWO refusals are available here and the grammar's comes first:
        # `ifndef` is outside the set, so the file is never queried. The
        # environment check stays as the guard for a file INSIDE the grammar
        # whose steps disagree, which is pinned in the sibling test below.
        assert "lint" not in covered, "the aggregate's env drops lint; it must run"
        assert refusals, "a refusal must be NAMED, not left to silence"

    @requires_make
    def test_a_multiline_command_is_never_a_recognised_make_invocation(self, tmp_path):
        """Every negated class in the patterns matches a newline.

        So `if grep -q "^lint:" Makefile; then make lint; else true\\nfi\\nexit 1\\n#; fi`
        satisfied the conditional form while executing `exit 1` afterwards -
        measured recognised=True, exit=1. Both recognised shapes are single
        line, so a newline anywhere refuses (counter-model round 2).
        """
        from lib.cicd.steps import command_runs_make_target

        (tmp_path / "Makefile").write_text("lint:\n\t@true\n")
        trailing = (
            'if grep -q "^lint:" Makefile; then make lint; else true\nfi\nexit 1\n#; fi'
        )
        assert not command_runs_make_target(trailing, "lint", str(tmp_path))

    @requires_make
    def test_make_is_asked_about_THIS_target_not_the_default_goal(self, tmp_path):
        """`MAKECMDGOALS` is part of the question (counter-model review).

        A rule guarded by `ifneq ($(MAKECMDGOALS),verify)` resolves one way
        when make is asked about `verify` and the OTHER way when it is asked
        about nothing. Measured on the pre-fix code, which ran `make -p -n`
        with no target: the query returned `['test', 'lint']` for a tree where
        `make verify` runs only `test`, so `lint` would have been suppressed in
        favour of an aggregate that never runs it.

        This is the SAME defect the issue is about - a derivation that answers
        a neighbouring question - and it survived into the fix.
        """
        from lib.cicd.steps import make_prerequisites, reset_make_prerequisite_cache

        (tmp_path / "Makefile").write_text(
            "lint:\n\t@true\ntest:\n\t@true\n"
            "ifneq ($(MAKECMDGOALS),verify)\nverify: lint\nendif\n"
            "verify: test\n\t@true\n"
        )
        reset_make_prerequisite_cache()
        from lib.cicd.steps import makefile_grammar_refusal

        # The goal fix still matters for any file INSIDE the grammar; this
        # particular file is now refused one step earlier, as a conditional.
        refusal = makefile_grammar_refusal(str(tmp_path))
        assert refusal is not None and "a conditional" in refusal, refusal
        assert make_prerequisites(str(tmp_path), "verify") is None

    @requires_make
    def test_a_target_specific_variable_is_not_a_prerequisite_list(self, tmp_path):
        """`verify: CHECKS = lint` assigns; it does not depend (counter-model).

        Measured on the pre-fix code, whose `[:1]` assignment guard looked at
        the wrong character: the query returned `['CHECKS', '=', 'lint']`, so
        a step whose id happened to be `lint` was credited to an aggregate that
        merely mentions it in a variable.
        """
        from lib.cicd.steps import make_prerequisites, reset_make_prerequisite_cache

        (tmp_path / "Makefile").write_text(
            "lint:\n\t@true\ntest:\n\t@true\n"
            "verify: CHECKS = lint\nverify: test\n\t@true\n"
        )
        reset_make_prerequisite_cache()
        from lib.cicd.steps import makefile_grammar_refusal

        # REFUSED BY THE GRAMMAR now, one step earlier: a target-specific
        # variable is not a rule, a recipe, an assignment or `.PHONY`, so
        # it is not a line the grammar recognises and the file is never
        # queried. The parser behaviour below is kept as the regression.
        refusal = makefile_grammar_refusal(str(tmp_path))
        assert refusal is not None and "does not recognise" in refusal, refusal
        assert make_prerequisites(str(tmp_path), "verify") is None

    @requires_make
    def test_a_FAILED_make_query_is_not_an_answer(self, tmp_path):
        """A non-zero make still prints a database; it is not evidence.

        GNU make emits a PARTIAL database even when it aborts. Measured on the
        pre-fix code, which checked only that stdout was non-empty: a makefile
        whose `$(error)` stops the parse still yielded `['lint']` - a
        subsumption derived from a make that had refused to run. "Cannot ask
        means subsume nothing" has to cover "asked, and was refused".
        """
        from lib.cicd.steps import make_prerequisites, reset_make_prerequisite_cache

        (tmp_path / "Makefile").write_text(
            "verify: lint\nlint:\n\t@true\n$(error deliberately unparseable)\n"
        )
        reset_make_prerequisite_cache()
        assert make_prerequisites(str(tmp_path), "verify") is None

    @requires_make
    def test_the_prerequisite_cache_does_not_outlive_a_run(self, tmp_path):
        """The memo spans a PROCESS; the makefile it answers about does not.

        One `make -p -n` per aggregate is the reason the memo exists. Spanning
        runs is not: a resumed run would suppress gates according to a makefile
        read earlier and since changed. Reset is the runner's first act.
        """
        from lib.cicd.steps import make_prerequisites, reset_make_prerequisite_cache

        makefile = tmp_path / "Makefile"
        makefile.write_text("lint:\n\t@true\ntest:\n\t@true\nverify: lint test\n\t@true\n")
        reset_make_prerequisite_cache()
        assert make_prerequisites(str(tmp_path), "verify") == ["lint", "test"]

        makefile.write_text("test:\n\t@true\nverify: test\n\t@true\n")
        assert make_prerequisites(str(tmp_path), "verify") == [
            "lint",
            "test",
        ], "within one run the memo is the point"
        reset_make_prerequisite_cache()
        assert make_prerequisites(str(tmp_path), "verify") == ["test"]

    @requires_make
    def test_the_generated_conditional_command_IS_recognised(self, tmp_path):
        """The guard rail for the allowlist.

        `generate_manifest` emits
        `if grep -q "^lint:" Makefile; then make lint; else <alt>; fi`, which
        runs `make lint` exactly when a `lint:` target exists - and subsumption
        only arises when make NAMED lint a prerequisite, which requires that
        target. Refusing this shape would turn the deduplication off for every
        generated project, which is "refuse everything", not a bound.
        """
        from lib.cicd.steps import command_runs_make_target

        generated = (
            'if grep -q "^lint:" Makefile 2>/dev/null; then make lint; '
            "else uv run --extra dev ruff check .; fi"
        )
        (tmp_path / "Makefile").write_text("lint:\n\t@true\n")
        assert command_runs_make_target(generated, "lint", str(tmp_path))
        # The direct form needs no root - there is no branch to decide.
        assert command_runs_make_target("make lint", "lint")
        # and it does not accept a neighbour's target, nor an unrecognised shape
        assert not command_runs_make_target("make typecheck", "lint")
        assert not command_runs_make_target("ruff check .", "lint")
        assert not command_runs_make_target("make lint && rm -rf /", "lint")
        # HORIZONTAL whitespace only: `make\nlint` is TWO commands, and the
        # pre-fix `\s+` accepted it as one (counter-model review).
        assert not command_runs_make_target("make\nlint", "lint")
        assert not command_runs_make_target("make lint; exit 1", "lint")

    @requires_make
    def test_the_generated_conditional_is_refused_when_its_grep_would_miss(
        self, tmp_path
    ):
        """The guard is a `grep`, so it is RUN, not assumed (counter-model).

        Recognising the shape establishes only what the command CAN do. This
        tree declares its targets through a variable, so there is no literal
        `lint:` line, the grep fails, and the ELSE branch runs - a fallback
        `make verify` never runs. Crediting subsumption from the shape alone
        would drop the lint check entirely, which is this issue's own defect
        (a derivation that answers a neighbouring question) one layer out.
        """
        from lib.cicd.steps import command_runs_make_target

        generated = (
            'if grep -q "^lint:" Makefile 2>/dev/null; then make lint; '
            "else uv run --extra dev ruff check .; fi"
        )
        (tmp_path / "Makefile").write_text("CHECKS = lint\n$(CHECKS):\n\t@true\n")
        assert not command_runs_make_target(generated, "lint", str(tmp_path))
        # And with no root there is no grep to run, so it cannot be proven.
        assert not command_runs_make_target(generated, "lint")

    @requires_make
    def test_an_aggregate_whose_command_is_not_make_verify_subsumes_nothing(
        self, tmp_path
    ):
        """Every suppression rests on the aggregate RUNNING (counter-model).

        A step is credited with running lint and test because it runs
        `make verify`, and that was never checked - the id was taken as the
        fact. Measured on the pre-fix code: a `verify` step whose command is
        `true` suppressed both gates, so the plan ran no checks at all and
        reported them subsumed. The ids are labels; only the command runs.
        """
        from lib.cicd.steps import (
            StepDef,
            reset_make_prerequisite_cache,
            subsumed_gate_ids,
        )

        (tmp_path / "Makefile").write_text(
            "lint:\n\t@true\ntest:\n\t@true\nverify: lint test\n\t@true\n"
        )

        def plan(verify_command):
            return [
                StepDef(id="lint", command="make lint", gate=True),
                StepDef(id="test", command="make test", gate=True),
                StepDef(id="verify", command=verify_command, gate=True),
            ]

        reset_make_prerequisite_cache()
        covered, _ = subsumed_gate_ids("finish", plan("make verify"), str(tmp_path))
        assert sorted(covered) == ["lint", "test"], "the honest plan still dedupes"

        for impostor in ("true", "make verify-fast", "echo make verify"):
            reset_make_prerequisite_cache()
            covered, refusals = subsumed_gate_ids(
                "finish", plan(impostor), str(tmp_path)
            )
            assert covered == {}, f"{impostor!r} must credit nothing"
            assert any(
                "declared as the aggregate" in r for r in refusals
            ), f"{impostor!r} must SAY why, not refuse silently"

    @requires_make
    def test_make_unavailable_subsumes_nothing(self, tmp_path):
        """When make cannot answer, every gate runs.

        A tree with no Makefile has no rule to read, so the derivation returns
        nothing subsumed rather than falling back to a textual guess. The
        failure mode is duplicated work, never a skipped check - which is what
        stops this fix introducing a false green through its own unavailability,
        the trap #1163 walked into.
        """
        from lib.cicd.steps import get_plan_steps, make_prerequisites, subsumed_gate_ids

        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        assert make_prerequisites(str(tmp_path), "verify") is None
        steps = get_plan_steps("finish", project_root=str(tmp_path))
        subsumed, refusals = subsumed_gate_ids("finish", steps, str(tmp_path))
        assert subsumed == {}
        assert any("make could not be asked" in r for r in refusals), refusals


# --- issue #1258: typecheck honours the repository's declared mypy scope ------


class TestScopedMypy:
    """`mypy .` checked tests/ in a repo whose contract is `mypy <pkg>`, and the
    finish gate failed on errors that contract does not cover (skillc#18).
    A declared `files =` is honoured by passing mypy NO path."""

    @staticmethod
    def _args_seen(tmp_path: Path, files: dict[str, str]) -> str:
        import shutil
        import subprocess

        from lib.cicd.models import scoped_mypy

        if shutil.which("bash") is None or shutil.which("awk") is None:
            pytest.skip("requires bash and awk")
        for name, text in files.items():
            (tmp_path / name).write_text(text)
        bindir = tmp_path / "bin"
        bindir.mkdir()
        fake = bindir / "mypy"
        fake.write_text('#!/usr/bin/env bash\nprintf "[%s]" "$*" > mypy.args\n')
        fake.chmod(0o755)
        subprocess.run(
            ["bash", "-c", scoped_mypy("")],
            cwd=tmp_path,
            env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"},
            check=True,
        )
        return (tmp_path / "mypy.args").read_text()

    def test_pyproject_declared_files_runs_bare_mypy(self, tmp_path: Path) -> None:
        assert self._args_seen(
            tmp_path, {"pyproject.toml": '[tool.mypy]\nfiles = ["skillc"]\nstrict = true\n'}
        ) == "[]"

    def test_mypy_ini_declared_files_runs_bare_mypy(self, tmp_path: Path) -> None:
        assert self._args_seen(tmp_path, {"mypy.ini": "[mypy]\nfiles = pkg\n"}) == "[]"

    def test_no_declaration_keeps_the_dot_default(self, tmp_path: Path) -> None:
        assert self._args_seen(tmp_path, {"pyproject.toml": "[tool.mypy]\nstrict = true\n"}) == "[.]"

    def test_no_config_at_all_keeps_the_dot_default(self, tmp_path: Path) -> None:
        assert self._args_seen(tmp_path, {}) == "[.]"

    def test_files_in_another_table_is_not_a_mypy_scope(self, tmp_path: Path) -> None:
        text = (
            '[tool.setuptools]\nfiles = ["x"]\n'
            '[tool.mypy]\nstrict = true\n'
            '[[tool.mypy.overrides]]\nmodule = "a"\nfiles = ["y"]\n'
        )
        assert self._args_seen(tmp_path, {"pyproject.toml": text}) == "[.]"

    def test_the_finish_plan_typecheck_step_uses_the_scoped_command(self) -> None:
        from lib.cicd.models import scoped_mypy
        from lib.cicd.steps import BUILTIN_PLANS

        for plan in ("finish", "check"):
            step = next(s for s in BUILTIN_PLANS[plan] if s.id == "typecheck")
            assert scoped_mypy("uv run --extra dev") in step.command, plan
