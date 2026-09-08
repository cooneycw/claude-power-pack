"""Tests for CI/CD runner state persistence."""

from pathlib import Path

import pytest

from lib.cicd.state import RunState, StepRecord, StepStatus


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    return tmp_path


class TestStepRecord:
    def test_defaults(self):
        record = StepRecord(step_id="lint")
        assert record.status == StepStatus.PENDING
        assert record.exit_code == 0
        assert record.attempt == 0

    def test_roundtrip(self):
        record = StepRecord(
            step_id="test",
            status=StepStatus.FAILED,
            exit_code=1,
            output="FAIL: test_foo",
            error="AssertionError",
            attempt=2,
            max_attempts=3,
        )
        d = record.to_dict()
        restored = StepRecord.from_dict(d)
        assert restored.step_id == "test"
        assert restored.status == StepStatus.FAILED
        assert restored.exit_code == 1
        assert restored.attempt == 2


class TestRunState:
    def test_create(self):
        state = RunState.create("finish", ["lint", "test", "security"])
        assert state.plan_name == "finish"
        assert len(state.step_records) == 3
        assert state.current_index == 0
        assert state.status == "running"
        assert all(r.status == StepStatus.PENDING for r in state.step_records)

    def test_save_and_load(self, tmp_project: Path):
        state = RunState.create("finish", ["lint", "test"])
        state.save(tmp_project)

        loaded = RunState.load(state.run_id, tmp_project)
        assert loaded.run_id == state.run_id
        assert loaded.plan_name == "finish"
        assert len(loaded.step_records) == 2
        assert loaded.current_index == 0

    def test_mark_step_success(self, tmp_project: Path):
        state = RunState.create("check", ["lint", "test"])
        state.mark_step_running(0)
        assert state.step_records[0].status == StepStatus.RUNNING
        assert state.step_records[0].attempt == 1

        state.mark_step_success(0, output="All checks passed")
        assert state.step_records[0].status == StepStatus.SUCCESS
        assert state.current_index == 1
        assert "passed" in state.step_records[0].output

    def test_mark_step_failed(self, tmp_project: Path):
        state = RunState.create("check", ["lint", "test"])
        state.mark_step_running(0)
        state.mark_step_failed(0, exit_code=1, error="ruff: 3 errors")

        assert state.step_records[0].status == StepStatus.FAILED
        assert state.step_records[0].exit_code == 1
        assert state.status == "failed"
        assert state.current_index == 0  # did not advance

    def test_mark_step_skipped(self):
        state = RunState.create("finish", ["lint", "test"])
        state.mark_step_skipped(0)
        assert state.step_records[0].status == StepStatus.SKIPPED
        assert state.current_index == 1

    def test_mark_complete(self):
        state = RunState.create("check", ["lint"])
        state.mark_step_success(0)
        state.mark_complete()
        assert state.status == "success"
        assert state.finished_at is not None

    def test_cleanup(self, tmp_project: Path):
        state = RunState.create("check", ["lint"])
        path = state.save(tmp_project)
        assert path.exists()
        state.cleanup(tmp_project)
        assert not path.exists()

    def test_find_latest_failed(self, tmp_project: Path):
        # No runs yet
        assert RunState.find_latest("finish", tmp_project) is None

        # Create a failed run
        state = RunState.create("finish", ["lint", "test"])
        state.mark_step_running(0)
        state.mark_step_failed(0, exit_code=1)
        state.save(tmp_project)

        found = RunState.find_latest("finish", tmp_project)
        assert found is not None
        assert found.run_id == state.run_id
        assert found.status == "failed"

    def test_find_latest_ignores_success(self, tmp_project: Path):
        state = RunState.create("finish", ["lint"])
        state.mark_step_success(0)
        state.mark_complete()
        state.save(tmp_project)

        assert RunState.find_latest("finish", tmp_project) is None

    def test_pending_steps(self):
        state = RunState.create("finish", ["lint", "test", "security"])
        state.mark_step_success(0)

        pending = state.pending_steps()
        assert len(pending) == 2
        assert pending[0][0] == 1  # index
        assert pending[0][1].step_id == "test"

    def test_can_retry(self):
        state = RunState.create("check", ["lint"])
        state.step_records[0].max_attempts = 3
        state.step_records[0].attempt = 1
        assert state.can_retry(0)

        state.step_records[0].attempt = 3
        assert not state.can_retry(0)

    def test_summary(self):
        state = RunState.create("finish", ["lint", "test"])
        state.mark_step_success(0)
        summary = state.summary()
        assert summary["plan"] == "finish"
        assert summary["status"] == "running"
        assert summary["steps"][0]["status"] == "success"
        assert summary["steps"][1]["status"] == "pending"

    def test_roundtrip_json(self, tmp_project: Path):
        state = RunState.create("deploy", ["security", "deploy"])
        state.mark_step_success(0, output="clean")
        state.mark_step_running(1)
        state.mark_step_failed(1, exit_code=1, error="deploy error")
        state.save(tmp_project)

        loaded = RunState.load(state.run_id, tmp_project)
        assert loaded.step_records[0].status == StepStatus.SUCCESS
        assert loaded.step_records[1].status == StepStatus.FAILED
        assert loaded.step_records[1].error == "deploy error"
        assert loaded.current_index == 1  # step 0 succeeded (advancing to 1), step 1 failed


