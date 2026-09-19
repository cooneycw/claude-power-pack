"""The committed case that goes red when pytest worker isolation breaks (issue #1086).

WHY THIS FILE EXISTS. Switching the suite to `-n` makes it finish in a fraction
of the time, and the natural reading of that is "same tests, less time". It is
not automatically true. A test whose isolation broke does not usually FAIL - it
passes for the wrong reason, because a sibling worker created the resource it
asserts on, or removed one it assumed absent. The speedup is visible on every
run; the weakening is visible on none of them.

So the question this file answers is not "did the parallel suite pass". It is
"WOULD THIS SUITE NOTICE if worker scoping stopped working at all". Issue #1086
asks for that as a committed case rather than as a one-off red somebody ran once
and wrote down:

    A test asserting that a worker-scoped resource path actually carries the
    worker id, run once with the scoping deliberately defeated to watch it go
    red, with that red recorded.

Recording a red in a PR body makes it evidence about one afternoon. Producing it
on every run makes it evidence about the suite, which is what the ADR 0008 bound
asks for - the proof that a control CAN FAIL is a by-product of RUNNING it, never
a separate ritual someone remembers.

HOW IT WORKS. `_run_fixture_suite` materialises a tiny eight-test pytest tree in
`tmp_path` and runs it under `-n 2` twice, changing exactly one thing:

  SCOPING=on   each test claims `<root>/<PYTEST_XDIST_WORKER>` - the real shape,
               where the resource path CARRIES the worker id. Both workers claim
               a different directory and the run is GREEN.
  SCOPING=off  each test claims `<root>/shared` - the same shape with the worker
               id removed, which is precisely what "isolation broke" means. The
               second worker's exclusive `mkdir` raises and the run is RED.

The claim is `os.mkdir`, not a write-then-read race with a sleep, because a race
is red MOST of the time and this needs to be red EVERY time. An intermittent
negative control is a negative control that will be deleted for flaking.

THE PRECONDITION THIS FIXTURE ASSERTS ABOUT ITSELF. A constructed-absence fixture
can construct an absence broader than it intended, and then its assertions hold
for reasons that have nothing to do with the subject (`docs/agents/detector-
contracts.md`; the CLAUDE.md directive `check-negative-fixture-preconditions.py`
enforces for PATH). The specific way this one could go vacuous: if only ONE worker
ever ran a test, `SCOPING=off` would claim `<root>/shared` exactly once, succeed,
and the run would be GREEN - the control would report "isolation is fine" having
never put two workers in contention at all. So the scoped run asserts that AT
LEAST TWO distinct worker directories exist afterwards. That is the direct
evidence that two workers genuinely ran concurrently, and without it the red below
would prove nothing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

#: The fixture suite. EIGHT tests and `-n 2`: xdist's initial round-robin hands
#: each worker two items before any test finishes, so both workers are in play
#: regardless of how fast individual tests are. The precondition assertion in
#: `test_worker_scoped_resources_let_the_fixture_suite_pass` verifies that
#: rather than trusting it.
FIXTURE_SUITE = '''\
"""A miniature suite whose tests contend for ONE named resource."""

import os
import pathlib

ROOT = pathlib.Path(os.environ["ISOLATION_ROOT"])

#: Claimed once per worker process. A worker legitimately runs several of these
#: tests, and the second one must not collide with its own first claim - the
#: contention this models is BETWEEN workers, not within one.
_CLAIMED = set()


def _claim():
    worker = os.environ.get("PYTEST_XDIST_WORKER", "no-worker")
    # The one difference between the two runs: whether the resource path carries
    # the worker id. `shared` is what a broken scoping looks like.
    name = worker if os.environ["SCOPING"] == "on" else "shared"
    if name in _CLAIMED:
        return
    # EXCLUSIVE by construction: mkdir raises FileExistsError if anyone else
    # already took this name. No sleep, no window, no flake.
    os.mkdir(ROOT / name)
    _CLAIMED.add(name)


def test_one(): _claim()
def test_two(): _claim()
def test_three(): _claim()
def test_four(): _claim()
def test_five(): _claim()
def test_six(): _claim()
def test_seven(): _claim()
def test_eight(): _claim()
'''

#: A config of its own, so the child run does not inherit CPP's `testpaths`,
#: `pythonpath` or per-test timeout and then measure those instead.
FIXTURE_INI = """\
[pytest]
addopts =
"""


def _run_fixture_suite(tmp_path: Path, scoping: str) -> subprocess.CompletedProcess:
    """Run the fixture suite under `-n 2` with worker scoping on or off."""
    case = tmp_path / f"case-{scoping}"
    tests = case / "tests"
    tests.mkdir(parents=True)
    (tests / "test_contended.py").write_text(FIXTURE_SUITE, encoding="utf-8")
    (case / "pytest.ini").write_text(FIXTURE_INI, encoding="utf-8")

    root = case / "resources"
    root.mkdir()

    env = dict(os.environ)
    # The OUTER run may itself be under xdist, and its worker id would otherwise
    # be inherited by this child's CONTROLLER. Strip both knobs so the child's
    # environment is decided here and not by however this suite was invoked.
    env.pop("PYTEST_XDIST_WORKER", None)
    env.pop("PYTEST_ADDOPTS", None)
    env["ISOLATION_ROOT"] = str(root)
    env["SCOPING"] = scoping

    return subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "-c", str(case / "pytest.ini"),
            "--rootdir", str(case),
            "-p", "no:cacheprovider",
            "-n", "2",
            "-q", str(tests),
        ],
        cwd=case, env=env, capture_output=True, text=True, timeout=300,
    )


def _claimed_names(tmp_path: Path, scoping: str) -> list[str]:
    return sorted(p.name for p in (tmp_path / f"case-{scoping}" / "resources").iterdir())


# --------------------------------------------------------------------------- #
# The two-sided case
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(
    shutil.which("python3") is None, reason="shells out to a python interpreter"
)
def test_worker_scoped_resources_let_the_fixture_suite_pass(tmp_path: Path) -> None:
    """GOOD: the resource path carries the worker id, so nothing collides.

    THE HALF THAT MATTERS for a control wedged at "red": a fixture suite that
    fails under every configuration would satisfy the red case below on its own
    and prove nothing about scoping. This is what separates the two.
    """
    result = _run_fixture_suite(tmp_path, "on")
    assert result.returncode == 0, (
        f"the worker-scoped run should be green.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    claimed = _claimed_names(tmp_path, "on")
    assert len(claimed) >= 2, (
        f"only {claimed} claimed, so fewer than two workers ran a test. The red "
        f"case below would then pass vacuously - one worker cannot collide with "
        f"itself - and this control would report 'isolation is fine' without ever "
        f"putting two workers in contention."
    )
    assert all(name.startswith("gw") for name in claimed), (
        f"claimed names {claimed} do not look like xdist worker ids, so the "
        f"resource path is not carrying the worker id and this run is green for "
        f"some other reason"
    )


@pytest.mark.skipif(
    shutil.which("python3") is None, reason="shells out to a python interpreter"
)
def test_defeating_worker_scoping_turns_the_fixture_suite_red(tmp_path: Path) -> None:
    """BAD: the worker id is removed from the resource path, and the run MUST fail.

    This is the recorded red, produced on every run rather than once by hand. If
    it ever goes green, worker isolation is no longer doing anything and every
    parallel green this repository has recorded since #1086 is a claim nobody can
    still support.
    """
    result = _run_fixture_suite(tmp_path, "off")
    assert result.returncode != 0, (
        f"removing the worker id from the resource path did NOT turn the suite "
        f"red, so this suite cannot detect broken worker isolation at all.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "FileExistsError" in (result.stdout + result.stderr), (
        f"the run failed, but not for the contention this case constructs - a "
        f"failure for some other reason is not evidence about isolation.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert _claimed_names(tmp_path, "off") == ["shared"], (
        "the defeated run should have produced exactly the one un-scoped name"
    )


# --------------------------------------------------------------------------- #
# ...and the same property, asserted about THIS suite's own run
# --------------------------------------------------------------------------- #
def test_tmp_path_carries_the_worker_id_under_xdist(tmp_path: Path) -> None:
    """The live assertion: this test's own `tmp_path` names its worker.

    The fixture suite above proves the DETECTION works. This asserts the property
    actually holds for the run in progress, which is the thing the detection is
    about.

    NOT WRITTEN AS A `skipif`, deliberately. A skip on the serial run and a skip
    on a parallel run whose worker id had vanished would print the same line, and
    the second is the failure this test exists to catch. So the serial branch
    ASSERTS what it observed instead: no worker id AND no test-run id, which is
    what a genuinely serial run looks like. A run carrying one without the other
    is under xdist with its scoping broken, and reddens here.

    pytest gives each xdist worker its own basetemp (`.../popen-gwN/`), and that
    is the mechanism every `tmp_path`-using test in this suite relies on for
    isolation - which is to say, nearly all of them. If it stops holding, tests
    that look independent start sharing a directory.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker is None:
        assert "PYTEST_XDIST_TESTRUNUID" not in os.environ, (
            "this run is under xdist (PYTEST_XDIST_TESTRUNUID is set) but carries "
            "no PYTEST_XDIST_WORKER, so worker identity has gone missing and "
            "nothing downstream can be scoped by it"
        )
        return

    assert worker in str(tmp_path), (
        f"tmp_path {tmp_path} does not carry worker id {worker!r}. Every test in "
        f"this suite that relies on tmp_path for isolation is now sharing a "
        f"directory with the other workers."
    )
