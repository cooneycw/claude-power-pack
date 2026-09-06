# Claude Power Pack

Claude Power Pack (CPP) is a Python 3.11+ repository of issue-driven workflow,
CI/CD, security, documentation, and project-management commands for Claude Code
and Codex. Command documents are the orchestration sources; Python and shell
helpers own deterministic behavior.

## Core Directives

- **NEVER output API keys, passwords, connection strings, or `.env` file contents in responses.** Output masking does not protect response text.
- **Use `make` targets for build/test/deploy operations.** If a needed target is missing, add it to the Makefile.
- **Progressive disclosure:** do not auto-load documentation; load the topic-specific source only when the task requires it.
- **Python 3.11+, uv for dependencies.** Each component owns its dependency configuration.
- **When fixing errors, fix BOTH the application code AND the CI/CD process.** Never bypass quality gates.
- Before debugging manually, run `make lint` and `make test`.
- A test that shells out to a real binary must use a `shutil.which` skip guard - including when it reaches that binary by running a repo shell script. `scripts/check-test-binary-guards.py` enforces the detailed contract.
- A fixture that constructs a NEGATIVE condition must assert that precondition before exercising the code. `scripts/check-negative-fixture-preconditions.py` owns the detectable contract.
- A pattern-matching fixture must not interpolate an absolute path it does not control; use a fixture-owned relative value and assert the intended classification.
- After any fix, verify through the full pipeline with `make verify`.
- Use `/cpp:dockers` for container status, health, and project linkages.
- Use single dashes (-), never Unicode em or en dashes, in markdown, comments, and documentation.
- Never wrap a read-only command in `cd X && ...`; use `git -C`, an absolute path, or the tool's path argument.
- Resolve edit paths from `git rev-parse --show-toplevel`; never hand-build an absolute worktree path (#486).
- In shared checkouts, characterize branch content with ref-scoped reads only; never substitute a working-tree read or cwd-relative pathspec for a branch measurement.
- Keep one inventory item per line. Per-item history belongs in [the script reference](docs/scripts.md) or [the command reference](docs/commands-reference.md), not this always-loaded file.

The detailed rationale, incidents, exceptions, and state transitions behind
these rules remain in [commands-reference.md](docs/commands-reference.md) and
[scripts.md](docs/scripts.md).

## Project Map

- `docs/skills/` - topic guidance loaded on demand.
- `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md` - full best-practices guide.
- `docs/commands-reference.md` - command decisions, histories, and workflow detail.
- `docs/scripts.md` - script inventory and per-script behavioral history.
- `docs/agents/knowledge-lifecycle.md` - canonical completed-spec graduation policy.
- `ISSUE_DRIVEN_DEVELOPMENT.md` - issue-driven development source.
- `PROGRESSIVE_DISCLOSURE_GUIDE.md` - context-loading guidance.
- `MCP_TOKEN_AUDIT_CHECKLIST.md` - MCP context-efficiency checklist.
- `.specify/` - active specifications, plans, tasks, templates, and lifecycle ledger.
- `.claude/commands/` - canonical Claude command documents and detailed state machines.
- `.claude/skills/` - canonical topic-skill packages and provenance.
- `codex/skills/` - generated Codex command-skill mirrors; regenerate with `make codex-skills`.
- `scripts/` - deterministic helpers and repository checks.
- `lib/cicd/` - CI/CD configuration, runner, health, smoke, and deployment verification.
- `lib/security/` - deterministic secret, dependency, and policy scanning.
- `lib/creds/` - secret retrieval, injection, UI, and audit support.
- `lib/cpp_memory/` - fail-open local or federated friction-knowledge ledger.
- `templates/` - Makefile, workflow, permission, and container templates.
- `vendor/project_next/` - pinned project-next engine vendored from codex-power-pack.
- `.woodpecker.yml` - repository CI pipeline.

Component contracts and retired-surface history are routed through
[the command reference](docs/commands-reference.md) and
[the script reference](docs/scripts.md); do not duplicate them here.

## Environment Variables

- `CLAUDE_PROJECT` selects the default `/project:next` repository under the user's projects directory.
- `FLOW_WORKTREE_BASE` optionally relocates visible sibling flow worktrees; never set it in shipped config.
- `SECOND_OPINION_URL` overrides the external second-opinion server base URL.
- `CPP_MEMORIES_BACKEND` selects the documented common-memory backend.

See [commands-reference.md](docs/commands-reference.md) for precedence and host
installation details.

## MCP Servers and Secrets

CPP ships no container runtime. It consumes the external second-opinion server
through `.mcp.json`, upstream Playwright MCP through `/cpp:init`, and upstream
Tavily MCP (tavily-mcp, npx/stdio) through `/cpp:init` for web search, extract,
crawl, and map. The Tavily API key is stored in `claude-power-pack/mcp-keys`
alongside the Second Opinion keys. Remaining AWS Secrets Manager consumers fetch
directly through the SDK or CLI; CPP stores no application secrets in this
repository. Use `/secrets:*` for credentials and `make secret-scan` for the
deterministic leak check. Runtime retirement, bootstrap, drift, and
reproducible-image details live in
[commands-reference.md](docs/commands-reference.md).

## Commands Reference

Command descriptions are already present in each session's skill listing. Use
the smallest applicable workflow and load its command document for execution:

- `/flow:*` - issue worktrees, planning gate, implementation, finish, merge, wave orchestration, and cleanup.
- `/project:init` - destination-first project creation and optional Wayfinder/spec handoff.
- `/project:next` - planning-aware next-action routing through the always-present vendored engine.
- `/spec:adopt` and `/speckit-*` - official spec-kit authoring; implementation routes to `/flow:auto`.
- `/cicd:*` - Makefile, container, pipeline, health, smoke, deploy, and infrastructure workflows.
- `/security:*` - deterministic scans; use native `/security-review` for semantic vulnerability review.
- `/documentation:*` - repository documentation, C4 diagrams, and presentations.
- `/claude-md:lint` - generated-project governance and compact knowledge-lifecycle guidance.
- `/cpp:*` - installation, updates, status, diagnostics, and on-demand references.
- `/self-improvement:*` - friction retrospectives and portable memory.
- `/second-opinion:*` and `/evaluate:*` - external multi-model evaluation.
- `/browser:session` and `/qa:test` - browser sessions and web QA.
- `/secrets:*` - masked credential management and validation.

Detailed arguments, recovery states, delegation decisions, and incident history
live in [commands-reference.md](docs/commands-reference.md). The permanent
workflow sources live under `.claude/commands/`.

## Makefile Integration

Makefile targets are the canonical build interface. Required local gates are:

- `make lint` - lint source.
- `make test` - run the test suite.
- `make typecheck` - run static type checks.
- `make verify` - full pre-deploy verification, including persistent-context checks.
- `make skills-check` - validate topic-skill provenance and surfaces.
- `make project-next-check` - verify the vendored project-next hash contract.
- `make codex-skills` - regenerate mirrors after command-document changes.

Flow runner, deployment, baseline, and fallback behavior remains in
[commands-reference.md](docs/commands-reference.md); per-helper behavior remains
in [scripts.md](docs/scripts.md).

## Security

- Never print, commit, or expose secrets. The PostToolUse hook masks tool output but does not authorize reading credentials.
- Destructive commands remain subject to native safeguards and explicit user authorization.
- The PermissionRequest hook is an observe-only, fail-open permission-prompt census; it never decides permissions.
- Never allowlist file-dumpers or bare tool namespaces. Raw shipping actions remain excluded from the user-level flow allowlist.
- `/flow:finish` and `/flow:deploy` run the deterministic security scan; CRITICAL findings block and HIGH findings warn.
- Branch-protection posture is declared in `.claude/branch-protection.json`; use its Makefile check/apply targets.
- The pending-retro reminder is opt-in and advisory.

The full hook, allowlist, branch-protection, scanning, and retired-runtime
contracts are maintained in [commands-reference.md](docs/commands-reference.md),
[scripts.md](docs/scripts.md), and `lib/security/README.md`.

## On-Demand Documentation

Load topic-specific skills from `docs/skills/`, or use
`/cpp:load-best-practices` and `/cpp:load-mcp-docs` for the full references.
Do not copy detailed manuals or command state machines into this file.

## Knowledge Lifecycle

Specifications are temporary coordination artifacts. Before a completed spec
is removed, durable facts must graduate to code and behavioral tests, schemas,
nearby intent comments, ADRs, domain glossaries, runbooks, maintained docs, or
linked issues. Run the verified mapping process in the
[canonical knowledge-lifecycle reference](docs/agents/knowledge-lifecycle.md);
independently valuable contracts are retained with a named owner.

## Secrets Management

Use the tiered credential interface documented by `/secrets:*` and
`lib/creds/`. Secret values never belong in responses, tracked files, command
arguments, or logs.

## Version

Current version: 7.4.0
