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


def finish_after_publication(step: str) -> bool:
    """A single documented call follows push and PR creation, before completion."""
    push = 'git push -u origin "$BRANCH"'
    create = "gh pr create "
    complete = "Report: `Step 7/8: Finish complete"
    if step.count(CALL) != 1 or not all(s in step for s in (push, create, complete)):
        return False
    return step.index(push) < step.index(create) < step.index(CALL) < step.index(complete)


@pytest.mark.parametrize("driver", ("codex", "qwen", "gemma"))
def test_actual_driver_finishes_only_after_publishing_the_pr(driver: str) -> None:
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    step = text.split("### Step 7: Finish", 1)[1].split("### Step 8:", 1)[0]
    assert finish_after_publication(step), f"{driver}: finish must follow push and PR creation"
    assert text.count(CALL) == 1
    early = step.split("1. **Commit**", 1)[0]
    assert 'flow-plan-record.py compliance 42 --base "$MERGE_BASE"' in early
    assert "The compliance call stays in the SAME shell block" in early


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
