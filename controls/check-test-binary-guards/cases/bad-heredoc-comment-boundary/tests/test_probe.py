"""KNOWN-BAD input (issue #1407, counter-model finding 1), split from the

original combined fixture per counter-model finding 4: a `;#` comment -
opened right after a `;` operator, not whitespace - carrying a heredoc-
opener-SHAPED token, in ISOLATION from any quoted-string shape, followed by
a REAL jq use. Before the word-boundary fix, `_heredoc_opener_is_live` only
recognized whitespace or start-of-line as preceding a real comment opener,
so `;#` was missed: the `#` reads as adjacent to non-whitespace (`;`), the
fake opener is treated as live, and `_mask_heredocs` masks everything after
it to EOF - including the real jq use - so the gate reports NO unguarded
test. Isolating this shape means this case is load-bearing only for the
WORD_BOUNDARY_CHARS half of the fix: reverting only that half must make this
case go undetected while the quoted-string and if-bang-preflight cases still
detect. There is no `shutil.which` guard here on purpose; the gate must
report this.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "needs-jq-after-semicolon-comment.sh"


def test_helper_runs() -> None:
    subprocess.run([str(HELPER)], check=True)
