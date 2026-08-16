"""Offline characterization tests for the project-next vendor guard."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project-next-vendor.py"
SPEC = importlib.util.spec_from_file_location("project_next_vendor", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
vendor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = vendor
SPEC.loader.exec_module(vendor)


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    target = tmp_path / "vendor" / "project_next"
    manifest = tmp_path / "project-next-vendor.json"
    shutil.copytree(ROOT / "vendor" / "project_next", target)
    shutil.copy2(ROOT / ".claude" / "project-next-vendor.json", manifest)
    monkeypatch.setattr(vendor, "VENDOR_ROOT", target)
    monkeypatch.setattr(vendor, "MANIFEST_PATH", manifest)
    return target, manifest


def test_offline_check_names_the_exact_drifted_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target, _ = _sandbox(monkeypatch, tmp_path)
    drifted = target / "lib" / "project_next" / "models.py"
    drifted.write_text(drifted.read_text(encoding="utf-8") + "# local edit\n", encoding="utf-8")

    assert vendor.cmd_check() == 1
    captured = capsys.readouterr()
    assert "lib/project_next/models.py" in captured.err
    assert "expected:" in captured.err
    assert "actual:" in captured.err


def test_offline_check_rejects_a_contract_version_not_derived_from_the_document(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, manifest_path = _sandbox(monkeypatch, tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["contract_version"] = "999"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert vendor.cmd_check() == 1
    assert "contract version mismatch" in capsys.readouterr().err


def test_upstream_network_failure_is_advisory_and_fail_open(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unavailable() -> str:
        raise urllib.error.URLError("offline fixture")

    monkeypatch.setattr(vendor, "_resolve_main", unavailable)

    assert vendor.cmd_upstream() == 0
    assert "skipping (fail-open)" in capsys.readouterr().err
