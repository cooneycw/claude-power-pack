"""Every flow helper prints its own exit status, so a pipe cannot delete it (issue #1031).

THE DEFECT. `pipefail` is not set in the calling lane, so

    helper ... | tail -3; echo "exit=$?"

prints `exit=0` while the helper refused with a usage error - `$?` is TAIL's.
It bit two of three workers in one wave, and trimming helper output is constant
here because these scripts print 10+ marker lines per call. `/codex:auto`
documents the hazard at length for its own lane (#798), which hardened the
DOCUMENTED invocation and did nothing for the idiom. Since #1027 it costs more
than it used to: every gate verdict now has its own exit code, so the pipe
destroys information that did not exist before.

THE REMEDY IS IN THE HELPER, NOT IN THE CALLER. Each one prints
`<NAMESPACE>_EXIT=<code>` as the last thing it writes. That is the whole point:
the alternative remedies all reduce to the caller remembering something.

WHY STDERR. Three reasons, and the third is the one that decided it:

  * stdout is these helpers' machine-readable contract, and sibling helpers
    capture it with `$(...)` - `flow-start-resolve.sh` reads
    `flow-worktree-claim.sh` and `stash-worktree-guard.sh` that way, and
    `speckit-context.py refresh` writes a whole issue body to stdout. Metadata
    on a data channel corrupts those callers.
  * stderr BYPASSES the pipe entirely, so it survives `| head -5` too, where a
    trailing stdout line would be lost outright.
  * the existing sibling filters (`grep -v '^STASH_GUARD'`,
    `grep -v '^FLOW_CLAIM'`) already swallow the prefixed name, so no consumer
    needed changing.

What would move this back: a consumer that reads a helper's stderr as data.
There is none today, and putting the status on stdout would have to answer the
`$(...)` captures above first.

MEMBERSHIP IS DERIVED. The population is the `HELPERS` array in
`flow-helpers-install.sh` - the family's own definition of itself - so a helper
added next month is covered from its first commit rather than when somebody
remembers this file. The NAMESPACE per helper is declared, because it follows
each script's existing marker prefix rather than its filename
(`gh-pr-merge.sh` -> `GH_PR_MERGE`, `flow-wave-mailbox.sh` -> `FLOW_MAILBOX`),
and a declared table that must match the derived population fails loudly when
either side moves.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
INSTALLER = SCRIPTS / "flow-helpers-install.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)

#: helper basename -> the marker namespace it already uses on its own output.
NAMESPACES = {
    "flow-start-resolve.sh": "FLOW_START_RESOLVE",
    "flow-live-driver-guard.sh": "FLOW_LIVE_DRIVER",
    "flow-stale-check.sh": "FLOW_STALE",
    "flow-worktree-guard.sh": "FLOW_WORKTREE_GUARD",
    "flow-worktree-claim.sh": "FLOW_CLAIM",
    "flow-wave-registry.sh": "FLOW_WAVE",
    "flow-wave-mailbox.sh": "FLOW_MAILBOX",
    "flow-wave-lexicon.sh": "FLOW_LEXICON",
    "flow-wave-plan.py": "FLOW_WAVE_PLAN",
    "speckit-context.py": "SPECKIT_CONTEXT",
    "flow-driver-capability.sh": "FLOW_DRIVER",
    "flow-vantage.sh": "FLOW_VANTAGE",
    "flow-finish-gate.sh": "FLOW_FINISH_GATE",
    "flow-ci-status.sh": "FLOW_CI",
    "flow-pr-watch.sh": "FLOW_PR_WATCH",
    "gh-pr-merge.sh": "GH_PR_MERGE",
    "worktree-remove.sh": "WORKTREE_REMOVE",
    "flow-worktree-sweep.sh": "FLOW_WORKTREE_SWEEP",
    "friction-log.sh": "FRICTION_LOG",
    "check-ignored-additions.sh": "CHECK_IGNORED_ADDITIONS",
    "delegated-run-check.sh": "DELEGATED_RUN_CHECK",
    "lane-serveability-check.sh": "LANE_SERVE",
    "cpp-commands-link.sh": "CPP_COMMANDS_LINK",
    "install-drift.sh": "INSTALL_DRIFT",
    "stash-worktree-guard.sh": "STASH_GUARD",
    "flow-helpers-install.sh": "FLOW_HELPERS",
}

#: The three helpers that install a cleanup `trap ... EXIT` of their own DEEP in
#: a subcommand. A bare one there REPLACES the top-level emitter and nothing
#: reports the loss, so they are checked for the chained form specifically.
CHAINERS = ("flow-wave-registry.sh", "flow-wave-mailbox.sh", "lane-serveability-check.sh")


def installed_helpers() -> list[str]:
    """The `HELPERS=(...)` array in flow-helpers-install.sh - the family itself."""
    text = INSTALLER.read_text(encoding="utf-8")
    match = re.search(r"^HELPERS=\(\n(.*?)^\)", text, re.MULTILINE | re.DOTALL)
    assert match, "flow-helpers-install.sh no longer declares HELPERS=( ... )"
    names = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    assert len(names) > 10, f"parsed an implausibly small family: {names}"
    return names


# --- membership ------------------------------------------------------------ #

def test_the_declared_table_covers_exactly_the_installed_family() -> None:
    """A helper added to the family without a namespace fails HERE, loudly.

    This is the half that stops the rule decaying into "whatever was true in
    September". The table cannot be a subset that quietly shrinks, and it cannot
    carry a name the family dropped.
    """
    family = set(installed_helpers())
    declared = set(NAMESPACES)
    assert declared - family == set(), f"declared but no longer in the family: {sorted(declared - family)}"
    assert family - declared == set(), (
        f"in the family with no exit-line namespace declared: {sorted(family - declared)}. "
        "Add the trap to the helper and the namespace here."
    )


def emit_lines(source: str, namespace: str) -> list[str]:
    """The lines that actually EMIT the marker - not every line mentioning it.

    A whole-file search for `>&2` is not a channel check: every one of these
    helpers writes unrelated diagnostics to stderr, so the redirect is present
    whatever the marker does. The first cut of this test made exactly that
    mistake and would have passed a marker moved to stdout - which is the one
    thing the channel choice exists to prevent, because sibling helpers capture
    these scripts' stdout with `$(...)`. Found by the counter-model review.
    """
    emit = re.compile(
        r"(printf\s+\"" + re.escape(namespace) + r"_EXIT=%d"
        r"|print\(f\"" + re.escape(namespace) + r"_EXIT=\{)"
    )
    return [line for line in source.splitlines() if emit.search(line)]


def emits_on_stderr(source: str, namespace: str) -> bool:
    lines = emit_lines(source, namespace)
    return bool(lines) and all(
        ">&2" in line or "file=sys.stderr" in line for line in lines
    )


@pytest.mark.parametrize("name", sorted(NAMESPACES))
def test_every_helper_emits_its_exit_line_on_stderr(name: str) -> None:
    source = (SCRIPTS / name).read_text(encoding="utf-8")
    namespace = NAMESPACES[name]
    assert emit_lines(source, namespace), f"{name} does not emit {namespace}_EXIT="
    assert emits_on_stderr(source, namespace), (
        f"{name} emits {namespace}_EXIT= on stdout, where it corrupts $(...) capture"
    )


def test_the_channel_check_rejects_a_marker_moved_to_stdout(tmp_path: Path) -> None:
    """RED, executed, on a REAL helper that also writes unrelated stderr.

    `flow-ci-status.sh` prints diagnostics to stderr throughout, so a whole-file
    `>&2` search passes on it no matter where the marker goes. That is why the
    mutation is applied here rather than to a toy string.
    """
    source = (SCRIPTS / "flow-ci-status.sh").read_text(encoding="utf-8")
    assert emits_on_stderr(source, "FLOW_CI"), "baseline: the shipped helper must pass"

    mutated = "\n".join(
        line.replace(" >&2", "") if "printf \"FLOW_CI_EXIT=%d" in line else line
        for line in source.splitlines()
    )
    assert ">&2" in mutated, "the mutation must leave the helper's OTHER stderr writes intact"
    assert not emits_on_stderr(mutated, "FLOW_CI"), (
        "the channel check passed a marker printed to stdout"
    )


@pytest.mark.parametrize("name", sorted(NAMESPACES))
def test_no_namespace_collides_with_a_marker_the_helper_already_uses(name: str) -> None:
    """`<NS>_EXIT=` must not be a second meaning for an `<NS>_EXIT:` that exists.

    Missed on the first cut and found by a sibling PR landing mid-run:
    `delegated-run-check.sh` already printed `DELEGATED_RUN_EXIT: <exit code as
    passed>` on stdout - the DELEGATED run's status, handed in by the caller -
    and the derived namespace produced `DELEGATED_RUN_EXIT=` for THIS script's
    own status. Two facts, one name, told apart only by `:` versus `=`; a grep
    for either returns both. The namespace is now `DELEGATED_RUN_CHECK`, and
    this is the check that would have said so.
    """
    source = (SCRIPTS / name).read_text(encoding="utf-8")
    collision = re.compile(rf"\b{re.escape(NAMESPACES[name])}_EXIT:")
    offenders = [ln.strip() for ln in source.splitlines() if collision.search(ln)]
    assert not offenders, (
        f"{name} already uses {NAMESPACES[name]}_EXIT: for something else: {offenders[:2]}"
    )


@pytest.mark.parametrize("name", CHAINERS)
def test_a_later_exit_trap_is_chained_not_bare(name: str) -> None:
    """No `trap ... EXIT` in these files may fail to carry the status forward."""
    token = f'{NAMESPACES[name]}_EXIT='
    for line in (SCRIPTS / name).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("trap ") or " EXIT" not in f"{stripped} ":
            continue
        if not stripped.endswith("EXIT") and " EXIT " not in stripped:
            continue
        assert token in stripped, (
            f"{name} installs an EXIT trap that does not emit {token}, which REPLACES the "
            f"top-level emitter: {stripped}"
        )


# --- the mechanism, executed ----------------------------------------------- #

def last_stderr(*argv: str) -> tuple[int, str]:
    proc = subprocess.run(list(argv), capture_output=True, text=True, timeout=120, check=False)
    lines = [ln for ln in proc.stderr.splitlines() if ln.strip()]
    return proc.returncode, (lines[-1] if lines else "")


@pytest.mark.parametrize(
    ("argv", "name"),
    [
        (["flow-finish-gate.sh", "--help"], "flow-finish-gate.sh"),
        (["flow-driver-capability.sh", "list"], "flow-driver-capability.sh"),
        (["friction-log.sh"], "friction-log.sh"),
    ],
)
def test_a_clean_run_reports_zero(argv: list[str], name: str) -> None:
    code, line = last_stderr("bash", str(SCRIPTS / argv[0]), *argv[1:])
    assert code == 0, line
    assert line == f"{NAMESPACES[name]}_EXIT=0", line


@pytest.mark.parametrize(
    ("script", "expected"),
    [("worktree-remove.sh", 1), ("gh-pr-merge.sh", 2)],
)
def test_a_refusal_reports_its_own_status(script: str, expected: int) -> None:
    """BOTH DIRECTIONS. A line wedged at 0 would pass every zero-exit test above
    and be worse than no line at all - it would report success for a refusal."""
    code, line = last_stderr("bash", str(SCRIPTS / script))
    assert code == expected, line
    assert line == f"{NAMESPACES[script]}_EXIT={expected}", line


def test_the_status_survives_the_pipe_that_caused_this(tmp_path: Path) -> None:
    """The literal failing idiom from the wave, re-run against a helper.

    `$?` is still tail's and still 0 - nothing here changes that - but the real
    status is now IN the output the reader is looking at.
    """
    proc = subprocess.run(
        f'bash {SCRIPTS / "gh-pr-merge.sh"} 2>&1 | tail -3; echo "dollar-question=$?"',
        shell=True, capture_output=True, text=True, timeout=120, check=False,
        executable="/bin/bash",
    )
    assert "dollar-question=0" in proc.stdout, "the masking idiom no longer masks - rewrite this test"
    assert "GH_PR_MERGE_EXIT=2" in proc.stdout, proc.stdout


def test_the_python_helpers_flush_stdout_before_the_status(tmp_path: Path) -> None:
    """Ordering is the whole claim, and Python block-buffers a piped stdout.

    Without the explicit flush the status lands BEFORE the contract under
    `2>&1 | tail -N`, so `tail` drops it while the line still appears in an
    untrimmed run - present when you check, absent when you rely on it.
    """
    body = tmp_path / "body.md"
    body.write_text("an ordinary issue body\n", encoding="utf-8")
    proc = subprocess.run(
        f'python3 {SCRIPTS / "speckit-context.py"} check --body-file {body} --root {ROOT} 2>&1 | tail -1',
        shell=True, capture_output=True, text=True, timeout=120, check=False,
        executable="/bin/bash",
    )
    assert proc.stdout.strip() == "SPECKIT_CONTEXT_EXIT=0", proc.stdout


# --- the guard's own bounds ------------------------------------------------ #

def test_the_stash_guard_emits_on_the_admin_lane(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], timeout=120, check=True)
    _code, line = last_stderr("bash", str(SCRIPTS / "stash-worktree-guard.sh"), "--check", str(repo))
    assert line == "STASH_GUARD_EXIT=0" or line.startswith("STASH_GUARD_EXIT="), line


def test_the_stash_guard_is_silent_on_the_hook_lane(tmp_path: Path) -> None:
    """It is COPIED INTO .git/hooks and runs on every ref update.

    A status line there would print on every `git commit` and `git fetch` in
    every repository carrying the guard. A guard that makes ordinary git noisy
    is a guard people remove, so this bound is asserted rather than assumed.
    """
    proc = subprocess.run(
        ["bash", str(SCRIPTS / "stash-worktree-guard.sh"), "committed"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert "STASH_GUARD_EXIT=" not in proc.stderr, proc.stderr
    assert "STASH_GUARD_EXIT=" not in proc.stdout, proc.stdout


# --- the negative control for the chaining rule ---------------------------- #

def test_a_bare_later_exit_trap_really_does_delete_the_line(tmp_path: Path) -> None:
    """RED, executed: the hazard `test_a_later_exit_trap_is_chained_not_bare` guards.

    A static check on trap text is re-reading the instrument, so this runs the
    two shapes and shows they differ. If bash ever stacked EXIT traps instead of
    replacing them, that static check would be guarding nothing, and this test
    is what would say so.
    """
    common = 'trap \'printf "TOY_EXIT=%d\\n" "$?" >&2\' EXIT\n'
    bare = tmp_path / "bare.sh"
    bare.write_text(f"#!/usr/bin/env bash\n{common}trap 'true' EXIT\nexit 7\n", encoding="utf-8")
    chained = tmp_path / "chained.sh"
    chained.write_text(
        f"#!/usr/bin/env bash\n{common}"
        'trap \'_rc=$?; true; printf "TOY_EXIT=%d\\n" "$_rc" >&2\' EXIT\nexit 7\n',
        encoding="utf-8",
    )

    _c1, bare_line = last_stderr("bash", str(bare))
    _c2, chained_line = last_stderr("bash", str(chained))
    assert bare_line == "", "a bare later EXIT trap no longer replaces the first one"
    assert chained_line == "TOY_EXIT=7", chained_line


# --- the exception path, which `finally` alone got backwards ---------------- #

def test_a_python_helper_prints_its_traceback_before_the_status(tmp_path: Path) -> None:
    """The counter-model finding: `finally` runs BEFORE the interpreter's traceback.

    So the first cut emitted `SPECKIT_CONTEXT_EXIT=1` and THEN re-raised, and
    `2>&1 | tail -1` deleted the marker - the exact idiom the marker exists to
    survive, defeating it on the one path where a reader most needs the status.
    Both Python helpers now report the traceback themselves, first.
    """
    proc = subprocess.run(
        f'python3 {SCRIPTS / "speckit-context.py"} check '
        f'--body-file {tmp_path / "absent.md"} --root {ROOT} 2>&1 | tail -1',
        shell=True, capture_output=True, text=True, timeout=120, check=False,
        executable="/bin/bash",
    )
    assert proc.stdout.strip() == "SPECKIT_CONTEXT_EXIT=1", proc.stdout

    unpiped = subprocess.run(
        ["python3", str(SCRIPTS / "speckit-context.py"), "check",
         "--body-file", str(tmp_path / "absent.md"), "--root", str(ROOT)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert unpiped.returncode == 1, unpiped.stderr
    assert "FileNotFoundError" in unpiped.stderr, (
        "the diagnostic was swallowed - reporting the status must not cost the traceback"
    )
    assert unpiped.stderr.rstrip().endswith("SPECKIT_CONTEXT_EXIT=1"), unpiped.stderr


def test_an_injected_exception_in_the_other_python_helper_reports_one(tmp_path: Path) -> None:
    """flow-wave-plan.py carries the identical wrapper, so it is exercised too.

    The failure is injected by importing the real module and replacing `main`,
    so this tests the SHIPPED entry point rather than a copy of its shape.
    """
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import runpy, sys, types\n"
        f"path = {str(SCRIPTS / 'flow-wave-plan.py')!r}\n"
        "src = open(path).read().replace('_code = main(sys.argv)', \"raise RuntimeError('injected')\")\n"
        "mod = types.ModuleType('__main__')\n"
        "mod.__dict__['__name__'] = '__main__'\n"
        "exec(compile(src, path, 'exec'), mod.__dict__)\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["python3", str(driver)], capture_output=True, text=True, timeout=120, check=False
    )
    assert proc.returncode == 1, proc.stderr
    assert "RuntimeError" in proc.stderr, proc.stderr
    assert proc.stderr.rstrip().endswith("FLOW_WAVE_PLAN_EXIT=1"), proc.stderr


def test_a_stdout_only_marker_would_not_satisfy_the_static_check() -> None:
    """The reviewer's red case for the enforcement test itself.

    `test_every_helper_emits_its_exit_line` asserts the marker AND a stderr
    redirect. A helper that printed the marker on stdout would corrupt the
    `$(...)` captures the channel choice exists to protect, so the check has to
    be able to say no to it - demonstrated here rather than assumed.
    """
    stdout_only = 'trap \'printf "TOY_EXIT=%d\\n" "$?"\' EXIT\n'
    assert ">&2" not in stdout_only
    assert "file=sys.stderr" not in stdout_only
