"""Tests for scripts/eli5-vendor.py - the vendored eli5-core guard (issues #591, #1012).

The link these protect: CPP vendors the eli5 necessity-gate core verbatim from
cooneycw/eli5-gate between the ``eli5-core`` markers. Before #591 the drift
script for that link was invoked by nothing at all - no CI step, no Makefile
target, no test - so a stale or locally-edited core was invisible.

Everything here is OFFLINE and stdlib-only on purpose: no network, no git, no
external binaries. The Woodpecker ``validate`` container (uv:python3.11-slim)
ships neither curl nor git, and an unguarded shell-out turns CI red even though
it passes locally (the recurring #451/#489 trap). The live-fetch half of the
guard (``--upstream``) is exercised only through a STUBBED fetcher - reaching the
real network here would be flaky, and would make a fail-open test's pass depend
on the runner's connectivity rather than on the code.

Since #1012 the machinery lives in ``lib/vendor.py`` and this script is a
declaration, so these tests drive it through its CLI (``main([...])``) rather
than through internal function names. That is deliberate: the CLI is what CI,
the Makefile and the negative control all invoke, and it is the surface a
refactor must not move.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lib import vendor

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "eli5-vendor.py"
MANIFEST = ROOT / ".claude" / "eli5-vendor.json"
CONTROL = ROOT / "controls" / "eli5-vendor"
BAD_CASE = CONTROL / "cases" / "bad-drifted-core"
GOOD_CASE = CONTROL / "cases" / "good-pinned-core"


def _load_module():
    """Import the hyphenated script by path (not importable as a module name)."""
    spec = importlib.util.spec_from_file_location("eli5_vendor", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eli5_vendor"] = module
    spec.loader.exec_module(module)
    return module


ev = _load_module()


def _fixture_tree(root: Path, core: str, *, pin: str | None = None) -> Path:
    """A miniature repo: one marker document plus the manifest that pins it."""
    document = root / ".claude" / "commands" / "flow" / "eli5.md"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text(
        "before\n<!-- eli5-core:begin -->\n" + core + "<!-- eli5-core:end -->\nafter\n",
        encoding="utf-8",
    )
    manifest = root / ".claude" / "eli5-vendor.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "source": {
                    "raw_url": "https://example.invalid/eli5.md",
                    "commits_api": "https://example.invalid/commits",
                    "upstream_commit": "0" * 40,
                },
                "vendored": {
                    "file": ".claude/commands/flow/eli5.md",
                    "core_sha256": pin if pin is not None else vendor.sha256_hex(core.encode("utf-8")),
                    "core_lines": len(core.splitlines()),
                },
            }
        ),
        encoding="utf-8",
    )
    return root


# --- wiring ------------------------------------------------------------------


def test_script_exists_and_executable():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), "eli5-vendor.py must be executable"


def test_manifest_is_present_and_well_formed():
    assert MANIFEST.is_file(), f"missing {MANIFEST} - the offline gate has nothing to pin against"
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["source"]["repo"] == "cooneycw/eli5-gate"
    assert data["source"]["raw_url"].startswith("https://")
    assert data["vendored"]["file"] == ".claude/commands/flow/eli5.md"
    sha = data["vendored"]["core_sha256"]
    assert isinstance(sha, str) and len(sha) == 64, "core_sha256 must be a full sha256 hex digest"


def test_manifest_pins_an_upstream_commit():
    """A manifest without an upstream SHA still guards content, but loses the
    provenance half - you cannot tell WHICH canonical revision was vendored."""
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    commit = data["source"].get("upstream_commit")
    assert isinstance(commit, str) and len(commit) >= 7, "re-vendor with `make eli5-revendor` to pin the upstream SHA"


# --- the gate itself ---------------------------------------------------------


def test_vendored_core_matches_the_manifest_pin():
    """THE gate: the checked-in core must be exactly what the manifest pins.

    Fails when someone edits the core between the markers directly instead of
    editing cooneycw/eli5-gate and re-vendoring.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    core = ev.extract_core((ROOT / manifest["vendored"]["file"]).read_text(encoding="utf-8"))
    assert vendor.sha256_hex(core.encode("utf-8")) == manifest["vendored"]["core_sha256"], (
        "vendored eli5 core does not match .claude/eli5-vendor.json. Edit the core "
        "UPSTREAM (cooneycw/eli5-gate) first, then run `make eli5-revendor`."
    )


