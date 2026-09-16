"""What `make verify` is wired to, and what may not silently stop being wired.

**This module deliberately carries NO skip guard.** Every assertion here reads
text out of `Makefile` and `.woodpecker.yml`; none shells out to anything. Its
siblings in `test_oscillation_control.py` are skipped when `git` is absent -
which is the CI environment - and two of these guards started life there, where
they would have been skipped in exactly the place they exist to protect. A guard
inert where it gates is the defect this repository keeps finding.

The four below answer one question in two directions:

- can the thing we just added be silently REMOVED? (`verify`'s membership, the
  declared tool set)
- can the thing we promised never to do be silently DONE? (`--exit-on-finding`
  in a recipe, `make verify` in CI)

Both are mechanism guards rather than instance fixes: the standing practice is
that after a repair you MUTATE THE REPAIR, and if the suite stays green the
repair is as unguarded as the defect was.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
WOODPECKER = ROOT / ".woodpecker.yml"


def recipe_lines() -> list[str]:
    """Lines `make` would RUN, not lines the Makefile contains.

    Recipe lines begin with a TAB. The distinction is not a nicety: the
    reversal trigger for `--exit-on-finding` is written in this same file as
    prose, so a substring search over the whole Makefile matches the sentence
    forbidding the thing and fails. Documenting a rule well makes a text guard
    about that rule MORE false-positive, not less.
    """
    return [ln for ln in MAKEFILE.read_text(encoding="utf-8").splitlines()
            if ln.startswith("\t")]


#: `make` invoking the `verify` target, on ONE line, comments removed. Scanned
#: per line so `\s` can never cross a newline and join two unrelated commands.
#: `verify(?![\w-])` rejects `verify-docs`, which a bare `\b` accepts.
MAKE_VERIFY = re.compile(r"\bmake\b(?:\s+\S+)*?\s+verify(?![\w-])")


def ci_make_verify_invocations(text: str) -> list[str]:
    """Every line in a pipeline document that runs make's `verify` target."""
    hits: list[str] = []
    for raw in text.splitlines():
        if raw.lstrip().startswith("#"):
            continue                       # a whole-line comment
        line = re.sub(r"\s#.*$", "", raw)  # ...and a trailing one
        m = MAKE_VERIFY.search(line)
        if m:
            hits.append(m.group(0).strip())
    return hits


def verify_prerequisites() -> list[str]:
    """The target list `verify:` depends on, with line continuations joined."""
    text = MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^verify:(.*?)(?=\n\S|\n\n)", text, re.MULTILINE | re.DOTALL)
    assert m, "no `verify:` target found; this module is asserting nothing"
    return m.group(1).replace("\\\n", " ").split()


# --------------------------------------------------------------------------- #
# Can what we added be silently removed?
# --------------------------------------------------------------------------- #

#: A TRIPWIRE, not a coverage map. It cannot know what `verify` *should*
#: contain; it fails loudly when something that IS there stops being there.
#: That is the failure mode with a live instance in this repo:
#: `check-negative-controls` is absent from `verify` today and nobody decided
#: it - the battery answering "can these gates fail" is simply not in the
#: aggregate gate, and every worker in this wave read a green `make verify` as
#: "the gates are healthy".
MUST_BE_IN_VERIFY = (
    "tools-check",
    "lint",
    "test",
    "typecheck",
    "shellcheck",
    "oscillation",
    "binary-guards-check",
    "negative-fixture-check",
    "scripts-inventory-check",
)


def test_verify_still_depends_on_each_gate_we_put_there() -> None:
    prereqs = verify_prerequisites()
    missing = [t for t in MUST_BE_IN_VERIFY if t not in prereqs]
    assert not missing, (
        f"these targets were dropped from `verify:` {missing}. If that was "
        f"deliberate, delete them from MUST_BE_IN_VERIFY in this test and say "
        f"why in the commit - the point is that it cannot happen silently."
    )


def test_the_declared_tool_set_cannot_be_quietly_shortened() -> None:
    """`tools-check` is an instrument, so it gets the same question as any other.

    A declaration that can be shortened reports a clean environment for a
    shorter list every time, and the report still says "ok". Nothing about the
    output would change.
    """
    text = MAKEFILE.read_text(encoding="utf-8")
    hard = re.search(r"^TOOLS_HARD\s*:=\s*(.+)$", text, re.MULTILINE)
    native = re.search(r"^TOOLS_NATIVE\s*:=\s*(.+)$", text, re.MULTILINE)
    assert hard and native, "the declared tool sets are gone entirely"

    declared = set(hard.group(1).split()) | set(native.group(1).split())
    required = {"git", "python3", "uv", "shellcheck", "gitleaks"}
    dropped = required - declared
    assert not dropped, (
        f"{sorted(dropped)} no longer appear in the declared set, so "
        f"`tools-check` will report a clean environment without checking them. "
        f"Two undeclared dependencies reached `make verify` in one day (#960, "
        f"#935); that is what this list exists to stop happening a third time."
    )


