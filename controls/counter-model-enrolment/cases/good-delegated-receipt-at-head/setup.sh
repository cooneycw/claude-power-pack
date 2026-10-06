#!/usr/bin/env bash
# A DELEGATED review (issue #1383): Codex implemented, the supervising Claude
# session reviewed. Before #1383 no honest receipt of this shape could be
# written, so every /codex:auto run reached this gate with nothing to show and
# went red. The gate reads only branch/head/status, so this case proves the
# direction field changes nothing about enrolment - a delegated `ran` receipt
# satisfies it exactly as a default-direction one does. The receipt's own
# shape is pinned by tests/test_counter_model_review.py, which validates this
# exact body.
set -eu
git init -q -b master .
git config user.email c@c; git config user.name c
git config commit.gpgsign false
echo base > base.txt; git add -A; git commit -qm base
mkdir -p docs/measurements/counter-model
python3 - "$(git rev-parse HEAD)" <<'PYEOF'
import json, sys, pathlib
r = {"schema": 1, "recorded_at": "2026-10-06T12:00:00Z", "issue": "1383",
     "branch": "master", "head": sys.argv[1], "status": "ran",
     "direction": "delegated",
     "implementer": "codex/gpt-6-astra",
     "implementer_evidence": {"thread_id": "t", "rollout": "2026/10/06/rollout-t.jsonl"},
     "reviewer": "claude/claude-opus-5-5",
     "reviewer_evidence": {"session_id": "s"},
     "passes": 1,
     "counts": {"accepted": 0, "rejected": 0, "deferred": 0},
     "red_cases": {"proposed": 0, "already_covered": 0}}
pathlib.Path("docs/measurements/counter-model/receipt.json").write_text(json.dumps(r, indent=2))
PYEOF
