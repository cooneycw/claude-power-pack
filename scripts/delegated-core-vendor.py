#!/usr/bin/env python3
"""delegated-core-vendor.py - one shared lifecycle for the delegated drivers (issue #1011).

`/codex:auto`, `/qwen:auto` and `/gemma:auto` describe the SAME eight-step
lifecycle and used to describe it three times: 367-454 non-blank lines shared per
pair. That is not a tidiness complaint. When #774 found that all three printed a
Step 2 plan report that "reads exactly like a checkpoint and was not one", the
defect was present in three documents simultaneously and had to be fixed in three
documents; the test written to hold them together was itself deduplicated, with
the comment "two copies of this guard would drift, and the drift would be
silent", while the documents it guards were not. By the time this landed the
drift was already real: codex's Steps 6-8 carried ~60 lines qwen's and gemma's
never received.

So the lifecycle lives once, in templates/delegated-driver-core.md, and is
RENDERED into each driver between `delegated-core:begin` / `delegated-core:end`
markers - the same vendor-with-markers shape `/flow:eli5` uses for its gate text
(#443/#591), but intra-repo, which makes codex-skill-sync.py the closer
precedent: generation from a checked-in source, with a check that reports drift
rather than a network fetch.

Usage:
    delegated-core-vendor.py                 # check (default): exit 1 on drift
    delegated-core-vendor.py check
    delegated-core-vendor.py --write         # (re)render into the driver files
    delegated-core-vendor.py --root DIR      # operate on another tree (fixtures)

Verdicts on stdout. A malformed SOURCE is reported once and stops the run,
because nothing can be meaningfully compared against it:
    MISSING     a driver file, its values file, or a region's marker pair is absent
    ORPHAN      a values file declares a slot the core does not use
    UNRESOLVED  a region carries `{{...}}` residue no slot rule claimed - a
                mistyped slot name would otherwise render verbatim into three
                prompt documents and no check would say so
    MISORDERED  the regions are present and correct but in the wrong order, so
                the document describes the lifecycle out of sequence
    DRIFT       a rendered region's bytes differ from the render (per file)

Reconcile drift by editing templates/delegated-driver-core.md (shared text) or
templates/delegated-driver-values/<driver>.md (per-model text) and re-running
with --write - NEVER by editing the rendered region in the driver file, which is
the drift this exists to catch.

Stdlib-only, offline and git-free, so it gives the same verdict in the slim CI
image as it does here.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: NEGATIVE-CONTROL: controls/delegated-core-vendor

DRIVERS = ("codex", "qwen", "gemma")
REGIONS = ("A", "B")

CORE_REL = "templates/delegated-driver-core.md"
VALUES_REL = "templates/delegated-driver-values"
DRIVER_REL = ".claude/commands/{driver}/auto.md"

REGION_MARKER = re.compile(r"^<!-- region: ([AB]) -->$", re.MULTILINE)
SLOT_MARKER = re.compile(r"^<!-- slot: ([A-Z0-9_]+) -->$", re.MULTILINE)
PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
#: Deliberately LOOSER than PLACEHOLDER. A slot name typed in the wrong case
#: (`{{driver}}`) is not a placeholder by the rule above, so it survives
#: rendering as literal text - into three prompt documents, silently. Anything
#: brace-brace-shaped left after rendering is refused rather than shipped.
RESIDUE = re.compile(r"\{\{[^}\n]*\}\}")

BEGIN = "<!-- delegated-core:begin {region} (canonical: {core}) -->"
END = "<!-- delegated-core:end {region} -->"


class CoreError(Exception):
    """A malformed template or values file - a bug in the source, not drift."""


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def parse_regions(text: str) -> dict[str, str]:
    """Split the core template into its named regions.

    Everything before the first region marker is template preamble - authoring
    guidance for whoever edits the core - and is deliberately NOT rendered. That
    is also why the preamble may mention `{{NAME}}` without tripping UNRESOLVED.
    """
    marks = list(REGION_MARKER.finditer(text))
    if not marks:
        raise CoreError(f"{CORE_REL}: no '<!-- region: X -->' marker found")
    out: dict[str, str] = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end() + 1 : end]
        if body.endswith("\n"):
            body = body[:-1]
        if m.group(1) in out:
            raise CoreError(f"{CORE_REL}: region {m.group(1)} declared twice")
        out[m.group(1)] = body
    missing = [r for r in REGIONS if r not in out]
    if missing:
        raise CoreError(f"{CORE_REL}: missing region(s) {', '.join(missing)}")
    return out


def parse_slots(text: str, rel: str) -> dict[str, str]:
    """Read a values file into {slot: value}.

    The value is the EXACT text between one marker line and the next - nothing is
    stripped. A trailing blank line in the values file is a trailing blank line
    in the rendered document, which is how a slot carries the paragraph break its
    surroundings need. A marker immediately followed by the next marker is the
    empty value.
    """
    marks = list(SLOT_MARKER.finditer(text))
    if not marks:
        raise CoreError(f"{rel}: no '<!-- slot: NAME -->' marker found")
    out: dict[str, str] = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end() + 1 : end]
        if body.endswith("\n"):
            body = body[:-1]
        name = m.group(1)
        if name in out:
            raise CoreError(f"{rel}: slot {name} declared twice")
        out[name] = body
    return out


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def render(region_text: str, slots: dict[str, str], rel: str) -> tuple[str, set[str]]:
    """Substitute slots into one region. Returns (rendered, slots actually used).

    Two substitution shapes, distinguished by whether the placeholder is alone on
    its line:

    - BLOCK: `{{NAME}}` is the whole line. Its value's lines replace the line. An
      empty value removes the line entirely, so an optional paragraph leaves no
      blank behind.
    - INLINE: `{{NAME}}` sits inside a line. Its value is spliced in and must be a
      single line, or the surrounding sentence silently becomes two.
    """
    used: set[str] = set()
    out: list[str] = []
    for line in region_text.split("\n"):
        stripped = line.strip()
        m = PLACEHOLDER.fullmatch(stripped)
        if m and stripped != line:
            raise CoreError(
                f"{rel}: block slot {{{{{m.group(1)}}}}} is indented; a block slot "
                "must start at column 0, since its value's lines are inserted as "
                "written and would not inherit the indent"
            )
        if m:
            name = m.group(1)
            if name not in slots:
                raise CoreError(f"{rel}: no value for block slot {{{{{name}}}}}")
            used.add(name)
            if slots[name] != "":
                out.extend(slots[name].split("\n"))
            continue

        def sub(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in slots:
                raise CoreError(f"{rel}: no value for inline slot {{{{{name}}}}}")
            value = slots[name]
            if "\n" in value:
                raise CoreError(
                    f"{rel}: inline slot {{{{{name}}}}} has a multi-line value; "
                    "inline slots must be a single line"
                )
            used.add(name)
            return value

        out.append(PLACEHOLDER.sub(sub, line))
    rendered = "\n".join(out)
    residue = RESIDUE.search(rendered)
    if residue:
        raise CoreError(
            f"UNRESOLVED: {rel} leaves {residue.group(0)} in the rendered core. "
            "Slot names are upper-case; a name in any other case is not a slot "
            "and would ship as literal text."
        )
    return rendered, used


# --------------------------------------------------------------------------
# driver files
# --------------------------------------------------------------------------

def _marker_line(text: str, marker: str) -> tuple[int, int] | None:
    """Span of a marker that occurs EXACTLY ONCE as a whole line.

    Returns (start of the marker's line, start of the following line).

    Line-anchored rather than substring-matched, which the first cut was. A
    substring search took the byte after the marker on faith: with the newline
    replaced by any other character, `<!-- ...begin B -->X### Step 5: Review`
    still located a payload that compared EQUAL to the render, so the gate
    reported clean on a document whose region heading had been welded onto its
    marker (found by the #1011 counter-model review).
    """
    matches = list(re.finditer(r"^" + re.escape(marker) + r"$", text, re.MULTILINE))
    if len(matches) != 1:
        return None
    m = matches[0]
    after = m.end() + 1 if m.end() < len(text) else m.end()
    return m.start(), after


def region_bounds(text: str, region: str, core_rel: str) -> tuple[int, int] | None:
    """Locate one fenced region's payload, or None if its markers are not a pair."""
    begin = _marker_line(text, BEGIN.format(region=region, core=core_rel))
    end = _marker_line(text, END.format(region=region))
    if begin is None or end is None:
        return None
    if end[0] < begin[1]:
        return None
    return begin[1], end[0]


def ordering_problem(bounds: dict[str, tuple[int, int]]) -> str | None:
    """Name the first out-of-sequence or overlapping region, if any.

    Comparing each region against its own render says nothing about WHERE that
    region sits. Regions A and B swapped wholesale compared equal twice and the
    gate reported clean - on a driver document that told the reader to invoke the
    model in Step 4 and then asked for approval afterwards, which inverts the one
    property #774 was about (the #1011 counter-model review found this).
    """
    ordered = [(r, bounds[r]) for r in REGIONS if r in bounds]
    for (prev_name, prev), (name, cur) in zip(ordered, ordered[1:]):
        if cur[0] < prev[1]:
            return (
                f"region {name} starts before region {prev_name} ends; the regions "
                "must appear in the order they are declared in the core"
            )
    return None


def expected(root: Path) -> dict[str, dict[str, str]]:
    """Render every driver's every region. Raises CoreError on a malformed source."""
    core_path = root / CORE_REL
    if not core_path.is_file():
        raise CoreError(f"MISSING: {CORE_REL}")
    regions = parse_regions(core_path.read_text(encoding="utf-8"))

    declared_anywhere: dict[str, set[str]] = {}
    out: dict[str, dict[str, str]] = {}
    for driver in DRIVERS:
        rel = f"{VALUES_REL}/{driver}.md"
        vpath = root / rel
        if not vpath.is_file():
            raise CoreError(f"MISSING: {rel}")
        slots = parse_slots(vpath.read_text(encoding="utf-8"), rel)
        used: set[str] = set()
        rendered: dict[str, str] = {}
        for region in REGIONS:
            rendered[region], region_used = render(regions[region], slots, rel)
            used |= region_used
        out[driver] = rendered
        declared_anywhere[driver] = set(slots) - used
    for driver, orphans in declared_anywhere.items():
        if orphans:
            raise CoreError(
                f"ORPHAN: {VALUES_REL}/{driver}.md declares slot(s) the core never "
                f"uses: {', '.join(sorted(orphans))}"
            )
    return out


def run_check(root: Path) -> int:
    try:
        want = expected(root)
    except CoreError as exc:
        print(str(exc))
        print("delegated-core-vendor: source is malformed; nothing was compared.")
        return 1

    problems = 0
    for driver, regions in want.items():
        rel = DRIVER_REL.format(driver=driver)
        path = root / rel
        if not path.is_file():
            print(f"MISSING: {rel}")
            problems += 1
            continue
        text = path.read_text(encoding="utf-8")
        found: dict[str, tuple[int, int]] = {}
        for region, body in regions.items():
            bounds = region_bounds(text, region, CORE_REL)
            if bounds is None:
                print(f"MISSING: {rel} has no matched delegated-core:{region} marker pair")
                problems += 1
                continue
            found[region] = bounds
            actual = text[bounds[0] : bounds[1]]
            if actual != body + "\n":
                print(f"DRIFT: {rel} region {region} differs from the rendered core")
                problems += 1
        misordered = ordering_problem(found)
        if misordered:
            print(f"MISORDERED: {rel}: {misordered}")
            problems += 1

    if problems:
        print(
            "\ndelegated-core-vendor: DRIFT detected. Edit the SOURCE "
            f"({CORE_REL} for shared text, {VALUES_REL}/<driver>.md for per-model "
            "text) and re-run with --write. Do not edit the rendered region."
        )
        return 1
    print(f"delegated-core-vendor: {len(DRIVERS)} driver(s) match the canonical core.")
    return 0


def run_write(root: Path) -> int:
    try:
        want = expected(root)
    except CoreError as exc:
        print(str(exc))
        return 1

    changed = 0
    for driver, regions in want.items():
        rel = DRIVER_REL.format(driver=driver)
        path = root / rel
        if not path.is_file():
            print(f"MISSING: {rel}")
            return 1
        text = path.read_text(encoding="utf-8")
        found = {}
        for region in REGIONS:
            bounds = region_bounds(text, region, CORE_REL)
            if bounds is None:
                print(f"MISSING: {rel} has no matched delegated-core:{region} marker pair")
                return 1
            found[region] = bounds
        misordered = ordering_problem(found)
        if misordered:
            # Refuse rather than rewrite. --write on a misordered document would
            # render each region correctly INTO the wrong position and leave a
            # tree the check then calls clean, which launders the defect.
            print(f"MISORDERED: {rel}: {misordered}")
            return 1
        # Last region first: rewriting shifts every offset after it.
        for region in reversed(REGIONS):
            start, stop = found[region]
            text = text[:start] + regions[region] + "\n" + text[stop:]
        if text != path.read_text(encoding="utf-8"):
            path.write_text(text, encoding="utf-8")
            print(f"wrote {rel}")
            changed += 1
    print(f"delegated-core-vendor: {changed} driver file(s) updated.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", nargs="?", default="check", choices=["check"])
    ap.add_argument("--write", action="store_true", help="re-render into the driver files")
    ap.add_argument("--root", default=str(REPO_ROOT), help="tree to operate on")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    return run_write(root) if args.write else run_check(root)


if __name__ == "__main__":
    sys.exit(main())
