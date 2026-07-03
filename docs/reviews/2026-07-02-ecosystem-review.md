# CPP Ecosystem Review - 2026-07-02

**Scope:** Critical review of Claude Power Pack v7.2.0 against the mid-2026 Claude Code ecosystem: what the ecosystem has commoditized, what CPP still uniquely owns, and where new skill opportunities exist.

**Method:** Three parallel research passes on 2026-07-02: (1) a full repo surface audit of this checkout at commit `9f92e5e`, (2) a live web sweep of comparable toolkits (star counts pulled from the GitHub API that day), (3) a feature-by-feature absorption check against native Claude Code capabilities (changelog, code.claude.com docs, anthropics repos). LOC figures were re-verified locally excluding vendored venvs.

**Framing (owner decision):** CPP is the owner's working workflow and is NOT being abandoned or rewritten. The direction adopted from this review is targeted: leverage external tooling where it has won, and wrap CPP skills around the remaining gaps. See the umbrella issue "Implement targeted recommendations from the 2026-07 ecosystem review".

---

## 1. Repo surface audit (v7.2.0)

### Command surface

84 slash-command files across 16 families:

| Family | Files | Notes |
|--------|-------|-------|
| flow | 12 | largest: /flow:auto (553 lines) |
| cicd | 10 | framework detection, pipeline/container/IaC generation |
| secrets | 9 | tiered dotenv -> env-file -> AWS SM |
| github | 6 | issue CRUD wrapping gh |
| skills | 6 | skills.sh wrapper |
| spec | 5 | largest: /spec:create (278 lines) |
| codex | 5 | largest: /codex:auto (422 lines) |
| security | 5 | native scanner + gitleaks/pip-audit orchestration |
| cpp | 4 | /cpp:init 1,312 lines; /cpp:update 889; /cpp:status 638 |
| second-opinion | 3 | multi-vendor review via MCP |
| documentation | 3 | pptx (delegated to native skill), c4 |
| project | 2 | /project:init 686 lines; /project-next 504 |
| evaluate | 2 | 4-phase multi-model evaluation |
| self-improvement | 2 | deploy retrospective |
| claude-md | 2 | CLAUDE.md lint |
| qa | 2 | Playwright web testing |

Plus 33 generated skills in `.claude/skills/` (14 speckit-*, 19 topical guides), maintained via curated deprecation lists (`scripts/skill-drift.py`, `scripts/mcp-drift.py`).

### Real code weight (venvs excluded, verified locally)

| Component | Python LOC | Notes |
|-----------|-----------|-------|
| lib/cicd | 7,361 | the largest genuinely-maintained codebase in the repo |
| lib/creds | 3,846 | secrets CRUD, FastAPI UI, audit logging, AWS SM provider |
| mcp-second-opinion | 3,593 | 3 LLM SDKs (google-genai, openai, anthropic); 86 MB image |
| lib/security | 1,867 | native scanners + external tool adapters |
| lib/spec_bridge | 1,382 | spec parser + GitHub issue sync + status reconciliation |
| mcp-playwright-persistent | 823 | 29 tools; 155 MB image (browser binaries) |
| scripts | ~4,700 (py+sh) | drift detection, c4-mermaid, health checks |
| tests | 8,979 | 35 files; heaviest on cicd, docker, deploy, drift |

Note: an earlier automated count reported 106K LOC for mcp-second-opinion; that included a vendored venv and is wrong. Real source is ~3.6K LOC.

### Complexity sinks (corrected ranking)

