"""Run `flow-plan-record.py approve` on one case, in a throwaway repository.

    run-case.py <case-dir> <gate>

A case directory holds `section.md`, the text a run appends to its plan record
before asking for approval, and optionally `lanes.md`, which becomes the
project's `.claude/lanes.md`. No `lanes.md` is the project that has not adopted
lanes. The gate's own output and exit code are passed through unchanged.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

case = Path(sys.argv[1]).resolve()
gate = Path(sys.argv[2]).resolve()
git = shutil.which("git")
if not git:
    print("FLOW_PLAN_RECORD_LANES_CONTROL: unavailable - git is not on PATH")
    raise SystemExit(3)

env = {k: v for k, v in os.environ.items() if k not in ("CODEX_THREAD_ID", "GIT_DIR", "GIT_WORK_TREE")}
env.update(CLAUDE_CODE_SESSION_ID="lanes-control", GIT_AUTHOR_NAME="c", GIT_AUTHOR_EMAIL="c@example.com",
           GIT_COMMITTER_NAME="c", GIT_COMMITTER_EMAIL="c@example.com", GIT_CONFIG_GLOBAL=os.devnull,
           GIT_CONFIG_SYSTEM=os.devnull)


def run(*argv: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True)


def setup(*argv: str, cwd: Path) -> None:
    done = run(*argv, cwd=cwd)
    if done.returncode != 0:
        print(f"FLOW_PLAN_RECORD_LANES_CONTROL: unavailable - setup step failed: {' '.join(argv[:3])}")
        print(done.stdout + done.stderr)
        raise SystemExit(3)


with tempfile.TemporaryDirectory() as directory:
    repo = Path(directory) / "repo"
    repo.mkdir()
    setup(git, "init", "-q", "-b", "main", cwd=repo)
    (repo / "README.md").write_text("base\n")
    if (case / "lanes.md").exists():
        (repo / ".claude").mkdir()
        shutil.copy(case / "lanes.md", repo / ".claude" / "lanes.md")
    setup(git, "add", "-A", cwd=repo)
    setup(git, "commit", "-qm", "base", cwd=repo)
    setup(git, "checkout", "-q", "-b", "issue-42-a-case", cwd=repo)
    body = repo.parent / "body.md"
    body.write_text("The issue body.\n")
    setup(sys.executable, str(gate), "reconcile", "42", cwd=repo)
    setup(sys.executable, str(gate), "read-issue", "42", "--body-file", str(body), cwd=repo)
    setup(sys.executable, str(gate), "begin-run", "42", cwd=repo)
    with (repo / "docs" / "flow-runs" / "issue-42.md").open("a") as record:
        record.write((case / "section.md").read_text())
    approved = run(sys.executable, str(gate), "approve", "42", cwd=repo)
    sys.stdout.write(approved.stdout)
    sys.stderr.write(approved.stderr)
    raise SystemExit(approved.returncode)
