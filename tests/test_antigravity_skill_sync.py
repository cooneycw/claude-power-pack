"""Real immutable build bytes feed the shared core; no host installation."""
import argparse
import hashlib
import importlib.util
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lib.antigravity_skills import TOPICS, BuildAdapter, Snapshot, build, link_parser, manifest
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
        "docs/skills/topic.md": b"# Intended guide\n[more](reference/more.md)\n",
        "docs/skills/reference/more.md": b"# More\n",
        "scripts/check-md-relative-links.py": (ROOT / "scripts/check-md-relative-links.py").read_bytes()}
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
    assert b"./reference/more.md" in package.members["references/docs/skills/topic.md"].content
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
        b"[Extra][guide]\n\n[guide]: reference/more.md#section\n"
        b"![diagram](images/chart.png)\n<a href=\"reference/more.md\">more</a>\n"
        b"```md\n[example](missing.md)\n```\n"),
        "docs/skills/images/chart.png": b"fixture image bytes"})
    package = build(revision, expected_topics=frozenset({"topic"})).packages[0]
    assert "references/docs/skills/images/chart.png" in package.members
    assert "references/docs/skills/reference/more.md" in package.members
    text = package.members["references/docs/skills/topic.md"].content
    assert b"[guide]: ./reference/more.md#section" in text
    assert b"[example](missing.md)" in text


def test_output_alias_is_refused_before_descendant_metadata(tmp_path, monkeypatch):
    revision = source(tmp_path)
    protected = tmp_path / "protected"
    protected.mkdir()
    alias = revision.snapshot_root / "antigravity"
    alias.symlink_to(protected, target_is_directory=True)
    assert alias.is_symlink()
    original = Path.is_symlink

    def guarded(path):
        if path != alias and path.is_relative_to(alias):
            raise AssertionError("metadata descended through an unchecked alias")
        return original(path)

    monkeypatch.setattr(Path, "is_symlink", guarded)
    result = refresh(BuildAdapter(alias / "skills", expected_topics=frozenset({"topic"})), Request(revision))
    assert result.exit_code == 1 and "alias refused" in result.reason
    assert not list(protected.iterdir())


