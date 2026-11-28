# check-control-cleanup-relay

`make control-cleanup-relay-check` rejects stdout-bearing `print` calls inside
`TemporaryDirectory` blocks in Python control implementations. It examines all
arguments, including concatenation and string prefixes, and recognizes direct
tempfile calls and imported aliases. A nested context reports each print once.

The implementation population is Python files under `controls/`, excluding
each control's direct `cases/`, `anchors/` and `history/` fixture trees. Their
exclusion count is printed; those trees contain deliberate old or malformed
inputs, not implementations. There are no per-site exemptions. An empty
implementation population, unreadable or unparseable source, enumeration error
or implementation symlink is UNKNOWN (exit 2). A known relay is BAD (exit 1);
fully examined implementations without that lexical shape are GOOD (exit 0).
When unreadable source and findings coexist, the findings are diagnostics and
UNKNOWN is the sole verdict marker.

This is a lexical boundary, not proof about arbitrary dynamic aliases,
indirect writes, or runtime exploitability. The #1984 planted cases exercise
actual wrapper behavior separately. The fixed controllers retain their
assertions and buffer subject output until temporary cleanup succeeds.

The guard runs in `make verify` and the existing Woodpecker `negative-controls`
step. `controls/control-cleanup-relay` commits the old #1983 shape,
concatenation, non-first stdout arguments and imported aliases as BAD inputs;
relay after cleanup is GOOD; empty and unparseable populations are UNKNOWN.
Its constructed always-clean anchor misses every BAD input and answers clean
on UNKNOWN inputs without examining them.
