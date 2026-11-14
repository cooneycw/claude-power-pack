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
Before the first checkpoint, the 21-case native matrix was rerun with all six
affected product files restored to actual base bytes: **13 failed, 8 passed**.
After review, the expanded 25-case native matrix on those same actual base
files reports **15 failed, 10 passed**; restored implementation passes all 25.
The original broader 28-file run had **1,231 passed**; the reviewed 32-file
focused run has **1,330 passed**.
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

The first checkpoint changed eleven launchers but missed delegated/core and
other query/probe surfaces. Review expanded this to the complete inventory
below: 24 source launchers and 22 generated copies capture policy before uv.
The entrypoint refuses incomplete, malformed, absent-value-inconsistent,
missing-current-policy and changed-topology records before CLI import. A valid
record is an exact no-op or removal of the one leading actual-runner bin entry.
Original duplicates, spaces, empty components and intentionally supplied CPP
entries survive; values are never shell-evaluated or included in diagnostics.
Without records, PATH stays unchanged, including absence. Marked absence is
refused because removing PATH can introduce system default directories. Explicit
empty PATH (presence x, value empty) stays present and empty. Metadata is consumed.

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
with ten BAD populations and two GOOD populations: one polluted-PATH lookup
plus nine independent refusal populations. The byte-compared actual
pre-PATH entrypoint at 35c51d81 misses every BAD input and agrees on the GOOD
unmarked/no-op population. It grades refusal and PATH; metadata consumption and
actual uv runtime are separate native tests.

