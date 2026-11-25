# A2 host fixture protocol

Preparation for #1896 after A1 merged in #1907. The original command draft is
now implemented using the real core merged in #1908 and approved in Run 2.
These are observer contracts, not executed host results. The exact relay is
in `issue-1896-a2-host-probe.sh` beside this document. Host execution is routed
through the task orchestrator after the frozen scripts and batch are reviewed.
No owner session or owner installation is involved.

## Execution envelope

The future dispatcher creates a fresh mode-0700 temporary fixture, records its
path, and uses fixture HOME, agent, cwd, XDG config/data/cache and every history
candidate. Children get an environment allowlist, no provider credentials and
offline/no-session RPC. This separates configuration; it is not an OS network
or credential-isolation boundary. Never inspect actual auth files to check the
envelope. Synthetic boundary sentinels are created only inside this fixture.
The candidate source is a clean, revision-bound disposable checkout. Report
candidate/script SHA256, pi/Python/strace versions, argv, allowed environment
names, cwd, exit codes, timeouts and child cleanup. A forced stop invalidates
the affected acceptance result. Output records live outside the source and
outside the target agent tree, under the fixture.

Each command below names the fixture interface. The host operator supplies a
reviewed immutable candidate checkout as `PI_A2_SOURCE`; `PI_A2_REVISION` is its
full reviewed commit and `PI_A2_PYTHON` its compatible interpreter. The actual
pi/strace binaries are explicit reviewed absolute paths. Require all variables
and verify the checkout before creating fixtures. Do not resolve these by
searching other sessions or their configuration.

```bash
: "${PI_A2_SOURCE:?reviewed clean checkout required}"
: "${PI_A2_REVISION:?full reviewed commit required}"
: "${PI_A2_PYTHON:?compatible absolute interpreter required}"
: "${PI_A2_PI_BIN:?reviewed pi executable required}"
: "${PI_A2_STRACE_BIN:?reviewed strace executable required}"

"$PI_A2_PYTHON" "$PI_A2_SOURCE/scripts/pi-host-fixture.py" \
  --self-test

"$PI_A2_PYTHON" "$PI_A2_SOURCE/scripts/pi-syscall-audit.py" \
  --self-test

"$PI_A2_PYTHON" "$PI_A2_SOURCE/scripts/pi-host-fixture.py" \
  --source "$PI_A2_SOURCE" --revision "$PI_A2_REVISION" \
  --pi-bin "$PI_A2_PI_BIN" --lane rpc --json

"$PI_A2_PYTHON" "$PI_A2_SOURCE/scripts/pi-host-fixture.py" \
  --source "$PI_A2_SOURCE" --revision "$PI_A2_REVISION" \
  --strace-bin "$PI_A2_STRACE_BIN" --lane syscalls --json
```

The dispatcher owns fixture creation and teardown in `finally`, stops/reaps all
children first, and records final fixture absence. Failure to clean up is an
explicit failed cleanup result with the exact fixture path retained for manual
undo. No broad cleanup glob, detached process or guessed process-group kill.
Commands return UNKNOWN when a required binary or evidence is unavailable.
Use the exact committed relay batch and check the frozen scripts' help before
requesting host execution. Self-tests exercise readers, not live host behavior.

## RPC lane: actual installed output and baseline diagnostics

1. Start with an empty fixture agent skills population. Invoke pi with
   `--mode rpc --offline --no-session`, sending only bounded discovery/tool
   inventory requests supported by the pinned version. Request ids are unique.
   No model prompt, skill invocation, provider login or session resume.
2. Capture raw stdout/stderr and exact exit/lifecycle results as the no-CPP-skills
   baseline. The preparatory pi 1.6.0 probe used `get_commands`; reconfirm the
   available/active built-in-tool inventory RPC from versioned docs/source
   before choosing those requests. Unsupported inventory is UNKNOWN, never an
   assumed tool-preservation pass.
