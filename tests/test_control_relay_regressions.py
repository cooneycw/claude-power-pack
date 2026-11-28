"""Real subject and anchor output must wait for control fixture cleanup (#1984)."""

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from tests.test_negative_controls import _load_harness_module

ROOT = Path(__file__).resolve().parents[1]

BOOTSTRAP = """
import errno
import inspect
import runpy
import sys
import tempfile
from pathlib import Path
script = Path(sys.argv[1]).resolve()
mode = sys.argv[2]
arguments = sys.argv[3:]
original = tempfile.TemporaryDirectory
class CleanupCrash(original):
    def __enter__(self):
        self.control_owned = Path(inspect.currentframe().f_back.f_code.co_filename) == script
        return super().__enter__()
    def cleanup(self):
        super().cleanup()
        if mode == "crash" and getattr(self, "control_owned", False):
            print("PLANTED_CONTROL_CLEANUP_CRASH", file=sys.stderr, flush=True)
            raise OSError(errno.ENOTEMPTY, "planted control cleanup failure", self.name)
tempfile.TemporaryDirectory = CleanupCrash
sys.argv = [str(script), *arguments]
runpy.run_path(str(script), run_name="__main__")
"""

# Exact registered inputs and observed normal exits, frozen before the fix.
# UNKNOWN uses the registered refusal, never a missing host prerequisite.
CASES = [('antigravity-skill-build', 'bad-changed-output', 'gate', 1, 'BAD'),
 ('antigravity-skill-build', 'unknown-source', 'gate', 4, 'UNKNOWN'),
 ('ci-shape-check', 'bootstrap-code', 'gate', 1, 'BAD'),
 ('ci-shape-check', 'backend', 'gate', 2, 'UNKNOWN'),
 ('ci-shape-check', 'mode', 'gate', 1, 'BAD'),
 ('ci-shape-check', 'unavailable', 'gate', 2, 'UNKNOWN'),
 ('claude-host-links', 'bad-outside', 'gate', 1, 'BAD'),
 ('claude-host-links', 'unknown-lock', 'gate', 4, 'UNKNOWN'),
 ('cpp-host-install-receipt', 'bad-deferred', 'gate', 1, 'BAD'),
 ('cpp-host-link-preservation', 'bad-regular', 'gate', 1, 'BAD'),
 ('cpp-install-receipt', 'bad-nonzero', 'gate', 1, 'BAD'),
 ('cpp-update-host-refresh', 'bad-unwritable', 'gate', 2, 'BAD'),
 ('cpp-update-host-refresh', 'unknown-unavailable', 'gate', 2, 'UNKNOWN'),
 ('driver-parity', 'bad-assignment-only', 'gate', 1, 'BAD'),
 ('driver-parity', 'bad-env-command', 'gate', 2, 'UNKNOWN'),
 ('pi-skill-build', 'missing', 'gate', 1, 'BAD'),
 ('pi-skill-build', 'unknown', 'gate', 4, 'UNKNOWN'),
 ('pi-skill-install', 'auth-helper-rejected', 'gate', 1, 'BAD'),
 ('pi-skill-install', 'ignored-source-member-refused', 'gate', 4, 'UNKNOWN'),
 ('antigravity-skill-build', 'good-fresh', 'gate', 0, 'GOOD'),
 ('antigravity-skill-build', 'bad-changed-output', 'anchor', 0, 'GOOD'),
 ('ci-shape-check', 'good', 'gate', 0, 'GOOD'),
 ('ci-shape-check', 'bootstrap-code', 'anchor', 0, 'GOOD'),
 ('claude-host-links', 'good-confined', 'gate', 0, 'GOOD'),
 ('claude-host-links', 'bad-outside', 'anchor', 0, 'GOOD'),
 ('cpp-host-install-receipt', 'good-written', 'gate', 0, 'GOOD'),
 ('cpp-host-install-receipt', 'bad-deferred', 'anchor', 0, 'GOOD'),
 ('cpp-host-link-preservation', 'good-links', 'gate', 0, 'GOOD'),
 ('cpp-host-link-preservation', 'bad-regular', 'anchor', 0, 'GOOD'),
 ('cpp-install-receipt', 'good-complete', 'gate', 0, 'GOOD'),
 ('cpp-install-receipt', 'bad-nonzero', 'anchor', 0, 'GOOD'),
 ('cpp-update-host-refresh', 'good-stale-refresh', 'gate', 0, 'GOOD'),
 ('cpp-update-host-refresh', 'bad-unwritable', 'anchor', 0, 'GOOD'),
 ('driver-parity', 'good-citation-line-shift', 'gate', 0, 'GOOD'),
 ('driver-parity', 'bad-assignment-only', 'anchor', 0, 'GOOD'),
 ('pi-skill-build', 'good', 'gate', 0, 'GOOD'),
 ('pi-skill-build', 'missing', 'anchor', 0, 'GOOD'),
 ('pi-skill-install', 'adopt-with-backup', 'gate', 0, 'GOOD'),
 ('pi-skill-install', 'auth-helper-rejected', 'anchor', 0, 'GOOD')]

