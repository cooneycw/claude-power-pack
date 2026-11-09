#!/usr/bin/env python3
"""Real wait-function projection; full-entrypoint tests cover no-merge effects."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    gate, case = map(Path, sys.argv[1:])
    if any(shutil.which(binary) is None for binary in ("bash", "jq")):
        print("APP_CHECK_CONTROL: unavailable")
        return 3
    data = json.loads((case / "input.json").read_text())
    assert data["required"]["checks"] == [{"context": "test", "app_id": 15368}]
    rows = data["runs"]["check_runs"]
    if data["condition"] != "good":
        assert not rows or any(row["app"]["id"] != 15368 or row["conclusion"] != "success" for row in rows)
    source = gate.read_text()
    projection = source[source.index("_gh_api_jq() {"):source.index("# Neither mechanism could be read")]
    with tempfile.TemporaryDirectory(prefix="app-check-control-") as directory:
        root = Path(directory)
        for name in ("required", "runs"):
            (root / (name + ".json")).write_text(json.dumps(data[name]))
        rollup = [{"context": line.rsplit("|", 1)[0], "state": line.rsplit("|", 1)[1]}
                  for line in data["rollup"].splitlines()]
        (root / "rollup.json").write_text(json.dumps({"statusCheckRollup": rollup}))
        if data.get("superseded"):
            assert len(rows) == 2 and rows[0]["check_suite"] == rows[1]["check_suite"]
            assert rows[0]["conclusion"] == "failure" and rows[1]["conclusion"] == "success"
            assert rows[0]["id"] < rows[1]["id"]
            (root / "runs-latest.json").write_text(json.dumps({"check_runs": rows[-1:]}))
        gh = root / "gh"
        gh.write_text('''#!/usr/bin/env bash
case "$1 $2" in
  api*protection/required_status_checks) file="$FIXTURE/required.json" ;;
  api*rules/branches/*) echo '[]' | jq -r "$4"; exit $? ;;
  api*check-runs*)
    file="$FIXTURE/runs.json"
    if [[ "$2" == *filter=latest* && -f "$FIXTURE/runs-latest.json" ]]; then
      file="$FIXTURE/runs-latest.json"
    fi ;;
  'pr view')
    if [[ "$*" == *statusCheckRollup* ]]; then file="$FIXTURE/rollup.json"
    else echo 'branch aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'; exit 0; fi ;;
  *) exit 2 ;;
esac
while (($#)); do
  if [[ "$1" == --jq ]]; then jq -r "$2" "$file"; exit $?; fi
  shift
done
exit 2
''')
        gh.chmod(0o755)
        script = root / "projected.sh"
        script.write_text('set -uo pipefail\n' + projection + '''
PR_NUMBER=42
PR_BASE_BRANCH=main
MATCH_HEAD_COMMIT=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
MATCH_HEAD_SET=1
WAIT_CI_SECS=""
GH_PR_MERGE_CHECK_ATTEMPTS=1
GH_PR_MERGE_CHECK_DELAY=0
wait_for_required_checks
''')
        result = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=10,
                                env={**os.environ, "GH_BIN": str(gh), "FIXTURE": str(root)})
        if result.returncode in (1, 10) and ("CI_WAIT: red" in result.stdout or "CI_WAIT: expired" in result.stdout):
            print("APP_CHECK_CONTROL: blocked")
            return 1
        if result.returncode == 0 and "CI_WAIT: green" in result.stdout:
            print("APP_CHECK_CONTROL: green")
            return 0
        print("APP_CHECK_CONTROL: unavailable - malformed gate evidence")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
