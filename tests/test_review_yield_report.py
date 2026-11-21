"""Fixture-only regression and committed negative controls for #1865."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/review-yield-report.py"
CONTRACT = ROOT / "docs/agents/closing-report-contract.md"
FIXTURES = ROOT / "tests/fixtures/review-yield-report"
SINCE, UNTIL = "2026-11-11", "2026-11-20"


def helper():
    assert SCRIPT.is_file(), "review-yield report implementation is missing"
    spec = importlib.util.spec_from_file_location("review_yield_report", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def data():
    return json.loads((FIXTURES / "provenance.json").read_text())


def report(value=None, contract=None):
    return helper().render(data() if value is None else value, SINCE, UNTIL,
                           CONTRACT.read_text() if contract is None else contract)


def test_committed_negative_control_flags_missing_but_not_present():
    value = data()
    issues = [pr["issues"][0] for pr in value["repos"]["cooneycw/example"]["prs"]]
    assert "Origin:" not in issues[0]["body"] and "Missed because:" not in issues[0]["body"]
    assert "Origin: #44" in issues[1]["body"]
    out = report(value)
    assert "#101: MISSING Origin, Missed because" in out
    assert "#102: recorded" in out
    assert "Earlier-work origins: 1" in out
    assert "no test covered it: 1" in out


def test_unreadable_is_unknown_and_not_zero_escapes():
    value = json.loads((FIXTURES / "unreadable.json").read_text())
    assert value["repos"]["cooneycw/example"]["prs"] is None
    out = report(value)
    assert "UNKNOWN" in out and "GitHub unavailable" in out
    assert "0 escapes" not in out
    assert "PRs readable: 0/unknown" in out


def test_readable_empty_is_distinct_from_unreadable():
    value = data()
    value["repos"]["cooneycw/example"]["prs"] = []
    out = report(value)
    assert "PRs readable: 0/0" in out
    assert "No merged fix(...) PRs in period" in out


@pytest.mark.parametrize("marker", ["defect-origin-answers", "defect-missed-answers"])
def test_missing_canonical_section_is_unknown(marker):
    contract = CONTRACT.read_text().replace(f"<!-- {marker} -->", "")
    assert f"<!-- {marker} -->" not in contract
    out = report(contract=contract)
    assert "UNKNOWN: canonical answer lists" in out
    assert "Earlier-work origins: 0" not in out


def test_latest_cumulative_receipt_per_issue_not_double_counted():
    out = report()
    assert "accepted: 3; rejected: 1; deferred: 1" in out
    assert "Issue #1: 2 passes" in out
    assert "1 older snapshot(s) omitted" in out


def test_date_boundaries_and_non_fix_prs():
    value = data()
    repo = value["repos"]["cooneycw/example"]
    for number, title, timestamp in [(103, "fix(core): too late", "2026-11-21T00:00:00Z"),
                                     (104, "feat(core): new", "2026-11-15T00:00:00Z")]:
        repo["prs"].append({"number": number, "title": title, "merged_at": timestamp, "issues": []})
    out = report(value)
    assert "#101:" in out and "#102:" in out
    assert "#103:" not in out and "#104:" not in out


def test_issue_comments_and_cross_repo_reference():
    value = data()
    issue = value["repos"]["cooneycw/example"]["prs"][0]["issues"][0]
    issue.update(repo="cooneycw/other", comments=["Origin: never worked\nMissed because: not a defect in earlier work"])
    out = report(value)
    assert "#101: recorded" in out and "cooneycw/other#1" in out


def test_partial_and_malformed_receipts_remain_unknown():
    value = data()
    repo = value["repos"]["cooneycw/example"]
    repo["receipts"].append({"issue": "2", "status": "ran", "recorded_at": "bad"})
    repo["errors"].append("receipt blob unreadable")
    out = report(value)
    assert "UNKNOWN" in out and "receipt blob unreadable" in out
    assert "Receipts readable: 2/3" in out


def test_missing_receipt_directory_is_unknown():
    value = data()
    value["repos"]["cooneycw/example"]["receipts"] = None
    out = report(value)
    assert "Review yield: UNKNOWN" in out


def test_unknown_answer_and_conflicts_are_not_valid_provenance():
    value = data()
    issue = value["repos"]["cooneycw/example"]["prs"][0]["issues"][0]
    issue["body"] = "Origin: made up\nMissed because: made up"
    issue["comments"] = ["Origin: #4", "Origin: #5"]
    out = report(value)
    assert "#101: INVALID" in out


def test_collector_api_failure_is_unknown():
    mod = helper()
    def broken(args):
        raise mod.ReadError("rate limited")
    value = mod.collect_repo(broken, "cooneycw/example", SINCE, UNTIL)
    assert value["prs"] is None and value["receipts"] is None
    assert any("rate limited" in error for error in value["errors"])


def test_pagination_keeps_pages_and_rejects_partial_page():
    mod = helper()
    calls = []
    def api(args):
        calls.append(args)
        return list(range(100)) if args[0].endswith("&page=1") else [100]
    assert len(mod.pages(api, "repos/o/r/issues/1/comments")) == 101
    assert len(calls) == 2
    def broken(args):
        if args[0].endswith("&page=1"):
            return list(range(100))
        raise mod.ReadError("page two failed")
    with pytest.raises(mod.ReadError, match="page two"):
        mod.pages(broken, "repos/o/r/issues/1/comments")


@pytest.mark.skipif(shutil.which("python3") is None, reason="requires python3")
def test_cli_from_other_directory_reads_real_fixture_output(tmp_path):  # binary-guard: allow fixtures never call gh
    assert SCRIPT.is_file(), "review-yield report implementation is missing"
    done = subprocess.run([sys.executable, str(SCRIPT), "--since", SINCE, "--until", UNTIL,
                           "--fixture", str(FIXTURES / "provenance.json")],
                          cwd=tmp_path, text=True, capture_output=True)
    assert done.returncode == 0, done.stderr
    assert "#101: MISSING" in done.stdout and "#102: recorded" in done.stdout


def test_malformed_fixture_shape_is_unknown_not_traceback():
    out = report({"repos": {"cooneycw/example": {"prs": [None], "receipts": [None]}}})
    assert "UNKNOWN" in out


def test_collector_success_reads_pinned_receipts_and_closed_issue_comments():
    import base64
    mod = helper()
    fixture = data()["repos"]["cooneycw/example"]
    calls = []
    def api(args):
        calls.append(args)
        path = args[0]
        if path.startswith("search/issues?"):
            return {"total_count": 1, "incomplete_results": False,
                    "items": [{"number": 102, "title": "fix(core): explained"}]}
        if path == "repos/cooneycw/example/pulls/102":
            return {"merged_at": "2026-11-20T23:59:59Z"}
        if path == "graphql":
            return {"data": {"repository": {"pullRequest": {"closingIssuesReferences": {
                "nodes": [{"number": 2, "repository": {"nameWithOwner": "cooneycw/other"}}],
                "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}}
        if path == "repos/cooneycw/other/issues/2":
            return {"body": "Origin: #44"}
        if path.startswith("repos/cooneycw/other/issues/2/comments?"):
            return [{"body": "Missed because: no test covered it"}]
        if path == "repos/cooneycw/example/commits/main":
            return {"sha": "pinned-main"}
        if path == "repos/cooneycw/example/git/trees/pinned-main?recursive=1":
            return {"truncated": False, "tree": [{"path": "docs/measurements/counter-model/a.json",
                                                  "sha": "receipt-blob", "type": "blob"}]}
        if path == "repos/cooneycw/example/git/blobs/receipt-blob":
            return {"encoding": "base64", "content": base64.b64encode(
                json.dumps(fixture["receipts"][1]).encode()).decode()}
        raise AssertionError(f"unhandled API request: {args}")
    collected = mod.collect_repo(api, "cooneycw/example", SINCE, UNTIL)
    assert collected["errors"] == []
    out = report({"repos": {"cooneycw/example": collected}})
    assert "#102: recorded (cooneycw/other#2)" in out
    assert "Receipt main snapshot: pinned-main" in out
    assert all(not any(arg in ("PATCH", "PUT", "DELETE") for arg in call) for call in calls)


def test_collector_truncated_search_and_tree_are_unknown():
    mod = helper()
    def api(args):
        if args[0].startswith("search/issues?"):
            return {"total_count": 1001, "incomplete_results": False, "items": []}
        if args[0].endswith("commits/main"):
            return {"sha": "main-sha"}
        return {"truncated": True, "tree": []}
    value = mod.collect_repo(api, "cooneycw/example", SINCE, UNTIL)
    assert value["prs"] is None and value["receipts"] is None
    out = report({"repos": {"cooneycw/example": value}})
    assert "UNKNOWN" in out and "1000-result bound" in out and "tree incomplete" in out


def test_closing_issue_connection_paginates_and_checks_graphql_errors():
    mod = helper()
    calls = []
    def api(args):
        calls.append(args)
        second = "cursor=next" in args
        return {"data": {"repository": {"pullRequest": {"closingIssuesReferences": {
            "nodes": [{"number": 2 if second else 1}],
            "pageInfo": {"hasNextPage": not second, "endCursor": None if second else "next"}}}}}}
    assert mod.closed_issues(api, "o/r", 1) == [{"number": 1}, {"number": 2}]
    assert len(calls) == 2
    with pytest.raises(mod.ReadError, match="GraphQL returned errors"):
        mod.closed_issues(lambda args: {"errors": [{"message": "rate limited"}]}, "o/r", 1)


def test_blank_line_does_not_consume_next_field():
    value = data()
    issue = value["repos"]["cooneycw/example"]["prs"][0]["issues"][0]
    issue["body"] = "Origin:\nMissed because: no test covered it"
    assert issue["body"].startswith("Origin:\n")
    out = report(value)
    assert "#101: MISSING Origin" in out
    assert "no test covered it: 2" in out


@pytest.mark.skipif(shutil.which("python3") is None, reason="requires python3")
def test_generated_codex_bundle_uses_real_script_and_canonical_contract(tmp_path):
    spec = importlib.util.spec_from_file_location("yield_codex_sync", ROOT / "scripts/codex-skill-sync.py")
    assert spec and spec.loader
    sync = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = sync
    spec.loader.exec_module(sync)
    generated = sync.generate_skill(ROOT / ".claude/commands/monthly/create.md", "monthly",
                                    sync.generated_names(["monthly"]))
    assert "docs/agents/closing-report-contract.md" in generated
    assert "scripts/review-yield-report.py" in generated
    for relative, text in generated.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    done = subprocess.run([sys.executable, str(tmp_path / "scripts/review-yield-report.py"),
                           "--since", SINCE, "--until", UNTIL, "--fixture", str(FIXTURES / "provenance.json")],
                          cwd=tmp_path, capture_output=True, text=True)
    assert done.returncode == 0
    assert "#101: MISSING" in done.stdout and "#102: recorded" in done.stdout
    assert "UNKNOWN" not in done.stdout.split("## cooneycw/example")[0]


def test_unreadable_linked_issue_does_not_count_as_readable_pr():
    value = data()
    issue = value["repos"]["cooneycw/example"]["prs"][0]["issues"][0]
    issue["comments"] = None
    assert issue["comments"] is None
    out = report(value)
    assert "PRs readable: 1/2" in out and "issue body/comments unreadable" in out


@pytest.mark.parametrize("location", ["body", "comments"])
def test_crlf_provenance_matches_lf(location):
    value = data()
    issue = value["repos"]["cooneycw/example"]["prs"][1]["issues"][0]
    text = issue["body"].replace("\n", "\r\n") + "\r\n"
    assert "\r\n" in text
    issue.update(body=text if location == "body" else "", comments=[text] if location == "comments" else [])
    out = report(value)
    assert "#102: recorded" in out
    assert "Earlier-work origins: 1" in out
    assert "no test covered it: 1" in out


@pytest.mark.skipif(shutil.which("git") is None, reason="requires git")
@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
@pytest.mark.skipif(shutil.which("python3") is None, reason="requires python3")
def test_claude_install_in_main_and_worktree(tmp_path):
    import os
    checkout = tmp_path / "main"
    checkout.mkdir()
    for relative in ("scripts/review-yield-report.py", "docs/agents/closing-report-contract.md"):
        source = ROOT / relative
        assert source.is_file(), f"implementation source missing: {relative}"
        target = checkout / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    def git(*args):
        return subprocess.run(["git", "-C", str(checkout), *args], capture_output=True, text=True, check=True)
    git("init")
    git("add", ".")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
    linked = tmp_path / "linked"
    git("worktree", "add", "--detach", str(linked), "HEAD")
    for layout in (checkout, linked):
        private_home = tmp_path / f"home-{layout.name}"
        installed = private_home / ".claude/scripts/review-yield-report.py"
        installed.parent.mkdir(parents=True)
        env = dict(os.environ, HOME=str(private_home))
        env.pop("CPP_DEFER_SURFACES", None)
        install = subprocess.run(["bash", str(ROOT / "scripts/cpp-host-write.sh"), "link-into",
                                  str(layout / "scripts/review-yield-report.py"),
                                  str(installed.parent), installed.name],
                                 env=env, text=True, capture_output=True)
        assert install.returncode == 0, install.stderr
        assert installed.is_symlink() and installed.resolve() == layout / "scripts/review-yield-report.py"
        done = subprocess.run([sys.executable, str(installed), "--since", SINCE, "--until", UNTIL,
                               "--fixture", str(FIXTURES / "provenance.json")],
                              cwd=private_home, env=env, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        assert "#101: MISSING" in done.stdout and "#102: recorded" in done.stdout


def test_real_1691_independent_branches_are_both_counted():
    value = data()
    receipts = [json.loads((FIXTURES / name).read_text())
                for name in ("1691-first-run.json", "1691-second-run.json")]
    assert receipts[0]["branch"] != receipts[1]["branch"]
    value["repos"]["cooneycw/example"]["receipts"] = receipts
    out = report(value)
    assert "accepted: 5; rejected: 0; deferred: 0" in out
    assert "Issue #1691: 3 passes" in out
    assert "0 older snapshot(s) omitted" in out


def test_duplicate_historical_receipts_without_run_identity_are_unknown():
    value = data()
    receipts = value["repos"]["cooneycw/example"]["receipts"]
    for receipt in receipts:
        receipt.pop("branch", None)
        receipt.pop("implementer_evidence", None)
    assert all("branch" not in receipt and "implementer_evidence" not in receipt for receipt in receipts)
    out = report(value)
    assert "UNKNOWN: ambiguous run identity for issue #1" in out
    assert "accepted: 3;" not in out


def test_malformed_search_candidate_preserves_later_fix_and_denominator():
    mod = helper()
    def api(args):
        path = args[0]
        if path.startswith("search/issues?"):
            return {"total_count": 2, "incomplete_results": False,
                    "items": [{}, {"number": 102, "title": "fix(core): readable"}]}
        if path.endswith("pulls/102"):
            return {"merged_at": "2026-11-20T12:00:00Z"}
        if path == "graphql":
            return {"data": {"repository": {"pullRequest": {"closingIssuesReferences": {
                "nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}}
        raise mod.ReadError("receipt source unavailable")
    value = mod.collect_repo(api, "cooneycw/example", SINCE, UNTIL)
    out = report({"repos": {"cooneycw/example": value}})
    assert "#102: MISSING linked closing issue" in out
    assert "PRs readable: 1/2" in out
    assert "No merged fix(...) PRs in period" not in out
    assert "UNKNOWN" in out


def test_separate_implementer_sessions_in_one_branch_are_independent():
    value = data()
    receipts = value["repos"]["cooneycw/example"]["receipts"]
    receipts[1]["implementer_evidence"]["thread_id"] = "another-fixture-session"
    assert receipts[0]["implementer_evidence"] != receipts[1]["implementer_evidence"]
    out = report(value)
    assert "accepted: 5; rejected: 2; deferred: 1" in out
    assert "Issue #1: 3 passes" in out


def test_repeated_branch_without_session_identity_is_ambiguous():
    value = data()
    receipts = value["repos"]["cooneycw/example"]["receipts"]
    for receipt in receipts:
        receipt.pop("implementer_evidence")
    assert all("implementer_evidence" not in receipt for receipt in receipts)
    out = report(value)
    assert "UNKNOWN: ambiguous run identity for issue #1, branch fixture-issue-1" in out
    assert "accepted: 3;" not in out