1. **lib/cicd** (7.4K LOC): 7 language stacks, 2 CI platforms, deploy strategies, IaC stubs. Differentiated, and a keeper, but the widest maintenance surface.
2. **Operational footprint around the MCP servers**: Docker compose + Rust AWS sidecar + Woodpecker + hadolint + Trivy image gates + SBOM + LocalStack runtime smoke, all protecting ~4.4K LOC of actual MCP source. The Trivy DB drift gate is a recurring maintenance tax (two-layer digest + venv bumps, see #406/#409).
3. **Installer machinery** (`/cpp:init` + `/cpp:update` + `/cpp:status` = ~2.8K lines of command prompt): 5-tier symlink/Docker install wizard plus drift cleanup. Most of this exists because CPP is NOT distributed as a plugin.
4. **Dual command/skill surfaces**: repo `.claude/commands/flow/*` vs global `~/.claude/skills/flow-*` must be edited twice (known divergence pain).

### Pruning trend (already underway, and correct)

- v7.0: Redis coordination MCP -> git worktrees
- v7.2: removed mcp-nano-banana (PPTX -> native anthropics/skills@pptx; C4 -> scripts/c4-mermaid.py), removed mcp-woodpecker-ci, trimmed second-opinion catalog 8 providers -> 3, retired wiki-* skill family
- Curated deprecation lists + user-confirmed teardown in /cpp:update

---

## 2. Ecosystem landscape (as of 2026-07-02)

### Anthropic-official

- **Plugin system + marketplaces** are the first-class distribution unit: `.claude-plugin/plugin.json` bundling commands, agents, skills, hooks, MCP config; installed via `/plugin install name@marketplace`. Official directory (anthropics/claude-plugins-official, ~31.5k stars) held ~101 plugins as of March 2026 (33 Anthropic-built incl. feature-dev, code-review, commit-commands, security-guidance, frontend-design; 68 partner). Third-party marketplace ecosystem ~9,000 entries by mid-2026. Install counts are large (frontend-design ~829k installs).
- **Agent Skills** became an open standard (agentskills.io, Dec 2025), adopted by ~40 clients (Copilot, Cursor, Codex, Gemini CLI, Goose, OpenCode). anthropics/skills (~157k stars) ships the official pptx skill among others.
- **First-party workflow/review/security**: native /code-review (+ cloud multi-agent ultra tier), native /security-review (+ GitHub Action), feature-dev plugin.

### Major community toolkits (stars 2026-07-02)

| Toolkit | Stars | Distribution | Philosophy |
|---------|-------|--------------|------------|
| obra/superpowers | 244k | plugin marketplace | phase-ordered engineering culture as skills (brainstorm -> worktree -> plan -> TDD -> review -> finish); ~752k installs |
| garrytan/gstack | 119k | plugin | role-persona team-in-a-box; 2026 breakout |
| github/spec-kit | 117k | official Claude Code plugin | dominant spec-driven-development standard |
| ruvnet/ruflo (ex claude-flow) | 63k | npm | maximalist multi-agent swarm orchestration |
| BMAD-METHOD | 50k | installer + web bundles | methodology-first agile SDLC personas |
| hesreallyhim/awesome-claude-code | 48k | index | ecosystem map |
| wshobson/agents | 37k | plugin marketplace | 88 plugins/194 agents; multi-harness single-source generation |
| davila7/claude-code-templates | 28k | npx CLI + catalog | pre-plugin-era package manager, now catalog/analytics |
| vercel-labs/skills (skills.sh) | 25k | npx skills | "npm for agent skills"; install into ~70 agents |
| SuperClaude_Framework | 23k | pipx dotfile installer | earliest viral framework; still not plugin-based; now smallest of the majors (cautionary tale) |
| EveryInc/compound-engineering-plugin | 22k | plugin | plan/work/assess/codify loop persisting learnings |
| BeehiveInnovations/pal-mcp-server (ex zen-mcp) | 12k | MCP server | cross-vendor model consultation (Gemini/GPT/Grok/OpenRouter/Ollama), consensus/debate workflows |

### Distribution-model norm

Plugin marketplaces are unambiguously the mid-2026 norm; git-clone + symlink/dotfile installers are the legacy pattern the leaders migrated off during late 2025 / early 2026. CPP's symlink install (and its dual-surface drift and 2.8K-line installer wizardry) is a structural cost of the legacy model.

---

## 3. Native absorption assessment (feature by feature)

Ratings: FULLY / LARGELY / PARTIALLY absorbed, or STILL DIFFERENTIATED.

| # | CPP feature | Native state (mid-2026) | Rating |
|---|-------------|--------------------------|--------|
| 1 | /flow worktree + PR plumbing | Built-in worktrees since v2.1.49 (`--worktree`, `.claude/worktrees/`); EnterWorktree tool; subagent worktree isolation by default; background agents commit/push/open draft PRs on finish (v2.1.194); claude-code-action v1.0 does issue -> PR in GH Actions; Routines = scheduled cloud agents | LARGELY (mechanics); the gate POLICY is not absorbed |
| 2 | /security:scan | Native /security-review (semantic: SQLi, XSS, authz, creds) + official GitHub Action. No native deterministic secret scanning, git-history scanning, or tool orchestration | PARTIALLY (semantic half absorbed; gitleaks/history half not) |
| 3 | second-opinion MCP | Native /code-review + cloud multi-agent ultra tier, but Anthropic-models-only. Cross-vendor consultation still requires community tooling (PAL/zen-mcp is the off-the-shelf leader) | PARTIALLY (multi-agent yes, multi-vendor no) |
| 4 | PPTX + diagrams | Official anthropics/skills pptx skill (already adopted by CPP in v7.2). No official C4/Mermaid skill found | PPTX LARGELY; C4 generator STILL DIFFERENTIATED |
| 5 | /skills:* wrapper | npx skills CLI + /plugin marketplace + auto-loading .claude/skills + /reload-skills | FULLY |
| 6 | /project:init | /init upgraded (~Mar 2026) to interview-style scaffold of CLAUDE.md/skills/hooks, but does NOT do zero-to-GitHub-repo (repo creation, CI, branch protection, first issues) | PARTIALLY (config half absorbed; repo-bootstrap half not) |
| 7 | /secrets:* | Only protective controls exist natively (sandbox.credentials blocks credential reads; deny rules; sandbox network allowlists). No native store/get/set/rotate/run story. Ecosystem norm for individuals is 1Password op run; an AWS SM sidecar is uncovered niche | STILL DIFFERENTIATED |
| 8 | /cicd:* | Nothing native. /install-github-app only scaffolds the Claude action workflow, not project pipelines/Makefiles/health/smoke | STILL DIFFERENTIATED (confirmed) |
| 9 | /spec:* | spec-kit official Claude Code plugin: 9 commands incl. speckit.clarify, speckit.analyze, speckit.checklist, and speckit.taskstoissues (tasks.md -> GitHub issues = /spec:sync's job) | LARGELY (by spec-kit, not by Claude Code) |
| 10 | /codex:auto | No native cross-vendor delegation (never will be). Pattern is commoditized at small granularity (codex-delegator skill, awslabs/cli-agent-orchestrator) but nobody prominent delegates a full issue lifecycle to a rival CLI | STILL DIFFERENTIATED |
| 11 | Safety hooks | PreToolUse deny hooks are the documented native guardrail path; native auto-blocking of destructive git commands (v2.1.154); OS sandboxing; permission auto-mode classifier; managed settings. Native blocks credential READS but does not MASK output | LARGELY (dangerous-command hook); secret-masking hook still additive |
| 12 | Persistent Playwright MCP | microsoft/playwright-mcp: persistent profiles by default, isolated mode, state save/restore, full tab management, Chrome extension mode; plus Claude Code native Chrome integration (beta). Gap: named concurrent multi-session management (open upstream request, playwright-mcp #1530) | LARGELY; named multi-session is the only remaining edge |

### Claude Code changelog highlights (late 2025 -> mid 2026)

Plugins + marketplaces, Agent Skills, subagents, /rewind, native LSP (2.0.x, late 2025); built-in worktrees (v2.1.49, Feb 2026); /init interview upgrade, /loop, Computer Use preview (Mar 2026); cloud multi-agent review tier + /code-review --fix (Apr 2026); dynamic workflows, agent teams, nested subagents, EnterWorktree, draft-PR-on-finish, sandbox.credentials, destructive-git auto-blocking, Routines/scheduled cloud agents (May-Jun 2026).

---

## 4. Verdicts

Guiding principle (owner-set): keep the CPP workflow; adopt upstream where commodity; wrap skills around gaps.

| Surface | Verdict | Rationale |
|---------|---------|-----------|
| /skills:* (6 cmds) | RETIRE | fully absorbed by npx skills + /plugin |
| /spec:create, /spec:sync, lib/spec_bridge | RETIRE after adapter check | spec-kit plugin upstream; see section 5 |
| /spec:status | KEEP conditionally | only if speckit lacks a bidirectional drift view |
| /flow worktree/PR plumbing | THIN | rebase onto native worktrees; keep gates, eli5, merge/cleanup discipline |
| Semantic half of /security:scan | THIN | defer to native /security-review; keep gitleaks/git-history/pip-audit orchestration |
| PreToolUse dangerous-command hook | RETIRE | native destructive-command blocking + sandbox |
| PostToolUse secret-masking hook | KEEP | native blocks reads, does not mask output |
| /documentation:pptx | done (v7.2) | already delegated to native skill |
| /documentation:c4 | KEEP | no native or prominent community equivalent |
| mcp-playwright-persistent | DECIDE | upstream absorbed persistence/tabs/state; only named multi-session remains; consider contributing that upstream (playwright-mcp #1530) vs carrying a 155 MB image for one feature |
| mcp-second-opinion | DECIDE | cross-vendor review is still a real niche; evaluate adopting PAL (12k stars) vs maintaining own 3-SDK server; keep the AWS sidecar secrets integration either way |
| /project:init CLAUDE.md portion | THIN | delegate to upgraded native /init; keep zero-to-repo orchestration |
| /cicd:* | KEEP | zero native or community equivalent, especially self-hosted Woodpecker |
| /secrets:* | KEEP | no native secrets store; integrate WITH sandbox.credentials rather than compete |
| /codex:* | KEEP | full-lifecycle cross-vendor delegation exists nowhere prominent |
| /flow gate policy + eli5 | KEEP (core moat) | no competitor is GitHub-issue-anchored with enforced quality gates |
| Installer (/cpp:init 5-tier symlink model) | RESTRUCTURE (evaluate) | plugin packaging would remove the dual surfaces, drift scripts, and most of the 2.8K-line wizard |

### CPP's durable identity after the cuts

Production discipline for a solo dev running real self-hosted infrastructure:

1. /flow as issue-anchored gate POLICY riding native worktree mechanics
2. /cicd:* codegen incl. self-hosted Woodpecker (uncovered ground ecosystem-wide)
3. /secrets:* lifecycle with the AWS SM sidecar (uncovered niche; ecosystem norm is 1Password, which does not fit AWS-centric shops)
4. /codex:auto cross-vendor lifecycle delegation
5. Cross-vendor second opinion (own server or PAL)

Distinct from every persona-pack and swarm-orchestrator in the landscape.

---

## 5. Spec-kit replacement: will it improve quality?

Short answer: yes for the spec-authoring pipeline, with two integration risks and one keeper.

**Where quality improves.** spec-kit's prompts are community-iterated at 117k-star scale and its plugin ships verification stages CPP lacks: speckit.clarify (structured de-ambiguation), speckit.analyze (cross-artifact consistency between spec/plan/tasks), speckit.checklist (acceptance validation). CPP's /spec:create is a single 278-line prompt with none of those loops. CPP's `.specify/` structure was already modeled on spec-kit, so migration friction is low, and ~1.4K LOC of spec_bridge plus tests and 5 commands get deleted. Upstream improvements arrive for free.

**Risk 1: issue shape.** `lib/spec_bridge/issue_sync.py:274` stamps every synced issue with `[<feature-name>, wave-N, enhancement]` labels. /flow:auto only needs an issue number, so flow compatibility is fine, but anything filtering by those labels (e.g. /project-next prioritization, wave ordering) breaks if speckit.taskstoissues labels differently. Mitigation: run speckit's sync against a scratch repo, diff the issue shape; worst case a ~20-line label-normalization adapter, not the whole bridge.

**Risk 2: /spec:status has no upstream equivalent.** `lib/spec_bridge/status.py:135` reconciles bidirectionally by querying issues by feature-name label and reporting spec/issue drift. spec-kit's sync is generate-and-push. If the drift view is actually used, keep /spec:status repointed at speckit's labels; if not, cut it too.

**Workflow-weight counterpoint.** spec-kit's full ceremony (constitution -> specify -> clarify -> plan -> tasks -> implement) is team-scale. For solo work the quality gain concentrates in speckit.clarify and speckit.analyze; the other stages are skippable overhead.

**Sequencing.** (1) Trial speckit.taskstoissues against a scratch repo, confirm the label story. (2) Add adapter if needed. (3) Delete spec_bridge in the same release that documents "spec-driven dev = spec-kit plugin + /flow:auto" as the supported path.

---

## 6. New skill opportunities (ranked by fit with core identity)

1. **Extract /flow:eli5 as a standalone necessity-gate plugin/skill.** The "should this issue exist at all" gate is genuinely novel (nothing in superpowers, spec-kit, or BMAD asks it). Small, portable, differentiated; a natural marketplace entry point.
2. **Deploy-verification / post-deploy watchdog skill.** "Validate the deployment, not just the code" - extend /cicd:smoke + /self-improvement:deployment into a distinctive deploy-confidence skill (post-deploy health regression, rollback verification). Nothing native covers it.
3. **Learning-codification loop.** Generalize /self-improvement:deployment: post-merge retro that asks what broke, what gate would have caught it, and writes the gate. Compound-engineering's philosophy, fitted to CPP's discipline story.
4. **Woodpecker / self-hosted CI plugin.** Genuinely uncovered ground in the entire ecosystem (everyone assumes GitHub Actions). Small audience, zero competition.
5. **Multi-harness skill generation.** wshobson/superpowers generate Codex/Cursor/Gemini artifacts from single markdown sources; making CPP's surviving skills consumable from Codex CLI is 2026 table stakes and replaces the retired codex-skill-gen approach with the standard pattern.
6. **Named-session Playwright: contribute upstream** (microsoft/playwright-mcp #1530) rather than build more; a merged PR retires the fork obligation permanently.

---

## 7. Sources

Key references gathered 2026-07-02 (see umbrella issue for the actionable subset):

- anthropics/claude-plugins-official, code.claude.com/docs/en/discover-plugins, anthropics/skills, agentskills.io coverage (The New Stack)
- code.claude.com/docs/en/worktrees, /docs/en/code-review, /docs/en/permissions, /docs/en/security, /docs/en/github-actions, /docs/en/chrome, /docs/en/agent-teams
- anthropic.com/news/automate-security-reviews-with-claude-code, anthropics/claude-code-security-review
- github/spec-kit (incl. plugin PR #1451 with speckit.taskstoissues), GitHub blog on spec-driven development
- obra/superpowers, garrytan/gstack, ruvnet/ruflo, BMAD-METHOD, wshobson/agents, davila7/claude-code-templates, SuperClaude_Framework, EveryInc/compound-engineering-plugin, hesreallyhim/awesome-claude-code
- BeehiveInnovations/pal-mcp-server (ex zen-mcp-server)
- microsoft/playwright-mcp (+ user-profile docs, issue #1530), playwright.dev/mcp
- vercel-labs/skills, vercel.com/changelog (skills.sh), skills.sh
- 1Password MCP security posts, Token Security on MCP secrets hygiene
- Nimbalyst agent-manager comparison, Composio top-plugins, Developers Digest worktree playbook
