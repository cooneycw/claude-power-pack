# Case for controls/counter-model-enrolment (issue #1700).
# A receipt claiming FIVE passes with no recorded ruling: nobody raised the cap, so the count must not pass.
set -eu
git init -q -b master .
git config user.email c@c; git config user.name c
git config commit.gpgsign false
echo base > base.txt; git add -A; git commit -qm base
mkdir -p docs/measurements/counter-model
python3 - "$(git rev-parse HEAD)" <<'PYEOF'
import json, sys, pathlib
r = {"schema": 2, "recorded_at": "2026-09-21T12:00:00Z", "issue": "1700",
     "branch": "master", "head": sys.argv[1], "status": "ran",
     "reviewer": "codex/gpt-6-astra", "implementer": "claude/claude-opus-5",
     "passes": 5, "extra_passes_reason": "passes 1-4 each found a real defect in the previous fix"}
# no escalation block: the count is unruled
pathlib.Path("docs/measurements/counter-model/receipt.json").write_text(json.dumps(r, indent=2))
PYEOF
