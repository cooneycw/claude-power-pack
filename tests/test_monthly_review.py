"""The monthly review's shared rules and helper (issue #1703).

Every source the scan reads has three answers - due, clear, unread - and the
review's own state has four. The cases below reach each one by an INPUT (a
stubbed command runner, a file, a date), because the failure this exists to
prevent is a quiet one: an unreadable source that reads like "nothing due", or
an unreadable listing that reads like "no review this month" and produces a
second review.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lib.monthly_review as mr  # noqa: E402

SCRIPT = ROOT / "scripts" / "monthly-review.py"
SPEC = importlib.util.spec_from_file_location("monthly_review_helper", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
helper = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helper
SPEC.loader.exec_module(helper)

TODAY = date(2026, 12, 9)
RESOLVER = Path("nit-store-resolve.sh")


def _review(number: int, month: str, *, body: str = "", created: str = "2026-12-01T00:00:00Z") -> dict:
    return {"number": number, "title": f"Monthly review: {month}", "labels": [{"name": "monthly-review"}],
            "createdAt": created, "body": body}


class Runner:
    """Answers by matching a fragment of the command; records every call.

    A command no rule matches FAILS (exit 1): an unstubbed read must never look
    like an empty answer, or a test could pass by not being asked.
    """

    def __init__(self, rules: dict[str, tuple[int, str]]):
        self.rules = rules
        self.calls: list[list[str]] = []

    def __call__(self, command):
        command = list(command)
        self.calls.append(command)
        joined = " ".join(command)
        for fragment, answer in self.rules.items():
            if fragment in joined:
                return answer
        return 1, ""


# --------------------------------------------------------------------------- #
# The review's state


def test_no_review_this_month_is_none_and_routes_to_create() -> None:
    state = mr.review_state([], [], TODAY)
    assert state.verdict == "none" and state.month == "2026-12" and state.route == "/monthly:create"


def test_an_open_review_is_open_with_its_item_counts() -> None:
    body = "- [ ] one\n- [x] two\n- [ ] three\n"
    state = mr.review_state([_review(40, "2026-12", body=body)], [], TODAY)
    assert (state.verdict, state.number, state.open_items, state.total_items) == ("open", 40, 2, 3)
    assert state.age_days == 8 and state.route == "/monthly:review"
    assert "OVERDUE" not in state.line()


def test_last_months_open_review_is_overdue_not_a_reason_to_create_another() -> None:
    state = mr.review_state([_review(31, "2026-11", created="2026-11-02T00:00:00Z")], [], TODAY)
    assert state.verdict == "open" and state.review_month == "2026-11"
    assert "OVERDUE" in state.line() and state.route == "/monthly:review"


def test_a_review_closed_this_month_is_done_not_none() -> None:
    state = mr.review_state([], [_review(40, "2026-12")], TODAY)
    assert state.verdict == "done" and state.number == 40 and state.route == ""


def test_a_review_closed_last_month_does_not_cover_this_one() -> None:
    assert mr.review_state([], [_review(31, "2026-11")], TODAY).verdict == "none"


def test_an_unread_closed_listing_is_unknown_never_none() -> None:
    """The case the whole state machine exists for: `none` asks for a new issue."""
    state = mr.review_state([], None, TODAY, unknown_reason="gh failed")
    assert state.verdict == "unknown" and state.route == ""
    assert "gh failed" in state.line() and "NOT evidence" in state.line()


def test_an_unread_open_listing_is_unknown() -> None:
    assert mr.review_state(None, [], TODAY).verdict == "unknown"


def test_an_issue_without_the_label_is_not_a_review_whatever_its_title() -> None:
    lookalike = {"number": 9, "title": "Monthly review: 2026-12", "labels": [{"name": "enhancement"}]}
    assert mr.review_state([lookalike], [], TODAY).verdict == "none"


# --------------------------------------------------------------------------- #
# The scan: each source, each answer


def _nit(status: str, number: int | None = None) -> tuple[int, str]:
    head = f"NIT_STORE={number}\n" if number else ""
    return (0 if status.startswith("ok") else 3, f"{head}NIT_STORE_STATUS: {status}\n")


def test_nit_store_with_findings_is_due() -> None:
    comments = json.dumps({"comments": [{}] * 12, "createdAt": "2026-11-12T00:00:00Z"})
    runner = Runner({"nit-store-resolve": _nit("ok", 77), "issue view 77": (0, comments)})
    items, store = mr.scan_nit_store(runner, RESOLVER, TODAY)
    assert store == 77 and [i.state for i in items] == ["due"]
    assert "#77: 12 finding(s), opened 27d ago" in items[0].text


def test_an_empty_nit_store_is_clear() -> None:
    empty = json.dumps({"comments": [], "createdAt": "2026-12-01T00:00:00Z"})
    runner = Runner({"nit-store-resolve": _nit("ok", 77), "issue view 77": (0, empty)})
    assert [i.state for i in mr.scan_nit_store(runner, RESOLVER, TODAY)[0]] == ["clear"]


def test_no_nit_store_is_clear_not_an_error() -> None:
    runner = Runner({"nit-store-resolve": (1, "NIT_STORE_STATUS: none - no open issue; file normally\n")})
    items, store = mr.scan_nit_store(runner, RESOLVER, TODAY)
    assert store is None and items[0].state == "clear" and "no open Nit Store" in items[0].text


@pytest.mark.parametrize("rules", [
    {"nit-store-resolve": (3, "NIT_STORE_STATUS: unknown - gh could not list\n")},
    {"nit-store-resolve": (127, "")},
    {"nit-store-resolve": _nit("ok", 77)},  # resolved, but the issue read fails
    {"nit-store-resolve": _nit("ok", 77), "issue view 77": (0, "not json")},
])
def test_a_nit_store_that_cannot_be_read_is_unread_never_clear(rules) -> None:
    items, _ = mr.scan_nit_store(Runner(rules), RESOLVER, TODAY)
    assert [i.state for i in items] == ["unread"], items


def test_each_evergreen_issue_is_a_line_and_the_nit_store_is_not_listed_twice() -> None:
    rows = json.dumps([{"number": 77, "title": "Nit Store"}, {"number": 12, "title": "Re-check the harness"},
                       {"number": 5, "title": "Cut a release"}])
    items = mr.scan_evergreen(Runner({"--label evergreen": (0, rows)}), skip=77)
    assert [i.text for i in items] == ["Standing item #5: Cut a release", "Standing item #12: Re-check the harness"]


def test_no_evergreen_issue_is_clear_and_a_failed_listing_is_unread() -> None:
    assert [i.state for i in mr.scan_evergreen(Runner({"--label evergreen": (0, "[]")}), None)] == ["clear"]
    assert [i.state for i in mr.scan_evergreen(Runner({}), None)] == ["unread"]
    assert [i.state for i in mr.scan_evergreen(Runner({"--label evergreen": (0, "{}")}), None)] == ["unread"]


def test_a_listing_that_fills_its_bound_is_unread() -> None:
    full = json.dumps([{"number": n, "title": f"t{n}"} for n in range(mr.LIST_LIMIT)])
    items = mr.scan_evergreen(Runner({"--label evergreen": (0, full)}), None)
    assert [i.state for i in items] == ["unread"] and "cut off" in items[0].text


def test_follow_ups_due_in_or_before_the_month_are_listed_and_later_ones_are_not() -> None:
    rows = json.dumps([
        {"number": 1, "title": "past", "body": "Due: 2026-11-30\n"},
        {"number": 2, "title": "last day", "body": "text\n- **Due:** 2026-12-31\n"},
        {"number": 3, "title": "next month", "body": "Due: 2027-01-01\n"},
    ])
    items = mr.scan_follow_ups(Runner({"--label follow-up": (0, rows)}), "2026-12")
    assert [(i.state, i.text.split(" - ")[0]) for i in items] == [
        ("due", "Follow-up due 2026-11-30"), ("due", "Follow-up due 2026-12-31")]


def test_a_follow_up_with_no_date_is_unread_not_silently_not_due() -> None:
    rows = json.dumps([{"number": 4, "title": "someday", "body": "do the thing\n"}])
    items = mr.scan_follow_ups(Runner({"--label follow-up": (0, rows)}), "2026-12")
    assert [i.state for i in items] == ["unread"] and "#4" in items[0].text


def test_only_later_follow_ups_is_clear_and_says_how_many_wait() -> None:
    rows = json.dumps([{"number": 3, "title": "later", "body": "Due: 2027-03-01"}])
    items = mr.scan_follow_ups(Runner({"--label follow-up": (0, rows)}), "2026-12")
    assert [i.state for i in items] == ["clear"] and "1 not yet due" in items[0].text
    assert [i.state for i in mr.scan_follow_ups(Runner({}), "2026-12")] == ["unread"]


def test_friction_three_states(tmp_path: Path) -> None:
    assert [i.state for i in mr.scan_friction(None)] == ["unread"]
    log = tmp_path / "friction.jsonl"
    assert not log.exists()  # precondition for the absent case
    assert [i.state for i in mr.scan_friction(log)] == ["clear"]
    log.write_text('{"class":"gate-failure"}\n{"class":"permission-prompt"}\n{"class":"red-output"}\n')
    items = mr.scan_friction(log)
    assert [i.state for i in items] == ["due"] and "2 friction signal(s)" in items[0].text
    assert "this host" in items[0].text
    log.write_text('{"class":"permission-prompt"}\n')
    assert [i.state for i in mr.scan_friction(log)] == ["clear"]


def test_a_broken_friction_record_is_reported_not_skipped(tmp_path: Path) -> None:
    log = tmp_path / "friction.jsonl"
    log.write_text('{"class":"gate-failure"}\n{"ts":\n')
    assert sorted(i.state for i in mr.scan_friction(log)) == ["due", "unread"]


def _budget_repo(tmp_path: Path, table: str, docs: dict[str, str]) -> Path:
    (tmp_path / ".claude" / "commands" / "x").mkdir(parents=True)
    (tmp_path / ".claude" / "command-word-budgets.tsv").write_text(table)
    for rel, text in docs.items():
        (tmp_path / ".claude" / "commands" / rel).write_text(text)
    return tmp_path


def test_command_budget_three_states(tmp_path: Path) -> None:
    """Counter-model review: #1703's acceptance names this source and the scan lacked it."""
    assert [i.state for i in mr.scan_command_budget(None)] == ["unread"]
    assert not (tmp_path / ".claude").exists()  # precondition: no budget surface at all
    items = mr.scan_command_budget(tmp_path)
    assert [i.state for i in items] == ["clear"] and "declares no" in items[0].text
    root = _budget_repo(tmp_path, "# comment\n3\tx/a.md\n2\tx/b.md\n", {"x/a.md": "one two three", "x/b.md": "one two"})
    items = mr.scan_command_budget(root)
    assert [i.state for i in items] == ["clear"] and "all 2 budgeted" in items[0].text
    (root / ".claude" / "commands" / "x" / "b.md").write_text("one two three four")
    items = mr.scan_command_budget(root)
    assert [i.state for i in items] == ["due"] and "x/b.md (4 > 2)" in items[0].text


