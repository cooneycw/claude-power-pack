"""A control's subject verdict must not survive a failed fixture cleanup (#1983)."""

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from tests.test_negative_controls import _load_harness_module

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="real control needs git")

EXECUTE = """
import errno
import runpy
import sys
import tempfile
from pathlib import Path

if sys.argv[3] == "crash":
    class CleanupCrash(tempfile.TemporaryDirectory):
        def cleanup(self):
            owned = Path(self.name).name.startswith(
                ("cpp-real-adapter-control-", "host-update-control-"))
            super().cleanup()
            if owned:
                print("PLANTED_CLEANUP_CRASH", file=sys.stderr, flush=True)
                raise OSError(errno.ENOTEMPTY, "planted cleanup failure", self.name)
    tempfile.TemporaryDirectory = CleanupCrash
runpy.run_path(str(Path(sys.argv[2]).parents[1] / "run-case.py"), run_name="__main__")
"""


@pytest.mark.parametrize("control", ["antigravity-skill-install-fidelity", "host-update-core"])
@pytest.mark.parametrize(
    "kind,case,expected_exit,expected_observation",
    [
        ("GOOD", "good-current", 0, "GOOD"),
        ("BAD", "bad-stale", 1, "BAD"),
        ("UNKNOWN", "unknown-lock", 4, "UNKNOWN"),
        ("anchor", "bad-stale", 0, "GOOD"),
    ],
)
def test_cleanup_failure_suppresses_the_real_subject_verdict(
    tmp_path, monkeypatch, control, kind, case, expected_exit, expected_observation,
):
    directory = ROOT / "controls" / control
    spec = json.loads((directory / "control.json").read_text())
    gate = (directory / spec["anchors"][0]["path"] if kind == "anchor"
            else ROOT / spec["gate"])
    harness = _load_harness_module()
    patterns = {name: re.compile(spec[name], re.MULTILINE) for name in
                ("detect_signal", "unavailable_signal", "unknown_signal", "good_signal")}
    temporary = tmp_path / "owned-temporary"
    temporary.mkdir()
    assert list(temporary.iterdir()) == []
    monkeypatch.setenv("TMPDIR", str(temporary))

    def invoke(mode):
        code, output, diagnostic = harness._invoke(
            [sys.executable, "-c", EXECUTE, "{gate}", "{case}", mode],
            gate, directory / "cases" / case, ROOT,
        )
        observed = harness._observe(
            code, spec["good_exit"], output, patterns["detect_signal"],
            patterns["unavailable_signal"], patterns["unknown_signal"], patterns["good_signal"],
        )
        return code, output, diagnostic, observed

    normal_code, normal_output, normal_diagnostic, normal_observed = invoke("normal")
    assert normal_code == expected_exit, normal_output
    assert normal_observed == expected_observation, normal_output
    assert "PLANTED_CLEANUP_CRASH" not in normal_output
    assert list(temporary.iterdir()) == [], normal_diagnostic

    code, output, diagnostic, observed = invoke("crash")
    assert code == 1 and "PLANTED_CLEANUP_CRASH" in output, output
    assert "planted cleanup failure" in diagnostic, output
    assert list(temporary.iterdir()) == [], diagnostic
    assert observed == harness.UNSIGNALLED, output
    assert not any(patterns[name].search(output) for name in
                   ("detect_signal", "unknown_signal", "good_signal")), output
