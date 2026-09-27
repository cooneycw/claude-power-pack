"""/codex:auto takes its sandbox mode from the caller, as data (issue #1285).

Inside a Kyle session container codex's own sandbox cannot start: bubblewrap
needs a user namespace that Docker's default seccomp refuses. A hard-coded
`--sandbox workspace-write` then makes codex exit 0 having executed nothing
(kyle#1396), and it overrides any config.toml the container writes. So the
caller supplies CODEX_AUTO_SANDBOX, and both invocations read it.

These tests EXECUTE the guard as the document ships it - extracted from the
rendered command file, not copied - so a guard that moves or breaks fails
here instead of silently ceasing to be covered. Hermetic and git-free.
"""

from __future__ import annotations

import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUTO = ROOT / ".claude" / "commands" / "codex" / "auto.md"

_GUARD = re.compile(
    r'^( *)CODEX_SANDBOX="\$\{CODEX_AUTO_SANDBOX:-workspace-write\}"\n.*?^\1esac\n',
    re.M | re.S,
)


def _guards() -> list[str]:
    return [textwrap.dedent(m.group(0)) for m in _GUARD.finditer(AUTO.read_text())]


def _run(guard: str, value: str | None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "CODEX_AUTO_SANDBOX"}
    if value is not None:
        env["CODEX_AUTO_SANDBOX"] = value
    return subprocess.run(
        ["bash", "-c", guard + 'echo "SANDBOX=$CODEX_SANDBOX"'],
        env=env, capture_output=True, text=True, timeout=30,
    )


_FENCE = re.compile(r"^( *)```bash\n(.*?)^\1```$", re.M | re.S)


def _execution_blocks(text: str) -> list[str]:
    """The fenced blocks that RUN codex against the worktree - Step 4 and the
    fix loop - identified by the invocation itself, not by counting fragments
    across the whole document (counter-model review, #1285)."""
    return [
        textwrap.dedent(m.group(2))
        for m in _FENCE.finditer(text)
        if re.search(r"^codex exec \\\n(?:\s+--?\S.*\\\n)*?\s+-C \"\$WORKTREE_PATH\"",
                     textwrap.dedent(m.group(2)), re.M)
    ]


def _check(block: str) -> None:
    guard = _GUARD.search(block)
    invocation = block.find("codex exec")
    assert guard, "execution block carries no sandbox guard"
    assert guard.end() <= invocation, "guard must run before the invocation"
    command = _invocation(block[invocation:])
    assert re.search(r'^\s+--sandbox "\$CODEX_SANDBOX" \\$', command, re.M)
    assert not re.search(r"^\s+--sandbox (?!\"\$CODEX_SANDBOX\")", command, re.M)


def _invocation(text: str) -> str:
    """The one shell command starting at *text*: its backslash-continued lines
    and no further, so a flag on a LATER command cannot be borrowed (review)."""
    lines = []
    for line in text.splitlines():
        lines.append(line)
        if not line.rstrip().endswith("\\"):
            break
    return "\n".join(lines)


def test_both_execution_blocks_take_the_sandbox_from_the_guard():
    # Step 4 and the fix loop. One guard would leave a retry inert in a
    # container after the first run worked, which reads as a flaky fix.
    blocks = _execution_blocks(AUTO.read_text())
    assert len(blocks) == 2
    for block in blocks:
        _check(block)


def test_an_unrelated_example_does_not_move_the_verdict():
    """Control: a prose example elsewhere is not an execution block."""
    extra = "\n```bash\n# history\ncodex exec --sandbox workspace-write x\n```\n"
    blocks = _execution_blocks(AUTO.read_text() + extra)
    assert len(blocks) == 2


def test_a_hard_coded_invocation_is_caught():
    """Red case: the pre-#1285 shape fails _check even with the guard present."""
    block = _execution_blocks(AUTO.read_text())[0]
    with pytest.raises(AssertionError):
        _check(block.replace('--sandbox "$CODEX_SANDBOX"', "--sandbox workspace-write"))


def test_a_flag_on_a_later_command_is_not_borrowed():
    """Red case: the flag moved off codex exec onto a following command."""
    block = _execution_blocks(AUTO.read_text())[0]
    moved = block.replace('    --sandbox "$CODEX_SANDBOX" \\\n', "", 1)
    assert moved != block, "precondition: the flag was removed from codex exec"
    moved += 'echo \\\n    --sandbox "$CODEX_SANDBOX" \\\n    done\n'
    assert '--sandbox "$CODEX_SANDBOX"' in moved
    with pytest.raises(AssertionError):
        _check(moved)


def test_removing_the_invocations_is_caught():
    """Red case: guards alone, with no codex exec, must not pass as coverage."""
    text = AUTO.read_text().replace("codex exec \\\n", "true \\\n")
    assert _execution_blocks(text) == []


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "workspace-write"),  # unset: #735's fence, exactly as before
        ("", "workspace-write"),
        ("workspace-write", "workspace-write"),
        ("danger-full-access", "danger-full-access"),  # what Kyle supplies
    ],
)
def test_accepted_values(index, value, expected):
    result = _run(_guards()[index], value)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == f"SANDBOX={expected}"


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("value", ["read-only", "danger", "workspace-write "])
def test_any_other_value_is_refused_not_defaulted(index, value):
    """The red case: a guard that defaulted instead would print SANDBOX=."""
    result = _run(_guards()[index], value)
    assert result.returncode == 1
    # The success line, anchored: the error message itself names the variable.
    assert not re.search(r"^SANDBOX=", result.stdout, re.M)
    assert "CODEX_AUTO_SANDBOX" in result.stdout
