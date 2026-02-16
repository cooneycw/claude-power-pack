"""Security scan configuration.

Loads configuration from .claude/security.yml if present,
otherwise uses sensible defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .models import Severity, Suppression


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
        """Parse YAML config file."""
        try:
            import yaml
        except ImportError:
            # If PyYAML not installed, use defaults
            return cls._defaults()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        config = cls._defaults()

        # Parse gates
        gates_data = data.get("gates", {})
        for gate_name, gate_cfg in gates_data.items():
            block = [_parse_severity(s) for s in gate_cfg.get("block_on", [])]
            warn = [_parse_severity(s) for s in gate_cfg.get("warn_on", [])]
            config.gates[gate_name] = GatePolicy(block_on=block, warn_on=warn)

        # Parse suppressions
        for supp in data.get("suppressions", []):
            config.suppressions.append(
                Suppression(
                    id=supp["id"],
                    path=supp.get("path"),
                    reason=supp.get("reason", ""),
                )
            )

        return config


def _parse_severity(name: str) -> Severity:
    """Parse severity name string to enum."""
    return Severity[name.upper()]
