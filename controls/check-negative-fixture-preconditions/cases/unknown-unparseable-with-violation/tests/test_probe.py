"""KNOWN-UNEXAMINABLE (union half 1): a real unwaived violation, beside a file
that does not parse.

This is the #1180 union. On its own this file is a plain known-bad: a wholesale
PATH replacement with no precondition. Paired with `test_broken.py` the gate
must NOT score it as a detection, because the run's population is incomplete -
so the case expects UNKNOWN, not BAD.

Before the fix the gate printed BOTH markers over this tree and the harness
scored it UNRESOLVED.
"""
import subprocess


def test_tool_is_absent(tmp_path):
    stub = tmp_path / "bin"
    stub.mkdir()
    subprocess.run(["some-tool"], env={"PATH": str(stub)}, capture_output=True)
