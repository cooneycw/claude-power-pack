"""CI entry admission on controlled identities; real root acceptance is separate."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PIN = "test/image@sha256:" + "a" * 64
OTHER_PIN = "test/image@sha256:" + "b" * 64
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
CONTEXT_CASES = ("legacy-context", "missing-pipeline", "invalid-pipeline", "zero-pipeline", "missing-commit",
                 "malformed-commit", "mismatched-commit")


def test_required_ci_step_is_pinned_and_can_overlap_validate():
    steps = yaml.safe_load((ROOT / ".woodpecker.yml").read_text())["steps"]
    assert "ci-shape" in steps, "required CI qualification has no pipeline consumer"
    step = steps["ci-shape"]
    assert step["image"] == steps["validate"]["image"] and "@sha256:" in step["image"]
    assert set(step["depends_on"]) == {
        "secret-scan", "make-stage", "git-stage", "codex-skills-generate"}
    assert step["commands"] == [
        'PATH="$PWD/.ci-bin:$PATH" make ci-shape-ci CI_SHAPE_RECEIPT=.ci-shape/ci.json']


def exercise(gate, temporary, case, monkeypatch):
    spec = importlib.util.spec_from_file_location("ci_shape_entry_subject", gate)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = temporary / "source"
    root.mkdir()
    ci_image = OTHER_PIN if case == "mismatched-image" else PIN
    config = "steps:\n  validate:\n    image: " + PIN + "\n"
    if case != "missing-image":
        config += "  ci-shape:\n    image: " + ci_image + "\n"
    (root / ".woodpecker.yml").write_text(config)
    git = ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid"]
    subprocess.run([*git, "init", "-q", str(root)], check=True, capture_output=True)
    subprocess.run([*git, "-C", str(root), "add", ".woodpecker.yml"], check=True, capture_output=True)
    subprocess.run([*git, "-C", str(root), "commit", "-qm", "controlled source"],
                   check=True, capture_output=True)
    head = subprocess.check_output([*git, "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setenv("CI", "woodpecker")
    monkeypatch.setenv("CI_PIPELINE_NUMBER", "4105")
    monkeypatch.setenv("CI_COMMIT_SHA", head)
    if case == "missing-context":
        monkeypatch.delenv("CI", raising=False)
    elif case == "legacy-context":
        monkeypatch.setenv("CI", "true")
    elif case == "missing-pipeline":
        monkeypatch.delenv("CI_PIPELINE_NUMBER")
    elif case == "invalid-pipeline":
        monkeypatch.setenv("CI_PIPELINE_NUMBER", "4105-forged")
    elif case == "zero-pipeline":
        monkeypatch.setenv("CI_PIPELINE_NUMBER", "0")
    elif case == "missing-commit":
        monkeypatch.delenv("CI_COMMIT_SHA")
    elif case == "malformed-commit":
        monkeypatch.setenv("CI_COMMIT_SHA", "HEAD")
    elif case == "mismatched-commit":
        monkeypatch.setenv("CI_COMMIT_SHA", "0" * 40)
    monkeypatch.setattr(os, "getuid", lambda: 1000 if case in ("wrong-identity", "wrong-real-identity") else 0)
    monkeypatch.setattr(os, "geteuid", lambda: 1000 if case in ("wrong-identity", "wrong-effective-identity") else 0)
    if case == "missing-context":
        assert "CI" not in os.environ
    elif case == "legacy-context":
        assert os.environ["CI"] == "true"
    else:
        assert os.environ["CI"] == "woodpecker"
    if case == "missing-pipeline":
        assert "CI_PIPELINE_NUMBER" not in os.environ
    elif case == "invalid-pipeline":
        assert not os.environ["CI_PIPELINE_NUMBER"].isdigit()
    elif case == "zero-pipeline":
        assert os.environ["CI_PIPELINE_NUMBER"] == "0"
    else:
        assert int(os.environ["CI_PIPELINE_NUMBER"]) > 0
    if case == "missing-commit":
        assert "CI_COMMIT_SHA" not in os.environ
    elif case in ("malformed-commit", "mismatched-commit"):
        assert os.environ["CI_COMMIT_SHA"] != head
    else:
        assert os.environ["CI_COMMIT_SHA"] == head
    if case == "missing-image":
        assert "  ci-shape:" not in (root / ".woodpecker.yml").read_text()
    elif case == "mismatched-image":
        assert ci_image != PIN and ci_image in (root / ".woodpecker.yml").read_text()
    if case.startswith("wrong-"):
        assert os.getuid() != 0 or os.geteuid() != 0
    else:
        assert os.getuid() == os.geteuid() == 0
    calls = []
    def producer(subject, tier, receipt, *, inside_image=None):
        calls.append((subject, tier, inside_image))
        record = {"state": "GOOD", "reason": "controlled producer; not actual root proof"}
        receipt.write_text(json.dumps(record))
        return record
    monkeypatch.setattr(module, "run", producer)
    receipt = temporary / "receipt.json"
    monkeypatch.setattr(sys, "argv", [str(gate), "ci", "--receipt", str(receipt)])
    try:
        code = module.main()
    except SystemExit as exc:
        code = exc.code
    return code, calls, receipt, root


@requires_git
@pytest.mark.parametrize("case", ["good", "missing-context", "missing-image", "mismatched-image", "wrong-identity",
                                  "wrong-real-identity", "wrong-effective-identity", *CONTEXT_CASES])
def test_ci_entry_checks_context_image_and_identity(tmp_path, monkeypatch, capsys, case):
    code, calls, receipt, root = exercise(ROOT / "scripts/ci-shape-check.py", tmp_path, case, monkeypatch)
    output = capsys.readouterr()
    if case == "good":
        assert code == 0 and calls == [(root, "image", PIN)], output
        assert "CI_SHAPE: GOOD:" in output.out
    else:
        assert code == 2 and calls == [], output
        assert "CI_SHAPE: UNKNOWN:" in output.out
        assert receipt.exists() and json.loads(receipt.read_text())["state"] == "UNKNOWN"
