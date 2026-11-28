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
    or shutil.which("bash") is None or shutil.which("python3") is None or shutil.which("tee") is None,
    reason="public review entry needs Git, Make, Bash, Python and tee",
)


def observe(case, temporary, helper=HELPER, *, qualification_only=False):
    """A real helper entry, an owned Git origin, and an observable stub reviewer."""
    import subprocess

    spec = json.loads((case / "case.json").read_text())
    work, environment = _fixture(temporary)
    calls = temporary / "qualification-calls"
    environment.update(CM_PYTHON=sys.executable, CI_SHAPE_CALLS=str(calls),
                       CI_SHAPE_STUB_STATE=spec["state"], CI_SHAPE_STUB_EXIT=str(spec["exit"]))
    if not spec.get("identity_error"):
        (work / "pyproject.toml").write_text('[project]\nname = "' + spec["project"] + '"\n')
    if spec.get("lookalike") or spec.get("identity_error"):
        for relative in ("lib/ci_shape_check.py", "scripts/ci-shape-check.py"):
            path = work / relative
            path.parent.mkdir(exist_ok=True)
            path.write_text("# Owned identity fixture; never executed.\n")
    (work / "Makefile").write_text(
        ".PHONY: ci-shape-check\nci-shape-check:\n"
        '\t@printf "%s\\n" ci-shape-check >> "$(CI_SHAPE_CALLS)"\n'
        '\t@if [ "$(CI_SHAPE_STUB_STATE)" = DUPLICATE ]; then '
        'printf "CI_SHAPE: GOOD: fixture\\nCI_SHAPE: GOOD: fixture\\n"; '
        'elif [ "$(CI_SHAPE_STUB_STATE)" != SILENT ]; then '
        'printf "CI_SHAPE: %s: tier=local; controlled consumer input\\n" "$(CI_SHAPE_STUB_STATE)"; fi\n'
        '\t@exit "$(CI_SHAPE_STUB_EXIT)"\n')
    _git("add", "-A", cwd=work, env=environment)
    _git("commit", "-qm", "declared subject and controlled qualification", cwd=work, env=environment)
    assert not calls.exists()
    assert Path(shutil.which("codex", path=environment["PATH"])) == temporary / "stub/codex"
    # Tripwires for expensive work outside the controlled Make entry. Ordinary
    # consumers must not stage/sync tools or launch an image before returning.
    work_calls = temporary / "unexpected-work"
    environment["CI_SHAPE_WORK_CALLS"] = str(work_calls)
    for tool in ("uv", "docker", "podman"):
        probe = temporary / "stub" / tool
        probe.write_text('#!/bin/sh\nprintf "%s\\n" "' + tool + '" >> "$CI_SHAPE_WORK_CALLS"\nexit 97\n')
        probe.chmod(0o755)
    transcript = temporary / "transcript.md"
    arguments = ["--qualify-only"] if qualification_only else ["--base", "origin/main", "--transcript", str(transcript)]
    answer = subprocess.run(["bash", str(helper), *arguments],
                            cwd=work, env=environment, capture_output=True, text=True, timeout=45)
    try:
        assert not work_calls.exists(), "consumer staged/synced/launched outside qualification"
        reviewer_calls = _calls(environment)
        if qualification_only:
            assert reviewer_calls == [], "qualification-only entry probed/launched Codex"
        return answer, spec, reviewer_calls, calls.read_text().splitlines() if calls.exists() else []
    finally:
        _cleanup_stream(answer.stdout)


def exercise(case, temporary, helper=HELPER, *, qualification_only=False):
    answer, spec, reviewer_calls, qualification_calls = observe(
        case, temporary, helper, qualification_only=qualification_only)
    if spec["project"] != "claude-power-pack":
        assert qualification_calls == [], "ordinary neighbor invoked CPP qualification"
        assert answer.returncode == 0 and (qualification_only or "exec" in reviewer_calls), (
            answer.stdout + answer.stderr)
    elif spec.get("admit", spec["state"] == "GOOD"):
        assert qualification_calls == ["ci-shape-check"], "CPP qualification did not run exactly once"
        assert answer.returncode == 0 and (qualification_only or "exec" in reviewer_calls), (
            answer.stdout + answer.stderr)
    else:
        assert "exec" not in reviewer_calls, "reviewer invoked despite " + spec["state"]
        assert qualification_calls == ([] if spec.get("identity_error") else ["ci-shape-check"]), (
            "CPP qualification/identity refusal was not examined")
        assert answer.returncode == 1 and "CODEX_REVIEW: blocked" in answer.stdout + answer.stderr
    return answer


@pytest.mark.parametrize("case", sorted(p.name for p in CASES.iterdir() if (p / "case.json").is_file()))
@pytest.mark.parametrize("qualification_only", [False, True])
def test_public_entry_qualification_before_review(tmp_path, case, qualification_only):
    exercise(CASES / case, tmp_path, qualification_only=qualification_only)
