"""Controls for `scripts/tools-version-check.sh` (issue #1029, specimen 3).

`make tools-check` asks `command -v`, which ANY version satisfies identically,
so a host on shellcheck 0.9.0 got the same green as CI's pinned 0.10.0 and the
two gates could disagree with nothing saying why. The controls are therefore:

  POSITIVE  a tool whose reported version differs from the pin reports
            `mismatch` - and names both numbers.
  NEGATIVE  a tool whose version equals the pin reports `ok`. Without it, a
            comparison that silently matched nothing would look identical.
  BLIND     a pin that cannot be parsed reports `unknown`, NEVER `ok`. A version
            checker that stops finding its pins and keeps printing green is the
            failure this issue is about, reproduced inside its own remedy.

The tools are supplied as PATH shims, so no host binary is touched and the same
verdicts are produced in CI - where none of the three real tools may exist.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tools-version-check.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)

#: The utilities the script itself calls. The sandbox PATH carries exactly these
#: and nothing else, so "absent" means absent rather than "we forgot to link it".
SANDBOX_UTILITIES = ("bash", "sh", "readlink", "dirname", "grep", "sed", "head", "awk")

MAKEFILE_PINS = """\
SHELLCHECK_IMAGE := koalaman/shellcheck-alpine:v{shellcheck}@sha256:deadbeef
GITLEAKS_IMAGE := zricethezav/gitleaks:v{gitleaks}@sha256:cafebabe
"""

JQ_STAGER_PIN = '''\
JQ_URL = "https://github.com/jqlang/jq/releases/download/jq-{jq}/jq-linux-amd64"
'''

#: Each shim prints its version in the SHAPE the real tool uses, so the parsing
#: this instrument depends on is what the tests exercise.
SHIM_BODIES = {
    "shellcheck": "#!/bin/sh\nprintf 'ShellCheck - shell script analysis tool\\nversion: %s\\n' {version}\n",
    "gitleaks": "#!/bin/sh\nprintf 'v%s\\n' {version}\n",
    "jq": "#!/bin/sh\nprintf 'jq-%s\\n' {version}\n",
}


@pytest.fixture
def sandbox(tmp_path: Path):
    """A pin root and an isolated PATH holding only what the script needs."""
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name in SANDBOX_UTILITIES:
        real = shutil.which(name)
        if real is None:
            pytest.skip(f"sandbox PATH needs {name}")
        (bindir / name).symlink_to(real)
    return root, bindir


def _write_pins(
    root: Path,
    *,
    shellcheck: str = "0.10.0",
    gitleaks: str = "8.30.1",
    jq: str = "1.7.1",
    makefile: str | None = None,
) -> None:
    body = (
        makefile
        if makefile is not None
        else MAKEFILE_PINS.format(shellcheck=shellcheck, gitleaks=gitleaks)
    )
    (root / "Makefile").write_text(body, encoding="utf-8")
    (root / "scripts" / "ci-stage-jq.py").write_text(
        JQ_STAGER_PIN.format(jq=jq), encoding="utf-8"
    )


def _install_shims(bindir: Path, **versions: str) -> None:
    for name, version in versions.items():
        shim = bindir / name
        shim.write_text(SHIM_BODIES[name].format(version=version), encoding="utf-8")
        shim.chmod(0o755)


def _run(root: Path, bindir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # ASSERT THE ABSENCE YOU BUILT (CLAUDE.md core directive, issue #697). This
    # replaces PATH wholesale, and a fixture whose sandbox silently still saw the
    # host's real tools would produce the same "no findings" output as a working
    # one - the vacuous-test shape. `scripts/check-negative-fixture-preconditions.py`
    # reports exactly this function without these two lines.
    assert shutil.which("grep", path=str(bindir)) is not None, (
        "the sandbox PATH must carry the utilities the script itself calls"
    )
    for tool in ("shellcheck", "gitleaks", "jq"):
        on_host = shutil.which(tool)
        in_sandbox = shutil.which(tool, path=str(bindir))
        if in_sandbox is not None:
            assert Path(in_sandbox).parent == bindir, (
                f"{tool} must resolve to the fixture shim, not {on_host}"
            )
    env = dict(os.environ)
    env["PATH"] = str(bindir)
    env["CPP_TOOLS_VERSION_ROOT"] = str(root)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _json(root: Path, bindir: Path) -> dict:
    result = _run(root, bindir, "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _state(payload: dict, name: str) -> dict:
    return next(entry for entry in payload["tools"] if entry["name"] == name)


def test_negative_control_matching_versions_report_ok(sandbox) -> None:
    """The half that separates a working comparison from one matching nothing."""
    root, bindir = sandbox
    _write_pins(root)
    _install_shims(bindir, shellcheck="0.10.0", gitleaks="8.30.1", jq="1.7.1")

    payload = _json(root, bindir)
    assert payload["verdict"] == "ok"
    for name in ("shellcheck", "gitleaks", "jq"):
        assert _state(payload, name)["state"] == "match"

    assert _run(root, bindir, "--quiet").stdout.strip() == ""


def test_positive_control_a_divergent_version_reports_mismatch(sandbox) -> None:
    """The specimen: present, so `tools-check` says ok; not the pinned version."""
    root, bindir = sandbox
    _write_pins(root)
    _install_shims(bindir, shellcheck="0.9.0", gitleaks="8.30.1", jq="1.7.1")

    payload = _json(root, bindir)
    assert payload["verdict"] == "mismatch"
    entry = _state(payload, "shellcheck")
    assert entry["state"] == "mismatch"
    assert entry["pinned"] == "0.10.0"
    assert entry["installed"] == "0.9.0"

    quiet = _run(root, bindir, "--quiet").stdout
    assert "shellcheck 0.9.0 != pinned 0.10.0" in quiet, (
        "both numbers must appear; 'a tool differs' is not actionable"
    )


def test_blind_control_an_unparseable_pin_is_unknown_never_ok(sandbox) -> None:
    """A checker that loses its pins and keeps printing green is the defect."""
    root, bindir = sandbox
    _write_pins(root, makefile="# the pin variables were renamed\n")
    _install_shims(bindir, shellcheck="0.10.0", gitleaks="8.30.1", jq="1.7.1")

    payload = _json(root, bindir)
    assert payload["verdict"] == "unknown"
    assert _state(payload, "shellcheck")["state"] == "unknown-pin"
    assert _state(payload, "shellcheck")["pinned"] is None
    assert _state(payload, "jq")["state"] == "match", (
        "an unreadable pin for one tool must not destroy another's comparison"
    )

    report = _run(root, bindir).stdout
    assert "TOOLS_VERSION: unknown" in report
    assert "DID NOT HAPPEN" in report


def test_blind_control_unknown_outranks_mismatch(sandbox) -> None:
    """An unmade comparison must never be summarised by a made one.

    With a mismatch present, reporting `mismatch` would be true but would hide
    that a different tool was never compared at all - and the aggregate is what
    a scripted caller reads.
    """
    root, bindir = sandbox
    _write_pins(root, makefile="GITLEAKS_IMAGE := zricethezav/gitleaks:v8.30.1@sha256:x\n")
    _install_shims(bindir, shellcheck="0.9.0", gitleaks="8.30.1", jq="1.7.1")

    payload = _json(root, bindir)
    assert _state(payload, "shellcheck")["state"] == "unknown-pin"
    assert payload["verdict"] == "unknown"


def test_an_absent_tool_is_absent_not_ok_and_not_a_mismatch(sandbox) -> None:
    """`tools-check` owns absence; this must not double-report it as divergence."""
    root, bindir = sandbox
    _write_pins(root)
    _install_shims(bindir, gitleaks="8.30.1", jq="1.7.1")
    assert shutil.which("shellcheck", path=str(bindir)) is None, (
        "the fixture must actually lack shellcheck, or this asserts nothing"
    )

    payload = _json(root, bindir)
    assert payload["verdict"] == "absent"
    entry = _state(payload, "shellcheck")
    assert entry["state"] == "absent"
    assert entry["installed"] is None
    assert entry["pinned"] == "0.10.0", "the pin is what someone installing it needs"


def test_mismatch_outranks_absent(sandbox) -> None:
    """Absence is already loudly reported elsewhere; divergence is the new fact."""
    root, bindir = sandbox
    _write_pins(root)
    _install_shims(bindir, gitleaks="8.30.1", jq="9.9.9")

    payload = _json(root, bindir)
    assert _state(payload, "shellcheck")["state"] == "absent"
    assert _state(payload, "jq")["state"] == "mismatch"
    assert payload["verdict"] == "mismatch"


def test_an_unparseable_installed_version_is_unknown_not_a_match(sandbox) -> None:
    """A tool whose version output changed shape was not compared."""
    root, bindir = sandbox
    _write_pins(root)
    _install_shims(bindir, gitleaks="8.30.1", jq="1.7.1")
    mute = bindir / "shellcheck"
    mute.write_text("#!/bin/sh\nprintf 'no version here\\n'\n", encoding="utf-8")
    mute.chmod(0o755)

    payload = _json(root, bindir)
    assert _state(payload, "shellcheck")["state"] == "unknown-installed"
    assert payload["verdict"] == "unknown"


def test_pins_are_read_from_the_declaring_files_not_restated(sandbox) -> None:
    """Change the declaration, and the instrument must follow it.

    This is what makes "the pin already exists, it is not re-declared here" a
    checkable property rather than a claim in a comment: a hard-coded constant
    would keep reporting the old number.
    """
    root, bindir = sandbox
    _write_pins(root, shellcheck="0.11.0", gitleaks="9.0.0", jq="2.0.0")
    _install_shims(bindir, shellcheck="0.11.0", gitleaks="9.0.0", jq="2.0.0")

    payload = _json(root, bindir)
    assert payload["verdict"] == "ok"
    assert _state(payload, "shellcheck")["pinned"] == "0.11.0"
    assert _state(payload, "gitleaks")["pinned"] == "9.0.0"
    assert _state(payload, "jq")["pinned"] == "2.0.0"
