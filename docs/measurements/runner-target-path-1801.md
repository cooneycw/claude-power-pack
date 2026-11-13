# Caller PATH implementation evidence (#1801)

Owner approved the [design](runner-target-path-1801-design.md), Q1-Q3, on
2026-11-13. This changes executable discovery for consumer gate steps. A forged
PATH record must never add a directory to the inherited search policy.

## Before and after

Full base clone: `35c51d81424999849f496f325a51ecc7b7ea9367`. Python 3.11.14
runner venv; owned target Python 3.12.3 venv. Tests extract the real CPP_RUN
array from this checkout's scripts/flow-finish-gate.sh, invoke actual
python -m lib.cicd and its DeterministicRunner, and run one owned custom step.
They do not execute a full finish gate or a live CI service.

On unchanged product source, the extended battery had 6 failures and 6 passes:
two original-PATH failures and four security helper/guard failures; independent
runner-interpreter, hand-written helper and installed-PyYAML controls pass.
The final native matrix was rerun with all six affected product files restored
to actual base bytes: **13 failed, 8 passed**. After restoring implementation,
all native cases pass, and the broader 28-file run reports **1,231 passed**.
The implementation makes these cases pass without replacing the runner's own
Python. Target PATH is restored exactly; VIRTUAL_ENV remains stripped and the
existing target UV_PROJECT_ENVIRONMENT restoration remains unchanged.

No PyYAML: import lib.security itself succeeds (lazy config dependency), then
current bare target security execution returns UNKNOWN/exit 2 for unreadable
YAML. An independently asserted target import-refusal population forces the
skip probe branch. Both finish/deploy scans now run on CPP's Python in both
populations, while a command-only mutant still skips and fails acceptance.
Hand-written PYTHONPATH=<cpp> python3 -m lib.security stays target-owned: exit 2
UNKNOWN without target PyYAML and exit 0 PASS with real PyYAML 6.0.3 Python
source installed into the isolated target (no fake module or foreign native
extension). No consumer checkout or external service is scanned.

## Changed interfaces

Eleven launcher sites in five sources capture a value/presence pair before uv.
The entrypoint refuses incomplete, malformed, absent-value-inconsistent,
missing-current-policy and changed-topology records before CLI import. A valid
record is an exact no-op or removal of the one leading actual-runner bin entry.
Original duplicates, spaces, empty components and intentionally supplied CPP
entries survive; values are never shell-evaluated or included in diagnostics.
Without records, PATH stays unchanged, including absence. Metadata is consumed.

The reserved CPP_RUNNER_PYTHON is always the actual sys.executable, overwriting
both host and explicit step values. Ten CPP-owned command bindings plus six
security skip expressions use it: five built-in commands (including mypy helper
in finish/check), two generated security commands, three CPP-manifest commands;
two import probes in each of those three sources. Ordinary target commands and
explicit step PATH overrides remain target policy. No missing-tool fallback.
Older generated security commands need migration; 13 accidental console tools
in CPP's venv are no longer borrowed. See the design's exact names and counts.

The baseline flow-command fixture keeps its historical needles: two obsolete
launcher obligations are explicitly retired with an owner-approved reason and
replaced by two new PATH-aware obligations. Verify-shape tests retain explicit
older no-record shapes for archived rationale/legacy callers, while accepting
the exact new shapes. Mutation controls still reject missing interpreter flags.
Generated Codex mirrors were rebuilt and their changed launcher text read.

## Committed control

controls/cicd-target-path executes the actual stdlib decoder without CLI dispatch,
with nine BAD populations and two GOOD populations: one polluted-PATH lookup
plus eight independent refusal populations. The byte-compared actual
pre-PATH entrypoint at 35c51d81 misses every BAD input and agrees on the GOOD
unmarked/no-op population. It grades refusal and PATH; metadata consumption and
actual uv runtime are separate native tests.

Five independent guards: pair completeness (two cases), presence enum, absent
value consistency, current PATH availability, and topology (added/reordered/
extra-removed directories). For every BAD input, a test removes only its named
If guard by AST and proves exit 1 blocked becomes exit 0 ready. No exception or
second guard is allowed to conceal the removed check. A later-effect sentinel
is untouched on refusal. An owned executable lookup demonstrates actual PATH
restoration and flips when only the PATH assignment is removed. A CLI test proves a forged record never imports the
command dispatcher and never echoes its private fixture value.

## Lanes for this change

| Lane | Decision and evidence |
| --- | --- |
| Checkout | Owned target repo and full CPP checkout; actual wrapper uses configured CPP path, no fixed home checkout. Existing worktree/runtime tests retained. |
| Harness | Canonical command docs and generated Codex launchers updated; actual generated text read. Existing handoff tests exercise six CLI commands. |
| Driver | Flow finish/deploy, Codex fallback and verify launch sites updated; caller metadata always overwritten by wrapper. No live delegated workflow claim. |
| Coordination | Kyle acceptance against the reviewed branch is required before merge; master arranges it. No live acceptance claimed yet. Skillc needs no acceptance change per ruling. |
| CI provider | No provider YAML changed. Owned shell/runner fixtures only before PR CI. |
| Project state | Target UV policy unset/set, target PyYAML absent/present, target import refusal, old no-record callers, missing PATH, spaces/duplicates/empty components and explicit CPP PATH. |

| Reader | Real output or behavior tested |
| --- | --- |
| Target step and interpreter lookup | Actual command -v, Python version, sys.executable and PATH in owned shell step through real uv/CLI runner. |
| CPP-owned commands and skip probes | Real built-in finish/deploy security ShellSteps with target import refusal and missing YAML dependency; command-only mutant fails acceptance. |
| Shell wrapper / entrypoint | Actual array extraction; inherited forged metadata overwritten; malformed metadata refuses before CLI import. |
| Make queries / retries / deploy strategies | Actual make query and make verify recipe record the same restored PATH; real subsumption credits lint to verify. Existing retry/deploy tests retained; no live deployment claimed. |
| Generated task manifests / CPP manifest | Explicit runtime commands and guards emitted; manifest and shell-boundary contract tests compare actual values. |
| Strict negative-control reader | Real checker runs all nine bad/two good populations and actual historical anchor with provenance. |
| Kyle consumer | Required container red-on-main/green-on-reviewed-branch run is pending; [kyle#2424](https://github.com/cooneycw/kyle/issues/2424). |
| Skillc consumer | Coordination recorded in [skillc#715](https://github.com/cooneycw/skillc/issues/715); no acceptance change required by owner. |

Lint, typecheck, binary guards, negative-fixture checks, command-document budgets,
behavioral obligations and relative links were checked before the checkpoint.
Four pure decoder-mapping tests and one pre-dispatch test are explicitly exempt
from the PATH-absence classifier: those inputs are mappings, not a process PATH
used to simulate missing tools. Actual subprocess fixtures assert lookup policy.

Full pre-gate list, independent model receipt and full gate follow orchestrator
checkpoint review. They have not been claimed by these focused results.
