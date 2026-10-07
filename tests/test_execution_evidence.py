"""Durable per-skill execution evidence (issue #1366).

Good / bad / unknown controls for the record writer and its `verify` reader. The
reader's verdict is consumed by another repository (skillc #249) that does not
re-derive it, so every way it can say `supported` has a case that must NOT.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from lib.cicd import evidence
from lib.cicd.evidence import (
    NOT_SUPPORTED,
    SUPPORTED,
    UNKNOWN,
    Recorder,
    build_record,
    redact_url,
    run_with_evidence,
    tree_identity,
    verify,
)
from lib.cicd.runner import DeterministicRunner
from lib.cicd.state import RunState, StepStatus, runner_state_dir
from lib.cicd.steps import StepDef

# Every repository fixture here is a real git repository.
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

# Synthetic, and ASSEMBLED at run time so the repository's own secret scanner
# never sees a token-shaped literal in this file (it would block the gate, and a
# suppression would be one more allowlist to keep honest). The privacy test only
# needs a value with a real token's SHAPE to prove it is redacted.
SYNTHETIC_TOKEN = "gh" + "p_" + "SYNTHETIC" + "0" * 27
SYNTHETIC_ENV_VALUE = "-".join(("synthetic", "env", "value", "1366"))


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git is required to build a repository fixture")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "a.txt").write_text("one\n")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-q", "-m", "init")
    _git(root, "remote", "add", "origin", f"https://x-access-token:{SYNTHETIC_TOKEN}@github.com/o/r.git")
    monkeypatch.setenv(evidence.ENV_SKILL, "flow-check")
    monkeypatch.delenv(evidence.ENV_EXPORT, raising=False)
    monkeypatch.delenv(evidence.ENV_PARENT, raising=False)
    return root


def _run(root: Path, steps: list[StepDef]) -> tuple[Any, Any]:
    runner = DeterministicRunner(project_root=root, output=StringIO())
    result = run_with_evidence(runner, "check", root, steps)
    store = evidence.store_dir(root, "flow-check")
    records = sorted(store.glob("*.json"), key=lambda p: p.stat().st_mtime) if store else []
    return result, records[-1] if records else None


def _gate(id_: str, command: str = "echo ok", **kw) -> StepDef:
    return StepDef(id=id_, command=command, gate=True, timeout_seconds=30, **kw)


def _verdict(path: Path, root: Path | None = None, current: bool = True) -> tuple[str, list[str]]:
    v, reasons, _ = verify(path, root, check_current=current)
    return v, reasons


# --- GOOD -------------------------------------------------------------------


def test_good_clean_completed_run_is_supported(repo: Path) -> None:
    result, path = _run(repo, [_gate("lint"), _gate("typecheck")])
    assert result.success and path is not None
    record = json.loads(path.read_text())
    assert record["terminal"] is True
    assert record["outcome"] == "completed"
    assert record["observed"]["tree_at_end"]["head"]
    v, reasons, claim = verify(path, repo)
    assert (v, reasons) == (SUPPORTED, [])
    assert claim and "lint success" in claim and "does NOT attest" in claim


def test_bad_green_test_step_with_unparsed_summary_is_qualified(repo: Path) -> None:
    # A `test` gate that exits 0 with no parseable summary is UNKNOWN to the
    # runner (#621/#977); the record must carry that, not a clean pass.
    result, path = _run(repo, [_gate("lint"), _gate("test")])
    assert result.success
    record = json.loads(path.read_text())
    assert record["outcome"] == "completed-with-qualifications"
    assert record["observed"]["runner"]["warnings"]
    assert _verdict(path, repo)[0] == NOT_SUPPORTED


def test_no_opt_in_writes_nothing_and_run_is_unchanged(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(evidence.ENV_SKILL)
    result, path = _run(repo, [_gate("lint")])
    assert result.success
    assert path is None


# --- BAD: each must NOT read as supported ----------------------------------


def test_bad_stale_head_with_dirty_changes(repo: Path) -> None:
    (repo / "a.txt").write_text("dirty once\n")
    _, path = _run(repo, [_gate("lint")])
    record = json.loads(path.read_text())
    assert record["observed"]["tree_at_end"]["dirty"] is True
    assert _verdict(path, repo)[0] == SUPPORTED
    # The #804 shape: the SAME file edited again. `git status` is identical
    # (` M a.txt`) - only the content signature can tell.
    (repo / "a.txt").write_text("dirty twice\n")
    v, reasons = _verdict(path, repo)
    assert v == NOT_SUPPORTED
    assert any("working tree content changed" in r for r in reasons)
    # And a new HEAD is stale too.
    _git(repo, "commit", "-qam", "next")
    v, reasons = _verdict(path, repo)
    assert v == NOT_SUPPORTED and any("stale: record is for HEAD" in r for r in reasons)


def test_bad_duplicate_and_replayed_invocation(repo: Path) -> None:
    _, path = _run(repo, [_gate("lint")])
    replay = path.with_name("replayed.json")
    shutil.copy(path, replay)
    v, reasons = _verdict(replay, repo)
    assert v == NOT_SUPPORTED
    assert any("does not match invocation" in r for r in reasons)
    v, reasons = _verdict(path, repo)
    assert v == NOT_SUPPORTED and any("duplicate invocation" in r for r in reasons)


def test_bad_missing_terminal_event(repo: Path) -> None:
    rec = Recorder(repo, "flow-check", "check", log=StringIO())
    rec.begin()  # killed before finish: SIGKILL never reaches a finally
    assert rec.path is not None
    record = json.loads(rec.path.read_text())
    assert record["terminal"] is False and record["outcome"] == "running"
    v, reasons = _verdict(rec.path, repo)
    assert v == NOT_SUPPORTED and any("no terminal event" in r for r in reasons)


def test_bad_interrupted_run_is_recorded_and_reraised(repo: Path) -> None:
    class Boom(DeterministicRunner):
        def run(self, plan_name, step_defs=None):  # type: ignore[override]
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_with_evidence(Boom(project_root=repo, output=StringIO()), "check", repo, [_gate("lint")])
    path = next((repo / ".git" / "cpp-evidence" / "flow-check").glob("*.json"))
    record = json.loads(path.read_text())
    assert record["outcome"] == "interrupted"
    assert record["terminal_event"]["detail"] == "KeyboardInterrupt"
    assert _verdict(path, repo)[0] == NOT_SUPPORTED


def test_bad_failed_gate_keeps_its_exit_and_unreached_steps_have_none(repo: Path) -> None:
    result, path = _run(repo, [_gate("lint", "exit 7"), _gate("test")])
    assert not result.success
    checks = {c["id"]: c for c in json.loads(path.read_text())["observed"]["checks"]}
    assert checks["lint"]["status"] == "failed" and checks["lint"]["exit_code"] == 7
    # Never reached: no exit code at all, never a fabricated 0.
    assert checks["test"]["status"] == "pending" and checks["test"]["exit_code"] is None
    assert checks["test"]["completed_at"] is None
    assert _verdict(path, repo)[0] == NOT_SUPPORTED


def test_bad_skipped_gate_is_not_passed(repo: Path) -> None:
    _, path = _run(repo, [_gate("lint"), _gate("typecheck", skip_if="true")])
    record = json.loads(path.read_text())
    tc = next(c for c in record["observed"]["checks"] if c["id"] == "typecheck")
    assert tc["status"] == "skipped" and tc["exit_code"] is None and tc["reason"]
    v, reasons = _verdict(path, repo)
    assert v == NOT_SUPPORTED and any("typecheck" in r for r in reasons)


def _state(statuses: dict[str, StepStatus], status: str, **per_step) -> RunState:
    st = RunState.create("check", list(statuses))
    st.status = status
    for rec in st.step_records:
        rec.status = statuses[rec.step_id]
        for key, value in per_step.get(rec.step_id, {}).items():
            setattr(rec, key, value)
    return st


def _write(repo: Path, **kw) -> Path:
    tree = tree_identity(repo)
    rec = build_record(
        invocation_id="0" * 32, skill="flow-check", plan_name="check", root=repo,
        begun_at="2026-10-04T00:00:00Z", tree_start=tree, tree_end=tree, **kw,
    )
    path = repo.parent / "store" / f"{'0' * 32}.json"
    evidence.atomic_write(path, rec)
    return path


def test_bad_stopped_aggregate_never_credits_unrun_gates(repo: Path) -> None:
    state = _state(
        {"lint": StepStatus.NOT_RUN, "test": StepStatus.NOT_RUN, "verify": StepStatus.FAILED},
        "failed",
        lint={"not_run_reason": "verify failed"},
        verify={"exit_code": 2},
    )
    path = _write(repo, state=state, gate_ids=["lint", "test", "verify"], terminal_kind="failed")
    record = json.loads(path.read_text())
    assert record["outcome"] == "stopped"
    lint = next(c for c in record["observed"]["checks"] if c["id"] == "lint")
    assert lint["status"] == "not-run" and lint["exit_code"] is None
    assert lint["reason"] == "verify failed"
    assert _verdict(path, repo)[0] == NOT_SUPPORTED


def test_bad_zero_population_is_not_a_pass(repo: Path) -> None:
    state = _state(
        {"test": StepStatus.SUCCESS}, "success",
        test={"tests": {"passed": 0, "failed": 0, "skipped": 4, "errors": 0, "executed": 0}},
    )
    path = _write(repo, state=state, gate_ids=["test"], terminal_kind="completed")
    record = json.loads(path.read_text())
    pop = record["observed"]["checks"][0]["population"]
    assert pop == {**pop, "measured": True, "count": 0}
    assert record["outcome"] == "completed-with-qualifications"
    v, reasons = _verdict(path, repo)
    assert v == NOT_SUPPORTED and any("examined nothing" in r for r in reasons)


def test_unmeasured_population_stays_unmeasured_not_zero(repo: Path) -> None:
    state = _state(
        {"lint": StepStatus.SUCCESS}, "success",
        lint={"coverage": {"state": "unknown", "units": None, "tool": "ruff"}},
    )
    path = _write(repo, state=state, gate_ids=["lint"], terminal_kind="completed")
    pop = json.loads(path.read_text())["observed"]["checks"][0]["population"]
    assert pop["measured"] is False and pop["count"] is None
    v, _, claim = verify(path, repo)
    assert v == SUPPORTED and claim is not None and "population not measured" in claim


# --- UNKNOWN ----------------------------------------------------------------


def test_unknown_unreadable_record(tmp_path: Path) -> None:
    bad = tmp_path / "x.json"
    bad.write_text("{ not json")
    assert _verdict(bad)[0] == UNKNOWN
    assert _verdict(tmp_path / "missing.json")[0] == UNKNOWN


def test_unknown_schema_is_not_guessed(repo: Path) -> None:
    _, path = _run(repo, [_gate("lint")])
    data = json.loads(path.read_text())
    data["schema"] = "cpp.execution-evidence/v999"
    path.write_text(json.dumps(data))
    assert _verdict(path, repo)[0] == UNKNOWN


def test_unknown_check_missing_population_is_not_a_crash(repo: Path) -> None:
    """A check entry missing `population` entirely must read UNKNOWN, never crash.

    cooneycw/claude-power-pack#1373: `_structure_errors` guarded with
    `c.get("population", {})` on one line and then indexed `c["population"]`
    directly on the next, so the guard's own default never protected the read
    it was written for. This is squarely the reader's documented threat model
    (a malformed/incomplete record), and a `KeyError` is outside its documented
    exit-code contract (0/3/4 only) - the same class of defect `test_unknown_schema_is_not_guessed`
    above exists to pin for a different field.
    """
    _, path = _run(repo, [_gate("lint")])
    data = json.loads(path.read_text())
    del data["observed"]["checks"][0]["population"]
    path.write_text(json.dumps(data))
    verdict, reasons = _verdict(path, repo)
    assert verdict == UNKNOWN
    assert any("population" in r for r in reasons)


def test_cli_exit_codes_follow_the_verdict(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, path = _run(repo, [_gate("lint")])
    assert evidence.cli(["verify", str(path), "--path", str(repo)]) == 0
    assert "EXECUTION_EVIDENCE: supported" in capsys.readouterr().out
    (repo / "a.txt").write_text("changed\n")
    assert evidence.cli(["verify", str(path), "--path", str(repo)]) == 3
    garbage = repo.parent / "g.json"
    garbage.write_text("[]")
    assert evidence.cli(["verify", str(garbage)]) == 4


# --- identity, privacy, storage --------------------------------------------


def test_record_binds_identity_and_separates_declared_from_observed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(evidence.ENV_PARENT, "parent-abc")
    monkeypatch.setenv(evidence.ENV_SKILL_SOURCE, "codex/skills/flow-check/SKILL.md")
    _, path = _run(repo, [_gate("lint")])
    record = json.loads(path.read_text())
    assert record["invocation_id"] == path.stem and record["run_id"].startswith("check-")
    assert record["declared"]["parent_invocation_id"] == "parent-abc"
    assert "not verified" in record["declared"]["source"]
    obs = record["observed"]
    assert obs["repository"]["worktree"] == str(repo.resolve())
    assert obs["helper"]["module_sha256"]["lib/cicd/evidence.py"]
    assert obs["helper"]["cpp_runner_modified"] in (True, False)
    assert obs["skill_source"]["path"] == ".claude/commands/flow/check.md"
    assert obs["tree_at_start"]["tree_signature"] == obs["tree_at_end"]["tree_signature"]


def test_privacy_no_credentials_or_environment(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CPP_TEST_PRIVATE_VALUE", SYNTHETIC_ENV_VALUE)
    _, path = _run(repo, [_gate("lint", f"echo {SYNTHETIC_TOKEN} $CPP_TEST_PRIVATE_VALUE")])
    text = path.read_text()
    assert SYNTHETIC_TOKEN not in text
    assert SYNTHETIC_ENV_VALUE not in text
    assert "x-access-token" not in text
    record = json.loads(text)
    assert record["observed"]["repository"]["origin"] == "https://github.com/o/r.git"
    assert record["observed"]["checks"][0]["evidence"]["output_sha256"]


def test_redact_url_shapes() -> None:
    assert redact_url("https://u:p@h.example:8443/o/r.git?t=1#x") == "https://h.example:8443/o/r.git"
    assert redact_url("git@github.com:o/r.git") == "git@github.com:o/r.git"
    assert redact_url(None) is None


def test_terminal_record_is_never_rewritten(repo: Path) -> None:
    rec = Recorder(repo, "flow-check", "check", log=StringIO())
    rec.begin()
    assert rec.path is not None
    assert rec.finish("completed", None) is not None
    first = rec.path.read_text()
    assert rec.finish("failed", None) is None
    assert rec.path.read_text() == first


def test_retention_prunes_oldest_and_keeps_newest(tmp_path: Path) -> None:
    for i in range(evidence.RETAIN + 5):
        p = tmp_path / f"{i:04d}.json"
        p.write_text("{}")
        os.utime(p, (1000 + i, 1000 + i))
    newest = tmp_path / "new.json"
    newest.write_text("{}")
    evidence.prune(tmp_path, protect=newest)
    left = sorted(tmp_path.glob("*.json"))
    assert len(left) == evidence.RETAIN and newest in left
    assert not (tmp_path / "0000.json").exists()


def test_export_writes_a_copy(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "artifacts"
    monkeypatch.setenv(evidence.ENV_EXPORT, str(out))
    _, path = _run(repo, [_gate("lint")])
    copy = out / path.name
    assert copy.read_text() == path.read_text()


def test_invalid_skill_name_records_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(evidence.ENV_SKILL, "../escape")
    result, path = _run(repo, [_gate("lint")])
    assert result.success and path is None
    assert not (repo / ".git" / "cpp-evidence").exists()


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "execution-evidence-verify.py"


def test_script_execution_evidence_verify_runs_with_bare_python(repo: Path) -> None:
    """scripts/execution-evidence-verify.py is stdlib-only: no uv, no pydantic."""
    import sys

    _, path = _run(repo, [_gate("lint")])
    ok = subprocess.run(
        [sys.executable, str(SCRIPT), str(path), "--path", str(repo)],
        capture_output=True, text=True, check=False,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert ok.stdout.rstrip().endswith("EXECUTION_EVIDENCE: supported")
    (repo / "a.txt").write_text("edited\n")
    stale = subprocess.run(
        [sys.executable, str(SCRIPT), str(path), "--path", str(repo)],
        capture_output=True, text=True, check=False,
    )
    assert stale.returncode == 3
    assert stale.stdout.rstrip().endswith("EXECUTION_EVIDENCE: not-supported")
    latest = subprocess.run(
        [sys.executable, str(SCRIPT), "latest", "flow-check", "--path", str(repo)],
        capture_output=True, text=True, check=False,
    )
    assert latest.returncode == 0 and str(path) in latest.stdout


# --- counter-model review (#1366): the READER re-derives, the summary is not trusted


def _good_record(repo: Path) -> tuple[Path, dict[str, Any]]:
    state = _state(
        {"lint": StepStatus.SUCCESS, "typecheck": StepStatus.SUCCESS}, "success",
        lint={"coverage": {"state": "covered", "units": 12, "tool": "ruff"}},
        typecheck={"coverage": {"state": "covered", "units": 40, "tool": "mypy"}},
    )
    path = _write(repo, state=state, gate_ids=["lint", "typecheck"], terminal_kind="completed")
    assert _verdict(path, repo)[0] == SUPPORTED, "precondition: the unmutated record is supported"
    return path, json.loads(path.read_text())


def _mutated(path: Path, record: dict[str, Any], mutate) -> Path:
    mutate(record)
    path.write_text(json.dumps(record))
    return path


@pytest.mark.parametrize(
    "label, mutate, needle",
    [
        ("zero population", lambda r: r["observed"]["checks"][0]["population"].update(count=0), "examined nothing"),
        ("declared gate with no entry", lambda r: r["observed"]["checks"].pop(1), "has no check entry"),
        ("terminal without event", lambda r: r.update(terminal_event=None), "no terminal event"),
        ("success with non-zero exit", lambda r: r["observed"]["checks"][0].update(exit_code=7), "exit code 7"),
        (
            "gate not run under a completed summary",
            lambda r: r["observed"]["checks"][1].update(status="not-run", exit_code=None),
            "not passed",
        ),
        (
            "rerun hidden from the summary",
            lambda r: r["observed"]["runner"].update(reruns=[{"step": "lint", "outcome": "passed-in-isolation"}]),
            "first attempt",
        ),
    ],
)
def test_bad_contradictory_record_is_not_supported_despite_its_summary(repo: Path, label, mutate, needle) -> None:
    path, record = _good_record(repo)
    assert record["outcome"] == "completed" and record["qualifications"] == []
    v, reasons = _verdict(_mutated(path, record, mutate), repo, current=False)
    assert v == NOT_SUPPORTED, label
    assert any(needle in r for r in reasons), (label, reasons)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(observed=None),
        lambda r: r["observed"].update(checks=[None]),
        lambda r: r["observed"].update(repository="x"),
        lambda r: r.update(terminal="yes"),
    ],
)
def test_unknown_malformed_nested_record_never_crashes(repo: Path, mutate, capsys: pytest.CaptureFixture[str]) -> None:
    path, record = _good_record(repo)
    _mutated(path, record, mutate)
    assert evidence.cli(["verify", str(path), "--path", str(repo)]) == 4
    assert capsys.readouterr().out.rstrip().endswith("EXECUTION_EVIDENCE: unknown")


def test_bad_rerun_that_passed_is_qualified_by_the_writer(repo: Path) -> None:
    state = _state({"test": StepStatus.SUCCESS}, "success",
                   test={"tests": {"passed": 10, "failed": 1, "skipped": 0, "errors": 0, "executed": 11}})
    path = _write(repo, state=state, gate_ids=["test"], terminal_kind="completed",
                  runner_facts={"reruns": [{"step": "test", "outcome": "passed-in-isolation", "ids": ["t::a"]}]})
    record = json.loads(path.read_text())
    assert record["outcome"] == "completed-with-qualifications"
    assert record["observed"]["runner"]["reruns"][0]["ids"] == ["t::a"]
    assert _verdict(path, repo)[0] == NOT_SUPPORTED


def test_unreached_and_skipped_steps_are_not_marked_executed(repo: Path) -> None:
    _, path = _run(repo, [_gate("lint", "exit 1"), _gate("test")])
    checks = {c["id"]: c for c in json.loads(path.read_text())["observed"]["checks"]}
    assert checks["lint"]["executed_in_this_invocation"] is True
    assert checks["test"]["executed_in_this_invocation"] is False
    shutil.rmtree(runner_state_dir(repo))  # or the next run RESUMES the failed one (issue #1409)
    _, path = _run(repo, [_gate("lint"), _gate("typecheck", skip_if="true")])
    checks = {c["id"]: c for c in json.loads(path.read_text())["observed"]["checks"]}
    assert checks["typecheck"]["executed_in_this_invocation"] is False


def test_bad_neighbour_worktree_record_neither_found_nor_supported(repo: Path, tmp_path: Path) -> None:
    neighbour = tmp_path / "neighbour"
    _git(repo, "worktree", "add", "-q", str(neighbour))
    _, mine = _run(repo, [_gate("lint")])
    _, theirs = _run(neighbour, [_gate("lint")])
    assert theirs.parent == mine.parent, "precondition: one shared store across worktrees"
    # The neighbour finished last; this checkout's latest is still its own.
    assert evidence.latest(repo, "flow-check") == mine
    assert evidence.latest(neighbour, "flow-check") == theirs
    v, reasons = _verdict(theirs, repo)
    assert v == NOT_SUPPORTED and any("not this checkout" in r for r in reasons)
    assert _verdict(theirs, neighbour)[0] == SUPPORTED


# --- counter-model re-review (#1366)


def test_bad_carried_test_record_with_failures_is_not_clean(repo: Path) -> None:
    """A resumed run carries the test record but not the earlier run's re-run list."""
    state = _state({"test": StepStatus.SUCCESS}, "success",
                   test={"tests": {"passed": 10, "failed": 1, "skipped": 0, "errors": 0, "executed": 11}})
    path = _write(repo, state=state, gate_ids=["test"], terminal_kind="completed",
                  executed_from=1, runner_facts={"tree_verified": True})
    record = json.loads(path.read_text())
    assert record["observed"]["checks"][0]["carried_from_previous_run"] is True
    assert record["observed"]["runner"]["reruns"] == [], "precondition: no re-run list survived"
    assert record["outcome"] == "completed-with-qualifications"
    record["outcome"], record["qualifications"] = "completed", []
    path.write_text(json.dumps(record))
    v, reasons = _verdict(path, repo, current=False)
    assert v == NOT_SUPPORTED and any("1 failure" in r for r in reasons)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["observed"]["repository"].update(worktree=None),
        lambda r: r["observed"]["tree_at_end"].update(head=None),
        lambda r: r["observed"].update(tree_at_end=None),
        lambda r: r["observed"]["tree_at_start"].update(tree_signature=None),
        lambda r: r["observed"].update(gates=[{}]),
        lambda r: r["observed"].update(runner="broken"),
        lambda r: r["observed"]["runner"].update(reruns="x"),
    ],
)
def test_unknown_missing_identity_or_malformed_even_without_freshness(repo: Path, mutate) -> None:
    path, record = _good_record(repo)
    _mutated(path, record, mutate)
    assert _verdict(path, repo, current=False)[0] == UNKNOWN
    assert evidence.cli(["verify", str(path), "--no-current"]) == 4
