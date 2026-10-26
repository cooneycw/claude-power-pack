"""Guard the documented ``lib.cicd verify`` invocation on every command surface (issue #595).

``lib/cicd`` is a package inside the CPP checkout, not an installed
distribution, so a documented invocation has exactly two ways to be wrong - and
both shipped for months in the deploy-verification path:

1. ``PYTHONPATH`` pointed INSIDE ``lib/`` instead of at its parent, so
   ``-m lib.cicd`` cannot resolve the package at all.
2. bare ``python3`` instead of ``uv run --project "$CPP_DIR"``, so the system
   interpreter (often 3.10, no venv) runs it and ``pydantic`` is missing.

Issue #430 fixed both in the ``/flow:auto`` Step 6 quality gate; Step 9's
``verify`` calls - and their ``/flow:deploy`` and ``/cicd:verify`` siblings -
were never updated alongside it. The failure prints to stderr mid-deploy and is
easy to narrate past, so it was captured in the friction buffer twice, months
apart, before anyone applied the recorded fix. This test is the gate that stops
a third recurrence: the invocation contract is asserted, not remembered.

SCOPE - deliberately narrow, and narrower than the defect. Only ``lib.cicd
verify`` lines are checked, because that is the deploy-verification gate #595
covers. The SAME broken ``PYTHONPATH="$CPP_DIR/lib"`` + bare-``python3`` shape
still appears on ~40 other ``lib.cicd`` lines across the ``cicd``, ``cpp``,
``codex`` and ``project`` command families (``detect``, ``check``, ``health``,
``smoke``, ``pipeline``, ``infra-*``, ``run --plan``). Those are a real latent
bug, not an oversight of this test - fixing them is a repo-wide sweep that
belongs in its own issue. Widening the patterns below is the intended way to
land that sweep.

Offline and stdlib-only by design: this reads markdown and shells out to
nothing. The Woodpecker ``validate`` container ships no git/docker/curl, and an
unguarded shell-out turns CI red even when it passes locally (#451/#489).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The surfaces that document how to run lib/cicd. `.claude/commands/` is the
# single source of truth; `codex/skills/` is generated from it
# and are included so a stale regenerated copy is caught too. CHANGELOG.md is
# deliberately excluded - it quotes historical commands as a record of what
# changed, and editing history to satisfy a lint is the wrong fix.
SURFACES = (".claude/commands", "plugins", "codex/skills")

# Only lines that actually invoke the verify subcommand (see SCOPE above).
VERIFY_LINE = re.compile(r"-m lib\.cicd verify\b")
BARE_PYTHON = re.compile(r"\bpython3\b")
PYTHONPATH_INTO_LIB = re.compile(r'PYTHONPATH="\$CPP_DIR/lib')
# Explicit approved shapes only: legacy commands and the CPP-specific isolated runner.
LEGACY_VERIFY = 'PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" python -m lib.cicd verify'
CPP_VERIFY = (
    'PYTHONPATH="$CPP_DIR:$PYTHONPATH" env -u UV_PROJECT_ENVIRONMENT '
    '"CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT-}" '
    '"CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT_PRESENT=${UV_PROJECT_ENVIRONMENT+x}" '
    'uv run --python 3.11 --no-python-downloads --project "$CPP_DIR" python -m lib.cicd verify'
)
VERIFY_PREFIXES = (LEGACY_VERIFY, CPP_VERIFY)
CORRECT_UV = re.compile(r"(?:" + re.escape(LEGACY_VERIFY.split(" ", 1)[1]) + "|" + re.escape(CPP_VERIFY) + r")\b")


def _markdown_files() -> list[Path]:
    files: list[Path] = []
    for surface in SURFACES:
        base = ROOT / surface
        if base.is_dir():
            files.extend(sorted(base.rglob("*.md")))
    return files


def _verify_lines() -> list[tuple[str, str]]:
    """Every (location, text) pair that invokes `-m lib.cicd verify`."""
    found = []
    for path in _markdown_files():
        rel = path.relative_to(ROOT)
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if VERIFY_LINE.search(line):
                found.append((f"{rel}:{lineno}", line.strip()))
    return found


VERIFY_LINES = _verify_lines()
_IDS = [loc for loc, _ in VERIFY_LINES]


def test_scan_found_verify_invocations():
    """An empty sweep proves nothing - fail loudly if the surfaces moved."""
    assert VERIFY_LINES, (
        f"no `-m lib.cicd verify` lines found under {SURFACES} - either the command "
        "surfaces moved or the pattern went stale; this guard would pass vacuously"
    )


@pytest.mark.parametrize(("location", "line"), VERIFY_LINES, ids=_IDS)
def test_pythonpath_points_at_cpp_dir_not_lib(location: str, line: str):
    """PYTHONPATH must be the PARENT of lib/, or `-m lib.cicd` cannot resolve."""
    assert not PYTHONPATH_INTO_LIB.search(line), (
        'PYTHONPATH must be "$CPP_DIR:$PYTHONPATH" (the parent of lib/), not '
        f'"$CPP_DIR/lib" (issue #595):\n  {location}: {line}'
    )


@pytest.mark.parametrize(("location", "line"), VERIFY_LINES, ids=_IDS)
def test_verify_runs_through_uv(location: str, line: str):
    """`lib.cicd verify` must run through uv, not the bare system interpreter."""
    assert not BARE_PYTHON.search(line), (
        'run verify via `uv run --project "$CPP_DIR" python -m lib.cicd verify`, not '
        f"bare python3 - the system interpreter has no pydantic (issue #595):\n  {location}: {line}"
    )
    assert CORRECT_UV.search(line), (
        "expected the canonical invocation "
        '`uv run --project "$CPP_DIR" python -m lib.cicd verify` (issue #595):\n  '
        f"{location}: {line}"
    )


@pytest.mark.parametrize("prefix", VERIFY_PREFIXES)
def test_verify_guard_accepts_both_explicit_shapes(prefix):
    assert CORRECT_UV.search(prefix)


@pytest.mark.parametrize(
    "bad",
    [
        CPP_VERIFY.replace("--python 3.11", "--python 3.12"),
        CPP_VERIFY.replace("--no-python-downloads ", ""),
        CPP_VERIFY.replace("env -u UV_PROJECT_ENVIRONMENT ", ""),
        CPP_VERIFY.replace('"$CPP_DIR" python', '"$OTHER_PROJECT" python'),
        LEGACY_VERIFY.replace("uv run --project", "python3 --project"),
    ],
)
def test_verify_guard_rejects_mutated_shapes(bad):
    assert not CORRECT_UV.search(bad)


def test_guard_control_distinguishes_its_committed_blind_pattern():
    blind = re.compile((ROOT / "tests/fixtures/step9_verify_contract/blind_uv_pattern.txt").read_text().strip())
    assert blind.search(CPP_VERIFY) and CORRECT_UV.search(CPP_VERIFY)
    bad = CPP_VERIFY.replace("--no-python-downloads ", "")
    assert blind.search(bad) and not CORRECT_UV.search(bad)
