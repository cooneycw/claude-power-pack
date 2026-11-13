# Runner target PATH: design for owner ruling (#1801)

Status: design and locally committed red cases only. No product code changed.
Base: full clone at main `35c51d81424999849f496f325a51ecc7b7ea9367`.
CPP venv: Python 3.11.14. Owned target venv: system Python 3.12.3, no packages.

## Measured reproduction

`tests/test_runner_target_path.py` extracts the exact `CPP_RUN` array from
this clone's `scripts/flow-finish-gate.sh`, then invokes its real
`python -m lib.cicd run --plan path_probe` entrypoint. The target manifest
contains one owned `sh probe.sh` step. Actual `lib/cicd/runner.py` builds its
environment and actual `ShellStep` executes it. No full gate, live CI, network
probe or fake uv is used. An owned startup observer records the running CPP
interpreter before dispatch. Only named environment fields are recorded.

Let C be this clone and T the owned target:

| Field | Caller | Runner startup | Target step |
| --- | --- | --- | --- |
| PATH | T/.target-venv/bin:/usr/local/bin:/usr/bin:/bin | C/.venv/bin plus caller PATH | Same polluted PATH |
| bare python3 | T/.target-venv/bin/python3, 3.12.3 | C/.venv/bin/python3, 3.11.14 | C/.venv/bin/python3, 3.11.14 |
| VIRTUAL_ENV | unset | C/.venv | unset |
| UV_PROJECT_ENVIRONMENT | unset or T/.target-venv | unset | Correctly restored to caller's value/presence |

Both unset and explicit target UV-environment populations reproduce the leak.
The selected regression battery on untouched product code reports **2 failed,
2 passed**: both target-interpreter assertions fail; both independent checks of
the runner's own interpreter/prefix staying in CPP pass. Existing environment
handoff/consumer-runner tests: 21 passed. Lint and binary guards pass.

## Environment map

| Boundary / source | Current PATH behavior |
| --- | --- |
| Shell CPP_RUN, flow-finish-gate.sh:538 | uv prepends CPP bin only in its child; shell parent's PATH is unchanged |
| Entry restore_target_environment, __main__.py:23 | Restores UV_PROJECT_ENVIRONMENT before CLI import; ignores PATH |
| _build_step_env, runner.py:304 | Copies PATH; strips PYTHONPATH/VIRTUAL_ENV/PYTHONHOME; sets target UV_PYTHON/cache policy |
| _execute context, runner.py:810 | One sanitized env for all steps; both fresh/resumed execution use it |
| ShellStep._resolve_env, steps.py:361 | Copies context env if needed and merges explicit per-step overrides; no PATH repair |
| ShellStep.should_skip / execute, steps.py:493/513 | Same resolved env for skip probe and command, so both leak |
| Normal step retries and failed-pytest rerun, runner.py:1373 | Reuse/copy context env; rerun adds PYTEST_ADDOPTS; leak persists |
| DockerComposeStrategy deploy/rollback/status, deploy/docker_compose.py | Passes context env to argv/shell commands; same leak |
| Make query / subsumption, steps.py:998/1539 | Copies os.environ plus step overrides and strips make's own variables; retains polluted PATH independently of _build_step_env |
| State Git probes, state.py:207, and other inherited CLI child commands | Inherit process PATH; state sets GIT_INDEX_FILE only |
| Standalone ShellStep / direct DeterministicRunner API | Uses whatever environment the caller supplied; no reconstructible pre-uv PATH |
| Makefile fallback, flow-finish-gate.sh:1373 | Does not invoke CPP_RUN; make inherits original shell PATH. Its uv fallback intentionally activates target project, not CPP |
| Enrolment-only, flow-finish-gate.sh:635/732 | Receipt helper runs with shell caller python3; CPP_RUN is not executed; no CPP uv prepend |
| check-summary, flow-finish-gate.sh:603 | Uses CPP_RUN for analyzer, so CLI child queries inherit polluted PATH; no target step execution |

Direct `python -m lib.cicd`, direct API calls and older wrappers lack a trustworthy
pre-uv PATH. An already active CPP venv explicitly on the caller's PATH is a
caller choice, not an injected entry to remove silently.

## One proposed design

Restore the full captured caller PATH at the existing entrypoint handoff boundary,
before CLI imports, rather than only in _build_step_env. This also covers make
queries and inherited subprocesses, which otherwise disagree with target steps.
The running CPP interpreter stays selected: modifying os.environ PATH cannot
replace the already running sys.executable. Keep all existing UV-environment,
Python-floor/pin, stripping and explicit step-env policies.

