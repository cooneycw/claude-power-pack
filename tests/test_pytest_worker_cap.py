"""The worker cap is EXPLICIT, and `auto` is refused (issues #640, #1086).

WHY THIS IS A TEST AND NOT A COMMENT. `scripts/pytest-workers.sh` is a gate that
lets work through: `make test` and the CI `validate` step pass its number straight
to `-n` and neither re-derives it. Its refusal is the only thing between a
host-set `PYTEST_WORKERS=auto` and one worker per core - 24 on this host, times
however many invocations are in flight, on a box that routinely carries four to
nine concurrent CPP suites from flow worktrees. The symptom of getting that wrong
is not a slow machine; it is intermittent reds that read as regressions in
whatever changed most recently.

#640 shipped exactly this precedence - `PYTEST_WORKERS` then `CPP_TEST_WORKERS` -
in `lib/cicd/steps.py`, FOR CONSUMER PROJECTS, and its issue body names this host's
contention as the reason. CPP never applied it to itself. So the precedence is
asserted against BOTH implementations here rather than against the shell script
alone: two copies of one convention that agree today and have nothing holding them
together tomorrow is the shape this repository keeps finding broken later.

THE CASE IS TWO-SIDED, which is the whole point of committing it. A guard that
refused everything would satisfy the `auto` half on its own and would break every
run; a guard that refused nothing would satisfy the accept half and would be the
blindness this exists to prevent. Both directions are here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from lib.cicd.steps import ShellStep, StepDef

ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "scripts" / "pytest-workers.sh"

requires_sh = pytest.mark.skipif(
    shutil.which("sh") is None, reason="shells out to sh to run the resolver"
)


def _resolve(**overrides: str) -> subprocess.CompletedProcess:
    """Run the resolver with a controlled environment.

    The two knobs are DELETED rather than set to "", because an empty string and
    an absent variable are different inputs to this resolver and a test that
    could not tell them apart would not notice the resolver losing that
    distinction either.
    """
    env = dict(os.environ)
    for key in ("PYTEST_WORKERS", "CPP_TEST_WORKERS"):
        env.pop(key, None)
    env.update(overrides)
    return subprocess.run(
        ["sh", str(RESOLVER)], env=env, capture_output=True, text=True, timeout=60
    )


# --------------------------------------------------------------------------- #
# REFUSED - the known-bad half
# --------------------------------------------------------------------------- #
@requires_sh
@pytest.mark.parametrize("source", ["PYTEST_WORKERS", "CPP_TEST_WORKERS"])
def test_auto_is_refused_from_either_variable(source: str) -> None:
    """`auto` must not resolve, from EITHER knob.

    Parametrised over both because a guard written against only the higher-
    precedence variable is silently absent for the lower one, and a host is just
    as able to export `CPP_TEST_WORKERS=auto`.
    """
    result = _resolve(**{source: "auto"})
    assert result.returncode == 2, (
        f"{source}=auto resolved instead of being refused; the cap is now one "
        f"worker per core on a shared 24-core host.\n{result.stdout}\n{result.stderr}"
    )
    assert "REFUSED" in result.stderr
    assert result.stdout.strip() == "", (
        "a refusal must print no number - a caller doing `-n \"$(...)\"` would "
        "otherwise use it"
    )


@requires_sh
@pytest.mark.parametrize("value", ["", "-3", "4.5", "eight", "8x", " "])
def test_a_value_that_is_not_a_positive_integer_is_refused(value: str) -> None:
    """Anything `-n` could not use is refused BEFORE pytest sees it.

    The empty string is in this list deliberately: `PYTEST_WORKERS=` exported by
    a wrapper is the most likely accident, and it must fall through to the
    default rather than resolving to nothing.
    """
    result = _resolve(PYTEST_WORKERS=value)
    if value == "":
        # An EMPTY value is UNSET and falls through to the next source in the
        # chain. A value of " " is not empty - it is a non-empty value that is
        # not a number, and it is refused like any other. The two are separate
        # cases here because the first cut of this test collapsed them with
        # `value.strip()`, which asserted the resolver should silently accept
        # whitespace as "nothing supplied" - a caller who exported a space meant
        # something, and guessing what is how a wrong number gets used quietly.
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().isdigit()
        return
    assert result.returncode == 2, f"{value!r} resolved: {result.stdout!r}"
    assert "REFUSED" in result.stderr


@requires_sh
def test_zero_workers_is_refused() -> None:
    """`0` is a positive-integer failure that digit-matching alone would admit."""
    result = _resolve(PYTEST_WORKERS="0")
    assert result.returncode == 2, result.stdout
    assert "REFUSED" in result.stderr


# --------------------------------------------------------------------------- #
# ACCEPTED - the known-good half, and the precedence
# --------------------------------------------------------------------------- #
@requires_sh
@pytest.mark.parametrize(
    ("env", "expected", "expected_source"),
    [
        ({"PYTEST_WORKERS": "8", "CPP_TEST_WORKERS": "3"}, "8", "PYTEST_WORKERS"),
        ({"CPP_TEST_WORKERS": "3"}, "3", "CPP_TEST_WORKERS"),
        ({}, None, "pytest-workers.sh default"),
    ],
)
def test_the_precedence_is_pytest_workers_then_cpp_then_the_default(
    env: dict[str, str], expected: str | None, expected_source: str
) -> None:
    """The #640 chain, end to end, including which source was used.

    `expected` is None for the default case on purpose: pinning the default's
    VALUE here would make this test fail on a deliberate re-tune of the number,
    which is a decision and not a regression. What must not change silently is
    that a default exists, is a positive integer, and SAYS it is the default.
    """
    result = _resolve(**env)
    assert result.returncode == 0, result.stderr
    resolved = result.stdout.strip()
    assert resolved.isdigit() and int(resolved) > 0, resolved
    if expected is not None:
        assert resolved == expected
    assert expected_source in result.stderr, (
        f"the resolver did not name {expected_source} as the source; the cap is "
        f"in the output but where it came from is not, and those are different "
        f"facts when three sources can supply it"
    )


@requires_sh
def test_the_resolved_cap_appears_in_the_output() -> None:
    """Acceptance item: "the cap visible in the run's output".

    Visible means a reader of the log can see the number without opening the
    Makefile or `.woodpecker.yml`. The stderr line is what makes that true, and
    it is separate from stdout so the value stays machine-consumable.
    """
    result = _resolve(PYTEST_WORKERS="6")
    assert "pytest-workers: -n 6" in result.stderr, result.stderr


# --------------------------------------------------------------------------- #
# The two implementations of one convention must agree
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"PYTEST_WORKERS": "8", "CPP_TEST_WORKERS": "3"}, ("8", "host-env")),
        ({"CPP_TEST_WORKERS": "3"}, ("3", "CPP_TEST_WORKERS")),
    ],
)
def test_the_runner_resolves_the_same_precedence_as_the_shell_resolver(
    env: dict[str, str], expected: tuple[str, str]
) -> None:
    """`lib/cicd/steps.py` is the OTHER implementation of this chain (#640).

    It is not called by `make test` - it sets the variable that `make test`'s
    recipe then reads - so the two are genuinely independent code paths over one
    convention. Asserting both here is what keeps them one convention.
    """
    step = ShellStep(StepDef(id="test", command="pytest"))
    assert step.resolve_pytest_workers({"env": env}) == expected


def _executed_lines() -> dict[str, list[str]]:
    """What the two build surfaces RUN, not what their files contain.

    THIS DISTINCTION IS THE TEST, not a nicety - and it was found by running the
    first cut, which matched the Makefile comment that FORBIDS `-n auto` and
    reported the Makefile as passing it. Documenting a rule well makes a text
    guard about that rule MORE false-positive, not less;
    `tests/test_verify_wiring.py::recipe_lines` carries the same lesson for the
    same file.

    Makefile: recipe lines begin with a TAB. `.woodpecker.yml`: the `commands:`
    lists, parsed, so a `#` comment anywhere in that file is structurally out of
    scope rather than stripped by a pattern that might not strip it.
    """
    makefile = [
        ln for ln in (ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
        if ln.startswith("\t")
    ]
    spec = yaml.safe_load((ROOT / ".woodpecker.yml").read_text(encoding="utf-8"))
    commands = [
        command
        for step in spec["steps"].values()
        for command in step.get("commands", [])
    ]
    return {"Makefile": makefile, ".woodpecker.yml": commands}


def test_no_shipped_caller_passes_n_auto() -> None:
    """The prohibition, made checkable.

    A comment saying "never `auto`" is a claim about intent. This is a claim
    about what executes: neither build surface may hand `-n auto` to pytest,
    however the number is otherwise resolved.
    """
    for name, lines in _executed_lines().items():
        offending = [
            line.strip() for line in lines if "-n auto" in line or "-n=auto" in line
        ]
        assert not offending, (
            f"{name} passes `-n auto`: {offending}. On this host that is 24 "
            f"workers per invocation, multiplied by everything else in flight."
        )


def test_both_build_surfaces_actually_go_through_the_resolver() -> None:
    """...and the prohibition above is not satisfied by nobody running pytest.

    THE PRECONDITION for the previous test. A `Makefile` with no pytest call and
    a `.woodpecker.yml` with no test step would both contain no `-n auto`, and
    that green would say nothing at all. This is what separates "does not use
    auto" from "does not run tests".
    """
    for name, lines in _executed_lines().items():
        joined = "\n".join(lines)
        assert "pytest-workers.sh" in joined, (
            f"{name} no longer resolves its worker count through "
            f"scripts/pytest-workers.sh, so the `auto` refusal does not apply to "
            f"it and the guard above is asserting nothing about this surface"
        )
        assert "-n " in joined, f"{name} does not pass -n to pytest at all"
