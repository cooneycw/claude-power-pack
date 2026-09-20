"""Offline characterization tests for the project-next ownership gate (issue #1069).

SUCCEEDS tests/test_project_next_vendor.py, which was retired with the gate it
characterized. The dispositions are recorded here rather than in the commit
message, because a reader asking "what happened to the vendor gate's coverage"
reads the test file, not the log:

CARRIED OVER, re-pointed at scripts/project-next-ownership.py - ten properties
that were never about vendoring, only about whether a per-file pin gate can
fail: a wedged-at-fail gate, naming the exact drifted file, a derived contract
version, an absent file being drift rather than an empty population, an unpinned
module being reported, a dropped pin being refused rather than read as one fewer
check, both committed control cases, `--root` aiming at the case instead of this
repository, and the shipped subprocess invocation.

RETIRED WITH ITS SUBJECT - `test_upstream_network_failure_is_advisory_and_fail_open`.
The gate has no `--upstream` mode now. There is no upstream: codex-power-pack
goes private and dormant, and lib/vendor.py carries no auth to reach it after
that, so a fail-open network advisory has nothing to be advisory about.

RETIRED, PARTIALLY - `test_manifest_validation_refuses_an_untrustworthy_pin`
parametrized over `upstream_commit`, `upstream_license`, `vendored_at` and
`source_repo`. All four are vendoring PROVENANCE fields and the ownership
manifest does not carry them; asserting on them would test a manifest shape that
no longer exists. The one semantic field that survives, `contract_version`, is
covered by the derived-version test below rather than left uncovered.

Stdlib-only and network-free: the `validate` CI container ships neither curl nor
git. Findings go to STDOUT here, where the retired gate used stderr.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project-next-ownership.py"
CONTROL = ROOT / "controls" / "project-next-ownership"
BAD_CASE = CONTROL / "cases" / "bad-drifted-file"
GOOD_CASE = CONTROL / "cases" / "good-pinned-files"

SPEC = importlib.util.spec_from_file_location("project_next_ownership", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
pno = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pno
SPEC.loader.exec_module(pno)

PINNED = ("docs/project-next-contract.md", "templates/project-next.schema.json")


def _sandbox(tmp_path: Path) -> Path:
    """A writable mini-repo holding a copy of the REAL engine tree.

    The real one, not a placeholder: these tests then say something about the
    engine CPP actually ships, which the committed control cases - deliberately
    a few placeholder bytes each - do not claim to.
    """
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "lib" / "project_next", root / "lib" / "project_next")
    for rel in PINNED:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    (root / ".claude").mkdir(parents=True)
    shutil.copy2(
        ROOT / ".claude" / "project-next-ownership.json",
        root / ".claude" / "project-next-ownership.json",
    )
    return root


def _manifest(root: Path) -> Path:
    return root / ".claude" / "project-next-ownership.json"


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
    assert pno.main(["check"]) == 0


def test_check_names_the_exact_drifted_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _sandbox(tmp_path)
    drifted = root / "lib" / "project_next" / "models.py"
    drifted.write_text(drifted.read_text(encoding="utf-8") + "# local edit\n", encoding="utf-8")

    assert pno.main(["check", "--root", str(root)]) == 1
    assert "lib/project_next/models.py does not match the manifest pin" in capsys.readouterr().out


def test_check_rejects_a_contract_version_not_derived_from_the_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Re-pinning an edited engine must not be able to keep the old version.

    contract_version is consumer-facing - the schema, the /project:next runtime
    pin, and the rendered decision-policy label all read it - so a manifest that
    simply asserts a version is a manifest that can lie about one.
    """
    root = _sandbox(tmp_path)
    _rewrite_manifest(root, contract_version="999")

    assert pno.main(["check", "--root", str(root)]) == 1
    assert "records '999'" in capsys.readouterr().out


def test_a_missing_engine_file_is_named_rather_than_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An absent file is drift, not an empty population.

    A per-file loop that skips what is not there reports "everything I looked at
    matched" over a tree with files deleted - the success message claiming more
    than its input population supports.
    """
    root = _sandbox(tmp_path)
    removed = root / "lib" / "project_next" / "rank.py"
    removed.unlink()
    assert not removed.exists(), "fixture must lack the engine file"

    assert pno.main(["check", "--root", str(root)]) == 1
    assert "lib/project_next/rank.py is pinned but absent" in capsys.readouterr().out


def test_an_unpinned_module_in_the_package_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A module nobody pins is reported, never ignored - otherwise the package
    is a place anything can be added and still verify clean, with no version
    bump ever having to account for it."""
    root = _sandbox(tmp_path)
    smuggled = root / "lib" / "project_next" / "extra.py"
    assert not smuggled.exists(), "fixture must start without the unpinned module"
    smuggled.write_text("EXTRA = 1\n", encoding="utf-8")

    assert pno.main(["check", "--root", str(root)]) == 1
    assert "lib/project_next/extra.py sits in the package and is pinned by nothing" in capsys.readouterr().out


def test_a_manifest_missing_a_pin_is_refused_rather_than_trusted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The file list is the HARDCODED UNIVERSE; the manifest supplies members.

    Dropping a pin must be refused, not read as "one fewer thing to check" -
    that is how a file quietly leaves the ownership contract while the gate
    keeps reporting clean over the remainder.
    """
    root = _sandbox(tmp_path)
    files = json.loads(_manifest(root).read_text(encoding="utf-8"))["files"]
    del files["lib/project_next/rank.py"]
    _rewrite_manifest(root, files=files)

    assert pno.main(["check", "--root", str(root)]) == 1
    assert "lib/project_next/rank.py is in the ownership contract and carries no pin" in capsys.readouterr().out


# --- the committed negative-control cases ------------------------------------


def test_the_committed_bad_case_is_reported_as_drift(capsys: pytest.CaptureFixture[str]) -> None:
    assert pno.main(["check", "--root", str(BAD_CASE)]) == 1
    assert "DRIFT: " in capsys.readouterr().out


def test_the_committed_good_case_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert pno.main(["check", "--root", str(GOOD_CASE)]) == 0
    assert "11 files match" in capsys.readouterr().out


def test_root_names_the_case_not_the_real_repository(capsys: pytest.CaptureFixture[str]) -> None:
    """A gate whose roots are module-level constants can only read THIS
    repository, so a run "against a fixture" answers about the wrong tree. The
    real tree matches its pins, so such a run prints a clean line and is
    indistinguishable from a working one - which is what makes a committed case
    possible at all. `--root` is the thing under test here.
    """
    assert pno.main(["check", "--root", str(BAD_CASE)]) == 1
    out = capsys.readouterr().out
    assert "lib/project_next/rank.py" in out


def test_the_shipped_invocation_still_works_as_a_subprocess() -> None:
    """`make project-next-check` calls this as a program, not as a module.

    Every test above drives `main()` directly, which cannot catch an import-time
    or shebang breakage in the surface the Makefile actually invokes.
    """
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "check"], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert "11 files match" in completed.stdout
