from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.project_next import CONTRACT_VERSION
from lib.project_next.models import RepositoryState, Worktree
from lib.project_next.rank import recommend
from lib.project_next.render import render_result

GOLDEN = Path(__file__).parent / "fixtures" / "golden"

#: The ONE place the contract version is pinned: the ownership manifest the
#: wrapper and `make project-next-check` already read (issue #1719). These tests
#: used to restate it as a literal, so every version bump meant finding each
#: copy. An unreadable manifest fails here, loudly, at import.
PINNED_VERSION: str = json.loads(
    (Path(__file__).resolve().parents[2] / "lib" / "project_next" / "ownership.json").read_text(encoding="utf-8")
)["contract_version"]


def test_all_human_modes_are_versioned_and_separate_both_decisions(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["active_pr_and_safe_issue"]["state"])
    result = recommend(state)

    for mode in ("brief", "compact", "full"):
        rendered = render_result(result, state, mode)
        assert PINNED_VERSION in rendered
        assert "Recommended: #2" in rendered or "**Recommended:** #2" in rendered
        assert "Top action" in rendered
        assert "Next safe issue" in rendered
        assert "#1" in rendered
        assert "#2" in rendered


def test_structured_output_is_versioned_and_json_serializable(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["active_pr_and_safe_issue"]["state"])
    payload = recommend(state).to_dict()

    assert CONTRACT_VERSION == PINNED_VERSION
    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["top_action"]["issue_number"] == 1
    assert payload["next_startable_issue"] == 2
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_human_modes_match_golden_operational_report(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["operational_report"]["state"])
    result = recommend(state)

    for mode, filename in (("brief", "brief.txt"), ("compact", "compact.md"), ("full", "full.md")):
        expected = (GOLDEN / filename).read_text(encoding="utf-8").rstrip("\n")
        assert render_result(result, state, mode) == expected


def test_the_full_worktree_table_renders_status_unknown_not_clean() -> None:
    """Site 4 of the four (#1398): the "Working tree" column must say

    `unknown (git status failed: <reason>)`, never fall through to `clean`
    the way `if worktree.dirty: ... else: "clean"` used to for `dirty=None`.
    """
    state = RepositoryState(
        repository="example/repo",
        default_branch="main",
        collected_at="2026-08-07T13:00:00Z",
        worktrees=(
            Worktree(
                "/repo-issue-7", "issue-7-x", dirty=None,
                status_unknown_reason="git status --short: fatal: not a git repository",
            ),
        ),
    )

    rendered = render_result(recommend(state), state, "full")

    assert "unknown (git status failed: git status --short: fatal: not a git repository)" in rendered
    assert "| /repo-issue-7 | issue-7-x |" in rendered


def test_json_mode_matches_golden_empty_repository_contract(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["empty_repository"]["state"])
    rendered = json.dumps(recommend(state).to_dict(), indent=2, sort_keys=True)

    assert rendered == (GOLDEN / "result.json").read_text(encoding="utf-8").rstrip("\n")


def test_compact_has_at_most_three_safe_candidates(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["operational_report"]["state"])
    rendered = render_result(recommend(state), state, "compact")

    assert rendered.count("`/flow:auto ") == 3
    assert "#1 Critical security repair — blocked" in rendered
    assert "`/flow:auto 1`" not in rendered


def test_no_recommendation_over_an_incomplete_inventory_never_claims_everything_is_blocked() -> None:
    # Counter-model review on #1626: an issue-list failure leaves zero issues. That
    # zero is unexamined, not "every open issue is blocked".
    state = RepositoryState(
        repository="example/failed",
        default_branch="main",
        collected_at="2026-11-06T00:00:00Z",
        inventory_complete=False,
        collector_errors=("open issue inventory unavailable: gh: rate limited",),
    )

    rendered = render_result(recommend(state), state, "compact")

    assert "every open issue is blocked" not in rendered
    assert "inventory is incomplete" in rendered
