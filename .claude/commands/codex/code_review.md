---
description: Codex reviews the code on the current branch (read-only) and returns structured findings - the cross-model pre-PR review stage
allowed-tools: Bash(codex:*), Bash(git:*), Bash(mktemp:*), Bash(cat:*), Bash(rm:*), Bash(test:*), Bash(wc:*), Bash(command -v codex), Read
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

**Which model reviews is host configuration, and this stage reports it rather
than asserting it.** Step 3 passes no `-m`, so the model comes from the layered
Codex configuration, and it changes: this document once named one model inline
and was wrong within days, and a later measurement named another. So no model
name is given here to copy - read `CODEX_REVIEW_MODEL` from the run (#1273).

The requirement this stage exists to satisfy is a PROPERTY - **the reviewing
model must not be the implementing model** ([ADR
0007](../../../docs/decisions/0007-counter-model-review.md)) - and a name copied
out of a document is not evidence about it.

**Capture the model OUTSIDE the findings transcript.** Do not ask the reviewer to
put its model in the report: Step 3's prompt fixes the heading as exactly
`## Findings`, and `counter-model-receipt.py` keys on that spelling, so a model
name added inside the transcript turns a successful review into `unparseable` -
recorded as `skipped / reviewer-unavailable`, a review that happened and was
counted as absent. Add `--json` alongside `--output-last-message` (they coexist),
take the thread id from the stream, and read that thread's rollout:

```bash
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
CM_RECEIPT="${CM_RECEIPT:-$HOME/.claude/scripts/counter-model-receipt.py}"
[ -f "$CM_RECEIPT" ] || CM_RECEIPT="${CLAUDE_PLUGIN_ROOT}/scripts/counter-model-receipt.py"
# FAIL CLOSED, and REFUSE rather than guess on an ambiguous match (issue
# #1400). This used to be inline `find ... -name "*$THREAD.jsonl" | head -1`
# then `grep -o '"model":"[^"]*"' | head -1` - the exact whole-file,
# first-match bug #1269 fixed inside the script, reintroduced here because
# this document never called back into the fix. `rollout-model` is now the
# one implementation both this document and `/codex:ask` call, so a second
# fix is never needed for a third copy.
if [ -f "$CM_RECEIPT" ]; then
    REVIEW_MODEL=$(python3 "$CM_RECEIPT" rollout-model \
        --exec-log "$STREAM" --sessions-dir "$CODEX_DIR/sessions" 2>/dev/null) \
        || REVIEW_MODEL=""
else
    REVIEW_MODEL=""
fi
```

`$STREAM` is the `--json` stream captured in Step 3; an empty `REVIEW_MODEL`
means the model could not be established, and the banner and any receipt must
say so rather than name one.

Anchor on the thread id, never on the newest rollout: with concurrent sessions
the newest belongs to whoever finished last, and on a skipped review it belongs
to an unrelated run - which would name a reviewer that never ran. Stamp
`$REVIEW_MODEL` in the Step 4 relay banner and pass it as `codex/$REVIEW_MODEL`
to any downstream receipt. When no review ran, there is no reviewer: leave the
field to the skip path rather than filling it from a neighbouring session.

This is the reviewer counterpart to the other Codex commands:

- **`/codex:code_review`** (this) - Codex reviews code Claude wrote. Read-only, structured findings.
- **`/codex:ask`** - ask Codex a free-form read-only question.
- **`/codex:exec`** - hand Codex a coding task (writes files).
- **`/codex:auto`** - full issue lifecycle delegated to Codex, with Claude reviewing.
- **`/second-opinion:start`** - review via *other* external LLMs through the MCP server.

The primary consumer is `/flow:auto` Step 6 item 1, which runs this review at
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

### Step 1: Preflight

```bash
if ! command -v codex >/dev/null 2>&1; then
    echo "CODEX_REVIEW: unavailable (Codex CLI not found - npm install -g @openai/codex; codex login)"
    exit 3
fi
codex --version
```

Exit 3 is the "unavailable" contract: a calling workflow treats it as
degrade-and-continue (warn, skip the review stage), never as a hard failure of
the run. Standalone, report it to the user and stop here.

### Step 2: Collect the diff

Resolve the base and capture what the review is about. Include committed and
uncommitted work - pre-PR review runs before the Finish-stage commit exists:

```bash
BASE="${BASE:-origin/$(git remote show origin 2>/dev/null | grep -oP 'HEAD branch: \K\S+' || echo main)}"
git fetch origin --quiet || true

DIFF_FILE=$(mktemp /tmp/codex-review-diff.XXXXXX.patch)
# Four refusal paths below (no common ancestor, no diff vs BASE, an unreadable
# or disallowed sandbox mode, a HOME that cannot be created) used to `exit 3`
# without removing $DIFF_FILE - only the two LATER refusals in the next block
# did (issue #1494). A trap covers every exit from THIS point in this shell,
# including ones added later, rather than four hand-matched `rm -f` calls that
# the next refusal added here would silently miss again.
trap 'rm -f "$DIFF_FILE"' EXIT
# MERGE BASE, not the moving tip (issue #927, nit-stored S1). `$BASE` is
# refreshed by the `git fetch` two lines up, so it is the tip AT REVIEW TIME,
# not the point this branch was cut. Two-dot `git diff origin/main` therefore
# compares the working tree against a tip that may carry commits this branch
# never had - and a sibling PR's ADDITIONS render as this author's DELETIONS.
# Measured: a reviewer handed such a diff returned three confident findings
# against a file the author had never touched, all of them accurate
# descriptions of reverting someone else's merged work.
#
# THIS CORRECTS THE REVIEWER'S RANGE. It cannot see a commit whose TREE
# PREDATES ITS PARENT - for that, compare `git diff --name-only origin/main`
# to your own file set before pushing. Do not read agreement between diff
# forms as confirmation that no revert is present; where the merge base IS
# origin/main, every form agrees and all of them are wrong together.
# A FAILED RESOLUTION MUST NOT BECOME AN EMPTY CLEAN REVIEW. In a shallow
# checkout, HEAD and $BASE can both be valid and share no locally discoverable
# ancestor: `git merge-base` then fails, MERGE_BASE is empty, both diffs fail,
# and $DIFF_FILE is left EMPTY - which the next step reads as "nothing to
# review" and exits 0. A review that never ran would report clean, which is
# this command's own failure class pointed at its own input.
if ! MERGE_BASE="$(git merge-base HEAD "$BASE")" || [ -z "$MERGE_BASE" ]; then
    echo "CODEX_REVIEW: unavailable (no common ancestor between HEAD and $BASE -" >&2
    echo "  a shallow clone cannot be reviewed against a base it cannot reach." >&2
    echo "  Deepen with: git fetch --unshallow, then re-run.)" >&2
    exit 3
fi
# A BRAND-NEW FILE IS INVISIBLE TO `git diff <ref>` UNTIL SOMETHING STAGES IT
# (issue #1030). `git diff` compares the ref's tree to the INDEX/working tree
# for paths the index already knows about; an untracked path has no entry to
# compare, so it is skipped entirely rather than shown as an addition. A
# change whose whole content is one or more new files therefore hands the
# reviewer an diff that omits the change - "no findings" then means nothing.
#
# `git add -N` (--intent-to-add) marks each untracked, non-ignored path in
# the index without staging its CONTENT, which is enough for `git diff <ref>`
# to treat it as a real addition. It is deliberately not undone afterward: the
# markers are inert until something actually stages content over them, and
# this command's own caller (`/flow:auto` Step 6) already runs `git add -A`
# before its commit, which supersedes them harmlessly - a blind `git reset`
# here would risk discarding unrelated work staged earlier in that same run.
#
# The count doubles as a membership floor, not just transparency: `git add -N .`
# marks EVERY untracked non-ignored path from the worktree root, so a count
# larger than what this change actually added means the review is about to
# see files nobody intended to include - worth surfacing before the review
# runs, not after.
#
# BOTH commands run from the WORKTREE ROOT explicitly, not the caller's cwd
# (codex review, Codex-flagged): `git add -N .` and `git ls-files` are
# relative to cwd, so invoked from a subdirectory they would only mark
# untracked files beneath it - a new file elsewhere in the worktree would
# stay invisible to the diff exactly as before this fix, while the count
# would silently omit it too.
#
# A FAILED intent-to-add MUST NOT become a review that reports itself
# complete (codex review, Codex-flagged): swallowing the exit status left a
# locked or unwritable index looking identical to success, so new files
# stayed invisible while the count message still claimed they were included.
#
# ENUMERATED PATHS ONLY, never a bare `git add -N .` (codex review,
# Codex-flagged, re-review): `-N .` walks the whole pathspec, which includes
# tracked files DELETED from the working tree but not yet `git rm`'d - and
# `add -N` stages that deletion into the index, not merely a placeholder for
# it. A deletion nobody asked this review to stage would then ride along into
# whatever the caller commits next. Untracked additions are the only thing
# this step needs to fix (a tracked deletion is already visible in a plain
# `git diff <ref>` with no staging at all), so mark exactly those paths -
# NUL-delimited, to survive a filename containing a space or newline.
#
# A FAILED ENUMERATION MUST NOT BECOME ZERO UNTRACKED FILES (issue #1261).
# `mapfile < <(git ls-files ...)` cannot see the exit status of the process
# substitution, so a failed `ls-files` came back as an empty array - identical
# to "no new files" - and the review ran over a diff missing every new file
# while the count line below read like a real zero. Enumerate into a file in
# the git dir, CHECK that command, then read the file (the #1220 shape).
GIT_ROOT="$(git rev-parse --show-toplevel)"
UNTRACKED_LIST="$(git -C "$GIT_ROOT" rev-parse --absolute-git-dir)/codex-review-untracked.$$"
if ! git -C "$GIT_ROOT" ls-files --others --exclude-standard -z > "$UNTRACKED_LIST"; then
    rm -f "$UNTRACKED_LIST"
    echo "CODEX_REVIEW: unavailable (could not enumerate untracked files -" >&2
    echo "  a failed listing would read as zero new files, and the review would" >&2
    echo "  report itself complete over a diff missing them.)" >&2
    exit 3
fi
mapfile -d '' -t UNTRACKED_FILES < "$UNTRACKED_LIST"
rm -f "$UNTRACKED_LIST"
UNTRACKED_COUNT=${#UNTRACKED_FILES[@]}
if [ "$UNTRACKED_COUNT" -gt 0 ] && ! git -C "$GIT_ROOT" add -N -- "${UNTRACKED_FILES[@]}"; then
    echo "CODEX_REVIEW: unavailable (could not stage untracked files as intent-to-add -" >&2
    echo "  new files would be invisible to the review, which would then report itself" >&2
    echo "  complete over an incomplete diff. Check for a locked or unwritable index.)" >&2
    exit 3
fi
if ! git diff "$MERGE_BASE" > "$DIFF_FILE"; then
    echo "CODEX_REVIEW: unavailable (diff against $MERGE_BASE failed)" >&2
    exit 3
fi
# Receipt-bound reviews consume a committed artifact, using the SAME canonical
# byte producer the writer independently recomputes. Standalone non-enrolled
# reviews retain the working-tree view above, but cannot claim schema-5 binding.
if [ -d "$GIT_ROOT/docs/measurements/counter-model" ]; then
    CM_RECEIPT="${CM_RECEIPT:-$HOME/.claude/scripts/counter-model-receipt.py}"
    [ -f "$CM_RECEIPT" ] || CM_RECEIPT="${CLAUDE_PLUGIN_ROOT}/scripts/counter-model-receipt.py"
    if [ ! -f "$CM_RECEIPT" ] || ! python3 "$CM_RECEIPT" review-patch --base "$BASE" > "$DIFF_FILE"; then
        echo "CODEX_REVIEW: blocked (commit the implementation checkpoint, then produce the canonical review patch)" >&2
        exit 1
    fi
fi
git diff --stat "$MERGE_BASE"
wc -l "$DIFF_FILE"
echo "Untracked files included in this diff: $UNTRACKED_COUNT (a count higher than expected means files nobody intended to include are about to be reviewed)"
# Reached the end without an early exit: $DIFF_FILE must survive into the
# later blocks that read and remove it themselves (line ~487, ~560+6).
# Disarm the trap - it exists to catch an EARLY exit in THIS block, never
# the ordinary end of it.
trap - EXIT
```

**An empty diff is still handed to the reviewer (issue #1015).** This used to
stop here - exit 0, "nothing to review vs $BASE" - and that early exit produced
no findings report at all. A caller parsing the transcript therefore read
`unparseable` and recorded the run as `skipped / reviewer-unavailable`: a skip
whose reason names an inability that did not happen. The reviewer was available
and was never asked.

So do not stop. Pass the empty diff to Step 3 and let the reviewer answer in the
prescribed words, which parses as `clean` and records an ordinary `ran` receipt.
Add to the prompt's context line that the diff is empty, so the reviewer is not
left guessing why it received nothing.

The rule this serves is `/flow:auto`'s: the ONLY condition that skips a review
is the inability to run codex. "There was nothing to look at" is not one, and a
silent exit here is how it would have become one anyway.

For very large diffs (thousands of lines), note it and proceed - Codex can also
open files itself in the read-only sandbox - but name the most important files in
the prompt so the review focuses where the risk is.

### Step 3: Run the review

Pipe the diff on stdin and ask for structured findings. Same sandbox posture as
`/codex:ask`: read-only, no network escalation, `--output-last-message` for the
clean answer.

**The review's SCOPE is measured, not assumed (issue #1261).** The prompt offers
the reviewer the repository's files for context, but that offer is only real
where codex's sandbox can start. In a Kyle session container bubblewrap has no
user namespace: every tool call the reviewer makes fails, and the review still
succeeds on the diff alone - a diff-only review indistinguishable from a full
one. So the block below probes the sandbox first (`codex sandbox`, no model
call) by reading one tracked file inside it, and emits `CODEX_REVIEW_SCOPE:`:

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
issue as the owner. The cause was not confirmed. Three candidates were left: the
read-only sandbox did not fence the network there, a host configuration let a
sandbox-denied command be approved to run outside it, or the caller supplied
`danger-full-access`. So the fix does not rely on any one of them:

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

```bash
# Sandbox mode, from the caller only (issue #1261, #1285 shape).
REVIEW_SANDBOX="${CODEX_REVIEW_SANDBOX:-read-only}"
case "$REVIEW_SANDBOX" in
    read-only) ;;
    danger-full-access) ;;
    *) echo "CODEX_REVIEW: unavailable (CODEX_REVIEW_SANDBOX='$REVIEW_SANDBOX' is not read-only or danger-full-access; refusing to run)" >&2; rm -f "$DIFF_FILE"; exit 3 ;;
esac

# Scope probe (issue #1261). A sandbox that cannot start makes the review
# file-blind while it still reports findings, so measure it before the run.
if [ "$REVIEW_SANDBOX" = "danger-full-access" ]; then
    REVIEW_SCOPE="full"
elif ! codex sandbox --help >/dev/null 2>&1; then
    REVIEW_SCOPE="unverified"
# The probe READS a tracked repository file under the sandbox, not merely
# starts it: startup alone does not prove the reviewer can read the tree
# (counter-model review). An empty repository has nothing to read - unverified.
# Paths are enumerated AND read from the same root (re-review: `git ls-files`
# is cwd-relative), and the candidate must exist on disk - a tracked file
# deleted in the working tree is not a failed read.
elif ! PROBE_ROOT="$(git rev-parse --show-toplevel)" || ! PROBE_FILE="$(
        git -C "$PROBE_ROOT" ls-files -z | while IFS= read -r -d '' f; do
            [ -f "$PROBE_ROOT/$f" ] && [ -r "$PROBE_ROOT/$f" ] && { printf '%s' "$f"; break; }
        done)" || [ -z "$PROBE_FILE" ]; then
    REVIEW_SCOPE="unverified"
elif (cd "$PROBE_ROOT" && codex sandbox -c 'sandbox_mode="read-only"' -- head -c 1 -- "$PROBE_FILE") >/dev/null 2>&1; then
    REVIEW_SCOPE="full"
else
    REVIEW_SCOPE="diff-only"
fi
echo "CODEX_REVIEW_SCOPE: $REVIEW_SCOPE"
case "$REVIEW_SCOPE" in
    full) SCOPE_LINE="You may also open the files in this repository (read-only) for surrounding context." ;;
    diff-only) SCOPE_LINE="You CANNOT open files in this repository: the sandbox cannot start here, so every tool call will fail. Review the diff alone, and say in your findings where a conclusion would need surrounding code you could not read." ;;
    *) SCOPE_LINE="Opening files in this repository may or may not work here; if a tool call fails, review the diff alone and say where a conclusion would need surrounding code you could not read." ;;
esac

# Network fence probe (issue #1450). A `--sandbox read-only` reviewer once ran
# an authenticated `gh api ... --method POST` and commented on an issue as the
# owner. So measure the fence as the scope is measured: try one harmless GET
# INSIDE the same sandbox, and a positive control OUTSIDE it, because a probe
# that fails where nothing is reachable at all has measured nothing.
#
# `blocked` IS A MEASUREMENT, NEVER A FAILURE TO MEASURE (issue #1458). Only a
# curl that RAN inside the sandbox and failed with a network-class exit (the
# table below: 6 resolve, 7 connect, 28 timeout) while the same GET works outside
# is `blocked`. A sandbox that did not start, a curl absent inside it, a TLS or
# CLI error: all `unverified`. One function runs BOTH sandboxed probes, so the
# start probe and the curl probe cannot differ in invocation or flags - a split
# that came from a flag difference would otherwise read as `blocked`.
NET_PROBE_URL="https://api.github.com/"
NET_BLOCKED_RCS="6 7 28"
net_sandbox() { codex sandbox -c 'sandbox_mode="read-only"' -- "$@"; }
if [ "$REVIEW_SANDBOX" = "danger-full-access" ]; then
    REVIEW_NETWORK="open"
elif ! command -v curl >/dev/null 2>&1 || ! codex sandbox --help >/dev/null 2>&1; then
    REVIEW_NETWORK="unverified"
elif ! net_sandbox true >/dev/null 2>&1; then
    REVIEW_NETWORK="unverified"
else
    net_sandbox curl -sS -o /dev/null --max-time 5 "$NET_PROBE_URL" >/dev/null 2>&1
    NET_RC=$?
    if [ "$NET_RC" -eq 0 ]; then
        REVIEW_NETWORK="open"
    elif case " $NET_BLOCKED_RCS " in *" $NET_RC "*) true ;; *) false ;; esac \
            && curl -sS -o /dev/null --max-time 5 "$NET_PROBE_URL" >/dev/null 2>&1; then
        REVIEW_NETWORK="blocked"
    else
        REVIEW_NETWORK="unverified"
    fi
fi
echo "CODEX_REVIEW_NETWORK: $REVIEW_NETWORK"
# Said on EVERY verdict: `blocked` measures one endpoint, not the whole egress.
NETWORK_LINE=" Do not run any command that contacts a remote service (gh, git fetch or push, curl, wget, or similar): this review is read-only and the caller routes every finding itself."

# Withdraw the credentials an ORDINARY gh, git or ssh invocation discovers
# (issues #1450, #1459), whatever the fence above measured. The reviewer runs with
# HOME set to an EMPTY directory - so gh's default config, git's global config,
# ~/.ssh and every other dotfile resolve to nothing - and CODEX_HOME pinned to the
# real one, so codex's own auth and model config are unchanged. Then:
#   GIT_CONFIG_NOSYSTEM and a GIT_CONFIG_GLOBAL holding ONLY the caller's
#   safe.directory entries (url.*.insteadOf tokens, helpers, headers: gone);
#   GIT_CONFIG_PARAMETERS resetting credential.helper and http.extraheader,
#   which reaches the repository's own .git/config too - and carries no `KEY`
#   in its name, which codex's default shell_environment_policy strips;
#   no SSH agent, GIT_SSH_COMMAND=false (git's ssh transport), no session bus;
#   GIT_ASKPASS=false and no SSH_ASKPASS, so an inherited askpass program cannot
#   answer git's credential prompt (counter-model review).
# A DIRECT ssh call still finds the account's ~/.ssh: OpenSSH reads the home
# directory from the password database, not $HOME (counter-model review).
# LC_ALL=C and LANG=C (issue #1461): a read DENIED mid-review is recognised in
# the receipt writer by its message ("Permission denied", "Operation not
# permitted"), so the reviewer's commands print those in the C locale's form.
# NOT withdrawn, and so MEASURED below rather than promised away: a credential
# embedded in the repository's own config, and files the reviewer can read by
# absolute path. approval_policy is pinned to "never" so no host configuration
# can approve a sandbox-denied command into running outside the sandbox.
# Fail CLOSED: an empty HOME that could not be made would hand over the real one.
REVIEW_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
REVIEW_HOME=$(mktemp -d /tmp/codex-review-home.XXXXXX) && [ -d "$REVIEW_HOME" ] \
    && mkdir -p "$REVIEW_HOME/.config/gh" || {
    echo "CODEX_REVIEW: unavailable (could not create an empty HOME for the reviewer; refusing to run it with the caller's credentials)" >&2; rm -f "$DIFF_FILE"; exit 3; }
git config --global --get-all safe.directory 2>/dev/null | while IFS= read -r d; do
    git config --file "$REVIEW_HOME/.gitconfig" --add safe.directory "$d"
done
: >> "$REVIEW_HOME/.gitconfig"

# Credentials in the repository's OWN config (issue #1459). They cannot be
# withdrawn without editing the caller's repository, so they are MEASURED and
# shown. The population is what git USES: local and worktree scope, with
# includes followed. Only KEY NAMES are printed, never values - and a key whose
# subsection is a URL (url.<base>.insteadof, http.<url>.extraheader) embeds that
# URL, so its subsection is printed redacted. A URL-scoped extraheader is also
# RESET for the reviewer, key by key: `http.extraheader=` does not reach it.
REVIEW_LOCAL_CRED_KEYS=""
REVIEW_HEADER_RESETS=""
# `-z` IS LOAD-BEARING (counter-model review): a subsection may contain `=`
# (`http.https://host/a=b/.extraheader`), so splitting `key=value` at the first
# `=` mis-reads the key. `-z` writes `scope\0key\nvalue\0`. The listing holds
# VALUES, so it goes to a file OUTSIDE the reviewer's HOME, removed at once.
REVIEW_LOCAL_CFG_FILE=$(mktemp /tmp/codex-review-localcfg.XXXXXX) || REVIEW_LOCAL_CFG_FILE=""
# Outside a repository `git config --list` still succeeds - over GLOBAL config
# alone - so "is this a repository" is asked first: no repository is unknown.
if [ -z "$REVIEW_LOCAL_CFG_FILE" ] || ! git rev-parse --git-dir >/dev/null 2>&1 \
        || ! git config --list --show-scope --includes -z > "$REVIEW_LOCAL_CFG_FILE" 2>/dev/null; then
    REVIEW_LOCAL_CREDS="unknown"
else
    while IFS= read -r -d '' scope && IFS= read -r -d '' kv; do
        case "$scope" in local|worktree) ;; *) continue ;; esac
        key=${kv%%$'\n'*}
        case "$kv" in *$'\n'*) val=${kv#*$'\n'} ;; *) val="" ;; esac
        case "$key" in
            remote.*.url|remote.*.pushurl)
                case "$val" in http://*@*|https://*@*) REVIEW_LOCAL_CRED_KEYS="$REVIEW_LOCAL_CRED_KEYS $key" ;; esac ;;
            url.*.insteadof)
                case "$key" in url.http://*@*|url.https://*@*) REVIEW_LOCAL_CRED_KEYS="$REVIEW_LOCAL_CRED_KEYS url.<redacted>.insteadof" ;; esac ;;
            http.extraheader)
                [ -n "$val" ] && REVIEW_LOCAL_CRED_KEYS="$REVIEW_LOCAL_CRED_KEYS http.extraheader" ;;
            http.*.extraheader)
                [ -n "$val" ] || continue
                case "$key" in
                    *"'"*) REVIEW_LOCAL_CRED_KEYS="$REVIEW_LOCAL_CRED_KEYS http.<redacted>.extraheader(NOT-RESET)" ;;
                    *) REVIEW_LOCAL_CRED_KEYS="$REVIEW_LOCAL_CRED_KEYS http.<redacted>.extraheader"
                       REVIEW_HEADER_RESETS="$REVIEW_HEADER_RESETS '$key'=''" ;;
                esac ;;
        esac
    done < "$REVIEW_LOCAL_CFG_FILE"
    if [ -n "$REVIEW_LOCAL_CRED_KEYS" ]; then REVIEW_LOCAL_CREDS="present"; else REVIEW_LOCAL_CREDS="absent"; fi
