"""A project whose own gate needs the pushed head: push first, then gate (#1706).

`/flow:auto` Step 6 and `/flow:finish` run the finish gate before `git push`.
A project gate that clones the ref under test from the remote (Kyle's
ci-shape-check) refused the unpushed commit, and neither document said what to
do. Both now carry one sentence, and the order itself is unchanged.

What these tests can say: the sentence is present, in the gate step, before the
first push, in both documents and in both generated Codex skills. What they
cannot say: whether an agent reading it pushes first. That is a model's
behaviour and nothing here measures it.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
COMMANDS = REPO / ".claude" / "commands" / "flow"

SENTENCE = (
    "If the project's gate needs the pushed head (it refuses an unpushed commit), "
    'commit and `git push -u origin "$BRANCH"` first, then gate'
)
GATE_CALL = "~/.claude/scripts/flow-finish-gate.sh\n"
PUSH_STEP = 'git push -u origin "$BRANCH"\n'  # the push STEP's own command line, not the sentence
NO_VERDICT_STOP = "A run with no `FLOW_FINISH_GATE:` verdict line did not run the gate"


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text)


@pytest.mark.parametrize("name", ["auto.md", "finish.md"])
def test_the_document_says_what_to_do_when_the_gate_needs_the_pushed_head(name: str) -> None:
    text = (COMMANDS / name).read_text(encoding="utf-8")
    assert normalized(text).count(SENTENCE) == 1, f"flow/{name} does not carry the pushed-head sentence exactly once"


@pytest.mark.parametrize("name", ["auto.md", "finish.md"])
def test_the_sentence_sits_in_the_gate_step_before_the_first_push(name: str) -> None:
    """Anywhere else it is advice nobody reads at the moment the gate goes red."""
    text = (COMMANDS / name).read_text(encoding="utf-8")
    sentence_at = text.index("needs the pushed head")
    gate_at = text.index(GATE_CALL)
    stop_at = text.index(NO_VERDICT_STOP)
    push_at = text.index(PUSH_STEP)
    assert gate_at < sentence_at < stop_at, f"flow/{name}: the sentence is outside the gate step"
    assert sentence_at < push_at, f"flow/{name}: the sentence comes after the push it is about"


@pytest.mark.parametrize("name", ["auto.md", "finish.md"])
def test_the_default_order_is_still_gate_then_push(name: str) -> None:
    """#1706 documents an exception. It must not have reordered the default."""
    text = (COMMANDS / name).read_text(encoding="utf-8")
    assert text.index(GATE_CALL) < text.index(PUSH_STEP), f"flow/{name}: the push now precedes the gate"


def test_the_rationale_says_why_the_order_stays() -> None:
    text = normalized((REPO / "docs" / "reference" / "flow-auto-rationale.md").read_text(encoding="utf-8"))
    assert "Why the gate runs before the push, and the one exception (issue #1706)" in text
    assert "would publish commits nothing has verified yet" in text


def test_the_trimmed_text_is_recorded() -> None:
    text = normalized((REPO / "docs" / "commands-reference.md").read_text(encoding="utf-8"))
    assert "Text moved out of `/flow:auto` and `/flow:finish` (#1706)" in text
    assert "used to share exit 0" in text
    assert "blocking in a worktree since #1258" in text
    assert "(`make lint`, `make test`, `make typecheck`, `make verify`)" in text


@pytest.mark.parametrize("skill", ["flow-auto", "flow-finish"])
def test_the_generated_codex_skill_carries_the_sentence(tmp_path: Path, skill: str) -> None:
    out = tmp_path / "codex-skills"
    built = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "codex-skill-sync.py"), "--write", "--output-root", str(out)],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    files = [out / skill / name for name in ("SKILL.md", "reference.md") if (out / skill / name).is_file()]
    assert files, f"the build produced no {skill} skill - this test read nothing"
    text = normalized("".join(f.read_text(encoding="utf-8") for f in files))
    assert SENTENCE in text
