"""Run `flow-plan-record.py compliance` on one case, in a throwaway repository.

    run-case.py <case-dir> <gate>

A case directory holds `section.md` (the text a run appends to its plan record
before approval), optionally `lanes.md` (the project's `.claude/lanes.md`; none
is the project that has not adopted lanes), and optionally `demonstrated.md`
(the run's `docs/flow-runs/issue-42.lanes-demonstrated.md`). A file named
`demonstrated-is-a-directory` makes that path a directory, which is one way
for it to exist and be unreadable.

The runner approves the plan, writes the planned file, and asks the gate for
its compliance verdict. COMPLIANCE NEVER CHANGES ITS EXIT CODE FOR A LANE - the
owner chose the verdict line, not a refusal (#1767) - so the exit code here is
the runner's own reading of that ONE line: 1 when the line carries a LANES
clause, 0 when it does not. The line itself is printed unchanged.
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
    print("FLOW_PLAN_RECORD_LANES_VERDICT_CONTROL: unavailable - git is not on PATH")
    raise SystemExit(3)

env = {k: v for k, v in os.environ.items() if k not in ("CODEX_THREAD_ID", "GIT_DIR", "GIT_WORK_TREE")}
env.update(CLAUDE_CODE_SESSION_ID="lanes-verdict-control", GIT_AUTHOR_NAME="c",
           GIT_AUTHOR_EMAIL="c@example.com", GIT_COMMITTER_NAME="c", GIT_COMMITTER_EMAIL="c@example.com",
           GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)


def run(*argv: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True)


def setup(*argv: str, cwd: Path) -> None:
    done = run(*argv, cwd=cwd)
    if done.returncode != 0:
        print("FLOW_PLAN_RECORD_LANES_VERDICT_CONTROL: unavailable - setup step failed: "
              f"{' '.join(argv[:3])}")
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
    setup(sys.executable, str(gate), "approve", "42", cwd=repo)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n")
    shown = repo / "docs" / "flow-runs" / "issue-42.lanes-demonstrated.md"
    if (case / "demonstrated.md").exists():
        shutil.copy(case / "demonstrated.md", shown)
    elif (case / "demonstrated-is-a-directory").exists():
        shown.mkdir()
    done = run(sys.executable, str(gate), "compliance", "42", "--base", "main", cwd=repo)
    lines = [line for line in done.stdout.splitlines() if line.startswith("PLAN_COMPLIANCE: ")]
    if len(lines) != 1:
        print("FLOW_PLAN_RECORD_LANES_VERDICT_CONTROL: unavailable - compliance printed "
              f"{len(lines)} verdict lines, not one")
        print(done.stdout + done.stderr)
        raise SystemExit(3)
    print(lines[0])
    sys.stderr.write(done.stderr)
    raise SystemExit(1 if ", LANES NOT " in lines[0] else 0)
