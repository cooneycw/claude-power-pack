from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.project_next.config import ConfigError, ProjectNextConfig, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_documented_example_matches_runtime_defaults() -> None:
    payload = json.loads((REPO_ROOT / "templates" / "project-next.json.example").read_text(encoding="utf-8"))

    assert ProjectNextConfig.from_dict(payload) == ProjectNextConfig()


def test_missing_configuration_degrades_to_defaults(tmp_path: Path) -> None:
    assert load_config(tmp_path) == ProjectNextConfig()


def test_unknown_configuration_is_rejected() -> None:
    with pytest.raises(ConfigError, match="unknown project-next configuration keys"):
        ProjectNextConfig.from_dict({"ranking_prompt": "guess"})


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"issue_limit": 0}, "positive integer"),
        ({"stale_after_days": -1}, "non-negative integer"),
        ({"default_mode": "verbose"}, "brief, compact, or full"),
        ({"critical_labels": "security"}, "array of strings"),
    ],
)
def test_invalid_configuration_is_rejected(payload: dict[str, object], message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        ProjectNextConfig.from_dict(payload)
