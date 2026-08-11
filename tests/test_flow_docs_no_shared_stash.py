"""Pin: the flow docs never touch the shared stash stack (issue #635).

Git stashes live in the repo's COMMON git dir, so every linked worktree shares
one stack. `/flow:auto` Step 6 and `/flow:finish` used to do
`stash push -u -> merge -> bare stash pop`; with concurrent sessions the pops
took whatever was top-of-stack and silently swapped uncommitted work between
worktrees (two confirmed symmetric hits plus a near-miss, aws-learn
2026-08-05). The fix is commit-first: WIP-commit the work, merge on the clean
tree, let the squash flatten the snapshot.

This is a doc-content pin because the regression already happened once as a
doc edit: #521 installed the stash dance as a FIX (for merge-order inversion),
and #635 is its residue. A future editor solving a merge-order problem must
not be able to quietly reintroduce the shared-stack race.

Comments MAY mention `git stash` (the blocks explain why it is forbidden);
only an executable stash line - a line whose code content starts with or
chains into `git stash` - fails the pin.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FLOW_DOCS = [
    ROOT / ".claude" / "commands" / "flow" / "auto.md",
    ROOT / ".claude" / "commands" / "flow" / "finish.md",
]


def _executable_stash_lines(text: str) -> list[str]:
    hits: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            continue  # explanatory comment - allowed to name the forbidden pattern
        code = line
        # Also catch chained forms: `foo && git stash pop`, `foo; git stash push`.
        for sep in ("&&", ";", "||", "|"):
            for part in code.split(sep):
                if part.strip().startswith("git stash"):
                    hits.append(raw)
    return hits


@pytest.mark.parametrize("doc", FLOW_DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_executable_stash_in_flow_docs(doc: Path) -> None:
    hits = _executable_stash_lines(doc.read_text())
    assert not hits, (
        f"{doc}: executable `git stash` line(s) reintroduce the #635 shared-stack "
        f"race - use the commit-first pattern (wip(flow): pre-merge snapshot):\n"
        + "\n".join(hits)
    )


def test_commit_first_pattern_present() -> None:
    for doc in FLOW_DOCS[:2]:
        text = doc.read_text()
        assert 'git commit -m "wip(flow): pre-merge snapshot"' in text, (
            f"{doc}: the commit-first stale-base pattern (#635) is missing"
        )


def test_clean_tree_seam_is_documented() -> None:
    """Condition from the #635 gate: the downstream commit step must treat an
    already-clean tree (work riding the WIP snapshot) as legitimate."""
    for doc in FLOW_DOCS[:2]:
        text = doc.read_text()
        assert "LEGITIMATE state, not a failure" in text, (
            f"{doc}: missing the already-committed seam note (#635 condition 1)"
        )
