"""Shared fixtures for CPP unit tests."""

from __future__ import annotations

import atexit
import os
import re
import shutil
import sys
import tempfile
import textwrap
from collections.abc import Mapping
from pathlib import Path

import pytest

import tests as _tests_package
from tests.supervise_reap import (
    OWNER_ENV,
    drain_unreaped,
    owner_marker,
    reap_supervise_daemons,
    sweep_orphaned_supervise_daemons,
)

#: The checkout, anchored on the IMPORTED `tests` package rather than on this
#: file's own location. `Path(__file__).parents[1]` is wrong in the one case that
#: matters: a `pytester` sub-run is given a COPY of this conftest in a temporary
#: directory, where that expression resolves to the temporary directory's parent
#: and every repo-relative lookup below silently finds nothing. The package is
#: imported off `PYTHONPATH`, so it resolves to the real checkout either way.
REPO_ROOT = Path(_tests_package.__file__).resolve().parents[1]

#: A FRESH BYTECODE CACHE PER SESSION (issue #1259). CPython trusts a
#: source-adjacent `__pycache__/*.pyc` whose recorded (whole-second mtime,
#: size) match the source, so a negative-control red run that mutates a script
#: without changing its length and `cp`s the snapshot back inside one second
#: leaves the MUTANT's bytecode serving the restored file - in either direction,
#: a control reporting the opposite of what ran. Relocating the cache means the
#: source-adjacent one is never read, and exporting it covers `python3
#: scripts/x.py` children, which import `lib/*` themselves.
#: `tests/test_pycache_isolation.py` plants the stale artifact and must stay red
#: without this.
_PYCACHE_PREFIX = tempfile.mkdtemp(prefix="cpp-pytest-pycache-")
sys.pycache_prefix = _PYCACHE_PREFIX
os.environ["PYTHONPYCACHEPREFIX"] = _PYCACHE_PREFIX
atexit.register(shutil.rmtree, _PYCACHE_PREFIX, True)


#: WHICH RUN STARTED THIS DAEMON (issue #1271). Every process that imports this
#: conftest - the controller and each xdist worker - names itself here, and every
#: subprocess the suite starts inherits it, detached `supervise` daemons
#: included. A later run's session-start sweep reaps a daemon only when the
#: process instance it names is gone. PLAIN ASSIGNMENT, for the same reason as
#: the host-install guard below: a `pytester` sub-run must name itself, not its
#: parent. A test that builds its subprocess env from scratch drops the marker,
#: and its daemons are then never swept - the safe direction.
os.environ[OWNER_ENV] = owner_marker()

#: What the session-start sweep did, for the terminal summary. Empty lists are
#: the ordinary case; a run that could not sweep says so rather than nothing.
_SWEEP_REPORT: dict[str, list[int] | str] = {}


def pytest_sessionstart(session: pytest.Session) -> None:
    """Reap supervise daemons orphaned by an EARLIER, dead run (issue #1271).

    Controller only: xdist workers would each repeat the same scan. The per-test
    autouse reaper below cannot do this - it only knows the pidfiles under its
    own `tmp_path`, and an interrupted run never reaches its teardown at all.
    """
    if hasattr(session.config, "workerinput"):
        return
    try:
        result = sweep_orphaned_supervise_daemons()
    except Exception as exc:  # noqa: BLE001 - reported, never silent
        _SWEEP_REPORT["error"] = f"{type(exc).__name__}: {exc}"
        return
    _SWEEP_REPORT["reaped"] = result.reaped
    _SWEEP_REPORT["survivors"] = result.survivors