CASES += [('delegated-codex-plan-lanes', 'good-every-lane', 'gate', 0, 'GOOD'),
 ('delegated-codex-plan-lanes', 'bad-omitted-lane', 'gate', 1, 'BAD'),
 ('delegated-qwen-plan-lanes', 'good-every-lane', 'gate', 0, 'GOOD'),
 ('delegated-qwen-plan-lanes', 'bad-omitted-lane', 'gate', 1, 'BAD'),
 ('delegated-gemma-plan-lanes', 'good-every-lane', 'gate', 0, 'GOOD'),
 ('delegated-gemma-plan-lanes', 'bad-omitted-lane', 'gate', 1, 'BAD'),
 ('execution-evidence-verify', 'good-clean-completed-current', 'gate', 0, 'GOOD'),
 ('execution-evidence-verify', 'bad-stale-same-file-edited-again', 'gate', 3, 'BAD'),
 ('execution-evidence-verify', 'unknown-check-missing-population', 'gate', 4, 'UNKNOWN'),
 ('flow-plan-provenance', 'valid', 'gate', 0, 'GOOD'),
 ('flow-plan-provenance', 'invalid', 'gate', 1, 'BAD'),
 ('flow-plan-provenance', 'unknown-contract', 'gate', 4, 'UNKNOWN'),
 ('flow-plan-record-lanes', 'good-every-lane-answered', 'gate', 0, 'GOOD'),
 ('flow-plan-record-lanes', 'bad-no-table', 'gate', 1, 'BAD'),
 ('flow-cpp-runtime', 'good-installed', 'gate', 0, 'GOOD'),
 ('flow-cpp-runtime', 'bad-missing-runtime-no-download', 'gate', 1, 'BAD'),
 ('pi-skill-install', 'unreadable-install', 'gate', 4, 'UNKNOWN')]

@pytest.mark.parametrize("control,case,subject,expected_exit,expected", CASES)
def test_real_control_holds_verdict_until_cleanup(
    monkeypatch, control, case, subject, expected_exit, expected,
):
    required = {"git", "bash", "make", "python3"}
    absent = sorted(name for name in required if shutil.which(name) is None)
    if absent:
        pytest.skip("real control needs " + ", ".join(absent))
    directory = ROOT / "controls" / control
    spec = json.loads((directory / "control.json").read_text())
    gate_ref = spec["gate"]
    gate = ROOT / (gate_ref["file"] if isinstance(gate_ref, dict) else gate_ref)
    if subject == "anchor":
        gate = directory / spec["anchors"][0]["path"]
    runner_ref = next((p for p in spec["invocation"]
                       if p.endswith(("run-case.py", "run_case.py"))), None)
    runner = ROOT / runner_ref if runner_ref else next(
        p for p in directory.glob("*.py") if p.name in {"run-case.py", "run_case.py"})
    harness = _load_harness_module()
    patterns = {key: re.compile(spec[key], re.MULTILINE) if spec.get(key) else None
                for key in ("detect_signal", "unknown_signal", "unavailable_signal", "good_signal")}
    # The unwritable fixture may demote UID. Its executable shim must have no
    # private pytest ancestor, and delegates every non-target command unchanged.
    with tempfile.TemporaryDirectory(prefix="relay-tools-") as owned:
        tools = Path(owned)
        tools.chmod(0o755)
        bootstrap = tools / "bootstrap.py"
        bootstrap.write_text(BOOTSTRAP)
        bootstrap.chmod(0o644)
        shim = tools / "python3"
        shim.write_text(
            f"#!{sys.executable}\nimport os,sys\nfrom pathlib import Path\n"
            f"target = Path({str(runner)!r}).resolve()\n"
            "if len(sys.argv)>1 and Path(sys.argv[1]).resolve()==target:\n"
            f" args=[{str(bootstrap)!r},str(target),os.environ['CPP_TEST_RELAY_MODE'],*sys.argv[2:]]\n"
            "else:\n args=sys.argv[1:]\n"
            f"os.execv({sys.executable!r},[{sys.executable!r},*args])\n"
        )
        shim.chmod(0o755)
        monkeypatch.setenv("PATH", str(tools) + os.pathsep + os.environ["PATH"])
        assert shutil.which("python3") == str(shim)

        def invoke(mode):
            original = spec["invocation"]
            if isinstance(gate_ref, dict):
                invocation = [p.replace("{target}", gate_ref["target"]) for p in original]
            else:
                if "-c" in original:
                    arguments = original[original.index("-c") + 2:]
                else:
                    at = next(i for i, p in enumerate(original)
                              if p.endswith(("run-case.py", "run_case.py")))
                    arguments = original[at + 1:]
                invocation = [sys.executable, str(bootstrap), str(runner), mode, *arguments]
            monkeypatch.setenv("CPP_TEST_RELAY_MODE", mode)
            code, output, diagnostic = harness._invoke(invocation, gate, directory / "cases" / case, ROOT)
            observed = harness._observe(code, spec.get("good_exit", 0), output,
                                        patterns["detect_signal"], patterns["unavailable_signal"],
                                        patterns["unknown_signal"], patterns["good_signal"])
            return code, output, diagnostic, observed

        code, output, _, observed = invoke("normal")
        assert code == expected_exit and observed == expected, output
        assert "PLANTED_CONTROL_CLEANUP_CRASH" not in output
        code, output, diagnostic, observed = invoke("crash")
        assert code not in (None, 0) and "PLANTED_CONTROL_CLEANUP_CRASH" in output, (output, diagnostic)
        assert observed == harness.UNSIGNALLED, output
        assert not any(p.search(output) for p in patterns.values() if p is not None), output