def test_check_command_passes_on_the_real_repo():
    assert ev.main([]) == 0


def test_manifest_line_count_matches():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    core = ev.extract_core((ROOT / manifest["vendored"]["file"]).read_text(encoding="utf-8"))
    assert len(core.splitlines()) == manifest["vendored"]["core_lines"]


# --- marker extraction -------------------------------------------------------


def test_extract_core_returns_only_the_marker_section():
    text = "before\n<!-- eli5-core:begin (canonical: x) -->\ncore line\n<!-- eli5-core:end -->\nafter\n"
    assert ev.extract_core(text) == "core line\n"


def test_extract_core_ignores_markers_mentioned_mid_line():
    """The Notes bullet in eli5.md mentions the markers in prose; anchoring to
    line starts is what keeps that from re-triggering the state machine."""
    text = (
        "see the <!-- eli5-core:begin --> marker in prose\n"
        "<!-- eli5-core:begin -->\n"
        "real core\n"
        "<!-- eli5-core:end -->\n"
    )
    assert ev.extract_core(text) == "real core\n"


def test_extract_core_rejects_a_missing_begin_marker():
    with pytest.raises(ev.CoreNotFound):
        ev.extract_core("no markers here\n")


def test_extract_core_rejects_an_unterminated_core():
    with pytest.raises(ev.CoreNotFound):
        ev.extract_core("<!-- eli5-core:begin -->\ndangling\n")


# --- failure surfacing -------------------------------------------------------


def test_check_reports_drift_when_the_core_is_edited(tmp_path: Path, capsys):
    """A tampered core must FAIL, not warn - this half of the guard is the hard
    gate; the live-fetch half is the advisory one."""
    root = _fixture_tree(tmp_path, "tampered\n", pin=vendor.sha256_hex(b"original\n"))
    assert ev.main(["--root", str(root)]) == 1
    assert "DRIFT" in capsys.readouterr().err


def test_check_passes_when_the_core_matches(tmp_path: Path):
    """The half that separates a working gate from one wedged at 'fail'."""
    root = _fixture_tree(tmp_path, "pinned\n")
    assert ev.main(["--root", str(root)]) == 0


def test_a_missing_vendored_file_fails_the_offline_gate(tmp_path: Path, capsys):
    """Absent is not clean. The copy is SUPPOSED to be here, so its absence is a
    failure of the gate's own question - unlike the advisory half below, which
    has nothing to compare and correctly exits 0."""
    root = _fixture_tree(tmp_path, "pinned\n")
    (root / ".claude" / "commands" / "flow" / "eli5.md").unlink()
    assert not (root / ".claude" / "commands" / "flow" / "eli5.md").exists(), "fixture must lack the vendored file"
    assert ev.main(["--root", str(root)]) == 1
    assert "not found" in capsys.readouterr().err


# --- the committed negative-control cases ------------------------------------
#
# The control harness runs these too. Asserting them from pytest as well is not
# duplication: `check-negative-controls.py` judges its own verdicts, and a
# second opinion from the same program is not one (the reason
# tests/test_negative_controls.py exists at all). These assert the GATE's exit
# codes directly, from a different process and a different entry point.


def test_the_committed_bad_case_is_reported_as_drift(capsys):
    assert ev.main(["--root", str(BAD_CASE)]) == 1
    assert "DRIFT: " in capsys.readouterr().err


def test_the_committed_good_case_passes(capsys):
    assert ev.main(["--root", str(GOOD_CASE)]) == 0
    assert "matches the manifest" in capsys.readouterr().out


