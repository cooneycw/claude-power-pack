"""Offline characterization tests for the project-next vendor guard (issues #723, #1012).

Stdlib-only and network-free: the `validate` CI container ships neither curl nor
git, and the live-fetch half is exercised through a stubbed fetcher so a
fail-open verdict can never depend on the runner's connectivity.

Since #1012 the machinery lives in `lib/vendor.py` and this script is a
declaration. These tests drive it through its CLI - `main(["check", "--root",
...])` - because that is the surface `make verify`, the Makefile targets and the
negative control all invoke, and it is what a refactor must not move. The two
`_sandbox` tests below kept their subject: a copy of the REAL 16-file vendored
tree, not a placeholder one, so they still say something about the engine CPP
actually ships.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lib import vendor

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project-next-vendor.py"
CONTROL = ROOT / "controls" / "project-next-vendor"
BAD_CASE = CONTROL / "cases" / "bad-drifted-file"
GOOD_CASE = CONTROL / "cases" / "good-pinned-files"

SPEC = importlib.util.spec_from_file_location("project_next_vendor", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
pnv = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pnv
SPEC.loader.exec_module(pnv)


def _sandbox(tmp_path: Path) -> Path:
    """A writable mini-repo holding a copy of the REAL vendored tree."""
    root = tmp_path / "repo"
    (root / "vendor").mkdir(parents=True)
    shutil.copytree(ROOT / "vendor" / "project_next", root / "vendor" / "project_next")
    (root / ".claude").mkdir(parents=True)
    shutil.copy2(ROOT / ".claude" / "project-next-vendor.json", root / ".claude" / "project-next-vendor.json")
    return root


def _manifest(root: Path) -> Path:
    return root / ".claude" / "project-next-vendor.json"


def _rewrite_manifest(root: Path, **changes: object) -> None:
    path = _manifest(root)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(changes)
    path.write_text(json.dumps(data), encoding="utf-8")


# --- the offline hard gate ---------------------------------------------------


def test_check_passes_on_the_real_repo() -> None:
    """The half that separates a working gate from one wedged at 'fail'.

    This gate is a prerequisite of `make verify`, so a check that refuses every
    tree blocks every merge - and would look identical to a working one in the
    drift test below.
    """
    assert pnv.main(["check"]) == 0


def test_offline_check_names_the_exact_drifted_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _sandbox(tmp_path)
    drifted = root / "vendor" / "project_next" / "lib" / "project_next" / "models.py"
    drifted.write_text(drifted.read_text(encoding="utf-8") + "# local edit\n", encoding="utf-8")

    assert pnv.main(["check", "--root", str(root)]) == 1
    captured = capsys.readouterr()
    assert "lib/project_next/models.py" in captured.err
    assert "expected:" in captured.err
    assert "actual:" in captured.err


def test_offline_check_rejects_a_contract_version_not_derived_from_the_document(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _sandbox(tmp_path)
    _rewrite_manifest(root, contract_version="999")

    assert pnv.main(["check", "--root", str(root)]) == 1
    assert "contract version mismatch" in capsys.readouterr().err


def test_a_missing_vendored_file_is_named_rather_than_skipped(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An absent file is drift, not an empty population.

    A per-file loop that simply skips what is not there reports "everything I
    looked at matched" over a tree with files deleted - the success message
    claiming more than its input population supports.
    """
    root = _sandbox(tmp_path)
    removed = root / "vendor" / "project_next" / "lib" / "project_next" / "rank.py"
    removed.unlink()
    assert not removed.exists(), "fixture must lack the vendored file"

    assert pnv.main(["check", "--root", str(root)]) == 1
    err = capsys.readouterr().err
    assert "lib/project_next/rank.py" in err
    assert "missing" in err


