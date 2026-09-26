"""A restored mutation must never be served a stale `.pyc` (issue #1259).

CPython validates a source-adjacent `__pycache__/*.pyc` on (source mtime in
whole seconds, source size) only. A negative-control red run mutates a script
without changing its length - `+= 1` -> `+= 0` - runs the suite, and `cp`s the
snapshot back within the same second. The cache is then valid by both criteria
and the MUTANT keeps executing against restored source (observed on #1034/PR
#1115 and #1235/PR #1244). The mirror case - a restored fix reading red, or a
mutant reading green - is what makes a negative control say the opposite of
what happened.

`tests/conftest.py` relocates the cache for the whole session, so the
source-adjacent `__pycache__` is never consulted. These tests plant exactly the
stale artifact that bit, and ask which code runs.
"""

from __future__ import annotations

import importlib.util
import os
import py_compile
import sys
from pathlib import Path


def _legacy_pyc(source: Path) -> Path:
    """Where CPython looks WITHOUT a pycache prefix - computed by hand, because
    `importlib.util.cache_from_source` already honours the prefix under test."""
    return source.parent / "__pycache__" / f"{source.stem}.{sys.implementation.cache_tag}.pyc"


def _load(source: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_size_preserving_mutant_pyc_is_not_executed(tmp_path: Path) -> None:
    source = tmp_path / "subject.py"
    stamp = 1_700_000_000

    # The red run: a mutant of IDENTICAL length, compiled to the legacy cache.
    source.write_text("VALUE = 0\n")
    os.utime(source, (stamp, stamp))
    py_compile.compile(str(source), cfile=str(_legacy_pyc(source)), doraise=True)

    # The restore: same length, same whole-second mtime - the cache still
    # "matches" by every criterion CPython checks.
    source.write_text("VALUE = 1\n")
    os.utime(source, (stamp, stamp))
    assert _legacy_pyc(source).is_file(), "precondition: the stale cache must exist"

    module = _load(source, "pycache_isolation_subject")
    assert module.VALUE == 1, (
        "the restored source is not what ran: a stale source-adjacent .pyc was "
        "served, so a negative-control red run can report the MUTANT's verdict"
    )


def test_the_cache_is_relocated_for_subprocesses_too() -> None:
    """A test that runs `python3 scripts/x.py` imports `lib/*` in a CHILD, which
    reads the source-adjacent cache unless the prefix travels in the env."""
    prefix = os.environ.get("PYTHONPYCACHEPREFIX", "")
    assert prefix, "PYTHONPYCACHEPREFIX is not exported to child processes"
    assert sys.pycache_prefix == prefix
    repo = Path(__file__).resolve().parents[1]
    assert not Path(prefix).resolve().is_relative_to(repo), (
        "the relocated cache lives inside the checkout, where it outlives the run"
    )
