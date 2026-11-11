# `check-cpp-init-promises` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `check-cpp-init-promises` (#1587)

Resolves CPP-supplied paths extracted from `cpp:init` disclosures, explicit
install/link statements, checkout source expressions, and installed helper or
command references. It maintains no separate asset inventory. Generated project
files, consumer configuration, external dependencies and retirement references
are classified and listed without checking their producers or contents.
Unknown promise shapes fail by file and line; an unreadable population is
UNKNOWN. The measured floor is 43 distinct source expressions, so an empty or
near-empty extraction fails. Intentional retirement requires a deliberate floor
change. This proves source existence, not installation or readiness.

`make cpp-init-promises-check`, `make verify` and CI run the gate.
`controls/cpp-init-promises` commits missing helper, unfixed `.claude/hooks.json`,
unknown, empty/near-empty, hidden affirmative, placeholder and escape cases,
plus generated-source roles, individual unknown operands and shell-variable forms,
with good fixed/retirement cases. Its constructed always-green anchor makes the
battery fail when the path check is absent; provenance is explicitly unverified.
