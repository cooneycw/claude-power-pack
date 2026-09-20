from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.project_next import CONTRACT_VERSION
from lib.project_next.models import RepositoryState
from lib.project_next.rank import recommend
from lib.project_next.render import render_result

GOLDEN = Path(__file__).parent / "fixtures" / "golden"


def test_all_human_modes_are_versioned_and_separate_both_decisions(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["active_pr_and_safe_issue"]["state"])
    result = recommend(state)

    for mode in ("brief", "compact", "full"):
        rendered = render_result(result, state, mode)
        assert "1.3" in rendered
        assert "Top action" in rendered
        assert "Next safe issue" in rendered
        assert "#1" in rendered
        assert "#2" in rendered


def test_structured_output_is_versioned_and_json_serializable(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["active_pr_and_safe_issue"]["state"])
    payload = recommend(state).to_dict()

    assert CONTRACT_VERSION == "1.3"
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


def test_json_mode_matches_golden_empty_repository_contract(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["empty_repository"]["state"])
    rendered = json.dumps(recommend(state).to_dict(), indent=2, sort_keys=True)

    assert rendered == (GOLDEN / "result.json").read_text(encoding="utf-8").rstrip("\n")


def test_compact_has_at_most_three_safe_candidates(project_next_scenarios: dict[str, Any]) -> None:
    state = RepositoryState.from_dict(project_next_scenarios["operational_report"]["state"])
    rendered = render_result(recommend(state), state, "compact")

    assert rendered.count("`$flow-auto ") == 3
    assert "#1 Critical security repair — blocked" in rendered
    assert "`$flow-auto 1`" not in rendered
