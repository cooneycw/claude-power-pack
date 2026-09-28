"""scripts/remote-branch-sweep.py - report-first deletion of provably-landed branches (#1262).

Every test runs against a canned API fixture (`--api-fixture`); none reaches the
real remote. `delete` refuses a fixture outright, so no test can delete anything.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "remote-branch-sweep.py"
CONTROL = ROOT / "controls" / "remote-branch-sweep"
REPO = "o/r"
NOW = "2026-09-28T12:00:00Z"
OLD = "2026-09-01T00:00:00Z"
MAIN_TIP = "m" * 40


def sha(ch: str) -> str:
    return ch * 40


def fixture(*branches: dict) -> dict:
    """Build an API table. Each branch dict: name, tip, and optionally prs
    (list of {number, state, merged_at, head, merge_commit_sha}), pushed_at,
    protected, merge_on_main (bool | None for unreadable)."""
    table: dict[str, object] = {
        f"repos/{REPO}": {"default_branch": "main"},
        f"repos/{REPO}/branches?per_page=100": [
            {"name": "main", "commit": {"sha": MAIN_TIP}, "protected": True},
            *({"name": b["name"], "commit": {"sha": b["tip"]}, "protected": b.get("protected", False)}
              for b in branches),
        ],
    }
    for b in branches:
        name, tip = b["name"], b["tip"]
        table[f"repos/{REPO}/branches/{name}"] = {"name": name, "commit": {"sha": tip},
                                                  "protected": b.get("protected", False)}
        table[f"repos/{REPO}/pulls?state=all&head=o:{name}&per_page=100"] = [
            {"number": p["number"], "state": p["state"], "merged_at": p.get("merged_at"),
             "head": {"sha": p["head"]}, "merge_commit_sha": p.get("merge_commit_sha")}
            for p in b.get("prs", [])
        ]
        ref = f"refs%2Fheads%2F{name}"
        table[f"repos/{REPO}/activity?ref={ref}&per_page=1"] = [{"timestamp": b.get("pushed_at", OLD)}]
        table[f"repos/{REPO}/commits/{tip}"] = {"commit": {"committer": {"date": b.get("committed_at", OLD)}}}
        for p in b.get("prs", []):
            if p.get("merge_commit_sha") and "merge_on_main" in b and b["merge_on_main"] is not None:
                table[f"repos/{REPO}/compare/{p['merge_commit_sha']}...main"] = (
                    {"status": "ahead", "behind_by": 0} if b["merge_on_main"]
                    else {"status": "diverged", "behind_by": 3})
    return table


def landed(name: str = "issue-1-done", tip: str = sha("a")) -> dict:
    return {"name": name, "tip": tip, "merge_on_main": True,
            "prs": [{"number": 1, "state": "closed", "merged_at": OLD, "head": tip,
                     "merge_commit_sha": sha("1")}]}


def run(tmp_path: Path, table: dict, mode: str = "plan", *extra: str) -> subprocess.CompletedProcess:
    api = tmp_path / "api.json"
    api.write_text(json.dumps(table), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), mode, "--repo", REPO, "--api-fixture", str(api),
         "--now", NOW, *extra],
        capture_output=True, text=True,
    )


def decisions(out: str) -> dict[str, str]:
    found = {}
    for line in out.splitlines():
        if line.startswith(("SWEEP_DELETE: ", "SWEEP_REFUSED: ")):
            kind, _, rest = line.partition(": ")
            found[rest.split()[0]] = kind
    return found


def test_a_branch_at_its_merged_head_with_the_merge_on_main_is_DELETABLE(tmp_path):
    result = run(tmp_path, fixture(landed()))
    assert result.returncode == 1, result.stderr  # the default branch is always refused
    assert decisions(result.stdout)["issue-1-done"] == "SWEEP_DELETE"
    assert decisions(result.stdout)["main"] == "SWEEP_REFUSED"


@pytest.mark.parametrize(("branch", "reason"), [
    ({**landed(), "tip": sha("b")}, "moved after the merge"),
    ({**landed(), "merge_on_main": False}, "NOT on the default branch"),
    ({**landed(), "merge_on_main": None}, "unverifiable"),
    ({**landed(), "pushed_at": "2026-09-28T01:00:00Z"}, "pushed within 24h"),
    ({**landed(), "committed_at": "2026-09-28T01:00:00Z"}, "pushed within 24h"),
    ({**landed(), "protected": True}, "protected"),
    ({**landed(), "prs": [*landed()["prs"], {"number": 2, "state": "open", "head": sha("a")}]},
     "open PR #2"),
    ({"name": "wip", "tip": sha("c"), "prs": [{"number": 3, "state": "closed", "head": sha("c")}]},
     "closed without merging"),
    ({"name": "orphan", "tip": sha("d")}, "no PR has ever used"),
])
def test_every_unsafe_shape_is_REFUSED(tmp_path, branch, reason):
    result = run(tmp_path, fixture(branch))
    assert result.returncode == 1, result.stderr
    assert decisions(result.stdout)[branch["name"]] == "SWEEP_REFUSED", result.stdout
    line = next(ln for ln in result.stdout.splitlines() if ln.startswith(f"SWEEP_REFUSED: {branch['name']} "))
    assert reason in line, line


def test_the_NEWER_of_activity_and_committer_date_decides_recency(tmp_path):
    """An old committer date must not hide a recent push (a force-push of an old
    commit), and an unanswered activity API falls back to the commit date."""
    table = fixture({**landed(), "pushed_at": "2026-09-28T02:00:00Z", "committed_at": OLD})
    result = run(tmp_path, table)
    assert "pushed within 24h (activity)" in result.stdout
    table = fixture(landed())
    del table[f"repos/{REPO}/activity?ref=refs%2Fheads%2Fissue-1-done&per_page=1"]
    report = run(tmp_path, table, "report")
    assert "committer-date (activity API did not answer)" in report.stdout


def test_a_scanned_LOCAL_worktree_holding_the_branch_puts_it_in_d(tmp_path):
    repo = tmp_path / "co"
    subprocess.run(["git", "init", "-q", "-b", "issue-1-done", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "c"], check=True)
    result = run(tmp_path, fixture(landed()), "plan", "--checkout", str(repo))
    assert decisions(result.stdout)["issue-1-done"] == "SWEEP_REFUSED"
    assert "scanned local worktree" in result.stdout


def test_an_UNREADABLE_api_is_unknown_never_an_empty_clean_report(tmp_path):
    table = fixture(landed())
    table["__unreadable__"] = [f"repos/{REPO}/branches?per_page=100"]
    result = run(tmp_path, table, "report")
    assert result.returncode == 3
    assert "SWEEP: unknown" in result.stdout
    assert "(a) merged" not in result.stdout


def test_the_report_states_the_rule_its_authority_and_what_it_cannot_see(tmp_path):
    result = run(tmp_path, fixture(landed(), {"name": "orphan", "tip": sha("d")}), "report")
    out = result.stdout
    assert 'authorised this cleanup with "do 1262"' in out
    assert "master's narrowing" in out
    assert "not the operator's own wording" in out
    assert "git push origin <sha>:refs/heads/<name>" in out
    assert "Local worktrees scanned for category (d): 0 checkout(s)" in out
    assert "other hosts are not visible" in out
    assert "SWEEP: report examined=3 a=1 b=0 c=1 d=0 excluded=1" in out


def test_delete_REFUSES_a_fixture_and_requires_confirm_and_a_checkout(tmp_path):
    api = tmp_path / "api.json"
    api.write_text(json.dumps(fixture(landed())), encoding="utf-8")
    for args in (["--api-fixture", str(api), "--confirm", "--checkout", str(tmp_path)],
                 ["--checkout", str(tmp_path)],
                 ["--confirm"]):
        result = subprocess.run([sys.executable, str(SCRIPT), "delete", "--repo", REPO, *args],
                                capture_output=True, text=True)
        assert result.returncode == 2, (args, result.stdout, result.stderr)
