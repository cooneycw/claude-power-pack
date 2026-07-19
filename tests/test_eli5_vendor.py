"""Tests for scripts/eli5-vendor.py - the vendored eli5-core guard (issue #591).

The link these protect: CPP vendors the eli5 necessity-gate core verbatim from
cooneycw/eli5-gate between the ``eli5-core`` markers. Before #591 the drift
script for that link was invoked by nothing at all - no CI step, no Makefile
target, no test - so a stale or locally-edited core was invisible.

Everything here is OFFLINE and stdlib-only on purpose: no network, no git, no
external binaries. The Woodpecker ``validate`` container (uv:python3.11-slim)
ships neither curl nor git, and an unguarded shell-out turns CI red even though
it passes locally (the recurring #451/#489 trap). The live-fetch half of the
guard (``--upstream``) is deliberately NOT exercised here - it is advisory and
fail-open by design, and a test that reaches the network would be flaky.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "eli5-vendor.py"
MANIFEST = ROOT / ".claude" / "eli5-vendor.json"


def _load_module():
    """Import the hyphenated script by path (not importable as a module name)."""
    spec = importlib.util.spec_from_file_location("eli5_vendor", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eli5_vendor"] = module
    spec.loader.exec_module(module)
    return module


ev = _load_module()


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
    manifest = ev.load_manifest()
    core = ev.extract_core(ev.vendored_path(manifest).read_text(encoding="utf-8"))
    assert ev.core_sha256(core) == manifest["vendored"]["core_sha256"], (
        "vendored eli5 core does not match .claude/eli5-vendor.json. Edit the core "
        "UPSTREAM (cooneycw/eli5-gate) first, then run `make eli5-revendor`."
    )


def test_check_command_passes_on_the_real_repo():
    assert ev.main([]) == 0


def test_manifest_line_count_matches():
    manifest = ev.load_manifest()
    core = ev.extract_core(ev.vendored_path(manifest).read_text(encoding="utf-8"))
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


def test_check_reports_drift_when_the_core_is_edited(tmp_path: Path, capsys, monkeypatch):
    """A tampered core must FAIL, not warn - this half of the guard is the hard
    gate; the live-fetch half is the advisory one."""
    vendored = tmp_path / "eli5.md"
    vendored.write_text("<!-- eli5-core:begin -->\ntampered\n<!-- eli5-core:end -->\n", encoding="utf-8")
    manifest = {
        "source": {"raw_url": "https://example.invalid/x.md", "upstream_commit": "deadbeef"},
        "vendored": {"file": vendored.name, "core_sha256": ev.core_sha256("original\n")},
    }
    monkeypatch.setattr(ev, "REPO_ROOT", tmp_path)
    assert ev.cmd_check(manifest) == 1
    assert "DRIFT" in capsys.readouterr().err


def test_upstream_check_fails_open_when_the_network_is_down(tmp_path: Path, capsys, monkeypatch):
    """Advisory means advisory: an unreachable canonical source exits 0 so an
    offline CI runner can never redden the pipeline on it."""
    vendored = tmp_path / "eli5.md"
    vendored.write_text("<!-- eli5-core:begin -->\ncore\n<!-- eli5-core:end -->\n", encoding="utf-8")

    def _boom(url: str) -> str:
        raise OSError("network is unreachable")

    monkeypatch.setattr(ev, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ev, "fetch", _boom)
    manifest = {"source": {"raw_url": "https://example.invalid/x.md"}, "vendored": {"file": vendored.name}}
    assert ev.cmd_upstream(manifest) == 0
    assert "fail-open" in capsys.readouterr().err


def test_upstream_check_reports_drift(tmp_path: Path, capsys, monkeypatch):
    vendored = tmp_path / "eli5.md"
    vendored.write_text("<!-- eli5-core:begin -->\nlocal\n<!-- eli5-core:end -->\n", encoding="utf-8")
    monkeypatch.setattr(ev, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ev, "fetch", lambda url: "<!-- eli5-core:begin -->\nupstream\n<!-- eli5-core:end -->\n")
    manifest = {"source": {"raw_url": "https://example.invalid/x.md"}, "vendored": {"file": vendored.name}}
    assert ev.cmd_upstream(manifest) == 1
    assert "drifted" in capsys.readouterr().err


def test_upstream_check_is_in_sync_when_cores_match(tmp_path: Path, monkeypatch):
    vendored = tmp_path / "eli5.md"
    body = "<!-- eli5-core:begin -->\nsame\n<!-- eli5-core:end -->\n"
    vendored.write_text(body, encoding="utf-8")
    monkeypatch.setattr(ev, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ev, "fetch", lambda url: body)
    manifest = {"source": {"raw_url": "https://example.invalid/x.md"}, "vendored": {"file": vendored.name}}
    assert ev.cmd_upstream(manifest) == 0
