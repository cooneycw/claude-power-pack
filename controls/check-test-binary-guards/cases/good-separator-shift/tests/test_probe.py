"""KNOWN-GOOD: a correctly waived direct invocation after raw separator characters.

The waiver is appended to the `def` line, which is the escape the gate's own
remediation text prescribes. This case must report clean.

Unlike the negative-fixture gate, the match here is EXACT - `func.lineno in
allow_lines` - so there is no +/-1 window to clear and even a one-line shift
would surface the defect. The shift is three anyway, to keep every #1110 fixture
under one rule.
"""
import subprocess
from pathlib import Path

SEPARATORS = ["  "]

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "needs-jq.sh"


def test_helper_runs() -> None:  # binary-guard: allow the fixture pins the helper
    subprocess.run([str(HELPER)], check=True)
