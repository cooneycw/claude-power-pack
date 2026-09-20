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

_PROBE = textwrap.dedent(
    """
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

    # Not just importable - usable. The derivation is the path a control
    # actually takes, and an import that succeeds while the first call raises
    # would leave the battery exactly as unable to run one.
    assert callable(steps.subsumed_gate_ids)
    assert callable(steps.get_plan_steps)
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
