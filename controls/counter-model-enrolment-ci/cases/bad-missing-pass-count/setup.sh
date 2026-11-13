#!/usr/bin/env bash
. "$(dirname "$0")/common.sh" 2>/dev/null || . ./common.sh
init_repo
write_receipt "$(git rev-parse HEAD)" ran issue-9-pr
git add -A; git commit -qm "receipt"
echo after > after.txt; git add -A; git commit -qm "after review"
git checkout -q --detach HEAD

python3 - <<'PYCASE'
import json
from pathlib import Path
p=next(Path("docs/measurements/counter-model").glob("*.json"))
r=json.loads(p.read_text())
del r["passes"]; assert "passes" not in r
p.write_text(json.dumps(r, indent=2)+"\n")
PYCASE
