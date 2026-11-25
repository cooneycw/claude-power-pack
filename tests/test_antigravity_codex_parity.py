"""Independent historical transforms on the same inputs, including parser code."""
import hashlib
import json
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls/antigravity-skill-build"


def inventory(output):
    return {p.relative_to(output).as_posix(): [hashlib.sha256(p.read_bytes()).hexdigest(),
                                             p.stat().st_mode & 0o777]
            for p in output.rglob("*") if p.is_file() and p.name != "README.md"}


def load(path, name):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    # Source material is shared; transform code and parser locations are not.
    for constant, suffix in (("REPO_ROOT", ""), ("SOURCE_ROOT", ".claude/commands"),
                             ("SCRIPTS_ROOT", "scripts"), ("DOCS_ROOT", "docs"),
                             ("CHARTERS_ROOT", "charters")):
        setattr(module, constant, ROOT / suffix)
    return module


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


@pytest.mark.parametrize("mask", [0o022, 0o002])
def test_two_generators_use_independent_parsers_and_identical_inputs(tmp_path, mask):
    data = baseline()
    pinned = load(CONTROL / data["generator_path"], "agy_pinned_codex")
    candidate = load(ROOT / "scripts/codex-skill-sync.py", "agy_current_codex")
    previous = os.umask(mask)
    try:
        actual = assert_parity(pinned, candidate, tmp_path)
        assert pinned._LINK_PARSER_CACHE and candidate._LINK_PARSER_CACHE
        assert set(pinned._LINK_PARSER_CACHE).isdisjoint(candidate._LINK_PARSER_CACHE)
        # Historical manifest was measured under 022. Both generators still
        # compare exact modes under either mask; only the historical byte
        # comparison is independent of that recorded process input.
        if mask == 0o022:
            delta = {p: actual.get(p) for p in actual.keys() | data["members"].keys()
                     if actual.get(p) != data["members"].get(p)}
            assert delta == {p: row["candidate"] for p, row in data["attributed_input_delta"].items()}
        else:
            assert {p: row[0] for p, row in actual.items()} == {
                p: row[0] for p, row in data["members"].items()}
        assert all(row["reason"] and row["source_commit"] for row in data["attributed_input_delta"].values())
    finally:
        os.umask(previous)


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


def test_missing_baseline_is_an_error_not_a_skip(tmp_path, monkeypatch):
    monkeypatch.setitem(baseline.__globals__, "CONTROL", tmp_path)
    assert not (tmp_path / "codex-baseline.json").exists()
    with pytest.raises(FileNotFoundError):
        baseline()
