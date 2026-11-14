"""Exercise a delegated document's recorded approval boundary, not a live model."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def unavailable(reason):
    print("DELEGATED_PLAN_LANES: unavailable - " + reason)
    raise SystemExit(3)


def section(text, number):
    match = re.search(rf"^### Step {number}:.*?(?=^### Step \d+:|\Z)", text, re.M | re.S)
    if match is None:
        unavailable(f"Step {number} is absent")
    return match.group(0)


def calls(text):
    """Only literal invocations in bash fences, never a comment or prose mention."""
    found = []
    for block in re.findall(r"^```bash\n(.*?)^```", text, re.M | re.S):
        for line in block.splitlines():
            match = re.fullmatch(
                r'~/.claude/scripts/flow-plan-record\.py '
                r'(reconcile|read-issue|begin-run|approve|compliance) 42(?: --base "\$MERGE_BASE")?', line)
            if match:
                found.append(match.group(1))
            elif "flow-plan-record.py" in line and not line.lstrip().startswith("#"):
                unavailable("unsupported helper invocation")
    return found


driver, case_arg, candidate_arg = sys.argv[1:4]
mode = sys.argv[4] if len(sys.argv) > 4 else "approve"
if (case_mode := Path(case_arg) / "mode.txt").is_file():
    mode = case_mode.read_text().strip()
if mode not in {"approve", "compliance", "compliance-shell", "product"}:
    unavailable("unknown mode")
if driver not in {"codex", "qwen", "gemma"}:
    unavailable("unknown driver")
case, candidate = Path(case_arg).resolve(), Path(candidate_arg).resolve()
document = candidate if candidate.suffix == ".md" else ROOT / f".claude/commands/{driver}/auto.md"
try:
    text = document.read_text()
except OSError:
    unavailable("driver document cannot be read")
approval_calls = calls(section(text, 3))
if not approval_calls:
    print("DELEGATED_PLAN_LANES: legacy continuation - recorded approval has no lane check")
    raise SystemExit(0)
if approval_calls != ["begin-run", "approve"] or calls(section(text, 1)) != ["reconcile", "read-issue"]:
    unavailable("incomplete or reordered plan lifecycle")
if mode in {"compliance", "compliance-shell"} and calls(section(text, 7)) != ["compliance"]:
    unavailable("close has no supported compliance invocation")
git = shutil.which("git")
if not git:
    unavailable("git is absent")
helper = ROOT / "scripts/flow-plan-record.py" if candidate.suffix == ".md" else candidate
env = {k: v for k, v in os.environ.items()
       if not k.startswith("GIT_") and k not in {"CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID"}}
env.update(CLAUDE_CODE_SESSION_ID="delegated-lanes-control", GIT_AUTHOR_NAME="control",
           GIT_AUTHOR_EMAIL="control@example.com", GIT_COMMITTER_NAME="control",
           GIT_COMMITTER_EMAIL="control@example.com", GIT_CONFIG_GLOBAL=os.devnull,
           GIT_CONFIG_SYSTEM=os.devnull)


def run(argv, cwd):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=30)


def setup(argv, cwd):
    done = run(argv, cwd)
    if done.returncode:
        unavailable("owned setup failed: " + done.stdout + done.stderr)


with tempfile.TemporaryDirectory(prefix="delegated-lanes-") as raw:
    top = Path(raw)
    main, work = top / "main", top / "work"
    home = top / "home"
    installed = home / ".claude/scripts/flow-plan-record.py"
    installed.parent.mkdir(parents=True)
    shutil.copy2(helper, installed)
    env["HOME"] = str(home)
    main.mkdir()
    setup([git, "init", "-q", "-b", "main"], main)
    (main / "README.md").write_text("owned base\n")
    if (case / "lanes.md").exists():
        (main / ".claude").mkdir()
        shutil.copy2(case / "lanes.md", main / ".claude/lanes.md")
    setup([git, "add", "-A"], main)
    setup([git, "commit", "-qm", "base"], main)
    base = run([git, "rev-parse", "HEAD"], main).stdout.strip()
    setup([git, "worktree", "add", "-q", "-b", "issue-42-case", str(work)], main)
    setup([git, "remote", "add", "origin", str(main)], work)
    setup([git, "update-ref", "refs/remotes/origin/main", base], work)
    setup([git, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main"], work)
    assert (work / ".git").is_file(), "construct a linked worktree, not a second plain checkout"
    body = top / "issue.md"
    body.write_text("Owned issue body.\n")
    setup([sys.executable, str(helper), "reconcile", "42"], work)
    setup([sys.executable, str(helper), "read-issue", "42", "--body-file", str(body)], work)
    setup([sys.executable, str(helper), "begin-run", "42"], work)
    with (work / "docs/flow-runs/issue-42.md").open("a") as record:
        record.write((case / "section.md").read_text())
    done = run([sys.executable, str(helper), "approve", "42"], work)
    if mode in {"compliance", "compliance-shell", "product"} and done.returncode == 0:
        if mode != "product" or (case / "product.txt").exists():
            (work / "src").mkdir()
            (work / "src/app.py").write_text("# The planned implementation.\n")
        if (case / "demonstrated.md").is_file():
            shutil.copy2(case / "demonstrated.md", work / "docs/flow-runs/issue-42.lanes-demonstrated.md")
        if mode == "compliance":
            done = run([sys.executable, str(helper), "compliance", "42", "--base", base], work)
        else:
            if not shutil.which("bash"):
                unavailable("bash is absent")
            blocks = re.findall(r"^```bash\n(.*?)^```", text, re.M | re.S)
            if mode == "compliance-shell":
                block = next(b for b in blocks if 'compliance 42 --base "$MERGE_BASE"' in b)
            else:
                block = next((b for b in blocks if "DELEGATED_PRODUCT_CHANGE:" in b), None)
                if block is None:
                    block = next(b for b in blocks if "FILES_CHANGED=" in b and '"$FILES_CHANGED" -eq 0' in b)
            done = run(["bash", "-c", block], work)
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    raise SystemExit(done.returncode)