def test_root_names_the_case_not_the_real_repository(capsys):
    """A verdict about the wrong tree is a plausible answer, not an error.

    Before #1012 the repository root was a module-level constant, so a run
    "against a fixture" silently read THIS repository and reported on it. The
    real core matches its pin, so such a run would have printed a clean line and
    looked exactly like a correct GOOD verdict on the case. What separates the
    two is WHICH manifest the report names, so that is what is asserted.
    """
    assert ev.main(["--root", str(BAD_CASE)]) == 1
    err = capsys.readouterr().err
    assert str(BAD_CASE) in err, "the drift report must name the case tree it was aimed at"
    assert str(MANIFEST) not in err, "the gate read the real repository instead of the case"


# --- the advisory half -------------------------------------------------------


def _stub_fetch(monkeypatch, handler) -> list[str]:
    """Replace the ONE network entry point and RECORD every call through it.

    A fail-open test's passing state carries almost no information on its own:
    "exit 0, a note on stderr" is also exactly what a test that exercised
    nothing produces. The returned list is the evidence that the stub was
    load-bearing - each test asserts on it, so a run that silently stopped
    fetching fails instead of passing quietly.

    `Fetcher.bytes_at` is the only `urlopen` site in `lib/vendor.py`, so
    replacing it is sufficient to keep every test in this file off the network.
    """
    seen: list[str] = []

    def recorded(self, url: str) -> bytes:
        seen.append(url)
        return handler(url)

    monkeypatch.setattr(vendor.Fetcher, "bytes_at", recorded)
    assert vendor.Fetcher.bytes_at is recorded, "fixture did not replace the network entry point"
    return seen


def test_upstream_check_fails_open_when_the_network_is_down(tmp_path: Path, capsys, monkeypatch):
    """Advisory means advisory: an unreachable canonical source exits 0 so an
    offline CI runner can never redden the pipeline on it."""

    def unreachable(url: str) -> bytes:
        raise vendor.SourceUnavailable("network is unreachable")

    fetched = _stub_fetch(monkeypatch, unreachable)
    root = _fixture_tree(tmp_path, "core\n")
    assert ev.main(["--upstream", "--root", str(root)]) == 0
    assert fetched, "nothing was fetched, so the fail-open path was never reached"
    assert "fail-open" in capsys.readouterr().err


def test_upstream_check_reports_drift(tmp_path: Path, capsys, monkeypatch):
    def upstream_moved(url: str) -> bytes:
        return b"<!-- eli5-core:begin -->\nupstream\n<!-- eli5-core:end -->\n"

    fetched = _stub_fetch(monkeypatch, upstream_moved)
    root = _fixture_tree(tmp_path, "local\n")
    assert ev.main(["--upstream", "--root", str(root)]) == 1
    assert fetched, "the verdict did not come from a fetched upstream copy"
    assert "drifted" in capsys.readouterr().err


def test_upstream_check_is_in_sync_when_cores_match(tmp_path: Path, monkeypatch):
    def upstream_same(url: str) -> bytes:
        return b"<!-- eli5-core:begin -->\nsame\n<!-- eli5-core:end -->\n"

    fetched = _stub_fetch(monkeypatch, upstream_same)
    root = _fixture_tree(tmp_path, "same\n")
    assert ev.main(["--upstream", "--root", str(root)]) == 0
    assert fetched, "an in-sync verdict with nothing fetched is vacuous"


