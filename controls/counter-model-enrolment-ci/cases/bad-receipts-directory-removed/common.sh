# Sourced by each case's setup.sh. Builds a repository whose HEAD is DETACHED,
# because that is what a CI pull_request checkout is: a SHA, no branch name.
set -eu
init_repo() {
  git init -q -b master .
  git config user.email c@c; git config user.name c
  git config commit.gpgsign false
  echo base > base.txt; git add -A; git commit -qm base
}
write_receipt() { # $1 head  $2 status  $3 branch  $4 skip_reason
  mkdir -p docs/measurements/counter-model
  python3 - "$@" <<PYEOF
import json, os, sys, pathlib
head, status, branch = sys.argv[1], sys.argv[2], sys.argv[3]
r = {"schema": 1, "recorded_at": "2026-10-17T00:00:00Z", "issue": "1452",
     "branch": branch, "head": head, "status": status,
     "reviewer": None if status == "skipped" else "codex/gpt-6.1-sol",
     "implementer": "claude/claude-opus-5-5"}
if status == "skipped":
    r["skip_reason"] = sys.argv[4]
elif os.environ.get("NO_SCOPE") != "1":
    r["scope"] = "diff-only"
name = f"{branch}-{status}.json"
pathlib.Path("docs/measurements/counter-model", name).write_text(json.dumps(r, indent=2))
PYEOF
}
