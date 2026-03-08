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
