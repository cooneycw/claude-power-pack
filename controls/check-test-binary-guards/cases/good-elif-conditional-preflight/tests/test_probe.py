"""KNOWN-GOOD input (issue #1407, counter-model finding 2): a `command -v
curl` preflight on an `elif` branch, correctly guarded.

Before the fix, `CONDITION_OPENER_RE` matched a column-zero `elif` the same
way it matched `if`/`while`/`until`, so this preflight was wrongly read as a
genuinely unconditional entry point and curl was promoted to `hard_required`
- which would make the gate demand a `shutil.which` guard even though curl is
provably optional here (the first branch can make the whole elif chain never
run). The fix excludes `elif` from `CONDITION_OPENER_RE`, so the preflight is
`scoped` as before, and the already-fail-soft use below keeps this case clean
with no guard at all. The gate must report this clean either way.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "needs-curl-via-elif-bang.sh"


def test_helper_runs() -> None:
    subprocess.run([str(HELPER)], check=True)
