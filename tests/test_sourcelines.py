"""`lib.sourcelines.source_lines` must agree with CPython's tokenizer (issue #1110).

WHAT THESE TESTS ARE FOR, AND WHAT THEY ARE NOT. They pin the helper's contract
against `ast` - the only authority that matters, since the whole point is that a
waiver's line number and a site's line number end up in one coordinate system.
They are NOT this helper's negative control. That role is held by the committed
cases of the two gates that use it (see the module docstring in
`lib/sourcelines.py`), which go red the moment the two coordinate systems
diverge again. These tests would keep passing against a helper that was
self-consistently wrong about something `ast` never told us; the gate cases
would not.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.sourcelines import source_lines  # noqa: E402

#: Every character `str.splitlines()` ends a line on that the tokenizer does
#: not. This list IS the defect's surface: each one, appearing raw anywhere in a
#: file, shifted every `splitlines()` line number after it.
SPLITLINES_ONLY = (
    pytest.param("\v", id="U+000B-vertical-tab"),
    pytest.param("\f", id="U+000C-form-feed"),
    pytest.param("\x1c", id="U+001C-file-separator"),
    pytest.param("\x1d", id="U+001D-group-separator"),
    pytest.param("\x1e", id="U+001E-record-separator"),
    pytest.param("\x85", id="U+0085-next-line"),
    pytest.param(" ", id="U+2028-line-separator"),
    pytest.param(" ", id="U+2029-paragraph-separator"),
)


@pytest.mark.parametrize("separator", SPLITLINES_ONLY)
def test_a_raw_separator_does_not_end_a_line(separator: str) -> None:
    """The defect, one character at a time, checked against `ast` itself.

    `splitlines()` breaks on the character and the tokenizer does not, so the
    two numberings disagree by one for everything after it. The `ast` line
    number of the marker statement is the ground truth here - this asserts the
    helper reproduces it, and asserts `splitlines()` does not, so a future
    change that quietly reintroduces `splitlines()` cannot leave this green.
    """
    source = 'x = "a' + separator + 'b"\ny = 1  # marker\n'

    marker_by_ast = ast.parse(source).body[1].lineno
    marker_by_helper = next(
        i for i, line in enumerate(source_lines(source), start=1) if "# marker" in line
    )
    marker_by_splitlines = next(
        i for i, line in enumerate(source.splitlines(), start=1) if "# marker" in line
    )

    assert marker_by_helper == marker_by_ast
    assert marker_by_splitlines != marker_by_ast, (
        "str.splitlines() agreed with ast for this character, so it is not one "
        "of the separators this helper exists to handle - the parametrize list "
        "no longer describes the defect"
    )


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_the_tokenizer_line_endings_do_end_a_line(ending: str) -> None:
    """The other half: the three real endings must still split.

    Without this, a helper that split on nothing at all would pass every test
    above - every marker would be on line 1 and `ast` would be asked about a
    one-line file. This is the case that makes the suite able to fail in the
    other direction.
    """
    source = ending.join(["first", "second", "third"])
    assert source_lines(source) == ["first", "second", "third"]


def test_a_trailing_newline_produces_no_phantom_final_line() -> None:
    """Shape-compatible with `splitlines()`, which is what callers replaced.

    Splitting on the pattern alone yields a trailing empty element that
    `splitlines()` does not produce. It shifts nothing - an empty line matches
    no waiver - but it would make `len(source_lines(s))` disagree with every
    reader's idea of how many lines a file has.
    """
    assert source_lines("a\nb\n") == ["a", "b"]
    assert source_lines("a\nb") == ["a", "b"]
    assert source_lines("a\nb\n") == "a\nb\n".splitlines()


def test_interior_blank_lines_are_preserved() -> None:
    """Blank lines are real lines with real numbers - only the TRAILING one goes.

    The trailing-empty rule above is a single, deliberate pop. A `strip`-style
    fix that dropped every empty element would renumber everything after the
    first blank line, which is the same class of bug in the other direction.
    """
    assert source_lines("a\n\n\nb\n") == ["a", "", "", "b"]
    assert source_lines("a\n\n\nb\n") == "a\n\n\nb\n".splitlines()


def test_empty_source_is_no_lines() -> None:
    assert source_lines("") == []
    assert source_lines("") == "".splitlines()


def test_agrees_with_ast_across_a_real_source_file() -> None:
    """One end-to-end check against a file nobody wrote for this test.

    The synthetic cases above each hold one character constant. This asserts
    the helper agrees with `ast` about EVERY statement in a real module, which
    is the property the gates actually depend on.
    """
    target = REPO_ROOT / "lib" / "sourcelines.py"
    source = target.read_text(encoding="utf-8")
    lines = source_lines(source)

    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.stmt) or not hasattr(node, "lineno"):
            continue
        assert 1 <= node.lineno <= len(lines), (
            f"ast reports line {node.lineno} but the helper produced "
            f"{len(lines)} line(s) - the two disagree about this file's extent"
        )
