# ADR 0012: The CI provider is a recorded per-project choice; CI capability is a recorded per-host fact

- Status: Accepted (owner rulings, 2026-10-30)
- Date: 2026-10-30
- Issue: #1612 (tracking), children #1607, #1608, #1609, #1610, #1611
- Related: #1604 (GitHub Actions as a first-class provider; items 1-5 landed in
  #1606), ADR 0004 (CPP's own branch-protection posture), ADR 0008 (the
  negative-control bound every new check here falls under)
- Architecture and plan: [ci-provider-chain.md](../architecture/ci-provider-chain.md)

## Context

CPP drives CI for every repository it manages: it generates pipelines
(`/cicd:pipeline`, `/cicd:woodpecker`), waits on them before merging
(`/flow:merge`, `/flow:auto` Step 7), verifies main after merging (Step 8),
watches wave merges (`flow-pr-watch.sh`) and enforces counter-model enrolment
as a CI step. Until now every one of those steps assumed self-hosted
Woodpecker, because every repository CPP drove used it.

That premise ended on 2026-10-30, when cooneycw/kyle#1475 ruled that the public
kyle candidate uses GitHub Actions while private kyle and CPP stay on
Woodpecker. Some projects will now choose Woodpecker and others GitHub Actions,
so "which provider" became a fact that differs per project.

An audit at `46d99956` found that fact recorded nowhere anyone reads:

- **Nothing asks.** `/project:init` asks about destination, framework and
  visibility, never CI. The `cicd.yml` template leaves `pipeline:` commented
  out, and `lib/cicd/config.py` defaults a missing provider to `github-actions`
  silently. CPP's own config therefore describes GitHub Actions while CPP runs
  Woodpecker.
- **Nothing derives.** No step turns a provider into the status checks branch
  protection should require. The `BranchProtection` model in
  `lib/cicd/config.py` is unused.
- **Every consumer infers for itself**, each differently: `flow-ci-status.sh`
  tries Woodpecker first and lets whichever lane answers decide;
  `flow-pr-watch.sh` hardcodes `ci/woodpecker/pr/woodpecker`; enrolment exists
  only as a step in CPP's own `.woodpecker.yml`; recovery text says "kill it on
  the Woodpecker server" for every repository.
- **Host capability is unchecked.** `/cpp:init` never confirms `gh auth`, never
  mentions `woodpecker-cli` or the Woodpecker token, and records nothing, so a
  flow run learns which providers this machine can reach only by failing.
  Meanwhile `/cpp:init` Tier 4 writes project files (Makefile, `cicd.yml`, a
  pipeline, containers) into whatever directory it runs from, and offers only
  GitHub Actions.

## Decision

1. **The provider is a per-project choice, made at `/project:init`, and
   recorded once** in the project's `.claude/cicd.yml` as `pipeline.provider`:
   `woodpecker`, `github-actions` or `both`. An existing repository records it
   through `/cicd:init`. That field is the single source; pipeline files and
   branch-protection checks are derived from it, never the other way round.

2. **A missing provider fails closed.** Absent means `unknown`, never a default.
   Generation refuses on `unknown`, and every flow consumer that needs the
   provider stops on `unknown` and names how to record one, rather than
   guessing. Owner ruling: the silent default is how CPP's own record came to
   name the wrong provider.

3. **`/cpp:init` is host setup; Tier 4 becomes host-only CI checks.** It checks
   whether this machine can use each provider (GitHub Actions: `gh` installed
   and authenticated; Woodpecker: `woodpecker-cli` authenticated and the API
   token resolvable), records the verdicts, and writes nothing into any
   project. Its former project-generation steps move to `/project:init` (new
   projects) and `/cicd:init` (existing repositories), and Tier 4 hands off to
   them in one line.

4. **The host record lives at the workspace root** - the directory holding the
   projects, here `~/Projects` - as `<root>/.claude/cpp-host.json`. `/cpp:init`
   asks for the root once, defaulting to the parent of the CPP checkout, and
   consumers find the record by walking up from a repository. It holds
   verdicts, versions and timestamps, never a secret. A provider that could not
   be checked is `unknown`, never `ready`.

5. **Consumers read the records; they do not infer.** CI lane selection,
   failing-test extraction, recovery text and preflight all key on the project's
   recorded provider, and check it against the host record before a run commits
   to waiting. Probing for a provider remains only as a fallback that announces
   itself as one.

## Consequences

- One reader (`python -m lib.cicd provider`) is the only parser of the record;
  shell helpers call it instead of each reading YAML. A test enforces that.
- `/flow:doctor` gains a cross-check of the four signals that can now disagree:
  the recorded provider, the pipeline files, the required checks and host
  capability. CPP's own repository is its first red case.
- Each new or widened check is an instrument under ADR 0008 and ships with a
  committed negative control: the reader's `unknown`, generation's refusal, lane
  selection, the host verdicts and every doctor line.
- `both` is a real choice, not a migration state: a `both` project's verdict is
  red when either provider is red.
- `/cpp:init` Tier 4 no longer writes into the repository it runs from. Users
  who relied on it to scaffold a project are pointed to `/project:init` or
  `/cicd:init` instead. This decision covers Tier 4's CI setup only: other
  tiers may still write project files (Tier 3's optional browser desk pool
  creates `.claude/playwright-pool.json`), and moving those is outside it.
- Required status checks are derived only from checks the PR event emits on a
  PR head. A Woodpecker push context runs only on `main`, so requiring it would
  hold every PR open; it stays post-merge verification, as ADR 0004 already
  sets for CPP.

## Open questions (owner)

- **Fork PRs and counter-model enrolment on public repositories** (#1604 item 8,
  carried into #1610). A fork PR carries no receipt, so an enforced enrolment
  step fails every outside contributor.
- **One host record per workspace root, or one per machine** (#1609). The
  default is per root; the two only differ on a machine with several roots.

## Rejected alternatives

- **Infer the provider from which pipeline file exists.** A file can exist for
  a provider the project has retired, or be absent while it is being written;
  inference is how the consumers disagree today.
- **Infer it from branch-protection contexts** (what `flow-ci-status.sh` does
  now). Required checks are a consequence of the choice, not the choice, and
  they are unreadable without `gh` authentication.
- **Keep project generation in `/cpp:init` and add a provider prompt.** It
  would still write into whatever directory the user happened to run it from,
  and would leave two divergent generators of `cicd.yml`.
