"""Exercise the rendered parent-only salvage procedure, not live model obedience."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_delegated_plan_finish import bash_blocks

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/flow-plan-record.py"
CALL = '~/.claude/scripts/flow-plan-record.py declare-salvage 42 "$SALVAGE_SHA" --reason "<why>"'
BEGIN = "~/.claude/scripts/flow-plan-record.py begin-run 42"
APPROVE = "~/.claude/scripts/flow-plan-record.py approve 42"
DRIVERS = ("codex", "qwen", "gemma")
requires_tools = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("git", "bash")), reason="runs real git and bash",
)


def step3(driver: str) -> str:
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    return text.split("### Step 3:", 1)[1].split("### Pre-child", 1)[0]


def salvage_block(step: str) -> str:
    blocks = re.findall(r"```bash\n(.*?)\n```", step, re.S)
    found = [block for block in blocks if CALL in [line.strip() for line in block.splitlines()]]
    assert len(found) == 1, "one active declare-salvage block required"
    return found[0]


def parent_contract(step: str) -> None:
    commands = [entry for block in bash_blocks(step) for entry in block]
    locations = [[n for n, line in commands if line == call] for call in (BEGIN, CALL, APPROVE)]
    assert all(len(items) == 1 for items in locations), "one active lifecycle call each"
    assert locations[0][0] < locations[1][0], "declare after begin-run"
    assert locations[1][0] < locations[2][0], "declare before approve"
    block = salvage_block(step)
    assert [line.strip() for line in block.splitlines()] == [
        'SALVAGE_SHA=""', 'if [ -n "$SALVAGE_SHA" ]; then', CALL,
        "SALVAGE_EXIT=$?", '[ "$SALVAGE_EXIT" -eq 0 ] || exit "$SALVAGE_EXIT"', "fi",
    ], "explicit SHA reset and conditional declaration required"
    flat = " ".join(step.split())
    for clause in (
        "The parent, never the child, owns that commit",
        "commit it unmodified as its own ancestor checkpoint",
        "Never infer salvage from history",
        "no preserved work means no call",
        "Non-zero: STOP",
    ):
        assert clause in flat, f"missing parent policy: {clause}"


@pytest.mark.parametrize("driver", DRIVERS)
def test_real_driver_declares_only_explicit_parent_salvage_before_stamp(driver: str) -> None:
    parent_contract(step3(driver))
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    child_contract(text)


def child_contract(text: str) -> None:
    section = text.split("### Step 4:", 1)[1].split("### Step 5:", 1)[0]
    blocks = re.findall(r"^```[a-z]*\n(.*?)^```[ \t]*$", section, re.M | re.S)
    fences = [block for block in blocks if block.startswith("EXECUTION FENCE - MANDATORY CONSTRAINTS\n")]
    assert len(fences) == 1, "one actual child execution fence required"
    assert "You MUST NOT:" in fences[0], "child prohibition required"
    forbidden = fences[0].split("You MUST NOT:", 1)[1].split("You MAY:", 1)[0]
    assert re.search(
        r"^1\. Run git commit, git push, or any git command that modifies history or refs\.$",
        forbidden, re.M,
    ), "commit instruction must be prohibited inside the child prompt"


@pytest.mark.parametrize("name", ("good", "permission", "outside-prompt"))
def test_committed_child_fence_controls(name: str) -> None:
    text = (ROOT / f"tests/fixtures/delegated-salvage/fence-{name}.md").read_text()
    assert "Run git commit, git push" in text, "precondition: command phrase remains in every case"
    if name == "good":
        child_contract(text)
    else:
        with pytest.raises(AssertionError):
            child_contract(text)


@pytest.mark.parametrize("name", (
    "good", "missing-call", "after-approve", "before-begin-run", "unconditional", "child-commit",
))
def test_committed_parent_controls(name: str) -> None:
    text = (ROOT / f"tests/fixtures/delegated-salvage/{name}.md").read_text()
    if name == "good":
        parent_contract(text)
    else:
        if name == "missing-call":
            assert CALL not in text, "precondition: declaration absent"
        elif name == "after-approve":
            assert text.index(BEGIN) < text.index(APPROVE) < text.index(CALL), "precondition: late only"
        elif name == "before-begin-run":
            assert text.index(CALL) < text.index(BEGIN) < text.index(APPROVE), "precondition: early only"
        elif name == "unconditional":
            assert 'if [ -n "$SALVAGE_SHA" ]; then' not in text, "precondition: no conditional"
        else:
            assert "The child owns that commit" in text, "precondition: wrong commit owner"
        message = {"after-approve": "declare before approve", "before-begin-run": "declare after begin-run"}
        with pytest.raises(AssertionError, match=message.get(name)):
            parent_contract(text)


@requires_tools
@pytest.mark.parametrize("driver", DRIVERS)
@pytest.mark.parametrize("layout", ("main", "linked"))
@pytest.mark.parametrize("selection", ("empty", "ancestor", "invalid", "nonancestor", "ambient"))
def test_execute_conditional_before_real_approval(
    tmp_path: Path, driver: str, layout: str, selection: str,
) -> None:
    step = step3(driver)
    parent_contract(step)
    block = salvage_block(step)
    home = tmp_path / "home"
    installed = home / ".claude/scripts"
    installed.parent.mkdir(parents=True)
    installed.symlink_to(ROOT / "scripts", target_is_directory=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "python3").symlink_to(sys.executable)
    gh = bindir / "gh"
    gh.write_text("#!/bin/sh\nexit 1\n")
    gh.chmod(0o755)
    env = {"HOME": str(home), "PATH": f"{bindir}:{os.environ['PATH']}",
           "CLAUDE_CODE_SESSION_ID": "owned-salvage-fixture"}
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(repo), *args], env=env, text=True).strip()

    def run(script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["bash", "-c", script], cwd=repo, env=env,
                              capture_output=True, text=True, timeout=30)

    git("init", "-q", "-b", "fixture-main")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Fixture")
    (repo / "saved.txt").write_text("base\n")
    git("add", "saved.txt")
    git("commit", "-qm", "base")
    if layout == "linked":
        linked = tmp_path / "linked"
        git("worktree", "add", "-qb", "fixture-linked", str(linked))
        repo = linked
        assert (repo / ".git").is_file(), "precondition: linked worktree"
    preserved = b"pre-existing dirty bytes\n"
    (repo / "saved.txt").write_bytes(preserved)
    assert git("status", "--porcelain"), "precondition: dirty work before parent preservation"
    git("add", "saved.txt")
    git("commit", "-qm", "parent explicitly preserves unmodified work")
    ancestor = git("rev-parse", "HEAD")
    assert git("show", f"{ancestor}:saved.txt") + "\n" == preserved.decode()
    assert run(f'{sys.executable} "{HELPER}" reconcile 42').returncode == 0
    assert run(BEGIN).returncode == 0
    record = repo / "docs/flow-runs/issue-42.md"
    record_before = record.read_text()
    chosen = ""
    if selection == "ancestor":
        chosen = ancestor
    elif selection == "invalid":
        chosen = "0" * 40
        assert subprocess.run(["git", "cat-file", "-e", chosen], cwd=repo, env=env,
                              capture_output=True).returncode != 0, "precondition: invalid object"
    elif selection == "nonancestor":
        chosen = git("commit-tree", git("rev-parse", "HEAD^{tree}"), "-m", "unrelated")
        assert subprocess.run(["git", "merge-base", "--is-ancestor", chosen, "HEAD"],
                              cwd=repo, env=env).returncode == 1, "precondition: unrelated commit"
    elif selection == "ambient":
        env["SALVAGE_SHA"] = ancestor
    if chosen:
        assert 'SALVAGE_SHA=""' in block
        block = block.replace('SALVAGE_SHA=""', f'SALVAGE_SHA="{chosen}"')
    sentinel = tmp_path / "approval-reached"
    result = run(block + f'\nprintf reached > "{sentinel}"\n')
    if selection in ("invalid", "nonancestor"):
        assert result.returncode != 0
        assert not sentinel.exists(), "failed declaration must stop before approval"
        assert record.read_text() == record_before
        return
    assert result.returncode == 0, result.stdout + result.stderr
    assert sentinel.exists()
    if selection == "ancestor":
        assert f"- Salvage:           {ancestor}" in record.read_text()
    else:
        assert record.read_text() == record_before, "no selection must make no helper call"
        assert not result.stdout and not result.stderr, "no declaration output when nothing preserved"
    with record.open("a") as stream:
        stream.write("\n- Approval: granted\n- Approver: fixture-owner\n"
                     "\n### Section C - the approved plan\n1. `saved.txt` - owned preservation\n")
    approved = run(APPROVE)
    assert approved.returncode in (0, 4), approved.stdout + approved.stderr
    assert "baseline stamped" in approved.stdout
    assert (repo / "saved.txt").read_bytes() == preserved