1. At each shipped gate/verify launcher capture PATH value and presence before
   uv, overwriting any inherited `CPP_RUNNER_TARGET_PATH` and `_PRESENT` metadata.
   The launch sites are: shell CPP_RUN (1); flow/auto verify (2); flow/deploy
   run/verify (4); codex/auto direct runner (1); cicd/verify (3): **11 sites in
   five source files**, plus generated skill mirrors after approval.
2. Extend the entrypoint's existing strict metadata decoding. Require a complete
   well-formed pair. Candidate PATH must exactly equal the current PATH with
   only the single leading running-CPP interpreter bin entry removed, or equal
   current PATH (no-op). A candidate cannot insert, reorder or revive a directory
   not present in the observed current sequence. Consume metadata before CLI
   import and never print its values. Measured uv 0.9.7 always prepends exactly
   one CPP bin entry, including when caller PATH already starts/ends with it.
   Preserve duplicates, empty components, spaces and any intentionally supplied
   CPP entry. Unexpected uv transformation or forged/incomplete metadata fails
   before target commands, rather than manufacturing a trusted search path.
3. With no PATH pair, preserve current PATH for backward-compatible direct or
   older launchers. Do not guess which entry belonged to the original caller.
   Such callers retain their current limitation until their launcher is updated.
   Missing PATH itself is not normalized to a new system search path.
4. Preserve CPP-owned helper dependency isolation explicitly. Add reserved
   `CPP_RUNNER_PYTHON` to the step environment, always assigned from actual
   sys.executable, overwriting any caller value. CPP-owned default helper commands
   use the quoted variable; ordinary target commands keep caller PATH. This is
   **10 command bindings**: five built-in plan entries (the mypy-scope helper in
   finish/check, two security modules and bootstrap); two generated manifest
   security steps; and three CPP-owned manifest Python helper steps. No automatic
   fallback to CPP for a target's missing ruff/pytest/mypy/python is permitted.
   Also pin all six security import skip probes to that same runtime: two
   built-in, two generated and two CPP manifest expressions. Thus the proposal
   covers ten command bindings plus six skip expressions, not ten total uses.
   Explicit manifest env overrides remain explicit consumer policy, not a new
   privilege boundary. The reserved value is not taken from handoff metadata.

This is one design: full caller restoration with explicit CPP helper identity.
Removing only every C/.venv/bin match is rejected: it loses intentional caller
entries, and preserving only one match does not restore original policy reliably
without metadata. It still couples behavior to guessed uv layout. The proposal
uses runtime bin identity solely to validate a captured handoff, not to invent
an original PATH.

## Consumer-visible inventory and migration

The installed CPP venv has **16 executable names** (activation helpers excluded):
three Python aliases (`python`, `python3`, `python3.11`) and **13 console tools**:
`bandit`, `bandit-baseline`, `bandit-config-generator`, `dmypy`, `markdown-it`,
`mypy`, `mypyc`, `py.test`, `pygmentize`, `pytest`, `ruff`, `stubgen`, `stubtest`.
All 13 console tools are absent from the owned target's original PATH. Two of
the Python aliases resolve to its own interpreter; python3.11 is absent. Thus
**14 names cease to be accidentally available** in that fixture, and two Python
names resolve to the intended target. External consumer counts are not inferred.

CPP's own manifest has nine steps; three call bare Python helpers (finish/deploy
security and bootstrap). Its Makefile lint/test/typecheck explicitly use
`uv run --extra dev` for ruff/pytest/mypy; **zero** of these three calls relies on
bare console tool discovery. Built-in quality fallbacks also invoke uv.

Generated owned samples each contain eight steps:

- UV sample: five explicit uv commands, two bare-python3 security commands, one
  make verify. No bare ruff/pytest/mypy executable.
- Pip sample: five bare `python -m ...` target commands, two bare-python3 security
  commands, one make verify. The five module commands must resolve target Python;
  missing target dependencies become real failures rather than borrow CPP's.

The dependency cliff is measured, not hypothetical: an owned `{}` security YAML
loads under CPP Python (exit 0; PyYAML available) and raises ConfigUnreadable under
the dependency-free target Python (exit 1; PyYAML absent). The explicit CPP helper
identity above preserves security behavior instead of silently dropping its config
or importing CPP packages through a target interpreter. Target-owned bare commands
that relied on leaked tools must install their own dependencies or invoke their
own uv environment. Existing generated security commands need regeneration to use
the reserved runtime interpreter, or an explicit migration; no silent rewriting.

