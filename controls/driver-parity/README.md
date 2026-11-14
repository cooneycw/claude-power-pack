# Driver parity control

These are owned text fixtures, not live delegated runs. `base-tree` copies the
four command documents from main `65921ba3`, appending fixture-only approval,
compliance, reconcile, read-issue and begin-run calls to each driver to make a
covered baseline. The table retains the owner-approved equivalents and gaps.
The main-gap case removes those appended calls again, exposing fifteen missing
pairs. The other cases change one coverage or policy condition at a time.

The fixture mirror is a source-text stand-in. It tests inventory comparison;
it does not attest generation or helper bundling. `tests/test_driver_parity.py`
separately builds and reads the real flow-auto Codex mirror. The stub generator
and driver declaration files state only the packaging population for fixtures.

Fourteen BAD, nine UNKNOWN and seven GOOD cases run through the real checker. The constructed
anchor checks a fixed helper list, omits all plan-record verbs and trusts waiver
metadata. It misses all BAD/UNKNOWN cases and agrees on the GOOD cases. UNKNOWN cases
explicitly declare the blind anchor clean with a reason. Its provenance is
constructed, never historical. UNKNOWN is a separate fail-closed verdict; a
crash is never a detection.

Issue #1811 tracks the still-owed work. Approval and compliance are never waived;
the real repository assertion validates #1809's required calls on this stack.
The eventual landing closes #1810 while #1811 remains open.

The fixture policy is frozen together with its fixture source documents; it is
not a second current policy and is not synchronized with the live table when
upstream driver lines move. Its citations bind to this owned snapshot. The
GOOD control cases validate that internal relationship, while the repository
parity test independently validates the live policy against live sources.

Review counterexamples also pin if/env command positions, alias reassignment,
a split mirror with an unrelated entry point, and installed-only path rewrites.
Bundling is checked per helper/verb membership: an invoked bundled primary
address must remain and resolve. Documented plugin/checkout fallback resolution
may coexist with that primary address; its phase or runtime choice is not proved.

Further cases cover executed echo/printf substitutions and conditional alias
changes. Literal same-helper fallback paths preserve identity; a different
nonempty job cannot be credited as the original helper. Dynamic alternatives
remain UNKNOWN. Empty absence is not credited as a different successful job.

Closed lexical rules distinguish helper-bearing substitutions (UNKNOWN) from
non-helper substitutions in arguments, comments from code, quoted output with
redirections from unquoted helper tokens, and literal parameter path segments
from dynamic executable paths. These have owned contrasting cases. Standard
file/location probes and empty clears are NON_EXECUTING; unsupported positions
and alias changes are UNKNOWN, never silently accepted. The grammar does not
claim general Bash interpretation. Helper-bearing heredoc data is UNKNOWN.
