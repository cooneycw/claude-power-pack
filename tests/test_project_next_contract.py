"""Unconditional contract and fixture dogfood for the project-next engine (#723).

Re-pointed at the #1069 ownership transfer. What each assertion below now tests,
and why, is recorded at the assertion rather than in this docstring: the ones
that pinned the VENDORING arrangement had to be re-pointed or retired, and a
retired assertion that is simply deleted takes the distinction it drew with it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "project_next" / "fixtures"
NEXT_MD = ROOT / ".claude" / "commands" / "project" / "next.md"
MANIFEST = ROOT / ".claude" / "project-next-ownership.json"

# No sys.path insert: `lib/project_next` is CPP's own package now (issue #1069)
# and resolves from the repo root like `lib.cicd` or `lib.security`. The insert
# that used to be here pointed at `vendor/project_next`, which no longer exists.
from lib.project_next import CONTRACT_VERSION  # noqa: E402
from lib.project_next.models import RepositoryState  # noqa: E402
from lib.project_next.rank import recommend  # noqa: E402
from lib.project_next.render import render_result  # noqa: E402


def test_wiring_always_uses_the_owned_engine_and_manifest_pin() -> None:
    text = NEXT_MD.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    # RE-POINTED (#1069). The doc must still name where the engine lives; only
    # the location changed, so the assertion survives at its new target.
    assert "lib/project_next/" in text
    # UNCHANGED. The entry point did not move.
    assert "scripts/project-next.py" in text
    # RE-POINTED (#1069): the manifest is an ownership record, not a vendor pin.
    assert ".claude/project-next-ownership.json" in text
    # UNCHANGED, and the most load-bearing line here: the decision comes VERBATIM
    # from the engine. Ownership changed; that invariant did not.
    assert "VERBATIM" in text
    # RETIRED AND REPLACED (#1069). This asserted `"vendored engine" in text`.
    # Keeping it would re-assert the premise the transfer retired, and deleting
    # it outright would drop the question it was really asking - does the doc
    # state where the decision policy comes from? It now asserts OWNERSHIP,
    # which is what silently regresses if anyone re-vendors this engine.
    assert "CPP OWNS the engine" in text
    assert "not vendored from anywhere now" in text
    # UNCHANGED.
    assert "no sibling-checkout probe" in text
    assert manifest["contract_version"] == CONTRACT_VERSION


def test_old_host_probe_and_prompt_fallback_are_fully_superseded() -> None:
    text = NEXT_MD.read_text(encoding="utf-8")

    assert "CPP fallback " + "(prompt-based)" not in text
    assert "Engine present but FAILS" not in text
    assert "Engine found" not in text


def test_owned_fixture_corpus_matches_engine_classification() -> None:
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


def test_cpp_entry_point_runs_the_owned_fixture_without_optional_checkout(tmp_path: Path) -> None:
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
    # RE-POINTED (#1069). The label read "(vendored engine)", which is now false.
    # Its JOB - saying the decision came VERBATIM from the engine rather than
    # from the adapter or a prompt - survives the transfer; only the vendoring
    # claim retires, so the assertion moves rather than going away.
    assert payload["decision_policy"] == f"contract v{CONTRACT_VERSION} (project-next engine)"
    assert payload["next_startable_issue"] == 2
    assert "cpp_extensions" in payload


def test_offline_ownership_hash_gate_is_part_of_the_suite() -> None:
    """RE-POINTED (#1069): same property, successor gate.

    The point was never "the vendor script runs" - it is that the offline hash
    gate `make verify` depends on is exercised by the suite too, so a gate that
    breaks is caught by the tests and not only by the aggregate.
    """
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "project-next-ownership.py"), "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "11 files match" in completed.stdout
