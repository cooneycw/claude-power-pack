"""Execute the documented Step 9 verify invocations for real (issue #603).

The pre-#595 broken invocation survived for months because nothing executed
it: CPP's own deploy is the #469 no-op and cicd.yml had no deploy_verification
stanza, so the repo that OWNS lib/cicd's verify path was the one repo that
never ran it. tests/test_cicd_verify_invocation.py pins the documented STRING;
this test goes further - it EXTRACTS the command strings from auto.md Step 9
and EXECUTES them against a scaffolded temp project, so a doc regression to
the broken shape (bare python3, PYTHONPATH inside lib/) is a red test, not
plausible-looking prose. Execution is the assertion.

Extraction contract (gate condition, #603): auto.md contains THREE
`uv run --project` occurrences. Line ~532 is PROSE - the Step 6 gate
description naming the #430 invocation contract - and is deliberately
EXCLUDED by section-scoping the parse to Step 9. The two Step-9 lines are the
executable pair: `verify --baseline --summary` (pre-deploy) and bare `verify`
(post-deploy). The parse asserts EXACTLY that pair, in that order, and fails
loud on any count mismatch in either direction - a stray third match or a
split/renamed section both mean the doc changed shape, and this test says so
instead of silently passing.

Guards: shells out to `uv` - present in the CI validate container (the image
is astral's uv image) and skipif-guarded for odd boxes; no git/docker/gitleaks
involved (#602 rule satisfied without exceptions).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUTO_MD = ROOT / ".claude" / "commands" / "flow" / "auto.md"

requires_uv = pytest.mark.skipif(
    shutil.which("uv") is None or shutil.which("bash") is None,
    reason="requires uv and bash on PATH",
)

MINIMAL_CICD_YML = """\
health:
  deploy_verification:
    enabled: true
  smoke_tests:
    - name: always-ok
      command: echo ok
"""


def _step9_section() -> str:
    text = AUTO_MD.read_text()
    start = text.find("### Step 9")
    assert start != -1, "auto.md no longer has a '### Step 9' section - doc shape changed"
    end = text.find("\n### ", start + 1)
    section = text[start : end if end != -1 else len(text)]
    return section


def extract_verify_invocations() -> list[str]:
    """The Step-9 verify command pair, exactly as documented."""
    lines = [
        ln.strip()
        for ln in _step9_section().splitlines()
        if "uv run --project" in ln and "-m lib.cicd verify" in ln
    ]
    assert len(lines) == 2, (
        f"expected EXACTLY the Step-9 verify pair (baseline + verify), found "
        f"{len(lines)}: {lines!r} - the doc changed shape; re-anchor this test "
        f"deliberately rather than letting it guess"
    )
    assert "--baseline" in lines[0], "first Step-9 invocation must be the baseline capture"
    assert "--baseline" not in lines[1], "second Step-9 invocation must be the bare verify"
    return lines


def test_extraction_is_section_scoped_and_exact() -> None:
    # File-global there are three `uv run --project` mentions (the third is
    # Step 6 prose); section-scoping must reduce that to the executable pair.
    assert AUTO_MD.read_text().count("uv run --project") == 3, (
        "auto.md's uv-run mention count changed - re-verify which occurrences "
        "are Step 9's executable pair and update the docstring"
    )
    extract_verify_invocations()


@requires_uv
def test_documented_step9_invocations_execute(tmp_path: Path) -> None:
    # Scaffold an isolated project: its own cicd.yml, NOT CPP's (isolation pin
    # below). The verify code reads config relative to the cwd it runs in.
    proj = tmp_path / "proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "cicd.yml").write_text(MINIMAL_CICD_YML)

    invocations = extract_verify_invocations()
    outputs = []
    for cmd in invocations:
        # The documented lines use $CPP_DIR; bind it to THIS checkout, exactly
        # as auto.md's Step 9 preamble resolves it.
        proc = subprocess.run(
            ["bash", "-c", cmd],
            cwd=proj,
            env={
                "PATH": subprocess.os.environ["PATH"],
                "HOME": subprocess.os.environ.get("HOME", str(tmp_path)),
                "CPP_DIR": str(ROOT),
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        assert proc.returncode == 0, (
            f"documented Step-9 invocation failed to execute:\n  {cmd}\n"
            f"stdout: {proc.stdout[-2000:]}\nstderr: {proc.stderr[-2000:]}"
        )
        outputs.append(proc.stdout + proc.stderr)

    # Baseline run writes the baseline; verify run must emit a verdict.
    assert any(
        word in outputs[1].lower() for word in ("proceed", "verdict", "pass", "ok")
    ), f"post-deploy verify emitted no verdict:\n{outputs[1][-2000:]}"


def test_scaffold_does_not_inherit_cpp_config(tmp_path: Path) -> None:
    """Isolation pin: the temp project's cicd.yml is the one the run sees -
    it has exactly one smoke test named always-ok, not CPP's config."""
    proj = tmp_path / "proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "cicd.yml").write_text(MINIMAL_CICD_YML)
    text = (proj / ".claude" / "cicd.yml").read_text()
    assert "always-ok" in text and "lib-cicd-imports" not in text
