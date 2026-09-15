"""The cross-model review diffs against the MERGE BASE, not a moving tip (#927).

`/codex:code_review` built its diff with `git diff "$BASE"` where `$BASE` is
`origin/<default>` - and it is refreshed by a `git fetch` two lines earlier, so
it is the tip AT REVIEW TIME rather than the point the branch was cut. Any
commit that lands on the base after the branch exists therefore appears in the
review diff INVERTED: a sibling PR's additions render as this author's
deletions.

MEASURED, not hypothesised. A reviewer handed such a diff returned three
confident MEDIUM findings against a file the author had never touched, each an
accurate description of reverting someone else's merged work. Acting on them
would have landed a real regression.

WHY THE EXECUTED CONTROL AND NOT A TEXT ASSERTION. This instrument's failure
mode is that it emits a CONFIDENT finding, so "it produced output" proves
nothing. The control builds a repository where the base genuinely advances past
the branch point and requires the PRE-FIX form to reproduce the artifact. If the
red case does not reproduce it, the hazard has not been captured and the green
case is worthless.

WHAT THIS DOES NOT COVER, stated because agreement between diff forms otherwise
reads as confirmation: this corrects the reviewer's RANGE. It cannot see a
commit whose TREE PREDATES ITS PARENT - `git reset --soft` onto an advanced
origin/main puts new main as parent with the old tree as content, the merge base
then IS origin/main, and every diff form agrees while all of them are wrong
together. For that, compare `git diff --name-only origin/main` against your own
file set before pushing. That mechanism is issue #985 and deliberately has no
case here.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
COMMAND = REPO / ".claude" / "commands" / "codex" / "code_review.md"


def test_the_command_diffs_against_a_merge_base() -> None:
    text = COMMAND.read_text(encoding="utf-8")
    assert "git merge-base HEAD" in text, (
        "code_review.md no longer resolves a merge base; a two-dot diff against "
        "a refreshed BASE renders a sibling's additions as this author's deletions"
    )
    # The bare two-dot form must not be what builds the reviewed diff.
    offenders = [
        ln for ln in text.splitlines()
        if re.match(r'^\s*git diff (--stat )?"\$BASE"\s*(>|$)', ln)
    ]
    assert not offenders, f"a bare two-dot diff against $BASE is still used: {offenders}"


def test_the_command_states_what_the_fix_does_not_cover() -> None:
    """The caveat is load-bearing and is asserted so it cannot quietly go.

    Someone who applies this fix, sees two-dot and three-dot agree, and
    concludes they are safe would ship a revert with MORE confidence than
    before. A remedy that narrows the reader's sense of the hazard while
    appearing to close it is the defect class this repository is working on.
    """
    text = COMMAND.read_text(encoding="utf-8")
    assert "PREDATES ITS PARENT" in text, (
        "code_review.md no longer says the range fix cannot see a commit whose "
        "tree predates its parent"
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required to build the fixture")
def test_the_prefix_form_reproduces_the_artifact_and_the_fixed_form_does_not(
    tmp_path: Path,
) -> None:
    """TWO-SIDED, on a repository where the base genuinely advances.

    RED  the pre-fix command must attribute the sibling's line to this author.
    GREEN the fixed command must attribute none of it.
    """
    def git(*args: str, cwd: Path) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
            # PATH is pinned for git-env isolation, not to construct an absence.
            # The negative condition this test depends on - that the branch does
            # not contain the sibling's line - is asserted explicitly in the body
            # below, and git's availability is covered by the skipif guard.
            # negative-fixture: allow PATH is isolation, not an absence
            env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin",
                 "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
        ).stdout

    upstream = tmp_path / "upstream.git"
    upstream.mkdir()
    git("init", "-q", "--bare", cwd=upstream)

    work = tmp_path / "work"
    work.mkdir()
    git("init", "-q", "-b", "main", cwd=work)
    git("remote", "add", "origin", str(upstream), cwd=work)
    (work / "shared.txt").write_text("line1\nline2\n", encoding="utf-8")
    git("add", "-A", cwd=work)
    git("commit", "-qm", "base", cwd=work)
    git("push", "-q", "origin", "main", cwd=work)

    # This author's branch, cut here.
    git("checkout", "-q", "-b", "mine", cwd=work)
    (work / "mine.txt").write_text("my own addition\n", encoding="utf-8")
    git("add", "-A", cwd=work)
    git("commit", "-qm", "my work", cwd=work)

    # A SIBLING lands on the base afterwards.
    sib = tmp_path / "sib"
    sib.mkdir()
    git("clone", "-q", str(upstream), str(sib / "c"), cwd=sib)
    clone = sib / "c"
    # The bare upstream's HEAD names whatever init.defaultBranch was, which need
    # not be the branch actually pushed - so the clone can land with nothing
    # checked out and a later push fails with "src refspec main does not match
    # any". Pin the branch explicitly rather than inheriting a host default.
    git("checkout", "-q", "-B", "main", "origin/main", cwd=clone)
    (clone / "shared.txt").write_text("line1\nline2\nSIBLING FEATURE LINE\n", encoding="utf-8")
    git("add", "-A", cwd=clone)
    git("commit", "-qm", "sibling feature", cwd=clone)
    git("push", "-q", "origin", "main", cwd=clone)
    git("fetch", "-q", "origin", cwd=work)

    # Precondition: this branch genuinely does not contain the sibling's line.
    assert "SIBLING" not in (work / "shared.txt").read_text(encoding="utf-8")

    pre_fix = git("diff", "origin/main", cwd=work)
    assert "-SIBLING FEATURE LINE" in pre_fix, (
        "the RED case did not reproduce the artifact, so this control does not "
        "capture the hazard and its green half proves nothing"
    )

    merge_base = git("merge-base", "HEAD", "origin/main", cwd=work).strip()
    fixed = git("diff", merge_base, cwd=work)
    assert "SIBLING" not in fixed, (
        f"the fixed form still attributes a sibling line:\n{fixed}"
    )
    assert "my own addition" in fixed, "the fixed form lost this author's own change"


def test_a_failed_merge_base_does_not_become_an_empty_clean_review() -> None:
    """Codex, MEDIUM: the failure mode of the fix itself.

    If `git merge-base` fails - valid refs, no locally discoverable ancestor, as
    in a shallow clone - MERGE_BASE is empty, both diffs fail, and $DIFF_FILE is
    left EMPTY. The next instruction reads an empty diff as "nothing to review"
    and exits 0, so a review that never ran reports clean. That is this
    command's own failure class pointed at its own input.
    """
    text = COMMAND.read_text(encoding="utf-8")
    assert "no common ancestor" in text, (
        "code_review.md does not handle a failed merge-base resolution, so an "
        "unresolvable base yields an empty diff read as 'nothing to review'"
    )
    assert re.search(r"if ! MERGE_BASE=|\[ -z \"\$MERGE_BASE\" \]", text), (
        "the merge-base resolution is not checked before the diff is taken"
    )