def test_upstream_does_not_fail_open_on_a_local_defect(tmp_path: Path, capsys, monkeypatch):
    """The narrow half of fail-open, asserted as a negative membership.

    "Any trouble exits 0" is one refactor away from "the advisory check never
    reports anything". A malformed LOCAL marker pair is not a network problem
    and must still exit 1 - so this fails if `SourceUnavailable` is ever widened
    to cover local defects, which no positive fail-open test can catch.
    """

    def never_called(url: str) -> bytes:  # pragma: no cover - must not run
        raise AssertionError("upstream was fetched despite a local defect")

    fetched = _stub_fetch(monkeypatch, never_called)
    root = _fixture_tree(tmp_path, "core\n")
    document = root / ".claude" / "commands" / "flow" / "eli5.md"
    document.write_text("<!-- eli5-core:begin -->\ndangling, no end marker\n", encoding="utf-8")
    assert "eli5-core:end" not in document.read_text(encoding="utf-8"), "fixture must lack the end marker"
    assert ev.main(["--upstream", "--root", str(root)]) == 1
    assert not fetched, "a local defect must be reported without consulting upstream"
    assert "fail-open" not in capsys.readouterr().err


# --- invocation parity -------------------------------------------------------


def test_the_shipped_invocations_still_work_as_a_subprocess():
    """CI and the Makefile call this as a program, not as a module.

    The #1012 refactor moved the implementation into `lib/vendor.py`, which the
    script reaches through a `sys.path` insert. An in-process import test cannot
    see a broken insert - pytest already has the repository root on `sys.path` -
    so this runs the real command line the way CI does.
    """
    done = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=str(ROOT), capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, f"`python3 scripts/eli5-vendor.py` failed:\n{done.stdout}\n{done.stderr}"
    assert "matches the manifest" in done.stdout


# --- the offline gate's own question, and nothing else -----------------------


def test_the_offline_gate_does_not_require_source_metadata(tmp_path: Path):
    """A pinned core that matches must pass even with no `source` block at all.

    The hard gate's question is entirely "do these bytes hash to the pinned
    value". Requiring `source.raw_url` here - which only the network modes read -
    made a matching document exit 1 over metadata the comparison never consults,
    a schema tightening on the one check CI blocks on. Found by the #1012
    counter-model review.
    """
    core = "pinned\n"
    document = tmp_path / ".claude" / "commands" / "flow" / "eli5.md"
    document.parent.mkdir(parents=True)
    document.write_text("<!-- eli5-core:begin -->\n" + core + "<!-- eli5-core:end -->\n", encoding="utf-8")
    manifest = tmp_path / ".claude" / "eli5-vendor.json"
    manifest.write_text(
        json.dumps({"vendored": {"file": ".claude/commands/flow/eli5.md",
                                 "core_sha256": vendor.sha256_hex(core.encode("utf-8"))}}),
        encoding="utf-8",
    )
    assert "source" not in json.loads(manifest.read_text(encoding="utf-8")), "fixture must lack the source block"
    assert ev.main(["--root", str(tmp_path)]) == 0


def test_revendor_replaces_the_core_in_place_and_repins(tmp_path: Path, monkeypatch):
    """The write path, which had no test before #1012's counter-model review.

    Everything OUTSIDE the markers must survive: this link vendors a slice of a
    document whose surrounding CPP wiring is not upstream's to write.
    """

    def upstream(url: str) -> bytes:
        if "commits" in url:
            return json.dumps([{"sha": "c" * 40}]).encode("utf-8")
        return b"<!-- eli5-core:begin -->\nfresh\n<!-- eli5-core:end -->\n"

    _stub_fetch(monkeypatch, upstream)
    root = _fixture_tree(tmp_path, "stale\n")
    assert ev.main(["--revendor", "--root", str(root)]) == 0

    document = (root / ".claude" / "commands" / "flow" / "eli5.md").read_text(encoding="utf-8")
    assert ev.extract_core(document) == "fresh\n"
    assert document.startswith("before\n"), "text above the markers must be untouched"
    assert document.endswith("after\n"), "text below the markers must be untouched"

    manifest = json.loads((root / ".claude" / "eli5-vendor.json").read_text(encoding="utf-8"))
    assert manifest["vendored"]["core_sha256"] == vendor.sha256_hex(b"fresh\n")
    assert manifest["source"]["upstream_commit"] == "c" * 40
    assert ev.main(["--root", str(root)]) == 0, "the re-vendored tree must pass the offline gate"
