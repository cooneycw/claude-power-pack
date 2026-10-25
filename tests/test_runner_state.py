"""Tests for CI/CD runner state persistence."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from lib.cicd.state import RunState, StepRecord, StepStatus, compute_tree_signature


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
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

    @requires_git
    def test_save_lands_outside_the_working_tree_in_a_git_repo(self, tmp_project: Path):
        """The actual Nit Store defect (issue #1409, comment 5847507826):
        a failed gate in cooneycw/skillc#8 left an untracked
        ``.claude/runs/finish-cfaef128.json`` that the next prescribed
        ``git add -A`` committed, and a later successful run's cleanup then
        committed its DELETION too - gate bookkeeping, and a deletion
        nobody did, both landing in the repository's history. In a git
        repo the state file must live where ``git add -A`` structurally
        cannot reach it."""
        _git_repo(tmp_project)
        state = RunState.create("finish", ["lint"])
        path = state.save(tmp_project)

        assert not (tmp_project / ".claude" / "runs").exists(), (
            "the old location must stay empty in a git repo"
        )
        assert ".git" in path.parts, path
        assert path.is_relative_to(tmp_project / ".git"), path

        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=tmp_project,
            check=True, capture_output=True, text=True,
        ).stdout
        assert status == "", (
            f"the state file must be invisible to git status: {status!r}"
        )

    def test_save_falls_back_to_the_working_tree_without_git(self, tmp_project: Path):
        """`tmp_project` here is NOT a git repository (no `_git_repo` init),
        so `runner_state_dir` must fail open to the pre-#1409 location
        rather than raise or silently drop the state - the same rule
        `compute_tree_signature` already states for an unverifiable git
        answer."""
        state = RunState.create("finish", ["lint"])
        path = state.save(tmp_project)
        assert path == tmp_project / ".claude" / "runs" / f"{state.run_id}.json"
        assert path.exists()

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


@requires_git
class TestComputeTreeSignature:
    """compute_tree_signature() is the crash-vs-repair discriminator for
    issue #804: a resume is only honored when this value, taken at persist
    time and again at resume time, matches.
    """

    def test_stable_when_nothing_changed(self, tmp_project: Path):
        _git_repo(tmp_project)
        (tmp_project / "a.py").write_text("x = 1\n")
        first = compute_tree_signature(tmp_project)
        second = compute_tree_signature(tmp_project)
        assert first is not None
        assert first == second

    def test_changes_on_a_tracked_file_edit(self, tmp_project: Path):
        _git_repo(tmp_project)
        target = tmp_project / "a.py"
        target.write_text("x = 1\n")
        before = compute_tree_signature(tmp_project)
        target.write_text("x = 2  # fixed\n")
        after = compute_tree_signature(tmp_project)
        assert before is not None and after is not None
        assert before != after

    def test_changes_on_a_new_untracked_not_gitignored_file(self, tmp_project: Path):
        """A new file lint would pick up must count as a tree change even
        though git has never seen it before - that's the point of scoping
        to tracked + untracked-but-not-gitignored, not tracked alone."""
        _git_repo(tmp_project)
        before = compute_tree_signature(tmp_project)
        (tmp_project / "new_module.py").write_text("y = 1\n")
        after = compute_tree_signature(tmp_project)
        assert before is not None and after is not None
        assert before != after

    def test_ignores_a_gitignored_file(self, tmp_project: Path):
        _git_repo(tmp_project)
        (tmp_project / ".gitignore").write_text("ignored.log\n")
        before = compute_tree_signature(tmp_project)
        (tmp_project / "ignored.log").write_text("noise\n")
        after = compute_tree_signature(tmp_project)
        assert before is not None and after is not None
        assert before == after

    def test_ignores_the_runners_own_state_directory(self, tmp_project: Path):
        """.claude/runs/ is the runner's own bookkeeping, written by the
        very run whose resume this signature is meant to gate - it must
        never be able to invalidate itself. Regression guard: without the
        exclusion, this signature changes on every resume regardless of
        whether the TREE changed, because the failed run's own state file
        did not exist yet when the first signature was taken."""
        _git_repo(tmp_project)
        before = compute_tree_signature(tmp_project)
        runs_dir = tmp_project / ".claude" / "runs"
        runs_dir.mkdir(parents=True)
        (runs_dir / "finish-deadbeef.json").write_text('{"run_id": "finish-deadbeef"}\n')
        after = compute_tree_signature(tmp_project)
        assert before is not None and after is not None
        assert before == after

    def test_none_outside_a_git_repository(self, tmp_project: Path):
        # tmp_project is a bare directory - never git-init'd.
        assert compute_tree_signature(tmp_project) is None

    def test_none_when_git_is_unavailable(self, tmp_project: Path, monkeypatch: pytest.MonkeyPatch):
        _git_repo(tmp_project)
        monkeypatch.setattr(shutil, "which", lambda _cmd: None)
        assert compute_tree_signature(tmp_project) is None


class TestResumeStateEvidence:
    @pytest.fixture(autouse=True)
    def isolated_state(self, tmp_project, monkeypatch):
        from lib.cicd import state as module
        monkeypatch.setattr(module, "runner_state_dir", lambda root: root / ".state")

    @staticmethod
    def evidence(state):
        getter = getattr(state, "resume_state_evidence", None)
        value = getter() if getter else None
        assert isinstance(value, dict), "real state path has no v1 resume evidence"
        return value

    def test_resume_state_exact_save_load_and_persisted_schema(self, tmp_project):
        state = RunState.create("check", ["stage-a"])
        before = state.to_dict()
        path = state.save(tmp_project)
        raw = path.read_bytes()
        saved = self.evidence(state)
        assert saved["version"] == 1 and saved["family"] == "cpp-run-state"
        assert saved["consumed"]["status"] == "none"
        assert saved["generated"] == {"status": "written", "file": path.name,
            "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "reason": None}
        assert json.loads(raw) == before == state.to_dict()
        loaded = RunState.load(state.run_id, tmp_project)
        observed = self.evidence(loaded)
        assert observed["consumed"] == {**saved["generated"], "status": "loaded"}
        assert observed["generated"]["status"] == "none"
        assert loaded.to_dict() == before
        loaded.save(tmp_project)
        assert path.read_bytes() == raw  # unchanged bytes are still a real save
        assert self.evidence(loaded)["generated"]["status"] == "written"
        loaded.cleanup(tmp_project)
        assert self.evidence(loaded)["final_state"]["status"] == "absent"

    def test_resume_state_post_load_swap_cannot_rewrite_consumed_bytes(self, tmp_project, monkeypatch):
        state = RunState.create("check", ["stage-a"])
        path = state.save(tmp_project)
        original = path.read_bytes()
        replacement = original.replace(b'"pending"', b'"failed"')
        assert original != replacement
        read_bytes, read_text, write_bytes = Path.read_bytes, Path.read_text, Path.write_bytes
        reads = []

        def swap_bytes(candidate):
            raw = read_bytes(candidate)
            if candidate == path:
                reads.append("bytes")
                write_bytes(path, replacement)
                assert read_bytes(path) == replacement
            return raw

        def swap_text(candidate, *args, **kwargs):
            text = read_text(candidate, *args, **kwargs)
            if candidate == path:
                reads.append("text")
                write_bytes(path, replacement)
                assert read_bytes(path) == replacement
            return text

        monkeypatch.setattr(Path, "read_bytes", swap_bytes)
        monkeypatch.setattr(Path, "read_text", swap_text)
        loaded = RunState.load(state.run_id, tmp_project)
        assert len(reads) == 1 and loaded.step_records[0].status == StepStatus.PENDING
        observed = self.evidence(loaded)
        assert observed["consumed"]["sha256"] == "sha256:" + hashlib.sha256(original).hexdigest()
        assert observed["consumed"]["bytes"] == len(original)
        assert len(reads) == 1  # evidence is never a later filesystem reread

    def test_resume_state_post_save_swap_cannot_rewrite_generated_bytes(self, tmp_project, monkeypatch):
        state = RunState.create("check", ["stage-a"])
        original = json.dumps(state.to_dict(), indent=2).encode()
        replacement = b"untrusted replacement after the write"
        assert replacement != original
        write_bytes, write_text = Path.write_bytes, Path.write_text
        captured = []

        def swap_bytes(path, raw):
            written = write_bytes(path, raw)
            captured.append(raw)
            write_bytes(path, replacement)
            assert path.read_bytes() == replacement
            return written

        def swap_text(path, text, *args, **kwargs):
            written = write_text(path, text, *args, **kwargs)
            captured.append(text.encode())
            write_bytes(path, replacement)
            assert path.read_bytes() == replacement
            return written

        monkeypatch.setattr(Path, "write_bytes", swap_bytes)
        monkeypatch.setattr(Path, "write_text", swap_text)
        state.save(tmp_project)
        assert captured == [original]
        observed = self.evidence(state)
        assert observed["generated"]["sha256"] == "sha256:" + hashlib.sha256(original).hexdigest()
        assert observed["generated"]["bytes"] == len(original)

    @pytest.mark.parametrize("fault", ["raise", "short"])
    def test_resume_state_later_failed_save_invalidates_prior_success(self, tmp_project, monkeypatch, fault):
        state = RunState.create("check", ["stage-a"])
        path = state.save(tmp_project)
        assert path.is_file()
        error = OSError("private state error must not enter protocol")
        write_bytes, write_text = Path.write_bytes, Path.write_text

        def broken_bytes(target, raw):
            if fault == "raise":
                raise error
            partial = raw[:len(raw) // 2]
            write_bytes(target, partial)
            assert target.read_bytes() == partial and partial != raw
            return len(partial)

        def broken_text(target, text, *args, **kwargs):
            if fault == "raise":
                raise error
            partial = text[:len(text) // 2]
            write_text(target, partial, *args, **kwargs)
            assert target.read_text() == partial and partial != text
            return len(partial)

        monkeypatch.setattr(Path, "write_bytes", broken_bytes)
        monkeypatch.setattr(Path, "write_text", broken_text)
        with pytest.raises(OSError) as caught:
            state.save(tmp_project)
        if fault == "raise":
            assert caught.value is error
        observed = self.evidence(state)
        assert observed["generated"]["status"] == "unreadable"
        assert observed["generated"]["sha256"] is None and observed["generated"]["bytes"] is None
        assert "private state error" not in json.dumps(observed)

    def test_resume_state_unknown_selection_is_not_no_input(self, tmp_project):
        from lib.cicd import state as module
        tracker = module.ResumeStateEvidence("check")
        directory = tmp_project / ".state"
        directory.mkdir()
        path = directory / "check-bad.json"
        path.write_bytes(b"not JSON")
        assert path.read_bytes() == b"not JSON"
        assert RunState.find_latest("check", tmp_project, evidence=tracker) is None
        assert tracker.snapshot()["consumed"]["status"] == "unreadable"
        path.unlink()
        clean = module.ResumeStateEvidence("check")
        assert RunState.find_latest("check", tmp_project, evidence=clean) is None
        assert clean.snapshot()["consumed"]["status"] == "none"

    def test_resume_state_auto_selects_the_actual_failed_buffer(self, tmp_project):
        state = RunState.create("check", ["stage-a"])
        state.mark_step_failed(0, 1)
        path = state.save(tmp_project)
        raw = path.read_bytes()
        found = RunState.find_latest("check", tmp_project)
        assert found is not None
        observed = self.evidence(found)
        assert observed["consumed"]["sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
        assert observed["generated"]["status"] == "none"

    def test_resume_state_bounds_change_evidence_not_io(self, tmp_project, monkeypatch):
        from lib.cicd import state as module
        state = RunState.create("check", ["stage-a"])
        path = state.save(tmp_project)
        assert len(path.read_bytes()) > 32
        assert module.RESUME_STATE_MAX_BYTES == 67108864
        monkeypatch.setattr(module, "RESUME_STATE_MAX_BYTES", 32)
        loaded = RunState.load(state.run_id, tmp_project)
        assert loaded.to_dict() == state.to_dict()
        assert self.evidence(loaded)["consumed"]["status"] == "unreadable"
        loaded.save(tmp_project)
        assert self.evidence(loaded)["generated"]["reason"] == "size-limit"

    @pytest.mark.parametrize("case", json.loads(
        (Path(__file__).parent / "fixtures/cicd-resume-state/cases.json").read_text()
    )["producer_inputs"], ids=lambda case: case["id"])
    def test_resume_state_fixture_inputs_through_actual_save(self, tmp_project, case):
        state = RunState.create(case["plan"], ["stage-a"])
        if "run_id" in case:
            state.run_id = case["run_id"]
        path = state.save(tmp_project)
        assert path.is_file() and state.plan_name == case["plan"]
        observed = self.evidence(state)
        assert observed["plan"] == case["wire_plan"]
        assert observed["generated"]["status"] == case["generated"]
        if case["wire_plan"] is None:
            assert case["plan"] not in json.dumps(observed)

    def test_resume_state_invalid_path_cannot_replace_the_original_error(self, tmp_project):
        state = RunState.create("invalid\x00plan", ["stage-a"])
        with pytest.raises(ValueError) as caught:
            state.save(tmp_project)
        assert "null" in str(caught.value).lower()
        observed = self.evidence(state)
        assert observed["plan"] is None
        assert observed["generated"]["status"] == "unreadable"

    def test_resume_state_no_selection_does_not_claim_empty_directory(self, tmp_project):
        from lib.cicd import state as module
        state = RunState.create("check", ["stage-a"])
        state.mark_complete()
        path = state.save(tmp_project)
        assert path.exists() and state.status == "success"
        tracker = module.ResumeStateEvidence("check")
        assert RunState.find_latest("check", tmp_project, evidence=tracker) is None
        assert path.exists()
        assert tracker.snapshot()["consumed"]["status"] == "none"
        assert tracker.snapshot()["final_state"]["status"] == "unreadable"

    def test_resume_state_same_bytes_in_neighbor_do_not_prove_ownership(self, tmp_project):
        state = RunState.create("check", ["stage-a"])
        first = state.save(tmp_project)
        neighbor = tmp_project / "neighbor"
        second = neighbor / ".state" / first.name
        second.parent.mkdir(parents=True)
        second.write_bytes(first.read_bytes())
        assert first.read_bytes() == second.read_bytes() and first != second
        one = self.evidence(RunState.load(state.run_id, tmp_project))
        two = self.evidence(RunState.load(state.run_id, neighbor))
        assert one == two
        assert set(one) == {"version", "family", "plan", "consumed", "generated", "final_state"}
        # No identity here binds an attempt/repository/source. Consumers supply it.

    def test_resume_state_serialization_error_is_same_object_and_not_prior_success(
            self, tmp_project):
        state = RunState.create("check", ["stage-a"])
        state.save(tmp_project)
        state.step_records[0].output = object()
        assert not isinstance(state.step_records[0].output, str)
        with pytest.raises(TypeError) as caught:
            state.save(tmp_project)
        assert state._resume_tracker().error is caught.value
        observed = self.evidence(state)
        assert observed["generated"]["reason"] == "serialization-failed"
        assert observed["generated"]["sha256"] is None

    def test_resume_state_failed_final_observation_is_not_absence(self, tmp_project, monkeypatch):
        state = RunState.create("check", ["stage-a"])
        path = state.save(tmp_project)
        lstat = Path.lstat

        def unreadable(candidate, *args, **kwargs):
            if candidate == path:
                raise PermissionError("private observation failure")
            return lstat(candidate, *args, **kwargs)

        monkeypatch.setattr(Path, "lstat", unreadable)
        observed = self.evidence(state)
        assert observed["final_state"] == {"status": "unreadable", "reason": "presence-unreadable"}
        assert observed["generated"]["status"] == "written"
        assert "private observation" not in json.dumps(observed)

    @pytest.mark.parametrize("operation", ["load", "save"])
    @pytest.mark.parametrize("kind", ["parent", "absolute", "embedded"])
    def test_resume_state_unsafe_logical_id_is_not_laundered_by_basename(
            self, tmp_project, operation, kind):
        state = RunState.create("check", ["stage-a"])
        if kind == "parent":
            state.run_id = "../foreign"
        elif kind == "absolute":
            state.run_id = str(tmp_project / "absolute-owned")
        else:
            state.run_id = "sub/foreign"
            (tmp_project / ".state" / "sub").mkdir(parents=True)
        expected = (tmp_project / ".state" / (state.run_id + ".json")).resolve()
        assert expected.is_relative_to(tmp_project)  # every actual write is fixture-owned
        path = state.save(tmp_project)
        assert path.resolve() == expected and path.is_file()
        observed_state = RunState.load(state.run_id, tmp_project) if operation == "load" else state
        assert observed_state.run_id == state.run_id  # existing I/O/parse choice is unchanged
        observed = self.evidence(observed_state)
        identity = observed["consumed" if operation == "load" else "generated"]
        assert identity["status"] == "unreadable" and identity["reason"] == "unsafe-logical-id"
        assert identity["file"] is None and identity["sha256"] is None
        assert state.run_id not in json.dumps(observed)

    def test_resume_state_safe_logical_id_allows_absolute_filesystem_location(self, tmp_project):
        assert tmp_project.is_absolute()
        state = RunState.create("check", ["stage-a"])
        path = state.save(tmp_project)
        assert path.is_absolute()
        observed = self.evidence(RunState.load(state.run_id, tmp_project))
        assert observed["consumed"]["status"] == "loaded"
        assert observed["consumed"]["file"] == path.name
        assert str(tmp_project) not in json.dumps(observed)

    def test_resume_state_direct_load_keeps_original_exception_identity(self, tmp_project, monkeypatch):
        from lib.cicd import state as module
        state = RunState.create("check", ["stage-a"])
        path = state.save(tmp_project)
        assert path.is_file()
        original_read = Path.read_bytes
        error = OSError("private load error")

        def denied(candidate):
            if candidate == path:
                raise error
            return original_read(candidate)

        tracker = module.ResumeStateEvidence("check")
        monkeypatch.setattr(Path, "read_bytes", denied)
        with pytest.raises(OSError) as caught:
            RunState.load(state.run_id, tmp_project, evidence=tracker)
        assert caught.value is error and tracker.error is error
        observed = tracker.snapshot()
        assert observed["consumed"]["status"] == "unreadable"
        assert "private load error" not in json.dumps(observed)

    def test_resume_state_rejected_requested_id_cannot_publish_innocent_final_presence(self, tmp_project):
        state = RunState.create("check", ["stage-a"])
        state.run_id = "foreign"
        path = state.save(tmp_project)
        outside_state = tmp_project / "foreign.json"
        outside_state.write_bytes(path.read_bytes())
        requested = "../foreign"
        assert (tmp_project / ".state" / (requested + ".json")).resolve() == outside_state
        loaded = RunState.load(requested, tmp_project)
        assert loaded.run_id == "foreign"
        observed = self.evidence(loaded)
        assert observed["consumed"]["status"] == "unreadable"
        assert observed["final_state"] == {"status": "unreadable", "reason": "unsafe-logical-id"}