# --------------------------------------------------------------------------- #
# Can what we promised never to do be silently done?
# --------------------------------------------------------------------------- #

def test_no_build_recipe_passes_exit_on_finding() -> None:
    """REVERSAL TRIGGER 1 (#936), made checkable.

    `--exit-on-finding` exists solely so `controls/check-oscillation` can
    register a two-sided case - the control framework decides a case from the
    exit code, and this detector deliberately exits 0 for BOTH verdicts. In a
    build target it makes the detector BLOCKING, which the owner ruled against:
    a blocking detector that flags every threshold edit gets switched off, and
    switching it off is itself an oscillation.

    `scripts/check-oscillation.py` has CLAIMED since #936 that a test asserted
    this. No such test existed. The claim was unbackable then - there was no
    build target - and it was still a claim.
    """
    recipes = recipe_lines()
    assert recipes, "no recipe lines parsed; the parse is wrong, not the Makefile"
    assert any("check-oscillation.py" in ln for ln in recipes), (
        "no recipe runs check-oscillation.py, so the detector is not wired into "
        "the build and this guard is asserting nothing"
    )
    offending = [ln.strip() for ln in recipes if "--exit-on-finding" in ln]
    assert not offending, (
        f"a build recipe passes --exit-on-finding, so the detector is now "
        f"blocking: {offending}"
    )

    control = (ROOT / "controls" / "check-oscillation" / "control.json")
    assert "--exit-on-finding" in control.read_text(encoding="utf-8"), (
        "the control no longer passes --exit-on-finding, so its known-BAD case "
        "cannot be scored BAD"
    )


def test_no_ci_step_runs_make_verify() -> None:
    """REVERSAL TRIGGER 2 (#987), made checkable.

    `oscillation` sits in `verify` and not in CI because the detector needs git
    and the CI image has none - safe only while `verify` is a LOCAL gate. The
    whole placement rests on one fact about a file in someone else's lane, so
    the fact is asserted rather than assumed.

    MATCHED ON A COMMAND SHAPE, not the literal string `make verify`. The first
    cut scanned only lines starting with `- ` for that substring, and both
    `- make -j2 verify` and a YAML block scalar containing the command slipped
    through - reproduced against the assertion before it was widened.
    """
    hits = ci_make_verify_invocations(WOODPECKER.read_text(encoding="utf-8"))
    assert not hits, (
        f"a CI step now invokes make's verify target: {hits}. The oscillation "
        f"target's git dependency has just become a CI dependency - give that "
        f"step a git-bearing image, or take `oscillation` out of `verify`."
    )


#: Innocent text that must NOT trip the guard, beside the shapes that must.
#: Every one of these was a false positive in the first cut, reproduced rather
#: than imagined: the pattern ran over the WHOLE document, so `\s` crossed
#: newlines and `- make lint` followed by `- echo verify complete` matched as a
#: single invocation; `verify\b` accepted `verify-docs` because a hyphen is a
#: word boundary; and inline comments were never stripped. A guard that blocks
#: valid CI changes gets removed, and then it guards nothing.
CI_GUARD_CASES = [
    ("      - make verify", True),
    ("      - make -j2 verify", True),
    ("      - |\n          set -e\n          make verify", True),
    ("      - make lint verify", True),
    ("      - make lint\n      - echo verify complete", False),
    ("      - make verify-docs", False),
    ("      - echo ready # make verify is local only", False),
    ("      # - make verify", False),
    ("      - uv run pytest", False),
]


@pytest.mark.parametrize("snippet,should_trip", CI_GUARD_CASES,
                         ids=[c[0][:34] for c in CI_GUARD_CASES])
def test_the_ci_guard_trips_on_invocations_and_not_on_prose(
    snippet: str, should_trip: bool
) -> None:
    """The guard's own two-sided case.

    A guard with only positive cases is a guard against the one spelling its
    author imagined; a guard with only negative ones cannot fail at all.
    """
    assert bool(ci_make_verify_invocations(snippet)) is should_trip
