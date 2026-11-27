"""The public review helper must qualify CPP before invoking its reviewer."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from tests.test_codex_review_run import HELPER, _calls, _cleanup_stream, _fixture, _git

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "controls/ci-shape-review-entry/cases"
pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("make") is None
    or shutil.which("bash") is None or shutil.which("python3") is None,
    reason="public review entry needs Git, Make, Bash and Python",
)


def exercise(case, temporary, helper=HELPER):
    """A real helper entry, an owned Git origin, and an observable stub reviewer."""
    import subprocess

    spec = json.loads((case / "case.json").read_text())
    work, environment = _fixture(temporary)
    calls = temporary / "qualification-calls"
    environment.update(CM_PYTHON=sys.executable, CI_SHAPE_CALLS=str(calls),
                       CI_SHAPE_STUB_STATE=spec["state"], CI_SHAPE_STUB_EXIT=str(spec["exit"]))
    (work / "pyproject.toml").write_text('[project]\nname = "' + spec["project"] + '"\n')
    (work / "Makefile").write_text(
        ".PHONY: ci-shape-check\nci-shape-check:\n"
        '\t@printf "%s\\n" ci-shape-check >> "$(CI_SHAPE_CALLS)"\n'
        '\t@printf "CI_SHAPE: %s: tier=local; controlled consumer input\\n" "$(CI_SHAPE_STUB_STATE)"\n'
        '\t@exit "$(CI_SHAPE_STUB_EXIT)"\n')
    _git("add", "pyproject.toml", "Makefile", cwd=work, env=environment)
    _git("commit", "-qm", "declared subject and controlled qualification", cwd=work, env=environment)
    assert not calls.exists()
    assert Path(shutil.which("codex", path=environment["PATH"])) == temporary / "stub/codex"
    transcript = temporary / "transcript.md"
    answer = subprocess.run(["bash", str(helper), "--base", "origin/main", "--transcript", str(transcript)],
                            cwd=work, env=environment, capture_output=True, text=True, timeout=45)
    try:
        reviewer_calls = _calls(environment)
        qualification_calls = calls.read_text().splitlines() if calls.exists() else []
        if spec["project"] != "claude-power-pack":
            assert qualification_calls == [], "ordinary neighbor invoked CPP qualification"
            assert answer.returncode == 0 and "exec" in reviewer_calls, answer.stdout + answer.stderr
        elif spec["state"] == "GOOD":
            assert qualification_calls == ["ci-shape-check"], "CPP qualification did not run exactly once"
            assert answer.returncode == 0 and "exec" in reviewer_calls, answer.stdout + answer.stderr
        else:
            assert "exec" not in reviewer_calls, "reviewer invoked despite " + spec["state"]
            assert qualification_calls == ["ci-shape-check"], "CPP qualification was not examined"
            assert answer.returncode == 1 and "CODEX_REVIEW: blocked" in answer.stdout + answer.stderr
        return answer
    finally:
        _cleanup_stream(answer.stdout)


@pytest.mark.parametrize("case", ["good", "bad", "unknown", "neighbor"])
def test_public_entry_qualification_before_review(tmp_path, case):
    exercise(CASES / case, tmp_path)
