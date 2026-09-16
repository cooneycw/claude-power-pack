#!/usr/bin/env python3
"""eli5-vendor.py - guard the canonical -> vendored link for the eli5 gate core.

CPP's ``/flow:eli5`` vendors its core - the section between the
``eli5-core:begin`` / ``eli5-core:end`` markers - verbatim from the canonical
standalone repo https://github.com/cooneycw/eli5-gate (extracted in #443). That
link had a drift script but no automation of any kind: no CI step, no Makefile
target, no test (issue #591). Advisory-by-design is fine; advisory-and-never-run
is decoration.

THIS FILE IS NOW A DECLARATION. The fetch/compare/report/re-vendor machinery
moved to ``lib/vendor.py`` in issue #1012, where it is shared with
``project-next-vendor.py``; what is left here is what is actually specific to
this link - the canonical repo, the manifest, the marker pair, and the prose a
reader needs when the gate fires. A third external core costs a file this size,
not another ~290 lines.

Three modes, unchanged in name, exit code and CLI:

    eli5-vendor.py              offline hard gate (CI `eli5-vendor-check`)
    eli5-vendor.py --upstream   live diff, advisory + fail-open
    eli5-vendor.py --revendor   re-fetch, replace in place, re-pin the manifest
    eli5-vendor.py --root DIR   operate on another tree (fixtures, controls)

Reconcile drift by editing the CANONICAL repo first, then re-vendoring here.
After a re-vendor, refresh the generated surfaces:
    python3 scripts/codex-skill-sync.py --write flow
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# `.resolve()` first, so this works through the ~/.claude/scripts SYMLINK as
# well as from the checkout: sys.path[0] is the directory of the path as
# INVOKED, which for a symlinked helper is ~/.claude/scripts, where lib/ does
# not exist.
sys.path.insert(0, str(REPO_ROOT))

from lib.vendor import (  # noqa: E402 - the path insert above must precede this
    CoreNotFound,
    Fetcher,
    MarkerSectionLayout,
    VendorSpec,
    extract_marker_section,
    run,
)

#: NEGATIVE-CONTROL: controls/eli5-vendor
#:     Registered per issue #1012. This gate lets work THROUGH - CI's
#:     `eli5-vendor-check` step reads its green as "the vendored core is still
#:     what upstream published", and nothing downstream re-derives that. A blind
#:     version prints the same clean line while the core quietly diverges, which
#:     is the pre-#591 state, where the drift script existed and was invoked by
#:     nothing at all.
#:
#:     It could not be registered before #1012: the manifest path and repo root
#:     were module-level constants, so the gate could not be aimed at a known-bad
#:     tree and its green had never been shown to be falsifiable. `--root` is
#:     what changed that, and is the reason the control is committed WITH the
#:     refactor rather than promised after it.

BEGIN_MARKER = "<!-- eli5-core:begin"
END_MARKER = "<!-- eli5-core:end"

SPEC = VendorSpec(
    name="eli5-vendor",
    subject="the vendored eli5 core",
    source_repo="https://github.com/cooneycw/eli5-gate",
    manifest_rel=".claude/eli5-vendor.json",
    layout=MarkerSectionLayout(
        begin_marker=BEGIN_MARKER,
        end_marker=END_MARKER,
        default_file=".claude/commands/flow/eli5.md",
        subject="vendored core",
        # Canonical coordinates as FALLBACKS, exactly as the pre-#1012 module
        # constants were. The manifest supplies both today; keeping the defaults
        # means a manifest that omits them still fetches, and the offline gate
        # never consults either.
        default_raw_url="https://raw.githubusercontent.com/cooneycw/eli5-gate/main/commands/eli5.md",
        default_commits_api=(
            "https://api.github.com/repos/cooneycw/eli5-gate/commits?path=commands/eli5.md&per_page=1"
        ),
    ),
    fetcher=Fetcher(user_agent="cpp-eli5-vendor", timeout=15),
    revendor_hint="make eli5-revendor",
    remedy=(
        "The core between the eli5-core markers was edited locally. That core is",
        "vendored from https://github.com/cooneycw/eli5-gate - edit it THERE first.",
        "If the local edit is the intended new content, the same target re-pins it.",
    ),
    revendor_next=("Next: python3 scripts/codex-skill-sync.py --write flow",),
    description="Guard the vendored eli5 gate core (issues #591, #1012).",
)


def extract_core(text: str) -> str:
    """The marker slice, kept as a named entry point for this link's markers."""
    return extract_marker_section(text, BEGIN_MARKER, END_MARKER)


def main(argv: list[str] | None = None) -> int:
    return run(SPEC, REPO_ROOT, argv)


__all__ = ["SPEC", "CoreNotFound", "REPO_ROOT", "extract_core", "main"]


if __name__ == "__main__":
    sys.exit(main())
