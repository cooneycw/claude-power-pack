# Generated CI counter-model enrolment

The main application templates from `/cicd:pipeline` include a
`counter-model-enrolment` job for GitHub Actions and Woodpecker. It checks the
consumer checkout's review receipts using CPP's trusted enrolment-only helper.
It does not install or run the consumer's dependencies.

Infrastructure generators retain their path filters and are excluded from this
change. Infrastructure-only repositories are not enrolled by these jobs.

This is a standing exclusion, not an open gap (declined in #1712): an infra
workflow runs only when its paths change, and a path-filtered check cannot be
a required check - a pull request that does not touch those paths would wait
on it forever. Enrolling infrastructure-only repositories would need a
separate, unfiltered workflow; nothing generates one. First recorded as
[Nit Store #864 seq 686](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6728623706),
a store that has since been closed.

## Actions deploy migration

**AWS/OIDC consumers must migrate IAM trust before their first regenerated
deploy.** The dedicated job's `environment: production` changes its exact OIDC
subject from `repo:O/R:ref:refs/heads/main` to
`repo:O/R:environment:production` (`O/R` is the consumer slug). Configure the
GitHub production environment to allow `main` only, then update the role's exact
subject condition while retaining the audience check. See the
[OIDC migration steps](../skills/cicd-verification.md#actions-deploy-oidc-migration).
The default `contents: read` also applies to platform deploys; tag pushes and
release creation need an explicit write grant on the dedicated deploy job.

## Immutable checker source

The single revision source is `.claude/cpp-install.json`'s `cpp_revision`, which
`/cpp:init` records from the installed CPP checkout. Configuration loading reads
that snapshot into derived metadata; a `cpp_revision` entry in `cicd.yml` cannot
override it. The rendered job embeds the full 40-character revision. A missing,
invalid or unreadable snapshot produces an UNKNOWN job with an `/cpp:init`
remedy, rather than following a branch or tag.

The job fetches that exact object from the official CPP repository into a
temporary checkout, verifies its resolved HEAD equals the pin, and invokes
`scripts/flow-finish-gate.sh --enrolment-only --branch <PR-source-branch>` from
there while the working directory remains the consumer checkout. A changed
consumer HEAD, failed fetch, incomplete bootstrap or unreadable checker result
is UNKNOWN (exit 5): retry the pipeline. It never becomes unenrolled or green.

Update CPP, refresh `/cpp:init`, regenerate the pipeline, and review the resulting
pin change in a PR. Release names are not executable references. In-memory API
configurations without loaded install metadata also generate UNKNOWN jobs.

## PR policy and history

A same-repository PR without a valid receipt fails (exit 1). A positively
identified fork PR warns and proceeds (exit 0). Missing, malformed or
unavailable fork evidence is UNKNOWN (exit 5), never a fork warning. Branch
names do not establish fork status.

Actions uses its event's head/base repository identities, `github.head_ref`,
and a full-history checkout of the PR head (`fetch-depth: 0`) with credential
persistence disabled. The checkout action is pinned to an immutable commit SHA. Its push-side
enrolment job is not applicable and does not evaluate receipts. Enabling the PR
trigger does not enable main-only application targets on PRs.

Woodpecker uses `CI_PIPELINE_EVENT`, `CI_COMMIT_PULL_REQUEST`, `CI_REPO`, and the
source branch to read GitHub's PR metadata. Head/base identities, source branch
and SHA must match the checkout. API errors, private metadata without readable
credentials and unsupported forges remain UNKNOWN. An optional `GH_TOKEN`
environment value can authenticate that read; the header travels through stdin.
No new secret binding is required by the generated template. Woodpecker's clone
has depth 0 and disables synthetic PR merges to preserve head attribution.

The Woodpecker step installs its own shell/git/HTTP tools; installation failures
are UNKNOWN. Enrolment is independent of application checks; explicit dependency
edges retain their secret-scan, build, security, smoke and deploy ordering.
Runtime dollars in its emitted command are escaped for provider
substitution. See the official [environment](https://woodpecker-ci.org/docs/usage/environment)
and [workflow syntax](https://woodpecker-ci.org/docs/usage/workflow-syntax)
documentation for the provider fields and escaping contract.

## Evidence boundaries

On `pull_request`, the PR's own workflow runs, so a same-repository PR can edit the pin or the job.

`controls/pinned-enrolment` executes the actual emitted shell with owned git and
HTTP stubs, using Actions' `bash -eo pipefail` behavior for its cases. Committed
bad inputs cover moving or short refs, SHA mismatch, fetch/bootstrap errors,
missing same-repository receipts on both providers, and unreadable metadata.
Cases pin UNKNOWN to exit 5 and missing receipts to exit 1. Valid receipts and
known forks are positive controls. The synthetic unenforced anchor misses every
refusal; the separate `pinned-enrolment-fork-evidence` and
`pinned-enrolment-exit-class` batteries prove near-miss anchors cannot hide absent
fork evidence or collapse UNKNOWN into FAIL. These controls do not claim live
provider coverage. Unit tests
also fetch a local trusted CPP fixture, run the real enrolment-only helper and
verify a receipt at an ancestor of the consumer HEAD.