@pytest.mark.parametrize("table", ["3\tx/missing.md\n", "many\tx/a.md\n", "no-tab-here\n"])
def test_a_budget_that_cannot_be_applied_is_unread_not_within_budget(tmp_path: Path, table: str) -> None:
    root = _budget_repo(tmp_path, table, {"x/a.md": "one"})
    assert [i.state for i in mr.scan_command_budget(root)] == ["unread"]


def test_the_friction_log_override_is_honoured(tmp_path: Path, monkeypatch) -> None:
    """Counter-model review: the producer honours CPP_FRICTION_LOG and the scan did not,
    so signals at the configured path read as 'no friction log on this host'."""
    log = tmp_path / "elsewhere.jsonl"
    log.write_text('{"class":"gate-failure"}\n')
    runner = Runner({"rev-parse": (0, str(tmp_path / "repo" / ".git") + "\n")})
    monkeypatch.delenv("CPP_FRICTION_LOG", raising=False)
    default = helper.friction_log(runner, tmp_path)
    assert default == tmp_path / "repo" / ".claude" / "friction.jsonl" and not default.exists()
    monkeypatch.setenv("CPP_FRICTION_LOG", str(log))
    assert helper.friction_log(runner, tmp_path) == log
    assert [i.state for i in mr.scan_friction(helper.friction_log(runner, tmp_path))] == ["due"]


