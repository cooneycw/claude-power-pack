"""Model-presence checks key on the FULL model name, not a prefix (#910).

`curl /api/tags | grep -q "${GEMMA_MODEL%%:*}"` strips at the first colon, so
`gemma4:31b-it-qat` becomes `gemma4` - which also matches `gemma4-code:latest`.
The check passes with the configured model entirely absent, provided a sibling
sharing its prefix is registered. Both hosts register exactly such a pair.

IT WAS TEN SITES, NOT THE TWO THE ISSUE NAMES, and the difference is the point.
The issue's title says "shadowed by #903's serveability probe, not fixed", and
that is true at the two sites its author examined: a spurious tags pass is
caught downstream by a stronger probe. At the other EIGHT there is no probe at
all. Each of those prints an affirmative line interpolating the FULL model name
after checking only a prefix::

    [x] Model present: $QWEN_MODEL

- a success message claiming more than its input population supports, inside
the diagnostic commands people run to find out whether the lane works.

WHY THE DETECTOR IS NOT LINE-ORIENTED. Two of the ten split the pipeline across
lines - `TAGS=$(curl ... api/tags)` and then `if echo "$TAGS" | grep -q ...` -
so a single-line pattern sees eight and certifies the remaining two clean
forever. A line-oriented tripwire here would be the bug with a test around it.
The detector resolves the tags-derived variable across the file instead.

THE NEGATIVE CONTROL IS THE REAL PRE-FIX TREE, not a synthetic fixture. The
detector is run against the file contents as they existed at this branch's
merge base, and REQUIRED to find every known site there. A detector that finds
nothing proves nothing about a tree where nothing is wrong, so it is pointed at
a tree where everything was.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
COMMANDS = REPO / ".claude" / "commands"

# NO COUNT LIVES HERE (issue #910, condition B3). An earlier cut of this file
# pinned "exactly ten" per file, and a tripwire built to a hardcoded number
# certifies whatever it was not told about - the same defect as a hardcoded
# denominator, which this repository landed fixes for twice on the day this was
# written. A twelfth site added next month must fail this automatically, which
# a number cannot do.
#
# The population is DERIVED: every `${VAR%%:*}` used AS A GREP PATTERN. After
# the fix that set must be EMPTY; before it, non-empty and containing the
# split-line forms.

# The two sites whose pipeline spans two lines. Named not as a count but as the
# proof that the detector is not line-oriented: a single-line pattern reports
# eight where this reports ten, and these are the two it cannot see.
SPLIT_LINE_SITES = (
    ".claude/commands/qwen/status.md",
    ".claude/commands/gemma/status.md",
)

PREFIX_FILES = (
    ".claude/commands/qwen/auto.md",
    ".claude/commands/gemma/auto.md",
    ".claude/commands/qwen/status.md",
    ".claude/commands/gemma/status.md",
    ".claude/commands/cpp/init.md",
    ".claude/commands/cpp/status.md",
    ".claude/commands/cpp/update.md",
)

# `${VAR%%:*}` appearing as a grep PATTERN. Deliberately NOT restricted to
# /api/tags: site eleven greps `ollama ps` by prefix and would have been
# excluded by a tags-shaped detector, which is how it survived the issue, my
# first sweep and the orchestrator's.
GREP_PATTERN_PREFIX = re.compile(r'grep[^|]*"\$\{(\w+)%%:\*\}"')


def prefix_grep_patterns(text: str) -> list[tuple[int, str]]:
    """Every `${VAR%%:*}` used as a grep PATTERN, whatever it greps."""
    return [
        (i, line.strip())
        for i, line in enumerate(text.splitlines(), 1)
        if GREP_PATTERN_PREFIX.search(line)
    ]


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "model_presence"


def _fixture_sites(name: str) -> list[tuple[str, str]]:
    """(origin, line) pairs from a committed fixture.

    Committed rather than read from a git ref. An earlier cut ran the detector
    against `git merge-base HEAD origin/main`, which stops being a PRE-FIX
    reference the moment this lands on main - the control would then find
    nothing, fail its own non-empty assertion, and do so on every branch cut
    afterwards. A control that destroys itself on merge. Codex caught it.
    """
    out: list[tuple[str, str]] = []
    origin = ""
    for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines():
        if line.startswith("# from "):
            origin = line[len("# from "):]
        elif line.strip() and not line.startswith("#"):
            out.append((origin, line))
    return out


def test_the_detector_finds_EXACTLY_the_defective_population() -> None:
    """THE CONTROL, with exact set equality against a committed pre-fix sample.

    "Some match overall" was not enough: a detector restricted to `echo "$TAGS"`
    satisfied it while ignoring every direct curl pipeline and the `ollama ps`
    site. Equality over the whole population is what proves coverage, and it
    carries no number - the population comes from the fixture.
    """
    sites = _fixture_sites("defective_pre_fix.txt")
    assert sites, "the defective fixture is empty - this control checks nothing"

    detected = {origin for origin, line in sites if prefix_grep_patterns(line)}
    expected = {origin for origin, _ in sites}
    missed = expected - detected
    assert not missed, (
        f"the detector does not see {len(missed)} of {len(expected)} known "
        f"defective sites: {sorted(missed)}. A detector that finds fewer sites "
        f"than existed certifies the remainder clean forever."
    )

    # BOTH SHAPES, named rather than counted: a line-oriented pattern sees the
    # direct pipelines and misses the variable-fed ones.
    assert any("status.md" in o for o in detected), "no split-line site detected"
    assert any("auto.md" in o for o in detected), "no direct-pipeline site detected"
    assert any("OLLAMA_PS" in line for _, line in sites), (
        "the fixture no longer carries the residency site, which a tags-shaped "
        "detector would have excluded"
    )


def test_no_grep_pattern_uses_a_prefix_now() -> None:
    """THE ASSERTION THE FIX EXISTS FOR - the population must be EMPTY.

    Derived over every command document and carrying no number, so a twelfth
    site added next month fails this on the day it lands.

    This test was DELETED for a while during review - I replaced the block it
    sat in while swapping out a different control, and the only tell was the
    collected count dropping from 21 to 12. Restored, and recorded because the
    file's primary assertion going missing is exactly the kind of absence the
    rest of this module exists to make loud.
    """
    offenders: list[str] = []
    for path in sorted(COMMANDS.rglob("*.md")):
        for lineno, line in prefix_grep_patterns(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(REPO)}:{lineno}: {line}")
    assert not offenders, (
        "a grep still matches on a model PREFIX, so it answers for any "
        "prefix-sharing sibling rather than the configured model:\n"
        + "\n".join(offenders)
    )


def test_the_detector_flags_NONE_of_the_legitimate_uses() -> None:
    """The GOOD half. A detector flagging all twenty is as useless as one
    flagging none, and only this direction catches it."""
    sites = _fixture_sites("legitimate_uses.txt")
    assert sites, "the legitimate fixture is empty - this control checks nothing"
    flagged = [(o, ln) for o, ln in sites if prefix_grep_patterns(ln)]
    assert not flagged, (
        f"the detector flags legitimate path derivations: {flagged}. Forcing "
        f"those to 'pass' means a blanket removal, which breaks the OpenCode "
        f"model reference."
    )


@pytest.mark.parametrize(
    "rel", sorted({o.rsplit(":", 1)[0] for o, _ in _fixture_sites("legitimate_uses.txt")}), ids=str
)
def test_every_legitimate_occurrence_survives(rel: str) -> None:
    """NEGATIVE MEMBERSHIP, counted per occurrence (#910 condition D).

    Substring membership let one occurrence stand in for another: cpp/init.md
    carries `NAME="${entry%%:*}"` TWICE, and removing the first left an `in
    text` assertion passing on the second. Multiplicity is checked instead, so
    losing either one fails.
    """
    from collections import Counter
    want = Counter(
        ln for o, ln in _fixture_sites("legitimate_uses.txt") if o.rsplit(":", 1)[0] == rel
    )
    text = (REPO / rel).read_text(encoding="utf-8")
    have = Counter()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in want:
            have[stripped] += 1
    for line, n in want.items():
        assert have[line] >= n, (
            f"{rel}: expected at least {n} occurrence(s) of {line!r}, found "
            f"{have[line]}. A legitimate path derivation was removed along with "
            f"the defective greps."
        )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash runs the shipped expression")
@pytest.mark.parametrize(
    "registered,model,expect_found",
    [
        ('{"models":[{"name":"gemma4:31b-it-qat"}]}', "gemma4:31b-it-qat", True),
        ('{"models":[{"name":"gemma4-code:latest"}]}', "gemma4:31b-it-qat", False),
        ('{"models":[{"name":"gemma4:31b-it-qat-extra"}]}', "gemma4:31b-it-qat", False),
        ('{"models":[{"name":"ns/gemma4:31b-it-qat"}]}', "gemma4:31b-it-qat", False),
    ],
    ids=["exact-present", "prefix-sibling", "longer-tag", "namespaced"],
)
def test_the_SHIPPED_manifest_check_discriminates(
    registered: str, model: str, expect_found: bool
) -> None:
    """EXECUTED against the shipped grep expression, not a stand-in.

    The first cut asserted against a Python `exact_hit()` helper, which tests
    the helper: stripping the JSON quote boundaries from the SHIPPED checks left
    every case green while `gemma4:31b-it-qat-extra` was accepted for an absent
    `gemma4:31b-it-qat`. A test that supplies its own implementation of the
    thing under test cannot fail for the reason it exists. Codex found it.

    Both directions are required: asserting only that the sibling payload fails
    is satisfied by a check wedged at 'absent', which breaks every real
    preflight while looking like a working guard.

    `namespaced` expects ABSENT and I had it backwards on the first cut. The
    quoted form needs an opening quote where `"ns/gemma4...` has a slash, so
    the match correctly fails - which is the right answer, since a host
    registering the model under a namespace does not have it under the bare
    name. The test caught my expectation rather than the code, and that is
    recorded because adjusting an expectation to match observed output is how a
    control gets laundered into agreement.
    """
    greps = _tags_greps()
    assert greps, "no shipped manifest check found - this test checks nothing"
    m = re.search(r'grep -qF "(\\"\$(\w+)\\")"', greps[0][1])
    assert m, f"the shipped check has an unexpected shape: {greps[0][1]}"
    pattern, var = m.group(1), m.group(2)

    script = f'printf %s "$TAGS" | grep -qF "{pattern}" && echo FOUND || echo ABSENT'
    proc = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True,
        # negative-fixture: allow PATH is isolation, not an absence
        env={"PATH": "/usr/bin:/bin", "TAGS": registered, var: model},
    )
    got = "FOUND" in proc.stdout
    assert got is expect_found, (
        f"shipped check on {registered} for {model}: expected "
        f"{'FOUND' if expect_found else 'ABSENT'}, got {proc.stdout.strip()}"
    )


# `ollama ps` rows, kept short so the parametrize table stays readable.
PS_HDR = "NAME                     ID    SIZE   PROCESSOR         UNTIL\n"
PS_RESIDENT = PS_HDR + "gemma4:31b-it-qat  ab1  20 GB  100% GPU  4m\n"
PS_SPILLED = PS_HDR + "gemma4:31b-it-qat  ab1  20 GB  73%/27% CPU/GPU  4m\n"
PS_SIBLING = PS_HDR + "gemma4-code:latest  cd2  18 GB  100% GPU  4m\n"
PS_LONGER = PS_HDR + "gemma4:31b-it-qat-extra  x  9 GB  100% GPU  4m\n"
PS_NAMESPACED = PS_HDR + "ns/gemma4:31b-it-qat  y  9 GB  100% GPU  4m\n"
PS_BOTH = PS_SIBLING + "gemma4:31b-it-qat  ab1  20 GB  73%/27% CPU/GPU  4m\n"


def _tags_greps() -> list[tuple[str, str]]:
    """EVERY line that greps a model variable against the tags manifest.

    Enumerated INDEPENDENTLY of the shape being asserted. The first cut
    extracted only lines already matching the CORRECT shape, so stripping the
    JSON quote boundaries from a shipped check removed it from the population
    rather than failing it - the detector's denominator shrank silently and the
    suite stayed green. A control whose population is defined by the property
    it checks cannot fail.
    """
    out: list[tuple[str, str]] = []
    for path in sorted(COMMANDS.rglob("*.md")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "grep" not in line or "MODEL" not in line:
                continue
            if "api/tags" in line or '"$TAGS"' in line:
                out.append((f"{path.relative_to(REPO)}:{i}", line.strip()))
    return out


def test_every_tags_grep_matches_the_quoted_full_name() -> None:
    """Shape asserted over an INDEPENDENTLY enumerated population.

    A check that drops its quote boundaries is still a tags grep, so it stays
    in this population and fails here - which is what the shape assertion in
    the executed test could not do on its own.
    """
    greps = _tags_greps()
    assert greps, "no tags grep found at all - this control checks nothing"
    bad = [
        f"{origin}: {line}" for origin, line in greps
        if not re.search(r'grep -qF "\\"\$\w+_MODEL\\""', line)
    ]
    assert not bad, (
        "a manifest check does not match the quoted full model name, so it "
        "accepts a longer tag or a prefix sibling:\n" + "\n".join(bad)
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required to execute the block")
@pytest.mark.parametrize(
    "ps_output,expect",
    [
        (PS_HDR, "NOT LOADED"),
        (PS_SPILLED, "spilled"),
        (PS_RESIDENT, "resident"),
        (PS_SIBLING, "NOT LOADED"),
        # Codex: `grep -F "$MODEL"` matched these, so a longer tag or a
        # namespaced sibling answered for the configured model.
        (PS_LONGER, "NOT LOADED"),
        (PS_NAMESPACED, "NOT LOADED"),
        # A real table: sibling AND configured model both listed.
        (PS_BOTH, "spilled"),
    ],
    ids=["not-loaded", "spilled-to-cpu", "fully-resident", "sibling-only",
         "longer-tag-sibling", "namespaced-sibling", "both-rows-present"],
)
def test_the_residency_check_distinguishes_all_three_outcomes(
    ps_output: str, expect: str, tmp_path: Path
) -> None:
    """THREE outcomes, executed (issue #910 condition B2).

    Two of them used to collide: `grep X | grep -qv "100% GPU"` returns 1 when
    NO row matched and also when every matching row is resident, so "not loaded
    at all" and "perfectly resident" produced identical SILENCE - in the command
    that exists to report exactly that difference.

    A control asserting only the spilled case passes on the pre-fix code, which
    is why all three are committed. The fourth case is the prefix collision:
    with only the sibling loaded, the answer must be NOT LOADED.
    """
    # Through the ENVIRONMENT so newlines survive. An earlier cut interpolated
    # `{ps_output!r}` into the script: Python's repr turns a newline into a
    # literal backslash-n, which bash inside double quotes does not decode, so
    # awk received ONE record instead of a realistic multi-line `ollama ps`
    # table. Single-row fixtures concealed it; the header rows below do not.
    proc = subprocess.run(
        ["bash", "-c", 'GEMMA_MODEL="gemma4:31b-it-qat"\n' + _residency_block()],
        capture_output=True, text=True,
        # negative-fixture: allow PATH is isolation, not an absence
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "OLLAMA_PS": ps_output},
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"the residency block errored:\n{out}"

    # EXCLUSIVE, not merely present. "100% GPU resident" is a SUBSTRING of
    # "not 100% GPU resident", so asserting the healthy marker also matched the
    # warning - replacing the condition with `elif true` left every case green
    # while reporting every loaded model as spilled. Each outcome now requires
    # its own marker AND the absence of the other two.
    markers = {
        "NOT LOADED": "is NOT LOADED",
        "spilled": "spilled to CPU",
        "resident": "is loaded and 100% GPU resident",
    }
    assert markers[expect] in out, f"expected the {expect} line, got:\n{out}"
    for other, text in markers.items():
        if other != expect:
            assert text not in out, (
                f"output claims {other} as well as {expect} - the three outcomes "
                f"are not exclusive:\n{out}"
            )


def _residency_block() -> str:
    """The shipped residency branch, lifted from gemma/status.md."""
    text = (REPO / ".claude/commands/gemma/status.md").read_text(encoding="utf-8")
    start = text.index('    GEMMA_ROW=$(echo "$OLLAMA_PS"')
    end = text.index("    fi", start) + len("    fi")
    return text[start:end]
