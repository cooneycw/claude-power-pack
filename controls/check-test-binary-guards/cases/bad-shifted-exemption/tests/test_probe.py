"""KNOWN-BAD: a shifted waiver must not silently exempt an unguarded test.

The waiver sits at module level and exempts no test as written. Six raw
separators move its computed line number onto the `def` line below, which the
unfixed gate reads as an exemption - reporting `ok ... 1 exempted` for a test
that carries no guard and no waiver.

The fabricated "1 exempted" is the tell: the count channel and the findings
channel are wrong together, from one shifted number (issue #1110).
"""
import subprocess
from pathlib import Path

SEPARATORS = ["  "]

# binary-guard: allow this waiver belongs to no test at all

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "needs-jq.sh"


def test_helper_runs() -> None:
    subprocess.run([str(HELPER)], check=True)
