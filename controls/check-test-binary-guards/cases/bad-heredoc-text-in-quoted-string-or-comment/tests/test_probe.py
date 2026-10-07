"""KNOWN-BAD input (issue #1407): a usage-string echo and a comment, each

containing a heredoc-opener-shaped token, followed by a REAL jq use. Before
the fix, `_mask_heredocs` treats the first fake opener as a real one and
masks everything after it to EOF - including the real jq use - so the gate
reports NO unguarded test. There is no `shutil.which` guard here on purpose;
the gate must report this.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "needs-jq-after-fake-heredoc.sh"


def test_helper_runs() -> None:
    subprocess.run([str(HELPER)], check=True)
