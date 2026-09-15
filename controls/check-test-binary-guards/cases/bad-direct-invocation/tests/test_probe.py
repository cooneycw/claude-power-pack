"""KNOWN-BAD input: a test that runs a repo script DIRECTLY, unguarded (issue #906).

`subprocess.run([str(HELPER)])` runs the helper on its shebang. That is the
natural spelling in this repository, and before 1fa3560 it entered no hop at
all, so the helper was never scanned and its hard `jq` dependency was invisible.

There is no `shutil.which` guard here on purpose. The gate must report this.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "needs-jq.sh"


def test_helper_runs() -> None:
    subprocess.run([str(HELPER)], check=True)
