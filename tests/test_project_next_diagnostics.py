"""Provider failures keep incomplete-inventory diagnostics, including blank streams."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from lib.project_next import collect

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("caller", ["collector", "native"])
@pytest.mark.parametrize(
    "stderr,stdout,expected",
    [
        (" \n", "\t\n", "command failed"),
        ("", "", "command failed"),
        (" \n", " authentication required \n", "authentication required"),
        (" error connecting to api.github.com \n", "ignored output", "error connecting to api.github.com"),
    ],
)
def test_failed_provider_uses_first_nonempty_stripped_diagnostic(
    monkeypatch, tmp_path, caller, stderr, stdout, expected
):
    completed = subprocess.CompletedProcess(["owned-provider"], 1, stdout=stdout, stderr=stderr)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)
    if caller == "collector":
        with pytest.raises(collect.CollectionError) as caught:
            collect.subprocess_runner(["gh", "issue", "list", "--json", "blockedBy"], tmp_path)
        diagnostic = str(caught.value)
    else:
        spec = importlib.util.spec_from_file_location("cpp_owned_diagnostics", ROOT / "scripts/project-next.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        rows, diagnostic = module._native_rows_live(tmp_path, 10)
        assert rows is None
    assert expected in diagnostic
    assert "Upgrade gh" not in diagnostic
    assert "2.94.0" not in diagnostic
