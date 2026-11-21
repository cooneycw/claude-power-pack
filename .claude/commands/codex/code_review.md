---
description: Codex reviews the code on the current branch (read-only) and returns structured findings - the cross-model pre-PR review stage
allowed-tools: Bash(~/.claude/scripts/codex-review-run.sh:*), Bash(scripts/codex-review-run.sh:*), Bash(cat:*), Bash(rm:*), Read
---

# Codex Code Review: Cross-Model Review of the Current Branch

Have OpenAI Codex review the code changes on the current branch as an
independent second model, and relay its findings in a structured format a caller
can act on. Codex runs **read-only**: it reads the diff and - where its sandbox
can start - the surrounding files; it cannot modify the tree, the credentials an
ordinary `gh`/`git`/`ssh` call discovers are withdrawn and any it cannot withdraw
are measured (`CODEX_REVIEW_LOCAL_CREDENTIALS`, issue #1459), and its network reach
is measured rather than promised (`CODEX_REVIEW_NETWORK`, issue #1450). Where the sandbox
cannot start (a container), the review is diff-only and says so
(`CODEX_REVIEW_SCOPE`, issue #1261). The review is advisory - Claude (or the user) triages
the findings and decides what to fix.

**The whole procedure is one helper, `scripts/codex-review-run.sh` (issue
#1847).** Run it bare and read its lines; never re-assemble its stages by hand.
The reviewer prompt lives there too, in one place.

**Which model reviews is host configuration, and this stage reports it rather
than asserting it.** No `-m` is passed, so read `CODEX_REVIEW_MODEL` from the
run (#1273). The requirement this stage exists to satisfy is a PROPERTY - **the
reviewing model must not be the implementing model** ([ADR
0007](../../../docs/decisions/0007-counter-model-review.md)) - and a name copied
out of a document is not evidence about it.

This is the reviewer counterpart to the other Codex commands:

- **`/codex:code_review`** (this) - Codex reviews code Claude wrote. Read-only, structured findings.
- **`/codex:ask`** - ask Codex a free-form read-only question.
- **`/codex:exec`** - hand Codex a coding task (writes files).
- **`/codex:auto`** - full issue lifecycle delegated to Codex, with Claude reviewing.
- **`/second-opinion:start`** - review via *other* external LLMs through the MCP server.

The primary consumer is `/flow:auto` Step 5 item 1, which runs this review at
the START of Finish - ahead of the quality gates, so a finding accepted from it
is linted and tested like any other change - and therefore before the PR exists.
It is equally usable standalone from any branch or worktree.

## Arguments

- `BASE` (optional): the base ref to diff against (e.g. `origin/main`). Default:
  `origin/<default-branch>` resolved from the repo, falling back to `origin/main`.
- `CONTEXT` (optional): extra reviewer context - typically the issue number or a
  one-line statement of intent, so Codex reviews against the intended change
  rather than guessing it.

## Instructions

When the user invokes `/codex:code_review [BASE] [CONTEXT]` (or a workflow calls
it as a stage), perform these steps:

### Step 1: Run the review

Invoke the helper bare, with literal values. It runs for minutes: run it in
the background (`/codex:ask`, "Long-running delegations").

```bash
~/.claude/scripts/codex-review-run.sh --base origin/main --context "issue #42: <title>" --transcript /path/to/transcript.md
```

On exit 127, use `scripts/codex-review-run.sh` in the CPP checkout and tell the
user to run **`/flow:repair`**. The `CODEX_REVIEW:` line is the verdict (stderr
for an early refusal); read it before the findings:

| Verdict | Exit | Meaning |
|---|---|---|
| `CODEX_REVIEW: ran` | 0 | The review ran; the transcript holds the markers, the banner and the findings |
| `CODEX_REVIEW: blocked (...)` | 1 | The patch is over Codex's input limit, or an enrolled repository has no committed checkpoint. Never a skip: split the change, or commit the bulk that needs no review separately, or commit the checkpoint |
| `CODEX_REVIEW: unavailable (...)` | 3 | No codex, no common ancestor with BASE (a shallow clone), an untracked-file listing or diff that failed, a refused `CODEX_REVIEW_SANDBOX`, no empty HOME for the reviewer, a failed `codex exec`, or an unwritable transcript. A caller degrades and continues; standalone, report it and stop |
| (usage) | 2 | A bad argument, or a transcript path unwritable or inside the checkout |

**An empty diff is still handed to the reviewer (issue #1015).** It parses as
`clean` and records an ordinary `ran` receipt: the ONLY condition that skips a
review is the inability to run codex.

The relay carries these markers, each a `NAME: value` line in the transcript:
`CODEX_REVIEW_BASE`, `CODEX_REVIEW_STREAM` (the retained `--json` stream; the
receipt writer derives the reviewer from it, so remove it only after the
receipt is written), `CODEX_REVIEW_MODEL`, `CODEX_REVIEW_SCOPE`,
`CODEX_REVIEW_NETWORK` and `CODEX_REVIEW_LOCAL_CREDENTIALS`.

Never add `--ephemeral` to the helper's `codex exec`: it writes no rollout, so no
receipt can be written (issue #1710).

### Step 2: Read what the review could see

**The review's SCOPE is measured, not assumed (issue #1261).** The helper probes
the sandbox (`codex sandbox`, no model call) by reading one tracked file inside it:

- `full` - the sandbox started and a repository file was readable inside it.
- `diff-only` - the probe failed; the reviewer is TOLD it cannot open files and
  the relay header says so. Report it; never present such a review as a full one.
- `unverified` - the probe could not be run (no `sandbox` subcommand on this
  codex, or no tracked file to read); the scope is unknown, which is not the
  same as full. The probe is a PRE-run measurement: it cannot see a read the
  reviewer attempts and is denied mid-run.

**The NETWORK fence is measured too, and the reviewer never holds a GitHub
credential (issue #1450).** A `--sandbox read-only` reviewer on a host whose
sandbox started once ran `gh api .../comments --method POST` and posted to an
issue as the owner. The cause was never confirmed, so each measure stands alone:

- `CODEX_REVIEW_NETWORK:` is measured before the run, against the GitHub API
  (the endpoint the incident reached). It is a measurement of one endpoint, not
  of the sandbox's whole egress policy, so the reviewer is told not to contact
  remote services on every verdict. **The verdict is this table and nothing
  else** (issue #1458). `tests/test_code_review_network_fence.py` is driven
  from it, so widening `blocked` means editing this table where a reviewer sees
  it. Both sandboxed probes go through one function with identical flags; only
  the argv after `--` differs.

  <!-- network-verdict-table -->
  | Probe outcome | `CODEX_REVIEW_NETWORK` |
  |---|---|
  | `CODEX_REVIEW_SANDBOX=danger-full-access` (no sandbox at all) | `open` |
  | no `codex sandbox` subcommand, or no `curl` | `unverified` |
  | the sandbox did not start (`-- true` failed, e.g. exit 101 with no bubblewrap) | `unverified` |
  | `curl` inside exited 0 | `open` |
  | `curl` inside exited 6, 7 or 28 (resolve, connect, timeout) and the same GET outside succeeded | `blocked` |
  | `curl` inside exited 6, 7 or 28 and the GET outside failed too | `unverified` |
  | `curl` inside exited anything else (127 absent, 35 TLS, a CLI usage error) | `unverified` |
  <!-- /network-verdict-table -->

- `-c 'approval_policy="never"'` is pinned, so no host configuration can
  approve a denied command into running unsandboxed.
- **Withdrawn (issues #1450, #1459)** - what an ordinary `gh`, `git` or `ssh`
  call would discover. The token variables are unset. `HOME` is an empty
  directory (with `CODEX_HOME` pinned to the real one), so gh's default config,
  git's global config and `~/.ssh` resolve to nothing. `GIT_CONFIG_NOSYSTEM`
  is set, and the global git config holds only the caller's `safe.directory`
  entries, so `url.*.insteadOf` tokens and helpers are gone.
  `credential.helper` and `http.extraheader` are reset for the repository's own
  config too. There is no SSH agent, `GIT_SSH_COMMAND=false`, no session bus
  for the gh keyring, and `GIT_ASKPASS=false` with no `SSH_ASKPASS`, so an
  inherited askpass program cannot answer git's credential prompt.
- **Not withdrawn, so measured.** A URL-scoped `http.<url>.extraheader` in the
  repository's own config is not reached by `http.extraheader=`; each one found
  is reset key by key and also reported. `CODEX_REVIEW_LOCAL_CREDENTIALS:
  present|absent|unknown` reports a credential embedded in the repository's OWN
  config, local and worktree scope with includes followed: userinfo in a remote
  URL, a `url.*.insteadOf` whose base carries one, or an `http[.<url>].extraheader`. Withdrawing those would mean editing the caller's
  repository. The check names KEYS only, never values; a key whose subsection
  is a URL prints it redacted (`url.<redacted>.insteadof`,
  `http.<redacted>.extraheader`). It does not refuse
  the review.
- **Not withdrawn, not measured:** a file the reviewer can read by ABSOLUTE
  path, such as the owner's real `~/.config/gh/hosts.yml`; and the owner's
  `~/.ssh` keys for a DIRECT `ssh` call, because OpenSSH takes the home
  directory from the password database rather than `$HOME`.
  `GIT_SSH_COMMAND=false` stops only git's own ssh transport. That
  is why `open` is reported as `open` and never as read-only.

A caller that knows codex's sandbox cannot start where it runs may supply
`CODEX_REVIEW_SANDBOX=danger-full-access` as data - the #1285 contract shape
(Kyle, for the containers it starts). Unset keeps `read-only`. Any other value is
refused, never defaulted. This command never chooses the escalation itself: it
would hand a reviewer that is meant to be read-only write access to the tree.
With `danger-full-access` there is no sandbox to probe and the scope is `full`.

### Step 3: Relay the findings

Show the transcript's banner and findings.
Present the findings **attributed to Codex** - never silently merged into your
own assessment. Then, standalone, add your own labeled triage: for each finding,
agree (worth fixing), disagree (with the reason), or defer (real but out of
scope). Do not apply fixes in this command - it is read-only by design; fixing
is the caller's decision (`/flow:auto` Step 5 item 1c does exactly that).
A finding the reviewer marks as a proposed scope expansion is still a finding:
whether it becomes a requirement, or ends as an accepted limitation, is decided
under [the issue contract](../../../docs/agents/issue-contract.md#supported-scope-and-proportional-prevention),
by the approver.

State the `CODEX_REVIEW_SCOPE`, `CODEX_REVIEW_NETWORK` and
`CODEX_REVIEW_LOCAL_CREDENTIALS` with the findings.
**Label `CODEX_REVIEW_NETWORK` as a sandbox-probe proxy, not a direct
measurement of the review itself (issue #1494).** The probe runs through
`codex sandbox`; the reviewer that actually produced the findings runs through
`codex exec`. The two invocation paths are not asserted to apply
identical network fencing, so this verdict characterizes the PROBE's
reachability, which stands in for the reviewer's rather than measuring it
directly - say so when relaying the verdict.
An `open` or `unverified` network is never described as read-only or
network-fenced: say which it was, and check the target repository for anything
the reviewer posted itself (issue #1450). A caller recording a receipt passes
`--network` and `--local-credentials` exactly as it passes `--scope`. A `diff-only` or `unverified`
review is still a review, but say which it was: good findings are not evidence
that the reviewer could read the surrounding code (issue #1261). A caller
recording a receipt passes this same marker as `--scope` to
`counter-model-receipt.py write` (issue #1400) - the writer re-measures it
against `$STREAM` and can only downgrade a claimed `full`, never upgrade a
`diff-only` or `unverified` one, so passing the marker as printed loses
nothing.

On `unavailable (codex exec exited N)`, report the failure honestly and do not
fabricate findings from whatever the transcript holds.

### Step 4: Route Deferred Findings to the Nit Store

A finding you triaged **defer** - real, but out of scope for this branch - is a
supplemental finding. This command does not fix it, and the triage line is not a
record: it scrolls out of the caller's context and is gone. Do not widen the
change to fix it, and do not drop it. Record it.

Resolve the repository's nit store with the shared resolver, bare:

```bash
~/.claude/scripts/nit-store-resolve.sh
```

It is the ONLY copy of the repository-to-issue map (#1272, #1273). It reads the
repository from `origin`, never from the directory name, because this step runs
from a per-issue worktree whose basename is not the repository. It answers a
number only after GitHub confirms that issue is OPEN and titled exactly "Nit Store".
Act on `NIT_STORE_STATUS`:

- `ok` - post to the number it printed as `NIT_STORE=`, IN the repository it
  printed as `NIT_STORE_REPO=`:
  `gh issue comment <NIT_STORE> --repo <NIT_STORE_REPO> --body "<one finding>"`.
  The `--repo` is not optional: without it gh picks its own default (a fork's
  upstream, or `GH_REPO`), and the verified number would be posted somewhere
  that was never checked. When
  `NIT_STORE_SOURCE=search` (an unmapped repository, resolved by exact title),
  say so in the closing report.
- `none` (exit 1) - GitHub was asked and there is no open Nit Store, or the
  mapped one is closed or retitled. If the repository has no nit store, file the finding as a normal issue instead.
- `unknown` (exit 3) - GitHub could not be asked, or the answer was ambiguous.
  Post nowhere. Say in the closing report that the finding is unrouted and
  carry it there verbatim, because `unknown` is not `none`.

On exit 127 the helper is not installed: fall back to `scripts/nit-store-resolve.sh`
in the CPP checkout (it may prompt once), and tell the user to run
**`/flow:repair`**.

- **One finding per comment.** State the file and line (or the command), what is
  wrong, why it matters, and which issue or PR you were reviewing when you found
  it. The comment is the whole record; it is read later without your context.
- **Attribute it.** The finding is Codex's; say so in the comment, exactly as the
  relay above does. A later reader weighs a cross-model finding differently from
  your own.
- **The store is an inbox, not a backlog.** A comment is a disposition, not a fix.
- **It is not a place to hide a defect that warrants its own ticket now.** A live
  correctness, security, or data-loss finding gets its own issue, whatever its
  scope - `defer` is a scope judgement, not a severity one.
- **Name what you stored, with the comment link, in your closing report.**

A review with nothing deferred stores nothing. That is an ordinary outcome, not a
gap to fill.

## Notes

- The review prompt in `scripts/codex-review-run.sh` carries the two detector questions inline rather than
  linking them, because the reviewing model runs `--sandbox read-only` against a
  diff and cannot be relied on to go and read a repository document. The
  canonical statement, with the instance index and the test shapes a finding
  should ask for, is
  [the detector contracts](../../../docs/agents/detector-contracts.md); read it
  when triaging a detector finding in Step 3. These are inline
  likewise: [lanes](../../../docs/agents/lanes.md),
  [readers](../../../docs/agents/changed-output-readers.md).
- Uses the user's **Codex account** (real quota/billing per call). One review
  pass plus at most one re-review is the intended cadence - never loop.
- Read-only sandbox: Codex cannot write to the tree. Whether it can reach the
  network is MEASURED, not promised: read `CODEX_REVIEW_NETWORK` (issue #1450).
  Either way the credentials an ordinary `gh`/`git`/`ssh` call would discover
  are withdrawn, those in the repository's own config are measured
  (`CODEX_REVIEW_LOCAL_CREDENTIALS`), a file readable by absolute path is
  still readable, and escalation out of the sandbox is pinned off. A caller-supplied
  `CODEX_REVIEW_SANDBOX=danger-full-access` (issue #1261), for a placement where
  the sandbox cannot start, has no mechanical write or network fence and always
  reports `open`. Codex always reaches OpenAI to run the model itself.
- `/flow:auto` Step 5 item 1c parses findings via
  `scripts/counter-model-receipt.py parse`: preserve `## Findings`, the clean
  `None - no defects found.` sentinel, and the prompt format.
- Findings carry `- Kind:`; missing/unknown kinds read `unstated`.
  See the [parser reference](../../../docs/scripts/counter-model-receipt.md).
- The `## Red cases` section is part of this command's own contract (issue
  #1030), not something a caller has to ask for separately.
  `None - no instrument changed.` is the explicit
  empty case, so an absent section stays distinguishable from a considered
  zero.
- For a review by non-OpenAI models, use `/second-opinion:start` instead.

Receipt-bound reviews follow [the runtime evidence contract](../../../docs/agents/counter-model-evidence.md). Binding names the recorded artifact, not the thoroughness of review. Pass `CODEX_REVIEW_BASE` as `--review-base` when recording the receipt.
