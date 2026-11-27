"""Independent historical transforms on the same inputs, including parser code."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git required for tracked parity inputs")

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls/antigravity-skill-build"


def inventory(output):
    return {p.relative_to(output).as_posix(): [hashlib.sha256(p.read_bytes()).hexdigest(),
                                             p.stat().st_mode & 0o777]
            for p in output.rglob("*") if p.is_file() and p.name != "README.md"}


def load(path, name, source_root=ROOT):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    # Source material is shared; transform code and parser locations are not.
    for constant, suffix in (("REPO_ROOT", ""), ("SOURCE_ROOT", ".claude/commands"),
                             ("SCRIPTS_ROOT", "scripts"), ("DOCS_ROOT", "docs"),
                             ("CHARTERS_ROOT", "charters")):
        setattr(module, constant, source_root / suffix)
    return module


def canonical_source(destination):
    """Copy tracked working-tree inputs under the historical 022 modes.

    copy2 preserves the source checkout modes regardless of the generator's
    umask. CI checks out sources as 0666/0777; Git records only executability.
    Normalize disposable inputs, retaining exact output mode comparisons.
    Other workers plant temporary commands in the real tree (#1920); never
    enumerate those untracked inputs or hide failures to read tracked ones.
    """
    paths = subprocess.check_output([
        "git", "-c", "core.fsmonitor=false", "-c", f"safe.directory={ROOT}",
        "-C", str(ROOT), "ls-files", "-z", "--",
        ".claude/commands", "scripts", "docs", "charters", "lib", "controls",
    ], text=True)
    for name in paths.split("\0"):
        if not name:
            continue
        source, target = ROOT / name, destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
        if not target.is_symlink():
            target.chmod(0o755 if target.stat().st_mode & 0o111 else 0o644)
    return destination


def test_canonical_source_ignores_a_probe_removed_after_directory_listing(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    tracked = {
        ".claude/commands/_tracked_probe_/auto.md": "tracked driver\n",
        "scripts/executable.py": "#!/usr/bin/env python3\n",
        "docs/guide.md": "tracked guide\n",
        "charters/README.md": "tracked charter\n",
        "lib/module.py": "# tracked module\n",
        "controls/case.txt": "tracked control\n",
    }
    for name, content in tracked.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o777 if name == "scripts/executable.py" else 0o666)
    link = source / "controls/guide-link"
    link.symlink_to("../docs/guide.md")
    subprocess.run(["git", "init", "--quiet", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    probe = source / ".claude/commands/_closing_report_probe_"
    probe.mkdir()
    (probe / "auto.md").write_text("transient untracked driver\n")
    indexed = subprocess.check_output(["git", "-C", str(source), "ls-files", "-z"], text=True).split("\0")
    assert ".claude/commands/_closing_report_probe_/auto.md" not in indexed
    assert ".claude/commands/_tracked_probe_/auto.md" in indexed
    assert probe.is_dir() and (probe / "auto.md").is_file()
    assert (source / "docs/guide.md").stat().st_mode & 0o777 == 0o666
    assert (source / "scripts/executable.py").stat().st_mode & 0o777 == 0o777
    original_scandir = os.scandir

    @contextmanager
    def list_then_remove(path):
        with original_scandir(path) as rows:
            entries = list(rows)
        if path == source / ".claude/commands":
            assert any(row.name == probe.name for row in entries)
            (probe / "auto.md").unlink()
            probe.rmdir()
        yield iter(entries)

    monkeypatch.setattr(os, "scandir", list_then_remove)
    monkeypatch.setitem(canonical_source.__globals__, "ROOT", source)
    output = tmp_path / "inputs"
    try:
        canonical_source(output)
        assert not (output / ".claude/commands/_closing_report_probe_").exists()
        for name, content in tracked.items():
            assert (output / name).read_text() == content
            expected = 0o755 if name == "scripts/executable.py" else 0o644
            assert (output / name).stat().st_mode & 0o777 == expected
        assert (output / "controls/guide-link").is_symlink()
        assert (output / "controls/guide-link").readlink() == link.readlink()
    finally:
        if probe.exists():
            (probe / "auto.md").unlink()
            probe.rmdir()


def test_canonical_source_stops_if_git_cannot_list_inputs(tmp_path, monkeypatch):
    def cannot_list(*args, **kwargs):
        raise subprocess.CalledProcessError(128, "git ls-files", stderr="input listing unavailable")

    monkeypatch.setattr(subprocess, "check_output", cannot_list)
    assert subprocess.check_output is cannot_list
    output = tmp_path / "inputs"
    with pytest.raises(subprocess.CalledProcessError, match="128"):
        canonical_source(output)
    assert not output.exists()


def test_canonical_source_stops_on_a_missing_tracked_input(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    tracked = source / "docs/guide.md"
    tracked.parent.mkdir()
    tracked.write_text("tracked guide\n")
    subprocess.run(["git", "init", "--quiet", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    tracked.unlink()
    assert not tracked.exists()
    assert subprocess.check_output(["git", "-C", str(source), "ls-files"], text=True).strip() == "docs/guide.md"
    monkeypatch.setitem(canonical_source.__globals__, "ROOT", source)
    with pytest.raises(FileNotFoundError):
        canonical_source(tmp_path / "inputs")


def test_canonical_source_trusts_only_its_explicit_repository(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    tracked = source / "docs/guide.md"
    tracked.parent.mkdir()
    tracked.write_text("tracked guide\n")
    subprocess.run(["git", "init", "--quiet", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    refused = subprocess.run(["git", "-C", str(source), "ls-files"], capture_output=True, text=True)
    assert refused.returncode == 128 and "dubious ownership" in refused.stderr
    monkeypatch.setitem(canonical_source.__globals__, "ROOT", source)
    output = canonical_source(tmp_path / "inputs")
    assert (output / "docs/guide.md").read_bytes() == tracked.read_bytes()
    # The command-scoped trust must not change global Git configuration.
    still_refused = subprocess.run(["git", "-C", str(source), "ls-files"], capture_output=True, text=True)
    assert still_refused.returncode == 128 and "dubious ownership" in still_refused.stderr


def baseline():
    data = json.loads((CONTROL / "codex-baseline.json").read_text())
    assert data["commit"] == "40d25173c8c09987fac851cffa565efdc0f11c72"
    for prefix in ("generator", "parser"):
        path = CONTROL / data[prefix + "_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == data[prefix + "_sha256"]
    return data


def assert_parity(pinned, candidate, output):
    assert pinned.main(["--write", "--output-root", str(output / "pinned")]) == 0
    assert candidate.main(["--write", "--output-root", str(output / "candidate")]) == 0
    left, right = inventory(output / "pinned"), inventory(output / "candidate")
    assert left and left == right, "Codex transform parity differs"
    return right


def assert_attribution(data, actual, mask):
    # Canonical inputs have Git's 0644/0755 modes. The independent generators
    # above still compare exact output modes. Only this comparison to the
    # historical 022 measurement removes the extra group-write bit from a
    # 002-created file; it never normalizes the generator-to-generator oracle.
    assert mask in (0o022, 0o002)
    comparable = {p: [row[0], row[1] & ~0o020 if mask == 0o002 else row[1]]
                  for p, row in actual.items()}
    delta = {p: comparable.get(p) for p in comparable.keys() | data["members"].keys()
             if comparable.get(p) != data["members"].get(p)}
    attributed = data["attributed_input_delta"]
    assert delta == {p: row["candidate"] for p, row in attributed.items()}, json.dumps(delta, sort_keys=True)
    for path, row in attributed.items():
        assert row.get("baseline") == data["members"].get(path), "attribution must retain the historical before value"
        assert row["reason"].strip() and len(row["source_commit"]) in (40, 64)
        assert all(c in "0123456789abcdef" for c in row["source_commit"])
        candidate = row["candidate"]
        assert candidate != data["members"].get(path), "attribution must represent a real input delta"
        if candidate is not None:
            assert len(candidate[0]) == 64 and all(c in "0123456789abcdef" for c in candidate[0])
            assert type(candidate[1]) is int and candidate[1] in (0o644, 0o755)


@pytest.mark.parametrize("mask", [0o022, 0o002])
def test_two_generators_use_independent_parsers_and_identical_inputs(tmp_path, mask):
    data = baseline()
    source = canonical_source(tmp_path / "inputs")
    pinned = load(CONTROL / data["generator_path"], "agy_pinned_codex", source)
    candidate = load(ROOT / "scripts/codex-skill-sync.py", "agy_current_codex", source)
    previous = os.umask(mask)
    try:
        actual = assert_parity(pinned, candidate, tmp_path)
        assert pinned._LINK_PARSER_CACHE and candidate._LINK_PARSER_CACHE
        assert set(pinned._LINK_PARSER_CACHE).isdisjoint(candidate._LINK_PARSER_CACHE)
        assert_attribution(data, actual, mask)
    finally:
        os.umask(previous)



def _assert_self_bundled_input_variation(tmp_path, mask):
    data = baseline()
    frozen_path = CONTROL / data["generator_path"]
    current_path = ROOT / "scripts/codex-skill-sync.py"
    frozen_bytes, current_bytes = frozen_path.read_bytes(), current_path.read_bytes()
    assert current_bytes != frozen_bytes, "the approved data deletion must vary the bundled source input"
    old_source = canonical_source(tmp_path / "old-inputs")
    new_source = canonical_source(tmp_path / "new-inputs")
    (old_source / "scripts/codex-skill-sync.py").write_bytes(frozen_bytes)
    variants = (
        ("before", frozen_path, old_source),
        ("after", current_path, new_source),
        ("frozen-on-after", frozen_path, new_source),
    )
    outputs, modules = [], []
    previous = os.umask(mask)
    try:
        for label, code, inputs in variants:
            module = load(code, f"self_bundle_{label}_{mask}", inputs)
            output = tmp_path / label
            assert module.main(["--write", "--output-root", str(output)]) == 0
            outputs.append(output)
            modules.append(module)
    finally:
        os.umask(previous)
    before, after, frozen_after = [inventory(output) for output in outputs]
    assert len(data["members"]) == 404, "the historical population stays immutable"
    expected_members = set(data["members"])
    for name, row in data["attributed_input_delta"].items():
        if row["candidate"] is None:
            expected_members.discard(name)
        else:
            expected_members.add(name)
    assert set(before) == set(after) == set(frozen_after) == expected_members
    assert after == frozen_after, "transforms must agree on identical new inputs"
    assert set(modules[1]._LINK_PARSER_CACHE).isdisjoint(modules[2]._LINK_PARSER_CACHE)
    # Equal transforms alone cannot prove the input was varied: the old input
    # makes both agree too. These actual bundled bytes close that blind spot.
    expected = set()
    for consumer in ("flow-auto", "flow-finish"):
        name = f"{consumer}/scripts/codex-skill-sync.py"
        assert (outputs[0] / name).read_bytes() == frozen_bytes
        # The deliberate mismatch must not ask pytest to diff whole generator
        # sources: CI=true enables an expensive full iterable diff for bytes.
        is_current = (outputs[1] / name).read_bytes() == current_bytes
        assert is_current, "bundled generator input was held old"
        expected.update((name, f"{consumer}/scripts/SHA256SUMS"))
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    assert changed == expected, "only two self-bundled source copies and their checksums may change"
    assert all(before[name][1] == after[name][1] for name in changed), "input variation must retain modes"
    print(f"self-bundle {mask:03o}: four input deltas, zero same-input transform deltas")


@pytest.mark.parametrize("mask", [0o022, 0o002])
def test_bundled_generator_input_variation_is_measured(tmp_path, mask):
    _assert_self_bundled_input_variation(tmp_path, mask)


@pytest.mark.parametrize("mask", [0o022, 0o002])
def test_bundled_input_variation_rejects_held_old_input(tmp_path, monkeypatch, mask):
    real_copy = canonical_source
    current = (ROOT / "scripts/codex-skill-sync.py").read_bytes()
    frozen = (CONTROL / baseline()["generator_path"]).read_bytes()
    assert current != frozen

    def hold_old(destination):
        source = real_copy(destination)
        member = source / "scripts/codex-skill-sync.py"
        assert member.read_bytes() == current, "the real copier must start with the changed input"
        member.write_bytes(frozen)
        assert member.read_bytes() != current, "the negative fixture must hold the old input"
        return source

    monkeypatch.setitem(_assert_self_bundled_input_variation.__globals__, "canonical_source", hold_old)
    with pytest.raises(AssertionError, match="bundled generator input was held old") as rejected:
        _assert_self_bundled_input_variation(tmp_path, mask)
    assert len(str(rejected.value)) < 256, "held-old rejection must have a bounded diagnostic"
    print(f"held-old-input {mask:03o}: RED bundled-member assertion despite equal transforms")

def test_changed_transform_is_detected(tmp_path, monkeypatch):
    data = baseline()
    pinned = load(CONTROL / data["generator_path"], "agy_transform_pinned")
    candidate = load(ROOT / "scripts/codex-skill-sync.py", "agy_transform_candidate")
    original = candidate.generate_skill

    def changed(*args, **kwargs):
        files = original(*args, **kwargs)
        return {**files, "SKILL.md": files["SKILL.md"] + "\nChanged transform control.\n"}

    monkeypatch.setattr(candidate, "generate_skill", changed)
    assert candidate.generate_skill is changed
    with pytest.raises(AssertionError, match="transform parity"):
        assert_parity(pinned, candidate, tmp_path)
    assert next((tmp_path / "candidate").glob("*/SKILL.md")).read_text().endswith(
        "Changed transform control.\n")


def test_changed_parser_is_detected(tmp_path):
    data = baseline()
    generator = tmp_path / "codex-skill-sync.py"
    generator.write_bytes((ROOT / "scripts/codex-skill-sync.py").read_bytes())
    parser = tmp_path / "check-md-relative-links.py"
    parser.write_bytes((ROOT / "scripts/check-md-relative-links.py").read_bytes()
                       + b"\ndef links_in(text):\n    return []\n")
    assert parser.read_bytes().endswith(b"def links_in(text):\n    return []\n")
    pinned = load(CONTROL / data["generator_path"], "agy_parser_pinned")
    candidate = load(generator, "agy_parser_candidate")
    text = "Read [bundled guide](../../../docs/skills/python-packaging.md).\n"
    source = ROOT / ".claude/commands/browser/help.md"
    left = pinned.rewrite_mirror_links(text, source, "SKILL.md", set())
    right = candidate.rewrite_mirror_links(text, source, "SKILL.md", set())
    assert left != text and right == text  # prove the link was eligible before corruption
    with pytest.raises(AssertionError):
        assert left == right, "Codex parser parity differs"
    with pytest.raises(AssertionError, match="transform parity"):
        assert_parity(pinned, candidate, tmp_path / "parser-trees")


def test_missing_baseline_is_an_error_not_a_skip(tmp_path, monkeypatch):
    monkeypatch.setitem(baseline.__globals__, "CONTROL", tmp_path)
    assert not (tmp_path / "codex-baseline.json").exists()
    with pytest.raises(FileNotFoundError):
        baseline()


@pytest.mark.parametrize("mode", [0o666, 0o755])
def test_changed_output_mode_is_detected(tmp_path, monkeypatch, mode):
    data = baseline()
    pinned = load(CONTROL / data["generator_path"], "agy_mode_pinned")
    candidate = load(ROOT / "scripts/codex-skill-sync.py", "agy_mode_candidate")
    original = candidate.main

    def changed(argv):
        result = original(argv)
        skill = next((tmp_path / "candidate").glob("*/SKILL.md"))
        skill.chmod(mode)
        assert skill.stat().st_mode & 0o777 == mode
        return result

    monkeypatch.setattr(candidate, "main", changed)
    previous = os.umask(0o022)
    try:
        with pytest.raises(AssertionError, match="transform parity"):
            assert_parity(pinned, candidate, tmp_path)
    finally:
        os.umask(previous)


@pytest.mark.parametrize("mask", [0o022, 0o002])
def test_nonempty_attribution_is_consumed_under_both_masks(mask):
    data = {"members": {"flow-auto/SKILL.md": ["a" * 64, 0o644]},
            "attributed_input_delta": {"flow-auto/SKILL.md": {
                "baseline": ["a" * 64, 0o644], "candidate": ["b" * 64, 0o644],
                "reason": "controlled source input change",
                "source_commit": "c" * 40}}}
    actual = {"flow-auto/SKILL.md": ["b" * 64, 0o644 if mask == 0o022 else 0o664]}
    assert data["attributed_input_delta"] and actual["flow-auto/SKILL.md"][0] != "a" * 64
    assert_attribution(data, actual, mask)


@pytest.mark.parametrize("mask", [0o022, 0o002])
@pytest.mark.parametrize("fault", ["hash", "mode", "unexpected-world-write", "missing-delta",
                                   "reason", "source-commit", "baseline-hash", "baseline-mode"])
def test_wrong_attribution_is_detected_under_both_masks(mask, fault):
    row = {"baseline": ["a" * 64, 0o644], "candidate": ["b" * 64, 0o644],
           "reason": "controlled source input change",
           "source_commit": "c" * 40}
    data = {"members": {"flow-auto/SKILL.md": ["a" * 64, 0o644]},
            "attributed_input_delta": {"flow-auto/SKILL.md": row}}
    actual = {"flow-auto/SKILL.md": ["b" * 64, 0o644 if mask == 0o022 else 0o664]}
    assert_attribution(data, actual, mask)
    if fault == "hash":
        row["candidate"][0] = "d" * 64
        assert row["candidate"][0] != actual["flow-auto/SKILL.md"][0]
    elif fault == "mode":
        row["candidate"][1] = 0o755
        assert row["candidate"][1] != actual["flow-auto/SKILL.md"][1]
    elif fault == "unexpected-world-write":
        actual["flow-auto/SKILL.md"][1] = 0o666
        assert actual["flow-auto/SKILL.md"][1] & 0o002
    elif fault == "missing-delta":
        data["attributed_input_delta"].clear()
        assert not data["attributed_input_delta"]
    elif fault == "baseline-hash":
        row["baseline"][0] = "d" * 64
        assert row["baseline"][0] != data["members"]["flow-auto/SKILL.md"][0]
    elif fault == "baseline-mode":
        row["baseline"][1] = 0o755
        assert row["baseline"][1] != data["members"]["flow-auto/SKILL.md"][1]
    elif fault == "reason":
        row["reason"] = ""
        assert not row["reason"]
    else:
        row["source_commit"] = "short"
        assert len(row["source_commit"]) != 40
    with pytest.raises(AssertionError):
        assert_attribution(data, actual, mask)


@pytest.mark.parametrize("field", ["commit", "generator_sha256", "parser_sha256"])
def test_historical_pin_replacement_is_detected(tmp_path, monkeypatch, field):
    data = baseline()
    for key in ("generator_path", "parser_path"):
        target = tmp_path / data[key]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CONTROL / data[key], target)
    replacement = "f" * (40 if field == "commit" else 64)
    assert data[field] != replacement
    data[field] = replacement
    (tmp_path / "codex-baseline.json").write_text(json.dumps(data))
    monkeypatch.setitem(baseline.__globals__, "CONTROL", tmp_path)
    with pytest.raises(AssertionError):
        baseline()
