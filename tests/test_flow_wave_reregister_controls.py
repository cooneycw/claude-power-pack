"""Each refusal control discriminates through its own guard, not its neighbour."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "flow-wave-registry.sh"
CONTROL = ROOT / "controls" / "flow-wave-reregister-work"
pytestmark = pytest.mark.skipif(
    any(shutil.which(x) is None for x in ("bash", "jq", "flock")),
    reason="control drives the real bash registry with jq and flock",
)


@pytest.mark.parametrize("own,other,needle", [
    ("bad-missing-lane", "bad-missing-observation", '&& [ "$A_FILES_SET" -eq 0 ]'),
    ("bad-missing-observation", "bad-missing-lane",
     '&& [ "$A_OBS" -ne 1 ] && [ "$A_CLEAR_PR" -ne 1 ]'),
])
def test_each_work_refusal_flips_when_only_its_guard_is_removed(tmp_path, own, other, needle):
    source = GATE.read_text()
    assert source.count(needle) == 1, "mutation must remove exactly one guard"
    mutant = tmp_path / "registry.sh"
    mutant.write_text(source.replace(needle, "&& false"))

    def run(case, gate):
        return subprocess.run([sys.executable, str(CONTROL / "run-case.py"),
                               str(CONTROL / "cases" / case), str(gate)],
                              capture_output=True, text=True, timeout=40)

    assert run(own, GATE).returncode == 1
    changed = run(own, mutant)
    assert changed.returncode == 0, changed.stdout + changed.stderr
    assert run(other, mutant).returncode == 1
