#!/usr/bin/env python3
"""retired-surface-prune.py - tear down GENERATED file surfaces CPP retired.

The gap this closes (issue #575): when CPP retires a generated surface it
deletes the generator from the repo - but every copy that generator already
wrote into a user's HOME stays exactly where it was, unmaintained and
invisible. Codex on the primary box was still loading 65 prompts from a surface
retired at the #556 cutover, and 49 generated skills frozen at 2026-07-04 were
still loading in Claude sessions alongside the current surface (#480/#481).
Nothing warned about either.

The surfaces are declared in `.claude/retired-surfaces.yaml`, the list of
record, in the same spirit as `.claude/deprecated-mcps.yaml` for MCP servers.

SAFETY - three independent properties, all required:

  1. CURATED. Only directories listed in the YAML are ever inspected. A
     directory CPP never generated into is invisible to this script.
  2. MARKER-GATED. Within a listed directory, only files whose first non-blank
     content line (after any YAML frontmatter) starts with one of that entry's
     `markers` are owned. Detection is by MARKER, never by name list - so a
     hand-authored file such as ~/.codex/prompts/cpp-memory.md, a skill the
     user wrote, or one installed with `npx skills add`, is preserved. An
     explicit `preserve:` list is belt-and-braces on top.
  3. REVERSIBLE. `--prune` MOVES owned files into a timestamped sibling
     directory (`<path>-retired-<YYYY-MM-DD>`) rather than deleting them,
     mirroring the manual remediation performed on 2026-07-14. Nothing this
     script does is unrecoverable.

Modes:
  --check    (default) report per-surface status; exit 1 if anything is owned
  --json     machine-readable report (used by /cpp:update Step 7.9)
  --plan     print exactly what --prune would move; pure, no side effects
  --prune NAME...   move owned files for the named surfaces (or --all)

Exit codes: 0 clean / 1 findings or refusal / 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SURFACES_FILE = REPO_ROOT / ".claude" / "retired-surfaces.yaml"

STATUS_OWNED = "ORPHANED GENERATED"
STATUS_CLEAN = "CLEAN"
STATUS_ABSENT = "ABSENT"


# --- YAML loading ------------------------------------------------------------


def _load_yaml(text: str) -> dict:
    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(text) or {}
    except ImportError:
        return _fallback_parse(text)


def _scalar(value: str) -> str:
    value = value.strip()
    if value[:1] in {'"', "'"} and value[-1:] == value[:1] and len(value) >= 2:
        return value[1:-1]
    return value


def _fallback_parse(text: str) -> dict:
    """Minimal parser for the retired-surfaces.yaml schema only.

    Handles a top-level `version` scalar and a `retired:` block list of
    mappings with scalar fields plus the block-list fields `markers` and
    `preserve`. Folded scalars (`reason: >-`) are dropped - they are reporting
    prose, never used for a decision. Keep folded text colon-free so a
    continuation line is never mistaken for a field.
    """
    result: dict = {}
    entries: list[dict] = []
    current: dict | None = None
    list_key: str | None = None
    list_indent = -1
    list_fields = {"markers", "preserve"}

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.lstrip(" ")

        if list_key is not None and body.startswith("- ") and indent > list_indent:
            current.setdefault(list_key, []).append(_scalar(body[2:]))  # type: ignore[union-attr]
            continue
        list_key = None

        if indent == 0 and not body.startswith("- ") and ":" in body:
            key, _, val = body.partition(":")
            key = key.strip()
            if key == "retired":
                result["retired"] = entries
            else:
                result[key] = _scalar(val)
            continue

        if body.startswith("- ") and "name:" in body:
            current = {}
            entries.append(current)
            key, _, val = body[2:].partition(":")
            current[key.strip()] = _scalar(val)
            continue

        if current is None:
            continue

        if ":" in body and not body.startswith("- "):
            key, _, val = body.partition(":")
            key = key.strip()
            sval = _scalar(val)
            if key in list_fields and sval == "":
                current[key] = []
                list_key = key
                list_indent = indent
            else:
                current[key] = sval

    if "retired" not in result:
        result["retired"] = entries
    return result


def load_surfaces(surfaces_file: Path) -> list[dict]:
    if not surfaces_file.is_file():
        return []
    data = _load_yaml(surfaces_file.read_text(encoding="utf-8"))
    entries = data.get("retired") or []
    return [e for e in entries if isinstance(e, dict) and e.get("name")]


# --- ownership ---------------------------------------------------------------


def first_content_line(path: Path) -> str:
    """First non-blank line after any YAML frontmatter block."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            content = content[end + len("\n---"):]
    for line in content.splitlines():
        if line.strip():
            return line
    return ""


def is_owned(path: Path, markers: list[str]) -> bool:
    line = first_content_line(path)
    return any(line.startswith(m) for m in markers if m)


def surface_path(entry: dict) -> Path:
    return Path(str(entry.get("path", ""))).expanduser()


