# ADR 0014: First-class Antigravity capability via a unified host-global update procedure

- Status: Accepted (owner, 2026-11-25; see PR #1895 comment 7167908207)
- Date: 2026-11-21
- Issue: #1876
- Related: ADR 0001 section 5 (single-source command layout; its
  plugin-marketplace packaging decision was retired by ADR 0005), ADR 0005
  (retire plugin-marketplace distribution; checkout and executed-copy split),
  ADR 0008 (instrument negative-control bound), ADR 0013 (generated mirrors are
  build output, not a tracked tree), #555/#556 (Codex skill generator), #720
  (topic skill provenance & `skills-check.py`), #823/#1029 (`install-drift.sh`),
  #1441 (`codex-global-agents.py`), #1669 (command word budgets),
  #1710/#1747 (counter-model runtime evidence)
- Consulted: Antigravity CLI built-in `agy-customizations` spec (observed
  2026-11-21: `SKILL.md`, `docs/plugins.md`, `docs/skills.md`, `docs/rules.md`,
  `docs/mcp_servers.md`, `docs/json_configs.md`); PR #1875 Codex and `cp-orch`
  round-1 reviews

## Provenance and adoption boundary

This proposal was originally drafted by AGY/Gemini in
[PR #1875](https://github.com/cooneycw/claude-power-pack/pull/1875), at
`226c0e1a177fd16cb1e0d4bbe5bec9aa7bfc1d99`. A native Codex session adopted and
independently inspected that text on 2026-11-22 against CPP main
`40d25173c8c09987fac851cffa565efdc0f11c72`, preparing this replacement for
fresh receipt-bound review. This provenance does not establish a supported
runtime receipt for the original Gemini work. Historical observations below
remain attributed reports; adoption does not turn them into fresh probes or
receipt-backed implementation evidence. The owner accepted the ADR on
2026-11-25.

## The decision, in plain language

Owner direction on 2026-11-22 selects **Option B: a separate copy-generator
and managed loose copies**, with **topic skills first** and **no symlinks**.
Option A (native plugins) is rejected for the initial delivery. These selected
choices did not by themselves accept the ADR; owner acceptance was separate
from a review approval.

CPP owns one shared `/cpp:update` procedure: discover existing CPP-managed
installations, refresh from one CPP revision, verify actual installed output,
and report per-harness outcomes with fault isolation. A current source
checkout must still refresh stale installations. The invoking CLI does not
choose which installed harnesses refresh.

The first delivery covers **Claude Code, Codex and AGY only, explicitly
PARTIAL**. The final all-harness contract also includes **pi (the pi coding
agent), Qwen and Gemma/OpenCode**. Those are named follow-up adapter and
acceptance deliveries under #1876/#1889, not delivered by the first subset.
Reports must name included and unimplemented harnesses; partial coverage must
never be reported as all-harness parity.

Topic skill availability does not establish workflow parity. The named
**command-derived skills and real AGY `cpp-update` invocation follow-up**
under #1876/#1888/#1889 must deliver command adaptation and actual invocation
before that claim. Full receipt-backed flow parity also requires the AGY
runtime evidence adapter in **#1886**.

## Amendment (2026-11-26): existing Claude command and helper links

The [owner ruling "1889 A"](https://github.com/cooneycw/claude-power-pack/issues/1889#issuecomment-7178523792)
creates one exception to this ADR's symlink rejection: Claude Code's existing
CPP command-family and flow-helper links stay links under the shared updater.
This includes the existing command links under `~/.claude/commands/` and helper
links under `~/.claude/scripts/`. It permits no new link kinds or harnesses.
Claude topic skills, Codex skills, AGY topics and every new harness remain
managed copies; their roots and package members retain the no-symlink policy.

The exception uses a typed, bounded, verified Claude-only link backend in the
shared driver. Each link must name its expected CPP source and resolve inside
the approved CPP checkout bound to the run's full source revision. A matching
suffix or a link-shaped name alone does not establish ownership or confinement.
Do not inspect or mutate arbitrary neighbors, follow an aliased install root,
or read target contents before proving the target is within that checkout.

Read-only verification checks each installed entry's actual type, link target
and confined resolution, then compares the expected source membership, bytes
and executable modes against the pinned revision. Check the persistent target
checkout's revision and cleanliness; links into a disposable build snapshot
that will be removed do not satisfy this contract. Resolving a link is a
topology check, not proof of current source contents. Refresh never moves,
cleans or modifies the target checkout, switches its branch, discards edits or
pulls inside the adapter. A revision mismatch or dirty target checkout reports
the links non-current or refused with the reason, never current. Only the link
entries themselves may be created or repointed. Unreadable or unprovable state
remains unknown; verify creates or repairs nothing.

Before the backend ships, commit controls for a link pointing outside the
checkout, a dangling link, and an expected link replaced by a regular file.
Each must be refused or reported non-current, with unexpected user content
preserved. Include a confined, intact link as the positive control. These are
requirements for #1889-B2, not implementation or executed acceptance evidence
in this amendment.

The updater report identifies this backend as **`links`**, never `copies`.
Report Claude topic copies separately when summarizing mixed components. The
existing shared revision, ownership, bounded lock, preservation and independent
per-harness failure contracts still apply. The write scope is exactly the
CPP-owned link entries under `~/.claude/commands/` and `~/.claude/scripts/`,
identified by both expected name and expected CPP source, using the existing
[per-entry ownership discipline](../../scripts/cpp-host-write.sh). Other entries,
including hand-added real files and foreign links, are never removed or
replaced. The mixed-farm hazard, where one hand-added real file changes layout
classification, is not authority to convert or replace the farm. The exception
does not weaken the managed-copy core's symlink refusal.

Delivery order is this docs-only amendment first, #1889-B1 copy adapters, then
#1889-B2 maintained update wiring and Claude links. The amendment lands before
that implementation; it does not complete #1889 or the epic acceptance. Initial
harness coverage remains explicitly PARTIAL.

## Selected Option B pipeline and ownership contract

Canonical `.claude/skills/<slug>/` packages plus their external
`docs/skills/*.md` guides feed a separate Antigravity builder. Its self-contained
output is ignored build output under `antigravity/skills/` (ADR 0013).
Referenced guides are bundled into each skill's `references/`, and links are
rewritten relative to the package. The installer copies that output into
`~/.gemini/config/skills/<slug>/`; installed skills must work in unrelated
repositories with the source unavailable. No symlinks, live-checkout references
or dependence on Codex being installed are permitted.

**Separate thin Antigravity script first; `scripts/codex-skill-sync.py` stays
   untouched.** Wave 1 starts with a separate thin Antigravity generator/bundler
   script (`scripts/antigravity-skill-sync.py`) and leaves
   `scripts/codex-skill-sync.py` untouched so downstream consumers
   (`cooneycw/kyle`'s `core/container_capabilities.py`, `cooneycw/skillc`, and
   `cooneycw/kyle-candidate`) face zero interface risk. Any later unification
   of the Codex and Antigravity generators MUST either:
   - keep the `codex` profile's output byte-identical (same file set, bytes, and
     modes) and keep `scripts/codex-skill-sync.py` callable at its current path
     and CLI, backed by a committed pre- vs. post-refactor tree-comparison
     parity test shown red on a deliberately changed transform; OR
   - be declared a versioned interface change with coordination issues filed in
     `cooneycw/kyle`, `cooneycw/skillc`, and `cooneycw/kyle-candidate` before
     merging.

Topic copies carry CPP ownership/provenance metadata, including
`metadata.source` pointing to `claude-power-pack/.claude/skills/<slug>`.
The later command-derived follow-up carries `GENERATED` markers. Ownership
markers do not grant permission to delete unexpected user content: define
expected package names and owned members explicitly, preserve foreign skills
and unexpected content, and refuse collisions or require an explicit reviewed
adoption rather than silently overwriting/pruning them. Prune only proven owned
orphans. A zero-validated install never establishes a clean result.

An advisory CPP write lock at `~/.gemini/config/.cpp-skill-install.lock`
serializes cooperating CPP mutations, including shared configuration writes.
It does not protect against direct AGY commands or other writers that ignore
it. Test actual adapter concurrency and both expected updates, not just valid
JSON or process exit. Native plugin lifecycle guarantees are not assumed.

After copying, compare actual installed membership, bytes/hashes and modes to
a fresh expected build. Native list/validate output and successful CLI exit
cannot replace that comparison. Include stale, missing-member, tampered,
foreign-content, collision and unreadable-target controls with committed
negative cases under ADR 0008.

## Attributed B0-B4 observations and remaining uncertainty

The following are AGY test-session/helper reports from 2026-11-22, relayed in
[#1887](https://github.com/cooneycw/claude-power-pack/issues/1887).
The Codex adopter has read the reports, not independently inspected the raw
probe artifacts or repeated the experiments. These observations inform the
selected design; they are not delivered CPP acceptance tests or an AGY receipt.
The preserved private archive contains 199 files and has SHA256
`56e8a3b3a932dc061450a5b6f620e4d582ddf245b10cc422e8bbf295bbb2dd9c`.
Archive preservation is not additional validation. Future sanitized fixtures
must retain mapping/digests to originals without publishing private paths,
credentials or unrelated session contents.

| Batch and report | Reported positive/comparison evidence | Design consequence and limit |
|---|---|---|
| [B0 isolation](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079256159) | A fresh process with a disposable home isolated marker and MCP configuration writes; helper re-checked regular configuration unchanged. Absent markers and enabling an absent plugin failed. | No supported profile/config-dir flag was available. Isolation covers configuration, not the whole filesystem; never repurpose HOME in a running session or transplant credentials. Configuration writes alone do not prove MCP tool execution. |
| [B1 skills/lifecycle](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079330832) | Loose skills loaded; fresh-session removal returned NOT_FOUND. Native v1-to-v2 reinstall removed a dropped skill, matched hashes/modes, worked with source moved aside and preserved sibling loose skills. Installed files were copies; reinstall repaired tampering. | Native concurrent disable lost an update in 1/10 trials; same-plugin installs were last-writer-wins. Native list/validate missed byte tampering. Reinstall removed foreign internal plugin files. These support CPP locking, installed-output comparison and explicit ownership boundaries, not native safety assumptions. |
| [B2 rules](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079368856) | Global GEMINI.md, global AGENTS.md and plugin rules/AGENTS.md loaded markers in fresh sessions across two unrelated repositories; removal removed markers. A 23,800-byte fixture loaded completely. | A 26,000-byte fixture silently dropped its tail, exit 0 and empty stderr; diagnostic logs revealed truncation. Native strict validation failed but install accepted it. The exact byte boundary was not established; the documented 20,000-token aggregate budget is unmeasured. |
| [B3 MCP](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079419121) | Reported real stdio handshake and Streamable HTTP operation; foreign global entry survived plugin lifecycle. Dead-server comparisons yielded TOOL_UNAVAILABLE. A working legacy SSE server failed with AGY while a compatible-client control succeeded before/after. | Use stdio or Streamable HTTP, not legacy SSE. Broken MCP in -p mode still exited 0. Actual health needs tool/server nonce artifacts; the relay did not include the nonce/call artifact, so this adoption makes no independent live-call acceptance claim. |
| [B4 runtime metadata](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079661668) | Native hooks.json lifecycle hooks exposed session ID, resolved modelName and turn provenance without transcript reads; spoofed user model labels did not override identity. Missing/unreadable identity remained unknown. | JSON/stream-json stdout alone lacks model identity. Hooks are a candidate source for #1886, not a delivered adapter, valid receipt or proof of complete implementing-model retention. |

The original #1875 report of `agy 1.5.14` plugin-list survival after source
deletion remains historical metadata evidence only. B0-B4 reports have their
own retained version/command artifacts; do not silently assign the older
version to them. The inspected `agy-customizations` specification describes
24,000 bytes per rules file and 20,000 aggregate tokens; B2 demonstrates a
truncation risk without measuring every threshold or aggregate-budget behavior.
Unsupported versions or incomplete inputs must remain unknown.

Canonical topic packages currently omit `metadata.source`; the original
report counted 18 packages and at least 11 external guide references, with
raw copies yielding 0 validated managed packages. This motivates metadata,
self-contained bundling and the expected-membership floor. The current planner
does not yet accept `antigravity`; all capabilities described here are planned.

## Rules and MCP under managed copies

Global rules mirror `~/.claude/CLAUDE.md` plus optional host-local additions
(following #1441) into a measured global GEMINI.md or AGENTS.md target.
Explicitly select/document the exact target and avoid duplicate loading.
Refuse unmanaged or hand-edited destinations without explicit `--adopt`.
Do not overwrite personal rules implicitly.

Enforce a per-file size **below the documented 24,000-byte ceiling at both
build and installation**, checking the actual bytes about to be installed.
Warning-only handling is insufficient after B2. Preserve semantics and local
additions: no silent truncation or summarization. If the full rules do not
fit, stop and obtain a separately measured design for splitting/loading order
and treatment of the still-unmeasured 20,000-token aggregate budget. Keep a
committed oversized fixture with a tail marker and a within-limit positive
fixture; prove oversize rejection and complete positive loading.

MCP uses key-scoped merges into `~/.gemini/config/mcp_config.json`, preserving
foreign registrations and refusing ambiguous ownership collisions. Use stdio
or Streamable HTTP `/mcp` (or an explicit stdio bridge); reject legacy `/sse`.
Native plugin MCP scoping was observed but is not the selected installation
mechanism. Managed-copy update/removal must independently demonstrate foreign
registration preservation.

Keep static config/byte drift separate from live health. Live health requires
an actual tool call with an independently observed server-response nonce and
retained call/server artifacts. A dead-server case must fail that claim even
if AGY returns exit 0; unperformed/unreadable health is unknown. Because
`/cpp:init` and `/cpp:status` consume `mcp-drift.py` without re-deriving its
verdict, it is inside ADR 0008's committed-negative-control bound. Retain the
working-compatible-client SSE control as well as stale-config and dead-server
cases. Validate operands using measured syntax: the B0 `plugin uninstall
--help` hazard is already recorded in the Nit Store; help-looking arguments
and exit 0 are insufficient evidence of read-only behavior or success.

## Epic acceptance criterion and fidelity boundaries

> `/cpp:update` discovers the host's existing CPP-managed installations,
> refreshes each from the same CPP revision, verifies installed output, and
> reports an outcome for each harness. The invoking CLI does not determine
> which installations get updated. Initial Claude/Codex/AGY coverage is PARTIAL;
> pi, Qwen and Gemma/OpenCode are named follow-up deliveries before claiming
> the final all-harness contract.

Start with a current checkout, stale managed Codex and AGY topic skills, and a
user-authored neighboring skill. One update must refresh both managed copies
from the same revision and retain the user's bytes. Repeat with a genuinely
unwritable destination, proving that precondition for the executing identity:
the other destination still refreshes and the summary identifies the failure.
Test unexpected internal content/collisions as well as neighboring skills.
Actual AGY invocation of `cpp-update` belongs to the command-derived follow-up;
do not count topic-only availability as that acceptance result.

| Surface | Selected Option B target | Required evidence / controls |
|---|---|---|
| Shared updater | One driver; initial Claude/Codex/AGY PARTIAL | Current checkout + stale installs, user preservation, unwritable-destination isolation; pi/Qwen/GemmaOpenCode follow-up acceptance |
| Topic skills | Managed copies in `~/.gemini/config/skills/` with CPP provenance | Fresh installed membership/bytes/hashes/modes, source-unavailable and unrelated-repo invocation, `controls/antigravity-skill-install-fidelity` |
| CPP writes | Advisory CPP lock, not native serialization | Controlled concurrent adapter updates; direct non-cooperating AGY writers explicitly outside lock guarantee |
| Global rules | Selected measured global file, explicit adopt protection | `controls/antigravity-global-rules`, build/install oversize rejection, full positive tail-marker loading, hand-edit/unmanaged protection |
| MCP | Key-scoped global configuration merge | Foreign-entry preservation, stale `/sse` and dead-server controls, actual nonce-backed health separate from static drift |
| Capability receipt | `scripts/cpp-install-receipt.py` | Planner/select/write/status round trip and existing capability/receipt controls |
| Review receipt | #1886 lifecycle-hook adapter | Complete model history, independent reviewer, exact-artifact binding and writer/validator/enrolment good/bad/unexaminable round trip |

All check helpers follow `scripts/codex-global-agents.py`'s vocabulary:
`current`, `stale`, `hand-edited`, `unmanaged`, `absent`, `not-applicable`
(exit 5), `unknown` (exit 4). No selected installation and no applicable AGY
surface is not-applicable; unreadable or incomplete applicable input is unknown.

## Alternatives and reversal trigger

Native plugins (Option A) are rejected for the initial delivery. B1 reported
useful staging/lifecycle behavior, but native serialization and integrity
checks did not satisfy CPP's contract and foreign internal content was removed.
Owner-selected managed copies provide an explicit CPP ownership boundary and
copy-generator path. Reconsider native packaging only through a later owner
ruling with proven locking, fidelity, adoption/preservation and rules/MCP
semantics; it is not an automatic fallback or currently open choice.

Symlinks, `skills.json` references into a checkout, a separate hand-maintained
Antigravity skill tree, and another bespoke per-CLI updater section remain
rejected (ADR 0001 section 5, ADR 0005 and ADR 0013). The shared driver reduces
existing per-CLI duplication while leaving Codex output untouched. Managed
copies require CPP to own bundling, pruning, locking, global-rule protection
and key-scoped MCP merges; native list/validate cannot stand in for that work.

## Rollout, owner acceptance and delivery boundaries

One AGY PR is in flight at a time, with full suites in PR CI only and Kyle
series-27 taking CI, host-resource and merge priority. No pushes or CI reruns
without the orchestrator's explicit window clearance. Kyle's CPP pin remains
**v13.0.0**; this document does not authorize a pin change. The owner accepted
this ADR on 2026-11-25, and it must merge before code merges. The ADR/plan lands
before activating child-issue scaffolding. The nine existing children remain
**open and parked pending that merge**; this docs-only revision closes none and
starts no implementation. Codex authors CPP work; AGY is the test bed.

Packaging B, topic-first and the partial first harness set are settled owner
choices. Owner acceptance of the ADR was separate from those choices, probe
completion and review approval. Exact global-rule target/loading choices
and follow-up delivery scheduling must be explicit in their implementation
plans. The five LOW findings from the first review remain recorded in Nit
Store comments linked from PR #1895; this revision is driven by the new owner
direction, not a separate nit-cleanup change.

## Three-wave plan: nine existing open delivery issues

### Wave 1: contract, topic builder and partial shared updater

1. **1.1 - #1887: measured packaging and updater contract.** Incorporate B0-B4
   evidence and sanitized fixture provenance; specify selected B, ownership,
   lock limits, exact invocation/report behavior and the PARTIAL first harness
   set. Preserve remaining unmeasured premises. The owner accepts the ADR;
   probe completion does not close this issue or activate scaffolding.
2. **1.2 - #1888: separate topic-only Antigravity builder.** Bundle canonical
   topics and external guides into ignored `antigravity/skills/` output with
   relative `references/`, CPP metadata and proposed Makefile build/check
   targets. Leave `scripts/codex-skill-sync.py` untouched. Verify real unrelated
   repository invocation with source unavailable and a missing-skill comparison.
   Depends on 1.1. The named command-derived/real-AGY-`cpp-update` follow-up
   under #1876/#1888/#1889 is outside topic-first delivery and must be tracked
   before workflow parity is claimed.
3. **1.3 - #1889: shared updater and managed-copy AGY adapter.** Implement the
   common driver and initial Claude/Codex/AGY coverage, always labelled PARTIAL.
   Copy/verify fresh output, serialize cooperating CPP writes, preserve foreign
   content and prune only owned orphans. Include `HOST-SURFACE` declarations,
   fidelity controls and the epic acceptance test. Depends on 1.2. Named
   follow-up deliveries are **pi adapter/acceptance**, **Qwen adapter/acceptance**
   and **Gemma/OpenCode adapter/acceptance** under #1876/#1889; none is implied
   complete by the first subset. Command-derived invocation remains a separate
   named follow-up as above.

### Wave 2: rules, MCP and runtime evidence

4. **2.1 - #1890: global rules sync.** Use the measured global file, preserve
   source semantics/local additions, protect unmanaged/hand-edited content with
   explicit adopt, and enforce build/install byte-size gates and tail-marker
   controls. Aggregate token budget remains unmeasured. Add `HOST-SURFACE`
   declarations and `controls/antigravity-global-rules`. Depends on 1.1.
5. **2.2 - #1891: global MCP merge, drift and actual health.** Key-scoped merges
   preserve foreign entries; use stdio/Streamable HTTP, reject legacy SSE, and
   separate static drift from nonce-backed health. Retain committed SSE,
   dead-server, foreign-entry and unknown-input controls. Expose CPP services
   such as second-opinion via `/mcp` and Playwright via stdio. Depends on 1.1.
6. **2.3 - #1886: AGY runtime evidence adapter.** Build on native lifecycle-hook
   metadata, not typed labels, stdout guesses or unrelated transcripts.
   Retain version/schema provenance, session/turn ordering and complete
   implementing-model sets; an unambiguous independent reviewer and exact
   artifact binding are required. Prove writer -> validator -> enrolment with
   good, spoofed-label, self-review, missing/unreadable and incomplete-history
   fixtures. Unsupported/unreadable histories fail unknown. Hook availability
   alone does not establish receipt-backed full flow parity. Depends on 1.1.

### Wave 3: drift, capability selection and maintained documentation

7. **3.1 - #1892: install drift.** Compare actual installed Option B copies to a
   fresh self-contained build, including bundled references, membership,
   bytes/hashes/modes and ownership limits. Enforce explicit package-name floor;
   zero validated never means clean. Use `tests/test_install_drift.py` and
   fidelity controls; command-derived output is covered only when delivered.
   Depends on 1.3.
8. **3.2 - #1893: capability planner and `/cpp:{init,update,status}`.** Add
   `antigravity` through `CAPABILITY_ORDER`, `CAPABILITY_DEPENDENCIES`,
   `TIER_CAPABILITIES`, `TIER_STEPS`, `CAPABILITY_REQUIRED`, `REFERENCES`,
   `STEP_REFS` and `OPTIONAL_STEPS` in `scripts/cpp-install-receipt.py`, with
   `controls/cpp-capability-selection` and `controls/cpp-install-receipt`.
   Delegate update to the common driver. Prove select/write/status round trip;
   do not mistake this wiring for delivered AGY command-derived invocation.
   Respect #1669 caps (init/update/status: 19,467 / 14,666 / 3,817 words): pay
   added words with offsets and old-vs-new instruction audit, or obtain an
   explicit owner cap ruling. Depends on 1.3, 2.1, 2.2 and 3.1.
9. **3.3 - #1894: maintained documentation.** Update
   `docs/HOST_MANAGED_ARTIFACTS.md`, `docs/agents/counter-model-evidence.md`,
   `README.md` and an AGY setup reference. State topic-only/partial harness
   boundaries and named follow-ups truthfully. Focused docs checks locally;
   full `make verify` and remaining gates in PR CI under Kyle priority.
   Depends on 2.3 and 3.2. None of these nine issues closes merely because this
   ADR/plan merges.
