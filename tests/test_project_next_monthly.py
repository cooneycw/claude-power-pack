"""`/project:next` reports the monthly review's state in every mode (issue #1703).

That report is the review's only trigger, so the two ways it could go quiet
are pinned: an unreadable closed-review listing must read `unknown` (never
`none`, which asks for a second review), and the line must be present in brief,
compact and full output alike. The engine's own decision is asserted unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project-next.py"
SPEC = importlib.util.spec_from_file_location("cpp_project_next_monthly", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
project_next = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = project_next
SPEC.loader.exec_module(project_next)

MODES = ("brief", "compact", "full")
WORK = {"number": 12, "title": "Ordinary work", "labels": ["enhancement"]}
REVIEW = {"number": 40, "title": "Monthly review: 2026-12", "labels": ["monthly-review"],
          "created_at": "2026-12-01T00:00:00Z", "body": "- [ ] one\n- [x] two\n"}


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch) -> None:
    monkeypatch.setattr(project_next, "_today", lambda: date(2026, 12, 9))


def _fixture(tmp_path: Path, issues: list[dict], **extra: object) -> Path:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"repository": "example/project", "default_branch": "main",
                                "collected_at": "2026-12-09T12:00:00Z", "issues": issues, **extra}),
                    encoding="utf-8")
    return path


def _render(tmp_path: Path, capsys, mode: str, issues: list[dict], **extra: object) -> str:
    assert project_next.main([str(tmp_path), f"--{mode}", "--input", str(_fixture(tmp_path, issues, **extra))]) == 0
    return capsys.readouterr().out


@pytest.mark.parametrize("mode", MODES)
def test_no_review_this_month_names_the_create_route(tmp_path: Path, capsys, mode: str) -> None:
    out = _render(tmp_path, capsys, mode, [WORK], monthly_reviews_closed=[])
    assert "none for 2026-12" in out and "/monthly:create" in out, out


@pytest.mark.parametrize("mode", MODES)
def test_an_open_review_is_reported_with_its_remaining_items(tmp_path: Path, capsys, mode: str) -> None:
    out = _render(tmp_path, capsys, mode, [WORK, REVIEW], monthly_reviews_closed=[])
    assert "open #40 (2026-12, 8d old, 1 of 2 item(s) open)" in out and "/monthly:review" in out, out


@pytest.mark.parametrize("mode", MODES)
def test_a_finished_month_is_done_and_asks_for_nothing(tmp_path: Path, capsys, mode: str) -> None:
    closed = [{"number": 40, "title": "Monthly review: 2026-12"}]
    out = _render(tmp_path, capsys, mode, [WORK], monthly_reviews_closed=closed)
    assert "done for 2026-12 (#40)" in out and "/monthly:create" not in out, out


@pytest.mark.parametrize("mode", MODES)
def test_an_unread_closed_listing_is_unknown_never_none(tmp_path: Path, capsys, mode: str) -> None:
    """No `monthly_reviews_closed` key: the listing was not read at all."""
    out = _render(tmp_path, capsys, mode, [WORK])
    assert "Monthly review" in out and "unknown" in out and "NOT evidence" in out, out
    assert "none for 2026-12" not in out and "/monthly:create" not in out, out


def test_the_json_carries_the_state_and_the_engine_decision_is_unchanged(tmp_path: Path, capsys) -> None:
    def payload(issues: list[dict], **extra: object) -> dict:
        assert project_next.main([str(tmp_path), "--json", "--input", str(_fixture(tmp_path, issues, **extra))]) == 0
        return json.loads(capsys.readouterr().out)

    without = payload([WORK])
    with_state = payload([WORK], monthly_reviews_closed=[])
    review = with_state["cpp_extensions"]["monthly_review"]
    assert review["verdict"] == "none" and review["month"] == "2026-12"
    assert without["cpp_extensions"]["monthly_review"]["verdict"] == "unknown"
    for key in ("next_startable_issue", "top_action", "candidates"):
        assert with_state.get(key) == without.get(key), key


def test_a_review_issue_is_ordinary_startable_work(tmp_path: Path, capsys) -> None:
    """It carries no non-startable marker, so the engine may rank and pick it."""
    assert project_next.main([str(tmp_path), "--json", "--input",
                              str(_fixture(tmp_path, [REVIEW], monthly_reviews_closed=[]))]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["next_startable_issue"] == 40, result["next_startable_issue"]
    assert result["cpp_extensions"]["monthly_review"]["verdict"] == "open"
