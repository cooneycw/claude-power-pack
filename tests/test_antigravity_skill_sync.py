"""Real immutable build bytes feed the shared core; no host installation."""
import json
import posixpath
import shutil
import subprocess
from pathlib import Path

import pytest

from lib.antigravity_skills import TOPICS, BuildAdapter, build, link_parser, manifest
from lib.host_update.driver import inspect, refresh
from lib.host_update.models import AdapterError, Request, Revision

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required for pinned source")


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def source(tmp_path, extra=None):
    root = tmp_path / "source"
    root.mkdir()
    files = {".claude/skills/topic/SKILL.md": (
        b"---\nname: topic\ndescription: Fixture topic\nmetadata:\n  provenance:\n    class: cpp-authored\n---\n"
        b"Read `docs/skills/topic.md` and [guide](../../../docs/skills/topic.md#heading).\n"),
        "docs/skills/topic.md": b"# Intended guide\n[more](../reference/more.md)\n",
        "docs/reference/more.md": b"# More\n"}
    files.update(extra or {})
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "source")
    return Revision(git(root, "rev-parse", "HEAD").decode().strip(), root)


def test_actual_inventory_is_nonzero_deterministic_and_portable():
    revision = Revision(git(ROOT, "rev-parse", "HEAD").decode().strip(), ROOT)
    expected = build(revision)
    assert {p.name for p in expected.packages} == TOPICS and len(TOPICS) == 18
    assert expected == build(revision)
    assert json.loads(manifest(expected))["manifest_sha256"] == expected.manifest_sha256
    for package in expected.packages:
        skill = package.members["SKILL.md"].content.decode()
        assert "source: claude-power-pack/.claude/skills/" + package.name in skill
        assert "revision: " + revision.commit in skill
        for name, member in package.members.items():
            if name.endswith(".md"):
                for _line, target in link_parser().links_in(member.content.decode()):
                    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                    assert resolved in package.members or any(
                        p.startswith(resolved.rstrip("/") + "/") for p in package.members
                    ), (package.name, name, target)


def test_real_core_consumes_bundled_guides_and_preserves_modes(tmp_path):
    revision = source(tmp_path, {".claude/skills/topic/scripts/run.sh": b"#!/bin/sh\nprintf ok\n"})
    script = revision.snapshot_root / ".claude/skills/topic/scripts/run.sh"
    script.chmod(0o755)
    git(revision.snapshot_root, "add", ".")
    git(revision.snapshot_root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "executable")
    revision = Revision(git(revision.snapshot_root, "rev-parse", "HEAD").decode().strip(), revision.snapshot_root)
    expected = build(revision, expected_topics=frozenset({"topic"}))
    package = expected.packages[0]
    assert b"./references/docs/skills/topic.md" in package.members["SKILL.md"].content
    assert b"../reference/more.md" in package.members["references/docs/skills/topic.md"].content
    assert package.members["scripts/run.sh"].mode == 0o755
    adapter = BuildAdapter(tmp_path / "output", expected_topics=frozenset({"topic"}))
    request = Request(revision)
    assert refresh(adapter, request).exit_code == 0
    assert inspect(adapter, request).exit_code == 0
    guide = tmp_path / "output/topic/references/docs/skills/topic.md"
    guide.write_bytes(b"changed")
    assert guide.read_bytes() != package.members["references/docs/skills/topic.md"].content
    assert inspect(adapter, request).exit_code == 1
    assert refresh(adapter, request).exit_code == 1  # preserve hand edits
    assert guide.read_bytes() == b"changed"


def test_reference_style_image_and_html_resources_are_bundled(tmp_path):
    revision = source(tmp_path, {"docs/skills/topic.md": (
        b"[Extra][guide]\n\n[guide]: ../reference/more.md#section\n"
        b"![diagram](../reference/chart.png)\n<a href=\"../reference/more.md\">more</a>\n"
        b"```md\n[example](missing.md)\n```\n"),
        "docs/reference/chart.png": b"fixture image bytes"})
    package = build(revision, expected_topics=frozenset({"topic"})).packages[0]
    assert "references/docs/reference/chart.png" in package.members
    assert "references/docs/reference/more.md" in package.members
    text = package.members["references/docs/skills/topic.md"].content
    assert b"[guide]: ../reference/more.md#section" in text
    assert b"[example](missing.md)" in text


@pytest.mark.parametrize("kind", ["missing", "escape", "symlink", "zero"])
def test_required_inputs_never_skip_to_green(tmp_path, kind):
    revision = source(tmp_path)
    root = revision.snapshot_root
    if kind == "missing":
        (root / "docs/skills/topic.md").unlink()
        assert not (root / "docs/skills/topic.md").exists()
    elif kind == "escape":
        (root / ".claude/skills/topic/SKILL.md").write_bytes(
            b"---\nname: topic\ndescription: fixture\n---\n[x](../../../../outside.md)\n")
        assert b"../../../../outside" in (root / ".claude/skills/topic/SKILL.md").read_bytes()
    elif kind == "symlink":
        path = root / "docs/skills/topic.md"
        path.unlink()
        path.symlink_to("/never-read")
        assert path.is_symlink()
    else:
        shutil.rmtree(root / ".claude")
        assert not (root / ".claude").exists()
    git(root, "add", "-A")
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", kind)
    revision = Revision(git(root, "rev-parse", "HEAD").decode().strip(), root)
    with pytest.raises(AdapterError):
        build(revision, expected_topics=frozenset({"topic"}))
