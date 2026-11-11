# `scripts-inventory-check` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `scripts-inventory-check`

- scripts-inventory-check - derives the ENTRY POPULATION of this file from `scripts/` and checks it both ways (#1013): `MISSING` is a script with no entry, `UNDECLARED` a section naming no script and not declared above. Only the SET is mechanical - the prose per entry stays hand-written, because the prose is the valuable part. The matching rule is the document's own, the backticked STEM, not the basename: #1013 as filed measured 44-of-67 by grepping for `.sh`/`.py` names that appear in no heading here, and adopting that rule would have demanded every heading be rewritten to carry an extension. Re-measured against the real convention the gap was 17. One script may own several sections (`check-test-binary-guards` owns three), so the rule asks whether at least one entry exists, never that exactly one does. Stdlib-only, git-free and offline, so `make verify` and the slim CI image agree; registered in `controls/scripts-inventory`, because a gate that lets work through cannot be trusted on a clean tree alone
