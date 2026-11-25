"""Relay the trace reader's verdict on finite committed raw-trace fixtures."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    gate, case = map(Path, sys.argv[1:3])
    seed = json.loads((case / "case.json").read_text())
    assert seed["record"]["traces"], "fixture must contain actual trace text"
    raw = "\n".join(seed["record"]["traces"].values())
    assert all(token in raw for token in seed["precondition_contains"]), "defining trace seed changed"
    assert all(pid not in seed["record"]["traces"] for pid in seed.get("absent_pids", []))
    with tempfile.TemporaryDirectory(prefix="pi-trace-reader-") as temporary:
        record = Path(temporary) / "record.json"
        record.write_text(json.dumps(seed["record"]))
        answer = subprocess.run([sys.executable, str(gate), str(record)],
                                capture_output=True, text=True, timeout=15)
    print(answer.stdout, end="")
    print(answer.stderr, end="", file=sys.stderr)
    return answer.returncode


if __name__ == "__main__":
    raise SystemExit(main())
