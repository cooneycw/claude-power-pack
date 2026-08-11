"""Regression tests for CPP marketplace retirement (issue #662, ADR 0005)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

RETIRED_PATHS = [
    ".claude-plugin",
    "plugins",
    "scripts/plugin-sync.sh",
]


@pytest.mark.parametrize("rel", RETIRED_PATHS)
def test_cpp_marketplace_artifact_stays_retired(rel: str) -> None:
    assert not (ROOT / rel).exists(), (
        f"{rel} was retired by issue #662 and must not return"
    )


def test_retirement_adr_exists() -> None:
    assert (
        ROOT / "docs/decisions/0005-retire-plugin-marketplace-distribution.md"
    ).is_file()


def test_original_marketplace_adr_is_marked_superseded() -> None:
    adr = (
        ROOT / "docs/decisions/0001-plugin-marketplace-packaging.md"
    ).read_text(encoding="utf-8")
    status = next(line for line in adr.splitlines() if line.startswith("- Status:"))
    assert "Superseded" in status
    assert "ADR 0005" in status
    assert "2026-08-11" in status
    assert "#662" in status
