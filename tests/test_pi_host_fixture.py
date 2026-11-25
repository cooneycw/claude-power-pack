"""RPC reader and lifecycle tests; these do not require or simulate live pi."""
import copy
import json
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = runpy.run_path(str(ROOT / "scripts/pi-host-fixture.py"))


@pytest.mark.parametrize("path", sorted((ROOT / "controls/pi-rpc-observer/cases").glob("*/case.json")),
                         ids=lambda p: p.parent.name)
def test_committed_rpc_cases(path):
    seed = json.loads(path.read_text())
    try:
        state = SUBJECT["rpc_audit"](seed["record"])["state"]
    except (ValueError, KeyError, TypeError):
        state = "unknown"
    assert state == {"GOOD": "matches", "BAD": "finding", "UNKNOWN": "unknown"}[seed["expect"]]


def test_missing_tool_inventory_never_borrowed_from_discovery():
    seed = json.loads((ROOT / "controls/pi-rpc-observer/cases/populated-baseline-pair/case.json").read_text())
    record = copy.deepcopy(seed["record"])
    record["tools"] = None
    assert SUBJECT["rpc_audit"](record)["state"] == "unknown"


def test_timeout_stops_and_reaps_actual_fixture_child(tmp_path):
    result = SUBJECT["run_child"]([sys.executable, "-c", "import time; time.sleep(30)"],
                                   tmp_path, {"HOME": str(tmp_path)}, timeout=0.05)
    assert result["forced_stop"] and result["exit"] is not None and result["exit"] != 0