fi
rm -f "$REVIEW_LOCAL_CFG_FILE"
echo "CODEX_REVIEW_LOCAL_CREDENTIALS: $REVIEW_LOCAL_CREDS${REVIEW_LOCAL_CRED_KEYS:+ (${REVIEW_LOCAL_CRED_KEYS# })}"

FINDINGS=$(mktemp /tmp/codex-review.XXXXXX.md)
# STREAM carries the thread id that Step 4 needs to identify the reviewing
# model. Without --json there is no thread id, and the Step-4 lookup silently
# matches every rollout on the host instead of this run's.
STREAM=$(mktemp /tmp/codex-review.XXXXXX.jsonl)

cat "$DIFF_FILE" | env -u GH_TOKEN -u GITHUB_TOKEN -u GH_ENTERPRISE_TOKEN -u GITHUB_ENTERPRISE_TOKEN \
    -u SSH_AUTH_SOCK -u DBUS_SESSION_BUS_ADDRESS -u GIT_CONFIG_COUNT \
    -u SSH_ASKPASS -u SSH_ASKPASS_REQUIRE GIT_ASKPASS=false \
    HOME="$REVIEW_HOME" CODEX_HOME="$REVIEW_CODEX_HOME" \
    GH_CONFIG_DIR="$REVIEW_HOME/.config/gh" GIT_TERMINAL_PROMPT=0 \
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL="$REVIEW_HOME/.gitconfig" \
    GIT_CONFIG_PARAMETERS="'credential.helper'='' 'http.extraheader'=''$REVIEW_HEADER_RESETS" \
    GIT_SSH_COMMAND=false LC_ALL=C LANG=C \
    codex exec \
    --sandbox "$REVIEW_SANDBOX" \
    -c 'approval_policy="never"' \
    --color never \
    --skip-git-repo-check \
    --json \
    --output-last-message "$FINDINGS" \
    "You are reviewing a code change as an independent reviewer. The unified diff is provided on stdin. ${SCOPE_LINE} ${NETWORK_LINE} Review intent/context: ${CONTEXT:-none provided}.

