from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "scenarios.json"


@pytest.fixture(scope="session")
def project_next_scenarios() -> dict[str, Any]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))
