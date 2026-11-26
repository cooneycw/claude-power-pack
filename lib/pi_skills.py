"""Pi topic build policy and immutable bytes; installation belongs to host_update.

This module never installs, adopts, prunes or writes an ownership record. A1's
fidelity result is a file snapshot, not a runtime selection or lock guarantee.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
LINK = re.compile(r"(?<!!)(\[[^\]]*\]\()([^\s)]+)(\))")
GUIDE = re.compile(r"(?<![\w/])docs/(?:skills|reference)/[A-Za-z0-9_./-]+\.md")
SOURCE_PREFIX = "claude-power-pack/.claude/skills/"


class PolicyError(ValueError):
    """Known unsupported input; no mutation is authorized."""


def credential_path(path: Path) -> bool:
    return any(part in {"auth.json", "mcp-auth.json"} for part in path.parts)


def within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def normalized(value: str | Path, cwd: Path, home: Path) -> Path:
    text = str(value)
    if not text or "\x00" in text:
        raise PolicyError("empty or NUL path")
    if text.startswith("file:"):
        url = urlsplit(text)
        if url.netloc not in ("", "localhost") or url.query or url.fragment:
            raise PolicyError("unsupported file URL")
        text = unquote(url.path)
    if text == "~" or text.startswith("~/"):
        text = str(home) + text[1:]
    elif text.startswith("~"):
        raise PolicyError("named-user expansion is unsupported")
    path = Path(text)
    if ".." in path.parts:
        raise PolicyError("path traversal refused")
    return Path(os.path.abspath(cwd / path))


def nofollow(path: Path) -> Path:
    """Validate existing ancestors without following symlinks (missing is OK)."""
    if ".." in path.parts:
        raise PolicyError("path traversal refused")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if credential_path(current):
            raise PolicyError("credential path metadata refused")
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        if stat.S_ISLNK(mode):
            raise PolicyError("symlink path refused: " + str(current))
    return path


def history_root(path: Path, seen: frozenset[Path] = frozenset()) -> Path:
    """Resolve only root/ancestor lstat/readlink; never enumerate history.

    Ruling 39944 permits this closed metadata population, including link target
    roots needed to establish exclusions. A dangling link is not known absence.
    """
    if path in seen or len(seen) > 32 or credential_path(path):
        raise PolicyError("ambiguous or credential history root")
    current = Path(path.anchor)
    for index, part in enumerate(path.parts[1:], start=1):
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            return path
        if stat.S_ISLNK(mode):
            link = Path(os.readlink(current))
            target = link if link.is_absolute() else current.parent / link
            target = Path(os.path.abspath(target))
            resolved = history_root(target, seen | {path})
            # Distinguish missing direct history from a dangling configured link.
            try:
                resolved.lstat()
            except FileNotFoundError as error:
                raise PolicyError("dangling history root link") from error
            rest = path.parts[index + 1:]
            return history_root(resolved.joinpath(*rest), seen | {path}) if rest else resolved
        if not stat.S_ISDIR(mode):
            raise PolicyError("history root/ancestor is not a directory")
    return path


def settings(path: Path) -> dict[str, object]:
    nofollow(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return {}
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise PolicyError("settings is not a regular file")
        value = json.load(stream)
    if not isinstance(value, dict):
        raise PolicyError("settings must be an object")
    session = value.get("sessionDir")
    if session is not None and not isinstance(session, str):
        raise PolicyError("sessionDir must be a string")
    return value


@dataclass(frozen=True)
class BuildPolicy:
    agent: Path
    histories: tuple[tuple[str, Path], ...]
    effective_history: Path
    destination: Path


def preflight(destination: Path, *, cwd: Path, home: Path, agent: str | Path | None = None,
              session_dir: str | None = None, environ: dict[str, str] | None = None,
              fidelity_only: bool = False, include_project: bool = True) -> BuildPolicy:
    """Pi policy inputs shared by builds, snapshots and core adapter preflight."""
    env = os.environ if environ is None else environ
    cwd = nofollow(cwd.absolute())
    home = home.absolute()
    agent_path = nofollow(normalized(agent or env.get("PI_CODING_AGENT_DIR") or home / ".pi/agent", cwd, home))
    try:
        global_settings = settings(agent_path / "settings.json")
        project_settings = settings(cwd / ".pi/settings.json") if include_project else {}
    except (OSError, UnicodeError, ValueError) as error:
        raise PolicyError("settings unreadable or malformed: " + str(error)) from error
    raw = [("cli", session_dir), ("environment", env.get("PI_CODING_AGENT_SESSION_DIR")),
           ("project", project_settings.get("sessionDir")), ("global", global_settings.get("sessionDir")),
           ("default", str(agent_path / "sessions"))]
    histories = tuple((label, history_root(normalized(value, cwd, home)))
                      for label, value in raw if isinstance(value, str) and value)
    output = normalized(destination, cwd, home)
    canonical_install = output == agent_path / "skills"
    if not include_project and not (fidelity_only and canonical_install):
        raise PolicyError("host fidelity is confined to canonical agent skills")
    project_root = cwd / ".pi"
    project_overlap = within(project_root, output) or (
        within(output, project_root) and not (fidelity_only and canonical_install))
    if output == home or (include_project and project_overlap):
        raise PolicyError("output_root_under_trusted_config")
    if (within(output, agent_path) or within(agent_path, output)) and not (fidelity_only and canonical_install):
        raise PolicyError("output_root_under_trusted_config")
    if any(within(output, root) or within(root, output) for _, root in histories):
        raise PolicyError("output_root_under_sessions")
    if output.name != "skills":
        raise PolicyError("build/fidelity destination must end in skills")
    nofollow(output)
    return BuildPolicy(agent_path, histories, histories[0][1], output)


def markdown(path: Path, *, exact_mode: bool = True) -> bytes:
    nofollow(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        mode = os.fstat(stream.fileno()).st_mode
        if not stat.S_ISREG(mode) or mode & 0o111 or (exact_mode and stat.S_IMODE(mode) != 0o644):
            rule = "regular 0644" if exact_mode else "regular non-executable"
            raise PolicyError("requires " + rule + " Markdown: " + str(path))
        content = stream.read()
    content.decode("utf-8")
    return content


def package_files(directory: Path, *, exact_mode: bool = True,
                  reader: Callable[[Path], bytes] | None = None) -> dict[str, bytes]:
    nofollow(directory)
    found: dict[str, bytes] = {}
    def fail(error: OSError) -> None:
        raise error

    for root, dirs, files in os.walk(directory, followlinks=False, onerror=fail):
        for name in dirs:
            path = Path(root) / name
            if path.is_symlink() or path.relative_to(directory).as_posix() != "references":
                raise PolicyError("unsupported package directory: " + str(path))
        for name in files:
            path = Path(root) / name
            member = path.relative_to(directory).as_posix()
            if member != "SKILL.md" and not re.fullmatch(r"references/[A-Za-z0-9_.-]+\.md", member):
                raise PolicyError("unsupported package member: " + member)
            if reader:
                found[member] = reader(path)
            else:
                found[member] = markdown(path) if exact_mode else markdown(path, exact_mode=False)
    if "SKILL.md" not in found:
        raise PolicyError("missing SKILL.md: " + str(directory))
    return found


def header(text: str) -> tuple[str, str]:
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise PolicyError("invalid skill frontmatter")
    front, body = text[4:].split("\n---\n", 1)
    return front, body


def safe_topic(text: str) -> None:
    if re.search(r"!command\b", text, re.I):
        raise PolicyError("command helper is outside topic policy")
    # A direct link to a pi auth store is forbidden; discussing credentials is
    # not itself a helper and must not reject the canonical secrets topic.
    for match in LINK.finditer(text):
        target = unquote(match[2]).lower()
        if re.search(r"(?:^|/)(?:mcp-)?auth\.json(?:$|[#?])", target):
            raise PolicyError("authentication link is outside topic policy")


@dataclass(frozen=True)
class Package:
    slug: str
    members: tuple[tuple[str, bytes], ...]

    def manifest(self) -> dict[str, dict[str, str | int]]:
        return {name: {"sha256": hashlib.sha256(data).hexdigest(), "mode": 0o644}
                for name, data in self.members}


def build(source: Path, *, reader: Callable[[Path], bytes] | None = None) -> tuple[Package, ...]:
    """Build from canonical topics only; never trust a generated inventory."""
    source = nofollow(source.absolute())
    topics = nofollow(source / ".claude/skills")
    entries = sorted(topics.iterdir())
    if not entries:
        raise PolicyError("canonical topic population is empty")
    packages = []
    for entry in entries:
        slug = entry.name
        if not SLUG.fullmatch(slug) or len(slug) > 64:
            raise PolicyError("invalid topic slug: " + slug)
        if entry.is_symlink() or not entry.is_dir():
            raise PolicyError("canonical entry is not a real package: " + slug)
        members = package_files(entry, exact_mode=False, reader=reader)
        text = members["SKILL.md"].decode("utf-8")
        front, body = header(text)
        declared = re.search(r"(?m)^name:\s*([^\n]+)$", front)
        if not declared or declared[1].strip(" '\"") != slug:
            raise PolicyError("skill name differs from canonical slug: " + slug)
        description = re.search(r"(?m)^description:[ \t]+([^\n]+)$", front)
        if not description or not 1 <= len(description[1]) <= 1024:
            raise PolicyError("missing or oversized skill description: " + slug)
        if re.search(r"(?m)^  source:", front):
            raise PolicyError("canonical topic already declares source")
        marker = "  source: " + SOURCE_PREFIX + slug
        if re.search(r"(?m)^metadata:\s*$", front):
            front = re.sub(r"(?m)^metadata:\s*$", "metadata:\n" + marker, front, count=1)
        else:
            front += "\nmetadata:\n" + marker
        members["SKILL.md"] = ("---\n" + front + "\n---\n" + body).encode()
        bundled: dict[Path, str] = {}

        def bundle(path: Path) -> str:
            if not within(path, source) or path.suffix != ".md":
                raise PolicyError("reference escapes Markdown source scope")
            relative = path.relative_to(source).as_posix()
            name = path.name if relative.startswith("docs/skills/") else relative.replace("/", "--")
            target = "references/" + name
            if path in bundled:
                return target
            if target in members:
                raise PolicyError("bundled reference collision: " + target)
            bundled[path] = target
            members[target] = b""  # reserve for recursive links
            content = (reader(path) if reader else markdown(path, exact_mode=False)).decode("utf-8")
            members[target] = rewrite(content, path, reference=True).encode()
            return target

        def rewrite(content: str, origin: Path, reference: bool = False) -> str:
            safe_topic(content)

            def link(match: re.Match[str]) -> str:
                target = match[2]
                if re.match(r"(?:[a-z]+:|#)", target, re.I):
                    return match[0]
                file, sep, anchor = target.partition("#")
                path = Path(os.path.abspath(origin.parent / unquote(file)))
                bundled_target = bundle(path)
                dest = Path(bundled_target).name if reference else "./" + bundled_target
                return match[1] + dest + (sep + anchor if sep else "") + match[3]

            def guide(match: re.Match[str]) -> str:
                dest = bundle(source / match[0])
                return ("./" if not reference else "") + (Path(dest).name if reference else dest)

            # Code fences document examples rather than package dependencies.
            # Keep them byte-for-byte; their link-shaped strings are not links.
            rendered = []
            fence: tuple[str, int] | None = None
            for line in content.splitlines(keepends=True):
                delimiter = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$", line)
                if delimiter:
                    mark, tail = delimiter.groups()
                    if fence is None:
                        fence = (mark[0], len(mark))
                    elif mark[0] == fence[0] and len(mark) >= fence[1] and not tail.strip():
                        fence = None
                    rendered.append(line)
                elif fence:
                    rendered.append(line)
                else:
                    segments = re.split(r"(`+[^`]*`+)", line)
                    rendered.append("".join(GUIDE.sub(guide, part if index % 2 else LINK.sub(link, part))
                                            for index, part in enumerate(segments)))
            return "".join(rendered)

        for member, data in list(members.items()):
            members[member] = rewrite(data.decode("utf-8"), entry / member,
                                      reference=member.startswith("references/")).encode()
        packages.append(Package(slug, tuple(sorted(members.items()))))
    return tuple(packages)


def fidelity(expected: tuple[Package, ...], root: Path) -> dict[str, object]:
    """Compare the entire expected population, preserving foreign neighbors."""
    if not expected:
        raise PolicyError("expected population is empty")
    findings: list[str] = []
    checked = 0
    unexamined = 0
    known_difference = False
    for package in expected:
        try:
            actual = package_files(root / package.slug)
            if actual != dict(package.members):
                findings.append(package.slug + ": membership/bytes differ")
                known_difference = True
            else:
                checked += 1
        except (FileNotFoundError, PolicyError) as error:
            known_difference = True
            findings.append(package.slug + ": " + str(error))
        except (OSError, UnicodeError) as error:
            unexamined += 1
            findings.append(package.slug + ": unexamined: " + str(error))
    state = "differs" if known_difference else "unknown" if unexamined else "matches"
    return {"scope": "file-snapshot", "expected": len(expected), "checked": checked,
            "fidelity": state, "unexamined": unexamined,
            "effectiveness": "unknown", "findings": findings,
            "installation": "not-examined"}


def write(expected: tuple[Package, ...], destination: Path) -> None:
    """Populate a new build directory; refuse overwriting any existing member."""
    nofollow(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if any(p.name != "README.md" for p in destination.iterdir()):
        if fidelity(expected, destination)["fidelity"] == "matches":
            return
        raise PolicyError("build destination differs; use a new empty build root (no pruning in A1)")
    for package in expected:
        for member, data in package.members:
            path = destination / package.slug / member
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
            path.chmod(0o644)
