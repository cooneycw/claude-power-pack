"""Shared fixtures for CPP unit tests."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest

from tests.supervise_reap import drain_unreaped, reap_supervise_daemons


@pytest.fixture(autouse=True)
def _reap_leaked_supervise_daemons(tmp_path: Path):
    """Reap any detached `supervise` daemon a test left behind (issue #1116).

    `supervise` daemons outlive the command that starts them by design (issue
    #814), so a test that starts one owns a process pytest will not clean up.
    Left alone they are reparented to `systemd --user` and hold their working
    directory - the per-issue worktree - open, which makes
    `worktree-remove.sh`'s #888 occupancy guard refuse to remove it at the end
    of a `/flow:auto` run. The guard is right; it should not be spending its
    credibility on our litter.

    This is `autouse` deliberately, and that is the substance of the fix rather
    than a detail of it. Per-test kill calls are the fast path and stay where
    they are, but they only run on the paths a test actually reaches: a test
    that raises early, or whose own kill times out, skips them entirely - and
    those are precisely the paths that leak. Teardown runs either way, for
    every test in the suite, including ones written after this comment by
    someone who never read it.
    """
    yield
    result = reap_supervise_daemons(tmp_path)
    # A cleanup that cannot report its own failure is the defect this fixture
    # exists to remove (counter-model review, issue #1116): the code it
    # replaced discarded its waiter's result, so a daemon that outlived the
    # kill produced no signal at all. Surviving SIGKILL plus its grace period
    # is a real fault - loud here, or invisible until it pins someone's
    # worktree hours later.
    # Two populations, because neither covers the other (counter-model
    # re-review, issue #1116). `survivors` is what THIS reap could not kill.
    # `drain_unreaped()` is what a test's own fast-path kill already gave up
    # on - which the reap cannot rediscover when the test overwrote or removed
    # the pidfile, as two tests here deliberately do.
    unreaped = drain_unreaped()
    assert not result.survivors and not unreaped, (
        f"supervise daemon(s) {sorted({*result.survivors, *unreaped})} survived "
        "cleanup; they still hold this test's working directory"
    )


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with .gitignore."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(
        textwrap.dedent("""\
        .env
        .env.*
        *.pem
        *.key
        secrets.*
        *.p12
        .claude/security.yml
        """)
    )
    return tmp_path


@pytest.fixture
def sample_tasks_md(tmp_path: Path) -> Path:
    """Create a sample tasks.md file."""
    content = textwrap.dedent("""\
    # Tasks: My Feature

    > **Plan:** [plan.md](./plan.md)
    > **Created:** 2026-01-01
    > **Status:** Ready

    ---

    ## Wave 1: Core setup

    - [ ] **T001** [US1] Create the main module `lib/main.py`
    - [x] **T002** [US1] Add configuration parsing `lib/config.py`
    - [ ] **T003** [P] [US2] Add parallel task support

    **Checkpoint:** `make test` passes

    ---

    ## Wave 2: Integration

    - [ ] **T004** [US1] Integrate with external API (depends on T001, T002)
    - [ ] **T005** [US2] Add error handling

    **Checkpoint:** Integration tests pass

    ---

    ## Issue Sync
    | Wave | Description | Issue | Status |
    |------|-------------|-------|--------|
    | 1 | Core setup | #42 | synced |
    | 2 | Integration | | pending |
    """)
    tasks_file = tmp_path / "tasks.md"
    tasks_file.write_text(content)
    return tasks_file


@pytest.fixture
def sample_spec_md(tmp_path: Path) -> Path:
    """Create a sample spec.md file."""
    content = textwrap.dedent("""\
    # Feature Specification: My Feature

    ## Overview

    This feature adds unit testing support to the project.

    ## User Stories

    ### US1: Test Runner [P1]

    **As a** developer,
    **I want** to run tests easily,
    **So that** I can verify code quality.

    **Acceptance Criteria:**
    - [ ] Tests run with `make test`
    - [ ] Coverage report generated

    ### US2: Test Fixtures [P2]

    **As a** developer,
    **I want** reusable test fixtures,
    **So that** I can write tests faster.

    **Acceptance Criteria:**
    - [ ] Shared conftest.py
    - [ ] Temporary directory fixtures

    ## Requirements

    | ID | Description | Priority | Story |
    |----|-------------|----------|-------|
    | R1 | Tests must run in < 30s | Must | US1 |
    | R2 | Support pytest markers | Should | US1 |
    | R3 | Fixture autodiscovery | Could | US2 |

    ## Edge Cases

    | Scenario | Handling |
    |----------|----------|
    | No tests found | Show warning |
    | Import errors | Report clearly |

    ## Out of Scope

    - Performance benchmarks
    - Browser testing

    ## Success Criteria

    - All tests pass
    - Coverage > 80%

    ## Open Questions

    - Should we require minimum coverage?
    """)
    spec_file = tmp_path / "spec.md"
    spec_file.write_text(content)
    return spec_file


# --------------------------------------------------------------------------- #
# Missing-binary skips are REPORTED, not merely correct (issue #926)
# --------------------------------------------------------------------------- #
# A guard turns a vacuous PASS into a SKIP. That is strictly better and it is not
# sufficient: `make test` sits inside `make verify`, the gate a worker reads
# before pushing, and pytest's summary is read as "N passed" while M skipped goes
# uncounted. So an unexercised lane still ships behind a green - the same defect
# one level up, in the aggregate the reader actually sees.
#
# MEASURED, which is why this exists rather than a comment saying "remember to
# check skips": `TestPsFallbackWatcherIdentityAcrossDirectories` forces the `ps`
# lane and asserts it reports `unknown`. With `ps` absent the lane reports
# `unknown` for an unrelated reason, so the class PASSED on a host without the
# binary it forces. Guarding it makes it SKIP. Without this hook, that skip is
# invisible in `make verify`, and "the ps lane is unexercised on this host" and
# "the ps lane works" render identically.
#
# The binary set is IMPORTED from the gate rather than restated here. A second
# list is a second population to keep in sync, and this one would drift silently
# the moment `GUARDED_BINARIES` grows.
def _guarded_binaries() -> frozenset[str]:
    import importlib.util
    import sys

    gate = Path(__file__).resolve().parents[1] / "scripts" / "check-test-binary-guards.py"
    try:
        spec = importlib.util.spec_from_file_location("_cpp_binary_guards", gate)
        if spec is None or spec.loader is None:
            return frozenset()
        module = importlib.util.module_from_spec(spec)
        sys.modules["_cpp_binary_guards"] = module
        spec.loader.exec_module(module)
        return frozenset(module.GUARDED_BINARIES)
    except Exception:
        # Reporting must never be the reason a suite fails. An unreadable gate
        # means no attribution, and the header below says so rather than
        # printing a confident zero.
        return frozenset()


def attribute_missing_binary_skips(
    reasons: list[str], binaries: frozenset[str]
) -> dict[str, int]:
    r"""Count skip reasons naming an absent binary. Pure, so it is testable.

    Extracted from the hook rather than left inline: a hook that reports
    "missing-binary skips" and actually counts EVERY skip is indistinguishable
    from a correct one on any run where all skips happen to be binary-related,
    which is most runs. The negative case needs a committed test, and a committed
    test needs a function to call.

    The boundary is `[\w-]` on both sides rather than `\b`, because `\b` treats a
    hyphen as a boundary: "no-ps-here" would count as naming `ps`. Both cases are
    pinned by test rather than left to this comment.
    """
    counts: dict[str, int] = {}
    for reason in reasons:
        for name in binaries:
            if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", reason):
                counts[name] = counts.get(name, 0) + 1
    return counts


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:  # noqa: ARG001
    """Name and count the skips caused by a binary being absent."""
    skipped = terminalreporter.stats.get("skipped", [])
    if not skipped:
        return

    binaries = _guarded_binaries()
    if not binaries:
        terminalreporter.write_line(
            "missing-binary skips: UNKNOWN - could not read GUARDED_BINARIES from "
            "scripts/check-test-binary-guards.py, so skips were not attributed",
            yellow=True,
        )
        return

    reasons = []
    for report in skipped:
        longrepr = getattr(report, "longrepr", None)
        if isinstance(longrepr, tuple) and len(longrepr) == 3:
            reasons.append(str(longrepr[2]))
    counts = attribute_missing_binary_skips(reasons, binaries)

    if not counts:
        return
    total = sum(counts.values())
    detail = ", ".join(f"{name}={counts[name]}" for name in sorted(counts))
    terminalreporter.write_line(
        f"missing-binary skips: {total} test(s) did not run because a binary is "
        f"absent ({detail}). Those lanes are UNEXERCISED here, not verified.",
        yellow=True,
    )
