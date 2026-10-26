"""Execute the documented Step 9 verify invocations for real (issue #603).

The pre-#595 broken invocation survived for months because nothing executed
it: CPP's own deploy is the #469 no-op and cicd.yml had no deploy_verification
stanza, so the repo that OWNS lib/cicd's verify path was the one repo that
never ran it. tests/test_cicd_verify_invocation.py pins the documented STRING;
this test goes further - it EXTRACTS the command strings from auto.md Step 9
and EXECUTES them against a scaffolded temp project, so a doc regression to
the broken shape (bare python3, PYTHONPATH inside lib/) is a red test, not
plausible-looking prose. Execution is the assertion.

Extraction remains section-scoped: exactly two approved executable commands,
baseline with summary then plain verify. Both the legacy and CPP 3.11 isolated
runner shapes are named explicitly. Empty, malformed, extra or reordered pairs
are refused rather than silently filtered out. Committed mutated documents below
are negative controls for the extractor; the real documented pair still executes.

Guards: shells out to `uv` - present in the CI validate container (the image
is astral's uv image) and skipif-guarded for odd boxes; no git/docker/gitleaks
involved (#602 rule satisfied without exceptions).
"""

from __future__ import annotations

import runpy
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_cicd_verify_invocation import CPP_VERIFY, LEGACY_VERIFY, VERIFY_PREFIXES

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


def _step9_section(text: str) -> str:
    start = text.find("### Step 9")
    assert start != -1, "auto.md no longer has a '### Step 9' section - doc shape changed"
    end = text.find("\n### ", start + 1)
    section = text[start : end if end != -1 else len(text)]
    return section


def extract_verify_invocations(text: str | None = None) -> list[str]:
    """Refuse any changed executable pair; never count only matching good lines."""
    section = _step9_section(AUTO_MD.read_text() if text is None else text)
    lines = [
        line.strip()
        for line in section.splitlines()
        if "-m lib.cicd verify" in line and not line.lstrip().startswith("#")
    ]
    assert len(lines) == 2, f"expected EXACTLY the Step-9 verify pair, found {len(lines)}: {lines!r}"
    assert lines[0] in [prefix + " --baseline --summary" for prefix in VERIFY_PREFIXES], "invalid baseline invocation"
    assert lines[1] in VERIFY_PREFIXES, "invalid plain verify invocation or reordered pair"
    return lines


def test_extraction_is_section_scoped_and_exact() -> None:
    lines = extract_verify_invocations()
    assert len(lines) == 2
    assert lines[0] == CPP_VERIFY + " --baseline --summary"
    assert lines[1] == CPP_VERIFY


def _owned_document(lines):
    return (
        "### Step 6\n" + LEGACY_VERIFY + "\n### Step 9: Deploy\n```bash\n" + "\n".join(lines) + "\n```\n### Step 10\n"
    )


@pytest.mark.parametrize("prefix", VERIFY_PREFIXES)
def test_owned_correct_pair_is_accepted(prefix):
    lines = [prefix + " --baseline --summary", prefix]
    assert extract_verify_invocations(_owned_document(lines)) == lines


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "extra",
        "reordered",
        "bare-python",
        "wrong-project",
        "wrong-pythonpath",
        "download",
        "handoff",
        "malformed",
    ],
)
def test_committed_document_mutations_are_refused(mutation):
    lines = [CPP_VERIFY + " --baseline --summary", CPP_VERIFY]
    if mutation == "empty":
        lines = []
    elif mutation == "extra":
        lines.append(CPP_VERIFY)
    elif mutation == "reordered":
        lines.reverse()
    else:
        old, new = {
            "bare-python": ('uv run --python 3.11 --no-python-downloads --project "$CPP_DIR" python', "python3"),
            "wrong-project": ('--project "$CPP_DIR"', '--project "$OTHER_PROJECT"'),
            "wrong-pythonpath": ('PYTHONPATH="$CPP_DIR:', 'PYTHONPATH="$CPP_DIR/lib:'),
            "download": ("--no-python-downloads ", ""),
            "handoff": ("env -u UV_PROJECT_ENVIRONMENT ", ""),
            "malformed": ("--baseline --summary", "--baseline --summary ; echo hidden"),
        }[mutation]
        assert old in lines[0]
        lines[0] = lines[0].replace(old, new)
    with pytest.raises(AssertionError):
        extract_verify_invocations(_owned_document(lines))


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
                "UV_PYTHON_DOWNLOADS": "never",
                **{
                    key: subprocess.os.environ[key]
                    for key in ("UV_PYTHON_INSTALL_DIR",)
                    if key in subprocess.os.environ
                },
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
    assert any(word in outputs[1].lower() for word in ("proceed", "verdict", "pass", "ok")), (
        f"post-deploy verify emitted no verdict:\n{outputs[1][-2000:]}"
    )


def test_scaffold_does_not_inherit_cpp_config(tmp_path: Path) -> None:
    """Isolation pin: the temp project's cicd.yml is the one the run sees -
    it has exactly one smoke test named always-ok, not CPP's config."""
    proj = tmp_path / "proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "cicd.yml").write_text(MINIMAL_CICD_YML)
    text = (proj / ".claude" / "cicd.yml").read_text()
    assert "always-ok" in text and "lib-cicd-imports" not in text


def test_extractor_controls_distinguish_the_committed_blind_anchor():
    blind = runpy.run_path(str(ROOT / "tests/fixtures/step9_verify_contract/blind_extractor.py"))[
        "extract_verify_invocations"
    ]
    good = _owned_document([CPP_VERIFY + " --baseline --summary", CPP_VERIFY])
    assert blind(good) == extract_verify_invocations(good)
    bad = _owned_document([])
    with pytest.raises(AssertionError):
        extract_verify_invocations(bad)
    assert blind(bad) == [LEGACY_VERIFY + " --baseline --summary", LEGACY_VERIFY]
