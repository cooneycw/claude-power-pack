# ADR 0012: The CI provider is a recorded per-project choice; CI capability is a recorded per-host fact

- Status: Accepted (owner rulings, 2026-10-30)
- Date: 2026-10-30
- Issue: #1612 (tracking), children #1607, #1608, #1609, #1610, #1611
- Related: #1604 (GitHub Actions as a first-class provider; items 1-5 landed in
  #1606), ADR 0004 (CPP's own branch-protection posture), ADR 0008 (the
  negative-control bound every new check here falls under)
- Architecture and plan: [ci-provider-chain.md](../architecture/ci-provider-chain.md)

## The owner's choices, in plain language

CI (continuous integration) is the robot that runs a project's tests every time
someone proposes a change. CPP works with two such robots today: Woodpecker,
which runs on our own machines, and GitHub Actions, which runs in GitHub's
cloud. More may come later.

1. **Each project says which robots it uses, and writes that down.** When a
   project is created (`/project:init`), it is asked "which CI do you use?" and
   may answer Woodpecker, GitHub Actions, both, or another one added later. The
   answer is saved in the project's own settings file, so every later step reads
   it instead of guessing.
2. **No answer means "stop and ask", not "assume".** If a project never wrote
   its answer down, CPP stops and says how to record it. Today it silently
   assumes GitHub Actions, which is how CPP's own settings came to name the
   wrong robot.
3. **Setting up a machine only checks the machine.** `/cpp:init` installs CPP on
   a computer. Its CI step (Tier 4) now only asks "which robots can THIS
   computer talk to?" - is GitHub logged in, does the Woodpecker key work - and
   writes the answers down. It is not a choice between robots: a machine may be
   able to reach one, several, or none. It no longer creates files inside
   whatever project folder it happened to be run from.
4. **The machine's answers live beside the projects.** They are saved once in
   the folder that holds all the projects (here `~/Projects`), so every project
   on the machine can read them.

Two choices are still open:

- **Outside contributors on public projects.** Every change here is reviewed by
  a second AI model, and the review leaves a receipt that CI checks for. Someone
  outside the team who proposes a change from their own copy of the project
  (a "fork") cannot produce that receipt. Should CI refuse their change, let it
  through without one, or only warn?
- **One machine record or several.** If one computer ever holds two separate
  folders of projects, should each folder keep its own copy of the machine's
  answers, or should there be one record for the whole computer? They would
  normally say the same thing; the default is one per folder.

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

1. **The providers are a per-project choice, made at `/project:init`, and
   recorded once** in the project's `.claude/cicd.yml` as a LIST,
   `pipeline.providers`, of one or more known provider names - today
   `woodpecker` and `github-actions`. An existing repository records it
   through `/cicd:init`. That field is the single source; pipeline files and
   branch-protection checks are derived from it, never the other way round.

   **The set is open, not binary** (owner clarification, 2026-10-30). A project
   may use either provider or both, and further providers may be added later.
   So the record is a list, not an enum with a combined `both` value that would
   need a new member for every combination. Each provider is one entry in a
   registry naming its pipeline generator, its required-check derivation, its
   CI lane and its host check; adding a provider adds a registry entry, and no
   consumer special-cases a combination. The legacy scalar `pipeline.provider`
   stays readable: `woodpecker` and `github-actions` map to a one-entry list,
   `both` to both names. A name not in the registry is refused, never ignored.

2. **A missing provider fails closed.** Absent means `unknown`, never a default.
   Generation refuses on `unknown`, and every flow consumer that needs the
   provider stops on `unknown` and names how to record one, rather than
   guessing. Owner ruling: the silent default is how CPP's own record came to
   name the wrong provider.

3. **`/cpp:init` is host setup; Tier 4 becomes host-only CI checks.** It checks
   EVERY registered provider independently (GitHub Actions: `gh` installed and
   authenticated; Woodpecker: `woodpecker-cli` authenticated and the API token
   resolvable; a future provider: its own registry check), records one verdict
   per provider, and writes nothing into any project. This is not a selection:
   a host can be ready for none, one or several providers at once, and the
   record says which. Its former project-generation steps move to `/project:init` (new
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
- A multi-provider project is a real configuration, not a migration state: its
  CI verdict is red when any listed provider is red, and running only when none
  is red and any is still running.
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
