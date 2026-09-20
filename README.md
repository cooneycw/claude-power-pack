# Claude Power Pack

**v8.0.0** - A productivity toolkit for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that adds workflow automation, MCP servers, security scanning, secrets management, and CI/CD integration - and, from 8.0, a verification discipline: a check whose output is read as evidence ships with a committed input that makes it report the other verdict, and a second model reviews every change by default.

## What It Does

- **Workflow commands** (`/flow:auto`, `/flow:start`, `/flow:eli5`, `/flow:finish`) - Issue-driven development with worktrees, a pre-implementation ELI5 plan/necessity approval gate that cannot be bypassed (#775), quality gates, automated PR lifecycle, and CI verification. The necessity gate also ships standalone as [eli5-gate](https://github.com/cooneycw/eli5-gate) - installable without CPP via `/plugin marketplace add cooneycw/eli5-gate` or `npx skills add cooneycw/eli5-gate`; CPP vendors its canonical core (file gate improvements there)
- **Wave orchestration** (`/flow:wave`, `/flow:register`, `/flow:sync`) - dependency-ordered issue waves fanned out across worker sessions, coordinated through a durable mailbox with an armed/stale/dead watch status visible on the roster (#778, #801), and per-driver capability declarations (scope, web access) so an orchestrator can check whether a driver can do the work before assigning it, not after a worker refuses (#783)
- **MCP servers** extending Claude Code's capabilities:
  - **Second Opinion** - Multi-model code review via external LLMs (Gemini, OpenAI, Anthropic), served by the external `cooneycw/mcp-second-opinion` repo and wired in through the root `.mcp.json` (streamable-http)
  - **Browser automation** - upstream `@playwright/mcp` server (npx/stdio, no container), registered by `/cpp:init`
  - **Tavily** - web search, content extraction, site crawling, and URL mapping via the upstream `tavily-mcp` server (npx/stdio), registered by `/cpp:init`; API key stored in AWS Secrets Manager (`claude-power-pack/mcp-keys`)
- **PowerPoint generation** - Slide decks via the native Anthropic `pptx` skill (`npx skills add anthropics/skills@pptx`)
- **Security scanning** (`/security:scan`) - Native vulnerability detection with git history analysis
- **Secrets management** (`/secrets:*`) - Tiered credential storage (dotenv, env-file, AWS Secrets Manager) with audit logging and a web UI
- **CI/CD integration** (`/cicd:*`) - Framework detection, Makefile generation, health checks, and IaC scaffolding
- **Woodpecker CI** - Self-hosted pipeline (secret-scan, lint, test, typecheck, Dockerfile lint) with programmatic status polling
- **Project scaffolding** (`/project:init`) - Zero-to-GitHub-repo setup with Makefile, CI pipeline, and Docker config
- **Skills ecosystem** - Discover, install, and manage agent skills from [skills.sh](https://skills.sh/) via native `npx skills` and the `/plugin` marketplace (the CPP `/skills:*` wrapper was retired in issue #437)
- **Secret-masking hook** - a PostToolUse hook in `.claude/hooks.json` masks secrets (connection strings, API keys, env vars) in Bash/Read output; host installation is managed by `/cpp:init` / `/cpp:update`; destructive commands are handled by Claude Code's native git auto-blocking + OS sandbox

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (optional - only to run the external second-opinion server locally, or as the gitleaks fallback for `make secret-scan`)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- GitHub CLI (`gh`) for issue/PR workflows

## Install

CPP's own plugin marketplace was retired by issue #662 and ADR [0005](docs/decisions/0005-retire-plugin-marketplace-distribution.md). Clone the repository; issue #663 restores the tiered `/cpp:init` + `/cpp:update` symlink surface as the canonical command installation path:

```bash
git clone https://github.com/cooneycw/claude-power-pack.git
cd claude-power-pack

# The restored canonical installer lands in issue #663:
/cpp:init
```

Existing CPP marketplace users should run `/plugin uninstall <family>@cpp` for each of the 15 installed families. `scripts/install-drift.sh` keeps the host checks visible: it guards installed `~/.claude/scripts/` helpers against the checkout through #663's symlink restoration, names lingering marketplace cache families as retired, non-failing migration state, and compares the installed `~/.codex/skills/` (#823) and `~/.claude/skills/` (#1029) COPIES - which `git pull` cannot refresh - against their sources. Every verdict is prefixed by `scripts/toolchain-provenance.sh`, because all of those compare against the checkout and none of them can say how current the checkout itself is (#1029). The symlink tier restored by #663 replaces those caches and follows `git pull` without a separate update stamp.

### Host setup

`/cpp:init` also configures the out-of-band infrastructure used by some command families:

- **External Second Opinion server** - the multi-model review server lives in its own repo ([cooneycw/mcp-second-opinion](https://github.com/cooneycw/mcp-second-opinion)). Start the external server, then register it with `claude mcp add second-opinion --transport http --url http://127.0.0.1:8080/mcp --scope user` (use your Tailscale URL for a remote host).
- **Browser automation** - registers the upstream `@playwright/mcp` npx/stdio server (no container).
- **Tavily web tools** - registers the upstream [tavily-mcp](https://github.com/tavily-ai/tavily-mcp) npx/stdio server for web search, extract, crawl, and map. Requires `TAVILY_API_KEY` (stored in AWS Secrets Manager `claude-power-pack/mcp-keys`).
- **Secrets provisioning** - AWS Secrets Manager access for Woodpecker CI keys (`essent-ai`) and the `CPP_MEMORIES_DSN` common-memory DSN; fetched directly via the AWS SDK/CLI.
- **Bootstrap prerequisites** - `jq`, and the optional spec-kit CLI (`specify`, the engine behind `/spec:adopt`).
- **Permission census hook + flow allowlist** - registers the observe-only PermissionRequest census hook and merges the read-only `/flow:*` allowlist - including the audited flow helper-script rules that make `/flow:auto` Phase 1 prompt-free (issue #581) - into `~/.claude/settings.json` (both user-confirmed).

`/cpp:update` refreshes those same host artifacts. See [`docs/HOST_MANAGED_ARTIFACTS.md`](docs/HOST_MANAGED_ARTIFACTS.md) for the full inventory.

### Developing CPP itself

To work on CPP (not just use it), clone and run the quality gates:

```bash
git clone https://github.com/cooneycw/claude-power-pack.git
cd claude-power-pack
uv sync --extra dev
make verify
```

`make verify` closes by naming every checker in the repository it did NOT run, with the reason for each - host-dependent checks, network checks, and the control battery. A checker accounted for nowhere fails the gate, so one cannot be added and wired to nothing (#1028).

`.claude/commands/<family>/*.md` is the permanent source of truth. It feeds only the generated Codex harness surface: `scripts/codex-skill-sync.py` emits per-command Codex skills under `codex/skills/` (`make codex-skills`, issue #555), guarded by an explicit `codex-skills-check` step in both CI and `make verify` (#1028). A bundled helper ships with what it actually runs - its sibling scripts and the libraries it imports - so the shipped copy can start. The older flat `codex/prompts/` surface it replaced was retired at the #556 cutover.

## Project Structure

```
claude-power-pack/
  .claude/commands/     Slash commands (/flow:*, /cicd:*, /security:*, etc.)
  .claude/hooks.json    Safety hooks (pre/post tool use)
  .mcp.json             Client pointer for the external second-opinion server
  codex/skills/         Generated Codex SKILL.md skills, second harness surface (#555)
  codex/cpp-memory.md   Curated Codex /cpp-memory prompt (#433; flat codex/prompts/ retired #556)
  lib/creds/            Secrets management library
  lib/security/         Security scanning library
  lib/cicd/             CI/CD framework detection and generation
  lib/vendor.py         Shared fetch/pin/drift core for external-repo links (#1012)
  docs/skills/          Topic-focused best practices (~3K tokens each)
  docs/scripts.md       Per-script history for the scripts/ inventory (#711);
                        population derived + gated by make scripts-inventory-check (#1013)
  docs/commands-reference.md  Per-command detail beyond the skill listing (#711)
  docs/security/dependency-advisory-dispositions.md
                        Per-advisory verdicts for the root uv.lock: look a scanner's
                        GHSA/PYSEC/CVE id up here before re-deriving it (#922)
  docs/security/bandit-finding-dispositions.md
                        Per-finding verdicts for bandit's MEDIUM+ residual: look a
                        (file, rule) pair up here before re-deriving it (#1113)
  woodpecker/           Woodpecker CI server + agent deployment configs
  templates/            Makefile, workflow, and container templates
  scripts/              Shell utilities
  controls/             Registered negative controls: per-gate fixtures + blind anchors (#924)
  tests/                Unit tests
  .woodpecker.yml       CI pipeline (secret-scan, lint, test, typecheck, drift gates, negative controls, Dockerfile lint)
  Makefile              Build interface for all operations
```

## Key Commands

| Category | Command | Description |
|----------|---------|-------------|
| Workflow | `/flow:auto 42` | Full issue lifecycle in one shot |
| Workflow | `/flow:start 42` | Create worktree for an issue |
| Workflow | `/flow:eli5 42` | Plain-language intent + necessity verdict + plan approval gate |
| Workflow | `/flow:finish` | Lint, test, typecheck, commit, push, create PR |
| Workflow | `/flow:wave` | Orchestrate a dependency-ordered issue wave across worker sessions |
| Improve | `/self-improvement:retro` | Post-run friction retro: capture -> codify durable fixes (the grill-me cycle) |
| Project | `/project:init myapp` | Scaffold a new project |
| Security | `/security:scan` | Full vulnerability scan |
| Secrets | `/secrets:list` | List managed credentials |
| CI/CD | `/cicd:init` | Detect framework, generate Makefile |
| Docs | `/documentation:c4` | Generate C4 architecture diagrams |
| Browser | `/browser:session create gmail` | Named concurrent browser sessions (lease-desk pool) |
| Review | `/second-opinion:start` | Get code review from external LLMs |

## MCP Servers

CPP ships no container runtime (retired in #469). The `/second-opinion:*` and `/evaluate:*` commands consume an **external** second-opinion server that runs from its own repo:

- Server repo: https://github.com/cooneycw/mcp-second-opinion (server + the AWS Secrets Manager Agent sidecar build recipe + a standalone docker-compose)
- CPP ships a root `.mcp.json` registering `second-opinion` as a streamable-http client at `${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp` (issue #633): localhost 8080 by default, overridable WITHOUT editing any tracked file by exporting `SECOND_OPINION_URL` with the base url, no `/mcp` (e.g. `export SECOND_OPINION_URL=http://127.0.0.1:8090`, or a Tailscale URL). Start the external server, then either rely on that env override or register at user scope:

```bash
claude mcp add second-opinion --transport http --url http://127.0.0.1:8080/mcp --scope user
```

Browser automation uses the upstream `@playwright/mcp` npx/stdio server (registered by `/cpp:init`). Tavily web search/extract/crawl/map uses the upstream `tavily-mcp` npx/stdio server (registered by `/cpp:init`); its API key (`TAVILY_API_KEY`) is stored in `claude-power-pack/mcp-keys` alongside the Second Opinion keys. CPP stores no application secrets on disk and runs no secrets sidecar; the remaining AWS Secrets Manager consumers (`essent-ai` for Woodpecker CI keys and the `CPP_MEMORIES_DSN` common-memory DSN) fetch directly via the AWS SDK/CLI.

## CI/CD

Woodpecker CI runs on every push and PR via a self-hosted agent:

- **Secret scan:** gitleaks over the tree before anything else runs
- **Tool staging:** `shellcheck-stage` and `jq-stage` copy their content-pinned binaries into `.ci-bin` for the steps that need them. Staging is deliberately SEPARATE from the gates that use those tools (#1086): `validate` needed one second of copying from a step that also spent thirty seconds linting, and `pytest` sat behind all of it
- **Validate:** lint (ruff) + test (pytest, parallel with an explicit worker cap - never `-n auto`) + typecheck (mypy) in a single consolidated step
- **Negative controls:** every registered gate must still report BAD on its known-bad fixture and GOOD on its known-good one, and each control must be demonstrated against a vendored anchor that MISSES the known-bad input - a control with no anchor is `UNPROVEN` and fails the step (#924)
- **Python SAST:** `bandit` over `lib/` and `scripts/`, gated at severity >= MEDIUM (#962). The skip list is EMPTY: codex-power-pack's inherited `--skip B104,B108,B310,B602` was measured against this tree and found to remove 10 of its 11 MEDIUM+ findings, because `shell=True` and hard-coded `/tmp` paths are what a repository of shell-out helpers does. The accepted residual lives one line per (file, rule, count) in `.bandit-audit-allow`, so a new site is a finding and a fixed one turns the gate red until its line comes out - though a same-count replacement is a named, tested blind spot rather than a claim. The step runs the live positive control BEFORE the audit, because a scan that cannot see prints the same clean line as a clean tree
- **Dockerfile lint:** hadolint over any remaining Dockerfile
- **CI verification:** `flow:auto` polls the Woodpecker API after merge to confirm the pipeline passes

The image-build, CVE-scan, SBOM, compose-policy, and runtime-smoke stages were retired with CPP's Docker MCP runtime in #469.

Architecture: Woodpecker server on a dedicated VM, agent on the dev workstation, connected via gRPC over Tailscale. Web UI at `woodpecker.essent-ai.com` via Cloudflare tunnel.

## Changelog

### v8.0.0 (2026-09-15)

**A major bump because it changes how work is ACCEPTED, not what commands
exist.** An instrument without a negative control stops being shippable, and
cross-model review moves from an opt-in command to a default stage. Both change
the contract with anyone building on CPP.

**Three ADRs, and 0008 and 0009 are siblings.**

- [ADR 0008](docs/decisions/0008-instrument-negative-control-bound.md) - before
  you ship an instrument, name the input that makes it report the **other
  verdict**. An instrument that cannot fail is not evidence: a green from a
  blind one and a green from a working one look identical. Bounded so it is
  affordable - the rule is owed where a verdict is consumed by a decision that
  will not independently re-derive it.
- [ADR 0009](docs/decisions/0009-oscillation-control.md) - before you ship a
  two-sided change, name the observation that would **move the setting back**,
  and commit it beside the setting. **Same epistemics, different object:** 0008
  governs instruments, 0009 governs the knobs those instruments are set with.
  If you cannot name one, it is not a decision - it is a preference, and it will
  oscillate.
- [ADR 0007](docs/decisions/0007-counter-model-review.md) - a second model reads
  the branch before the PR exists, by default, stated as a property rather than
  a tool name: *the reviewing model must not be the implementing model.*

**Registered negative controls went from nothing to six.** At the end of
2026-09-14 the `controls/` directory did not exist. The machinery itself landed
the next morning (#924), and by the end of 2026-09-15 six controls were
registered - `check-negative-controls`, `check-negative-fixture-preconditions`,
`check-oscillation`, `check-test-binary-guards`, `secret-scan`,
`shellcheck-gate`. The framework is registered in its own framework, which is
the point: a control battery nothing checks is the defect it exists to find.

> **The rest of this section is a dated snapshot of 2026-09-15, and two of its
> statements were closed by #1036 on 2026-09-20.** The snapshot is kept rather
> than rewritten, because what it records is a repository that could see its own
> accounting defect and say so before it had a fix - and a passage edited to look
> correct would destroy exactly that. What changed:
>
> - `check-oscillation` was added to the census by 967c098 (#1060), so the live
>   non-member named below no longer exists.
> - **the summary line no longer has the defect it is criticised for here.** It
>   now states the RELATION rather than two counts pressed together -
>   `22 registered, 22 of 90 enumerated instruments ... carry a control that
>   discriminates, none registered outside the census; the denominator is 76
>   registrable + 14 external subject(s) with no file under scripts/ for a
>   marker, reachable only by wrapping; discovery reads scripts/* (top-level
>   files only ...)`. A registered control whose gate is absent from the census
>   is NAMED, derived on every run. Reporting it is not yet FAILING on it; that
>   is a separate decision and printing the fact does not pre-empt it.

**Deliberately not stated as a coverage fraction over the 63-row census, because
the two numbers are counted independently.** Five of the six register against a
row in [ADR 0008](docs/decisions/0008-instrument-negative-control-bound.md)'s
census; `check-oscillation` is a **new** instrument that the census does not yet
enumerate, so the registration count is not a subset of the census and "6 of 63"
would be a fraction whose numerator and denominator do not describe the same
set. `secret-scan` also covers only the working-tree half of its row - the CI
step scans git history as well - and its manifest says so. The gate's own
summary line does print `N of 63`; **that line had the same defect** and was
recorded rather than quietly worked around - then fixed under #1036, which is
what the note above describes.

**Two counts, both honest, and neither is the other:** six registered controls,
and 63 enumerated instruments. Of the 63, discovery can currently find a
registration marker only in a top-level `scripts/` file, which is 48 of them -
the other 15 are external binaries and module entry points (`make verify`,
`ruff`, `mypy`, `pytest`, `gitleaks`, `hadolint`, `lib.cicd` x7,
`lib.security` x2). That is a limit of where the scan looks, not a hard ceiling:
`secret-scan` registers a control for `gitleaks` precisely by wrapping it in
`scripts/secret-scan-check.sh`, so a wrapper is the available route for the
other fourteen.

**The six is the gate's own output** (`NEGATIVE_CONTROL_REGISTERED: 6`), not a
file count. A recursive search **under `controls/`** returns **eight** - the two
extras are toy fixtures inside `check-negative-controls`' own test cases - and a
**repository-wide** search returns **nine**, the ninth being an unrelated
prototype manifest under `docs/research/`. Neither file count is the figure, and
both look like an inflated headline.

**Counting the six needs nothing; seeing all six PASS needs the CI
dependencies.** Registration is a discovery count and reports `6` regardless of
whether each control can run. The verdicts are what depend on tooling:
`controls/secret-scan` needs `gitleaks`, which CI stages into the
negative-controls step and a typical developer host does not have, and there it
reports `UNSIGNALLED` rather than passing. It is the inverse of the usual trap -
load-bearing where it gates, unrunnable where it was written - so a clone that
sees `UNSIGNALLED` is missing a tool, not reading a wrong figure.

**What the counter-model stage measured on its first run.** 16 red cases
proposed, **3 already covered** by the implementer's tests - 13 novel. Taken on
an **adversarial workload**: the change was authored by a session that had spent
that day on this exact defect class, with ADR 0008 merged the previous afternoon
(2026-09-14) and ADR 0009 that same afternoon (2026-09-15), the latter by the
same author. If the two models were agreeing by shared training
corpus rather than reviewing, that is the run where it would have shown. Stated
with the number, because a favourable measurement whose conditions are not
recorded gets discounted later by a reader assuming they were easy.

**A measurement corrected in flight, recorded rather than quietly replaced.**
The harness-strategy research below reports **0 of the last 200 merged PRs** ran
cross-model review, against a positive control of 199/200. Re-derived on
2026-09-15 that is **superseded**: 21 of 200, positive control 197, and the
shape is the finding - **0 of 170 across two months, then 21 of 30 in two days**,
because a wave orchestrator declared the driver in policy. The number moved
because of an intervention by the party doing the measuring, so the thesis is
not "an opt-in stage does not exist" but **"it exists exactly as long as someone
with authority keeps re-imposing it, and that mandate dies with the wave"** -
which is why 8.0 makes the stage a default rather than a command. The research
document is left as written; it was true when written.

**Those are MARKER counts, not execution counts, and the distinction is one of
8.0's own findings.** They count PR bodies containing a heading the run was
instructed to write - so a review that happened under a different heading is
counted as not having happened. PR #1000 is exactly that case, inside the
measured window: two review passes, eleven findings fixed, no marker. The
positive control shows the query works; it cannot detect this class of false
negative. ADR 0007 replaces the marker with a receipt written by the run, which
fixes it going forward; the historical count is not recoverable.

**The reasoning, not marketing.** Why an instrument now needs a red case is a
question with an evidence-based answer, and these are the documents that carry
it:

- [`docs/research/spec-driven-development-2026.html`](docs/research/spec-driven-development-2026.html) -
  the conference-grounded review (AI Dev / AI Native DevCon, AI Engineer World's
  Fair 2026, AIware 2026, GitHub Universe / Microsoft Build) that established
  the position 8.0 implements: the 2026 consensus is *spec-anchored*, not
  spec-as-source; the centre of gravity moved from "spec" to "harness"; and
  **verification outranks generation**.
- [`docs/research/harness-strategy-recommendation-2026-09-14.html`](docs/research/harness-strategy-recommendation-2026-09-14.html) -
  the strategy: keep CPP rather than migrate to a skills framework, bound the
  negative-control discipline so it is affordable, and make the counter-model
  routine.
- [`docs/research/issue-quality-assessment-2026-09-14.html`](docs/research/issue-quality-assessment-2026-09-14.html) -
  the delivery-quality review that set the constraint on how 8.0 was scoped:
  *"adopt the proportional issue contracts already delivered rather than
  building another governance layer."*

### v7.5.0 (2026-09-07)

- **Wave reliability fixes** - `/flow:wave` mailbox watch state is now fused from the live watcher count and its heartbeat stamp so a dead watch can no longer be reported as `armed` (#801); a post-clearance PR pipeline watch (`flow-pr-watch.sh`) classifies a cleared PR's next CI run as green/cancelled/flake/red/timeout instead of leaving it unwatched (#788); delegated driver lanes (`/codex:auto`, `/qwen:auto`, `/gemma:auto`) now judge run success from the payload rather than a misleading `$?`, after the Qwen CLI was found reporting `is_error: false` on a dead endpoint (#798); seven other confidently-wrong `flow-wave-mailbox watch` reports fixed (#792)
- **Driver capability declarations** (#783) - `scripts/flow-driver-capability.sh` declares each delegated driver's scope (general vs. implementation-only) and web access so an orchestrator can check fit before assignment instead of after a worker refuses
- **Wave roster shows who's actually listening** (#778) - `flow-wave-mailbox.sh watch` stamps a heartbeat so the roster can tell an armed watch apart from one that died silently
- **No-bypass gates extended to the delegated drivers** (#784, #775) - the ELI5 plan/necessity approval gate and its delegated-driver equivalent now have no invoker-typed or trailer-based bypass on any of the four drivers

### v7.4.0 (2026-07-18)

- **Top-level commands folded into families + discovery-completeness gate** (#582) - `/project-next` / `/project-lite` became `/project:next` / `/project:lite`; `/dockers`, `/happy-check`, `/load-best-practices`, `/load-mcp-docs` moved into the `cpp` family; a new gate fails CI on any command left outside `.claude/commands/<family>/*.md`, since that path is what both the plugin and Codex-skill generators discover from

### v7.3.0 (2026-07-04)

- **Plugin-marketplace distribution + install-path cutover** (epic #417 Phase B, ADR 0001) - CPP adopted 15 per-family plugins and retired its earlier symlink surface (#477/#478/#479/#480). **Reversed 2026-08-11:** issue #662 / ADR 0005 retires CPP's marketplace lane after version-stamp drift proved unreconcilable; uninstall existing families with `/plugin uninstall <family>@cpp`. The tiered `/cpp:init` + `/cpp:update` symlink surface returns as canonical in #663.
- **Docker MCP runtime retired** (#469, #423) - Second Opinion moved to its own external repo ([cooneycw/mcp-second-opinion](https://github.com/cooneycw/mcp-second-opinion)) consumed via a `.mcp.json` client pointer; browser automation moved to the upstream `@playwright/mcp` npx server. CPP ships no containers and `make deploy` is an informative no-op.
- **`/flow:eli5` necessity gate extracted** to the standalone [eli5-gate](https://github.com/cooneycw/eli5-gate) plugin (#443); CPP vendors its canonical core with a drift check.

### v7.2.0 (2026-06-28)

- **`/flow:eli5` + `/flow:auto` approval gate** (#398) - plain-language intent, necessity/staleness verdict, and a plan-approval pause between Analyze and Implement
- **Skill drift/orphan detection in `/cpp:update`** (#395) - curated-list-driven detection and guarded prune of retired/orphaned generated skills
- **Fix:** `drift-detect.sh` no longer reports false Docker/systemd "deployment model conflict" on Docker-only hosts - systemd unit presence now derives from `LoadState`, not `is-active` (#400)

### v7.1.0 (2026-06-07)

- **Skills ecosystem integration** - New `/skills:*` command family wrapping the `npx skills` CLI for discovering, installing, and managing agent skills from [skills.sh](https://skills.sh/)
- Quality vetting in `/skills:find` checks install counts, source reputation, and GitHub stars before recommending

### v6.0.0 (2026-05-31)

- **Breaking change: Docker-only MCP deployment** - Docker with local builds is now the only supported Tier 3 runtime
- **Legacy systemd migration** - `cpp:update` detects legacy MCP systemd units and guides teardown before Docker refresh
- **Status clarity** - `cpp:status` reports `Docker (local build)` and labels remaining systemd units as migration-required legacy state

### v5.2.0 (2026-03-08)

- **C4 diagram QA framework** - `validate_diagram` MCP tool with density scoring, XSS sanitization, WCAG AA contrast checks
- **Multi-diagram C4 generation** - L3 for all containers, L4 for top 3 components per container
- **Density-aware splitting** - `split_diagram` MCP tool auto-splits large diagrams into summary + detail views
- **QA gating in skills** - c4 and pptx skills check warnings after every `generate_diagram`, retry on edge errors, split on overflow
- **Shared theme tokens** - `ThemeTokens` contract for consistent colors across all diagram types
- **c4-manifest.json** - Tracks all generated diagrams with parent-child relationships
- **index.html** - Hierarchical navigation page for all C4 diagrams
- **XSS fix** - HTML-escape all node labels in diagram output
- **WCAG AA fix** - All color palettes meet 4.5:1 minimum contrast ratio
- **496 tests** - Comprehensive test coverage for validation, density, splitting, contrast, and C4 integration

### v5.1.0 (2026-03-07)

- **Woodpecker CI pipeline** - Self-hosted CI with MCP image security gates
- **Runtime smoke tests** - CI brings the MCP stack up in an isolated compose project, checks service health, then tears it down
- **CI verification in flow:auto** - New Step 7/8 polls Woodpecker or GitHub Actions after merge, blocks deploy on failure
- **Consolidated pipeline** - Merged lint/test/typecheck into single validate step (eliminates 2x `uv sync`)
- **Health-based runtime checks** - `docker compose --wait` validates container healthchecks during smoke runs
- **Extended CI polling** - flow:auto timeout increased from 5 to 10 minutes
- **Woodpecker v3 API fix** - Repo ID lookup for correct API path

### v5.0.2 (2026-02-27)

- Nano Banana: Base64 OOM guard, Docker path fallback, validation tightening
- SlideDefinition dataclass for PowerPoint generation
- MCP server drift detection in `/cpp:update`

### v5.0.1 (2026-02-26)

- PPTX QC validation, multi-framework support, AWS gating
- Em dash cleanup across all markdown and documentation

## License

MIT - see [LICENSE](LICENSE)
