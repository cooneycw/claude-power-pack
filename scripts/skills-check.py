#!/usr/bin/env python3
"""Validate CPP's canonical topic skills and read-only managed mirrors (#720).

The topic-knowledge surface lives in ``.claude/skills/<slug>/SKILL.md``. This
checker keeps that surface attributable and deterministic without relying on
git, PyYAML, or any host binary, so the same validation runs in the slim CI
image and on developer machines.

Managed packages under ``.agents/skills`` are a different concern. They are
host-local copies created by external installers and are gitignored. A package
is CPP-managed only when its frontmatter carries a recognizable
``metadata.source`` link back to ``claude-power-pack/.claude/skills``. Marked
packages are compared with their canonical source; everything else is treated
as user-authored and ignored. This script is a scanner only: it has no write,
delete, repair, or install mode.

Usage:
    python3 scripts/skills-check.py
    python3 scripts/skills-check.py --root DIR
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_CLASSES = frozenset({"vendored", "adapted", "inspired", "cpp-authored"})
UPSTREAM_FIELDS = (
    "upstream_author",
    "source_url",
    "license",
    "revision",
    "local_changes",
)
DESCRIPTION_MAX = 200

MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^\s)>]+)")


class FrontmatterError(ValueError):
    """A SKILL.md frontmatter block is absent or structurally invalid."""


@dataclass(frozen=True)
class Finding:
    """One fail-class validation result."""

    code: str
    path: Path
    detail: str

    def render(self, root: Path) -> str:
        try:
            path: Path | str = self.path.relative_to(root)
        except ValueError:
            path = self.path
        return f"{self.code}: {path}: {self.detail}"


@dataclass
class Report:
    """All findings plus informational managed-install observations."""

    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings


def _scalar(value: str) -> str:
    """Parse the quoted or plain scalar subset used by skill frontmatter."""
    value = value.strip()
    if value[:1] in {'"', "'"}:
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise FrontmatterError(f"invalid quoted scalar: {value}") from exc
        if not isinstance(parsed, str):
            raise FrontmatterError(f"frontmatter values must be strings: {value}")
        return parsed
    return value


def _parse_mapping(lines: list[str]) -> dict[str, object]:
    """Parse a strict, stdlib-only subset of YAML mappings.

    Skill metadata needs nested mappings and string scalars only. Rejecting
    richer YAML here is deliberate: provenance should remain compact, obvious,
    and reviewable without an environment-specific parser.
    """
    result: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, result)]

    for line_number, raw_line in enumerate(lines, start=2):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
            raise FrontmatterError(f"line {line_number}: tabs are not valid indentation")
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        content = raw_line.strip()
        key, separator, raw_value = content.partition(":")
        if not separator or not key.strip():
            raise FrontmatterError(f"line {line_number}: expected key: value")

        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise FrontmatterError(f"line {line_number}: invalid indentation")
        parent = stack[-1][1]
        key = key.strip()
        if key in parent:
            raise FrontmatterError(f"line {line_number}: duplicate key {key!r}")

        if raw_value.strip():
            parent[key] = _scalar(raw_value)
        else:
            child: dict[str, object] = {}
            parent[key] = child
            stack.append((indent, child))
    return result


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Return parsed frontmatter and the byte-significant Markdown body."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise FrontmatterError("missing opening --- frontmatter delimiter")
    end = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.rstrip("\r\n") == "---"),
        None,
    )
    if end is None:
        raise FrontmatterError("missing closing --- frontmatter delimiter")
    mapping_lines = [line.rstrip("\r\n") for line in lines[1:end]]
    return _parse_mapping(mapping_lines), "".join(lines[end + 1 :])


def _frontmatter_header(path: Path) -> dict[str, object] | None:
    """Read only enough of an installed SKILL.md to recognize CPP ownership.

    An unmarked user's skill body is never loaded. The opening frontmatter is
    the minimum evidence needed to distinguish managed content from protected
    neighbor content.
    """
    with path.open(encoding="utf-8") as handle:
        first = handle.readline()
        if first.rstrip("\r\n") != "---":
            return None
        lines = [first]
        for line in handle:
            lines.append(line)
            if line.rstrip("\r\n") == "---":
                break
        else:
            return None
    metadata, _ = parse_frontmatter("".join(lines))
    return metadata


def _nested(mapping: dict[str, object], *keys: str) -> object | None:
    current: object = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _add(report: Report, code: str, path: Path, detail: str) -> None:
    report.findings.append(Finding(code, path, detail))


def _validate_provenance(
    report: Report,
    skill_path: Path,
    metadata: dict[str, object],
) -> None:
    provenance = _nested(metadata, "metadata", "provenance")
    if not isinstance(provenance, dict):
        _add(report, "INVALID_PROVENANCE", skill_path, "missing metadata.provenance mapping")
        return

    provenance_class = provenance.get("class")
    if provenance_class not in PROVENANCE_CLASSES:
        allowed = ", ".join(sorted(PROVENANCE_CLASSES))
        _add(
            report,
            "INVALID_PROVENANCE",
            skill_path,
            f"class must be one of {allowed}; got {provenance_class!r}",
        )
        return

    if provenance_class not in {"vendored", "adapted"}:
        return

    missing = [
        field_name
        for field_name in UPSTREAM_FIELDS
        if not isinstance(provenance.get(field_name), str)
        or not str(provenance[field_name]).strip()
    ]
    if missing:
        _add(
            report,
            "INVALID_PROVENANCE",
            skill_path,
            f"{provenance_class} skill is missing: {', '.join(missing)}",
        )
        return

    source_url = str(provenance["source_url"])
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.path:
        _add(
            report,
            "INVALID_PROVENANCE",
            skill_path,
            "source_url must be an exact http(s) URL",
        )

    revision = str(provenance["revision"]).strip().lower()
    if revision in {"head", "main", "master", "latest", "tip", "unpinned"}:
        _add(
            report,
            "INVALID_PROVENANCE",
            skill_path,
            f"revision {revision!r} is movable rather than pinned",
        )

    # CPP cannot vendor a skill from its own canonical repository. This catches
    # a general false-attribution shape without hard-coding nonexistent skill
    # names such as grill-yourself.
    host = parsed.netloc.lower()
    url_path = parsed.path.lower().rstrip("/") + "/"
    same_repo = (
        host == "github.com" and url_path.startswith("/cooneycw/claude-power-pack/")
    ) or (
        host == "raw.githubusercontent.com"
        and url_path.startswith("/cooneycw/claude-power-pack/")
    )
    if same_repo:
        _add(
            report,
            "FALSE_UPSTREAM_ATTRIBUTION",
            skill_path,
            f"{provenance_class} source points back to CPP itself",
        )


def _validate_references(report: Report, skill_dir: Path, skill_path: Path, body: str) -> None:
    for match in MARKDOWN_LINK_RE.finditer(body):
        target = unquote(match.group(1)).split("#", 1)[0].split("?", 1)[0]
        if not target:
            continue
        parsed = urlparse(target)
        if parsed.scheme or parsed.netloc or target.startswith("/"):
            continue
        resolved = skill_dir / target
        if not resolved.exists():
            _add(
                report,
                "BROKEN_REFERENCE",
                skill_path,
                f"relative Markdown reference does not resolve: {target}",
            )

    for path in sorted(skill_dir.rglob("*")):
        if path.is_symlink() and not path.exists():
            _add(
                report,
                "BROKEN_REFERENCE",
                path,
                f"dangling symlink -> {os.readlink(path)}",
            )


def _validate_package(
    report: Report,
    skill_dir: Path,
    names: dict[str, Path],
) -> None:
    skill_path = skill_dir / "SKILL.md"
    if skill_path.is_symlink() and not skill_path.exists():
        _add(report, "BROKEN_REFERENCE", skill_path, f"dangling symlink -> {os.readlink(skill_path)}")
        return
    if not skill_path.is_file():
        _add(report, "INVALID_PACKAGE", skill_dir, "directory has no SKILL.md")
        return

    try:
        metadata, body = parse_frontmatter(skill_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, FrontmatterError) as exc:
        _add(report, "INVALID_FRONTMATTER", skill_path, str(exc))
        return

    for required in ("name", "description", "trigger"):
        value = metadata.get(required)
        if not isinstance(value, str) or not value.strip():
            _add(report, "INVALID_FRONTMATTER", skill_path, f"missing non-empty {required}")

    description = metadata.get("description")
    if isinstance(description, str) and len(description) > DESCRIPTION_MAX:
        _add(
            report,
            "INVALID_FRONTMATTER",
            skill_path,
            f"description is {len(description)} characters; limit is {DESCRIPTION_MAX}",
        )

    name = metadata.get("name")
    if isinstance(name, str) and name.strip():
        normalized = name.strip().casefold()
        if normalized in names:
            other = names[normalized]
            _add(
                report,
                "DUPLICATE_SURFACE",
                skill_path,
                f"skill name duplicates {other.parent.name!r}",
            )
        else:
            names[normalized] = skill_path

    _validate_provenance(report, skill_path, metadata)
    _validate_references(report, skill_dir, skill_path, body)


def _validate_canonical(report: Report, root: Path) -> None:
    skills_root = root / ".claude" / "skills"
    if not skills_root.is_dir():
        _add(report, "INVALID_SURFACE", skills_root, "canonical skills directory is missing")
        return

    entries = sorted(skills_root.iterdir(), key=lambda path: path.name.casefold())
    names: dict[str, Path] = {}
    slugs: dict[str, Path] = {}
    for entry in entries:
        if entry.is_symlink() and not entry.exists():
            _add(report, "BROKEN_REFERENCE", entry, f"dangling symlink -> {os.readlink(entry)}")
            continue
        if entry.is_file() and entry.suffix == ".md":
            _add(
                report,
                "DUPLICATE_SURFACE",
                entry,
                "retired flat topic skill remains beside canonical packages",
            )
            continue
        if not entry.is_dir():
            _add(report, "INVALID_SURFACE", entry, "unexpected non-package entry")
            continue

        slug = entry.name.casefold()
        if slug in slugs:
            _add(
                report,
                "DUPLICATE_SURFACE",
                entry,
                f"slug duplicates {slugs[slug].name!r} by case",
            )
            continue
        slugs[slug] = entry
        _validate_package(report, entry, names)


def _cpp_managed_source(metadata: dict[str, object]) -> str | None:
    source = _nested(metadata, "metadata", "source")
    if not isinstance(source, str):
        return None
    normalized = source.replace("\\", "/").lower()
    if "claude-power-pack" not in normalized or ".claude/skills/" not in normalized:
        return None
    return source


def _canonical_source(root: Path, source: str) -> Path | None:
    """Resolve a recognized managed source without guessing from dir names."""
    normalized = source.replace("\\", "/").split("#", 1)[0].split("?", 1)[0]
    marker = ".claude/skills/"
    index = normalized.lower().find(marker)
    if index < 0:
        return None
    relative = normalized[index:]
    candidate = (root / Path(relative)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    if candidate.is_dir():
        candidate = candidate / "SKILL.md"
    return candidate


def _normalized_skill(path: Path) -> tuple[dict[str, object], str]:
    metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    metadata = deepcopy(metadata)
    nested = metadata.get("metadata")
    if isinstance(nested, dict):
        nested.pop("source", None)
        if not nested:
            metadata.pop("metadata")
    return metadata, body


def _supporting_files(package: Path) -> dict[str, tuple[str, bytes | str]]:
    files: dict[str, tuple[str, bytes | str]] = {}
    for path in sorted(package.rglob("*")):
        if path.is_dir() and not path.is_symlink():
            continue
        relative = path.relative_to(package).as_posix()
        if relative == "SKILL.md":
            continue
        if path.is_symlink():
            files[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            files[relative] = ("file", path.read_bytes())
    return files


def _managed_differences(canonical: Path, installed: Path) -> list[str]:
    differences: list[str] = []
    try:
        canonical_skill = _normalized_skill(canonical)
        installed_skill = _normalized_skill(installed)
    except (OSError, UnicodeError, FrontmatterError) as exc:
        return [f"unreadable managed package: {exc}"]
    if canonical_skill != installed_skill:
        differences.append("SKILL.md metadata or body differs")

    canonical_files = _supporting_files(canonical.parent)
    installed_files = _supporting_files(installed.parent)
    if canonical_files != installed_files:
        missing = sorted(canonical_files.keys() - installed_files.keys())
        extra = sorted(installed_files.keys() - canonical_files.keys())
        changed = sorted(
            name
            for name in canonical_files.keys() & installed_files.keys()
            if canonical_files[name] != installed_files[name]
        )
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"extra {', '.join(extra)}")
        if changed:
            details.append(f"changed {', '.join(changed)}")
        differences.append("supporting files differ (" + "; ".join(details) + ")")
    return differences


def _validate_managed(report: Report, root: Path, managed_root: Path) -> None:
    if not managed_root.is_dir():
        report.notes.append(f"managed installs: nothing to check ({managed_root} is absent)")
        return

    managed_count = 0
    clean_count = 0
    for package in sorted(managed_root.iterdir(), key=lambda path: path.name.casefold()):
        if not package.is_dir():
            continue
        skill_path = package / "SKILL.md"
        if not skill_path.is_file():
            continue
        try:
            header = _frontmatter_header(skill_path)
        except (OSError, UnicodeError, FrontmatterError):
            # Without a valid CPP source marker this is protected neighbor
            # content, not a broken managed install we can attribute to CPP.
            continue
        if header is None:
            continue
        source = _cpp_managed_source(header)
        if source is None:
            continue

        managed_count += 1
        canonical = _canonical_source(root, source)
        if canonical is None or not canonical.is_file():
            _add(
                report,
                "MANAGED_ORPHAN",
                skill_path,
                f"metadata.source has no canonical package: {source}",
            )
            continue

        differences = _managed_differences(canonical, skill_path)
        if differences:
            _add(
                report,
                "MANAGED_DRIFT",
                skill_path,
                "; ".join(differences),
            )
        else:
            clean_count += 1
            report.notes.append(f"managed install {package.name}: clean parity")

    if managed_count == 0:
        report.notes.append("managed installs: no CPP-marked packages; user content ignored")
    else:
        report.notes.append(
            f"managed installs: checked {managed_count} CPP-marked package(s), {clean_count} clean"
        )


def check_repository(root: Path, managed_skills_root: Path | None = None) -> Report:
    """Validate one tree. The optional managed root makes tests hermetic."""
    root = root.resolve()
    report = Report()
    _validate_canonical(report, root)
    managed_root = managed_skills_root or root / ".agents" / "skills"
    _validate_managed(report, root, managed_root)
    report.findings.sort(key=lambda finding: (str(finding.path), finding.code, finding.detail))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="repository root (default: the checkout containing this script)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    report = check_repository(root)

    for note in report.notes:
        print(f"skills-check: {note}")
    if report.ok:
        print("skills-check: ok - canonical packages and managed installs are valid")
        return 0

    print(f"skills-check: {len(report.findings)} failure(s)", file=sys.stderr)
    for finding in report.findings:
        print(f"  {finding.render(root)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
