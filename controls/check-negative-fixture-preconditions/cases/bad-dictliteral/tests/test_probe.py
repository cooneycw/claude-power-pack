"""KNOWN-BAD: a wholesale PATH replacement in a dict literal, with no precondition.

This is the shape the gate was blind to until #933, and the shape six live sites
used - two of them fail-open tests, which is the exact class the gate exists for.
"""
import subprocess


def test_tool_is_absent(tmp_path):
    stub = tmp_path / "bin"
    stub.mkdir()
    # No `shutil.which(...) is None` assertion: the absence is claimed, never proven.
    subprocess.run(["some-tool"], env={"PATH": str(stub)}, capture_output=True)