def probe_module():
    path = ROOT / "docs/measurements/antigravity-topic-builder.probe.py"
    spec = importlib.util.spec_from_file_location("agy_topic_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_probe_acceptance_oracle_detects_wrong_hash_decoy_and_missing_guide(tmp_path):
    probe = probe_module()
    guide = tmp_path / "installed/references/guide.md"
    guide.parent.mkdir(parents=True)
    guide.write_bytes(b"fixture guide tail")
    digest = probe.digest(guide.read_bytes())
    good = {"status": "read", "path": str(guide), "sha256": digest, "tail": "fixture guide tail"}
    assert probe.matches_response("positive", good, guide, digest, good["tail"], 0)
    for bad in (dict(good, sha256="wrong"), dict(good, path=str(tmp_path / "project/guide.md")),
                dict(good, tail="DECOY"), {"status": "missing", "path": str(guide), "sha256": "", "tail": ""}):
        assert bad != good
        assert not probe.matches_response("positive", bad, guide, digest, good["tail"], 0)
    assert not probe.matches_response("positive", good, guide, digest, good["tail"], 1)
    missing = {"status": "missing", "path": str(guide), "sha256": "", "tail": ""}
    assert guide.exists()
    assert not probe.matches_response("missing-guide", missing, guide, digest, good["tail"], 0)
    guide.unlink()
    assert not guide.exists()
    assert probe.matches_response("missing-guide", missing, guide, digest, good["tail"], 0)
    assert not probe.matches_response("missing-guide", good, guide, digest, good["tail"], 0)


def test_live_probe_profile_guard_rejects_alias_before_descendant_metadata(tmp_path, monkeypatch):
    probe = probe_module()
    profile = tmp_path / ".agy-probe-home"
    profile.mkdir()
    protected = tmp_path / "protected"
    protected.mkdir()
    alias = profile / ".gemini"
    alias.symlink_to(protected, target_is_directory=True)
    assert alias.is_symlink()
    original = Path.is_symlink

    def guarded(path):
        if path != alias and path.is_relative_to(alias):
            raise AssertionError("profile guard followed an unchecked alias")
        return original(path)

    monkeypatch.setattr(Path, "is_symlink", guarded)
    with pytest.raises(RuntimeError, match="profile alias refused"):
        probe.profile_paths_safe(profile, (profile / ".gemini/config/skills",))


def test_probe_help_accepts_stderr_without_weakening_contract_checks():
    probe = probe_module()
    help_text = pinned_agy_help()
    stderr_help = subprocess.CompletedProcess(["agy", "--help"], 0, stdout="", stderr=help_text)
    assert stderr_help.stdout == "" and all(flag in stderr_help.stderr for flag in (
        "--print", "--dangerously-skip-permissions", "--output-format", "--print-timeout"))
    assert probe.checked_help(stderr_help) == help_text
    stdout_help = subprocess.CompletedProcess(["agy", "--help"], 0, stdout=help_text, stderr="")
    assert probe.checked_help(stdout_help) == help_text
    for invalid in (subprocess.CompletedProcess(["agy", "--help"], 1, stdout="", stderr=help_text),
                    subprocess.CompletedProcess(["agy", "--help"], 0, stdout="", stderr="unrelated output")):
        with pytest.raises(RuntimeError):
            probe.checked_help(invalid)


def pinned_agy_help():
    raw = (ROOT / "controls/antigravity-skill-build/reference/agy-1.5.17-help.txt").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "ce786669ed163e82508a7b2d36196e416093149f9a8e0436c2068c9e99740e89"
    return raw.decode()


def test_probe_consumer_argv_matches_documented_agy_1517_flag_forms():
    probe = probe_module()
    help_text = pinned_agy_help()
    descriptions = dict(re.findall(r"(?m)^  (-{1,2}[^\s]+) +(.+)$", help_text))
    assert descriptions["-p"] == "Short alias for --print"
    assert "single prompt non-interactively" in descriptions["--print"]
    assert "Auto-approve all tool permission requests" in descriptions["--dangerously-skip-permissions"]
    assert "(default 0s)" in descriptions["--print-timeout"]
    formats = re.search(r"\((text, [^)]+)\)", descriptions["--output-format"]).group(1).split(", ")

    def duration(value):
        # Help records default 0s; the native 1.5.17 failure in mailbox 40290
        # confirms '180' is invalid and the value takes a Go duration.
        if not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]+)?(?:ns|us|ms|s|m|h))+", value):
            raise argparse.ArgumentTypeError("duration requires its unit")
        return value

    contract = argparse.ArgumentParser(allow_abbrev=False)
    contract.add_argument("--dangerously-skip-permissions", action="store_true", required=True)
    contract.add_argument("--output-format", choices=formats, required=True)
    contract.add_argument("--print-timeout", type=duration, required=True)
    contract.add_argument("-p", "--print", dest="print_mode", action="store_true", required=True)
    contract.add_argument("prompt")
    prompt = "Use python-packaging and read its bundled guide."
    argv = probe.consumer_argv(Path("/fixture/.local/bin/agy"), prompt)
    assert Path(argv[0]).is_absolute() and Path(argv[0]).name == "agy"
    parsed = contract.parse_args(argv[1:])
    assert parsed.output_format == "json" and parsed.print_timeout == "180s"
    assert parsed.dangerously_skip_permissions and parsed.print_mode and parsed.prompt == prompt
    assert argv[-2:] == ["-p", prompt]
    bad_duration = list(argv)
    bad_duration[bad_duration.index("--print-timeout") + 1] = "180"
    bad_enum = list(argv)
    bad_enum[bad_enum.index("--output-format") + 1] = "yaml"
    bad_boolean = [*argv[:2], "false", *argv[2:]]
    for invalid in (bad_duration, bad_enum, bad_boolean, argv[:-1]):
        assert invalid != argv
        with pytest.raises(SystemExit):
            contract.parse_args(invalid[1:])


def test_probe_consumer_environment_changes_only_home_and_logs_names(tmp_path, capsys):
    probe = probe_module()
    inherited = {name: f"private-sentinel-{index}" for index, name in enumerate((
        "HOME", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
        "XDG_STATE_HOME", "XDG_CACHE_HOME", "UV_CACHE_DIR", "GIT_OPTIONAL_LOCKS", "OTHER_SETTING"))}
    original = dict(inherited)
    profile = tmp_path / ".agy-probe-home"
    child = probe.consumer_environment(inherited, profile, tmp_path / "scratch")
    assert child["DBUS_SESSION_BUS_ADDRESS"] == inherited["DBUS_SESSION_BUS_ADDRESS"]
    assert child == {**inherited, "HOME": str(profile)}
    assert inherited == original
    report = probe.environment_names(child, ("HOME",))
    assert report == {"set_names": ["HOME"], "inherited_names": sorted(set(inherited) - {"HOME"})}
    probe.emit("consumer-env", **report)
    logged = capsys.readouterr().out
    assert all(value not in logged for value in inherited.values())
    assert str(profile) not in logged


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


