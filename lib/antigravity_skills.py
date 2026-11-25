"""Self-contained AGY topic packages over the neutral managed-copy core.

Only tracked blobs at one commit are source inputs. This adapter manages an
explicit build-output directory; production host discovery belongs to delivery B.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import posixpath
import re
import sys
import tempfile
from functools import cache
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

import yaml

from lib.host_update.driver import _source_git
from lib.host_update.models import (
    AdapterError,
    Discovery,
    ExpectedBuild,
    ExpectedMember,
    ExpectedPackage,
    Policy,
    Request,
    Revision,
    State,
    build_manifest_sha256,
)
from lib.host_update.scope import Scope, absolute

TOPICS = frozenset({
    "best-practices", "boot", "browser-tiered", "cicd-verification", "claude-md-config",
    "code-quality", "context-efficiency", "documentation", "evaluate", "hooks-automation",
    "idd-workflow", "infrastructure-hardening", "mcp-optimization", "project-deploy",
    "python-packaging", "secrets", "session-management", "spec-driven-dev",
})
BUNDLED_SCRIPTS = frozenset({"scripts/c4-mermaid.py"})
# Markdown destinations plus the repository paths used as plain-text read/run
# instructions by canonical topic documents. Project example paths are not
# dependencies merely because they resemble a checkout path.
DESTINATION = re.compile(r"(?P<start>!?\[[^\]\n]*\]\()(?P<path><[^>\n]+>|[^\s)]+)")
DEFINITION = re.compile(r"(?m)^(?P<start> {0,3}\[[^\]\n]+\]:[ \t]*)(?P<path><[^>\n]+>|[^\s]+)")
HTML = re.compile(r"(?P<start>\b(?:href|src)=[\"'])(?P<path>[^\"'\n]+)")
BARE = re.compile(r"(?<![\w/])(?:docs/(?:skills|reference|agents)|scripts)/[A-Za-z0-9_.%/-]+\.[A-Za-z0-9]+")


@cache
def _load_link_parser(content: bytes):
    identity = hashlib.sha256(content).hexdigest()
    name = f"agy_topic_markdown_{identity}"
    # Import the trusted pinned CPP module with the standard loader. Its
    # private materialization is removed immediately and never enters output.
    with tempfile.TemporaryDirectory(prefix="cpp-agy-parser-") as temporary:
        path = Path(temporary) / "check-md-relative-links.py"
        path.write_bytes(content)
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


def link_parser(snapshot: Snapshot | None = None):
    if snapshot is None:
        content = (Path(__file__).resolve().parent.parent / "scripts/check-md-relative-links.py").read_bytes()
    else:
        content = snapshot.read("scripts/check-md-relative-links.py").content
    return _load_link_parser(content)


def visible_markdown(text: str, parser=None) -> str:
    """Mask comments/code without changing offsets, including image contexts."""
    parser = parser if parser is not None else link_parser()

    def mask(match):
        return re.sub(r"[^\n]", " ", match.group())

    text = parser.COMMENT_RE.sub(mask, text)
    fence = None
    paragraph_open = False
    list_indent = 0
    visible = []
    for line in text.splitlines(keepends=True):
        hidden = False
        if fence is None:
            match = parser.FENCE_RE.match(line)
            if match:
                fence = match.group(1)
                paragraph_open = False
                hidden = True
            else:
                expanded = line.expandtabs(4)
                indent = len(expanded) - len(expanded.lstrip())
                if expanded.strip() and indent < list_indent:
                    list_indent = 0
                hidden = indent >= list_indent + 4 and not paragraph_open
                marker = re.match(r"^( {0,3})(?:[-+*]|[0-9]{1,9}[.)])( +)", expanded)
                if marker and not hidden:
                    list_indent = marker.end()
                paragraph_open = bool(expanded.strip()) and not hidden
        else:
            match = parser.CLOSING_FENCE_RE.match(line)
            if match and match.group(1).startswith(fence):
                fence = None
            hidden = True
            paragraph_open = False
        visible.append(re.sub(r"[^\n]", " ", line) if hidden else line)
    return parser.INLINE_CODE_RE.sub(mask, "".join(visible))


def unknown(reason: str) -> AdapterError:
    return AdapterError(reason, exit_code=4)


class Snapshot:
    """Closed tracked population, excluding worktree/ignored files and aliases."""

    def __init__(self, revision: Revision):
        self.revision = revision
        result = _source_git(revision, ["ls-tree", "-rz", "--full-tree", revision.commit])
        if result.returncode:
            raise unknown("tracked source inventory unavailable")
        self.files: dict[str, tuple[int, str]] = {}
        for row in result.stdout.split(b"\0"):
            if not row:
                continue
            info, raw_path = row.split(b"\t", 1)
            mode, kind, oid = info.decode().split()
            path = raw_path.decode("utf-8")
            if kind == "blob":
                self.files[path] = (int(mode, 8), oid)

    def read(self, path: str) -> ExpectedMember:
        if path not in self.files:
            raise unknown(f"required tracked source missing: {path}")
        mode, oid = self.files[path]
        if mode not in (0o100644, 0o100755):
            raise AdapterError(f"source is not a regular supported file: {path}", state=State.UNMANAGED)
        result = _source_git(self.revision, ["cat-file", "blob", oid])
        if result.returncode or len(result.stdout) > 16 * 1024 * 1024:
            raise unknown(f"source blob unreadable or oversized: {path}")
        return ExpectedMember(result.stdout, mode & 0o777)


def _resolve(raw: str, source: str, files: dict[str, tuple[int, str]]) -> str | None:
    value = unquote(raw.strip("<>"))
    url = urlsplit(value)
    if url.scheme or url.netloc or not url.path:
        return None
    if url.path.startswith(("/", "~")) or "\\" in url.path or "\0" in url.path:
        raise AdapterError("absolute or unsafe package reference", state=State.UNMANAGED)
    candidate = posixpath.normpath(posixpath.join(posixpath.dirname(source), url.path))
    if candidate not in files and url.path.startswith(("docs/", "scripts/", "templates/")):
        candidate = posixpath.normpath(url.path)
    if candidate.startswith("../") or candidate == "..":
        raise AdapterError("reference escapes source snapshot", state=State.UNMANAGED)
    if candidate not in files:
        if any(path.startswith(candidate.rstrip("/") + "/") for path in files):
            return candidate.rstrip("/") + "/"
        raise unknown(f"unresolved local reference in {source}: {url.path}")
    return candidate


def build(revision: Revision, *, expected_topics: frozenset[str] = TOPICS) -> ExpectedBuild:
    snapshot = Snapshot(revision)
    actual = {PurePosixPath(p).parts[2] for p in snapshot.files
              if p.startswith(".claude/skills/") and len(PurePosixPath(p).parts) == 4
              and p.endswith("/SKILL.md")}
    if not expected_topics or actual != expected_topics:
        raise unknown("canonical topic population differs from the explicit nonzero inventory")
    parser = link_parser(snapshot)
    packages: list[ExpectedPackage] = []
    for topic in sorted(expected_topics):
        prefix = f".claude/skills/{topic}/"
        destinations = {p: p.removeprefix(prefix) for p in snapshot.files if p.startswith(prefix)}
        pending = list(destinations)
        members: dict[str, ExpectedMember] = {}

        def include(path: str) -> str:
            if path.endswith("/"):
                raise AdapterError("directory bundling is outside topic scope", state=State.UNMANAGED)
            if path not in destinations:
                # Preserve the complete repository-relative path to avoid two
                # distinct guides/resources with the same basename colliding.
                destinations[path] = f"references/{path}"
                pending.append(path)
            return destinations[path]

        while pending:
            source = pending.pop()
            output = destinations[source]
            member = snapshot.read(source)
            if source.endswith(".md"):
                text = member.content.decode("utf-8")

                def rewrite(raw: str) -> str:
                    path = _resolve(raw, source, snapshot.files)
                    if path is None:
                        return raw
                    fragment = urlsplit(raw.strip("<>")).fragment
                    allowed = not path.endswith("/") and (
                        path.startswith(prefix) or path.startswith("docs/skills/") or path in BUNDLED_SCRIPTS)
                    if not allowed:
                        # Reference material outside the topic contract remains
                        # an immutable upstream link, never a recursive corpus.
                        kind = "tree" if path.endswith("/") else "blob"
                        result = (f"https://github.com/cooneycw/claude-power-pack/{kind}/"
                                  f"{revision.commit}/{quote(path, safe='/')}")
                        if fragment:
                            result += "#" + fragment
                        return f"<{result}>" if raw.startswith("<") else result
                    destination = include(path)
                    relative = posixpath.relpath(destination, posixpath.dirname(output) or ".")
                    result = "./" + relative if not relative.startswith(".") else relative
                    if fragment:
                        result += "#" + fragment
                    return f"<{result}>" if raw.startswith("<") else result

                # Plain root-relative source instructions are rewritten before
                # Markdown links, otherwise a generated references/docs path
                # could be mistaken for another repository dependency.
                def bare(match: re.Match[str]) -> str:
                    value = match.group()
                    if value not in snapshot.files:
                        if value.startswith("docs/"):
                            raise unknown(f"required guide missing: {value}")
                        return value  # a project example, not a CPP source file
                    return rewrite(value)

                # Keep link destinations out of the plain-path pass.
                links: list[str] = []
                visible = visible_markdown(text, parser)

                def stash(match: re.Match[str]) -> str:
                    if visible[match.start("path"):match.end("path")] != match.group("path"):
                        return match.group()
                    links.append(match.group("start") + rewrite(match.group("path")))
                    return f"\x00AGYLINK{len(links) - 1}\x00"

                for pattern in (DESTINATION, DEFINITION, HTML):
                    visible = visible_markdown(text, parser)
                    text = pattern.sub(stash, text)
                text = BARE.sub(bare, text)
                for index, link in enumerate(links):
                    text = text.replace(f"\x00AGYLINK{index}\x00", link)
                if output == "SKILL.md":
                    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
                        raise unknown(f"missing topic frontmatter: {topic}")
                    front, body = text[4:].split("\n---\n", 1)
                    metadata = yaml.safe_load(front)
                    if (not isinstance(metadata, dict) or metadata.get("name") != topic
                            or not isinstance(metadata.get("description"), str)
                            or not metadata["description"].strip()):
                        raise unknown(f"invalid topic frontmatter: {topic}")
                    extra = metadata.setdefault("metadata", {})
                    if not isinstance(extra, dict):
                        raise unknown(f"invalid topic metadata: {topic}")
                    extra["source"] = f"claude-power-pack/.claude/skills/{topic}"
                    extra["cpp"] = {"schema": 1, "revision": revision.commit, "harness": "antigravity"}
                    text = ("---\n" + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True) + "---\n"
                            "\nResolve package-relative guide and script paths from the directory containing this "
                            "SKILL.md, including when the current project is elsewhere.\n\n" + body)
                member = ExpectedMember(text.encode(), member.mode)
            if output in members:
                raise AdapterError("bundled destination collision", state=State.UNMANAGED)
            members[output] = member
            if len(members) > 3000:
                raise unknown("reference closure exceeds bounded package population")
        packages.append(ExpectedPackage(topic, f"claude-power-pack/.claude/skills/{topic}", members))
    result = tuple(packages)
    return ExpectedBuild(revision.commit, result, build_manifest_sha256(revision.commit, result))


class BuildAdapter:
    harness = "antigravity-build"

    def __init__(self, output: Path, *, expected_topics: frozenset[str] = TOPICS):
        self.output = absolute(output)
        self.expected_topics = expected_topics

    def preflight(self, request: Request) -> Policy:
        root = self.output
        source = request.revision.snapshot_root
        # Default source/antigravity/skills is intentional ignored build output.
        # Any other overlap could authorize mutation of canonical source files.
        if ((root.is_relative_to(source) and root != source / "antigravity/skills")
                or source.is_relative_to(root)):
            raise AdapterError("output overlaps canonical source", state=State.UNMANAGED)
        policy = Policy(root, root / ".cpp-managed/ownership.json", root / ".cpp-install.lock",
                        root / ".cpp-managed/work")
        scope = Scope(policy)
        # Default output descends no-follow from the source anchor. An explicit
        # destination approves its existing parent (including system aliases),
        # then the core opens the output root and descendants no-follow.
        try:
            if root.is_relative_to(source):
                anchor = Scope(Policy(source, source / ".unused-ledger", source / ".unused-lock",
                                      source / ".unused-work"))
                with anchor.directory(root.parent):
                    pass
            try:
                with scope.directory(root):
                    pass
            except FileNotFoundError:
                pass
        except AdapterError as exc:
            raise AdapterError("build-output alias refused", state=State.UNMANAGED) from exc
        return policy

    def discover(self, policy: Policy, request: Request) -> Discovery:
        return Discovery(True, False, ("explicit generated-output scope",))

    def build(self, revision: Revision, policy: Policy) -> ExpectedBuild:
        return build(revision, expected_topics=self.expected_topics)


def manifest(expected: ExpectedBuild) -> str:
    """Portable measurement payload, separate from filesystem ownership."""
    return json.dumps({"schema": 1, "revision": expected.revision, "manifest_sha256": expected.manifest_sha256,
                       "packages": {p.name: {n: {"sha256": m.sha256, "mode": m.mode}
                                              for n, m in sorted(p.members.items())}
                                    for p in expected.packages}}, sort_keys=True, indent=2) + "\n"
