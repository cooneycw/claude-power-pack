"""Run mypy on the repository's DECLARED scope, else on `.` (issue #1258).

Invoked by the finish/check plans' typecheck fallback as

    python3 <cpp>/lib/cicd/mypy_scope.py uv run --extra dev mypy

and execs that command unchanged when the active mypy config declares
``files``, or with ``.`` appended when it does not. mypy reads ``files`` from
its own config when given no paths, so a declared scope is honoured by passing
none.

WHY A FILE AND NOT INLINE SHELL. The fallback slot of a generated gate command
may not contain ``;``, ``&``, ``|`` or a backtick - `command_runs_make_target`
refuses a slot that could chain, because it is the one place caller text reaches
an accepted command. A shell probe needs all of those, so it cost the typecheck
gate its subsumption under `make verify` and ran it twice. This is one plain
command. Run by PATH, never ``-m``: ``-m`` needs PYTHONPATH, which the runner
strips from child steps on purpose (#534).

THE RULE is the same one `models.MYPY_DECLARED_FILES_PROBE` encodes for
generated Makefiles (which must be self-contained, so cannot call this file):
the FIRST of mypy.ini, .mypy.ini, pyproject.toml, setup.cfg that carries a
``[mypy]`` / ``[tool.mypy]`` section is the active config, as in mypy itself; a
``files`` key in that section is a declared scope. tests/test_runner.py runs
both implementations over the same cases so they cannot drift.

Stdlib only and line-based (no tomllib): the host ``python3`` may predate 3.11.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

CONFIG_ORDER = ("mypy.ini", ".mypy.ini", "pyproject.toml", "setup.cfg")
_HEADER = re.compile(r"^\s*\[")
_MYPY_HEADER = re.compile(r"^\s*\[(tool\.)?mypy\]\s*(#.*)?$")
# `files = x` / `files: x` (INI accepts both delimiters) and TOML's quoted-key
# spelling `"files" = [...]` (counter-model review, pass 2).
_FILES_KEY = re.compile(r'^\s*"?files"?\s*[=:]')


def _section_state(text: str) -> str:
    """``files`` / ``nofiles`` for a file with a mypy section, else ``none``."""
    in_mypy = seen = has_files = False
    for line in text.splitlines():
        if _HEADER.match(line):
            in_mypy = bool(_MYPY_HEADER.match(line))
            seen = seen or in_mypy
        elif in_mypy and _FILES_KEY.match(line):
            has_files = True
    if not seen:
        return "none"
    return "files" if has_files else "nofiles"


def declares_files(root: Path) -> bool:
    """True when the config mypy would use declares ``files``."""
    for name in CONFIG_ORDER:
        path = root / name
        if not path.is_file():
            continue
        state = _section_state(path.read_text(encoding="utf-8", errors="replace"))
        if state != "none":
            return state == "files"
    return False


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: mypy_scope.py <command...>", file=sys.stderr)
        return 2
    command = list(argv) if declares_files(Path.cwd()) else [*argv, "."]
    os.execvp(command[0], command)
    return 127  # pragma: no cover - execvp does not return


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
