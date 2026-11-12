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

**A promised path must be tracked (#1716).** When `--root` is the root of a git
checkout, a supplied path that exists but is not tracked is a finding
(`untracked promised path ... does not ship`): `Path.exists()` alone passed a
file present only in one working tree, such as a local `.venv`. A glob is
judged on its tracked matches, so local debris it also matches
(`scripts/__pycache__`) is not a finding, and a glob with no tracked match is.
Where the root is not a git checkout root - the control's scratch cases, an
unpacked archive - the tracked check does not run, and the summary line says
`tracked check NOT RUN ... whether they ship is unverified` in place of `each is
tracked`. Tests: `tests/test_cpp_init_promises.py`.

**Classification is per line (#1716).** `creates project` followed by the path
on the same line is a generated file. The same sentence wrapped before its path
leaves the path alone on a line in the disclosure step, where it reads as a
CPP-supplied source that is missing. This is the supported boundary, not a bug
to widen: joining lines would let a verb on one line excuse a path on the next,
and a wrong join is a silent miss. When a `missing promised path` finding is
printed, a note names the remedy: keep the declaration and its path on one line.