3. Install the actual full canonical population with the delivered CLI/core,
   not a synthetic equivalent. Verify under the real shared-lock path. Start
   a fresh identical pi child; require every expected `skill:<slug>` once,
   expected source attribution and version-supported baseDir semantics. Global
   sourceInfo.baseDir was the agent root in the earlier probe, not package root.
   Compare built-in tool inventory to baseline, including a fixture skill named
   `bash`; it must remain a skill and must not replace the tool.
4. Preserve baseline stderr verbatim and require no added diagnostics. Any
   version-specific volatile-field normalization must be explicit, bounded and
   justified before execution. Do not silently filter warnings or treat exit 0
   as diagnostic equality. A malformed skill must add a detected diagnostic;
   if the pinned loader does not warn for the chosen seed, select a documented
   diagnostic-producing malformed seed before acceptance. Same-name collision
   was silent in the earlier probe and is not a valid warning control.
5. Remove an expected installed package in the disposable fixture and require
   the reader to reject the missing command; restore through the real installer
   and observe presence again. Missing response, duplicate id, empty-success,
   missing expected slug and malformed response are committed reader negatives.
6. Bounded same-name project shadowing is a separate trusted-project fixture
   with explicit synthetic trust configuration; report the selected source.
   Global installed fidelity cannot become an effectiveness claim. Runtime
   observations concern this fixture/version/context only.

Each baseline/installed pair uses equivalent fresh initialized fixture state;
record any files pi itself initializes without reading their content. Pi startup
is outside the copier zero-auth-probe claim. Report known baseline diagnostics
as diagnostics, even when the differential is empty.

## Syscall lane: copier and verifier only

Trace the delivered Python CLI/core children without invoking pi. Before each
case create its synthetic settings/history/auth/trusted-root sentinels outside
the trace. Build an explicit operation allowance from the reviewed contract,
never infer permission from the accesses observed. A draft raw trace envelope is:

```bash
"$PI_A2_STRACE_BIN" -ff -ttt -yy -s 65535 -o "$PI_A2_TRACE_PREFIX" \
  -e trace=%file,%desc,%process \
  "$PI_A2_PYTHON" "$PI_A2_SOURCE/scripts/pi-skill-sync.py" \
  --install --root "$PI_A2_SOURCE" \
  --home "$PI_A2_FIXTURE_HOME" --agent-dir "$PI_A2_FIXTURE_AGENT" --json
```

This inner command is launched by the fixture dispatcher with all fixture
variables validated; it is not a standalone operator copy/paste batch. Final
strace capabilities/flags must be help-verified on the execution host. Include
all children, metadata/read/write/path operations, directory enumeration,
descriptor-relative operations, mmap writes and cwd/fd changes. The classifier
tracks pid ancestry, cwd, directory fds and annotated descriptor targets; covers
failed as well as successful forbidden probes; handles unfinished/resumed lines
or declares UNKNOWN. Truncated strings, unresolved paths, unsupported relevant
syscalls or incomplete child traces are UNKNOWN. Restricting to `%file` alone
would miss descriptor writes and is insufficient.

Allowed scopes: immutable source reads and required interpreter/library reads;
bounded exact settings reads; canonical skills and management subtree for
install; exact advisory lock; fixture evidence output owned by the dispatcher.
Verify uses an existing shared lock, creates nothing and changes no ledger.
Settings/tools/extensions/history/auth never become writable because they are
inside the fixture. No auth-file open/stat/access/readlink is allowed. History
root/ancestor no-follow lstat/readlink is allowed solely for exclusions;
descendant metadata, opens or enumeration are forbidden. Fail before forbidden
root touches on rejected output aliases; root-resolution allowance is closed
and distinct from descendant access.

Required actual trace pairs, in addition to committed classifier fixtures:

