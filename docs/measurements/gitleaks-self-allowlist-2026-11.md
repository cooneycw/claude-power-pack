# What gitleaks lets the scanned change excuse - measured 2026-11-12

Read this before building anything that tries to stop a pull request from
allowlisting its own leak in the generated secret scan. It was designed once,
measured, and not built (issue #1712, Nit Store #864 seq 699).

## What was measured

- Binary: `gitleaks` v8.30.1, the version the generated pipelines pin
  (`zricethezav/gitleaks:v8.30.1`). Run directly on this host.
- Command under test: `gitleaks detect --source . --redact --no-banner`, plus
  the flag named in each row. Exit 1 is "findings", exit 0 is "none".
- Each case in its own scratch git repository. **The baseline was confirmed red
  (exit 1) before each case**; a case counts only if it moves a red baseline.
- Planted values: this repository's own known-bad control fixture
  (`controls/secret-scan/cases/bad-private-key`) and a synthetic
  GitHub-token-shaped string generated at random. No real credential.

## The first attempt was blind

The first run planted a value built from AWS's documentation example. gitleaks
allowlists that value itself, so the baseline exited 0 and every case after it
"passed". All of those results were discarded. The lesson is the usual one: the
zeros of a probe that cannot find anything look exactly like real zeros.

## Results

Three channels by which the change under scan can excuse its own finding.

| Channel | Baseline | With the channel | Flag tried | With the flag |
|---|---|---|---|---|
| 1. A `.gitleaks.toml` in the scanned tree that allowlists the file, with NO `--config` given | exit 1 | exit 0 | `--config <a file with no allowlist>` | exit 1: the flag restores the finding |
| 2. A `.gitleaksignore` in the scanned tree holding the finding's fingerprint, even UNTRACKED | exit 1 | exit 0 | `-i <an empty directory>`, and `-i <an empty file>` | exit 0 both times: **neither form switched it off**. Removing the file from the workspace restores exit 1. No other flag was tried, and gitleaks's source was not read, so "no flag exists" is not established |
| 3. An inline `gitleaks:allow` comment on the leaking line, in a fresh history | exit 1 | exit 0 | `--ignore-gitleaks-allow` | exit 1: the flag restores the finding |

One trap met on the way: in a repository whose EARLIER commit holds the secret
without the inline comment, adding the comment later does not clear the
finding, because the history scan still reads the earlier commit. Channel 3 was
therefore measured in a history where the only commit already carries the
comment.

Also measured, for the adoption path the documentation gives:

- A report written with `--report-path` and passed back with `--baseline-path`
  makes the run exit 0 while only the recorded findings exist, and exit 1 again
  once a further, unrecorded finding is committed.
- The same with the `Match` and `Secret` fields REMOVED from every entry of the
  baseline: still exit 0 on the recorded findings, still exit 1 on a new one.
- A baseline cut down to `RuleID`, `File`, `Commit`, `StartLine`, `Fingerprint`
  and `Description` does not match: exit 1 on the recorded findings.
- The report's entries also carry `Author`, `Email`, `Date` and `Message`.

**Is a `--redact` report safe to commit? Not established, and there is a
reason to think not.** The counter-model reviewer of this note reported a
`curl-auth-header` finding whose `Match` held a complete token-shaped value
despite `--redact`. One attempt here to reproduce that (a planted
GitHub-token-shaped value in a `curl -H "Authorization: Bearer ..."` line) did
NOT show it: the value appeared nowhere in the report. One failed reproduction
does not make the report safe: issue #1288 already records that `--redact`
cannot mask a secret inside another rule's match. The documentation therefore
says to strip `Match` and `Secret` and not to commit the raw report.

Not measured: other gitleaks versions; `gitleaks dir` and `gitleaks git` (the
newer subcommands); the GitHub Actions job's container form, which mounts the
repository read-only.

## Why a mechanism was not built

The plan had been: on a pull request, take the scanner's config from the base
branch. Written out as states, it does not hold.

- The base branch is usually not in the step's workspace. This repository's own
  pipeline clones at depth 1. Fetching the base inside the scanner's image needs
  network and, for a private repository, credentials in a third-party image.
- Channel 2 had no flag that worked in two tries. The ignore file would have to be replaced on disk, and
  the generated GitHub Actions job mounts the repository read-only.
- Channel 3 has a flag, and using it on pull requests turns every reviewed
  inline allow already in the repository into a failure on every pull request.
- On a same-repository pull request both providers are understood to run the
  pipeline DEFINITION from the pull request's head (not measured here; it is
  the same class `docs/agents/generated-ci-enrolment.md` concedes for the
  enrolment pin). A change that wants to hide a leak can then edit or delete
  the scan step. A guarantee that one more edited file removes is not a
  guarantee.

So "the generated secret scan cannot be weakened by the change under scan" is
not achievable inside the generated step. What the scan is, and the control
that does that job, are in `docs/skills/woodpecker-ci.md`.