def test_an_unpinned_file_under_the_subtree_is_reported(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A file nobody pins is reported, never ignored - otherwise the vendored
    subtree is a place anything can be smuggled into and still verify clean."""
    root = _sandbox(tmp_path)
    smuggled = root / "vendor" / "project_next" / "lib" / "project_next" / "extra.py"
    assert not smuggled.exists(), "fixture must start without the unpinned file"
    smuggled.write_text("EXTRA = 1\n", encoding="utf-8")

    assert pnv.main(["check", "--root", str(root)]) == 1
    err = capsys.readouterr().err
    assert "lib/project_next/extra.py" in err
    assert "unexpected file" in err


def test_a_manifest_missing_a_pin_is_refused_rather_than_trusted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The file list is the HARDCODED UNIVERSE; the manifest supplies members.

    Dropping a pin must be refused, not read as "one fewer thing to check" -
    that is how a file quietly leaves the vendoring contract while the gate
    keeps reporting clean over the remainder.
    """
    root = _sandbox(tmp_path)
    files = json.loads(_manifest(root).read_text(encoding="utf-8"))["files"]
    del files["lib/project_next/rank.py"]
    _rewrite_manifest(root, files=files)

    assert pnv.main(["check", "--root", str(root)]) == 1
    assert "manifest file set differs from the vendoring contract" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("field", "value", "needle"),
    [
        ("upstream_commit", "abc123", "full lowercase commit SHA"),
        ("upstream_license", "", "upstream_license must be a non-empty string"),
        ("vendored_at", "not-a-date", "vendored_at must be an ISO date"),
        ("source_repo", "https://github.com/someone/else", "source_repo must be"),
    ],
)
def test_manifest_validation_refuses_an_untrustworthy_pin(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    field: str,
    value: str,
    needle: str,
) -> None:
    """Each of these needs a differently-malformed manifest, which is why they
    are tests rather than committed control cases: a case tree can carry one."""
    root = _sandbox(tmp_path)
    _rewrite_manifest(root, **{field: value})

    assert pnv.main(["check", "--root", str(root)]) == 1
    assert needle in capsys.readouterr().err


# --- the committed negative-control cases ------------------------------------


def test_the_committed_bad_case_is_reported_as_drift(capsys: pytest.CaptureFixture[str]) -> None:
    assert pnv.main(["check", "--root", str(BAD_CASE)]) == 1
    assert "DRIFT: " in capsys.readouterr().err


def test_the_committed_good_case_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert pnv.main(["check", "--root", str(GOOD_CASE)]) == 0
    assert "16 files match" in capsys.readouterr().out


def test_root_names_the_case_not_the_real_repository(capsys: pytest.CaptureFixture[str]) -> None:
    """Before #1012 VENDOR_ROOT was a module-level constant, so a run "against a
    fixture" read THIS repository and answered about it. The real tree matches
    its pins, so such a run printed a clean line and was indistinguishable from
    a correct GOOD verdict on the case. Which manifest the report NAMES is what
    separates them."""
    assert pnv.main(["check", "--root", str(BAD_CASE)]) == 1
    err = capsys.readouterr().err
    assert str(BAD_CASE) in err, "the drift report must name the case tree it was aimed at"
    assert str(ROOT / ".claude" / "project-next-vendor.json") not in err


# --- the advisory half -------------------------------------------------------


def test_upstream_network_failure_is_advisory_and_fail_open(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Advisory means advisory: unreachable upstream exits 0 with a note.

    The stub records its calls, because "exit 0 and a note" is also what a test
    that exercised nothing produces - so the recording is what makes the pass
    mean something.
    """
    fetched: list[str] = []

    def unavailable(self, url: str) -> bytes:
        fetched.append(url)
        raise vendor.SourceUnavailable("offline fixture")

    monkeypatch.setattr(vendor.Fetcher, "bytes_at", unavailable)
    assert vendor.Fetcher.bytes_at is unavailable, "fixture did not replace the network entry point"

    assert pnv.main(["--upstream"]) == 0
    assert fetched, "nothing was fetched, so the fail-open path was never reached"
    assert "skipping (fail-open)" in capsys.readouterr().err


# --- invocation parity -------------------------------------------------------


def test_the_shipped_invocation_still_works_as_a_subprocess() -> None:
    """`make project-next-check` calls this as a program, not as a module.

    #1012 moved the implementation into `lib/vendor.py`, reached through a
    `sys.path` insert. An in-process import cannot see a broken insert - pytest
    already has the repository root on `sys.path` - so this runs the real
    command line `make verify` runs.
    """
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "check"], cwd=str(ROOT), capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, f"`python3 scripts/project-next-vendor.py check` failed:\n{done.stdout}\n{done.stderr}"
    assert "files match" in done.stdout