Six independent guards: pair completeness (two cases), presence enum, absent
value consistency, marked-absence refusal, current PATH availability, and topology (added/reordered/
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
| Strict negative-control reader | Real checker runs all ten bad/two good populations and actual historical anchor with provenance. |
| Kyle consumer | Required container red-on-main/green-on-reviewed-branch run is pending; [kyle#2424](https://github.com/cooneycw/kyle/issues/2424). |
| Skillc consumer | Coordination recorded in [skillc#715](https://github.com/cooneycw/skillc/issues/715); no acceptance change required by owner. |

Lint, typecheck, binary guards, negative-fixture checks, command-document budgets,
behavioral obligations and relative links were checked before the checkpoint.
Four pure decoder-mapping tests and one pre-dispatch test are explicitly exempt
from the PATH-absence classifier: those inputs are mappings, not a process PATH
used to simulate missing tools. Actual subprocess fixtures assert lookup policy.

Full pre-gate list, independent model receipt and full gate follow orchestrator
checkpoint review. They have not been claimed by these focused results.


## Checkpoint review corrections

The launch inventory enforcement test joins shell continuation lines before
scanning every literal -m lib.cicd occurrence
in command documents, templates, scripts, canonical skills and built Codex skills,
plus the authoritative rationale source copied into the generated skill. It
fails unknown subcommands and missing target-boundary metadata, rejects an echo
of metadata as a handoff, and refuses multiple module launches on one line until
they are separately classified. Opaque Python module and lib.cicd subcommand
variables are refused pending explicit classification. Committed bad/repaired
fixtures prove this check
can fail. Against the actual 49d7ff60 source tree, it finds 13 missing source
handoffs; all are now fixed, including three delegated finish paths, check,
health, smoke, the generic skill example and runnable rationale examples.
The delegated core was regenerated through its writer and its drift check passes.
The behavioral-fixture test now permits only the two exact approved retirements,
pins replacement bash-line kind/count and exact inserted metadata, and proves
that reverting either new command to its retired form yields one missing-step
finding. Retiring the old line cannot excuse losing the replacement.

`check` currently uses a static Makefile parser, with no subprocess today. It is
conservatively protected as a target-query boundary. Health executes configured
endpoint/process child probes; smoke executes configured commands. Both receive
handoffs. `flow-host` only reads provider/recorded host capability data and runs
neither target commands nor make queries; no capture is needed there. Host-CI
refresh and doctor use fixed provider probes, not target-configured gate commands.

Strict discrimination alone reports provenance unverified by design. The control
README gives the explicit --verify-provenance command and full-history/named-main/
anchor-blob prerequisites. Verified control runs here use both flags.

Real uv 0.9.7 measurements: an unset PATH produces CPP-bin alone and is refused
before CLI dispatch; explicitly empty PATH produces CPP-bin plus a trailing colon,
which is restored to exactly empty. Its owned shell-builtin step runs with an
empty PATH and cannot find python3, proving CPP's bin was not retained. Without
resolving the launcher locations, the actual bare env/uv array exits 127 before
uv for both populations. Tests freeze only the already-known env/uv executable
locations to reach actual uv without adding any PATH directory. Both failure
stages are explicit; no silent pass with CPP Python first is accepted.

Consumer ordering: update the CPP pin before adopting "$CPP_RUNNER_PYTHON" in a
hand-written step. Before this change that variable is empty and command lookup
fails. No production _resolve_env caller branches on None; each passes its value
to subprocess. Security external adapters find pip-audit, gitleaks and npm through
PATH; none belongs to the removed accidental CPP-venv names, so no external scan
tool is removed by this restoration.

Supplemental existing bootstrap-wrapper cwd defect was separately filed as
[CPP #1803](https://github.com/cooneycw/claude-power-pack/issues/1803); it is not
fixed here. Its direct wrapper retains original PATH and is classified below.


## Counter-model pass 1 corrections

The gpt-6.1-terra review identified continuation/constructed-launch blind spots
and line-number churn in the inventory identity. Four new assertions fail on
unchanged checkpoint a5d9b825: split module tokens, a variable module, a variable
subcommand, and an unrelated introductory paragraph. Joining continuations before
matching and refusing opaque Python module/subcommand expressions makes the bad
launches visible. The repaired split launcher passes. Stable inventory rows omit
physical line numbers while preserving source path, classification and repeated
occurrences. Duplicating a launcher still changes the inventory.
The focused PATH/control/inventory tests pass all 66 cases. No bytes under lib/
or scripts/ changed from the checkpoint; the runtime protocol is unchanged.

## Counter-model pass 2 corrections

Terra identified a forged-absence default-search widening and an earlier-uv
handoff attribution error. Both regression tests fail on unchanged 9bb5a8eb:
the forged record actually runs system sh after an empty PATH excluded it, and
the two-command launcher incorrectly appears captured. Marked absence is now
refused by an independent named guard; accepted records always assign PATH
rather than deleting it. A committed BAD case and single-guard mutant pin that
refusal. Actual subprocess tests distinguish absent from explicit empty policy;
both current-empty and CPP-bin-prefixed empty inputs preserve explicit empty
PATH and continue to exclude default tools. Unmarked absence is unchanged.
The scanner binds metadata to the matched module's own simple-command segment;
bad/repaired two-uv fixtures exercise semicolon, AND, OR and pipeline boundaries.
The final focused PATH/control/inventory run passes 76 cases.

## Counter-model pass 3 follow-up

Terra reviewed product c13099a1, including the absent/empty policy matrix, and
identified one remaining inventory bypass: inner env could unset the captured
metadata before Python starts. This tests/docs-only follow-up requires the
reviewed direct uv run form, known uv options and direct python/python3 -m.
Unknown wrappers or options are refused rather than credited. The outer env
accepts only the exact capture assignments (no duplicates or replacements),
plus the existing initial -u UV_PROJECT_ENVIRONMENT option in verify lanes.
Three committed BAD fixtures cover inner env, outer unsetting of a record,
and replacement of an already captured record. All three assertions fail on
unchanged c13099a1; the direct repaired fixture passes. The complete existing
138-row inventory stays green, and 79 focused tests pass.
Terra has not reviewed this follow-up check; it is submitted to cr-orch for
independent delta review. All product launcher and runtime bytes are unchanged.

## Complete literal launch inventory

This table records all 138 literal occurrences, including module references and
generated copies, rather than presenting references as executed commands. Class i
is the target-execution/query boundary (check is conservatively included despite
its current static parser); class ii does neither. There are 24 captured source
launchers across 15 files and 22 captured generated copies. Three class-i rows
are explicit direct-call exceptions: one inline check instruction plus its mirror,
and the standalone bootstrap wrapper. None activates CPP through uv. The 89
remaining rows are read/generation/fixed-provider operations or module references.
The unit check rejects new unclassified or missing-policy launchers and pins this
table to the real population using source paths, classifications and multiplicity;
physical line numbers remain diagnostics and are excluded from identity. It
classifies known subcommands; it is not a call-
graph analyzer, so semantic changes inside an existing subcommand require review.
It recognizes Python executables and interpreter variables named with PYTHON;
arbitrary executable aliases, eval and indirect shell expansion require review
rather than a claim of static coverage.
The runnable rationale source is included because Codex packages its examples.

<!-- launch-inventory:begin -->
| Source | Subcommand | Class | Policy | Basis |
| --- | --- | --- | --- | --- |
| `.claude/commands/cicd/check.md` | `check` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/cicd/container.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/container.md` | `container` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/container.md` | `container` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/health.md` | `health` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/cicd/infra-discover.md` | `infra-discover` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/infra-init.md` | `infra-init` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/infra-init.md` | `infra-init` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/infra-pipeline.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/infra-pipeline.md` | `infra-pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/init.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/init.md` | `check` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/cicd/init.md` | `check` | i | direct/no prepend | inline direct interpreter retains caller PATH; no uv boundary |
| `.claude/commands/cicd/init.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/init.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/init.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/init.md` | `checks` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/pipeline.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/pipeline.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/pipeline.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/pipeline.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/pipeline.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/pipeline.md` | `checks` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/pipeline.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/smoke.md` | `smoke` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/cicd/verify.md` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `.claude/commands/cicd/verify.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/cicd/verify.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/cicd/verify.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/cicd/woodpecker.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/woodpecker.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cicd/woodpecker.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/codex/auto.md` | `run` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/cpp/init.md` | `host-ci` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/cpp/status.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/flow/auto.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/flow/auto.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/flow/deploy.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/flow/deploy.md` | `run` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/flow/deploy.md` | `health` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/flow/deploy.md` | `smoke` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/flow/deploy.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/flow/deploy.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/flow/doctor.md` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `.claude/commands/flow/doctor.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/flow/doctor.md` | `check` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/flow/doctor.md` | `doctor-ci` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/flow/finish.md` | `flow-host` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/flow/merge.md` | `flow-host` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/gemma/auto.md` | `run` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/commands/project/init.md` | `checks` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/project/init.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/project/init.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/project/init.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/project/init.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/project/init.md` | `checks` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `.claude/commands/qwen/auto.md` | `run` | i | captured | PATH handoff before target execution/query boundary |
| `templates/delegated-driver-core.md` | `run` | i | captured | PATH handoff before target execution/query boundary |
| `scripts/check-control-ci-deps.py` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `scripts/ci-provider-advisory.sh` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `scripts/ci-provider-advisory.sh` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `scripts/ci-provider-advisory.sh` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `scripts/ci-provider-advisory.sh` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `scripts/flow-finish-gate.sh` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `scripts/flow-finish-gate.sh` | `dispatcher` | i | captured | PATH handoff before target execution/query boundary |
| `.claude/skills/cicd-verification/SKILL.md` | `<command>` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/cicd-check/reference.md` | `check` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/cicd-container/SKILL.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-container/SKILL.md` | `container` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-container/SKILL.md` | `container` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-health/reference.md` | `health` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/cicd-infra-discover/SKILL.md` | `infra-discover` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-infra-init/SKILL.md` | `infra-init` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-infra-init/SKILL.md` | `infra-init` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-infra-pipeline/SKILL.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-infra-pipeline/SKILL.md` | `infra-pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-init/reference.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-init/reference.md` | `check` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/cicd-init/reference.md` | `check` | i | direct/no prepend | inline direct interpreter retains caller PATH; no uv boundary |
| `codex/skills/cicd-init/reference.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-init/reference.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-init/reference.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-init/reference.md` | `checks` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-pipeline/reference.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-pipeline/reference.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-pipeline/reference.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-pipeline/reference.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-pipeline/reference.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-pipeline/reference.md` | `checks` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-pipeline/reference.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-smoke/reference.md` | `smoke` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/cicd-verify/reference.md` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `codex/skills/cicd-verify/reference.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/cicd-verify/reference.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/cicd-verify/reference.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/cicd-woodpecker/reference.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-woodpecker/reference.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/cicd-woodpecker/reference.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/flow-auto/docs/reference/flow-auto-rationale.md` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `codex/skills/flow-auto/docs/reference/flow-auto-rationale.md` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `codex/skills/flow-auto/docs/reference/flow-auto-rationale.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-auto/docs/reference/flow-auto-rationale.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-auto/reference.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-auto/reference.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-auto/scripts/flow-finish-gate.sh` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `codex/skills/flow-auto/scripts/flow-finish-gate.sh` | `dispatcher` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-check/lib/cicd/evidence.py` | `evidence` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/flow-check/lib/cicd/evidence.py` | `evidence` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/flow-check/scripts/flow-finish-gate.sh` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `codex/skills/flow-check/scripts/flow-finish-gate.sh` | `dispatcher` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-deploy/reference.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-deploy/reference.md` | `run` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-deploy/reference.md` | `health` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-deploy/reference.md` | `smoke` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-deploy/reference.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-deploy/reference.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-doctor/reference.md` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `codex/skills/flow-doctor/reference.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/flow-doctor/reference.md` | `check` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-doctor/reference.md` | `doctor-ci` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/flow-finish/reference.md` | `flow-host` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/flow-finish/scripts/flow-finish-gate.sh` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `codex/skills/flow-finish/scripts/flow-finish-gate.sh` | `dispatcher` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/flow-merge/reference.md` | `flow-host` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/flow-merge/scripts/flow-finish-gate.sh` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `codex/skills/flow-merge/scripts/flow-finish-gate.sh` | `dispatcher` | i | captured | PATH handoff before target execution/query boundary |
| `codex/skills/project-init/reference.md` | `checks` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/project-init/reference.md` | `detect` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/project-init/reference.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/project-init/reference.md` | `provider` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/project-init/reference.md` | `pipeline` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `codex/skills/project-init/reference.md` | `checks` | ii | not required | record/generation or fixed CPP probes; no target-configured step |
| `docs/reference/flow-auto-rationale.md` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `docs/reference/flow-auto-rationale.md` | `(reference)` | ii | not required | reference to module/import root, no dispatched subcommand |
| `docs/reference/flow-auto-rationale.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
| `docs/reference/flow-auto-rationale.md` | `verify` | i | captured | PATH handoff before target execution/query boundary |
<!-- launch-inventory:end -->
