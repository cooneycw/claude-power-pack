#!/usr/bin/env python3
"""project-next-vendor.py - guard the codex-power-pack -> vendored project-next link.

CPP consumes the project-next decision contract from codex-power-pack while
shipping an always-present copy, so CI and local runs never depend on a sibling
checkout. The copy is deliberately boring: a fixed list of upstream files, each
pinned by its own sha256 in ``.claude/project-next-vendor.json``. Per-file pins
are the point - a failure names the exact drifted file rather than the tree.

THIS FILE IS NOW A DECLARATION. The fetch/compare/report/re-vendor machinery
moved to ``lib/vendor.py`` in issue #1012, where it is shared with
``eli5-vendor.py``. What stays here is what is specific to this link: which
files form the vendoring contract, where they come from, and the two invariants
that have no eli5 analogue (an unexpected-file scan, and a contract version
cross-checked against the vendored document rather than trusted from the
manifest).

Three modes, unchanged in name, exit code and CLI:

    project-next-vendor.py check       offline hard gate (`make verify`)
    project-next-vendor.py --upstream  live diff, advisory + fail-open
    project-next-vendor.py --revendor  re-fetch at an immutable commit, re-pin
    project-next-vendor.py --root DIR  operate on another tree (fixtures, controls)
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# `.resolve()` first, so this works through a symlinked copy as well as from the
# checkout: sys.path[0] is the directory of the path as INVOKED, not the real
# one, and lib/ sits beside the real one.
sys.path.insert(0, str(REPO_ROOT))

from lib.vendor import (  # noqa: E402 - the path insert above must precede this
    Fetcher,
    FileSetLayout,
    VendorSpec,
    run,
)

#: NEGATIVE-CONTROL: controls/project-next-vendor
#:     Registered per issue #1012. This gate lets work THROUGH - it is a
#:     prerequisite of `make verify` (ADR 0008 row 31), whose green is read as
#:     "the vendored engine is the one upstream published" by sessions that do
#:     not re-derive it. A blind version prints the same "16 files match" line
#:     over a tree that has drifted.
#:
#:     It could not be registered before #1012: VENDOR_ROOT and MANIFEST_PATH
#:     were module-level constants, so the gate could only ever read THIS
#:     repository and could not be aimed at a known-bad tree. `--root` is what
#:     made a committed case possible, which is why the control lands with the
#:     refactor rather than after it.

#: The vendoring contract: the HARDCODED UNIVERSE. The manifest supplies the
#: members and is refused if its key set differs, so a dropped pin cannot pass
#: as "nothing to check" and an extra one cannot smuggle a file in.
UPSTREAM_FILES = (
    "LICENSE",
    "docs/project-next-contract.md",
    "lib/project_next/__init__.py",
    "lib/project_next/classify.py",
    "lib/project_next/cli.py",
    "lib/project_next/collect.py",
    "lib/project_next/config.py",
    "lib/project_next/models.py",
    "lib/project_next/rank.py",
    "lib/project_next/render.py",
    "scripts/project-next.py",
    "tests/project_next/fixtures/scenarios.json",
    "tests/project_next/fixtures/golden/brief.txt",
    "tests/project_next/fixtures/golden/compact.md",
    "tests/project_next/fixtures/golden/full.md",
    "tests/project_next/fixtures/golden/result.json",
)

SOURCE_REPO = "https://github.com/cooneycw/codex-power-pack"

SPEC = VendorSpec(
    name="project-next-vendor",
    subject="the vendored project-next engine",
    source_repo=SOURCE_REPO,
    manifest_rel=".claude/project-next-vendor.json",
    layout=FileSetLayout(
        files=UPSTREAM_FILES,
        subtree="vendor/project_next",
        source_repo=SOURCE_REPO,
        api_root="https://api.github.com/repos/cooneycw/codex-power-pack",
        raw_root="https://raw.githubusercontent.com/cooneycw/codex-power-pack",
        # The version is DERIVED from the vendored document and compared with
        # the manifest, so editing the manifest alone cannot claim a contract
        # version the document does not carry.
        derived_field=("docs/project-next-contract.md", r"Contract version `(?P<version>[^`]+)`", "contract_version"),
    ),
    fetcher=Fetcher(user_agent="cpp-project-next-vendor", timeout=20),
    revendor_hint="make project-next-revendor",
    check_verb=True,
    description="Verify or refresh CPP's vendored project-next engine (issues #723, #1012).",
)


def main(argv: list[str] | None = None) -> int:
    return run(SPEC, REPO_ROOT, argv)


__all__ = ["SPEC", "REPO_ROOT", "UPSTREAM_FILES", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
