"""Admission only; mocked producer/identity is never actual root acceptance."""
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.test_ci_shape_ci_entry import exercise  # noqa: E402


def main():
    gate, case_path = map(Path, sys.argv[1:3])
    case = json.loads((case_path / "case.json").read_text())["case"]
    with tempfile.TemporaryDirectory(prefix="cpp-ci-entry-control-") as owned:
        with pytest.MonkeyPatch.context() as patch:
            code, calls, receipt, _ = exercise(gate, Path(owned), case, patch)
            if code == 0 and len(calls) == 1:
                print("CI_SHAPE_CI_CONTROL: admitted - producer invoked")
                return 0
            if code == 2 and not calls and receipt.exists():
                record = json.loads(receipt.read_text())
                if record["state"] == "UNKNOWN":
                    print("CI_SHAPE_CI_CONTROL: refused - UNKNOWN before producer")
                    return 1
    print("CI_SHAPE_CI_CONTROL: unavailable - admission not established")
    return 2
if __name__ == "__main__":
    raise SystemExit(main())
