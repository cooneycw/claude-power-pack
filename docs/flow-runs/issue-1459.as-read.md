<!-- flow-run n=1 id=2e7a4d0aa2b9477f881bb71177903071 -->
## Run 1 - issue #1459 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1459
- Read at:      2026-10-17T01:19:20Z
- updatedAt:    2026-10-17T00:14:47Z   (context only - moves on comments and labels)
- Body digest:  06b147482053f5cbf47bbae11b4aa5b6a31bf104ade0044c8c60a3ceec0d0fb7   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1826 of 1826 (cap 16384)

### Body as read
Found while reviewing PR #1451 (merged as 6457407; Refs #1450).

## Defect

The doc says that, under the #1450 fence, "gh and git invoked as usual find no credential" (`.claude/commands/codex/code_review.md`, around lines 282-287 and 521-524). Several credentials are still used automatically by an ordinary command.

- **Token in the remote URL.** With `url.<tok>@github.com.insteadOf`, the token is embedded in the rewritten URL. Confirmed: `git ls-remote --get-url` still returns `https://x-access-token:SECRET@...` with the credential helper reset.
- **`http.extraheader`.** Not cleared, so an auth header configured there is still sent.
- **SSH.** An SSH remote still authenticates through `SSH_AUTH_SOCK` (not unset) or `~/.ssh` keys.
- **gh.** gh's empty `GH_CONFIG_DIR` is undone by one variable: `GH_CONFIG_DIR=~/.config/gh gh api ...`. HOME is unchanged, and a keyring-stored token is also unaffected.

## Why it matters

#1450 was a "read-only" reviewer posting to GitHub. Withdrawing credentials is meant to make that impossible even if the network fence fails. As written, it only stops the default gh path.

## Suggested fix

- Unset `SSH_AUTH_SOCK` and set `GIT_SSH_COMMAND=false`.
- Neutralise `url.*.insteadOf` and `http.*.extraheader` (for example with `GIT_CONFIG_GLOBAL` pointed at an empty file, plus `GIT_CONFIG_NOSYSTEM=1`).
- Reword the doc claim to what is actually withdrawn.
- Add a test for each path.

A related caveat (unverified): codex's default `shell_environment_policy` excludes `*KEY*` names. That could strip `GIT_CONFIG_KEY_0` while `GIT_CONFIG_COUNT=1` remains. Git then fails every command with "missing config key GIT_CONFIG_KEY_0" (rc 128). That fails closed, but it would break `git diff`/`git log` for the reviewer. Using `GIT_CONFIG_GLOBAL` avoids `KEY`-named variables entirely.

