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

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.isolated_env import ISOLATED_PATH

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
            env={"HOME": str(tmp_path), "PATH": ISOLATED_PATH,
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


# ---------------------------------------------------------------------------
# Issue #1030, defect 1: a brand-new, never-`git add`ed file is invisible to
# `git diff <ref>`. A change whose whole content is one or more new files
# therefore hands the reviewer a diff that omits the change entirely, and
# "no findings" then means nothing.
# ---------------------------------------------------------------------------


def test_the_command_stages_untracked_files_before_diffing() -> None:
    text = COMMAND.read_text(encoding="utf-8")
    assert re.search(r"git add -N \.", text), (
        "code_review.md no longer stages untracked files as intent-to-add "
        "before diffing, so a brand-new file is invisible to the review"
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required to build the fixture")
def test_a_new_untracked_file_is_invisible_without_intent_to_add_and_visible_with_it(
    tmp_path: Path,
) -> None:
    """RED/GREEN for defect 1.

    RED: a plain `git diff <base>` never mentions a file nobody staged - this
    is the artifact the fix exists to remove, reproduced directly rather than
    assumed.
    GREEN: `git add -N .` (intent-to-add) is enough to make the same `git
    diff <base>` show the file as a real addition, with its full content.
    """
    def git(*args: str, cwd: Path) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
            # negative-fixture: allow PATH is isolation, not an absence
            env={"HOME": str(tmp_path), "PATH": ISOLATED_PATH,
                 "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
        ).stdout

    work = tmp_path / "work"
    work.mkdir()
    git("init", "-q", "-b", "main", cwd=work)
    (work / "base.txt").write_text("base\n", encoding="utf-8")
    git("add", "-A", cwd=work)
    git("commit", "-qm", "base", cwd=work)
    base_sha = git("rev-parse", "HEAD", cwd=work).strip()

    # This author's whole change: one brand-new file, never staged.
    (work / "new_module.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    pre_fix = git("diff", base_sha, cwd=work)
    assert "new_module.py" not in pre_fix, (
        "precondition did not reproduce the artifact: an untracked file must be "
        "invisible to a plain `git diff <ref>`, or this control proves nothing"
    )

    git("add", "-N", ".", cwd=work)
    fixed = git("diff", base_sha, cwd=work)
    assert "new_module.py" in fixed, "the fixed form still omits the new file"
    assert "+def f():" in fixed, "the fixed form did not show the file's content as added"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required to build the fixture")
def test_intent_to_add_does_not_disturb_other_staged_work(tmp_path: Path) -> None:
    """`git add -N .` must not be followed by a blanket `git reset` (issue #1030).

    A blind reset after the diff would discard unrelated content a caller
    staged earlier in the same run - not merely the intent-to-add markers this
    command adds. Pin that the markers alone do not stage real content: `git
    diff --cached` for the untracked file must stay empty even after `add -N`.
    """
    def git(*args: str, cwd: Path) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
            # negative-fixture: allow PATH is isolation, not an absence
            env={"HOME": str(tmp_path), "PATH": ISOLATED_PATH,
                 "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
        ).stdout

    work = tmp_path / "work"
    work.mkdir()
    git("init", "-q", "-b", "main", cwd=work)
    (work / "base.txt").write_text("base\n", encoding="utf-8")
    git("add", "-A", cwd=work)
    git("commit", "-qm", "base", cwd=work)

    # Real, intentional staged work from earlier in a run this command must not touch.
    (work / "already_staged.txt").write_text("earlier work\n", encoding="utf-8")
    git("add", "already_staged.txt", cwd=work)

    (work / "new_module.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    untracked = git("ls-files", "--others", "--exclude-standard", cwd=work).splitlines()
    git("add", "-N", "--", *untracked, cwd=work)

    cached = git("diff", "--cached", cwd=work)
    assert "already_staged.txt" in cached and "earlier work" in cached, (
        "unrelated staged work must survive untouched"
    )
    assert "new_module.py" not in cached, (
        "intent-to-add must not stage the new file's CONTENT, only mark its path"
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required to build the fixture")
def test_intent_to_add_does_not_stage_an_unrelated_tracked_deletion(tmp_path: Path) -> None:
    """Codex review finding, accepted: `-N .` is not scoped to untracked paths.

    `git add -N .` walks the whole pathspec, which includes a TRACKED file
    removed from the working tree but never `git rm`'d - and `add -N` stages
    that removal into the index, not merely a placeholder for it (measured:
    `git status --porcelain` reads " D path" before, "D  path" - staged -
    after a bare `add -N .`). A deletion nobody asked this review to touch
    would then ride along into whatever the caller commits next. Scoping to
    the enumerated untracked paths only (this fix) must leave it untouched -
    and it does not need staging anyway, since a plain `git diff <ref>`
    already shows a tracked deletion with no staging at all.
    """
    def git(*args: str, cwd: Path) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
            # negative-fixture: allow PATH is isolation, not an absence
            env={"HOME": str(tmp_path), "PATH": ISOLATED_PATH,
                 "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
        ).stdout

    work = tmp_path / "work"
    work.mkdir()
    git("init", "-q", "-b", "main", cwd=work)
    (work / "unrelated_tracked.txt").write_text("do not touch\n", encoding="utf-8")
    git("add", "-A", cwd=work)
    git("commit", "-qm", "base", cwd=work)

    (work / "unrelated_tracked.txt").unlink()
    (work / "new_module.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    # Precondition: a bare `git add -N .` DOES stage the deletion - if it did
    # not, this control would not be exercising the defect it claims to.
    precondition = tmp_path / "precondition"
    shutil.copytree(work, precondition)
    git("add", "-N", ".", cwd=precondition)
    assert "D  unrelated_tracked.txt" in git("status", "--porcelain", cwd=precondition), (
        "precondition did not reproduce the artifact: `git add -N .` must "
        "stage a tracked deletion, or this control proves nothing"
    )

    # The fix: enumerate untracked paths and pass them literally.
    untracked = git("ls-files", "--others", "--exclude-standard", cwd=work).splitlines()
    assert untracked == ["new_module.py"]
    git("add", "-N", "--", *untracked, cwd=work)

    status = git("status", "--porcelain", cwd=work)
    assert " D unrelated_tracked.txt" in status, (
        f"the tracked deletion must stay UNSTAGED:\n{status}"
    )
    assert " A new_module.py" in status, f"the new file must still be marked:\n{status}"


# ---------------------------------------------------------------------------
# Issue #1030, defect 4: the command's own output contract used to say "Return
# ONLY a findings report", so a caller reading code_review.md alone - not
# supplying the red-cases ask itself, as /flow:auto used to - got no red cases
# at all. Fixed by making "## Red cases" part of THIS command's documented
# contract, with an EXPRESSIBLE empty case: a review that changed no
# instrument must still emit a sentinel, so an absent section stays
# distinguishable from a considered zero (`red_cases.proposed: 0` recorded
# honestly, vs. a missing output nobody asked for).
# ---------------------------------------------------------------------------


def test_the_contract_requires_a_red_cases_section_not_only_findings() -> None:
    text = COMMAND.read_text(encoding="utf-8")
    # The precise ORIGINAL instruction line, not the shorter phrase the Notes
    # section legitimately quotes as historical context for why this changed -
    # a blanket "not in text" check would false-positive on that quote.
    assert "Return ONLY a findings report in exactly this format:" not in text, (
        "code_review.md's prompt still tells the reviewer to return ONLY "
        "findings, so a caller relying on this document alone gets no red "
        "cases (issue #1030)"
    )
    assert "Return a findings report AND a red cases section" in text, (
        "code_review.md's prompt no longer asks for both outputs"
    )
    assert "## Red cases" in text, (
        "code_review.md's own prompt no longer asks for a '## Red cases' section"
    )


def test_the_empty_red_cases_case_is_expressible_not_merely_absent() -> None:
    """The empty case must be a SENTINEL the reviewer is told to emit.

    Without an explicit "write this exact sentence" instruction for the
    no-instrument-changed case, a reviewer that found nothing to say about red
    cases would simply omit the section - which `counter-model-receipt.py`
    could not tell apart from a reviewer that never got asked at all. Pinning
    the literal sentinel text is what keeps a considered zero from silently
    becoming a missing output.
    """
    text = COMMAND.read_text(encoding="utf-8")
    assert "None - no instrument changed." in text, (
        "code_review.md's prompt no longer gives the reviewer an explicit "
        "empty-case sentinel for '## Red cases', so a considered zero and a "
        "missing section become indistinguishable"
    )
    # The instruction must actually tell the reviewer WHEN to use it (no
    # instrument added or modified) - the bare string alone could be an
    # unrelated example rather than the documented empty case.
    assert re.search(
        r"modifies no instrument.{0,40}None - no instrument changed", text, re.S
    ), (
        "the empty-case sentinel is not tied to 'the change modifies no "
        "instrument' - it must be clear WHEN a reviewer should emit it"
    )


# ---------------------------------------------------------------------------
# Cross-model review findings on the #1030 fix itself (accepted, fixed here):
# a failed intent-to-add must not report itself complete, and both commands
# must run from the worktree root rather than the caller's cwd.
# ---------------------------------------------------------------------------


def _step2_block() -> str:
    """The Step 2 'Collect the diff' bash block, executed for real."""
    text = COMMAND.read_text(encoding="utf-8")
    section = text[text.index("### Step 2: Collect the diff") : text.index("### Step 3:")]
    match = re.search(r"```bash\n(.*?)```", section, re.S)
    assert match, "no bash block in Step 2"
    return match.group(1)


requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")


def _git(*args: str, cwd: Path, env_extra: dict[str, str] | None = None) -> str:
    env = {"PATH": ISOLATED_PATH,  # negative-fixture: allow PATH is isolation, not an absence
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env,
    ).stdout


@requires_git
def test_step2_from_a_subdirectory_still_sees_a_sibling_new_file(tmp_path: Path) -> None:
    """Codex review finding, accepted: cwd must not narrow what gets marked.

    Invoking Step 2 from a subdirectory used to mark only untracked files
    beneath it - a new file elsewhere in the worktree stayed invisible to the
    diff exactly as before the #1030 fix, and the count silently omitted it.
    """
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    env = {"HOME": str(home)}
    _git("init", "-q", "-b", "main", cwd=work, env_extra=env)
    (work / "base.txt").write_text("base\n", encoding="utf-8")
    _git("add", "-A", cwd=work, env_extra=env)
    _git("commit", "-qm", "base", cwd=work, env_extra=env)

    subdir = work / "src"
    subdir.mkdir()
    # The sibling new file lives OUTSIDE the subdirectory the block runs from.
    (work / "sibling_new.py").write_text("def g():\n    return 2\n", encoding="utf-8")

    # negative-fixture: allow PATH is isolation, not an absence
    full_env = {**os.environ, "HOME": str(home), "PATH": ISOLATED_PATH,
                "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x",
                "BASE": "HEAD"}
    proc = subprocess.run(
        ["bash", "-c", _step2_block() + '\necho "COUNT=$UNTRACKED_COUNT"\necho "DIFF_FILE_PATH=$DIFF_FILE"'],
        cwd=subdir, env=full_env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "COUNT=1" in proc.stdout, (
        f"the sibling new file was not counted from a subdirectory invocation:\n{proc.stdout}"
    )
    diff_file = re.search(r"^DIFF_FILE_PATH=(\S+)$", proc.stdout, re.M)
    assert diff_file, f"DIFF_FILE path not found in output:\n{proc.stdout}"
    diff_content = Path(diff_file.group(1)).read_text()
    assert "sibling_new.py" in diff_content, (
        "the sibling new file is still missing from the diff when run from a subdirectory"
    )


@requires_git
def test_step2_fails_loudly_when_intent_to_add_cannot_run(tmp_path: Path) -> None:
    """Codex review finding, accepted twice: a swallowed failure must not look
    like success, and the SIMULATION of that failure must be deterministic.

    The first version of this test chmod'd `.git` read-only, then `pytest.skip`d
    if that did not actually cause a failure (e.g. running as root) - a
    non-deterministic simulation with a skip escape hatch is exactly the shape
    that lets a reintroduced `git add -N . 2>/dev/null || true` pass this test
    by skipping rather than failing. `.git/index.lock` is git's OWN concurrency
    mechanism: pre-creating it makes ANY git command that touches the index
    fail with a fixed, privilege-independent exit code (measured: 128), so
    there is no skip path and no privilege dependency left to hide behind.
    """
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    env = {"HOME": str(home)}
    _git("init", "-q", "-b", "main", cwd=work, env_extra=env)
    (work / "base.txt").write_text("base\n", encoding="utf-8")
    _git("add", "-A", cwd=work, env_extra=env)
    _git("commit", "-qm", "base", cwd=work, env_extra=env)
    (work / "new_module.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    (work / ".git" / "index.lock").touch()
    try:
        # negative-fixture: allow PATH is isolation, not an absence
        full_env = {**os.environ, "HOME": str(home), "PATH": ISOLATED_PATH,
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x",
                    "BASE": "HEAD"}
        proc = subprocess.run(
            ["bash", "-c", _step2_block()],
            cwd=work, env=full_env, capture_output=True, text=True,
        )
    finally:
        (work / ".git" / "index.lock").unlink(missing_ok=True)

    assert proc.returncode == 3, f"expected exit 3, got {proc.returncode}:\n{proc.stderr}"
    assert "CODEX_REVIEW: unavailable" in proc.stderr, proc.stderr
    assert "intent-to-add" in proc.stderr, proc.stderr


@requires_git
def test_the_failure_guard_actually_guards_something(tmp_path: Path) -> None:
    """The control on the control (Codex review finding, accepted).

    Pins the OTHER half: replacing the checked `if ! ... add -N ...; then exit
    3; fi` with the old swallowed form (`git add -N ... 2>/dev/null || true`)
    against the SAME `.git/index.lock` fixture must make this test's own
    assertions fail - proving the guard in `test_step2_fails_loudly_when_
    intent_to_add_cannot_run` is load-bearing, not merely un-skipped.
    """
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    env = {"HOME": str(home)}
    _git("init", "-q", "-b", "main", cwd=work, env_extra=env)
    (work / "base.txt").write_text("base\n", encoding="utf-8")
    _git("add", "-A", cwd=work, env_extra=env)
    _git("commit", "-qm", "base", cwd=work, env_extra=env)
    (work / "new_module.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    swallowed_block = re.sub(
        r'if \[ "\$UNTRACKED_COUNT" -gt 0 \] && ! git -C "\$GIT_ROOT" add -N -- '
        r'"\$\{UNTRACKED_FILES\[@\]\}"; then\n'
        r'(?:.*\n)*?'
        r'fi\n',
        'git -C "$GIT_ROOT" add -N -- "${UNTRACKED_FILES[@]}" 2>/dev/null || true\n',
        _step2_block(),
    )
    assert "2>/dev/null || true" in swallowed_block, (
        "the substitution did not match the current guard shape - update this "
        "test's pattern to match code_review.md's Step 2 block"
    )

    (work / ".git" / "index.lock").touch()
    try:
        # negative-fixture: allow PATH is isolation, not an absence
        full_env = {**os.environ, "HOME": str(home), "PATH": ISOLATED_PATH,
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x",
                    "BASE": "HEAD"}
        proc = subprocess.run(
            ["bash", "-c", swallowed_block],
            cwd=work, env=full_env, capture_output=True, text=True,
        )
    finally:
        (work / ".git" / "index.lock").unlink(missing_ok=True)

    assert proc.returncode != 3, (
        "the swallowed form must NOT exit 3 - if it does, this test's "
        "substitution failed to remove the guard and proves nothing"
    )
