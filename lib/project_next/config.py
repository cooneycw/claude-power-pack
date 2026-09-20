"""Harness-neutral configuration for project-next."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from .models import normalize_label


class ConfigError(ValueError):
    """Raised when project-next configuration is invalid."""


@dataclass(frozen=True)
class ProjectNextConfig:
    issue_limit: int = 200
    default_mode: str = "compact"
    # Vocabularies are matched against normalize_label() output, so `priority:high`,
    # `priority/high`, and `Priority High` all reach the `priority-high` entry.
    critical_labels: tuple[str, ...] = ("security", "blocker", "critical", "urgent", "sev-1", "p0")
    high_priority_labels: tuple[str, ...] = ("p0", "p1", "priority-high", "high-priority", "high")
    medium_priority_labels: tuple[str, ...] = ("p2", "priority-medium", "medium-priority", "medium")
    quick_win_labels: tuple[str, ...] = (
        "documentation",
        "docs",
        "chore",
        "small",
        "size-s",
        "good-first-issue",
        "quick-win",
        "easy",
    )
    planning_labels: tuple[str, ...] = ("epic", "planning", "discussion", "tracking", "meta")
    stale_after_days: int = 30

    @property
    def known_labels(self) -> frozenset[str]:
        return frozenset(
            self.critical_labels
            + self.high_priority_labels
            + self.medium_priority_labels
            + self.quick_win_labels
            + self.planning_labels
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectNextConfig:
        data = {key: value for key, value in data.items() if key != "$schema"}
        allowed = {item.name for item in fields(cls)}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ConfigError(f"unknown project-next configuration keys: {', '.join(unknown)}")

        values = dict(data)
        tuple_fields = {
            "critical_labels",
            "high_priority_labels",
            "medium_priority_labels",
            "quick_win_labels",
            "planning_labels",
        }
        for name in tuple_fields:
            if name in values:
                value = values[name]
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    raise ConfigError(f"{name} must be an array of strings")
                values[name] = tuple(normalize_label(item) for item in value)

        issue_limit = values.get("issue_limit", cls.issue_limit)
        if not isinstance(issue_limit, int) or isinstance(issue_limit, bool) or issue_limit < 1:
            raise ConfigError("issue_limit must be a positive integer")
        stale_after_days = values.get("stale_after_days", cls.stale_after_days)
        if not isinstance(stale_after_days, int) or isinstance(stale_after_days, bool) or stale_after_days < 0:
            raise ConfigError("stale_after_days must be a non-negative integer")
        mode = values.get("default_mode", cls.default_mode)
        if mode not in {"brief", "compact", "full"}:
            raise ConfigError("default_mode must be brief, compact, or full")
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for item in fields(self):
            value = getattr(self, item.name)
            result[item.name] = list(value) if isinstance(value, tuple) else value
        return result


def load_config(repository: Path, explicit_path: Path | None = None) -> ProjectNextConfig:
    path = explicit_path or repository / ".project-next.json"
    if not path.exists():
        return ProjectNextConfig()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"{path} must contain a JSON object")
    return ProjectNextConfig.from_dict(payload)
