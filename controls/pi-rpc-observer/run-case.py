"""Feed committed raw RPC pairs to the actual reader, without pi or credentials."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    gate, case = map(Path, sys.argv[1:3])
    seed = json.loads((case / "case.json").read_text())
    assert seed["record"]["expected"], "fixture must define a nonzero expected population"
    record, scenario = seed["record"], seed["scenario"]
    if scenario == "added-diagnostic":
        assert record["installed"]["stderr"] != record["baseline"]["stderr"]
    elif scenario == "unavailable-tool-inventory":
        assert record["tools"] is None
    elif scenario == "replaced-builtin-tool":
        assert record["tools"]["baseline"] != record["tools"]["installed"]
    elif scenario in ("empty-success", "missing-expected-skill"):
        assert json.loads(record["installed"]["stdout"])["data"]["commands"] == []
    elif scenario == "missing-response":
        assert record["installed"]["stdout"] == ""
    elif scenario == "duplicate-response-id":
        assert record["installed"]["stdout"].count('"id": "commands"') == 2
    elif scenario == "malformed-response":
        assert record["installed"]["stdout"] == "{invalid\n"
    with tempfile.TemporaryDirectory(prefix="pi-rpc-reader-") as temporary:
        record = Path(temporary) / "record.json"
        record.write_text(json.dumps(seed["record"]))
        answer = subprocess.run([sys.executable, str(gate), "--read-rpc", str(record)],
                                capture_output=True, text=True, timeout=15)
    print(answer.stdout, end="")
    print(answer.stderr, end="", file=sys.stderr)
    return answer.returncode


if __name__ == "__main__":
    raise SystemExit(main())
