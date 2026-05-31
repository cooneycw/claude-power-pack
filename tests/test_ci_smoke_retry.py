"""Tests for bounded-retry hardening of the runtime-smoke probes.

A service can pass the compose `--wait` readiness gate yet briefly refuse a
fresh in-container connection, which made the smoke flaky when the probe
hard-failed on the first refusal. The smoke now retries via a shared
`probe_until_ok` helper; these tests guard that wiring against regression.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]


def _smoke_block() -> str:
    steps = yaml.safe_load((REPO / ".woodpecker.yml").read_text())["steps"]
    commands = steps["runtime-smoke"]["commands"]
    # The check functions live in the single large heredoc-style shell command.
    return next(c for c in commands if "check_http()" in c)


def test_probe_helper_retries_with_a_bounded_attempt_count() -> None:
    block = _smoke_block()
    assert "probe_until_ok()" in block
    assert "max_attempts=10" in block
    # Retries must be bounded and eventually exit non-zero, not loop forever.
    assert "attempt -ge" in block.replace('"', "")
    assert "exit 1" in block


def test_both_probes_go_through_the_retry_helper() -> None:
    block = _smoke_block()
    # Neither check function should call `docker compose exec` for its probe
    # directly any more - both must funnel through probe_until_ok.
    assert block.count("probe_until_ok ") >= 2, "both check functions must retry"


def test_probe_failure_dumps_diagnostics() -> None:
    block = _smoke_block()
    assert "docker compose -p \"$PROJECT\" ps" in block
    assert "logs --tail" in block
