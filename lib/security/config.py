"""Security scan configuration.

Loads configuration from .claude/security.yml if present,
otherwise uses sensible defaults.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .models import Severity, Suppression


class ConfigUnreadable(Exception):
    """`.claude/security.yml` exists and could not be applied (issue #1299).

    Raised instead of falling back to defaults. A silent fallback drops the
    repository's suppressions (a false BLOCK on a planted test key) AND its
    stricter gate policy (a false PASS), and both are indistinguishable from a
    real verdict. The measured case: the finish step runs `python3 -m
    lib.security` under whatever `python3` is on PATH, and a system python3
    without PyYAML discarded the file with no message.
    """

    def __init__(self, path: Path, cause: str) -> None:
        self.path = path
        # ONE line: the cause lands inside the single `SECURITY_GATE:` summary
        # line, and PyYAML's parse errors span several.
        self.cause = " ".join(cause.split())
        super().__init__(f"{path}: {cause}")


#: The keys a suppression may carry. Anything else is REFUSED, not ignored: a
#: misspelt `secrets:` would otherwise vanish and leave an id+path suppression
#: that covers every value in the file - wider than the author wrote.
_SUPPRESSION_KEYS = {"id", "path", "reason", "secret"}


@dataclass
class GatePolicy:
    """Policy for a specific flow gate (finish or deploy)."""

    block_on: list[Severity] = field(default_factory=lambda: [Severity.CRITICAL])
    warn_on: list[Severity] = field(default_factory=lambda: [Severity.HIGH])


@dataclass
class SecurityConfig:
    """Configuration for security scanning."""

    gates: dict[str, GatePolicy] = field(default_factory=dict)
    suppressions: list[Suppression] = field(default_factory=list)

    @classmethod
    def load(cls, project_root: Optional[str] = None) -> SecurityConfig:
        """Load config from .claude/security.yml or use defaults."""
        if project_root is None:
            project_root = os.getcwd()

        config_path = Path(project_root) / ".claude" / "security.yml"
        if config_path.exists():
            return cls._from_yaml(config_path)

        return cls._defaults()

    @classmethod
    def _defaults(cls) -> SecurityConfig:
        return cls(
            gates={
                "flow_finish": GatePolicy(
                    block_on=[Severity.CRITICAL],
                    warn_on=[Severity.HIGH],
                ),
                "flow_deploy": GatePolicy(
                    block_on=[Severity.CRITICAL, Severity.HIGH],
                    warn_on=[Severity.MEDIUM],
                ),
            },
            suppressions=[],
        )

    @classmethod
    def _from_yaml(cls, path: Path) -> SecurityConfig:
        """Parse YAML config file.

        Raises ConfigUnreadable - never returns defaults - when the file exists
        but cannot be read or does not have the documented shape.
        """
        try:
            import yaml
        except ImportError:
            raise ConfigUnreadable(
                path, f"PyYAML is not importable by {sys.executable}"
            ) from None

        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigUnreadable(path, f"{type(exc).__name__}: {exc}") from None
        if not isinstance(data, dict):
            raise ConfigUnreadable(path, "top level is not a mapping")

        config = cls._defaults()

        # Parse gates
        gates_data = data.get("gates") or {}
        try:
            for gate_name, gate_cfg in gates_data.items():
                block = [_parse_severity(s) for s in gate_cfg.get("block_on", [])]
                warn = [_parse_severity(s) for s in gate_cfg.get("warn_on", [])]
                config.gates[gate_name] = GatePolicy(block_on=block, warn_on=warn)
        except (AttributeError, KeyError, TypeError) as exc:
            raise ConfigUnreadable(path, f"gates: {type(exc).__name__}: {exc}") from None

        # Parse suppressions
        for n, supp in enumerate(data.get("suppressions") or [], start=1):
            config.suppressions.append(_parse_suppression(path, n, supp))

        return config


def _parse_suppression(path: Path, n: int, supp: object) -> Suppression:
    """One `suppressions:` entry, validated; anything malformed is unreadable."""
    where = f"suppressions[{n}]"
    if not isinstance(supp, dict):
        raise ConfigUnreadable(path, f"{where} is not a mapping")
    unknown = sorted(set(supp) - _SUPPRESSION_KEYS)
    if unknown:
        raise ConfigUnreadable(
            path,
            f"{where} has unknown key(s) {unknown}; allowed: {sorted(_SUPPRESSION_KEYS)}",
        )
    if not isinstance(supp.get("id"), str) or not supp["id"]:
        raise ConfigUnreadable(path, f"{where} needs a non-empty string `id`")
    for key in ("path", "secret"):
        value = supp.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ConfigUnreadable(path, f"{where}.{key} must be a string")
        try:
            re.compile(value)
        except re.error as exc:
            raise ConfigUnreadable(path, f"{where}.{key} is not a valid regex: {exc}") from None
    return Suppression(
        id=supp["id"],
        path=supp.get("path"),
        reason=str(supp.get("reason", "")),
        secret=supp.get("secret"),
    )


def _parse_severity(name: str) -> Severity:
    """Parse severity name string to enum."""
    return Severity[name.upper()]
