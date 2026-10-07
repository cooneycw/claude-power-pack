"""The `validate` step's full-suite pytest invocation carries `--durations=N` (issue #1411).

A CI timeout used to answer "slow or hung?" only by reproducing quietly, hours
later, on a different (often shared, overloaded) host - #1311 found genuinely
slow tests sitting next to ones that ran 0.2-2s quiet locally and 10-120s in
CI, a 50-60x stall under load that the timeout and stack trace alone cannot
distinguish from a hang. With the flag, the slowest N tests' actual times are
in the very log that failed, so the call can be made from it alone.

Scoped to the FULL-SUITE invocation (the one carrying `-n <workers>`), never
the narrower targeted re-run a few lines below it (`-k "SubsumedGates or
ResumeSettlesDeferredGates"`): that one runs two cheap, already-known tests
and gains nothing from a durations report.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def validate_commands(pipeline: Any) -> list[Any]:
    """The `validate` step's `commands:` list, or `[]` if unreadable."""
    if not isinstance(pipeline, dict):
        return []
    steps = pipeline.get("steps")
    if not isinstance(steps, dict):
        return []
    validate = steps.get("validate")
    if not isinstance(validate, dict):
        return []
    commands = validate.get("commands")
    return commands if isinstance(commands, list) else []


def durations_violations(commands: list[Any]) -> list[str]:
    """Every way the full-suite pytest invocation can lack a usable `--durations`."""
    full_suite = [
        c for c in commands
        if isinstance(c, str) and "pytest" in c and " -n " in c
    ]
    if not full_suite:
        return ["no full-suite pytest invocation found (no ` -n ` pytest line)"]
    violations: list[str] = []
    for line in full_suite:
        match = re.search(r"--durations=(\S+)", line)
        if not match:
            violations.append(f"no --durations flag: {line!r}")
            continue
        value = match.group(1)
        try:
            n = int(value)
        except ValueError:
            violations.append(f"--durations value is not an integer: {line!r}")
            continue
        if n < 0:
            violations.append(f"--durations value is negative: {line!r}")
    return violations


def test_the_real_validate_step_has_no_durations_violations() -> None:
    pipeline = yaml.safe_load((ROOT / ".woodpecker.yml").read_text(encoding="utf-8"))
    commands = validate_commands(pipeline)
    assert commands, "the validate step's commands list must be readable"
    assert durations_violations(commands) == []


@pytest.mark.parametrize(
    "commands, expected",
    [
        # (a) the flag is simply absent - the pre-#1411 shape.
        (['uv run pytest -n "$(sh scripts/pytest-workers.sh)"'], "no --durations flag"),
        # (b) present, but on the WRONG (targeted, non-`-n`) invocation only.
        (
            [
                'uv run pytest -n "$(sh scripts/pytest-workers.sh)"',
                'uv run pytest tests/test_runner.py -k "SubsumedGates" --durations=25',
            ],
            "no --durations flag",
        ),
        # (c) present but not a usable integer.
        (['uv run pytest -n 4 --durations=abc'], "not an integer"),
        # (d) present but negative - not a count pytest can act on.
        (['uv run pytest -n 4 --durations=-1'], "negative"),
        # (e) no pytest `-n` line at all - the check cannot even find what to judge.
        (['uv run ruff check .'], "no full-suite pytest invocation found"),
    ],
)
def test_each_way_durations_can_be_wrong_is_reported(
    commands: list[str], expected: str
) -> None:
    violations = durations_violations(commands)
    assert any(expected in v for v in violations), violations


def test_the_intended_shape_passes() -> None:
    assert durations_violations(['uv run pytest -n 4 --durations=25']) == []
    # durations=0 means "show all" to pytest, not "show nothing" - a stronger
    # diagnostic than N, never a violation.
    assert durations_violations(['uv run pytest -n 4 --durations=0']) == []