def test_the_helper_is_executable() -> None:
    """Both commands invoke it directly, and the installers skip a non-executable helper."""
    import os

    assert os.access(SCRIPT, os.X_OK), "scripts/monthly-review.py must be committed mode 100755"


def test_the_body_keeps_unread_sources_as_items_to_resolve() -> None:
    body = mr.render_body([mr.Item("a", "due", "Do the thing"), mr.Item("b", "unread", "source b failed"),
                           mr.Item("c", "clear", "nothing in c")], TODAY)
    assert "- [ ] Do the thing" in body and "- [ ] UNREAD - source b failed" in body
    assert "- nothing in c" in body and mr.count_items(body) == (2, 2)


def test_a_repository_with_nothing_gets_a_short_list_not_an_error(tmp_path: Path) -> None:
    runner = Runner({"nit-store-resolve": (1, "NIT_STORE_STATUS: none - nothing\n"),
                     "--label evergreen": (0, "[]"), "--label follow-up": (0, "[]")})
    items = mr.scan(runner, RESOLVER, tmp_path / "absent.jsonl", TODAY, tmp_path)
    assert {i.state for i in items} == {"clear"} and len(items) == 5
    assert "- nothing was found due" in mr.render_body(items, TODAY)


# --------------------------------------------------------------------------- #
# The helper: status and create


