# `check-cpp-init-cicd-args` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `check-cpp-init-cicd-args` (#1596)

`make cpp-init-cicd-args-check`, `make verify` and CI parse literal
`python -m lib.cicd` calls in `cpp:init` and statically referenced CPP helper
sources against `lib.cicd.cli.create_parser().parse_args`. No command handler is
executed and no flag list is copied. The current init population floor is 5.
Bash words use shlex with quote-aware operator boundaries; shell values are
represented by stable values (choice values come from the parser). The check
validates argument syntax, not actual values, runtime readiness or side effects.
Literal CPP checkout/installed-helper paths and helper sibling directories from
an explicit `BASH_SOURCE`/`dirname` binding are followed without execution.
Expanding heredocs that mix module hints with command substitutions fail as
unexamined; quoted or escaped heredoc text remains data.
Sources reached without literal module launches are counted separately;
unresolvable helper invocation paths fail, while file-test operands remain
metadata. Unknown launcher/build shapes and early parser exits fail with a named
source location instead of disappearing. Literal Python argv builders are checked;
unrecognized builders with an explicit module hint fail closed. Computed module
names are outside this static population. The verdict names invocation and
source-file counts rather than claiming arbitrary shell/Python analysis.

`controls/cpp-init-cicd-args` commits an invented flag independent of the real
`--generate-makefile` feature, helper and shell-boundary cases, empty/floor
refusals, and valid counterparts. A repaired bad-flag case must become clean;
a constructed always-green anchor must be BLIND on every bad case.
