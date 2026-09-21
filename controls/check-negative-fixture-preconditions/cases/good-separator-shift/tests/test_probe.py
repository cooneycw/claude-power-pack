"""KNOWN-GOOD: a correctly waived site sitting after raw separator characters.

The waiver below is on the line directly above its site, which is where the
gate's own remediation text tells authors to put it. This case must report
clean.

THE SHIFT IS THREE, AND THAT IS LOAD-BEARING (issue #1110). `_function_sites`
honours a waiver on the site line OR the line above, so a +/-1 window absorbs a
ONE-character shift and a single-separator fixture passes on the unfixed gate -
proving nothing. Three clears the window, which is also what the live incident
that exposed this did. If you edit this file, keep the separator count above one
or this case silently stops being a regression case.
"""
import subprocess

SEPARATORS = ["  "]


def test_waived(tmp_path):
    stub = tmp_path / "bin"
    stub.mkdir()
    # negative-fixture: allow PATH is isolation, not an absence
    subprocess.run(["a"], env={"PATH": str(stub)}, capture_output=True)