Before inspecting the change, if repository execution is available, execute exactly 'git rev-parse HEAD' as a separate shell tool call and retain its result. Never copy a head from this prompt or from session startup metadata. If execution is unavailable, review only the exact stdin patch; its runtime-captured bytes bind the reviewed artifact.

Review for: correctness bugs, security issues, missed edge cases, broken or missing tests, and meaningful simplifications. Do NOT restyle working code or comment on formatting.

If the diff adds or changes a check, gate, guard, tripwire or allowlist, ask two further questions of it and report a failure of either as a finding: (1) does its success message claim more than its input population supports - can a zero distinguish 'I looked and found nothing' from 'there was nothing to look at'; and (2) can a non-zero distinguish 'our thing changed' from 'a neighbour changed'. Widening the detector is not always the remedy: where the narrow answer is deliberately correct, say so and say where the larger question should be answered instead.

Return a findings report AND a red cases section, in exactly this format. Emit the report headings as unfenced Markdown; code examples may use fences:

## Findings

### [SEVERITY] short title
- File: <path>:<line>
- Issue: <one-paragraph description of the defect and the failure scenario>
- Suggestion: <concrete fix>

Severity is one of CRITICAL, HIGH, MEDIUM, LOW. Order findings most severe first. If the change is sound, return '## Findings' followed by 'None - no defects found.' Do not pad with praise or restate the diff.

