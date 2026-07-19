"""Tests for scripts/branch-protection.sh - declared branch-protection posture (#577).

Contract:
- ``check`` (the default) normalizes live protection and the declared posture to
  one shape and compares them: exit 0 in sync, exit 1 on drift with both sides
  printed.
- The two representations differ on the wire - GitHub returns nested
  ``{"enabled": bool}`` objects and may express required contexts either as
  ``contexts`` or as ``checks[].context`` - so normalization, not raw equality,
  is what the check tests.
- An UNPROTECTED branch (the API 404s) is reported as drift, never as a crash.
- ``--apply`` PUTs the declared ``.protection`` payload verbatim.
- The shipped posture is the one ADR 0004 records.

``gh`` is stubbed via the BRANCH_PROTECTION_GH env hook; the stub logs its argv
and echoes a scripted protection document.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "branch-protection.sh"
POSTURE = ROOT / ".claude" / "branch-protection.json"

requires_jq = pytest.mark.skipif(
    shutil.which("jq") is None, reason="jq not installed (absent in the CI validate image)"
)

# The live shape GitHub returns for the posture ADR 0004 declares.
LIVE_IN_SYNC = {
    "required_status_checks": {"strict": True, "contexts": ["ci/woodpecker/pr/woodpecker"]},
    "required_pull_request_reviews": {
        "dismiss_stale_reviews": False,
        "require_code_owner_reviews": False,
        "required_approving_review_count": 0,
    },
    "enforce_admins": {"enabled": False},
    "allow_force_pushes": {"enabled": False},
    "allow_deletions": {"enabled": False},
}

# The pre-#577 posture: PRs forced, but no required check at all.
LIVE_RELAXED = json.loads(json.dumps(LIVE_IN_SYNC))
LIVE_RELAXED["required_status_checks"] = {"strict": True, "contexts": [], "checks": []}


def _make_stub(tmp_path: Path, live: dict | None, *, api_exit: int = 0) -> dict:
    """Fake gh that logs argv and echoes ``live`` for a protection GET.

    ``live=None`` models an unprotected branch: the API 404s with no output.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    call_log = tmp_path / "calls.log"
    body = tmp_path / "live.json"
    body.write_text(json.dumps(live) if live is not None else "")

    stub = bin_dir / "gh"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "gh $*" >> "{call_log}"\n'
        '# A PUT consumes stdin and prints nothing; a GET echoes the scripted doc.\n'
        'if [[ "$*" == *"--method PUT"* ]]; then cat >/dev/null; exit 0; fi\n'
        f'cat "{body}"\n'
        f"exit {api_exit}\n"
    )
    stub.chmod(0o755)
    return {"BRANCH_PROTECTION_GH": str(stub), "_call_log": call_log}


def _run(tmp_path: Path, stubs: dict, *args: str, config: Path | None = None):
    env = os.environ.copy()
    env["BRANCH_PROTECTION_GH"] = stubs["BRANCH_PROTECTION_GH"]
    cfg = config or POSTURE
    return subprocess.run(
        ["bash", str(SCRIPT), *args, "--config", str(cfg)],
        check=False,
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def _calls(stubs: dict) -> list[str]:
    log = stubs["_call_log"]
    return log.read_text().splitlines() if log.exists() else []


def test_script_is_executable():
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK), "branch-protection.sh must be executable"


def test_posture_file_matches_adr_0004():
    # The shipped posture IS the decision record; a silent edit here would make
    # ADR 0004 a lie. Pin the three settings the ADR argues about.
    doc = json.loads(POSTURE.read_text())
    assert doc["branch"] == "main"
    p = doc["protection"]
    assert p["required_status_checks"]["contexts"] == ["ci/woodpecker/pr/woodpecker"]
    assert p["required_status_checks"]["strict"] is True
    assert p["required_pull_request_reviews"]["required_approving_review_count"] == 0
    assert p["enforce_admins"] is False, "ADR 0004 keeps the owner break-glass"


def test_posture_file_is_tracked():
    # .gitignore blankets *.json; without an explicit negation the posture file is
    # silently untracked and the check compares against nothing (issue #430 trap).
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(POSTURE.relative_to(ROOT))],
        cwd=ROOT,
        check=False,
    )
    assert result.returncode != 0, ".claude/branch-protection.json must not be gitignored"


@requires_jq
def test_check_in_sync_exits_zero(tmp_path: Path):
    stubs = _make_stub(tmp_path, LIVE_IN_SYNC)
    result = _run(tmp_path, stubs)
    assert result.returncode == 0, result.stderr
    assert "in-sync" in result.stdout


@requires_jq
def test_check_reports_drift_on_relaxed_protection(tmp_path: Path):
    # The pre-#577 state: no required contexts. Must be drift, with both sides shown.
    stubs = _make_stub(tmp_path, LIVE_RELAXED)
    result = _run(tmp_path, stubs)
    assert result.returncode == 1
    assert "BRANCH_PROTECTION: drift" in result.stderr
    assert "ci/woodpecker/pr/woodpecker" in result.stderr, "declared side must be shown"


@requires_jq
def test_checks_array_form_is_equivalent_to_contexts(tmp_path: Path):
    # GitHub may return required contexts under `checks[].context` instead of the
    # legacy `contexts` list. Normalization must read both, or an in-sync repo
    # reports permanent drift.
    live = json.loads(json.dumps(LIVE_IN_SYNC))
    live["required_status_checks"] = {
        "strict": True,
        "contexts": [],
        "checks": [{"context": "ci/woodpecker/pr/woodpecker", "app_id": None}],
    }
    stubs = _make_stub(tmp_path, live)
    result = _run(tmp_path, stubs)
    assert result.returncode == 0, result.stderr + result.stdout


@requires_jq
def test_unprotected_branch_is_drift_not_crash(tmp_path: Path):
    # An unprotected branch 404s with an empty body; that is the maximally-drifted
    # state, not an error to die on.
    stubs = _make_stub(tmp_path, None, api_exit=1)
    result = _run(tmp_path, stubs)
    assert result.returncode == 1
    assert "BRANCH_PROTECTION: drift" in result.stderr


@requires_jq
def test_apply_puts_the_declared_payload(tmp_path: Path):
    stubs = _make_stub(tmp_path, LIVE_IN_SYNC)
    result = _run(tmp_path, stubs, "--apply")
    assert result.returncode == 0, result.stderr
    calls = _calls(stubs)
    put = [c for c in calls if "--method PUT" in c]
    assert len(put) == 1, calls
    assert "branches/main/protection" in put[0]


@requires_jq
def test_explicit_repo_overrides_the_owner_repo_placeholder(tmp_path: Path):
    stubs = _make_stub(tmp_path, LIVE_IN_SYNC)
    result = _run(tmp_path, stubs, "--repo", "someone/elsewhere")
    assert result.returncode == 0, result.stderr
    assert any("someone/elsewhere/branches/main/protection" in c for c in _calls(stubs))


def test_unknown_argument_is_usage_error(tmp_path: Path):
    stubs = _make_stub(tmp_path, LIVE_IN_SYNC)
    result = _run(tmp_path, stubs, "--wat")
    assert result.returncode == 2
    assert "Usage" in result.stderr


@requires_jq
def test_missing_config_fails_clearly(tmp_path: Path):
    stubs = _make_stub(tmp_path, LIVE_IN_SYNC)
    result = _run(tmp_path, stubs, config=tmp_path / "nope.json")
    assert result.returncode == 1
    assert "not found" in result.stderr
