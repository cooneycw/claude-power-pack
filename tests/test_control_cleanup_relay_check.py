"""Exercise the real lexical guard with its committed opposite inputs."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/check-control-cleanup-relay.py"
CONTROL = ROOT / "controls/control-cleanup-relay"
SPEC = json.loads((CONTROL / "control.json").read_text())


def invoke(root):
    return subprocess.run([sys.executable, str(GATE), "--root", str(root)],
                          capture_output=True, text=True, check=False, timeout=15)


@pytest.mark.parametrize("case", SPEC["cases"], ids=lambda case: case["name"])
def test_committed_shape_controls(tmp_path, case):
    implementations = tmp_path / "controls/example"
    implementations.mkdir(parents=True)
    source = CONTROL / case["input"] / "source.txt"
    if source.exists():
        shutil.copyfile(source, implementations / "run-case.py")
    answer = invoke(tmp_path)
    expected = {"GOOD": 0, "BAD": 1, "UNKNOWN": 2}[case["expect"]]
    assert answer.returncode == expected, answer.stdout + answer.stderr
    assert f"CONTROL_RELAY: {case['expect'].lower() if expected else 'ok'} - " in answer.stdout


def test_real_control_implementations_are_examined():
    answer = invoke(ROOT)
    assert answer.returncode == 0, answer.stdout + answer.stderr
    assert "CONTROL_RELAY_FILES: 0\n" not in answer.stdout
    assert "CONTROL_RELAY: ok - " in answer.stdout


def test_nested_temporary_context_reports_one_site(tmp_path):
    implementations = tmp_path / "controls/example"
    implementations.mkdir(parents=True)
    (implementations / "run-case.py").write_text(
        "import tempfile\nwith tempfile.TemporaryDirectory():\n"
        "    with tempfile.TemporaryDirectory():\n        print(result.stdout)\n")
    answer = invoke(tmp_path)
    assert answer.returncode == 1, answer.stdout
    assert answer.stdout.count("CONTROL_RELAY_SITE:") == 1


def test_parse_failure_is_unknown_even_with_a_known_bad_site(tmp_path):
    implementations = tmp_path / "controls/example"
    implementations.mkdir(parents=True)
    shutil.copyfile(CONTROL / "cases/bad-old-shape/source.txt", implementations / "bad.py")
    (implementations / "unreadable.py").write_bytes(b"\xff")
    answer = invoke(tmp_path)
    assert answer.returncode == 2, answer.stdout
    assert "CONTROL_RELAY_SITE:" in answer.stdout
    assert "CONTROL_RELAY: unknown - " in answer.stdout
    assert "CONTROL_RELAY: bad - " not in answer.stdout


def test_fixture_only_tree_does_not_satisfy_nonempty_population(tmp_path):
    fixtures = tmp_path / "controls/example/cases"
    fixtures.mkdir(parents=True)
    (fixtures / "broken.py").write_text("deliberately invalid fixture (\n")
    answer = invoke(tmp_path)
    assert answer.returncode == 2, answer.stdout
    assert "CONTROL_RELAY_FILES: 0\n" in answer.stdout
    assert "CONTROL_RELAY_FIXTURE_TREES: 1 " in answer.stdout


def test_implementation_symlink_is_unexamined(tmp_path):
    implementations = tmp_path / "controls/example"
    implementations.mkdir(parents=True)
    target = tmp_path / "outside.py"
    target.write_text("print('outside implementation population')\n")
    (implementations / "linked.py").symlink_to(target)
    answer = invoke(tmp_path)
    assert answer.returncode == 2, answer.stdout
    assert "implementation file is a symlink" in answer.stdout
