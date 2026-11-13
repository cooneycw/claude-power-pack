"""#1765 contract cases prepared before product code, with main/held override hooks.

Constructed receipts and owned Git histories exercise the real shell entry point.
The held branch is reference-only; no code is imported from it into this change.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = Path(os.environ.get("CPP_ENROLMENT_TEST_GATE", ROOT / "scripts" / "flow-finish-gate.sh"))
HELPER = Path(os.environ.get("CPP_ENROLMENT_TEST_HELPER", ROOT / "scripts" / "counter-model-receipt.py"))
CASES = json.loads((ROOT / "tests/fixtures/counter_model/enrolment_cases.json").read_text())
pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None
    or shutil.which("make") is None or shutil.which("python3") is None,
    reason="real enrolment integration requires bash, git, make and python3",
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=repo, text=True, stderr=subprocess.PIPE, timeout=20
    ).strip()


def _receipt(branch: str, head: str) -> dict:
    return dict(schema=1, recorded_at="2026-09-20T09:19:05Z", issue="1765", branch=branch,
                head=head, status="ran", implementer="claude/fixture-a", reviewer="codex/fixture-b",
                scope="full", passes=2, counts=dict(accepted=0, rejected=0, deferred=0),
                red_cases=dict(proposed=0, already_covered=0))


@pytest.mark.parametrize("mode", ["gate", "enrolment"])
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_enrolment_answer_contract(tmp_path: Path, case: dict, mode: str) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    branch = case.get("branch", "fixture-branch")
    population = case.get("population", "receipt")
    # Each mode reaches only owned no-op quality targets, never this suite.
    (repo / "Makefile").write_text(
        "lint:\n\t@echo fixture-lint\ntest:\n\t@echo '1 passed in 0.01s'\n"
        "typecheck:\n\t@echo 'Success: no issues found in 1 source file'\nverify:\n\t@echo fixture-verify\n"
    )
    old_head = head = "a" * 40
    if population != "not-git":
        _git(repo, "init", "-q", "-b", branch)
        _git(repo, "config", "user.email", "fixture@example.invalid")
        _git(repo, "config", "user.name", "Fixture")
        _git(repo, "add", "Makefile")
        _git(repo, "commit", "-qm", "older")
        old_head = _git(repo, "rev-parse", "HEAD")
        (repo / "file").write_text("newer\n")
        _git(repo, "add", "file")
        _git(repo, "commit", "-qm", "newer")
        head = _git(repo, "rev-parse", "HEAD")
        assert head != old_head
    if population == "not-git":
        probe = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=repo,
                               capture_output=True, text=True, timeout=20)
        assert probe.returncode != 0, "fixture must be outside every Git repository"
    if "head" in case:
        probe = subprocess.run(["git", "cat-file", "-e", case["head"]], cwd=repo,
                               capture_output=True, text=True, timeout=20)
        assert probe.returncode != 0, "fixture head must be absent from this full repository"
    receipts = repo / "docs/measurements/counter-model"
    filename = case.get("filename", "99-latest.json")
    if population == "absent":
        assert not receipts.exists()
    else:
        receipts.mkdir(parents=True)
    if population == "receipt":
        record = _receipt(branch, case.get("head", head))
        if "passes" in case:
            record["passes"] = case["passes"]
        if case.get("omit_passes"):
            del record["passes"]
            assert "passes" not in record
        if "ruling" in case:
            record["escalation"] = dict(ruled_by="fixture authority", reference="fixture ruling",
                                         raised_cap=case["ruling"])
            record["extra_passes_reason"] = "fixture accepted findings required another pass"
        elif isinstance(record.get("passes"), int) and record["passes"] > 3:
            assert "escalation" not in record, "negative fixture has no ruling"
        if "direction" in case:
            record["direction"] = case["direction"]
        if case.get("scope", "full") is None:
            del record["scope"]
            assert "scope" not in record
        if "skip" in case:
            record = {key: value for key, value in record.items() if key not in ("passes", "counts", "red_cases")}
            record.update(status="skipped", reviewer=None, skip_reason=case["skip"])
        if case.get("nested_skip"):
            assert record["status"] == "ran"
            record = dict(metadata=dict(status="skipped", skip_reason="codex-absent"), **record)
        if case.get("older"):
            older = _receipt(branch, old_head)
            assert older["head"] != head
            (receipts / "00-older.json").write_text(json.dumps(older, indent=2))
        text = json.dumps(record, indent=2, ensure_ascii=case.get("ascii", True))
        if case.get("format") == "two-space":
            text = text.replace('"passes": 5', '"passes":  5')
            assert '"passes":  5' in text
        elif case.get("format") == "trailing-space":
            text = text.replace('"passes": 5,', '"passes": 5  ,')
            assert '"passes": 5  ,' in text
        if case.get("raw") == "truncated":
            text = '{"status": "ran",'
            with pytest.raises(json.JSONDecodeError):
                json.loads(text)
        elif case.get("raw") == "array":
            text = "[]"
            assert not isinstance(json.loads(text), dict)
            assert "\n" in filename or "\x1f" in filename
        (receipts / filename).write_text(text + "\n")
        if case.get("foreign_invalid"):
            foreign = _receipt("another-branch", head)
            del foreign["passes"]
            assert foreign["branch"] != branch and "passes" not in foreign
            (receipts / "foreign.json").write_text(json.dumps(foreign, indent=2))
    helper = HELPER
    if case.get("helper") == "missing":
        helper = tmp_path / "absent-helper.py"
        assert not helper.exists()
    elif case.get("helper") == "blind":
        helper = tmp_path / "blind-helper.py"
        helper.write_text("raise SystemExit(0)\n")
        probe = subprocess.run(["python3", str(helper)], capture_output=True, text=True, timeout=20)
        assert probe.returncode == 0 and not probe.stdout, "fixture helper must be blind"
    elif case.get("helper") in (
        "crash", "empty-declared", "undeclared", "multiline", "blank-line",
        "mismatched-code", "escalated-code-receipt-line",
    ):
        helper = tmp_path / "bad-helper.py"
        bodies = {
            "crash": "raise RuntimeError('fixture crash')\n",
            "blank-line": "print('FLOW_FINISH_GATE_COUNTER_MODEL: ')\nraise SystemExit(10)\n",
            "mismatched-code": "print('FLOW_FINISH_GATE_COUNTER_MODEL: missing: no receipt')\nraise SystemExit(10)\n",
            "escalated-code-receipt-line": (
                "print('FLOW_FINISH_GATE_COUNTER_MODEL: receipt: fake')\nraise SystemExit(11)\n"
            ),
            "empty-declared": "raise SystemExit(10)\n",
            "undeclared": "print('FLOW_FINISH_GATE_COUNTER_MODEL: receipt: fake')\nraise SystemExit(99)\n",
            "multiline": "print('FLOW_FINISH_GATE_COUNTER_MODEL: receipt: fake\\nextra line')\nraise SystemExit(10)\n",
        }
        helper.write_text(bodies[case["helper"]])
        probe = subprocess.run(["python3", str(helper)], capture_output=True, text=True, timeout=20)
        assert probe.returncode in (1, 10, 11, 99), "fixture produces a rejected private answer"
    env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    env.update(FLOW_GATE_CPP_DIR="", CM_RECEIPT_HELPER=str(helper),
               CPP_COORDINATION_ADMISSION_FILE=str(tmp_path / "admission-off"))
    args = ["bash", str(GATE)]
    if mode == "enrolment":
        args += ["--enrolment-only", "--branch", branch]
    result = subprocess.run(args, cwd=repo, env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == case[mode], result.stdout + result.stderr
    markers = [line for line in result.stdout.splitlines() if line.startswith("FLOW_FINISH_GATE_COUNTER_MODEL:")]
    assert len(markers) == 1, result.stdout
    assert markers[0].startswith(f"FLOW_FINISH_GATE_COUNTER_MODEL: {case['state']}:"), result.stdout
    if case.get("names_file"):
        assert filename in result.stdout + result.stderr
    if case.get("raw") == "array":
        assert "hostile-" in result.stdout + result.stderr, "unreadable filename must be named safely"


@pytest.mark.parametrize("enrolled", [False, True])
@pytest.mark.parametrize("mode", ["gate", "enrolment"])
def test_only_an_unenrolled_repository_works_without_python(tmp_path: Path, enrolled: bool, mode: str) -> None:
    from tests.test_flow_finish_gate import _enrolled_repo

    repo = _enrolled_repo(tmp_path)
    if not enrolled:
        shutil.rmtree(repo / "docs/measurements/counter-model")
    bindir = tmp_path / "bin-without-python"
    bindir.mkdir()
    for name in ("bash", "git", "sed", "head", "grep", "awk", "id", "dirname", "cat", "mktemp",
                 "tee", "make", "env", "rm", "wc", "sort", "cut", "tr", "touch", "find", "date", "tail"):
        binary = shutil.which(name)
        if binary is None:
            pytest.skip(f"fixture needs {name}")
        (bindir / name).symlink_to(binary)
    assert shutil.which("python3", path=str(bindir)) is None, "fixture PATH has no Python"
    env = {"PATH": str(bindir), "HOME": str(tmp_path), "FLOW_GATE_CPP_DIR": "",
           "CM_RECEIPT_HELPER": str(HELPER), "CPP_COORDINATION_ADMISSION_FILE": str(tmp_path / "off")}
    args = ["bash", str(GATE)]
    if mode == "enrolment":
        args += ["--enrolment-only", "--branch", "master"]
    result = subprocess.run(args, cwd=repo, env=env, capture_output=True, text=True, timeout=30)
    expected = 1 if enrolled or mode == "enrolment" else 4
    assert result.returncode == expected, result.stdout + result.stderr
    state = "unknown" if enrolled else "not-enrolled"
    assert f"FLOW_FINISH_GATE_COUNTER_MODEL: {state}:" in result.stdout


@pytest.mark.parametrize("mode", ["gate", "enrolment"])
@pytest.mark.parametrize("unruled", [False, True])
def test_tied_heads_cannot_hide_an_escalation_or_an_invalid_review(tmp_path: Path, mode: str, unruled: bool) -> None:
    from tests.test_flow_finish_gate import _diamond_repo, _named_receipt

    repo, main, side = _diamond_repo(tmp_path)
    first = "2026-01-01T000000Z-issue-1765.json"
    _named_receipt(repo, first, main, scope="full")
    _named_receipt(repo, "2026-01-02T000000Z-issue-1765.json", side, scope="full")
    path = repo / "docs/measurements/counter-model" / first
    receipt = json.loads(path.read_text())
    receipt["passes"] = 4
    if not unruled:
        receipt.update(escalation=dict(ruled_by="fixture authority", reference="fixture ruling", raised_cap=4),
                       extra_passes_reason="fixture needs four passes")
    else:
        assert "escalation" not in receipt
    path.write_text(json.dumps(receipt, indent=2))
    env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    env.update(FLOW_GATE_CPP_DIR="", CM_RECEIPT_HELPER=str(HELPER),
               CPP_COORDINATION_ADMISSION_FILE=str(tmp_path / "off"))
    args = ["bash", str(GATE)]
    if mode == "enrolment":
        args += ["--enrolment-only", "--branch", "master"]
    result = subprocess.run(args, cwd=repo, env=env, capture_output=True, text=True, timeout=30)
    expected = 1 if unruled else 0 if mode == "enrolment" else 4
    assert result.returncode == expected, result.stdout + result.stderr
    state = "unknown" if unruled else "escalated"
    assert f"FLOW_FINISH_GATE_COUNTER_MODEL: {state}:" in result.stdout
