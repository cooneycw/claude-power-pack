"""KNOWN-GOOD: the same dict-literal replacement, with its precondition asserted."""
import shutil
import subprocess


def test_tool_is_absent(tmp_path):
    stub = tmp_path / "bin"
    stub.mkdir()
    assert shutil.which("some-tool", path=str(stub)) is None, "fixture must lack some-tool"
    subprocess.run(["some-tool"], env={"PATH": str(stub)}, capture_output=True)
