"""Execute init's permission-only observer and pin profile-question reachability."""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"
CASES = json.loads((ROOT / "tests/fixtures/cpp-init-permission-summary/cases.json").read_text())


def _profile_tiers(text):
    section = text.split("## Step 3b:", 1)[1].split("## Step 4:", 1)[0]
    matches = re.findall(r"^\*\*Only show this step.*?$", section, re.M)
    assert len(matches) == 1, "profile question needs one explicit tier condition"
    tiers = {int(value) for value in re.findall(r"Tier ([1-7])", matches[0])}
    assert tiers, "tier extractor must examine a nonempty condition"
    return tiers


@pytest.mark.parametrize("tier", range(1, 8))
def test_profile_question_covers_every_tier_that_installs_tier_two(tier):
    assert (tier in _profile_tiers(INIT.read_text())) is (tier in {2, 3, 4, 5})


def _observer_code():
    matches = re.findall(
        r"^# CPP_INIT_PERMISSION_OBSERVER_BEGIN\n(.*?)^# CPP_INIT_PERMISSION_OBSERVER_END$",
        INIT.read_text(), re.M | re.S,
    )
    assert len(matches) == 1, "missing unique executable permission observer"
    assert matches[0].strip(), "observer extraction must not silently examine nothing"
    return matches[0]


def _observe(monkeypatch, settings, presets=INIT):
    monkeypatch.setattr(sys, "argv", ["permission-observer", str(presets), str(settings)])
    output = io.StringIO()
    with contextlib.redirect_stdout(output), pytest.raises(SystemExit) as stopped:
        exec(compile(_observer_code(), str(INIT), "exec"), {"__name__": "__main__"})
    raw = output.getvalue()
    assert "do-not-render-this-value" not in raw
    assert "PRIVATE_TEST_FIELD" not in raw
    return stopped.value.code, json.loads(raw)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_observer_reads_actual_project_file_without_emitting_values(tmp_path, monkeypatch, case):
    settings = tmp_path / "settings.local.json"
    if case["mode"] == "json":
        settings.write_text(json.dumps(case["settings"]))
    elif case["mode"] == "raw":
        settings.write_text(case["settings"])
    elif case["mode"] == "directory":
        settings.mkdir()
        assert settings.is_dir(), "fixture must really be unreadable as a file"
    else:
        assert case["mode"] == "absent" and not settings.exists()
    code, report = _observe(monkeypatch, settings)
    assert code == (0 if case["verified"] else 3)
    assert report["verified"] is case["verified"]
    assert report["verification"] == ("verified" if case["verified"] else "unverified")
    assert report["profile"] == case["profile"]
    assert report["counts"] == case["counts"]
    assert report["scope"] == "project-file declarations only"


def test_retained_standard_file_is_not_inferred_to_be_selected_trusted(tmp_path, monkeypatch):
    case = next(case for case in CASES if case["name"] == "standard")
    settings = tmp_path / "settings.local.json"
    settings.write_text(json.dumps(case["settings"]))
    monkeypatch.setenv("PROFILE_NAME", "Trusted")
    code, report = _observe(monkeypatch, settings)
    assert code == 0 and report["profile"] == "Standard"
    assert report["profile"] != "Trusted"


def test_missing_canonical_definitions_are_unverified_not_guessed(tmp_path, monkeypatch):
    case = next(case for case in CASES if case["name"] == "cautious")
    settings = tmp_path / "settings.local.json"
    settings.write_text(json.dumps(case["settings"]))
    missing = tmp_path / "missing-init.md"
    assert not missing.exists()
    code, report = _observe(monkeypatch, settings, presets=missing)
    assert code == 3 and report["verified"] is False
    assert report["profile"] == "unknown"


def test_summary_permission_lines_use_observation_and_keep_other_steps_untouched():
    summary = INIT.read_text().split("## Step 7: Installation Summary", 1)[1]
    assert "Permission Profile: {PERMISSION_REPORT.profile}" in summary
    assert "{PROFILE_NAME}" not in summary
    assert "Blocked: rm -rf, git push --force, sudo" not in summary
    for field in ("allow", "ask", "deny"):
        assert "{PERMISSION_REPORT.counts." + field + "}" in summary
    assert "{STEP_RESULTS}" in summary and "{MCP_RESULTS}" in summary
    assert "does not re-check other installation steps" in summary
    assert "null means unverified; numeric zero remains zero" in summary


def test_custom_wording_names_only_the_provided_pr_write_category():
    text = INIT.read_text()
    assert "The Custom GitHub CLI write category adds PR create/merge only" in text
    assert "does not include issue-write verbs" in text
    assert "Select Custom mode to choose\nbroader GitHub permissions explicitly" not in text


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
@pytest.mark.parametrize("status", [0, 19], ids=["silent-zero", "silent-failure"])
def test_shell_wrapper_reports_unverified_when_observer_emits_nothing(tmp_path, status):
    summary = INIT.read_text().split("## Step 7: Installation Summary", 1)[1]
    block = re.search(r"^```bash\n(.*?)^```$", summary, re.S | re.M)
    assert block, "summary must run the observer before rendering permission fields"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "python3"
    stub.write_text(f"#!{shutil.which('bash')}\nexit {status}\n")
    stub.chmod(0o755)
    env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ["PATH"], CPP_DIR=str(ROOT))
    assert shutil.which("python3", path=env["PATH"]) == str(stub), "fixture must really intercept the observer"
    result = subprocess.run(["bash", "-c", block[1]], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
    report = json.loads(result.stdout)
    assert report["verified"] is False and report["verification"] == "unverified"
    assert report["counts"] == dict.fromkeys(("allow", "ask", "deny"))
