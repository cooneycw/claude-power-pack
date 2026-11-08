"""Exercise the published preservation recipe, including failed publication."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".claude/commands/flow/cleanup.md"
requires_tools = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("bash", "git", "awk", "python3", "mktemp", "cat", "rm")),
    reason="requires bash, git, awk, python3, mktemp, cat and rm",
)
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")


def _recipe():
    match = re.search(
        r"<!-- preserved-wip-handoff:begin -->\s*```bash\n(.*?)\n```\s*"
        r"<!-- preserved-wip-handoff:end -->", SOURCE.read_text(), re.S,
    )
    assert match, "preservation has no executable issue-handoff recipe"
    return match[1]


@requires_tools
@requires_git
@pytest.mark.parametrize("mode", [
    "good", "closed", "post-fails", "readback-mismatch", "remote-tip-mismatch", "wrong-issue-url",
])
def test_preservation_requires_a_readable_handoff_for_the_pushed_tip(tmp_path, mode):
    recipe = _recipe()
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (repo / "work.txt").write_text("preserved work\n")
    git("add", "work.txt")
    git("commit", "-qm", "preserved work")
    git("branch", "-M", "issue-42-preserved")
    git("remote", "add", "origin", str(remote))
    git("push", "-q", "origin", "HEAD")
    if mode == "remote-tip-mismatch":
        (repo / "work.txt").write_text("unpushed remainder\n")
        git("commit", "-qam", "unpushed work")
    tip = git("rev-parse", "HEAD")
    pushed = git("ls-remote", "origin", "refs/heads/issue-42-preserved").split()[0]
    assert (tip != pushed) == (mode == "remote-tip-mismatch")

    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
mode = os.environ['HANDOFF_MODE']
if args == ['--fixture-mode']:
    print(mode)
    sys.exit(0)
root = Path(os.environ['HANDOFF_FIXTURE'])
with (root / 'calls.jsonl').open('a') as log:
    log.write(json.dumps(args) + '\\n')
if '--method' in args:
    body = next(arg[6:] for arg in args if arg.startswith('body=@'))
    (root / 'body.txt').write_text(Path(body).read_text())
    if mode == 'post-fails':
        print('fixture rejects comment creation', file=sys.stderr)
        sys.exit(1)
    print('101')
elif '.state' in args:
    print('closed' if mode == 'closed' else 'open')
elif '.body' in args:
    print('mismatched body' if mode == 'readback-mismatch' else (root / 'body.txt').read_text())
elif '.html_url' in args:
    issue = '99' if mode == 'wrong-issue-url' else '42'
    print(f'https://github.com/example/repo/issues/{issue}#issuecomment-101')
else:
    raise SystemExit('unexpected API request')
''')
    gh.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}",
           "WIP_ROOT": str(repo), "WIP_REPO": "example/repo", "WIP_ISSUE": "42",
           "WIP_PROVENANCE": "Preserved as found by fixture worker",
           "WIP_REMAINING": "Verify tests; retain literal $(touch must-not-run)",
           "HANDOFF_MODE": mode, "HANDOFF_FIXTURE": str(tmp_path)}
    configured = subprocess.run([str(gh), "--fixture-mode"], env=env, capture_output=True, text=True, check=True)
    assert configured.stdout.strip() == mode
    result = subprocess.run(["bash", "-c", recipe], cwd=tmp_path, env=env, capture_output=True, text=True)
    if mode in ("good", "closed"):
        assert result.returncode == 0, result.stderr
        assert "PRESERVED_WIP_HANDOFF: https://github.com/example/repo/issues/42#issuecomment-101" in result.stdout
        body = (tmp_path / "body.txt").read_text()
        assert tip in body and "issue-42-preserved" in body
        assert f"#42 ({'closed' if mode == 'closed' else 'open'})" in body
        assert env["WIP_PROVENANCE"] in body and env["WIP_REMAINING"] in body
        calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
        assert any("POST" in args and "repos/example/repo/issues/42/comments" in args for args in calls)
        assert not (tmp_path / "must-not-run").exists()
    else:
        assert result.returncode != 0
        assert "PRESERVED_WIP_HANDOFF:" not in result.stdout
    if mode == "remote-tip-mismatch":
        assert not (tmp_path / "calls.jsonl").exists(), "wrong-tip preservation reached GitHub"
    assert repo.is_dir() and git("rev-parse", "HEAD") == tip
    assert git("ls-remote", "origin", "refs/heads/issue-42-preserved").split()[0] == pushed
