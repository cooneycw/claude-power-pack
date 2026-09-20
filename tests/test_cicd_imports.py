"""The runner must import without pydantic (issue #1163).

`lib/cicd/__init__.py` used to re-export sixteen submodules eagerly. Two import
pydantic and four more import `.config`, so `import lib.cicd.steps` pulled it in
whatever `steps` itself needed - and the negative-controls CI step runs an image
with no pydantic and no virtualenv. The consequence was that NO registered
control could exercise a gate whose path reaches `lib.cicd`, which is what #1163
is about.

Deferring the re-exports fixed it. This file is what stops it coming back: a new
eager `from .config import ...` at the top of `__init__.py` would silently take
the battery's reach away again, and nothing else in the suite would notice -
every other test runs under a virtualenv where pydantic is present, so the
broken and the working package are byte-identical there.

THE BLOCK IS A SUBPROCESS, NOT A MONKEYPATCH. `sys.modules` edits inside the
test process would leak into every later test in the session, and a package
already imported by an earlier test would satisfy the import from the module
cache regardless - so the check would pass whether or not the property held.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Blocking a package by name means blocking what it imports, too: pydantic's
# extension module `pydantic_core` is a separate top-level package, and leaving
# it importable would only move the failure rather than test for it.
_BLOCKED = ("pydantic", "pydantic_core")

# RAW, and that matters. The probe writes a Makefile, so the template contains
# `\n` and `\t`. In a non-raw string those are interpreted when _PROBE is BUILT,
# injecting real newlines with no indentation - and `textwrap.dedent` then finds
# a common prefix of "" and strips nothing, so every line reaches python3 with
# four leading spaces and it dies of IndentationError on line 2. Raw keeps them
# as two characters until the probe's own string literal is parsed by the child.
_PROBE = textwrap.dedent(
    r"""
    import sys

    # PRECONDITION FIRST. A None entry in sys.modules makes `import x` raise
    # ImportError, which is what the CI image's absence looks like from inside
    # the interpreter. Assert the block actually took: without this the probe
    # would pass on a machine where pydantic simply imports fine, and the test
    # would be measuring nothing.
    {block}
    try:
        import pydantic
    except ImportError:
        pass
    else:
        raise SystemExit("PRECONDITION FAILED: pydantic still importable")

    sys.path.insert(0, {root!r})

    import lib.cicd.steps as steps
    import lib.cicd.runner as runner

    # THE CLI ENTRY POINT, not just the modules. `scripts/flow-finish-gate.sh`
    # runs `python -m lib.cicd run`, so `__main__` -> `cli` is the path that has
    # to start - and `cli.py` is where seven module-scope imports reached
    # pydantic. A guard importing only steps and runner passes with an eager
    # config import restored in cli.py, which a counter-model review verified by
    # mutation: the property named and the property tested were different.
    import lib.cicd.__main__  # noqa: F401

    # CALLED, not merely callable. `callable(f)` is true of a function whose
    # body imports pydantic on first use, so the old assertion would hold for a
    # package that still cannot do the work in this environment.
    import tempfile
    from pathlib import Path

    scratch = Path(tempfile.mkdtemp())
    (scratch / "Makefile").write_text(
        "lint:\n\t@true\ntest:\n\t@true\ntypecheck:\n\t@true\n"
        "security_scan:\n\t@true\nverify: lint test typecheck\n\t@true\n"
    )
    resolved = [d.id for d in steps.get_plan_steps("finish", project_root=str(scratch))]
    assert resolved[:3] == ["lint", "test", "typecheck"], resolved
    covered, refusals = steps.subsumed_gate_ids(
        "finish", steps.get_plan_steps("finish", project_root=str(scratch)), str(scratch)
    )
    assert covered == {{"lint": "verify", "test": "verify", "typecheck": "verify"}}, covered
    # THE REFUSALS ARE ASSERTED TOO, not discarded (#1165). They are how the
    # derivation says it could NOT answer - `make` absent from this
    # environment, or an unreadable rule - and an empty mapping with a refusal
    # beside it is a DIFFERENT fact from an empty mapping with none. Binding
    # the tuple and checking only its first half would let this probe pass
    # while reporting that make could not be asked at all.
    assert refusals == [], refusals
    assert runner.DeterministicRunner is not None
    print("OK")
    """
)


_BLOCK = "\n    ".join(
    [f"for name in {_BLOCKED!r}:", "    sys.modules[name] = None"]
)
# The same probe with the block replaced by a no-op. Parameterised rather than
# edited by string surgery: an earlier cut commented out the loop header and
# took its colon with it, so the probe died of SyntaxError and the test read
# that as "the precondition did not fire" - passing for the wrong reason in the
# one test whose job is to prove the precondition works.
_NO_BLOCK = "pass  # deliberately not blocking, to prove the precondition fires"


def _run_probe(block: str = _BLOCK) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", _PROBE.format(block=block, root=str(ROOT))],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_steps_and_runner_import_without_pydantic() -> None:
    proc = _run_probe()
    assert "PRECONDITION FAILED" not in proc.stdout + proc.stderr, (
        "the probe could not block pydantic, so it proved nothing"
    )
    assert proc.returncode == 0, (
        "lib.cicd.steps / lib.cicd.runner cannot be imported without pydantic. "
        "Something at the top of lib/cicd/__init__.py imports it eagerly again, "
        "and the negative-controls battery can no longer exercise any control "
        "that reaches lib.cicd (issue #1163).\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    assert "OK" in proc.stdout


def test_the_block_itself_can_fail() -> None:
    """The probe's precondition is load-bearing, so prove it can fire.

    Without the block, `import pydantic` succeeds here and the probe must say
    so rather than sail past. A guard whose precondition cannot fail is a guard
    that reports the same thing whatever the tree does.
    """
    proc = _run_probe(block=_NO_BLOCK)
    assert "PRECONDITION FAILED" in proc.stdout + proc.stderr, (
        "with the block removed the probe still reported success, so its "
        "precondition assert is not doing anything"
    )


def test_a_manifest_that_cannot_be_read_is_refused_not_substituted() -> None:
    """A present manifest plus an unloadable reader must FAIL, not fall back.

    `get_plan_steps` caught ImportError and returned BUILTIN_PLANS. That was
    harmless only while the CLI could not start without pydantic - the process
    died before reaching it. #1163 removed that by design, which made the
    fall-through reachable and turned a loud failure into a SILENT SUBSTITUTION
    of a different plan.

    Measured on this repository with pydantic blocked, before the fix: `deploy`
    returned the built-in steps, losing `drift_check` and gaining
    `stale_commit_check`, with no warning and a successful run. Found by
    counter-model review of the very change that opened the path.
    """
    probe = textwrap.dedent(
        f"""
        import sys
        for name in {_BLOCKED!r}:
            sys.modules[name] = None
        sys.path.insert(0, {str(ROOT)!r})
        from lib.cicd.steps import get_plan_steps
        try:
            get_plan_steps("deploy", project_root={str(ROOT)!r})
        except RuntimeError as exc:
            assert "cicd_tasks.yml" in str(exc), exc
            print("REFUSED")
        else:
            raise SystemExit("FELL BACK: the built-in plan was substituted silently")
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, timeout=120
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "REFUSED" in proc.stdout


def test_no_manifest_still_uses_the_builtin_plans() -> None:
    """The guard rail: refusing must not become refusing everything.

    A project with no manifest has nothing to lose, and the built-in plans are
    the right answer there - which is the ordinary case for every repository
    the gate runs in without one.
    """
    probe = textwrap.dedent(
        f"""
        import sys, tempfile
        for name in {_BLOCKED!r}:
            sys.modules[name] = None
        sys.path.insert(0, {str(ROOT)!r})
        from lib.cicd.steps import get_plan_steps
        ids = [d.id for d in get_plan_steps("deploy", project_root=tempfile.mkdtemp())]
        assert ids, "no steps resolved"
        print("BUILTIN", ids[0])
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, timeout=120
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "BUILTIN" in proc.stdout
