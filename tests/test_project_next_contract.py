"""Pins for /project:next's adoption of the shared behavioral contract (#636).

The decision policy - classification, ranking, top-action vs next-startable -
is owned by codex-power-pack's versioned contract (v1.3) and its engine; CPP
keeps collection notes and rendering. Two layers of coverage:

- Wiring pins (always run): next.md names the pinned contract version, the
  engine entry point, the runtime version check, and the labeled fallback -
  the prose contract this repo actually ships.
- Dogfood (gate condition 2 semantics): SKIPS only when no CxPP checkout is
  present (the CI container has none). When a checkout with the engine IS
  present, any invocation error - missing dep, crash, bad JSON - is a FAILURE,
  never a skip: a skipif that swallows a broken engine on the one machine
  class that can exercise it rots silently. Runs fixture-backed (--input), so
  no network is involved.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NEXT_MD = ROOT / ".claude" / "commands" / "project" / "next.md"

CXPP_PROBES = [
    Path.home() / "Projects" / "codex-power-pack",
    Path("/opt/codex-power-pack"),
    Path.home() / ".codex-power-pack",
]


def _cxpp_dir() -> Path | None:
    for d in CXPP_PROBES:
        if (d / "scripts" / "project-next.py").is_file():
            return d
    return None


class TestWiring:
    """Always-run pins on the doc contract."""

    def test_pins_contract_version(self) -> None:
        text = NEXT_MD.read_text()
        assert "contract version 1.3" in text.lower() or "contract v1.3" in text.lower()

    def test_names_engine_entry_point_and_source_of_truth(self) -> None:
        text = NEXT_MD.read_text()
        assert "scripts/project-next.py" in text
        assert "codex-power-pack" in text
        assert "not an authoritative implementation" in text

    def test_runtime_version_check_instruction(self) -> None:
        # Gate condition 3: the doc must have the model READ the located
        # contract's stated version and flag a mismatch, never silently proceed.
        text = NEXT_MD.read_text()
        assert 'grep -m1 "Contract version"' in text
        assert "update the pin after review" in text

    def test_fallback_is_labeled_not_silent(self) -> None:
        text = NEXT_MD.read_text()
        assert "CPP fallback (prompt-based)" in text
        assert "never papered over" in text

    def test_engine_answer_is_verbatim(self) -> None:
        # The contract's core rule: no prompt-side override of the decision.
        text = NEXT_MD.read_text()
        assert "VERBATIM" in text


@pytest.mark.skipif(_cxpp_dir() is None, reason="no codex-power-pack checkout on this machine")
class TestDogfood:
    """Fixture-backed engine run. Present checkout + broken engine = FAIL."""

    def test_engine_runs_a_contract_fixture_and_honors_output_contract(
        self, tmp_path: Path
    ) -> None:
        if shutil.which("python3") is None:  # pragma: no cover
            pytest.fail("python3 missing but a CxPP checkout is present")
        cxpp = _cxpp_dir()
        assert cxpp is not None
        scenarios_file = cxpp / "tests" / "project_next" / "fixtures" / "scenarios.json"
        assert scenarios_file.is_file(), (
            "CxPP checkout present but fixture corpus missing - broken engine "
            "installs must FAIL this test, not skip (gate condition 2)"
        )
        scenarios = json.loads(scenarios_file.read_text())
        name, scenario = next(iter(sorted(scenarios.items())))
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps(scenario["state"]))

        proc = subprocess.run(
            [
                sys.executable,
                str(cxpp / "scripts" / "project-next.py"),
                "--input",
                str(state_file),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, (
            f"engine invocation failed on fixture '{name}' (checkout present -> "
            f"this is a FAILURE, not a skip):\n{proc.stderr}"
        )
        result = json.loads(proc.stdout)  # bad JSON raises -> failure, as required

        # Output contract shape: disjoint classification sets, and
        # next_startable never references a non-available issue.
        def _numbers(key: str) -> set:
            val = result.get(key) or result.get("classification", {}).get(key) or []
            out = set()
            for item in val:
                out.add(item["number"] if isinstance(item, dict) else item)
            return out

        in_flight = _numbers("in_flight")
        blocked = _numbers("blocked")
        uncertain = _numbers("uncertain")
        available = _numbers("available")
        sets = [in_flight, blocked, uncertain, available]
        for i, a in enumerate(sets):
            for b in sets[i + 1 :]:
                assert not (a & b), f"classification sets overlap: {a & b}"

        nsi = result.get("next_startable_issue")
        if isinstance(nsi, dict):
            nsi = nsi.get("number")
        if nsi is not None:
            assert nsi not in in_flight | blocked | uncertain
