"""KNOWN-GOOD input: the same direct invocation, correctly guarded.

Identical to the bad case except for the `shutil.which` skip guard, in the shape
the gate's own remediation text prescribes. The gate must report this clean.

This half is not decoration: a gate wedged at "fail" passes the known-bad check
on its own, and only the good case can tell that apart from a gate that works.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "needs-jq.sh"

requires_jq = pytest.mark.skipif(
    shutil.which("jq") is None, reason="jq absent in the CI validate image"
)


@requires_jq
def test_helper_runs() -> None:
    subprocess.run([str(HELPER)], check=True)
