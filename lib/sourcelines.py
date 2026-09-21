"""Split Python source into lines the way CPython's tokenizer does (issue #1110).

WHY THIS EXISTS, AND WHY IT IS NOT `str.splitlines()`. A gate that finds its
WAIVER COMMENTS by counting lines and its SITES with `ast` is using two
coordinate systems, and they disagree. `str.splitlines()` ends a line on eight
characters the tokenizer does not treat as line ends at all::

    \\v (U+000B)  \\f (U+000C)  U+001C  U+001D  U+001E
    U+0085       U+2028       U+2029

CPython's tokenizer ends a line on ``\\n``, ``\\r\\n`` or ``\\r`` and nothing
else. So a single one of those characters appearing raw anywhere in a file -
inside a string literal is the ordinary way - shifts every `splitlines()` line
number after it while the `ast` line numbers stay correct.

Both directions then fail, and the second is the one that motivated this:

* a correct waiver stops matching its site, and the build goes red on a file
  that was fine. Noisy, but it announces itself.
* the displaced number lands on a DIFFERENT site that nobody waived, silently
  exempting it. The gate then reports a green it did not earn, and nothing
  about that green looks wrong.

**Do not reach for `str.splitlines()` inside this module.** Its extra
separators are the entire defect this exists to remove; a "simplification" back
to it reintroduces the bug in the one place every caller trusts.

THIS MODULE HAS NO NEGATIVE CONTROL OF ITS OWN, DELIBERATELY. ADR 0008 bounds
the committed-case requirement to an instrument whose VERDICT is consumed by a
decision that will not independently re-derive it. This returns DATA, not a
verdict: every caller re-derives its result on every run, and the committed
cases of the gates that use it -
``controls/check-negative-fixture-preconditions/cases/{good-separator-shift,
bad-shifted-exemption}`` and the matching pair under
``controls/check-test-binary-guards`` - go red the moment this function stops
agreeing with `ast`. Those ARE this helper's negative control. Adding a
separate one here would be decorative: it would test this function against its
own definition while the real question - do the gates' two coordinate systems
still agree - is already asked, committed, and failing-closed elsewhere.
"""

from __future__ import annotations

import re

#: The tokenizer's line endings, longest-first so ``\r\n`` is one break and not
#: two. Anything not matched here is ordinary text, however much
#: ``str.splitlines()`` would like to break on it.
_LINE_END_RE = re.compile(r"\r\n|\r|\n")


def source_lines(source: str) -> list[str]:
    """``source`` split into lines in the coordinate system `ast` reports.

    A drop-in replacement for ``source.splitlines()`` wherever the resulting
    index is compared against an `ast` node's ``lineno``. Enumerate it from 1,
    exactly as before::

        allow_lines = {
            i for i, line in enumerate(source_lines(source), start=1)
            if ALLOW_RE.search(line)
        }

    A TRAILING NEWLINE PRODUCES NO PHANTOM FINAL LINE. Splitting ``"a\\n"`` on
    the pattern alone yields ``["a", ""]``, one element longer than
    ``splitlines()`` gives, and that extra element would shift nothing but
    would make ``len(source_lines(s))`` disagree with every reader's idea of
    how many lines a file has. The single trailing empty element is dropped so
    this matches ``splitlines()`` in shape and differs from it only where it
    must - on which characters end a line. Interior blank lines are untouched,
    because they are real lines with real numbers.
    """
    lines = _LINE_END_RE.split(source)
    if lines and lines[-1] == "":
        lines.pop()
    return lines
