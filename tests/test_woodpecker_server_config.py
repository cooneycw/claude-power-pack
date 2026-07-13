"""Contracts for resilient Woodpecker server configuration fetches."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SERVER_COMPOSE_FILES = [
    ROOT / "woodpecker" / "docker-compose.yml",
    ROOT / "templates" / "woodpecker" / "docker-compose.server.yml.example",
]


@pytest.mark.parametrize("compose_path", SERVER_COMPOSE_FILES, ids=lambda path: path.name)
def test_server_retries_slow_forge_config_fetches(compose_path: Path) -> None:
    """Live and scaffolded servers tolerate transient forge latency."""
    compose = yaml.safe_load(compose_path.read_text())
    environment = compose["services"]["woodpecker-server"]["environment"]

    assert "WOODPECKER_FORGE_TIMEOUT=15s" in environment
    assert "WOODPECKER_FORGE_RETRY=5" in environment
