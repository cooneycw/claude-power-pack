"""Unconditional contract and fixture dogfood for the vendored engine (#723)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "project_next"
FIXTURES = VENDOR / "tests" / "project_next" / "fixtures"
NEXT_MD = ROOT / ".claude" / "commands" / "project" / "next.md"
MANIFEST = ROOT / ".claude" / "project-next-vendor.json"

sys.path.insert(0, str(VENDOR))
from lib.project_next import CONTRACT_VERSION  # noqa: E402
from lib.project_next.models import RepositoryState  # noqa: E402
from lib.project_next.rank import recommend  # noqa: E402
from lib.project_next.render import render_result  # noqa: E402


def test_wiring_always_uses_the_vendored_engine_and_manifest_pin() -> None:
    text = NEXT_MD.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert "vendor/project_next/" in text
    assert "scripts/project-next.py" in text
    assert ".claude/project-next-vendor.json" in text
    assert "VERBATIM" in text
    assert "vendored engine" in text
    assert "no sibling-checkout probe" in text
    assert manifest["contract_version"] == CONTRACT_VERSION


def test_old_host_probe_and_prompt_fallback_are_fully_superseded() -> None:
    text = NEXT_MD.read_text(encoding="utf-8")

    assert "CPP fallback " + "(prompt-based)" not in text
    assert "Engine present but FAILS" not in text
    assert "Engine found" not in text


def test_vendored_fixture_corpus_matches_engine_classification() -> None:
    scenarios = json.loads((FIXTURES / "scenarios.json").read_text(encoding="utf-8"))

    for name, scenario in scenarios.items():
        result = recommend(RepositoryState.from_dict(scenario["state"]))
        expected = scenario["expected"]
        assert list(result.classification.in_flight) == expected["in_flight"], name
        assert list(result.classification.blocked) == expected["blocked"], name
        assert list(result.classification.available) == expected["available"], name
        assert list(result.classification.uncertain) == expected["uncertain"], name
        if result.next_startable_issue is not None:
            assert result.next_startable_issue in result.classification.available, name


def test_vendored_human_and_json_goldens_are_executable() -> None:
    scenarios = json.loads((FIXTURES / "scenarios.json").read_text(encoding="utf-8"))
    operational = RepositoryState.from_dict(scenarios["operational_report"]["state"])
    result = recommend(operational)
    for mode, filename in (("brief", "brief.txt"), ("compact", "compact.md"), ("full", "full.md")):
        expected = (FIXTURES / "golden" / filename).read_text(encoding="utf-8").rstrip("\n")
        assert render_result(result, operational, mode) == expected

    empty = RepositoryState.from_dict(scenarios["empty_repository"]["state"])
    expected_json = (FIXTURES / "golden" / "result.json").read_text(encoding="utf-8").rstrip("\n")
    assert json.dumps(recommend(empty).to_dict(), indent=2, sort_keys=True) == expected_json


def test_cpp_entry_point_runs_vendored_fixture_without_optional_checkout(tmp_path: Path) -> None:
    scenarios = json.loads((FIXTURES / "scenarios.json").read_text(encoding="utf-8"))
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(scenarios["active_pr_and_safe_issue"]["state"]), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "project-next.py"),
            str(tmp_path),
            "--input",
            str(state_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["decision_policy"] == f"contract v{CONTRACT_VERSION} (vendored engine)"
    assert payload["next_startable_issue"] == 2
    assert "cpp_extensions" in payload


def test_offline_vendor_hash_gate_is_part_of_the_suite() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "project-next-vendor.py")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "16 files match" in completed.stdout
