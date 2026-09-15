"""KNOWN-GOOD: a PREPEND, which adds a stub without removing anything.

The case that stops the #933 widening becoming an over-correction. A derived
value constructs no absence, so there is nothing to assert and flagging it would
be the over-application issue #697 warned against. If a future change makes the
dict-literal detection ignore the derived test, this case - not the bad one -
is what fails.
"""
import os
import subprocess


def test_stub_takes_precedence(tmp_path):
    stub = tmp_path / "bin"
    stub.mkdir()
    subprocess.run(["some-tool"], env={"PATH": f"{stub}:{os.environ['PATH']}"}, capture_output=True)
