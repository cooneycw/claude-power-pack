"""Fixture-only regression and committed negative controls for #1865."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get("CPP_REVIEW_YIELD_TEST_SCRIPT", ROOT / "scripts" / "review-yield-report.py"))
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


def title_populations():
    return json.loads((FIXTURES / "title-populations.json").read_text())


def title_population_data():
    value = data()
    value["repos"]["cooneycw/example"]["prs"] = [
        {"number": row["number"], "title": row["title"],
         "merged_at": "2026-11-15T00:00:00Z", "issues": []}
        for row in title_populations()["cases"]]
    return value


def test_title_population_collector_old_and_new_side_by_side():
    mod = helper()
    fixture = title_populations()
    calls = []

    def api(args):
        path = args[0]
        if path.startswith("search/issues?"):
            return {"total_count": len(fixture["cases"]), "incomplete_results": False,
                    "items": fixture["cases"]}
        if "/pulls/" in path:
            calls.append(int(path.rsplit("/", 1)[1]))
            return {"merged_at": "2026-11-15T00:00:00Z"}
        if path == "graphql":
            return {"data": {"repository": {"pullRequest": {"closingIssuesReferences": {
                "nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}}
        return pinned_api(args)

    assert fixture["old_numbers"] == [201, 202]
    assert fixture["new_numbers"] == [201, 202, 203, 204]
    value = mod.collect_repo(api, "cooneycw/example", SINCE, UNTIL,
                             archive_reader=lambda *_: pinned_archive())
    assert value["receipts"] is not None  # The archive also carries its existing malformed receipt.
    assert [pr["number"] for pr in value["prs"]] == fixture["new_numbers"]
    assert calls == fixture["new_numbers"]  # Excluded titles never fetch PR details.
    out = report({"repos": {"cooneycw/example": value}})
    assert "PRs readable: 4/4" in out
    for row in fixture["cases"]:
        assert (f"- #{row['number']}:" in out) is row["new"]


def test_title_population_render_accepts_only_the_expanded_forms():
    fixture = title_populations()
    out = report(title_population_data())
    assert "PRs readable: 4/12" in out
    for row in fixture["cases"]:
        assert (f"- #{row['number']}:" in out) is row["new"]


def test_title_population_unchanged_rows_match_frozen_predecessor_bytes():
    fixture = title_populations()
    value = json.loads((FIXTURES / fixture["unchanged_input"]).read_text())
    assert (report(value) + "\n").encode() == fixture["unchanged_report"].encode()


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
    import hashlib
    mod = helper()
    fixture = data()["repos"]["cooneycw/example"]
    content = json.dumps(fixture["receipts"][1]).encode()
    oid = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
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
                                                  "sha": oid, "type": "blob"}]}
        raise AssertionError(f"unhandled API request: {args}")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        member = tarfile.TarInfo('root/docs/measurements/counter-model/a.json')
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))
    collected = mod.collect_repo(api, "cooneycw/example", SINCE, UNTIL,
                                 archive_reader=lambda *_: stream.getvalue())
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
@pytest.mark.parametrize("expanded", [False, True])
def test_generated_codex_bundle_uses_real_script_and_canonical_contract(tmp_path, expanded):
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
    fixture = FIXTURES / "provenance.json"
    if expanded:
        fixture = tmp_path / "titles.json"
        fixture.write_text(json.dumps(title_population_data()))
    done = subprocess.run([sys.executable, str(tmp_path / "scripts/review-yield-report.py"),
                           "--since", SINCE, "--until", UNTIL, "--fixture", str(fixture)],
                          cwd=tmp_path, capture_output=True, text=True)
    assert done.returncode == 0
    if expanded:
        assert "#203: MISSING" in done.stdout and "#204: MISSING" in done.stdout
        assert "PRs readable: 4/12" in done.stdout
    else:
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
@pytest.mark.parametrize("expanded", [False, True])
def test_claude_install_in_main_and_worktree(tmp_path, expanded):
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
    fixture = FIXTURES / "provenance.json"
    if expanded:
        fixture = tmp_path / "titles.json"
        fixture.write_text(json.dumps(title_population_data()))
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
                               "--fixture", str(fixture)],
                              cwd=private_home, env=env, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        if expanded:
            assert "#203: MISSING" in done.stdout and "#204: MISSING" in done.stdout
            assert "PRs readable: 4/12" in done.stdout
        else:
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


def kind_fixture_report(name):
    receipt = json.loads((FIXTURES / name).read_text())
    value = {"repos": {"fixture/repo": {"prs": [], "receipts": [receipt], "errors": []}}}
    return receipt, helper().render(value, "2026-11-27", "2026-11-27", CONTRACT.read_text())


def test_historical_kind_counts_are_unknown_not_zero():
    receipt, out = kind_fixture_report("pre-kind-schema5-receipt.json")
    assert "counts_by_kind" not in receipt and receipt["schema"] == 5
    assert "selected-report kinds: UNKNOWN" in out
    assert "Selected-report kinds coverage: 0/1 measured; 0/1 carry counts_by_kind" in out
    for kind in ("correctness", "security", "edge-case", "test-adequacy",
                 "plan-bookkeeping", "simplification", "unstated"):
        assert f"{kind}: 0" not in out


def test_three_pass_selected_report_is_not_cumulative():
    receipt, out = kind_fixture_report("three-pass-selected-report.json")
    assert receipt["passes"] == 3 and sum(receipt["counts_by_kind"]["kinds"].values()) == 1
    assert "selected-report kinds: correctness: 1;" in out
    assert "correctness: 3" not in out
    assert "Selected-report kinds coverage: 1/1 measured; 1/1 carry counts_by_kind" in out
    assert "Cumulative kinds: UNKNOWN" in out


@pytest.mark.parametrize("change", [
    "negative", "bool", "missing-kind", "unknown-kind", "wrong-scope", "wrong-record",
    "bool-artifact-record", "float-schema", "missing-kinds", "null-kinds",
])
def test_malformed_selected_report_kinds_are_unknown(change):
    receipt = json.loads((FIXTURES / "three-pass-selected-report.json").read_text())
    value = receipt["counts_by_kind"]
    assert value["scope"] == "selected_report" and value["kinds"]["correctness"] == 1
    if change == "negative":
        value["kinds"]["correctness"] = -1
    elif change == "bool":
        value["kinds"]["correctness"] = True
    elif change == "missing-kind":
        del value["kinds"]["correctness"]
    elif change == "unknown-kind":
        value["kinds"]["invented"] = 1
    elif change == "wrong-scope":
        value["scope"] = "cumulative"
    elif change == "wrong-record":
        value["report_record"] += 1
    elif change == "bool-artifact-record":
        value["report_record"] = 1
        receipt["reviewed_artifact"]["report_record"] = True
    elif change == "float-schema":
        receipt["schema"] = 5.0
    elif change == "missing-kinds":
        del value["kinds"]
    else:
        value["kinds"] = None
    record = {"repos": {"fixture/repo": {"prs": [], "receipts": [receipt], "errors": []}}}
    out = helper().render(record, "2026-11-27", "2026-11-27", CONTRACT.read_text())
    assert "selected-report kinds: UNKNOWN" in out
    assert "Selected-report kinds coverage: 0/1 measured; 1/1 carry counts_by_kind" in out
    assert "correctness: 0" not in out


def test_selected_kind_reader_unavailable_is_unknown(tmp_path, monkeypatch):
    mod = helper()
    monkeypatch.setattr(mod, "__file__", str(tmp_path / "report.py"))
    assert not (tmp_path / "counter-model-receipt.py").exists()
    receipt = json.loads((FIXTURES / "three-pass-selected-report.json").read_text())
    rows = "\n".join(mod.selected_kind_rows([receipt]))
    assert "selected-report kinds: UNKNOWN" in rows
    assert "0/1 measured; 1/1 carry counts_by_kind" in rows


def test_generated_monthly_bundle_reads_selected_kinds(tmp_path):
    spec = importlib.util.spec_from_file_location("kind_bundle_sync", ROOT / "scripts/codex-skill-sync.py")
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    files = sync.generate_skill(ROOT / ".claude/commands/monthly/create.md", "monthly",
                                sync.generated_names(["monthly"]))
    bundle = tmp_path / "monthly-create"
    for name, content in files.items():
        dest = bundle / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    receipt = json.loads((FIXTURES / "three-pass-selected-report.json").read_text())
    fixture = tmp_path / "input.json"
    fixture.write_text(json.dumps({"repos": {"fixture/repo": {"prs": [], "receipts": [receipt], "errors": []}}}))
    result = subprocess.run(  # binary-guard: allow fixture-only report never calls gh/git
        [sys.executable, str(bundle / "scripts/review-yield-report.py"), "--since", "2026-11-27",
         "--until", "2026-11-27", "--fixture", str(fixture)],
        capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "selected-report kinds: correctness: 1;" in result.stdout
    assert "Selected-report kinds coverage: 1/1 measured; 1/1 carry counts_by_kind" in result.stdout


PINNED = FIXTURES / 'pinned-tree'
PIN = 'a' * 40


def pinned_api(args):
    path = args[0]
    if path.startswith('search/issues?'):
        return {'total_count': 0, 'incomplete_results': False, 'items': []}
    if path.endswith('/commits/main'):
        return {'sha': PIN}
    if path == f'repos/cooneycw/example/git/trees/{PIN}?recursive=1':
        return json.loads((PINNED / 'tree.json').read_text())
    raise AssertionError(f'unexpected API call (including serial blobs): {args}')


def pinned_archive(extra=None, omit=None, change=None):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for entry in json.loads((PINNED / 'tree.json').read_text())['tree']:
            name = entry['path']
            if name == omit:
                continue
            content = (PINNED / name).read_bytes()
            if name == change:
                content += b' '
            member = tarfile.TarInfo('fixture-root/' + name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        if extra:
            name, kind = extra
            member = tarfile.TarInfo(name)
            if kind == 'symlink':
                member.type = tarfile.SYMTYPE
                member.linkname = '../../outside'
            archive.addfile(member, io.BytesIO(b''))
    return stream.getvalue()


def test_pinned_archive_output_matches_committed_prechange_bytes():
    calls = []
    def reader(repo, commit):
        calls.append((repo, commit))
        return pinned_archive()
    collected = helper().collect_repo(pinned_api, 'cooneycw/example', SINCE, UNTIL,
                                     archive_reader=reader)
    assert calls == [('cooneycw/example', PIN)]
    assert (report({'repos': {'cooneycw/example': collected}}) + '\n').encode() == (PINNED / 'expected.md').read_bytes()
    assert len(collected['receipts']) == 6  # Includes malformed and out-of-period records.


@pytest.mark.parametrize('name', json.loads((PINNED / 'unsafe-names.json').read_text()))
def test_pinned_archive_refuses_committed_malicious_member_names(name):
    assert name.startswith('/') or '..' in name.split('/')
    value = helper().collect_repo(pinned_api, 'cooneycw/example', SINCE, UNTIL,
                                 archive_reader=lambda *_: pinned_archive(extra=(name, 'file')))
    assert value['receipts'] is None
    assert value['receipt_source_failed'] is True
    assert 'UNKNOWN' in report({'repos': {'cooneycw/example': value}})


@pytest.mark.parametrize('fault', ['missing', 'unreadable', 'mismatch', 'symlink'])
def test_pinned_archive_failures_are_unknown_and_nonzero(fault, monkeypatch, capsys):
    first = json.loads((PINNED / 'tree.json').read_text())['tree'][0]['path']
    assert (PINNED / first).is_file()
    def reader(*_):
        if fault == 'unreadable':
            raise helper().ReadError('archive unavailable')
        if fault == 'missing':
            return pinned_archive(omit=first)
        if fault == 'mismatch':
            return pinned_archive(change=first)
        return pinned_archive(omit=first, extra=('fixture-root/' + first, 'symlink'))
    mod = helper()
    # Use the same module's exception class for the unreadable transport.
    if fault == 'unreadable':
        def reader(*_):
            raise mod.ReadError('archive unavailable')
    monkeypatch.setattr(mod, 'gh_api', pinned_api)
    monkeypatch.setattr(mod, 'gh_archive', reader)
    assert mod.main(['--since', SINCE, '--until', UNTIL, '--repo', 'cooneycw/example']) != 0
    assert 'UNKNOWN' in capsys.readouterr().out


def test_archive_transport_requests_exact_commit_once(monkeypatch):
    mod = helper()
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=b'archive-bytes')
    monkeypatch.setattr(mod.subprocess, 'run', run)
    assert mod.gh_archive('cooneycw/example', PIN) == b'archive-bytes'
    assert len(calls) == 1
    assert calls[0][0] == ['gh', 'api', f'repos/cooneycw/example/tarball/{PIN}']
    assert calls[0][1].get('text', False) is False


@pytest.mark.parametrize('fault', ['exit', 'timeout', 'oserror'])
def test_archive_transport_failure_is_readerror(fault, monkeypatch):
    mod = helper()
    def run(command, **kwargs):
        if fault == 'timeout':
            raise subprocess.TimeoutExpired(command, 120)
        if fault == 'oserror':
            raise OSError('transport unavailable')
        return subprocess.CompletedProcess(command, 1, stdout=b'')
    monkeypatch.setattr(mod.subprocess, 'run', run)
    with pytest.raises(mod.ReadError, match='archive (unavailable|unreadable)'):
        mod.gh_archive('cooneycw/example', PIN)


@pytest.mark.parametrize('fault', ['invalid-tar', 'duplicate', 'multiple-roots'])
def test_archive_container_failures_are_unknown(fault):
    if fault == 'invalid-tar':
        content = b'not a gzip archive'
        assert not content.startswith(b'\x1f\x8b')
    else:
        first = json.loads((PINNED / 'tree.json').read_text())['tree'][0]['path']
        name = ('fixture-root/' if fault == 'duplicate' else 'other-root/') + first
        content = pinned_archive(extra=(name, 'file'))
    value = helper().collect_repo(pinned_api, 'cooneycw/example', SINCE, UNTIL,
                                 archive_reader=lambda *_: content)
    assert value['receipt_source_failed'] is True
    assert value['receipts'] is None


def test_archive_ignores_unrelated_symlink_without_extraction(monkeypatch):
    mod = helper()
    def forbidden(*args, **kwargs):
        raise AssertionError('archive extraction must never occur')
    monkeypatch.setattr(tarfile.TarFile, 'extract', forbidden)
    monkeypatch.setattr(tarfile.TarFile, 'extractall', forbidden)
    value = mod.collect_repo(pinned_api, 'cooneycw/example', SINCE, UNTIL,
                            archive_reader=lambda *_: pinned_archive(extra=('fixture-root/unrelated/link', 'symlink')))
    assert not value.get('receipt_source_failed')
    assert (report({'repos': {'cooneycw/example': value}}) + '\n').encode() == (PINNED / 'expected.md').read_bytes()


def test_archive_keeps_original_pin_when_main_moves():
    calls = []
    def api(args):
        calls.append(args[0])
        assert calls.count('repos/cooneycw/example/commits/main') <= 1
        return pinned_api(args)
    def archive(repo, commit):
        assert commit == PIN
        # A second main read would observe a different snapshot. Never request it.
        return pinned_archive()
    value = helper().collect_repo(api, 'cooneycw/example', SINCE, UNTIL, archive_reader=archive)
    assert value['receipt_head'] == PIN
    assert (report({'repos': {'cooneycw/example': value}}) + '\n').encode() == (PINNED / 'expected.md').read_bytes()


def test_missing_pinned_tree_cli_is_unknown_nonzero(monkeypatch, capsys):
    mod = helper()
    def api(args):
        if '/git/trees/' in args[0]:
            raise mod.ReadError('pinned tree is missing')
        return pinned_api(args)
    monkeypatch.setattr(mod, 'gh_api', api)
    assert mod.main(['--since', SINCE, '--until', UNTIL, '--repo', 'cooneycw/example']) == 1
    out = capsys.readouterr().out
    assert 'UNKNOWN' in out and 'pinned tree is missing' in out
    assert 'Receipts readable: 0/unknown' in out


@pytest.mark.skipif(shutil.which('python3') is None, reason='requires python3')
@pytest.mark.parametrize('generated', [False, True])
@pytest.mark.parametrize('unavailable', [False, True])
def test_pinned_archive_real_cli_and_generated_reader(tmp_path, monkeypatch, generated, unavailable):
    script = SCRIPT
    if generated:
        spec = importlib.util.spec_from_file_location('archive_bundle', ROOT / 'scripts/codex-skill-sync.py')
        sync = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sync)
        for name, content in sync.generate_skill(ROOT / '.claude/commands/monthly/create.md', 'monthly',
                                                sync.generated_names(['monthly'])).items():
            target = tmp_path / 'bundle' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        script = tmp_path / 'bundle/scripts/review-yield-report.py'
    archive = tmp_path / 'snapshot.tar.gz'
    archive.write_bytes(pinned_archive())
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    calls = tmp_path / 'calls.jsonl'
    fake = bindir / 'gh'
    fake.write_text(f'''#!{sys.executable}
import json,sys
from pathlib import Path
endpoint=sys.argv[2]
with Path({str(calls)!r}).open('a') as stream:
    stream.write(json.dumps(endpoint)+'\\n')
if endpoint.startswith('search/issues?'):
    print(json.dumps({{'total_count':0,'incomplete_results':False,'items':[]}}))
elif endpoint.endswith('/commits/main'):
    print(json.dumps({{'sha':{PIN!r}}}))
elif '/git/trees/' in endpoint:
    print(Path({str(PINNED / 'tree.json')!r}).read_text())
elif endpoint == 'repos/cooneycw/example/tarball/{PIN}':
    if {unavailable!r}:
        sys.exit(1)
    sys.stdout.buffer.write(Path({str(archive)!r}).read_bytes())
else:
    sys.exit(9)
''')
    fake.chmod(0o755)
    monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
    result = subprocess.run(  # binary-guard: allow fixture-owned gh transport, no network or real gh/git
        [sys.executable, str(script), '--since', SINCE, '--until', UNTIL, '--repo', 'cooneycw/example'],
        capture_output=True, cwd=tmp_path)
    observed = [json.loads(row) for row in calls.read_text().splitlines()]
    assert len(observed) == 4
    assert observed[-1] == f'repos/cooneycw/example/tarball/{PIN}'
    assert not any('/git/blobs/' in call for call in observed)
    if unavailable:
        assert result.returncode == 1
        assert b'UNKNOWN' in result.stdout and b'Receipts readable: 0/unknown' in result.stdout
    else:
        assert result.returncode == 0, result.stderr
        assert result.stdout == (PINNED / 'expected.md').read_bytes()