def scan_surface(entry: dict) -> dict:
    """Classify one surface. Pure - reads only."""
    name = str(entry.get("name", ""))
    path = surface_path(entry)
    markers = [m for m in (entry.get("markers") or []) if m]
    preserve = set(entry.get("preserve") or [])
    depth = str(entry.get("depth", "flat"))
    entry_file = str(entry.get("entry_file", "SKILL.md"))

    report = {
        "name": name,
        "path": str(path),
        "depth": depth,
        "reason": str(entry.get("reason", "")).strip(),
        "replacement": str(entry.get("replacement", "")).strip(),
        "owned": [],
        "preserved": [],
        "status": STATUS_ABSENT,
    }
    if not path.is_dir():
        return report

    if depth == "dirs":
        for child in sorted(path.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if child.name in preserve:
                report["preserved"].append(child.name)
                continue
            if is_owned(child / entry_file, markers):
                report["owned"].append(child.name)
            else:
                report["preserved"].append(child.name)
    else:
        for child in sorted(path.iterdir()):
            if not child.is_file() or child.name.startswith("."):
                continue
            if child.name in preserve:
                report["preserved"].append(child.name)
                continue
            if is_owned(child, markers):
                report["owned"].append(child.name)
            else:
                report["preserved"].append(child.name)

    report["status"] = STATUS_OWNED if report["owned"] else STATUS_CLEAN
    return report


def scan_all(entries: list[dict]) -> list[dict]:
    return [scan_surface(e) for e in entries]


# --- reporting ---------------------------------------------------------------


def print_report(reports: list[dict], verbose: bool = False) -> None:
    for r in reports:
        line = f"{r['status']:<20} {r['name']:<22} {r['path']}"
        if r["status"] == STATUS_OWNED:
            line += f"  ({len(r['owned'])} owned, {len(r['preserved'])} preserved)"
        elif r["status"] == STATUS_CLEAN:
            line += f"  ({len(r['preserved'])} file(s), none owned by CPP)"
        print(line)
        if r["status"] == STATUS_OWNED:
            if r["reason"]:
                print(f"  reason:      {r['reason']}")
            if r["replacement"]:
                print(f"  replacement: {r['replacement']}")
            shown = r["owned"] if verbose else r["owned"][:5]
            for name in shown:
                print(f"    - {name}")
            if not verbose and len(r["owned"]) > len(shown):
                print(f"    ... and {len(r['owned']) - len(shown)} more (--verbose to list)")
            if r["preserved"]:
                kept = r["preserved"] if verbose else r["preserved"][:5]
                print(f"  preserved (not CPP-generated): {', '.join(kept)}")


def plan_prune(report: dict, today: str) -> list[str]:
    """The exact moves --prune would perform. Pure - no side effects."""
    if report["status"] != STATUS_OWNED:
        return []
    dest = f"{report['path']}-retired-{today}"
    lines = [f"mkdir -p {dest}"]
    lines += [f"mv {report['path']}/{name} {dest}/{name}" for name in report["owned"]]
    return lines


# --- teardown ----------------------------------------------------------------


def prune(entries: list[dict], names: list[str], today: str) -> int:
    by_name = {str(e.get("name")): e for e in entries}
    rc = 0
    for name in names:
        entry = by_name.get(name)
        if entry is None:
            print(
                f"REFUSED {name}: not in the retired-surfaces.yaml list of record",
                file=sys.stderr,
            )
            rc = 1
            continue
        report = scan_surface(entry)
        if report["status"] != STATUS_OWNED:
            print(f"REFUSED {name}: status is {report['status']}, nothing owned by CPP to move", file=sys.stderr)
            rc = 1
            continue
        path = surface_path(entry)
        dest = path.parent / f"{path.name}-retired-{today}"
        dest.mkdir(parents=True, exist_ok=True)
        moved = 0
        for child_name in report["owned"]:
            src = path / child_name
            target = dest / child_name
            if target.exists():
                shutil.rmtree(target) if target.is_dir() else target.unlink()
            shutil.move(str(src), str(target))
            moved += 1
        print(f"retired-surface-prune: moved {moved} owned item(s) from {path} -> {dest}")
        print(f"  recover with: mv {dest}/* {path}/")
    return rc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tear down retired GENERATED host surfaces (issue #575).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report status (default); exit 1 on findings")
    mode.add_argument("--json", action="store_true", help="machine-readable report")
    mode.add_argument("--plan", action="store_true", help="print the moves --prune would make; no side effects")
    mode.add_argument("--prune", nargs="*", metavar="NAME", help="move owned files for these surfaces")
    parser.add_argument("--all", action="store_true", help="with --prune: every surface with findings")
    parser.add_argument("--verbose", action="store_true", help="list every owned item")
    parser.add_argument(
        "--surfaces-file",
        type=Path,
        default=DEFAULT_SURFACES_FILE,
        help=f"list of record (default: {DEFAULT_SURFACES_FILE})",
    )
    args = parser.parse_args(argv)

    entries = load_surfaces(args.surfaces_file)
    if not entries:
        print(f"retired-surface-prune: no surfaces listed in {args.surfaces_file}", file=sys.stderr)
        return 0

    reports = scan_all(entries)
    today = date.today().isoformat()

    if args.json:
        print(json.dumps({"surfaces": reports}, indent=2))
        return 0

    if args.plan:
        any_planned = False
        for r in reports:
            lines = plan_prune(r, today)
            if lines:
                any_planned = True
                print(f"# {r['name']} ({len(r['owned'])} item(s))")
                for line in lines:
                    print(line)
        if not any_planned:
            print("retired-surface-prune: nothing to plan - no surface has CPP-owned files")
        return 0

    if args.prune is not None:
        names = args.prune
        if args.all:
            names = [r["name"] for r in reports if r["status"] == STATUS_OWNED]
        if not names:
            print("retired-surface-prune: nothing to prune (pass NAME... or --all)", file=sys.stderr)
            return 0
        return prune(entries, names, today)

    print_report(reports, verbose=args.verbose)
    findings = [r for r in reports if r["status"] == STATUS_OWNED]
    if findings:
        print("")
        print(f"{len(findings)} retired surface(s) still have CPP-generated files on this host.")
        print("Review with --plan, then move them aside with --prune --all (reversible).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
