"""CI entry admission on controlled identities; real root acceptance is separate."""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIN = "test/image@sha256:" + "a" * 64
OTHER_PIN = "test/image@sha256:" + "b" * 64


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
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setenv("CI", "true")
    if case == "missing-context":
        monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(os, "getuid", lambda: 1000 if case == "wrong-identity" else 0)
    monkeypatch.setattr(os, "geteuid", lambda: 1000 if case == "wrong-identity" else 0)
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


@pytest.mark.parametrize("case", ["good", "missing-context", "missing-image", "mismatched-image", "wrong-identity"])
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