@pytest.fixture(autouse=True)
def _reap_leaked_supervise_daemons(tmp_path: Path):
    """Reap any detached `supervise` daemon a test left behind (issue #1116).

    `supervise` daemons outlive the command that starts them by design (issue
    #814), so a test that starts one owns a process pytest will not clean up.
    Left alone they are reparented to `systemd --user` and hold their working
    directory - the per-issue worktree - open, which makes
    `worktree-remove.sh`'s #888 occupancy guard refuse to remove it at the end
    of a `/flow:auto` run. The guard is right; it should not be spending its
    credibility on our litter.

    This is `autouse` deliberately, and that is the substance of the fix rather
    than a detail of it. Per-test kill calls are the fast path and stay where
    they are, but they only run on the paths a test actually reaches: a test
    that raises early, or whose own kill times out, skips them entirely - and
    those are precisely the paths that leak. Teardown runs either way, for
    every test in the suite, including ones written after this comment by
    someone who never read it.
    """
    yield
    result = reap_supervise_daemons(tmp_path)
    # A cleanup that cannot report its own failure is the defect this fixture
    # exists to remove (counter-model review, issue #1116): the code it
    # replaced discarded its waiter's result, so a daemon that outlived the
    # kill produced no signal at all. Surviving SIGKILL plus its grace period
    # is a real fault - loud here, or invisible until it pins someone's
    # worktree hours later.
    # Two populations, because neither covers the other (counter-model
    # re-review, issue #1116). `survivors` is what THIS reap could not kill.
    # `drain_unreaped()` is what a test's own fast-path kill already gave up
    # on - which the reap cannot rediscover when the test overwrote or removed
    # the pidfile, as two tests here deliberately do.
    unreaped = drain_unreaped()
    assert not result.survivors and not unreaped, (
        f"supervise daemon(s) {sorted({*result.survivors, *unreaped})} survived "
        "cleanup; they still hold this test's working directory"
    )


# --------------------------------------------------------------------------- #
# The suite must not be able to write to the host's Codex skill directory (#1232)
# --------------------------------------------------------------------------- #
# One test called `codex-skill-sync.py --install` without redirecting its
# destination, so `run_install()` installed a two-entry fixture over the
# developer's real `~/.codex/skills` and pruned the other 72 skills as orphans -
# correct behaviour on the wrong source tree. It happened on every `make test`
# and every `make verify`, in every checkout, and the test PASSED while doing it:
# nothing it asserted had anything to do with the host.
#
# ARMED HERE, ENFORCED IN THE SCRIPT. The refusal lives in
# `scripts/codex-skill-sync.py` and keys on an exact PATH this sets. That
# placement is what makes it cover a SUBPROCESS as well as an in-process call: a
# future test that shells out to `--install` inherits this variable. A conftest
# that monkeypatched the module attribute instead would be blind to exactly that
# caller, and blind to any test that loaded the module under another name.
#
# PLAIN ASSIGNMENT, never `setdefault`. A `pytester` sub-run inherits this
# process's environment and must recompute the value against ITS OWN `$HOME`;
# keeping the parent's value would protect a directory the child never writes to
# and leave the one it does write to unguarded.
#
# There is no opt-out, and that is deliberate: no test has a legitimate reason to
# write to this path. The `tmp_home` fixture in
# `tests/test_codex_skill_sync.py` satisfies the prohibition by pointing the
# destination somewhere else, which is what an opted-in test looks like.
#
# WHAT THIS DOES NOT DO, so its silence is not read as coverage: it guards ONE
# destination. It says nothing about any other write a test might make under the
# real `$HOME`.

#: Populated when the guard could NOT be armed. Read by the terminal summary, so
#: an unarmed guard reports itself instead of looking like a clean run - the whole
#: failure mode here is a green that means "nothing checked".
_HOST_INSTALL_GUARD_UNARMED: list[str] = []


