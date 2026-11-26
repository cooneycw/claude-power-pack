# #1897 topic installation and undo protocol

Local preparation was authorized by mailbox 40632, followed by the durability
exception in mailbox 40651. The [owner ruling](https://github.com/cooneycw/claude-power-pack/issues/1897#issuecomment-7179886781)
and orchestrator mailbox 40665 now approve the plan and unpark fixture work,
including branch pushes and PR CI. The orchestrator still requires clearance
before opening a PR. One owner install/undo is authorized only after fixture
success and presentation of the exact committed commands to the owner.

Use the delivered code at `337f411a6bb2cf104040fd5407a1987842ea89bb` for initial
fixture replay. A later execution must record its exact source revision and
clean state. Keep the frozen Part-1 design unchanged; #1896's runtime amendments
and observed fixture evidence are separate historical facts.

## Local fixture recipe

Create a fresh mode-0700 scratch root, an existing empty agent, a fixture home,
history, XDG config/data/cache and working/evidence directories. Supply a fresh
environment containing selected Make/Python/Git executable directories, locale,
those fixture paths, disabled user-site and bytecode, and isolated Git settings.
Do not inherit provider credentials. Use a separate clean detached source
worktree so this local document cannot invalidate source binding.

These are the existing production interfaces; substitute only validated fixture
paths and the pinned full revision in the argument value:

```sh
make --no-print-directory -s -C <clean-source> pi-skills
make --no-print-directory -s -C <clean-source> pi-skills-install \
  PI_SKILL_ARGS='--root <clean-source> --revision <full-sha> --home <fixture-home> --agent-dir <fixture-agent> --json'
make --no-print-directory -s -C <clean-source> pi-skills-verify \
  PI_SKILL_ARGS='--root <clean-source> --revision <full-sha> --home <fixture-home> --agent-dir <fixture-agent> --json'
```

The first command writes the source's ignored `pi/skills` build, disjoint from
fixture agent/history paths. Derive expected slugs, members, hashes and modes
from that actual build. Check source status remains clean. Preserve real CLI
JSON, command argv, exit/lifecycle and installed hashes/modes outside the agent.
Counts are nonzero and must match the actual fresh population; 18/36 is the
current observation, not a zero-validation fallback or a universal constant.

Seed a synthetic personal skill as a foreign-neighbor control. Initial CPP
topic slots, management state and primary lock must be absent in this replay.
Before each install, save scoped CPP pre-state/backup and an exact inverse
recipe. Fixture repair backups and negative mutations remain within this one
disposable fixture. They are never copied to the owner installation.

| Fixture observation | Required distinction |
|---|---|
| Full install and verify | Actual expected/examined package/member counts and exact fresh bytes/modes |
| One bundled-reference byte changed | Assert exactly one changed byte; actual verify must fail; fresh-build repair returns positive |
| Expected package/member missing | Assert prior presence and continued nonzero expected count; verify fails; repair returns positive |
| Expected source marker removed | Assert marker presence before and absence after; verify fails; repair returns positive |
| Changed owned file before undo | Undo refuses before deleting any scoped artifact; intervening edit survives |
| Exact fixture undo | Only logged still-matching created topics/management/new locks removed; personal neighbor retained |
| Presence/absence reader | Post-install manifest is a nonempty positive control before comparing post-undo absence with baseline |

Use actual installer adoption only for explicitly logged fixture repair, never
for owner collisions. An absent owned package uses ordinary `--install`; passing
`--adopt` for that absent path correctly refuses because it is outside the
reviewed edited-conflict set. Changed bytes or a stripped marker use explicit
fixture-only adoption. Keep raw negative and repaired verifier outputs. Missing
pi means real discovery/reload is unexecuted; CLI/fidelity or existing reader
self-tests cannot substitute for it. The current local replay introduces no
new aggregate acceptance grader: inspect the actual existing reader outputs.

After fixture undo, installed parity should report missing expected packages,
not current. The cleanup comparison is against the scoped pre-state. Preserve
synthetic personal file bytes/modes and its identity/mtime, and report which
directory metadata is outside that comparison. Dispose only of the registered
scratch root after retaining the evidence; never use a broad cleanup glob.

## Owner batch - exact commands must be shown first

The host operator supplies the exact source/tool revision, approved existing
session/context, scoped pre-state and exclusive topic-writer window. No new pi
process uses owner HOME. Only install, verification and reload/discovery in the
existing authorized session are permitted; no prompt, skill invocation or
provider turn. Capture only the relevant skill UI, not pane history.

The first batch supports absent canonical CPP topic slots and management state,
with unrelated personal skills allowed. An existing slot/collision/ownership
record returns a concrete preservation/restore amendment before any install.
No automatic owner adoption. Under mailbox 40665's first-batch absent-state
requirement, an existing primary lock also stops the batch before installation.
Never enumerate the whole agent or inspect credential paths. Published records
exclude credential-file names/contents, tokens and private host/session names.

Before each owner install, log the actual fixed target list and exact inverse
procedure. It must account for topic directories, ownership ledger, work/journal,
primary coordination lock and both derived locks, plus whether the skills root
already existed. A new lock is removed only within the operator-exclusive writer
window; advisory locking alone does not make unlinking a lock race-safe.
Freeze a post-install manifest and require still-matching CPP-created content
before removing anything. A changed or unexpected file stops undo for review;
do not erase it or claim clean cleanup. An incomplete install without a usable
post-state is a recovery review, never permission for broad deletion.

Record baseline relevant discovery, full real install/verify, reload presence,
then logged undo and reload again. The post-install presence is the positive
control before the post-undo absence comparison. Compare scoped file hashes,
modes and expected artifacts to baseline; do not infer an unchanged whole agent
or restoration of all parent timestamps. Owner sign-off is a distinct final row.

## Six boundaries, attribution and remaining work

Carry #1896's accepted rerun-2 copier/verifier observations by reference and
bounded summary: forbidden probes; Markdown-only payloads; trusted-write and
transient-write separation; every history source/alias; path/collision protection;
and full membership/reference parity. Its actual source was `38041ce1`; the later
root-CI fix changed the fixture harness only. Do not repeat historical sensitive
path spellings in this issue's evidence or copy raw traces into the repository.

The built-in-tool inventory and skill-loader diagnostic measurements remain
UNKNOWN under #1896. Equal RPC stderr covers only runtime/extension/provider/flag
diagnostics. Neither discovery nor undo proves bearer isolation, provider behavior,
contextual effectiveness or a container boundary. Keep observed, planned,
unexecuted and owner-signed rows distinct. No automatic Section-5 unpark follows.
