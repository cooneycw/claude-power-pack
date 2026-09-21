"""KNOWN-BAD: a shifted waiver must not silently exempt an unwaived site.

The waiver here belongs to NOTHING - it sits at module level and exempts no
site as written. Five raw separators move its computed line number onto the
unwaived replacement below, which the unfixed gate then treats as waived and
reports clean.

This is the SILENT direction of issue #1110 and the reason it was filed rather
than nit-stored. The noisy direction announces itself with a red build; this one
produces a green the gate did not earn, and nothing about it looks wrong.
"""
import subprocess

SEPARATORS = ["  "]

# negative-fixture: allow this waiver belongs to no site at all


def test_unwaived(tmp_path):
    stub = tmp_path / "bin"
    stub.mkdir()
    subprocess.run(["b"], env={"PATH": str(stub)}, capture_output=True)