def _refuse_install_dest_env() -> str:
    """The env var name, READ FROM THE SCRIPT that consumes it.

    Spelling it twice would mean a rename in the script leaves this conftest
    exporting a variable nothing reads - the guard silently absent, with no
    signal. Derived, a rename breaks the derivation and the summary says so.
    """
    import importlib.util
    import sys

    script = REPO_ROOT / "scripts" / "codex-skill-sync.py"
    spec = importlib.util.spec_from_file_location("_cpp_codex_skill_sync_env", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_cpp_codex_skill_sync_env"] = module
    spec.loader.exec_module(module)
    return str(module.REFUSE_INSTALL_DEST_ENV)


def pytest_configure(config: pytest.Config) -> None:
    """Arm the host-install refusal for this process and everything it spawns."""
    _build_codex_skills(config)
    try:
        name = _refuse_install_dest_env()
        dest = Path.home() / ".codex" / "skills"
    except Exception as exc:  # noqa: BLE001 - reported, never silent
        _HOST_INSTALL_GUARD_UNARMED.append(f"{type(exc).__name__}: {exc}")
        return
    os.environ[name] = str(dest)


# --------------------------------------------------------------------------- #
# codex/skills/ is build output, so the suite builds it (#1670)
# --------------------------------------------------------------------------- #
# Some forty test files read the generated Codex skills under `codex/skills/`.
# While that tree was tracked, a fresh clone simply had it. It is ignored build
# output now (ADR 0013), so a fresh clone has only its README and every one of
# those tests would fail on a missing file that no commit removed.
#
# BUILT ONCE, BY THE CONTROLLER. An xdist worker carries `workerinput`; letting
# each worker regenerate would have a dozen processes rewriting files the
# others are reading.
#
# A FAILED BUILD STOPS THE RUN. Carrying on would turn one generator error into
# hundreds of unrelated-looking failures, and a stale tree left from an earlier
# build would be worse: those tests would pass against yesterday's skills.
#
# `--write` REGENERATES, it does not merely fill gaps: it rewrites any file that
# differs and prunes what is no longer generated, so the tree the suite reads is
# the one the current sources produce.
#
# ONCE PER SESSION TREE, NOT ONCE PER PROCESS. Several tests start a nested
# pytest (`pytester`) that loads this same conftest, some of them against a
# fake repository root with no generator in it. A nested run rebuilding the
# tree would rewrite it under the parallel session that is reading it. The
# environment variable is inherited by every child, so only the outermost
# process builds.
_CODEX_SKILLS_BUILT_ENV = "CPP_TEST_CODEX_SKILLS_BUILT"


def _build_codex_skills(config: pytest.Config) -> None:
    if hasattr(config, "workerinput") or os.environ.get(_CODEX_SKILLS_BUILT_ENV):
        return
    import subprocess
    import sys

    script = REPO_ROOT / "scripts" / "codex-skill-sync.py"
    result = subprocess.run(
        [sys.executable, str(script), "--write"],
        capture_output=True, text=True, timeout=300, check=False,
    )
    if result.returncode != 0:
        raise pytest.UsageError(
            "could not build codex/skills/ before the test session"
            f" (codex-skill-sync.py --write exited {result.returncode}):\n"
            f"{result.stdout}{result.stderr}"
        )
    os.environ[_CODEX_SKILLS_BUILT_ENV] = str(REPO_ROOT)


@pytest.fixture(autouse=True)
def isolate_flow_wave_lineage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep host sockets and session hooks out of tests unless explicitly supplied."""
    missing = tmp_path / "no-flow-wave-session"
    assert not missing.exists(), "precondition: the default lineage path does not exist"
    monkeypatch.setenv("FLOW_WAVE_SOCK_DIR", str(missing))
    monkeypatch.setenv("FLOW_WAVE_SESSION_PIDS", str(missing))


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with .gitignore."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(
        textwrap.dedent("""\
        .env
        .env.*
        *.pem
        *.key
        secrets.*
        *.p12
        .claude/security.yml
        """)
    )
    return tmp_path


@pytest.fixture
def sample_tasks_md(tmp_path: Path) -> Path:
    """Create a sample tasks.md file."""
    content = textwrap.dedent("""\
    # Tasks: My Feature

    > **Plan:** [plan.md](./plan.md)
    > **Created:** 2026-01-01
    > **Status:** Ready

    ---

    ## Wave 1: Core setup

    - [ ] **T001** [US1] Create the main module `lib/main.py`
    - [x] **T002** [US1] Add configuration parsing `lib/config.py`
    - [ ] **T003** [P] [US2] Add parallel task support

    **Checkpoint:** `make test` passes

    ---

    ## Wave 2: Integration

    - [ ] **T004** [US1] Integrate with external API (depends on T001, T002)
    - [ ] **T005** [US2] Add error handling

    **Checkpoint:** Integration tests pass

    ---

    ## Issue Sync
    | Wave | Description | Issue | Status |
    |------|-------------|-------|--------|
    | 1 | Core setup | #42 | synced |
    | 2 | Integration | | pending |
    """)
    tasks_file = tmp_path / "tasks.md"
    tasks_file.write_text(content)
    return tasks_file


@pytest.fixture
def sample_spec_md(tmp_path: Path) -> Path:
    """Create a sample spec.md file."""
    content = textwrap.dedent("""\
    # Feature Specification: My Feature

    ## Overview

    This feature adds unit testing support to the project.

    ## User Stories

    ### US1: Test Runner [P1]

    **As a** developer,
    **I want** to run tests easily,
    **So that** I can verify code quality.

    **Acceptance Criteria:**
    - [ ] Tests run with `make test`
    - [ ] Coverage report generated

    ### US2: Test Fixtures [P2]

    **As a** developer,
    **I want** reusable test fixtures,
    **So that** I can write tests faster.

    **Acceptance Criteria:**
    - [ ] Shared conftest.py
    - [ ] Temporary directory fixtures

    ## Requirements

    | ID | Description | Priority | Story |
    |----|-------------|----------|-------|
    | R1 | Tests must run in < 30s | Must | US1 |
    | R2 | Support pytest markers | Should | US1 |
    | R3 | Fixture autodiscovery | Could | US2 |

    ## Edge Cases

    | Scenario | Handling |
    |----------|----------|
    | No tests found | Show warning |
    | Import errors | Report clearly |

    ## Out of Scope

    - Performance benchmarks
    - Browser testing

    ## Success Criteria

    - All tests pass
    - Coverage > 80%

    ## Open Questions

    - Should we require minimum coverage?
    """)
    spec_file = tmp_path / "spec.md"
    spec_file.write_text(content)
    return spec_file


# --------------------------------------------------------------------------- #
# Missing-binary skips are REPORTED, not merely correct (issue #926)
# --------------------------------------------------------------------------- #
# A guard turns a vacuous PASS into a SKIP. That is strictly better and it is not
# sufficient: `make test` sits inside `make verify`, the gate a worker reads
# before pushing, and pytest's summary is read as "N passed" while M skipped goes
# uncounted. So an unexercised lane still ships behind a green - the same defect
# one level up, in the aggregate the reader actually sees.
#
# MEASURED, which is why this exists rather than a comment saying "remember to
# check skips": `TestPsFallbackWatcherIdentityAcrossDirectories` forces the `ps`
# lane and asserts it reports `unknown`. With `ps` absent the lane reports
# `unknown` for an unrelated reason, so the class PASSED on a host without the
# binary it forces. Guarding it makes it SKIP. Without this hook, that skip is
# invisible in `make verify`, and "the ps lane is unexercised on this host" and
# "the ps lane works" render identically.
#
# The binary set is IMPORTED from the gate rather than restated here. A second
# list is a second population to keep in sync, and this one would drift silently
# the moment `GUARDED_BINARIES` grows.
def _guarded_binaries() -> frozenset[str]:
    import importlib.util
    import sys

    # REPO_ROOT, not `Path(__file__)` (issue #1341): in a `pytester` sub-run this
    # file is a copy in a temporary directory, and the gate is not beside it.
    gate = REPO_ROOT / "scripts" / "check-test-binary-guards.py"
    try:
        spec = importlib.util.spec_from_file_location("_cpp_binary_guards", gate)
        if spec is None or spec.loader is None:
            return frozenset()
        module = importlib.util.module_from_spec(spec)
        sys.modules["_cpp_binary_guards"] = module
        spec.loader.exec_module(module)
        return frozenset(module.GUARDED_BINARIES)
    except Exception:
        # Reporting must never be the reason a suite fails. An unreadable gate
        # means no attribution, and the header below says so rather than
        # printing a confident zero.
        return frozenset()


def attribute_missing_binary_skips(
    reasons: list[str], binaries: frozenset[str]
) -> dict[str, int]:
    r"""Count skip reasons naming an absent binary. Pure, so it is testable.

    Extracted from the hook rather than left inline: a hook that reports
    "missing-binary skips" and actually counts EVERY skip is indistinguishable
    from a correct one on any run where all skips happen to be binary-related,
    which is most runs. The negative case needs a committed test, and a committed
    test needs a function to call.

    The boundary is `[\w-]` on both sides rather than `\b`, because `\b` treats a
    hyphen as a boundary: "no-ps-here" would count as naming `ps`. Both cases are
    pinned by test rather than left to this comment.
    """
    counts: dict[str, int] = {}
    for reason in reasons:
        for name in binaries:
            if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", reason):
                counts[name] = counts.get(name, 0) + 1
    return counts


def unattributed_skip_reasons(
    reasons: list[str], binaries: frozenset[str]
) -> list[str]:
    r"""Skip reasons naming NO guarded binary. Pure, so it is testable.

    THE COMPANION HALF, and the reason it exists (issue #1157). The hook above
    reports skips it can attribute to an absent binary and returns silently when
    there are none, so a skip meaning "I could not evaluate this" renders in the
    summary as a bare `1 skipped` - byte-identical to one meaning "not
    applicable on this machine". The distinction those two need is the whole
    subject of the issue this was found in: an unknowable answer must not read
    as a clean one, and a test that declined to run must not read as a test that
    ran.

    MEASURED, which is how it was found rather than reasoned about: a race in
    `tests/test_negative_controls.py` made one test render UNRESOLVED and skip on
    EVERY full run. The suite reported `5478 passed, 2 skipped`, twice, and two
    clean runs were nearly accepted as evidence for a subject that never
    executed. Nothing in the summary said which test, or why.

    Shares the sibling's boundary rule so the two partition the same population:
    every reason is in exactly one of them.

    WHAT THIS DOES NOT ESTABLISH, and the report is worded to match (#1157
    counter-model review, MEDIUM). Name matching decides membership; it does not
    decide CAUSE, and it errs in both directions:

      - a reason that NAMES a guarded binary without absence being the cause -
        "git is installed but the required commit is missing" - is counted by
        the sibling as a missing-binary skip and never reaches this list;
      - a reason about a binary that is simply not in `GUARDED_BINARIES` -
        "requires bash on PATH" - lands here, and it IS an absent-binary skip.

    So this is the set the classifier could not attribute, not the set that is
    "not about a binary". Claiming the second would be the membership-floor and
    ownership-boundary failures that `docs/agents/detector-contracts.md` asks of
    any check - in a hook that exists to stop a skip being read as a pass.
    """
    return [
        reason
        for reason in reasons
        if not any(
            re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", reason)
            for name in binaries
        )
    ]


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:  # noqa: ARG001
    """Name and count the skips caused by a binary being absent."""
    # FIRST, and before any early return: an unarmed host-install guard (#1232)
    # must be reported on a run with no skips at all, which is the ordinary run.
    # The blocks below return early when `skipped` is empty, so anything printed
    # after them is printed only on runs that happened to skip something.
    for why in _HOST_INSTALL_GUARD_UNARMED:
        terminalreporter.write_line(
            "host-install guard: NOT ARMED - the suite could write to the host's "
            f"~/.codex/skills and nothing would stop it ({why}). This run proved "
            "nothing about that (issue #1232).",
            red=True,
        )

    # The cross-run sweep (#1271), also before any early return. Silent when it
    # found nothing: that is every ordinary run, and the sweep's own tests are
    # what prove it can find something.
    if "error" in _SWEEP_REPORT:
        terminalreporter.write_line(
            f"supervise sweep: DID NOT RUN ({_SWEEP_REPORT['error']}) - daemons orphaned "
            "by earlier interrupted runs were not looked for (issue #1271).",
            yellow=True,
        )
    if _SWEEP_REPORT.get("reaped"):
        terminalreporter.write_line(
            f"supervise sweep: reaped {len(_SWEEP_REPORT['reaped'])} supervise daemon(s) "
            f"left by an earlier pytest run that died mid-test: {_SWEEP_REPORT['reaped']} "
            "(issue #1271).",
            yellow=True,
        )
    if _SWEEP_REPORT.get("survivors"):
        terminalreporter.write_line(
            f"supervise sweep: could NOT kill orphaned daemon(s) {_SWEEP_REPORT['survivors']} "
            "- they are still running (issue #1271).",
            red=True,
        )

    skipped = terminalreporter.stats.get("skipped", [])
    if not skipped:
        return

    binaries = _guarded_binaries()
    if not binaries:
        terminalreporter.write_line(
            "missing-binary skips: UNKNOWN - could not read GUARDED_BINARIES from "
            "scripts/check-test-binary-guards.py, so skips were not attributed",
            yellow=True,
        )
        return

    reasons = []
    for report in skipped:
        longrepr = getattr(report, "longrepr", None)
        if isinstance(longrepr, tuple) and len(longrepr) == 3:
            reasons.append(str(longrepr[2]))
    counts = attribute_missing_binary_skips(reasons, binaries)

    if counts:
        total = sum(counts.values())
        detail = ", ".join(f"{name}={counts[name]}" for name in sorted(counts))
        terminalreporter.write_line(
            f"missing-binary skips: {total} test(s) did not run because a binary is "
            f"absent ({detail}). Those lanes are UNEXERCISED here, not verified.",
            yellow=True,
        )

    # NAMED, NOT COUNTED (issue #1157). The block above used to `return` when it
    # could attribute nothing, so every skip that is not about an absent binary
    # reached the reader as a bare `N skipped` - and "I could not evaluate this"
    # renders there identically to "not applicable on this machine". The first
    # of those is action-required and the second is not.
    #
    # The reason text is what distinguishes them and pytest prints it only under
    # `-rs`, which `make verify` does not pass. So it is printed here, where the
    # summary already is, rather than left to a flag nobody remembers.
    unattributed = unattributed_skip_reasons(reasons, binaries)
    if unattributed:
        terminalreporter.write_line(
            f"unattributed skips: {len(unattributed)} test(s) this hook could not attribute to "
            "a guarded binary. That is a statement about THIS CLASSIFIER, not about the cause - "
            "read the reason. A skip is not a pass:",
            yellow=True,
        )
        for reason in unattributed:
            first = reason.strip().splitlines()[0] if reason.strip() else "(no reason given)"
            terminalreporter.write_line(
                f"    {first[:160]}{'...' if len(first) > 160 else ''}", yellow=True
            )


# --------------------------------------------------------------------------- #
# An owned CPP checkout for tests that run the REAL gate (issue #1718)
# --------------------------------------------------------------------------- #
# Two tests run the shipped finish path, which does
# `uv run --python 3.11 --no-python-downloads --project "$CPP_DIR"`. They used
# to pass the checkout the suite itself is running from as that directory. uv
# then makes that checkout's `.venv` match the 3.11 pin: where the `.venv` was
# first built by a plain `uv run` on another minor (3.12 on a host that has
# both), uv REMOVES it and recreates it - mid-suite, under the feet of every
# test still to run. One of the two runs offline with an empty cache, so the
# rebuilt environment stayed empty and 274 later tests failed with
# "No module named 'yaml'". The other rebuilt it without the dev extra and
# passed, having removed pytest from the environment running it.
#
# A test must not rebuild the environment it is running in. So the gate is
# pointed at a COPY of the working tree's `lib/`, `scripts/`, `pyproject.toml`
# and `uv.lock`, with its own 3.11 environment built once per session. It is a
# copy of the WORKING TREE, not of HEAD, so it still tests what is being edited.

_OWNED_CPP_PARTS = ("pyproject.toml", "uv.lock", "lib", "scripts")


def venv_fingerprint(venv: Path) -> tuple[str, tuple[tuple[str, int], ...]] | None:
    """What a virtual environment holds, read without running anything through
    uv: the interpreter its `pyvenv.cfg` names (version and home), and each
    site-packages entry with the number of files under it. None when there is
    no environment at that path. Read from the files directly - `uv run`
    repairs an environment before running a check in it, so a check made
    through uv cannot see one that was emptied.

    Two equal readings say the version, the home, the entry names and their
    file counts did not change between them. They do not say the environment
    works, and a difference does not say which process made it."""
    cfg = venv / "pyvenv.cfg"
    if not cfg.is_file():
        return None
    fields = {}
    for line in cfg.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep:
            fields[key.strip()] = value.strip()
    version = fields.get("version_info") or fields.get("version") or "?"
    interpreter = f"{version} at {fields.get('home', '?')}"
    entries: dict[str, int] = {}
    for site in venv.glob("lib/python*/site-packages"):
        for entry in site.iterdir():
            # Bytecode caches are written by the interpreter as it imports, so
            # they are not evidence of anything a test did.
            if entry.name == "__pycache__":
                continue
            if entry.is_dir():
                count = sum(1 for p in entry.rglob("*")
                            if p.is_file() and p.suffix != ".pyc")
            else:
                count = 1
            entries[entry.name] = entries.get(entry.name, 0) + count
    return interpreter, tuple(sorted(entries.items()))


# --- a partial clone turns a read of git history into a network request -------
#
# CI clones with `--depth=1 --filter=tree:0`. In such a clone, reading an
# object that is not present makes git fetch it from the remote, per read, so
# a test that reads real history there takes as long as the remote takes to
# answer (issue #1718: pipeline 3760 lost a test to its 120 second limit that
# takes 0.4 seconds in a full checkout). The comparison that needs the network
# belongs to the `negative-controls` CI step, where it is counted.

PARTIAL_CLONE_SKIP_REASON = (
    "partial clone: real-history comparison is done by the negative-controls CI step on pull requests"
)


def is_partial_clone(root: Path) -> bool:
    """Whether `root`'s repository is a partial clone, read from git's own
    configuration: a promisor remote, or `extensions.partialclone`. Only those
    two facts answer yes. A configuration git cannot read, or any other
    failure of the question, is an error - never a quiet no, and never a skip."""
    import subprocess

    # Outside a repository `git config` still answers, from the user's own
    # configuration, with a clean "no such key". That is not an answer about
    # `root`, so ask first whether there is a repository there at all.
    inside = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-dir"],
                            capture_output=True, text=True, timeout=30, check=False)
    assert inside.returncode == 0, (
        f"git could not say whether {root} is a partial clone: it is not a repository git can read "
        f"(exit {inside.returncode}): {inside.stderr.strip()[-300:]}")
    for args in (["--get-regexp", r"^remote\..*\.promisor$"], ["--get", "extensions.partialclone"]):
        asked = subprocess.run(["git", "-C", str(root), "config", *args],
                               capture_output=True, text=True, timeout=30, check=False)
        if asked.returncode == 0:
            if args[0] == "--get" or any(line.split()[-1].lower() == "true"
                                         for line in asked.stdout.splitlines() if line.split()):
                return True
            continue
        # `git config` exits 1 for "no such key": the one clean no.
        assert asked.returncode == 1 and not asked.stderr.strip(), (
            f"git could not say whether {root} is a partial clone "
            f"(exit {asked.returncode}): {asked.stderr.strip()[-300:]}")
    return False


def skip_in_partial_clone(root: Path) -> None:
    """Skip the calling test, with the reason that names who compares instead,
    when and only when `root` is a partial clone."""
    if is_partial_clone(root):
        pytest.skip(PARTIAL_CLONE_SKIP_REASON)


# CI's `validate` step runs the suite as ROOT (uid 0): the step's image sets no
# user and `.woodpecker.yml` names none, so `tmp_path` there is under
# `/tmp/pytest-of-root/` (first recorded in pipeline 2248; issue #1718, row 11).
#
# What follows from it. Root reads, writes and traverses a path whatever its
# mode, so a fixture that LOWERS A MODE (chmod 000, 0o555, 0o400) to build an
# unreadable, unwritable or untraversable path builds nothing there: the path
# stays usable and the code under test never meets the condition. Such a
# fixture must either skip under root, or assert its precondition (try the
# access it meant to forbid) before exercising the code - and a test that skips
# for this reason does NOT run in CI at all, only on a developer host.
#
# This is a DECLARATION, not a predicate: tests keep their own root handling.
# `tests/test_ci_runs_as_root_declared.py` compares it with the real uid when
# the suite runs in CI, so a change of CI user reds that test instead of
# silently changing which fixtures skip.
CI_RUNS_AS_ROOT = True


# What a child that runs uv on a project of the test's own may INHERIT. Built
# from nothing, by name: stripping the uv settings one knows about leaves the
# ones one does not, and uv reads more than fifty.
_UV_CHILD_INHERITS = (
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR",
    # where uv keeps its installed interpreters and its download cache
    "UV_PYTHON_INSTALL_DIR", "XDG_DATA_HOME", "XDG_CACHE_HOME",
    # reaching the package index from behind a proxy or a private CA
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    "SSL_CERT_FILE", "SSL_CERT_DIR",
)


def uv_child_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """The environment for a child that runs uv on a project of the test's
    own: only the names in `_UV_CHILD_INHERITS`, taken from `environ`. Nothing
    inherited can then tell uv WHICH project, directory, environment,
    interpreter or configuration to use - an inherited `UV_PROJECT` or
    `UV_WORKING_DIR` (or older `UV_WORKING_DIRECTORY`) sends a nested `uv run`
    back to the checkout the suite
    runs from, whatever `--project` the outer call named. A test then sets the
    uv settings it means to."""
    source = os.environ if environ is None else environ
    return {key: source[key] for key in _UV_CHILD_INHERITS if key in source}


def find_python(uv: str, env: Mapping[str, str], minor: str) -> Path:
    """The host's Python `minor`, or a skip when uv says it has none. Any
    OTHER failure of the question (a configuration uv cannot read, a crash) is
    an error: read as "no interpreter" it would turn the tests off."""
    import subprocess

    probe = subprocess.run(
        [uv, "python", "find", minor, "--no-python-downloads"],
        env=dict(env), capture_output=True, text=True, timeout=60, check=False,
    )
    if probe.returncode != 0 and "No interpreter found" in probe.stderr:
        pytest.skip(f"requires a Python {minor} interpreter; discovery forbids downloads")
    assert probe.returncode == 0, (
        f"uv could not answer whether Python {minor} is installed (exit {probe.returncode}): "
        f"{probe.stderr.strip()[-400:]}")
    return Path(probe.stdout.strip())


def find_python_311(uv: str, env: Mapping[str, str]) -> Path:
    return find_python(uv, env, "3.11")


def build_owned_cpp_checkout(root: Path, dest: Path) -> Path:
    """Copy `root`'s CPP runtime to `dest` and build its Python 3.11
    environment there. Skips ONLY for a missing prerequisite (uv, or a 3.11
    interpreter); once both are present a build that fails is an error."""
    import shutil
    import subprocess

    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("requires uv to build an owned CPP environment")
    dest.mkdir()
    for part in _OWNED_CPP_PARTS:
        source = root / part
        if source.is_dir():
            shutil.copytree(source, dest / part, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(source, dest / part)
    env = uv_child_env()
    # The ONE prerequisite that may skip: no Python 3.11 on this host. Asked
    # separately, so that a build that fails for any other reason (a broken
    # lock, an unsatisfiable dependency) is an ERROR and not a quiet skip.
    find_python_311(uv, env)
    built = subprocess.run(
        [uv, "sync", "--python", "3.11", "--no-python-downloads", "--project", str(dest)],
        env=env, capture_output=True, text=True, timeout=110, check=False,
    )
    assert built.returncode == 0, (
        "uv and Python 3.11 are present, but the owned CPP environment did not build "
        f"(exit {built.returncode}): {built.stderr.strip()[-600:]}"
    )
    assert venv_fingerprint(dest / ".venv") is not None, "the owned environment was not created"
    return dest


@pytest.fixture(scope="session")
def owned_cpp_checkout(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of this checkout's CPP runtime with its own Python 3.11
    environment, for a test that must run the real gate."""
    return build_owned_cpp_checkout(
        Path(__file__).resolve().parents[1],
        tmp_path_factory.mktemp("owned-cpp") / "claude-power-pack")
