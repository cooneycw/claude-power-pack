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

# A stub `gh` that HONOURS the arguments the resolver's contract rests on, so a
# resolver that dropped one would get a different answer (counter-model review):
#   - `--repo` is required and selects that repository's fixture;
#   - `issue view N` prints "<state>\t<title>";
#   - `issue list` applies `--state open` only when asked, applies `--limit`, and
#     applies the exact-title filter only when the `--jq` program asks for it,
#     emitting the `TOTAL` line only when the program asks for that too.
# GH_STUB_FAIL=1 makes every call fail.
GH_STUB = r'''#!/usr/bin/env python3
import json, os, sys
if os.environ.get("GH_STUB_FAIL") == "1":
    sys.exit(1)
repos = json.load(open(os.environ["GH_STUB_ISSUES"]))
a = sys.argv[1:]
def opt(name, default=None):
    return a[a.index(name) + 1] if name in a else default
if a[:2] == ["repo", "view"]:
    sys.exit(1)
repo = opt("--repo")
if repo is None or repo not in repos:
    sys.exit(1)
issues = repos[repo]
if a[:2] == ["issue", "view"]:
    i = issues.get(a[2])
    if i is None:
        sys.exit(1)
    print(i["state"] + "\t" + i["title"])
elif a[:2] == ["issue", "list"]:
    rows = sorted(issues.items(), key=lambda kv: int(kv[0]))
    if opt("--state") == "open":
        rows = [r for r in rows if r[1]["state"] == "OPEN"]
    rows = rows[: int(opt("--limit", "30"))]
    jq = opt("--jq", "")
    if "TOTAL" in jq:
        print(f"TOTAL {len(rows)}")
    for n, i in rows:
        if 'select(.title == "Nit Store")' not in jq or i["title"] == "Nit Store":
            print(n)
else:
    sys.exit(2)
'''


def _run(tmp_path: Path, issues: dict, *args: str, fail: bool = False,
         cwd: Path | None = None) -> tuple[int, str]:
    """`issues` is keyed by OWNER/NAME, then by issue number."""
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
CPP, CXPP, OTHER = "cooneycw/claude-power-pack", "cooneycw/codex-power-pack", "someone/other"


def test_a_mapped_open_nit_store_is_the_answer(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {CPP: {"864": OPEN_STORE}}, "--repo", CPP)
    assert rc == 0 and "NIT_STORE=864" in out and "NIT_STORE_SOURCE=map" in out, out


def test_a_closed_mapped_target_is_none_never_the_number(tmp_path: Path) -> None:
    """The #227 shape: the map named an issue that had been CLOSED."""
    rc, out = _run(tmp_path, {CPP: {"864": {"state": "CLOSED", "title": "Nit Store"}}}, "--repo", CPP)
    assert rc == 1 and "NIT_STORE_STATUS: none" in out and "normal issue" in out, out
    assert "NIT_STORE=864" not in out


def test_a_retitled_mapped_target_is_refused(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {CPP: {"864": {"state": "OPEN", "title": "Release checklist"}}}, "--repo", CPP)
    assert rc == 1 and "not 'Nit Store'" in out and "NIT_STORE=864" not in out, out


def test_an_unreadable_mapped_target_is_unknown_not_none(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {CPP: {"864": OPEN_STORE}}, "--repo", CPP, fail=True)
    assert rc == 3 and "NIT_STORE_STATUS: unknown" in out and "NIT_STORE=" not in out.replace(
        "NIT_STORE_REPO=", ""), out


def test_an_unmapped_repo_with_one_exact_store_is_found_by_search(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {OTHER: {"7": {"state": "OPEN", "title": "Nit Store"},
                                     "8": {"state": "OPEN", "title": "Nit Store follow-ups"},
                                     "9": {"state": "CLOSED", "title": "Nit Store"}}},
                   "--repo", OTHER)
    assert rc == 0 and "NIT_STORE=7" in out and "NIT_STORE_SOURCE=search" in out, out


def test_an_unmapped_repo_with_no_store_is_none(tmp_path: Path) -> None:
    """codex-power-pack today: unmapped, and no open issue titled 'Nit Store'."""
    rc, out = _run(tmp_path, {CXPP: {"227": {"state": "CLOSED", "title": "Nit Store"}}}, "--repo", CXPP)
    assert rc == 1 and "NIT_STORE_STATUS: none" in out, out


def test_two_exact_stores_is_unknown(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {OTHER: {"7": OPEN_STORE, "9": OPEN_STORE}}, "--repo", OTHER)
    assert rc == 3 and "2 open issues" in out, out


def test_an_unreadable_search_is_unknown(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {}, "--repo", OTHER, fail=True)
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
    rc, out = _run(tmp_path, {CPP: {"864": OPEN_STORE}}, cwd=wt)
    assert rc == 0 and "NIT_STORE_REPO=cooneycw/claude-power-pack" in out, out


def test_no_repository_is_unknown(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {}, fail=True)
    assert rc == 3 and "could not determine the repository" in out, out


def test_a_bad_argument_is_a_usage_error(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, {}, "--bogus")
    assert rc == 2 and "unknown argument" in out, out


def test_a_same_named_repository_under_another_owner_is_searched(tmp_path: Path) -> None:
    """Counter-model review: the map was keyed on NAME, so someone/claude-power-pack
    was handed cooneycw's #864 and never searched for its own store."""
    fork = "someone/claude-power-pack"
    rc, out = _run(tmp_path, {fork: {"7": OPEN_STORE, "864": {"state": "OPEN", "title": "unrelated"}}},
                   "--repo", fork)
    assert rc == 0 and "NIT_STORE=7" in out and "NIT_STORE_SOURCE=search" in out, out


def test_a_listing_that_fills_its_bound_is_unknown(tmp_path: Path) -> None:
    """Counter-model review: the exact-title filter runs after gh's bound, so a
    full page of near-matches can hide the store (or a second one)."""
    near = {str(n): {"state": "OPEN", "title": f"Nit Store follow-up {n}"} for n in range(1, 201)}
    near["500"] = OPEN_STORE
    rc, out = _run(tmp_path, {OTHER: near}, "--repo", OTHER)
    assert rc == 3 and "may be cut off" in out and "NIT_STORE=500" not in out, out
