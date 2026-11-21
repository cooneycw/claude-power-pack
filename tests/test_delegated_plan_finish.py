"""Delegated finish checks the published PR, not an earlier local checkpoint.

These are documented-procedure checks, not evidence of live driver execution.
The committed Step 7 render excerpts exercise missing, premature and correct
calls; actual generated command documents are inspected separately.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/delegated-plan-finish"
CALL = "~/.claude/scripts/flow-plan-record.py finish 42"


def bash_blocks(text: str) -> list[list[tuple[int, str]]]:
    """Read literal active lines in these documents' bash fences, not general shell."""
    blocks: list[list[tuple[int, str]]] = []
    active = False
    for number, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if line == "```bash":
            active = True
            blocks.append([])
        elif line == "```":
            active = False
        elif active and line and not line.startswith("#"):
            blocks[-1].append((number, line))
    return blocks


def compliance_with_base(step: str) -> bool:
    early = step.split("1. **Commit**", 1)[0]
    call = '~/.claude/scripts/flow-plan-record.py compliance 42 --base "$MERGE_BASE"'
    for block in bash_blocks(early):
        for index, (_, line) in enumerate(block):
            if line == call:
                return any("MERGE_BASE=$(git merge-base" in previous for _, previous in block[:index])
    return False


def finish_after_publication(step: str) -> bool:
    """A single documented call follows push and PR creation, before completion."""
    push = 'git push -u origin "$BRANCH"'
    create = "gh pr create "
    complete = "Report: `Step 7/8: Finish complete"
    commands = [entry for block in bash_blocks(step) for entry in block]
    pushes = [number for number, line in commands if line == push]
    creates = [number for number, line in commands if line.startswith(create)]
    finishes = [number for number, line in commands if line == CALL]
    reports = [number for number, line in enumerate(step.splitlines()) if line.startswith(complete)]
    if not all(len(matches) == 1 for matches in (pushes, creates, finishes, reports)):
        return False
    return pushes[0] < creates[0] < finishes[0] < reports[0]


@pytest.mark.parametrize("driver", ("codex", "qwen", "gemma"))
def test_actual_driver_finishes_only_after_publishing_the_pr(driver: str) -> None:
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    step = text.split("### Step 7: Finish", 1)[1].split("### Step 8:", 1)[0]
    assert finish_after_publication(step), f"{driver}: finish must follow push and PR creation"
    assert text.count(CALL) == 1
    early = step.split("1. **Commit**", 1)[0]
    assert 'flow-plan-record.py compliance 42 --base "$MERGE_BASE"' in early
    assert "The compliance call stays in the SAME shell block" in early
    assert compliance_with_base(step)


@pytest.mark.parametrize("driver", ("codex", "qwen", "gemma"))
def test_actual_driver_distinguishes_each_finish_verdict(driver: str) -> None:
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    heading = "4. **Close the plan record after push and PR creation:**"
    assert heading in text, f"{driver}: missing published-plan check and its verdict handling"
    close = text.split(heading, 1)[1]
    close = close.split("Report: `Step 7/8:", 1)[0]
    for instruction in (
        "Read every verdict, not only the combined exit",
        "`ISSUE_DRIFT: clean`",
        "`drift` prints changed issue bytes",
        "resolve under existing",
        "authority and explain in the PR",
        "`unresolved` means unchecked, never clean",
        "Relay compliance/stability and lane verdicts as above",
        "never rewrite approval",
        "`FLOW_PLAN_RECORD: present` proceeds",
        "`absent` STOP",
        "commit/push this run's record, rerun",
        "`unverified` STOP",
        "check authentication",
        "and network, rerun",
        "Neither permits cleanup/merge",
    ):
        assert instruction in close, f"{driver}: lost {instruction}"


@pytest.mark.parametrize(
    ("name", "expected"),
    (("missing-finish", False), ("finish-before-pr", False), ("good-finish", True)),
)
def test_committed_render_controls(name: str, expected: bool) -> None:
    step = (FIXTURES / f"{name}.md").read_text()
    if name == "missing-finish":
        assert CALL not in step
    elif name == "finish-before-pr":
        assert step.count(CALL) == 1
        assert step.index(CALL) < step.index("gh pr create ")
    else:
        assert step.count(CALL) == 1
        assert step.index("gh pr create ") < step.index(CALL)
    assert finish_after_publication(step) is expected


@pytest.mark.parametrize("name", ("commented-finish", "commented-pr"))
def test_commented_commands_cannot_establish_publication_order(name: str) -> None:
    step = (FIXTURES / f"{name}.md").read_text()
    disabled = "# " + (CALL if name == "commented-finish" else "gh pr create ")
    assert disabled in step
    assert not finish_after_publication(step)


@pytest.mark.parametrize("driver", ("codex", "qwen", "gemma"))
def test_deferred_acceptance_items_remain_explicit(driver: str) -> None:
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    assert "Record deferred items too." in text


def test_split_shell_cannot_supply_compliance_base() -> None:
    step = (FIXTURES / "split-compliance.md").read_text()
    assert '```bash\n~/.claude/scripts/flow-plan-record.py compliance' in step
    assert "MERGE_BASE=$(git merge-base" in step
    assert not compliance_with_base(step)
