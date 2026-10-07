"""KNOWN-BAD input (issue #1407): a TOP-LEVEL `if ! command -v curl; then

... exit; fi` preflight, followed by a stderr-silenced curl use. Before the
fix, `_preflight_declarations` reads the "if !" text preceding the match on
the same line as evidence of NESTING, misclassifying this top-level,
unconditionally-exiting preflight as `scoped` - and the later stderr-
silenced use independently reads as fail-soft, so the gate reports NO
unguarded test either way. There is no `shutil.which` guard here on purpose;
the gate must report this.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "needs-curl-via-if-bang.sh"


def test_helper_runs() -> None:
    subprocess.run([str(HELPER)], check=True)
