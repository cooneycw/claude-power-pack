# Case for controls/counter-model-enrolment-selection (issue #1707).
# An OLDER valid review and an UNUSABLE receipt for the commit being merged: the gate must judge the nearest one and red.
set -eu
git init -q -b master .
git config user.email c@c; git config user.name c
git config commit.gpgsign false
mkdir -p docs/measurements/counter-model
echo base > base.txt; git add -A; git commit -qm base
echo a > f.txt; git add -A; git commit -qm "older reviewed commit"
OLDER=$(git rev-parse HEAD)
echo b > f.txt; git commit -qam "the commit being merged"
HEAD_SHA=$(git rev-parse HEAD)
receipt() { # $1 filename  $2 head  $3 status
  printf '{\n  "schema": 1,\n  "recorded_at": "2026-09-21T12:00:00Z",\n  "issue": "1707",\n  "branch": "master",\n  "head": "%s",\n  "status": "%s",\n  "reviewer": "codex/gpt-6-astra",\n  "implementer": "claude/claude-opus-5"\n}\n' "$2" "$3" > "docs/measurements/counter-model/$1"
}
receipt 2026-01-01T000000Z-issue-1707.json "$OLDER" ran
receipt 2026-01-02T000000Z-issue-1707.json "$HEAD_SHA" garbage