def test_missing_plain_guide_instruction_is_unknown(tmp_path):
    revision = source(tmp_path, {".claude/skills/topic/SKILL.md": (
        b"---\nname: topic\ndescription: Fixture\n---\nRead `docs/skills/missing.md`.\n")})
    assert not (revision.snapshot_root / "docs/skills/missing.md").exists()
    with pytest.raises(AdapterError, match="required guide") as error:
        build(revision, expected_topics=frozenset({"topic"}))
    assert error.value.exit_code == 4


def test_topic_closure_routes_unrelated_corpus_and_directories_upstream(tmp_path, monkeypatch):
    revision = source(tmp_path, {"docs/skills/topic.md": (
        b"# Topic guide\n[index](../scripts.md) [directory](../research/) "
        b"[helper](../../scripts/unallowed.py)\n"),
        "docs/scripts.md": b"[history](research/large.md)\n",
        "docs/research/large.md": b"Unrelated historical corpus\n",
        "scripts/unallowed.py": b"import lib.unbundled\n"})
    original = Snapshot.read

    def bounded_read(snapshot, path):
        assert path not in {"docs/scripts.md", "docs/research/large.md", "scripts/unallowed.py"}
        return original(snapshot, path)

    monkeypatch.setattr(Snapshot, "read", bounded_read)
    package = build(revision, expected_topics=frozenset({"topic"})).packages[0]
    assert set(package.members) == {"SKILL.md", "references/docs/skills/topic.md"}
    text = package.members["references/docs/skills/topic.md"].content.decode()
    upstream = "https://github.com/cooneycw/claude-power-pack/"
    assert upstream + f"blob/{revision.commit}/docs/scripts.md" in text
    assert upstream + f"tree/{revision.commit}/docs/research/" in text
    assert upstream + f"blob/{revision.commit}/scripts/unallowed.py" in text


def test_system_alias_above_approved_output_prefix_is_supported(tmp_path):
    actual = tmp_path / "actual-home"
    actual.mkdir()
    alias = tmp_path / "system-home"
    alias.symlink_to(actual, target_is_directory=True)
    assert alias.is_symlink()
    fixture = alias / "fixture"
    fixture.mkdir()
    revision = source(fixture)
    adapter = BuildAdapter(fixture / "output", expected_topics=frozenset({"topic"}))
    result = refresh(adapter, Request(revision))
    assert result.exit_code == 0, result.reason
    assert inspect(adapter, Request(revision)).exit_code == 0


def test_explicit_system_alias_parent_is_a_trusted_prefix_but_root_alias_is_refused(tmp_path):
    revision = source(tmp_path)
    actual = tmp_path / "actual-home"
    actual.mkdir()
    alias = tmp_path / "system-home"
    alias.symlink_to(actual, target_is_directory=True)
    assert alias.is_symlink()
    adapter = BuildAdapter(alias / "skills", expected_topics=frozenset({"topic"}))
    assert refresh(adapter, Request(revision)).exit_code == 0
    root_alias = actual / "skills-alias"
    root_alias.symlink_to(actual / "skills", target_is_directory=True)
    assert root_alias.is_symlink()
    assert refresh(BuildAdapter(root_alias, expected_topics=frozenset({"topic"})), Request(revision)).exit_code == 1


def test_parser_transform_is_read_from_pinned_source_snapshot(tmp_path):
    parser = (ROOT / "scripts/check-md-relative-links.py").read_bytes()
    revision = source(tmp_path, {"scripts/check-md-relative-links.py": (
        parser + b"\nFENCE_RE = re.compile(r'(?!)')\n"),
        "docs/skills/topic.md": b"```md\n[example](missing.md)\n```\n"})
    assert b"FENCE_RE = re.compile(r'(?!)')" in (
        revision.snapshot_root / "scripts/check-md-relative-links.py").read_bytes()
    with pytest.raises(AdapterError, match="unresolved local reference"):
        build(revision, expected_topics=frozenset({"topic"}))


def test_only_allowlisted_external_script_travels_and_loads_without_checkout(tmp_path):
    revision = Revision(git(ROOT, "rev-parse", "HEAD").decode().strip(), ROOT)
    expected = build(revision)
    scripts = {(p.name, name) for p in expected.packages for name in p.members
               if name.startswith("references/scripts/")}
    assert scripts == {("documentation", "references/scripts/c4-mermaid.py")}
    script = tmp_path / "c4-mermaid.py"
    package = next(p for p in expected.packages if p.name == "documentation")
    script.write_bytes(package.members["references/scripts/c4-mermaid.py"].content)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run([sys.executable, str(script), "--help"], cwd=tmp_path,
                            capture_output=True, text=True, env=env)
    assert result.returncode == 0 and "--model" in result.stdout