| Case | Required observed distinction |
|---|---|
| Legal isolated build / actual install and verify | Nonzero expected population, exact package bytes/modes and only allowed operations |
| `pi_auth_open_attempt` | Seeded synthetic auth stat is caught; valid copier/verifier makes no auth probe |
| `session_overwrites_trusted_config` | Seeded create-then-unlink under fixture trusted extensions is caught despite identical final snapshot |
| `output_root_under_trusted_config` | Direct, nested, inverse containment and symlink aliases refused before forbidden-root operations |
| `output_root_under_sessions` / `writable_session_dir_isolated_from_skill_root` | CLI/env/global/project/default and overridden candidates, external history/skills, nested and alias forms refused; legal isolated root accepted |
| History allowance | Root/ancestor no-follow resolution accepted; seeded descendant stat/list/open rejected |
| `topic_skill_auth_helper_rejected` / `skill_path_escape` | Auth-link/helper, traversal, symlink, executable and manifest seeds refused without forbidden probe |
| `foreign_package_collision` | Foreign collision refused, neighbor unchanged; explicit adoption preserves reported in-scope backup |
| `missing_expected_skill_or_marker` / `modified_bundled_reference` | Actual installed baseline passes; removed slug/marker and one-byte reference edit fail |

Keep the deliberately bad trace-generating child separate from the delivered
subject and label it as an observer control. It operates only on explicit
fixture sentinels. Trace its actual auth stat and transient write; static trace
text alone does not establish live observer coverage. Demonstrate the classifier
also rejects a malformed/unresolvable trace and accepts a known legal trace.
The load-bearing observer controls and blind anchors must be committed before
their verdict is consumed by another session.

## Handoff and limits

Return a per-case manifest with expected/observed counts, raw-record digests,
complete paired diagnostics, command results, classifier coverage/UNKNOWNs and
cleanup result. Keep raw traces private if they contain host-specific paths;
publish only reviewed sanitized measurement summaries with digest/provenance.
No public private-session names. The author verifies returned record digests
and readers independently; attribution must distinguish host execution from
local analysis. UNKNOWN/unexecuted rows stay visible until actual evidence
arrives. This protocol proves no runtime bearer isolation, live-provider
behavior, owner-session validation or container boundary.

## Real-core allowance amendment

The plan now binds to merged core #1908 at main
`adf70c291cf3aa457e56a21cec17983dc761da13`; coding approval is still pending.
The proposed pi layout supplies these exact coordination files:

- Primary: `<agent>/.cpp-skills.lock`.
- Ledger sibling: `<agent>/skills/.cpp-managed/.ownership.json.cpp-lock`.
- Work sibling: `<agent>/skills/.cpp-managed/.work.cpp-lock`.

The last two are derived by core from `ownership.json` and `work`, not optional
CLI choices. Refresh may create/open them and take exclusive locks. Verify may
open only existing files read-only/shared, with no root/directory/file creation;
an appearing lock causes a retry and unstable evidence becomes UNKNOWN. Trace
allowances must distinguish these operations per mode. No blanket permission
to enumerate the lock parent, management neighbors or agent directory follows.
Use exact policy paths, plus the core's derived sibling formula, in each case's
independent allowance; do not learn allowed files from the trace under test.

Core accepts system symlink ancestors above its approved root; root and
descendants are no-follow. Pi preflight must independently reject user-controlled
aliases above skills, including the primary-lock parent, before core IO. A1's
stricter no-follow preflight remains the proposed policy. Add actual traced
above-root alias-escape refusals; do not classify all ancestor traversal as
trusted because the generic scope supports system aliases.

Record-only refresh may change pending/transaction metadata, ledger and locks
under the above allowances, while leaving installed package files untouched.
Verify never reconciles a stale record. The host fixture must compare actual
package identities/bytes/modes and classify management writes separately, then
reject a seeded package rewrite masquerading as metadata reconciliation. A
valid prior claim and exact fresh-build population are prerequisites. An
unmarked package or a package claimed by another identity is never adopted by
this exception; explicit adoption also cannot override another identity's claim.
These live fixture cases supplement the committed reader controls and remain
UNKNOWN/unexecuted until returned records demonstrate them.
