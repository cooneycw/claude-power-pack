# Lanes demonstrated - issue #1737

RETROACTIVE RECORD, written 2026-11-12 after the change merged as #1751
(merge commit 3e52bf6d). The pull request merged without this file; its rows
are taken from that pull request's "Lanes for this change" table.

| Lane | What was demonstrated |
|---|---|
| Project state | A project with a `.claude/security.yml` path suppression for an extensionless file and one without: a planted assignment in `Makefile` is reported with no configuration and not reported with the suppression (`tests/test_security_scanners.py::TestExtensionlessFilesAreRead::test_a_path_suppression_clears_an_extensionless_file`). |
| Reader: lib/cicd coverage logic, which reads secrets-scanned= from the gate line | The real cli over a real tree, before and after adding extensionless files: the gate line keeps its shape and only `secrets-scanned=` rises (`test_the_gate_line_keeps_its_shape_and_only_the_count_rises`). |
