"""Pin emitted literal value sets to the script reference (#1493)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/lane-serveability-check.sh"
DOC = ROOT / "docs/scripts.md"


def _assert_value_sets(script: str, doc: str) -> None:
    for function, key in (("emit", "STATUS"), ("emit_age", "FRESHNESS")):
        emitted = set(re.findall(rf'^\s*{function}\s+"([^"\n]+)"', script, re.M))
        enumerations = re.findall(rf'`LANE_SERVE_{key}:\s*([^`]+)`', doc)
        assert len(enumerations) == 1, f"expected one LANE_SERVE_{key} enumeration"
        documented = {value.strip() for value in enumerations[0].split("|")}
        assert emitted, f"no {function} literal call sites found"
        assert emitted == documented, (
            f"LANE_SERVE_{key}: script-only (missing from docs)={sorted(emitted - documented)}; "
            f"docs-only (missing from script)={sorted(documented - emitted)}"
        )


def test_emitted_values_match_documentation() -> None:
    _assert_value_sets(HELPER.read_text(), DOC.read_text())