def _main(monkeypatch, runner: Runner, *argv: str, capsys) -> tuple[int, str]:
    monkeypatch.setattr(helper, "make_runner", lambda root: runner)
    code = helper.main(["--today", TODAY.isoformat(), *argv])
    return code, capsys.readouterr().out


QUIET = {"nit-store-resolve": (1, "NIT_STORE_STATUS: none - nothing\n"), "--label evergreen": (0, "[]"),
         "--label follow-up": (0, "[]"), "rev-parse": (1, "")}


def _listing(*rows: dict, state: str = "OPEN") -> tuple[int, str]:
    return 0, json.dumps([{**row, "state": state} for row in rows])


def test_status_reports_each_state(monkeypatch, capsys) -> None:
    code, out = _main(monkeypatch, Runner({"--state all": _listing()}), "status", capsys=capsys)
    assert code == 0 and "MONTHLY_REVIEW: none for 2026-12" in out
    code, out = _main(monkeypatch, Runner({"--state all": _listing(_review(40, "2026-12"))}), "status", capsys=capsys)
    assert code == 0 and "MONTHLY_REVIEW: open #40" in out
    done = _listing(_review(40, "2026-12"), state="CLOSED")
    code, out = _main(monkeypatch, Runner({"--state all": done}), "status", capsys=capsys)
    assert code == 0 and "MONTHLY_REVIEW: done for 2026-12 (#40)" in out


@pytest.mark.parametrize("answer", [(1, ""), (0, "not json"), (0, "{}")])
def test_status_is_unknown_with_its_own_exit_when_github_cannot_be_read(monkeypatch, capsys, answer) -> None:
    code, out = _main(monkeypatch, Runner({"--state all": answer}), "status", capsys=capsys)
    assert code == helper.UNKNOWN_EXIT and "MONTHLY_REVIEW: unknown" in out and "none for" not in out


def test_create_writes_one_issue_with_the_label(monkeypatch, capsys) -> None:
    runner = Runner({**QUIET, "--state all": _listing(), "label create": (0, ""),
                     "issue create": (0, "https://github.com/o/r/issues/41\n")})
    code, out = _main(monkeypatch, runner, "create", capsys=capsys)
    assert code == 0 and "MONTHLY_REVIEW_CREATE: created https://github.com/o/r/issues/41" in out
    created = [c for c in runner.calls if c[:3] == ["gh", "issue", "create"]]
    assert len(created) == 1
    assert created[0][created[0].index("--title") + 1] == "Monthly review: 2026-12"
    assert created[0][created[0].index("--label") + 1] == "monthly-review"


@pytest.mark.parametrize("existing_state", ["OPEN", "CLOSED"])
def test_create_twice_in_a_month_does_not_open_a_second_review(monkeypatch, capsys, existing_state) -> None:
    runner = Runner({**QUIET, "--state all": _listing(_review(40, "2026-12"), state=existing_state),
                     "issue create": (0, "https://github.com/o/r/issues/99\n")})
    code, out = _main(monkeypatch, runner, "create", capsys=capsys)
    assert code == 0 and "MONTHLY_REVIEW_CREATE: exists #40" in out
    assert not [c for c in runner.calls if c[:3] == ["gh", "issue", "create"]], runner.calls


def test_create_refuses_when_the_state_is_unknown(monkeypatch, capsys) -> None:
    """Unknown is not none: writing here is how a month gets two reviews."""
    runner = Runner({**QUIET, "issue create": (0, "https://github.com/o/r/issues/99\n")})
    code, out = _main(monkeypatch, runner, "create", capsys=capsys)
    assert code == helper.UNKNOWN_EXIT and "MONTHLY_REVIEW_CREATE: refused" in out
    assert not [c for c in runner.calls if c[:3] == ["gh", "issue", "create"]], runner.calls


def test_a_dry_run_writes_nothing(monkeypatch, capsys) -> None:
    runner = Runner({**QUIET, "--state all": _listing()})
    code, out = _main(monkeypatch, runner, "create", "--dry-run", capsys=capsys)
    assert code == 0 and "# Monthly review: 2026-12" in out and "MONTHLY_REVIEW_CREATE: dry-run" in out
    assert not [c for c in runner.calls if c[:2] == ["gh", "label"] or c[:3] == ["gh", "issue", "create"]]


def test_a_failed_issue_create_is_refused_not_reported_created(monkeypatch, capsys) -> None:
    runner = Runner({**QUIET, "--state all": _listing(), "label create": (0, "")})
    code, out = _main(monkeypatch, runner, "create", capsys=capsys)
    assert code == helper.UNKNOWN_EXIT and "refused" in out and "CREATE: created" not in out
