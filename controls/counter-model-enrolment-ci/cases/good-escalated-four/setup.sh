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
r["passes"] = 4; r["extra_passes_reason"] = "fixture review needed another pass"; r["escalation"] = dict(ruled_by="fixture authority", reference="fixture ruling", raised_cap=4)
p.write_text(json.dumps(r, indent=2)+"\n")
PYCASE
