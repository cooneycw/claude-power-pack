"""scripts/nit-store-resolve.sh - the one copy of the Nit Store map (#1272, #1273).

Every case drives the real script with a stubbed `gh` first on PATH. The stub
answers `issue view` and `issue list` from a small JSON fixture and can be told
to fail, so each verdict is reached by an input rather than by reading the code.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "nit-store-resolve.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required")

# A stub `gh`: `issue view N` prints "<state>\t<title>" for a known issue, `issue
# list` prints the numbers of open issues whose title is exactly "Nit Store", and
# GH_STUB_FAIL=1 makes every call fail. It honours --jq only in the two shapes
# the script uses, which is all a stub owes it.
GH_STUB = r'''#!/usr/bin/env python3
import json, os, sys
if os.environ.get("GH_STUB_FAIL") == "1":
    sys.exit(1)
issues = json.load(open(os.environ["GH_STUB_ISSUES"]))
a = sys.argv[1:]
if a[:2] == ["issue", "view"]:
    i = issues.get(a[2])
    if i is None:
        sys.exit(1)
    print(i["state"] + "\t" + i["title"])
elif a[:2] == ["issue", "list"]:
    for n, i in sorted(issues.items(), key=lambda kv: int(kv[0])):
        if i["state"] == "OPEN" and i["title"] == "Nit Store":
            print(n)
elif a[:2] == ["repo", "view"]:
    sys.exit(1)
else:
    sys.exit(2)
'''


def _run(tmp_path: Path, issues: dict, *args: str, fail: bool = False,
         cwd: Path | None = None) -> tuple[int, str]:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(GH_STUB)
    gh.chmod(0o755)
    data = tmp_path / "issues.json"
    data.write_text(json.dumps(issues))
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}",
           "GH_STUB_ISSUES": str(data), "GH_STUB_FAIL": "1" if fail else "0"}
    r = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True,
                       env=env, cwd=str(cwd or tmp_path))
    return r.returncode, r.stdout + r.stderr


OPEN_STORE = {"state": "OPEN", "title": "Nit Store"}


def test_a_mapped_open_nit_store_is_the_answer(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {"864": OPEN_STORE}, "--repo", "cooneycw/claude-power-pack")
    assert rc == 0 and "NIT_STORE=864" in out and "NIT_STORE_SOURCE=map" in out, out


def test_a_closed_mapped_target_is_none_never_the_number(tmp_path: Path) -> None:
    """The #227 shape: the map named an issue that had been CLOSED."""
    rc, out = _run(tmp_path, {"864": {"state": "CLOSED", "title": "Nit Store"}},
                   "--repo", "cooneycw/claude-power-pack")
    assert rc == 1 and "NIT_STORE_STATUS: none" in out and "normal issue" in out, out
    assert "NIT_STORE=864" not in out


def test_a_retitled_mapped_target_is_refused(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {"864": {"state": "OPEN", "title": "Release checklist"}},
                   "--repo", "cooneycw/claude-power-pack")
    assert rc == 1 and "not 'Nit Store'" in out and "NIT_STORE=864" not in out, out


def test_an_unreadable_mapped_target_is_unknown_not_none(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {"864": OPEN_STORE}, "--repo", "cooneycw/claude-power-pack", fail=True)
    assert rc == 3 and "NIT_STORE_STATUS: unknown" in out and "NIT_STORE=" not in out.replace(
        "NIT_STORE_REPO=", ""), out


def test_an_unmapped_repo_with_one_exact_store_is_found_by_search(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {"7": {"state": "OPEN", "title": "Nit Store"},
                              "8": {"state": "OPEN", "title": "Nit Store follow-ups"}},
                   "--repo", "someone/other")
    assert rc == 0 and "NIT_STORE=7" in out and "NIT_STORE_SOURCE=search" in out, out


def test_an_unmapped_repo_with_no_store_is_none(tmp_path: Path) -> None:
    """codex-power-pack today: unmapped, and no open issue titled 'Nit Store'."""
    rc, out = _run(tmp_path, {"227": {"state": "CLOSED", "title": "Nit Store"}},
                   "--repo", "cooneycw/codex-power-pack")
    assert rc == 1 and "NIT_STORE_STATUS: none" in out, out


def test_two_exact_stores_is_unknown(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {"7": OPEN_STORE, "9": OPEN_STORE}, "--repo", "someone/other")
    assert rc == 3 and "2 open issues" in out, out


def test_an_unreadable_search_is_unknown(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {}, "--repo", "someone/other", fail=True)
    assert rc == 3 and "could not list" in out, out


@pytest.mark.parametrize("url", [
    "git@github.com:cooneycw/claude-power-pack.git",
    "https://github.com/cooneycw/claude-power-pack.git",
    "https://github.com/cooneycw/claude-power-pack",
])
def test_the_repo_comes_from_origin_not_the_directory_name(tmp_path: Path, url: str) -> None:
    """Flow runs from a per-issue worktree whose basename is not the repo."""
    if shutil.which("git") is None:
        pytest.skip("git is required to build the origin fixture")
    wt = tmp_path / "claude-power-pack-issue-865"
    wt.mkdir()
    subprocess.run(["git", "init", "-q", str(wt)], check=True)
    subprocess.run(["git", "-C", str(wt), "remote", "add", "origin", url], check=True)
    rc, out = _run(tmp_path, {"864": OPEN_STORE}, cwd=wt)
    assert rc == 0 and "NIT_STORE_REPO=cooneycw/claude-power-pack" in out, out


def test_no_repository_is_unknown(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {}, fail=True)
    assert rc == 3 and "could not determine the repository" in out, out


def test_a_bad_argument_is_a_usage_error(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {}, "--bogus")
    assert rc == 2 and "unknown argument" in out, out