## Red cases

For each instrument this change adds or modifies (a check, gate, guard, tripwire or allowlist), name the concrete input that would make that instrument report the OTHER verdict - name the input, not the intention. If the change modifies no instrument, write exactly 'None - no instrument changed.' so an absent section is distinguishable from a considered zero." | tee "$STREAM"

# `--json` puts the event stream on stdout, so TEE it: the caller still sees the
# run and $STREAM keeps the thread id Step 4 needs to identify the model.
#
# Read codex's status from PIPESTATUS, not $?. This was already a pipeline
# (`cat | codex`) and the tee makes it three stages; $? is the LAST stage, so a
# failed review would report success and be relayed as an empty findings report.
CODEX_EXIT=${PIPESTATUS[1]}
rm -rf "$REVIEW_HOME"
```

Deep reviews of large diffs can run for many minutes; for anything non-trivial
run the command in the background and poll, exactly as documented in
`/codex:ask` under "Long-running delegations".

### Step 4: Relay the findings

```bash
# A shell variable does NOT cross a command boundary: /flow:auto cannot read
# $REVIEW_MODEL out of this command's shell, and the findings transcript
# deliberately carries no model. Emit a marker, same convention as
# FLOW_CI_STATUS / COUNTER_MODEL_REVIEW, and let the caller consume it.
echo "CODEX_REVIEW_BASE: $BASE"
echo "CODEX_REVIEW_STREAM: $STREAM"
echo "CODEX_REVIEW_MODEL: ${REVIEW_MODEL:-unknown}"
echo "CODEX_REVIEW_SCOPE: ${REVIEW_SCOPE:-unverified}"
echo "CODEX_REVIEW_NETWORK: ${REVIEW_NETWORK:-unverified}"
echo "CODEX_REVIEW_LOCAL_CREDENTIALS: ${REVIEW_LOCAL_CREDS:-unknown}"
case "${REVIEW_NETWORK:-unverified}" in
    blocked) NETWORK_BANNER="network: blocked" ;;
    open) NETWORK_BANNER="network: OPEN - not a network-fenced review" ;;
    *) NETWORK_BANNER="network: unverified - not shown to be fenced" ;;
