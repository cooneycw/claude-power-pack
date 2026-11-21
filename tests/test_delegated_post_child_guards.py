"""The parent checks child edits before its first checkpoint and shipping commit."""

import re
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests/fixtures/delegated-post-child"
WORKTREE = "~/.claude/scripts/flow-worktree-guard.sh --strict"
IGNORED = "~/.claude/scripts/check-ignored-additions.sh"
CHECKPOINT = "Commit the implementation checkpoint"
SHIP = "Commit the changes"
FIX_RETURN = "Child returned; parent checks before reading the fix payload."


def active_steps(document: str) -> dict[int, str]:
    """Read active Markdown sections, keeping code/prose order and dropping comments."""
    steps: dict[int, list[str]] = {}
    current = None
    tokens = MarkdownIt("commonmark").parse(document)
    for i, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h3":
            title = tokens[i + 1].content
            current = next((n for n in (4, 5, 6, 7) if title.startswith(f"Step {n}:")), None)
            if current is not None:
                steps[current] = []
        if current is None:
            continue
        if token.type == "inline":
            steps[current].append("".join(child.content for child in token.children or []
                                          if child.type in {"text", "code_inline"}))
        elif token.type == "fence" and token.info == "bash":
            code = "\n".join(line.strip() for line in token.content.splitlines()
                             if not line.lstrip().startswith("#"))
            steps[current].append("\0" + code + "\0")  # Separate tool calls cannot share $?.
    return {n: "\n".join(lines) for n, lines in steps.items()}


def guard_contract(document: str) -> bool:
    steps = active_steps(document)
    initial = steps.get(4, "")
    capture = re.search(r"(?m)^(?:CODEX|QWEN|GEMMA)_EXIT=\$\?\n", initial)
    if capture is None or not initial[capture.end():].startswith(WORKTREE + "\n"):
        return False
    for number, boundary in ((5, CHECKPOINT), (6, "Re-run quality gates"), (7, SHIP)):
        section = steps.get(number, "")
        if WORKTREE not in section or boundary not in section:
            return False
        if section.index(WORKTREE) >= section.index(boundary):
            return False
        guard = re.search(re.escape(WORKTREE) + r"\ncase \$\? in\n([^\0]*?)\nesac", section, re.DOTALL)
        if guard is None:
            return False
        if number == 5 and not initial[capture.end():].startswith(guard[0]):
            return False
        if '3) echo "STOP: leaked edits; inspect and attribute before reverting main"; exit 3 ;;' not in guard[1]:
            return False
        if '4|5) echo "Report the guard verdict above; no clean-main claim" ;;' not in guard[1]:
            return False
        if number == 6:
            if FIX_RETURN not in section or section.index(FIX_RETURN) > section.index(WORKTREE):
                return False
            if "_FIX_EXIT=$?" not in section or section.index("_FIX_EXIT=$?") > section.index(WORKTREE):
                return False
            payload = "~/.claude/scripts/delegated-run-check.sh"
            if payload not in section or section.index(payload) < section.index(WORKTREE):
                return False
            if "tail -40" in section and section.index("tail -40") < section.index(WORKTREE):
                return False
        else:
            if IGNORED not in section or section.index(IGNORED) >= section.index(boundary):
                return False
            ignored = re.search(re.escape(IGNORED) + r"\ncase \$\? in\n([^\0]*?)\nesac", section, re.DOTALL)
            if (ignored is None
                    or '3) echo "STOP: inspect ignored additions before committing"; exit 3 ;;' not in ignored[1]):
                return False
    return True


@pytest.mark.parametrize("driver", ("codex", "qwen", "gemma"))
def test_actual_render_checks_each_child_and_precommit_boundary(driver: str) -> None:
    document = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    assert guard_contract(document), f"{driver}: post-child/precommit guard missing or late"


@pytest.mark.parametrize(
    "case", ("good", "missing-call", "after-first-commit", "overwritten-status", "overwritten-ignored-status",
             "split-worktree-fence", "split-ignored-fence"),
)
def test_committed_placement_cases(case: str) -> None:
    document = (CASES / f"{case}.md").read_text()
    if case in {"split-worktree-fence", "split-ignored-fence"}:
        command = WORKTREE if case == "split-worktree-fence" else IGNORED
        assert command + "\n```\n\n```bash\ncase $?" in document
    elif case == "missing-call":
        assert WORKTREE not in active_steps(document)[5]
    elif case == "overwritten-ignored-status":
        assert IGNORED + "\necho done\ncase $?" in document
    elif case == "overwritten-status":
        assert WORKTREE + "\necho done\ncase $?" in document
    elif case == "after-first-commit":
        step = active_steps(document)[5]
        assert step.index(CHECKPOINT) < step.index(WORKTREE)
    assert guard_contract(document) is (case == "good")


def test_commented_calls_do_not_establish_guards() -> None:
    good = (CASES / "good.md").read_text()
    assert guard_contract(good)
    assert not guard_contract(good.replace(WORKTREE, "# " + WORKTREE))


@pytest.mark.parametrize("driver", ("codex", "qwen", "gemma"))
def test_initial_child_boundary_precedes_payload(driver: str) -> None:
    document = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    initial = active_steps(document)[4]
    capture = re.search(r"(?m)^(?:CODEX|QWEN|GEMMA)_EXIT=\$\?\n", initial)
    assert capture is not None
    assert initial[capture.end():].startswith(WORKTREE + "\n")


def test_initial_guard_blocks_are_identical() -> None:
    blocks = []
    for driver in ("codex", "qwen", "gemma"):
        text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
        initial = active_steps(text)[4]
        match = re.search(re.escape(WORKTREE) + r"\ncase \$\? in\n[^\0]*?\nesac", initial, re.DOTALL)
        assert match is not None
        blocks.append(match[0])
    assert blocks[0] == blocks[1] == blocks[2]