class TestCarriedOverStepsAreMarked:
    """A resumed run must not render a carried-over step like a fresh one.

    Issue #838 follow-up. A resume starts at ``current_index``, so every
    earlier step keeps the result it earned in a PREVIOUS invocation - against
    a tree that has usually changed, because fixing something is the normal
    reason to resume. Until this marking, those results were reported in
    exactly the form of a step that had just run.

    Observed twice on one day, in opposite registers:

    * a cached ``test: SUCCESS (103 passed)`` on a run where pytest was never
      invoked at all, and
    * a cached ``lint: SUCCESS`` for a tree whose linted source had been
      edited between the two runs - the quieter one, because the suite really
      did re-execute and only the lint result was stale.

    Both were caught by out-of-band knowledge: grepping line 1 for "Resuming"
    and counting pytest invocations, and remembering a hand-run ``make lint``.
    Neither is a property of the output, which is what these tests fix.
    """

    def _failed_at_second_step(self) -> RunState:
        state = RunState.create("finish", ["lint", "test", "typecheck"])
        state.mark_step_success(0, "ruff ok", tests={"passed": 12, "executed": 12})
        state.mark_step_running(1)
        state.mark_step_failed(1, error="boom", exit_code=1)
        return state

    def test_a_carried_step_is_marked_when_the_run_resumed_past_it(self):
        state = self._failed_at_second_step()
        lint = state.summary(executed_from=1)["steps"][0]
        assert lint["carried_from_previous_run"] is True
        assert lint["executed_in_this_run"] is False

    def test_a_step_executed_in_this_invocation_is_not_marked(self):
        """The other direction, and the one that keeps the marking meaningful.

        A marking that appeared on every step would be noise, and a reader who
        learns to ignore it is worse off than one who never had it.
        """
        state = self._failed_at_second_step()
        steps = state.summary(executed_from=1)["steps"]
        assert "carried_from_previous_run" not in steps[1]
        assert "executed_in_this_run" not in steps[1]

    def test_a_fresh_run_marks_nothing(self):
        """executed_from=0 is a run that started at the beginning."""
        state = self._failed_at_second_step()
        for entry in state.summary(executed_from=0)["steps"]:
            assert "carried_from_previous_run" not in entry

    def test_omitting_executed_from_is_unchanged(self):
        """Callers that do not know where the invocation began keep the old
        shape exactly - the marking is additive, never a silent rewrite."""
        state = self._failed_at_second_step()
        for entry in state.summary()["steps"]:
            assert "carried_from_previous_run" not in entry
            assert "executed_in_this_run" not in entry

    def test_a_pending_step_before_the_resume_point_is_not_called_carried(self):
        """Nothing to be stale about.

        A pending or skipped record before the resume index has no result, so
        marking it 'carried' would assert a previous execution that never
        happened - a false claim in the direction of more confidence, which is
        the direction that matters.
        """
        state = RunState.create("finish", ["lint", "test", "typecheck"])
        state.mark_step_skipped(0)
        state.mark_step_running(1)
        state.mark_step_failed(1, error="boom", exit_code=1)
        entry = state.summary(executed_from=1)["steps"][0]
        assert entry["status"] == StepStatus.SKIPPED.value
        assert "carried_from_previous_run" not in entry