esac
case "${REVIEW_LOCAL_CREDS:-unknown}" in
    absent) LOCAL_BANNER="local credentials: none in this repository's config" ;;
    present) LOCAL_BANNER="local credentials: PRESENT in this repository's config (${REVIEW_LOCAL_CRED_KEYS# }) - not withdrawn" ;;
    *) LOCAL_BANNER="local credentials: unknown - this repository's config could not be read" ;;
esac
echo "===== Codex (${REVIEW_MODEL:-model unread}) code review - scope: ${REVIEW_SCOPE:-unverified} - ${NETWORK_BANNER} - ${LOCAL_BANNER} ====="
cat "$FINDINGS"
rm -f "$DIFF_FILE" "$FINDINGS"
# Retain $STREAM until the caller writes and stages its receipt; the writer
# must resolve the actual exec evidence. The caller may then remove this file.
```

Present the findings **attributed to Codex** - never silently merged into your
own assessment. Then, standalone, add your own labeled triage: for each finding,
agree (worth fixing), disagree (with the reason), or defer (real but out of
scope). Do not apply fixes in this command - it is read-only by design; fixing
is the caller's decision (`/flow:auto` Step 6 item 1c does exactly that).

State the `CODEX_REVIEW_SCOPE`, `CODEX_REVIEW_NETWORK` and
`CODEX_REVIEW_LOCAL_CREDENTIALS` with the findings.
**Label `CODEX_REVIEW_NETWORK` as a sandbox-probe proxy, not a direct
measurement of the review itself (issue #1494).** The probe above runs through
`codex sandbox`; the reviewer that actually produced the findings runs through
`codex exec` (Step 3). The two invocation paths are not asserted to apply
identical network fencing, so this verdict characterizes the PROBE's
reachability, which stands in for the reviewer's rather than measuring it
directly - say so when relaying the verdict, the same way `diff-only` is
relayed as "cannot open files" rather than "a lesser review."
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

If `CODEX_EXIT` is non-zero, report the failure honestly and do not fabricate
findings; a calling workflow treats it like the exit-3 unavailable case.

### Step 5: Route Deferred Findings to the Nit Store

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

- The review prompt above carries the two detector questions inline rather than
  linking them, because the reviewing model runs `--sandbox read-only` against a
  diff and cannot be relied on to go and read a repository document. The
  canonical statement, with the instance index and the test shapes a finding
  should ask for, is
  [the detector contracts](../../../docs/agents/detector-contracts.md); read it
  when triaging a detector finding in Step 4.
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
- The findings format above is the contract `/flow:auto` Step 6 item 1c parses,
  via `scripts/counter-model-receipt.py parse`. It keys on the `## Findings`
  heading and, for a clean review, the `None - no defects found.` sentinel - so
  keep the prompt's format block intact if you adjust the prompt.
- The `## Red cases` section is part of this command's own contract (issue
  #1030), not something a caller has to ask for separately - it was previously
  supplied only by `/flow:auto`'s call site, which meant a document reading
  this contract alone and following "Return ONLY a findings report" would
  silently get no red cases. `None - no instrument changed.` is the explicit
  empty case, so an absent section stays distinguishable from a considered
  zero.
- For a review by non-OpenAI models, use `/second-opinion:start` instead.

Receipt-bound reviews follow [the runtime evidence contract](../../../docs/agents/counter-model-evidence.md). Binding names the recorded artifact, not the thoroughness of review. Pass `CODEX_REVIEW_BASE` as `--review-base` when recording the receipt.
