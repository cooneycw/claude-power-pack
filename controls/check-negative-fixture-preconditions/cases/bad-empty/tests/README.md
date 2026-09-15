KNOWN-BAD: a tests/ directory that exists and holds no test files.

Deliberately NOT a `.gitkeep`: git cannot track an empty directory, and the
condition under test is "the directory is real and the scan population is zero".
This file is not named `test_*.py` or `conftest.py`, so the gate's own
`test_files()` does not count it - which is the whole point.

Scanning nothing and reporting "ok" is a false clean bill of health (#840). The
anchor `eae94b5` predates that fix and exits 0 here.