Skip conditions, normal commands, retries, deploy/rollback subprocesses and make
queries all see the same restored base PATH. Explicit step PATH still overrides
it. The fallback and enrolment-only lanes gain no CPP prepend and keep their
current behavior. UV_PROJECT_ENVIRONMENT restoration remains unchanged. The
runner stays 3.11; no target interpreter version is selected merely by this fix.
Kyle's issue reports 17/27 controls using bare python3, one failure and 16 silent
wrong-interpreter passes; those are the issue's measurements, not fresh consumer
repo probes. Coordination tickets belong to orchestrator/master.

## Committed control plan and acceptance

The local red cases are committed now under tests/fixtures/runner_target_path
and tests/test_runner_target_path.py. Upon approval register
`controls/cicd-target-path` on the handoff instrument, anchored to this actual
pre-fix entrypoint. Owned bad input: polluted CPP-first PATH plus valid caller
handoff whose target python3 must win; current source misses it. Repair: retain
caller PATH exactly, while independent outer-runtime observation stays CPP.
Add committed forged-directory, orphan/presence, duplicate/space/empty-component,
caller-intentionally-CPP, and unmarked-legacy populations. A constant pass/fail
must fail the control. Also test skip_if, make queries, retries and explicit PATH
overrides with real resolved child output, plus explicit CPP security YAML loading.
No full suite, gate, PR, consumer ticket or product change is authorized yet.

## Owner rulings requested

1. Approve full caller PATH restoration at entry before imports, strict no-added-
   directory validation, and unchanged/no-guess legacy behavior when metadata is
   absent, across all 11 gate/verify launch sites?
2. Approve the new reserved runtime-interpreter variable and ten explicit CPP
   helper bindings, with regeneration/migration required for older generated
   security commands, and no implicit fallback for target-owned tools?
3. Confirm coordinated consumer rollout and required dependency migration in
   kyle, skillc and kyle-candidate before CPP ships this interface change. Which
   consumers must demonstrate acceptance before merge? Orchestrator/master files
   those coordination issues; this worker has filed none.


## Additional security acceptance cases (orchestrator 24312)

Still test-only, with production files unchanged. The extended local battery
has **6 failed, 6 passed**. Two red cases are original target-Python resolution;
four are CPP-owned security steps under restored target PATH: finish/deploy
without PyYAML and finish/deploy with an explicitly refusing target import probe.
The passing controls are two CPP runner-interpreter populations, two hand-written
security outcomes, and two positive built-in scans with target PyYAML installed.

Important measured distinction: bare `import lib.security` succeeds without
PyYAML, because config.py imports yaml lazily. Both current built-in skip probes
therefore return false for skip; their commands RUN and exit 2 with
`SECURITY_GATE: flow_finish UNKNOWN` / `flow_deploy UNKNOWN`, explaining that
configuration was not applied. The no-PyYAML input alone does not establish a
silent skip. A separate owned target-python shim refuses exactly that import
probe and delegates all other invocations to the actual target Python; its
refusal is asserted before running the step. Both current steps then skip,
which makes forgetting to pin skip_if distinguishable from fixing the command.

The consumer's hand-written `PYTHONPATH=<cpp> python3 -m lib.security gate
flow_finish` runs with the actual target venv under the proposed restored-PATH
environment supplied directly to ShellStep (no product implementation). With an
owned empty security YAML and no PyYAML: exit 2 UNKNOWN, not skip, and no scan
verdict. With the real PyYAML 6.0.3 Python implementation copied from CPP's
installed dependency into the isolated target's site-packages (no native extension
for the different Python, no fake module): exit 0 PASS. Both built-in scan fixture
populations also exit 0 PASS when that target dependency is present, proving the
missing-dependency red has no unrelated finding. The source fixture contains
only harmless owned files and a complete ignore policy. No live scan is run.

The binding count is now explicit: **10 command expressions plus 6 skip_if
expressions = 16 interpreter-bearing expressions**, in addition to 11 launcher
handoffs. Target hand-written commands remain target-owned and require their own
PyYAML when using a security config; they are not automatically reclassified as
CPP-owned. Coordination text must state that measured migration requirement.
