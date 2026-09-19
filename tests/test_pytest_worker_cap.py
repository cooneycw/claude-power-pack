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
import re
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
    raw = (ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
    # Recipe lines JOINED across `\` continuations, so one logical shell command
    # is one entry. `make test` resolves the cap and invokes pytest on the same
    # continued line, and splitting them would make the two halves look like
    # unrelated commands to the guard below - which is precisely the mistake it
    # exists to catch in the yaml.
    makefile: list[str] = []
    pending = ""
    for ln in raw:
        if not ln.startswith("\t") and not pending:
            continue
        pending += ln.rstrip("\\") if ln.endswith("\\") else ln
        if not ln.endswith("\\"):
            makefile.append(pending)
            pending = ""
    if pending:
        makefile.append(pending)
    spec = yaml.safe_load((ROOT / ".woodpecker.yml").read_text(encoding="utf-8"))
    commands = [
        command
        for step in spec["steps"].values()
        for command in step.get("commands", [])
    ]
    return {"Makefile": makefile, ".woodpecker.yml": commands}


#: A REAL pytest invocation. `(?![\w./-])` is what keeps `pytest-workers.sh` out:
#: a bare `"pytest" in cmd` substring test is satisfied by the RESOLVER's own
#: filename, so `sh scripts/pytest-workers.sh -n 8` - which runs no tests at all -
#: passed the first two versions of these guards (counter-model review pass 2,
#: #1086, gpt-6-astra). The guard was reading its own helper as its subject.
PYTEST_TOKEN = re.compile(r"(?<![\w./-])pytest(?![\w./-])")

#: The `-n` argument, with its quoting. Attribution matters as much as the value:
#: an unrelated `grep -n auto README.md` in a recipe is not a pytest worker count,
#: and the literal-substring version rejected it. Conversely `-n "auto"` IS one
#: and the literal version missed it. Both directions were reproduced.
#: `\S+` LAST, because it cannot span the spaces inside `$(sh scripts/... )`:
#: against `-n "$(sh scripts/pytest-workers.sh)"` it captured `"$(sh` and the
#: wiring check then saw no resolver at all. A quoted string or a command
#: substitution is ONE argument and must be captured whole.
DASH_N = re.compile(r"""-n[=\s]+("[^"]*"|'[^']*'|\$\([^)]*\)|\S+)""")

#: Same LENGTH as the resolver's filename, so masking it to keep `PYTEST_TOKEN`
#: off the helper does not shift the offsets used to read the original string.
_MASK = "R" * len("pytest-workers.sh")


def _pytest_invocations(commands: list[str]) -> list[str]:
    """Commands that actually run pytest, resolver mentions excluded."""
    out = []
    for cmd in commands:
        stripped = _normalise(cmd).replace("pytest-workers.sh", _MASK)
        if PYTEST_TOKEN.search(stripped):
            out.append(cmd)
    return out


def _normalise(cmd: str) -> str:
    """One spelling for both surfaces.

    `make` escapes a shell `$` as `$$` in a recipe, so the SAME command reads
    `"$$workers"` in the Makefile and `"$workers"` in the yaml. A guard that
    understands only one of those silently stops applying to the other - and the
    Makefile is the surface `/flow:finish` actually runs.
    """
    return cmd.replace("$$", "$")


def _worker_arg(cmd: str) -> str | None:
    """The value pytest's `-n` receives, unquoted, or None if it has none.

    Read from the ORIGINAL text at an offset found in the masked copy, so the
    resolver's filename is invisible to the pytest-token search and still visible
    in the value - which is the whole point of the wiring check.
    """
    norm = _normalise(cmd)
    masked = norm.replace("pytest-workers.sh", _MASK)
    token = PYTEST_TOKEN.search(masked)
    if not token:
        return None
    m = DASH_N.search(norm, token.start())
    if not m:
        return None
    return m.group(1).strip().strip("\"'")


def test_no_shipped_caller_passes_n_auto() -> None:
    """The prohibition, attributed to the pytest invocation that owns the flag.

    Two failures the literal `"-n auto" in line` version had, both reproduced:
    it MISSED `pytest -n "auto"`, which the shell passes to pytest as `auto`; and
    it REJECTED `grep -n auto README.md`, which is not a worker count at all.
    Reading the argument of an actual pytest invocation answers the question that
    was being asked instead of one that merely looks like it.
    """
    for name, lines in _executed_lines().items():
        for cmd in _pytest_invocations(lines):
            value = _worker_arg(cmd)
            assert value != "auto", (
                f"{name} passes `-n auto` to pytest: {cmd.strip()[:160]}. On this "
                f"host that is 24 workers per invocation, multiplied by everything "
                f"else in flight."
            )


def test_an_unrelated_dash_n_is_not_read_as_a_worker_count() -> None:
    """The other direction of the same guard, committed as a case.

    A prohibition that fires on `grep -n` would be routed around within a week,
    and the routing-around is what actually removes the protection. This pins
    that it does not.
    """
    assert _pytest_invocations(["grep -n auto README.md"]) == []
    assert _pytest_invocations(["sh scripts/pytest-workers.sh -n 8"]) == [], (
        "the resolver's own filename contains 'pytest' - if it is read as a "
        "pytest invocation, a command that runs no tests satisfies every guard here"
    )
    assert _worker_arg('uv run pytest -n "auto"') == "auto"
    assert _worker_arg("uv run pytest -n 8") == "8"
    # A command substitution is ONE argument, spaces and all.
    assert _worker_arg('uv run pytest -n "$(sh scripts/pytest-workers.sh)"') == (
        "$(sh scripts/pytest-workers.sh)"
    )
    assert _worker_arg("uv run pytest") is None


def test_both_build_surfaces_actually_go_through_the_resolver() -> None:
    """...and the prohibition above is not satisfied by nobody running pytest.

    THE PRECONDITION for the previous test. A `Makefile` with no pytest call and
    a `.woodpecker.yml` with no test step would both contain no `-n auto`, and
    that green would say nothing at all. This is what separates "does not use
    auto" from "does not run tests".
    """
    for name, lines in _executed_lines().items():
        # ONE command must carry all three, not three substrings scattered across
        # the file. The first cut joined every command and asked whether
        # `pytest-workers.sh` and `-n ` appeared ANYWHERE - so deleting the real
        # pytest invocation and leaving an unrelated step that merely mentioned
        # the resolver kept both assertions green (counter-model review, #1086,
        # gpt-6-astra, MEDIUM: "the guard searches all commands for two
        # independent substrings without establishing that pytest executes or
        # consumes the resolver's output").
        invocations = _pytest_invocations(lines)
        assert invocations, (
            f"{name} runs no pytest at all, so the `auto` prohibition above is "
            f"asserting nothing about this surface. Commands examined:\n"
            + "\n".join(f"  {c[:120]}" for c in lines[:40])
        )

        # THE CAP MUST REACH PYTEST, not merely be computed nearby. Both earlier
        # versions accepted `workers="$(sh scripts/pytest-workers.sh)"; uv run
        # pytest -n 24` - resolver invoked, verdict discarded, hard-coded 24 sent
        # instead (counter-model review pass 2). So the `-n` argument itself must
        # be tied to the resolver: either a direct command substitution, or a
        # variable this same command assigned from one.
        wired = []
        for cmd in invocations:
            value = _worker_arg(cmd)
            if value is None:
                continue
            if "pytest-workers.sh" in value:
                wired.append(cmd)
                continue
            var = re.fullmatch(r"\$\{?(\w+)\}?", value)
            # `["\']?` because the assignment is `workers="$(...)"`, quote included.
            if var and re.search(
                rf"{re.escape(var.group(1))}=[\"']?\$\([^)]*pytest-workers\.sh[^)]*\)",
                _normalise(cmd),
            ):
                wired.append(cmd)
        assert wired, (
            f"{name} runs pytest, but no invocation takes its `-n` value from "
            f"scripts/pytest-workers.sh - so the resolver's refusal of `auto` and "
            f"its cap do not govern what actually runs. Invocations examined:\n"
            + "\n".join(f"  {c.strip()[:160]}" for c in invocations)
        )
