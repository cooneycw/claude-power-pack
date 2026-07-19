"""Tests for scripts/tool-risk-drift.py and its wiring (issue #576).

The invariant: CPP classifies command risk in two places that MUST agree on what
is dangerous - the canonical ``scripts/classify-tool-risk.py`` (behind
``/security:permissions``) and the copy vendored inline into
``scripts/hook-permission-census.sh`` (kept self-contained so the census hook
stays fail-open). If ``DESTRUCTIVE_TOKENS`` or ``CODE_EXEC`` drift apart, a
command one classifier calls dangerous can be emitted as an allow-rule candidate
by the other.

The guard for that shipped with #495, its header documenting ``--strict`` "(for
CI)" - and was then wired into nothing at all: no pipeline step, no Makefile
target, no test. #576 wires it. Half of this file therefore tests the WIRING
rather than the script: a guard that runs nowhere protects nothing, and the
dormancy is exactly what recurred here (the same shape #591 fixed for the eli5
vendor link).

Everything here is OFFLINE and stdlib-only on purpose - no network, no git, no
external binaries. The Woodpecker ``validate`` container (uv:python3.11-slim)
ships none of them, and an unguarded shell-out turns CI red even though it passes
locally (the recurring #451/#489 trap).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tool-risk-drift.py"
CANONICAL = ROOT / "scripts" / "classify-tool-risk.py"
VENDORED = ROOT / "scripts" / "hook-permission-census.sh"
WOODPECKER = ROOT / ".woodpecker.yml"
MAKEFILE = ROOT / "Makefile"

GUARDED_SETS = ("DESTRUCTIVE_TOKENS", "CODE_EXEC")


def _load_module():
    """Import the hyphenated script by path (not importable as a module name)."""
    spec = importlib.util.spec_from_file_location("tool_risk_drift", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["tool_risk_drift"] = module
    spec.loader.exec_module(module)
    return module


trd = _load_module()


def _run(*args, cwd=None):
    """Run the guard as a subprocess; returns CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
    )


# --- the script itself --------------------------------------------------------


def test_script_exists_and_executable():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), "tool-risk-drift.py must be executable"


def test_both_classifiers_are_present():
    """The guard is fail-open on a missing source, so absence must be caught here."""
    assert CANONICAL.is_file(), f"missing {CANONICAL} - the canonical taxonomy"
    assert VENDORED.is_file(), f"missing {VENDORED} - the vendored census copy"


def test_guarded_sets_parse_from_both_sources():
    canon = CANONICAL.read_text(encoding="utf-8")
    vendor = VENDORED.read_text(encoding="utf-8")
    for name in GUARDED_SETS:
        a = trd.extract_set(canon, name)
        b = trd.extract_set(vendor, name)
        assert a, f"{name} did not parse out of {CANONICAL.name}"
        assert b, f"{name} did not parse out of {VENDORED.name}"


def test_repo_taxonomy_is_in_sync():
    """The live invariant: the two classifiers agree today."""
    canon = CANONICAL.read_text(encoding="utf-8")
    vendor = VENDORED.read_text(encoding="utf-8")
    for name in GUARDED_SETS:
        assert trd.extract_set(canon, name) == trd.extract_set(vendor, name), (
            f"{name} has drifted between {CANONICAL.name} and {VENDORED.name}; "
            f"reconcile against the canonical copy ({CANONICAL.name})."
        )


def test_strict_exits_zero_when_in_sync():
    proc = _run("--strict")
    assert proc.returncode == 0, f"--strict failed on a clean tree:\n{proc.stdout}{proc.stderr}"
    assert "in sync" in proc.stdout


def test_strict_exits_one_on_injected_drift(tmp_path):
    """A token added to one classifier and not the other must fail --strict."""
    fake = tmp_path / "scripts"
    fake.mkdir()
    (fake / "classify-tool-risk.py").write_text(
        'DESTRUCTIVE_TOKENS = {"rm", "dd", "mkfs"}\nCODE_EXEC = {"python"}\n',
        encoding="utf-8",
    )
    (fake / "hook-permission-census.sh").write_text(
        'DESTRUCTIVE_TOKENS = {"rm", "dd"}\nCODE_EXEC = {"python"}\n',
        encoding="utf-8",
    )
    proc = _run("--strict", "--root", str(tmp_path))
    assert proc.returncode == 1, f"--strict did not fail on drift:\n{proc.stdout}"
    assert "DRIFT in DESTRUCTIVE_TOKENS" in proc.stdout
    assert "mkfs" in proc.stdout


def test_default_mode_is_advisory_on_drift(tmp_path):
    """Without --strict the guard reports and exits 0 (fail-open by design)."""
    fake = tmp_path / "scripts"
    fake.mkdir()
    (fake / "classify-tool-risk.py").write_text(
        'DESTRUCTIVE_TOKENS = {"rm"}\nCODE_EXEC = {"python", "node"}\n', encoding="utf-8"
    )
    (fake / "hook-permission-census.sh").write_text(
        'DESTRUCTIVE_TOKENS = {"rm"}\nCODE_EXEC = {"python"}\n', encoding="utf-8"
    )
    proc = _run("--root", str(tmp_path))
    assert proc.returncode == 0, "default mode must stay advisory"
    assert "DRIFT in CODE_EXEC" in proc.stdout


def test_missing_source_is_skipped_not_fatal(tmp_path):
    """Fail-open on an unreadable source, even under --strict."""
    proc = _run("--strict", "--root", str(tmp_path))
    assert proc.returncode == 0
    assert "skipping" in proc.stdout


# --- the wiring (this is what #576 is actually about) -------------------------


def test_woodpecker_runs_the_guard_in_strict_mode():
    """A guard with no CI step is dormant - the #576 defect, re-armed as a test."""
    text = WOODPECKER.read_text(encoding="utf-8")
    assert "tool-risk-drift:" in text, (
        ".woodpecker.yml must define a tool-risk-drift step - without it the "
        "shared-taxonomy guard runs nowhere (issue #576)."
    )
    assert "scripts/tool-risk-drift.py --strict" in text, (
        "the CI step must pass --strict; bare invocation exits 0 on drift and "
        "would make the step decorative."
    )
    assert "failure: ignore" not in text.split("tool-risk-drift:")[1].split("dockerfile-lint:")[0], (
        "the taxonomy gate is safety-critical and must be a hard gate, unlike "
        "the advisory eli5-upstream-drift step."
    )


def test_makefile_exposes_the_guard():
    text = MAKEFILE.read_text(encoding="utf-8")
    assert "tool-risk-check:" in text, "Makefile must expose the CI shape (make tool-risk-check)"
    assert "tool-risk-drift:" in text, "Makefile must expose the advisory shape"
    assert "tool-risk-check tool-risk-drift" in text, "both targets must be .PHONY"
