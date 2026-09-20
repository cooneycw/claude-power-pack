"""The bashrc append is idempotent, and its guard can actually fire (#1142).

`/cpp:init` appends two blocks to `~/.bashrc`. The tmux block has always
guarded itself; the PS1 block did not, so running `/cpp:init` twice and
answering yes both times left two `export PS1=` lines. #1139 relocated both
into `scripts/cpp-host-write.sh` and carried the defect forward deliberately
behind a `--no-guard` flag, because a refactor that also repairs cannot
demonstrate it preserved behaviour. This is the repair, and these are its
tests.

TWO ASSERTIONS, AND THE SECOND IS WHY THE FIRST MEANS ANYTHING. The count
alone cannot tell "the guard matched on the second run" from "the append
happened once for some other reason", and a guard whose marker never occurs in
the content it appends would never fire while still passing a single run. So
the marker is asserted to be present in the bytes written, in the same test.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "cpp-host-write.sh"

#: The marker and content exactly as `.claude/commands/cpp/init.md` passes
#: them. If the document changes one and not the other, the guard stops
#: firing and this test is the thing that notices.
MARKER = "# Claude Power Pack - worktree context in prompt"
CONTENT = (
    "\n"
    "# Claude Power Pack - worktree context in prompt\n"
    "export PS1='$(~/.claude/scripts/prompt-context.sh)\\w $ '\n"
)


def _append(home: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Run one bashrc-append against a sandboxed $HOME. Never the real one."""
    env = os.environ.copy()
    env.update({"HOME": str(home), "USER": "tester"})
    return subprocess.run(
        ["bash", str(HELPER), "bashrc-append", MARKER, "-", *extra],
        input=CONTENT,
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        check=False,
    )


def test_running_twice_leaves_one_export(tmp_path: Path) -> None:
    """The #1142 defect: two runs used to leave two exports."""
    home = tmp_path / "home"
    home.mkdir()

    first = _append(home)
    second = _append(home)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr

    bashrc = (home / ".bashrc").read_text()
    assert bashrc.count("export PS1=") == 1, (
        "two appends left "
        f"{bashrc.count('export PS1=')} export line(s); the marker guard did "
        "not fire on the second run"
    )


def test_the_guard_marker_occurs_in_the_content_it_appends(tmp_path: Path) -> None:
    """A guard whose marker never appears in its content can never fire.

    That failure is invisible to a count on a single run and produces a file
    that grows forever, so it is asserted directly rather than inferred from
    the idempotence test passing.
    """
    home = tmp_path / "home"
    home.mkdir()

    assert MARKER in CONTENT, (
        "the marker is not in the content the helper appends, so the guard "
        "greps for a string that will never be in the file"
    )

    _append(home)
    bashrc = (home / ".bashrc").read_text()
    assert MARKER in bashrc, (
        "the marker is absent from the written file, so a second run cannot "
        "match it however correct the guard logic is"
    )


#: The document is where the defect actually lived, and the first cut of this
#: file missed it. `test_running_twice_leaves_one_export` drives the HELPER
#: directly and never passes `--no-guard`, so it exercised the guarded path
#: both before and after the fix - it PASSED on the unfixed tree, which makes
#: it no regression test at all. Measured, not reasoned: run against
#: origin/main it reported 2 passed, 1 failed, and the one failure was the
#: helper-side assertion below.
#:
#: The defect was `/cpp:init` PASSING the flag. So this asserts on what the
#: document does, which is the thing that was wrong.
INIT_MD = ROOT / ".claude" / "commands" / "cpp" / "init.md"


def test_the_ps1_call_site_does_not_disable_its_guard() -> None:
    """`/cpp:init` must not pass `--no-guard` when appending the PS1 block."""
    text = INIT_MD.read_text()
    assert MARKER in text, (
        "the PS1 marker is not in init.md; this test is aimed at a call site "
        "that has moved, and would pass vacuously"
    )
    call = next(
        (line for line in text.split("\n") if "--no-guard" in line),
        "",
    )
    assert "--no-guard" not in text, (
        "init.md still passes --no-guard, so running /cpp:init twice appends "
        f"the PS1 export twice: {call.strip()[:90]}"
    )


def test_the_helper_no_longer_accepts_no_guard(tmp_path: Path) -> None:
    """`--no-guard` existed only to carry the defect across #1139's move.

    It named its own deletion condition; this asserts the deletion happened,
    so the flag cannot quietly return and re-open the duplicate append.
    """
    home = tmp_path / "home"
    home.mkdir()

    result = _append(home, "--no-guard")

    assert "--no-guard" not in HELPER.read_text(), (
        "the --no-guard branch is still in the helper"
    )
    #: The flag is now an unrecognised argument. It must not silently behave
    #: as though it were still supported.
    second = _append(home, "--no-guard")
    bashrc = (home / ".bashrc").read_text()
    assert bashrc.count("export PS1=") <= 1, (
        f"passing a removed flag re-enabled the duplicate append "
        f"({bashrc.count('export PS1=')} exports); result={result.returncode}, "
        f"second={second.returncode}"
    )
