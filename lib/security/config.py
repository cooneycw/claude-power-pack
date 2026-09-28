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
from typing import Any, Optional

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

        # NO SOURCE TEXT IN ANY MESSAGE (counter-model review, HIGH). PyYAML's
        # `str(exc)` quotes the offending line, and the offending line of a
        # malformed `secret:` entry IS the secret - printed to a CI log by the
        # very gate meant to keep it out. Only the error class, the problem
        # (a grammar statement, never a token's text) and the position leave.
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except UnicodeDecodeError as exc:
            raise ConfigUnreadable(path, f"not valid UTF-8 at byte {exc.start}") from None
        except OSError as exc:
            raise ConfigUnreadable(path, f"{type(exc).__name__}: {exc.strerror}") from None
        except yaml.YAMLError as exc:
            raise ConfigUnreadable(path, _yaml_error(exc)) from None

        # EMPTY IS THE ONLY SHAPE THAT DEFAULTS. `safe_load(f) or {}` also turned
        # a top-level `false`, `0` or `[]` into defaults - a file that says
        # something malformed read as a file that says nothing.
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ConfigUnreadable(path, f"top level is a {type(data).__name__}, not a mapping")

        config = cls._defaults()

        # Parse gates
        gates_data = _section(path, data, "gates", dict)
        for gate_name, gate_cfg in gates_data.items():
            if not isinstance(gate_cfg, dict):
                raise ConfigUnreadable(path, f"gates.{gate_name} is not a mapping")
            policy = {}
            for key in ("block_on", "warn_on"):
                names = gate_cfg.get(key, [])
                if not isinstance(names, list):
                    raise ConfigUnreadable(path, f"gates.{gate_name}.{key} is not a list")
                try:
                    policy[key] = [_parse_severity(n) for n in names]
                except (KeyError, AttributeError):
                    raise ConfigUnreadable(
                        path,
                        f"gates.{gate_name}.{key} names an unknown severity "
                        f"(allowed: {[s.name.lower() for s in Severity]})",
                    ) from None
            config.gates[gate_name] = GatePolicy(**policy)

        # Parse suppressions
        for n, supp in enumerate(_section(path, data, "suppressions", list), start=1):
            config.suppressions.append(_parse_suppression(path, n, supp))

        return config


def _yaml_error(exc: Exception) -> str:
    """Class, problem and position of a YAML error - never its source excerpt."""
    problem = getattr(exc, "problem", None)
    mark = getattr(exc, "problem_mark", None)
    where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark is not None else ""
    return f"{type(exc).__name__}: {problem or 'unparseable'}{where}"


def _section(path: Path, data: dict, key: str, kind: type) -> Any:
    """A top-level section: absent or empty defaults; any other wrong type refuses."""
    value = data.get(key)
    if value is None:
        return kind()
    if not isinstance(value, kind):
        raise ConfigUnreadable(
            path, f"`{key}` is a {type(value).__name__}, not a {kind.__name__}"
        )
    return value


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
