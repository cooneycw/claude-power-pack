"""Tripwire for the declared fact that CI runs the suite as root (issue #1718, row 11).

`tests/conftest.py` declares `CI_RUNS_AS_ROOT`. About two dozen tests skip, or
take a different branch, when the effective uid is 0, because root is not
stopped by a lowered mode. Which of them run in CI therefore depends on the CI
user, and nothing compared the declaration with the fact: if the `validate`
step ever stopped running as root, those tests would silently start running
there (or, the other way round, silently stop) with no test saying so.

The comparison can only be made where the fact lives, so it runs IN CI ONLY.
On a developer host it would compare the declaration with the developer's own
uid, which says nothing about CI.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from tests import conftest

#: A session is "in CI" when either name is set to a non-empty value. `CI` is
#: the name `scripts/skill-coverage-snapshot.py` already treats as CI
#: (`CI_ENV_VARS`), and Woodpecker sets it on every step; `CI_PIPELINE_EVENT`
#: is the Woodpecker variable `.woodpecker.yml` itself reads.
CI_MARKERS = ("CI", "CI_PIPELINE_EVENT")


def in_ci(environ: Mapping[str, str]) -> bool:
    return any(environ.get(name) for name in CI_MARKERS)


def disagreement(environ: Mapping[str, str], euid: int, declared: bool) -> str | None:
    """Why the declaration is wrong for this session, or None.

    None also when the session is not in CI: there the question is not asked.
    """
    if not in_ci(environ):
        return None
    is_root = euid == 0
    if is_root == declared:
        return None
    return (
        f"tests/conftest.py declares CI_RUNS_AS_ROOT = {declared}, but this CI session's "
        f"effective uid is {euid}. Either the CI user changed - then update the declaration "
        "and re-read every fixture that skips or branches on root, because the set of tests "
        "CI runs has just changed - or this is not CI and "
        f"{' / '.join(CI_MARKERS)} is set in a developer shell."
    )


def test_the_declaration_matches_the_ci_user() -> None:
    """In CI: the declared value equals `os.geteuid() == 0`. THE COMPARISON RUNS
    IN CI ONLY; outside CI this asserts only that the constant exists and is a
    bool, and the other tests in this file show the comparison can fail."""
    declared = conftest.CI_RUNS_AS_ROOT
    assert isinstance(declared, bool), f"CI_RUNS_AS_ROOT must be a bool, got {declared!r}"
    problem = disagreement(os.environ, os.geteuid(), declared)
    assert problem is None, problem


def test_a_changed_ci_user_is_reported() -> None:
    """The red case: CI as an unprivileged user while root is declared, and the reverse."""
    for marker in CI_MARKERS:
        ci = {marker: "woodpecker"}
        assert in_ci(ci), f"precondition: {marker} marks the session as CI"
        unprivileged = disagreement(ci, 1000, True)
        assert unprivileged is not None and "effective uid is 1000" in unprivileged
        assert disagreement(ci, 0, False) is not None
        assert disagreement(ci, 0, True) is None
        assert disagreement(ci, 1000, False) is None


def test_outside_ci_the_comparison_is_not_made() -> None:
    """A developer's uid is not evidence about CI, in either direction."""
    for environ in ({}, {"CI": ""}, {"HOME": "/h"}):
        assert not in_ci(environ), f"precondition: {environ} is not CI"
        assert disagreement(environ, 1000, True) is None
        assert disagreement(environ, 0, False) is None
