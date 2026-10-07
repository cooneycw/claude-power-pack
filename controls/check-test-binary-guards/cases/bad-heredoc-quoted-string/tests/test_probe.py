"""KNOWN-BAD input (issue #1407), split from the original combined fixture

per counter-model finding 4: a double-quoted usage string carrying a
heredoc-opener-SHAPED token, in ISOLATION from any comment-opener shape,
followed by a REAL jq use. Before the fix, `_mask_heredocs` treats the fake
opener as real and masks everything after it to EOF - including the real jq
use - so the gate reports NO unguarded test. Isolating this shape means this
case is load-bearing only for the quote-tracking half of
`_heredoc_opener_is_live`: reverting only that half must make this case go
undetected while the comment-boundary and if-bang-preflight cases still
detect. There is no `shutil.which` guard here on purpose; the gate must
report this.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "needs-jq-after-quoted-heredoc-text.sh"


def test_helper_runs() -> None:
    subprocess.run([str(HELPER)], check=True)
