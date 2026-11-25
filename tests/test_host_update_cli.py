"""Feed real core results through the actual JSON/report CLI reader."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_host_update_core import Case

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git for source/checkout fixtures")
ROOT = Path(__file__).absolute().parents[1]
CLI = ROOT / "scripts/cpp-host-update.py"


def cli(case, operation, *, cwd=ROOT):
    return subprocess.run([sys.executable, str(CLI), operation, "--fixture-root", str(case.root), "--json"],
                          cwd=cwd, capture_output=True, text=True, timeout=15)


@pytest.mark.parametrize("external", [False, True])
def test_actual_cli_refresh_then_verify_with_real_report(tmp_path, external):
    case = Case(tmp_path / "fixture")
    case.descriptor(two=True)
    cwd = tmp_path if external else ROOT
    refreshed = cli(case, "refresh", cwd=cwd)
    assert refreshed.returncode == 0, refreshed.stderr + refreshed.stdout
    value = json.loads(refreshed.stdout)
    assert value["coverage"] == "fixture-only" and value["schema"] == 1
    assert [row["after"]["state"] for row in value["results"]] == ["current", "current"]
    assert {row["revision"] for row in value["results"]} == {case.revision}
    verified = cli(case, "verify", cwd=cwd)
    assert verified.returncode == 0 and "HOST_UPDATE: current" in verified.stderr
    assert all(row["effectiveness"]["state"] == "unknown" for row in json.loads(verified.stdout)["results"])


def test_cli_unknown_record_keeps_other_adapter_outcome(tmp_path):
    case = Case(tmp_path / "fixture")
    case.descriptor(two=True)
    assert cli(case, "refresh").returncode == 0
    ledger = case.root / "a/skills/.managed/ownership.json"
    ledger.write_bytes(b"incomplete JSON")
    assert ledger.read_bytes() == b"incomplete JSON"
    result = cli(case, "verify")
    assert result.returncode == 4
    value = json.loads(result.stdout)
    assert [row["exit_code"] for row in value["results"]] == [4, 0]
    assert "HOST_UPDATE: unknown" in result.stderr


def test_cli_refuses_unmarked_root_without_install_io(tmp_path):
    case = Case(tmp_path / "fixture")
    case.descriptor()
    (case.root / ".cpp-host-update-fixture").unlink()
    assert not (case.root / ".cpp-host-update-fixture").exists()
    result = cli(case, "refresh")
    assert result.returncode == 2 and "invalid fixture" in result.stderr
    assert not (case.root / "a/.install.lock").exists()


@pytest.mark.parametrize("layout", ["worktree", "shallow"])
def test_source_binding_supports_linked_worktree_and_shallow_clone(tmp_path, layout):
    case = Case(tmp_path / "fixture")
    alternate = case.root / "alternate"
    if layout == "worktree":
        case.git("worktree", "add", "--detach", str(alternate), case.revision)
    else:
        subprocess.run(["git", "clone", "-q", "--depth=1", case.source.as_uri(), str(alternate)],
                       check=True, timeout=10)
    case.descriptor()
    location = case.root / "fixture.json"
    descriptor = json.loads(location.read_bytes())
    descriptor["source"] = "alternate"
    descriptor["adapters"][0]["source"] = "alternate"
    location.write_text(json.dumps(descriptor))
    result = cli(case, "refresh")
    assert result.returncode == 0, result.stderr + result.stdout
