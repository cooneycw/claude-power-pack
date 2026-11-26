# Flow run record - issue #1888

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=436421200a034ac5ab42a4fe1c242621 -->
## Run 1

- Run-id:            436421200a034ac5ab42a4fe1c242621
- Run-start:         adf70c291cf3aa457e56a21cec17983dc761da13

- Issue:             #1888
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          ch-orch mailbox 40220, approving Section C at 30c4b23a

### Section A - intent

CPP's topic guides currently depend on files in its own checkout. Copying a
skill into Antigravity can therefore leave it reading a missing guide, or a
same-named file in the user's unrelated project. This delivery packages each
topic with the files it needs, checks that the complete package arrived, and
proves a real Antigravity invocation reads the intended bundled guide. Existing
Codex users must receive exactly the output their current generator would make.

### Section B evidence

Issue created 2026-11-22T12:04:40Z. Post-filing commits inspected:
458ee7c1 (#1895 accepted ADR), 9af6d361 (#1898 pi plan), 790174a3
(#1906 contract), 2f5c96be (#1907 pi builder), adf70c29 (#1908 neutral core).
Merged PR search since filing also returned #1885 and #1882; neither implements
the AGY builder. Relevant source history contains #1907/#1908; no AGY builder
exists. Related issues inspected/considered: #1876, #1886, #1887, #1888, #1889,
#1890-#1894, #1896, #1897 and #1900. None supersedes #1888.

The issue's parked/rulings-open prose predates accepted ADR 0014: Option B,
topic-only and no symlinks are settled. Approved order is contract, neutral
core, this builder, then real-adapter integration B. Reframe the remaining work
as a builder adapter over the merged core, without another copier or premature
production discovery. The pi builder is Markdown-only and includes pi-specific
policy; it is precedent rather than an AGY dependency or an authorized shared
generator refactor.

Current scope follows approved-order comment
https://github.com/cooneycw/claude-power-pack/issues/1888#issuecomment-7168491832,
merged contract #1906 and merged core #1908. These supersede the stale parked
and rulings-open issue text; the issue body is not edited.

Host worktrees are the completed #1887/#1889 branches and this fresh main-based
branch. No unpublished AGY implementation was found; other hosts' unpublished
work is unexamined. Historical commit 40d25173 is available here, but fresh CI
must not depend on that object. Neither codex-skill-sync.py nor its link parser
has changed from that baseline in the inspected history. Existing pi parity
vendors a generator/manifest but loads the candidate parser into both versions;
Nit 7172824059 assigns that blind spot to this delivery.

### Section C - proposed plan (pending approval)

1. `lib/antigravity_skills.py` - topic inventory, pinned tracked-source reads, transitive portable bundling/link rewriting, frontmatter/provenance, immutable ExpectedBuild and a build-output Adapter using lib.host_update.
2. `scripts/antigravity-skill-sync.py` - thin deterministic build/check CLI, explicit source/revision/output options, core reports and bounded exits; default ignored antigravity/skills output, no host-global enrollment.
3. `tests/test_antigravity_skill_sync.py` - real canonical and fixture builds, exact expected membership, metadata/modes, resource preservation, link closure, collisions/escapes/unreadable inputs, and real core refresh/verify reader.
4. `tests/test_antigravity_skill_cli.py` - actual CLI from root/external cwd, checkout/worktree and full/shallow source shapes; generated tree ignores and core refusal/preservation behavior.
5. `tests/test_antigravity_codex_parity.py` - same candidate inputs through independently loaded historical/candidate generators and their own parsers; compare complete paths/bytes/modes, historical payload attribution, and committed changed-transform/changed-parser negative cases.
6. `controls/antigravity-skill-build/control.json` - register nonzero fresh-build GOOD, changed output/missing package/broken reference BAD, unreadable source UNKNOWN and declared blind anchor expectations.
7. `controls/antigravity-skill-build/run-case.py` - seed asserted case preconditions, invoke actual CLI/core and inspect actual reports and preserved content.
8. `controls/antigravity-skill-build/cases.json` - committed build/fidelity and parity case inputs, including distinct transform/parser mutations.
9. `controls/antigravity-skill-build/anchors/constructed-always-current.py` - blind verifier for discrimination evidence; never presented as historical code.
10. `controls/antigravity-skill-build/reference/codex-skill-sync-40d25173.py` - byte-exact historical generator with provenance/digest, isolated from candidate transform helpers.
11. `controls/antigravity-skill-build/reference/check-md-relative-links.py` - byte-exact historical parser beside the pinned generator; same-name helper resolution must remain historical.
12. `controls/antigravity-skill-build/codex-baseline.json` - pinned commit, generator/parser hashes and complete historical output membership/hashes/modes; explicit attributed candidate-input delta, never silently re-pin.
13. `Makefile` - focused tests, build/check and control targets; no host installation target in this delivery.
14. `.gitignore` - ignore generated antigravity/skills tree while retaining its source README.
15. `antigravity/skills/README.md` - generated-output/source boundary and build entry points.
16. `docs/scripts.md` - one inventory row for the new thin CLI.
17. `docs/scripts/antigravity-skill-sync.md` - source/output/revision/metadata/exit contract, supported resources, parity provenance and production-integration boundary.
18. `controls/census.md` - register the new load-bearing verifier and parity checks with committed controls and evidence limits.
19. `docs/measurements/antigravity-topic-builder.md` - sanitized real-output consumer acceptance commands/results, artifact digests, unrelated-project decoy/missing-guide comparisons and explicit unexamined runtime claims.
20. `changelog.d/1888.md` - topic-only builder; named command-derived and real cpp-update follow-up under #1876/#1888/#1889, runtime receipt adapter #1886 separate.

Scope: approximately 20 product/test/control/docs paths plus plan, as-read,
lane-results and review receipt records; roughly 1500-2400 new lines excluding
vendored historical payload. Tier 3 shared contract already supplied by #1887;
no spec rewrite or Codex interface change. Concrete implementation choices can
use existing parser/frontmatter helpers without changing canonical topic files.

The adapter returns core ExpectedBuild/ExpectedPackage/ExpectedMember values and
uses core refresh/inspect for disposable generated output. Its ledger/work and
all three locks are under the explicitly selected output scope; it does not
discover ~/.gemini or add a production registry entry. Build reads only regular
tracked source at the requested full commit, retains supported executable
resources, rejects symlinks/escapes, and resolves local reference closure without
reading unrelated repository files. Stable source yields stable bytes/modes;
revision provenance is deterministic. Canonical topic inventory is explicit and
nonzero (currently 18); additions/removals require deliberate inventory review.

Parity: vendor reviewed historical generator AND parser from 40d25173; their
digests and manifest let git-less/shallow CI run the full comparison. Missing or
unreadable baseline is unknown/failure, never skip-to-green. Both transforms see
identical current source/helpers-as-payload/docs/charters, while their parser
implementations remain isolated. Compare historical baseline payload separately
and attribute every changed member to a source change; fail unattributed delta.
Do not re-pin unless contract review explicitly approves reason and new pin.
Changed transform and changed parser must each make parity fail, with asserted
mutation preconditions. AGY metadata is injected only into generated copies.

Live acceptance uses real build output copied through the core into a disposable
AGY test configuration in a fresh process, arranged through ch-orch/master's
test helper. Do not repurpose this session's HOME or transfer credentials.
An unrelated repo contains a same-named decoy guide; source is unavailable to
the consumer. Prove intended bundled guide read with distinct markers, then
remove bundled content and require detection. Native exit/list/validate alone
does not establish fidelity or guide usage. If helper/runtime evidence is
unavailable, report it as pending and do not claim acceptance completed.

Risks: transitive links can escape into arbitrary files, duplicate basenames
can collide, frontmatter rewriting can alter semantics, resource modes can
drift with umask, and a baseline using candidate parser code can go blind.
Core handles preservation/ownership/locks; AGY adapter supplies supported member
policy and preflight. Real host AGY no-follow prefixes, initial enrollment,
shared registry and one-revision cross-adapter acceptance belong to #1889-B.

Challenge: reusing pi's Markdown-only bundler would discard AGY-required scripts
and resources. Prefer AGY policy over the neutral core and keep Codex untouched;
do not force cross-harness unification as part of this change.

### Lanes for this change

| Lane | Answer | Note |
|---|---|---|
| Checkout | will test | main checkout / linked worktree through real source builder and CLI |
| Harness | will test | real AGY topic consumer through helper; Claude/Codex install not changed, Codex generator output parity checked independently |
| Driver | not applicable | no flow or delegated-driver instruction change |
| Coordination | not applicable | product local core locks; validation heavy gate uses renewing Kyle supervisor |
| CI provider | not covered | local checks and eventual Woodpecker PR CI; no provider behavior change |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not; complete managed and absent/foreign/colliding output, unrelated AGY project with decoy |
| Toolchain version | not covered | host and pinned CI only, no version matrix; record actual live AGY version |
| Clone shape | will test | a full clone with all refs / a fresh or shallow main-only clone; vendored baseline still compared, missing provenance never skipped |
| Run location | will test | invoked from the CPP root / from another directory with identical explicit source and output |
| Gate target | not applicable | no consumer quality-gate runtime selection change |
| Wave role state | not applicable | no role or mailbox registry edits |
| Reader: core adapter | tested against real output | expected build feeds actual core refresh/inspect and resulting trees are rehashed |
| Reader: build/check CLI | tested against real output | actual subprocess CLI consumes builder/core results |
| Reader: AGY skill invocation | will test | actual generated package in unrelated repo; intended guide/decoy/missing comparisons |
| Reader: Codex consumers | tested against real output | historical/candidate builds compared paths/bytes/modes; no downstream interface change |
| Reader: status/shared host update | not covered | #1889-B/#1892/#1893 integration remains separate |

Reader search positively found Makefile's Codex generator invocations before
listing consumers. Known downstream consumers Kyle/skillc/kyle-candidate retain
their current generator interface. Lane file reviewed 11 days ago: fresh.
Approval conditions from mailbox 40220: both transform/parser negative cases
must fail parity; missing baseline is unknown/failure. Once implementation is
frozen, commit exact scratch-only host commands in a probe file for master to
fetch with git show at the frozen SHA and run in agy-probe's isolated profile.
Log undo first; never touch the owner's real configuration. Live results remain
unknown until observed and this issue closes only on real evidence. Branch
pushes are allowed; PR requires ch-orch clearance.

Focused Make targets and registered controls precede formal counter-model
review; direct paired finish gate follows truthful runtime receipt. One AGY PR
in flight, PR CI only and owner CPP pin unchanged. Approval required before
implementation; mail Section C summary to ch-orch now.
