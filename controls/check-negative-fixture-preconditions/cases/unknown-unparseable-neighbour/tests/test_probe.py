"""KNOWN-UNEXAMINABLE (the unearned green): a fully COMPLIANT fixture, beside a
file that does not parse.

Nothing in this file is wrong - the precondition is asserted, exactly as
`good-asserted`. The case expects UNKNOWN rather than GOOD because of its
NEIGHBOUR: with one file unparsed the gate cannot issue a clean bill for the
tree, and `files_scanned` would otherwise count a file it never opened.

This is the case that fails on the bare `except SyntaxError: continue` guard,
which prints `ok - ...` here and converts a loud wrong-reason red into a silent
unearned green.
"""
import shutil
import subprocess


def test_tool_is_absent(tmp_path):
    stub = tmp_path / "bin"
    stub.mkdir()
    assert shutil.which("some-tool", path=str(stub)) is None, "fixture must lack some-tool"
    subprocess.run(["some-tool"], env={"PATH": str(stub)}, capture_output=True)
