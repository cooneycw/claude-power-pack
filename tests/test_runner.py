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
    RERUN_PASSED_IN_ISOLATION,
    DeterministicRunner,
    RunResult,
    _build_step_env,
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
        assert 'grep -q "^${id}:" Makefile 2>/dev/null' in body
        assert 'make "${id}" || FAILED=1' in body
        assert "uv run --extra dev ${uvargs} || FAILED=1" in body
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
        assert result.tests["test"]["streams_read"] == ["stdout", "stderr"]

    def test_a_rerun_summary_on_stderr_is_not_read_as_nothing_ran(
        self, tmp_project: Path
    ) -> None:
        """#900's verdict, extended to the stream dimension (issue #939).

        The re-run prints "no tests ran" on stdout and its real summary on
        stderr. Pre-fix the truthy all-zeros stdout outcome won, so the re-run
        reported RE-RUN INCONCLUSIVE and #900's `passed-in-isolation` verdict
        was never reached although a readable result existed.
        """
        step = StepDef(
            id="test",
            command=(
                "if [ -f rerun-marker ]; then "
                "printf '=== no tests ran in 0.01s ===\\n'; "
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

        assert result.reruns[0]["outcome"] == RERUN_PASSED_IN_ISOLATION, (
            "the re-run's summary was readable on stderr; reporting "
            "inconclusive would be the #939 defect wearing #621's hat"
        )
        assert "RE-RUN INCONCLUSIVE" not in log.getvalue()

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
            "streams_read": ["stdout"],
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

        `security_scan` is in both `finish` and `deploy`. A derived set keyed on
        id would silently resolve a disagreement between two declarations of the
        same id - "gate here, not there" becomes "gate everywhere" with nobody
        told. Make the disagreement fail instead of resolving it.
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
            step_defs=[
                self._always_run("lint"),
                self._always_skip("stale_commit_check"),
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
            step_defs=[self._always_run("lint"), self._always_skip("security_scan")],
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
