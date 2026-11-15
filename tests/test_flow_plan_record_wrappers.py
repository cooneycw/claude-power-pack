"""The three plan-record run verbs /flow:auto calls (issue #1849).

`start`, `approve --plan` and `finish` wrap the existing verbs. What this pins,
at the NEW entry points rather than only in the underlying functions:

  - a malformed plan is refused by `approve --plan` and writes NOTHING;
  - a wrapper never reports success over a failed or unavailable inner result;
  - `finish` prints every inner verdict line, not one collapsed pass/fail;
  - the record `approve --plan` writes is the one the old verbs wrote.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "flow-plan-record.py"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")

SESSION = "session-wrappers"

PLAN = """- Issue:             #42
- Approval:          granted

### Section B evidence
none

### Section C - the approved plan
1. `src/a.py` - the change

Scope: 1 file.
Risks: none.
"""

LANES_TABLE = """
### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | not applicable - fixture |
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True).stdout


@pytest.fixture
def fake_gh(tmp_path: Path) -> Path:
    """A `gh` that answers only `issue view ... --json body` from a file, so no
    test depends on the network or this host's login."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    body = tmp_path / "issue-body.md"
    body.write_text("the issue body\n")
    gh = bindir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f'  *"--json body"*) cat "{body}" ;;\n'
        "  *) exit 1 ;;\n"
        "esac\n")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return bindir


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "wt"
    r.mkdir()
    git(r, "init", "-q", "-b", "issue-42-a-fixture")
    git(r, "config", "user.email", "t@e.com")
    git(r, "config", "user.name", "t")
    (r / "README.md").write_text("base\n")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "base")
    return r


def helper(repo: Path, bindir: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in {"CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID"}}
    env["CLAUDE_CODE_SESSION_ID"] = SESSION
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    return subprocess.run(["python3", str(HELPER), *args], cwd=repo, capture_output=True,
                          text=True, env=env)


def record(repo: Path) -> Path:
    return repo / "docs" / "flow-runs" / "issue-42.md"


def baseline(repo: Path) -> Path:
    return Path(git(repo, "rev-parse", "--absolute-git-dir").strip()) / "flow-plan-baseline-42"


def plan_file(tmp_path: Path, text: str, name: str = "plan-42.md") -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


# ------------------------------------------------------------------ start

def test_start_runs_reconcile_then_read_issue(repo: Path, fake_gh: Path) -> None:
    proc = helper(repo, fake_gh, "start", "42")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "FLOW_PLAN_RECORD: absent" in proc.stdout
    assert "FLOW_PLAN_RUN: minted" in proc.stdout
    assert "AS_READ: recorded" in proc.stdout
    assert "FLOW_PLAN_START: reconcile=0 read-issue=0" in proc.stdout


def test_start_reports_an_unreadable_issue_and_does_not_succeed(
        repo: Path, tmp_path: Path) -> None:
    broken = tmp_path / "broken-bin"
    broken.mkdir()
    gh = broken / "gh"
    gh.write_text("#!/bin/sh\nexit 1\n")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    proc = helper(repo, broken, "start", "42")
    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert "AS_READ: unresolved" in proc.stdout
    assert "FLOW_PLAN_START: reconcile=0 read-issue=4" in proc.stdout


def load_module():
    spec = importlib.util.spec_from_file_location("plan_record_wrappers", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_failed_reconcile_stops_start_before_the_read(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    module = load_module()
    monkeypatch.setattr(module, "cmd_reconcile", lambda _issue: module.ERROR)

    def never(*_args: object) -> int:
        raise AssertionError("read-issue ran after a failed reconcile")

    monkeypatch.setattr(module, "cmd_read_issue", never)
    assert module.cmd_start("42") == module.ERROR
    assert "FLOW_PLAN_START: reconcile=1 read-issue=not-run" in capsys.readouterr().out


# ------------------------------------------------------------------ approve --plan

def test_approve_plan_writes_the_same_record_the_old_verbs_wrote(
        repo: Path, fake_gh: Path, tmp_path: Path) -> None:
    assert helper(repo, fake_gh, "start", "42").returncode == 0
    proc = helper(repo, fake_gh, "approve", "42", "--plan", str(plan_file(tmp_path, PLAN)))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "FLOW_PLAN_RECORD: baseline stamped" in proc.stdout
    assert baseline(repo).is_file()
    assert (repo / "docs" / "flow-runs" / "issue-42.as-read.md").is_file()
    new = record(repo).read_text()

    # The same run, assembled the old way: begin-run, a hand append, approve.
    old_repo = tmp_path / "old"
    shutil.copytree(repo, old_repo)
    record(old_repo).unlink()
    assert helper(old_repo, fake_gh, "begin-run", "42").returncode == 0
    with record(old_repo).open("a") as fh:
        fh.write(PLAN)
    assert helper(old_repo, fake_gh, "approve", "42").returncode == 0
    assert record(old_repo).read_text() == new
    assert baseline(old_repo).read_text() == baseline(repo).read_text()


@pytest.mark.parametrize(
    ("plan", "said"),
    [
        (PLAN.replace("1. `src/a.py` - the change", "1. src/a.py and some prose"),
         "name no file compliance can read"),
        (PLAN.replace("1. `src/a.py` - the change\n", "the change, unnumbered\n"),
         "Section C has no numbered lines"),
        (PLAN.replace("### Section C - the approved plan", "### The plan"),
         "no `### Section C` heading"),
        ("<!-- flow-run n=9 id=abc -->\n## Run 9\n" + PLAN, "carries its own run marker"),
    ],
    ids=["unparseable-line", "no-numbered-line", "no-section-c", "injected-marker"],
)
def test_a_malformed_plan_is_refused_and_writes_nothing(
        repo: Path, fake_gh: Path, tmp_path: Path, plan: str, said: str) -> None:
    assert helper(repo, fake_gh, "start", "42").returncode == 0
    assert not record(repo).exists()            # precondition: nothing written yet
    proc = helper(repo, fake_gh, "approve", "42", "--plan", str(plan_file(tmp_path, plan)))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert said in proc.stdout and "Nothing was written." in proc.stdout
    assert not record(repo).exists()
    assert not baseline(repo).exists()


def test_a_second_plan_for_the_same_run_is_refused(
        repo: Path, fake_gh: Path, tmp_path: Path) -> None:
    assert helper(repo, fake_gh, "start", "42").returncode == 0
    assert helper(repo, fake_gh, "approve", "42", "--plan",
                  str(plan_file(tmp_path, PLAN))).returncode == 0
    before = record(repo).read_bytes()
    proc = helper(repo, fake_gh, "approve", "42", "--plan",
                  str(plan_file(tmp_path, PLAN, "again.md")))
    assert proc.returncode == 1 and "already has an approved plan" in proc.stdout
    assert record(repo).read_bytes() == before


def test_a_plan_after_salvage_lands_in_the_same_run(
        repo: Path, fake_gh: Path, tmp_path: Path) -> None:
    assert helper(repo, fake_gh, "start", "42").returncode == 0
    assert helper(repo, fake_gh, "begin-run", "42").returncode == 0
    sha = git(repo, "rev-parse", "HEAD").strip()
    assert helper(repo, fake_gh, "declare-salvage", "42", sha, "--reason", "kept").returncode == 0
    proc = helper(repo, fake_gh, "approve", "42", "--plan", str(plan_file(tmp_path, PLAN)))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = record(repo).read_text()
    assert text.count("<!-- flow-run ") == 1 and f"- Salvage:           {sha}" in text


def test_approve_plan_without_a_run_identity_is_refused(
        repo: Path, fake_gh: Path, tmp_path: Path) -> None:
    proc = helper(repo, fake_gh, "approve", "42", "--plan", str(plan_file(tmp_path, PLAN)))
    assert proc.returncode == 1 and "no usable run identity" in proc.stdout
    assert not record(repo).exists()


def test_a_project_with_lanes_refuses_a_plan_that_answers_none(
        repo: Path, fake_gh: Path, tmp_path: Path) -> None:
    lanes = repo / ".claude" / "lanes.md"
    lanes.parent.mkdir()
    lanes.write_text("# Lanes\n\nReviewed: 2026-11-15\n\n| Lane | Values | How it is exercised |\n"
                     "|---|---|---|\n| Checkout | main / worktree | tests |\n")
    assert helper(repo, fake_gh, "start", "42").returncode == 0
    proc = helper(repo, fake_gh, "approve", "42", "--plan", str(plan_file(tmp_path, PLAN)))
    assert proc.returncode == 1 and "no lanes table" in proc.stdout, proc.stdout
    assert not record(repo).exists()
    proc = helper(repo, fake_gh, "approve", "42", "--plan",
                  str(plan_file(tmp_path, PLAN + LANES_TABLE, "with-lanes.md")))
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_plain_approve_still_only_warns_on_a_malformed_line(
        repo: Path, fake_gh: Path) -> None:
    """The delegated drivers keep the old verb and its old behaviour (#1809)."""
    assert helper(repo, fake_gh, "start", "42").returncode == 0
    assert helper(repo, fake_gh, "begin-run", "42").returncode == 0
    with record(repo).open("a") as fh:
        fh.write(PLAN.replace("1. `src/a.py` - the change", "1. src/a.py and some prose"))
    proc = helper(repo, fake_gh, "approve", "42")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "will read UNKNOWN at compliance" in proc.stderr


# ------------------------------------------------------------------ finish

def approved(repo: Path, fake_gh: Path, tmp_path: Path) -> None:
    assert helper(repo, fake_gh, "start", "42").returncode == 0
    assert helper(repo, fake_gh, "approve", "42", "--plan",
                  str(plan_file(tmp_path, PLAN))).returncode == 0


def test_finish_prints_every_verdict_and_fails_on_an_absent_record(
        repo: Path, fake_gh: Path, tmp_path: Path) -> None:
    approved(repo, fake_gh, tmp_path)
    head = git(repo, "rev-parse", "HEAD").strip()   # the record is NOT committed there
    proc = helper(repo, fake_gh, "finish", "42", "--head", head)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "ISSUE_DRIFT: clean" in proc.stdout
    assert re.search(r"^PLAN_COMPLIANCE: ", proc.stdout, re.M)
    assert "FLOW_PLAN_RECORD: absent" in proc.stdout
    assert re.search(r"^FLOW_PLAN_FINISH: drift=0 compliance=\d head-check=1 ", proc.stdout, re.M)


def test_finish_succeeds_only_when_every_inner_verb_does(
        repo: Path, fake_gh: Path, tmp_path: Path) -> None:
    approved(repo, fake_gh, tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("x = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "the change")
    head = git(repo, "rev-parse", "HEAD").strip()
    proc = helper(repo, fake_gh, "finish", "42", "--head", head, "--base", "HEAD~1")
    assert "ISSUE_DRIFT: clean" in proc.stdout
    assert "PLAN_COMPLIANCE: agreement" in proc.stdout, proc.stdout + proc.stderr
    assert "FLOW_PLAN_RECORD: present" in proc.stdout
    assert "FLOW_PLAN_FINISH: drift=0 compliance=0 head-check=0" in proc.stdout
    assert proc.returncode == 0


def test_a_crashing_inner_verb_is_a_failure_and_the_others_still_run(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    module = load_module()

    def boom(*_args: object) -> int:
        raise RuntimeError("inner verb crashed")

    ran: list[str] = []
    monkeypatch.setattr(module, "cmd_drift", boom)
    monkeypatch.setattr(module, "cmd_compliance", lambda *_a: ran.append("compliance") or module.OK)
    monkeypatch.setattr(module, "cmd_head_check", lambda *_a: ran.append("head-check") or module.OK)
    assert module.cmd_finish("42", None, None) == module.ERROR
    out = capsys.readouterr().out
    assert ran == ["compliance", "head-check"]
    assert "`drift` failed unexpectedly; its result is NOT available" in out
    assert "FLOW_PLAN_FINISH: drift=1 compliance=0 head-check=0" in out


@pytest.mark.parametrize(
    ("codes", "expected"),
    [([0, 0, 0], 0), ([0, 3, 0], 3), ([3, 4, 0], 4), ([4, 1, 3], 1), ([0, 2], 2), ([], 1)],
)
def test_worst_of_never_lets_a_milder_code_win(codes: list[int], expected: int) -> None:
    assert load_module().worst(codes) == expected


def test_the_wrappers_dispatch_exactly_the_declared_composites() -> None:
    """The table driver-parity expands by is the table the wrappers run."""
    module = load_module()
    assert module.COMPOSITE_VERBS == {
        "start": ("reconcile", "read-issue"),
        "approve --plan": ("begin-run", "approve"),
        "finish": ("drift", "compliance", "head-check"),
    }


def recorded_calls(module, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    for verb, fn in {"reconcile": "cmd_reconcile", "read-issue": "cmd_read_issue",
                     "begin-run": "cmd_begin_run", "approve": "cmd_approve",
                     "drift": "cmd_drift", "compliance": "cmd_compliance",
                     "head-check": "cmd_head_check"}.items():
        monkeypatch.setattr(module, fn, lambda *_a, _v=verb: calls.append(_v) or module.OK)
    return calls


def test_each_wrapper_runs_exactly_what_its_table_entry_says(
        repo: Path, fake_gh: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Counter-model finding (#1849): `approve --plan` once hard-coded its calls,
    so editing the table changed what parity credited and not what ran. The
    actual calls are recorded, against the real table and an edited one."""
    module = load_module()
    calls = recorded_calls(module, monkeypatch)
    assert module.cmd_start("42") == 0 and module.cmd_finish("42", None, None) == 0
    assert calls == [*module.COMPOSITE_VERBS["start"], *module.COMPOSITE_VERBS["finish"]]

    calls.clear()
    monkeypatch.setitem(module.COMPOSITE_VERBS, "finish", ("head-check", "drift"))
    monkeypatch.setitem(module.COMPOSITE_VERBS, "start", ("read-issue",))
    assert module.cmd_start("42") == 0 and module.cmd_finish("42", None, None) == 0
    assert calls == ["read-issue", "head-check", "drift"]

    # approve --plan: the real helper's begin-run makes the section; record the rest.
    assert helper(repo, fake_gh, "start", "42").returncode == 0
    monkeypatch.chdir(repo)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION)
    real_begin = load_module().cmd_begin_run
    calls.clear()
    monkeypatch.setattr(module, "cmd_begin_run",
                        lambda issue: calls.append("begin-run") or real_begin(issue))
    monkeypatch.setitem(module.COMPOSITE_VERBS, "approve --plan", ("begin-run", "drift", "approve"))
    assert module.cmd_approve_plan("42", str(plan_file(tmp_path, PLAN))) == 0
    assert calls == ["begin-run", "drift", "approve"]


def test_an_unknown_verb_in_the_table_is_an_error_not_a_silent_skip(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    module = load_module()
    recorded_calls(module, monkeypatch)
    monkeypatch.setitem(module.COMPOSITE_VERBS, "finish", ("drift", "no-such-verb"))
    assert module.cmd_finish("42", None, None) == module.ERROR
    assert "names `no-such-verb`, which no subcommand implements" in capsys.readouterr().out


def test_a_plan_over_another_sessions_committed_run_appends_run_two(
        repo: Path, fake_gh: Path, tmp_path: Path) -> None:
    """Project state with an adopted record: an earlier run, committed by another
    session, is kept byte for byte and this run's plan becomes Run 2."""
    assert helper(repo, fake_gh, "start", "42").returncode == 0
    assert helper(repo, fake_gh, "approve", "42", "--plan",
                  str(plan_file(tmp_path, PLAN))).returncode == 0
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run 1")
    run_one = record(repo).read_text()
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    env["CLAUDE_CODE_SESSION_ID"] = "another-session"
    env["PATH"] = f"{fake_gh}{os.pathsep}{env.get('PATH', '')}"
    for args in (["start", "42"], ["approve", "42", "--plan", str(plan_file(tmp_path, PLAN, "p2.md"))]):
        proc = subprocess.run(["python3", str(HELPER), *args], cwd=repo, capture_output=True,
                              text=True, env=env)
        assert proc.returncode == 0, proc.stdout + proc.stderr
    text = record(repo).read_text()
    assert text.startswith(run_one) and "## Run 2" in text
    assert text.count("<!-- flow-run ") == 2
