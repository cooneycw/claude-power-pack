"""Tests for Docker health summary diagnostics."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "docker-health-check.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("docker_health_check", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sidecar_dependency_warning_recommends_force_recreate() -> None:
    module = _load_script()
    rows = [
        {"Service": "aws-secrets-agent", "State": "restarting", "Health": "unhealthy"},
        {"Service": "mcp-second-opinion", "State": "created", "Health": ""},
        {"Service": "mcp-nano-banana", "State": "running", "Health": "healthy"},
    ]

    warning = module._sidecar_dependency_warning(rows, ["core"])

    assert warning is not None
    assert "mcp-second-opinion" in warning
    assert "Docker Compose captures environment at container create time" in warning
    assert "docker compose --profile core up -d --force-recreate aws-secrets-agent mcp-second-opinion" in warning


def test_sidecar_dependency_warning_skips_when_agent_is_healthy() -> None:
    module = _load_script()
    rows = [
        {"Service": "aws-secrets-agent", "State": "running", "Health": "healthy"},
        {"Service": "mcp-second-opinion", "State": "created", "Health": ""},
    ]

    assert module._sidecar_dependency_warning(rows, ["core"]) is None
