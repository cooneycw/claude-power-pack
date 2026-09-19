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

`/cpp:update` (issue #1056) carries a DIFFERENT rule, below, and the difference
is deliberate rather than an inconsistency. It runs in the MAIN checkout, where
a stash is legitimate - the flow docs' "no executable stash at all" rule does
not fit it and imposing one would force a worse change. What is forbidden there
is the verb that takes a stranger's entry: `git stash pop` resolves to whatever
is on top of the shared stack, which with concurrent sessions is routinely
somebody else's work. The safe restore names OUR entry by the SHA captured at
push time, so the pin also REQUIRES that pattern rather than only forbidding the
bad one - a prohibition alone would pass a file that stopped restoring at all,
which is the exact state #1056 found (pushed, never popped, orphaned for 16
days).
"""

from __future__ import annotations

import re
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


CPP_UPDATE_DOC = ROOT / ".claude" / "commands" / "cpp" / "update.md"


#: A `git stash <verb>` INVOCATION anywhere in an executable line, not only at
#: its start. The first cut of this detector anchored on `part.strip()
#: .startswith(...)`, which reads `if git stash pop; then` as clean - the exact
#: spelling the fixed document would most plausibly regress to, since the block
#: it guards is written as `if git stash apply "$SHA"; then`.
#:
#: TWO POPULATIONS ARE NARROWED, AND BOTH NARROWINGS ARE THE POINT:
#:
#:   fenced blocks only  - `update.md` is prose around ```bash blocks, and only
#:                         the blocks are executable. Prose naming the forbidden
#:                         command is how this file explains the rule.
#:   quoted text masked  - `echo "Avoid this; git stash pop"` is a line that
#:                         PRINTS the words. Splitting on `;` without respecting
#:                         quotes read it as an invocation, and the mirror-image
#:                         error let `echo "... git stash apply $STASH_SHA"` in
#:                         the recovery message satisfy the restore check while
#:                         nothing restored.
#:
#: Both were found by the counter-model review on this branch and are committed
#: as cases in `test_pop_detector_*`, so neither can come back quietly.
_SHELL_LEAD = re.compile(
    r"^(?:!\s*|if\s+|elif\s+|then\s+|else\s+|while\s+|until\s+|do\s+|"
    r"\{\s*|\(\s*|time\s+|command\s+|eval\s+)+"
)
_QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'")


def _code_lines(text: str) -> list[str]:
    """Only the lines inside ``` fences - the executable population."""
    out, inside = [], False
    for raw in text.splitlines():
        if raw.lstrip().startswith("```"):
            inside = not inside
            continue
        if inside:
            out.append(raw)
    return out


def _invokes(line: str, verb: str) -> bool:
    """Does this line EXECUTE `git stash <verb>`, allowing shell lead-ins?

    Quoted STRING CONTENT is masked before splitting, so text a line merely
    prints is never read as a command.
    """
    if line.strip().startswith("#"):
        return False
    masked = _QUOTED.sub(lambda m: '"' + "\x00" * max(len(m.group(0)) - 2, 0) + '"', line)
    for sep in ("&&", ";", "||", "|"):
        masked = masked.replace(sep, "\n")
    return any(
        _SHELL_LEAD.sub("", part.strip()).startswith(f"git stash {verb}")
        for part in masked.split("\n")
    )


def test_cpp_update_never_pops_the_shared_stack() -> None:
    """#1056: `/cpp:update` may stash in the main checkout; it may never `pop`.

    A bare pop takes top-of-stack, not your entry. On 2026-09-19 a worker's pop
    restored 67 lines of a different session's in-progress work and lost its own.
    """
    hits = [raw for raw in _code_lines(CPP_UPDATE_DOC.read_text()) if _invokes(raw, "pop")]
    assert not hits, (
        f"{CPP_UPDATE_DOC}: executable `git stash pop` reintroduces the #1056 "
        f"shared-stack race - restore by SHA with `git stash apply` instead:\n"
        + "\n".join(hits)
    )


def test_pop_detector_catches_an_if_prefixed_pop() -> None:
    """Committed case for the detector itself (counter-model finding, this branch).

    A detector that only matches at the start of a line cannot see the one
    spelling this document would actually regress to. These two assertions are
    what separate the fixed detector from the one that shipped green over
    `if git stash pop; then`.
    """
    assert _invokes('  if git stash pop; then', "pop")
    assert _invokes('  git stash pop', "pop")
    assert _invokes('  foo && git stash pop', "pop")
    assert not _invokes('  # never use git stash pop here', "pop")
    assert not _invokes('a sentence mentioning git stash pop in prose', "pop")
    # Counter-model cases: quoted text is PRINTED, not executed.
    assert not _invokes('  echo "Avoid this; git stash pop"', "pop")
    assert not _invokes('  echo "Recovery: git stash apply $STASH_SHA"', "apply")
    # ... and masking a quoted argument must not hide the command itself.
    assert _invokes('  if git stash apply "$STASH_SHA"; then', "apply")


def test_cpp_update_restores_what_it_sets_aside() -> None:
    """The other half: forbidding `pop` alone would pass a file that never restores.

    That is not hypothetical - it is the state #1056 found. `/cpp:update` pushed
    an entry on 2026-09-03 and had no restore step at all, leaving it unclaimed
    on the shared stack for sixteen days.

    The restore must be an EXECUTABLE `git stash apply`, not the string appearing
    somewhere in the file: the recovery instructions this document prints on a
    failed apply contain that text too, so a substring check over the whole file
    would accept a document that stopped restoring and merely still explained how
    to (counter-model finding, this branch).
    """
    applies = [raw for raw in _code_lines(CPP_UPDATE_DOC.read_text()) if _invokes(raw, "apply")]
    assert applies, (
        f"{CPP_UPDATE_DOC}: no EXECUTABLE `git stash apply` - work set aside is "
        f"never restored (#1056)"
    )
    # The APPLY must receive the captured SHA. A bare `git stash apply` restores
    # top-of-stack, which is the very thing the SHA exists to avoid - and the
    # earlier form of this assertion ("STASH_SHA" appears somewhere in the file)
    # passed that mutation, because the recovery message mentions the variable
    # too (counter-model finding, this branch).
    assert any("STASH_SHA" in raw for raw in applies), (
        f"{CPP_UPDATE_DOC}: `git stash apply` does not receive the captured SHA, so "
        f"the restore takes top-of-stack - a sibling's entry (#1056):\n"
        + "\n".join(applies)
    )


def test_clean_tree_seam_is_documented() -> None:
    """Condition from the #635 gate: the downstream commit step must treat an
    already-clean tree (work riding the WIP snapshot) as legitimate."""
    for doc in FLOW_DOCS[:2]:
        text = doc.read_text()
        assert "LEGITIMATE state, not a failure" in text, (
            f"{doc}: missing the already-committed seam note (#635 condition 1)"
        )
