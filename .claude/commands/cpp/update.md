---
description: Update Claude Power Pack to the latest version
allowed-tools: Bash(git:*), Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(cat:*), Bash(uv:*), Bash(claude mcp list:*), Bash(claude mcp add:*), Bash(claude mcp remove:*), Bash(sudo systemctl:*), Bash(systemctl:*), Bash(command -v:*), Bash(ln:*), Bash(mkdir:*), Bash(cp:*), Bash(diff:*), Bash(find:*), Bash(grep:*), Bash(sed:*), Bash(awk:*), Bash(sort:*), Bash(mktemp:*), Bash(rm:*), Bash(sudo rm:*), Bash(curl:*), Bash(ss:*), Bash(docker:*), Bash(make:*), Bash(python3:*), AskUserQuestion
---

# Claude Power Pack Update

Update CPP to the latest version, detect MCP server and skill drift, and offer guided remediation.

Each Bash tool call starts a fresh shell. Bind every required input as a quoted
LITERAL in the SAME call, using the values printed earlier; do not export or
source prior shell state. `CPP_DIR` is the absolute checkout path from Step1.
For local-model lanes, copy the printed `declare -p` values as literal bindings,
including the status array; never evaluate unreviewed output. Bind each consent
answer to explicit yes/no from THIS run. Missing/malformed inputs refuse.
Replace each `REPLACE_WITH_*` token before executing its fence.

---
## Step 1: Locate CPP Source

```bash
CPP_DIR=""
# The search list is overridable so a test can control it, and defaults to the
# shipped paths so nothing changes in production (#1138). Without this the two
# locator tests could only make a checkout absent by overriding $HOME, which
# leaves /opt/claude-power-pack ambient: on a host that has one they take the
# checkout-found branch and assert against the wrong thing - a test whose input
# is host state, load-bearing on one box and inert on another.
for dir in ${CPP_INIT_CANDIDATES:-~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack}; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done

if [ -n "$CPP_DIR" ]; then
  echo "Found claude-power-pack at: $CPP_DIR"
else
  # TWO DIFFERENT FACTS (issue #1138). "No checkout here" is not "CPP is
  # unavailable", and this block used to measure the first and report the
  # second. In a kyle session container the command surface and the helpers are
  # projected in read-only by the substrate, with no checkout anywhere - so the
  # old message announced that CPP was not installed to a session that was
  # running a CPP command at that moment, and advised a clone that is the one
  # action leading into the install path that cannot work there.
  #
  # This tests for the OBJECTS - is a checkout here, is a surface here, can it
  # be written - and never for a particular substrate. Which substrate, if any,
  # is providing the surface is a separate question with its own issue (#1132);
  # answering it here would decide it by accident.
  # COUNT CPP'S SURFACE, NOT EVERY NEIGHBOUR'S (counter-model review, #1138).
  # The first cut counted every immediate entry under ~/.claude/commands, so a
  # single hand-written `personal.md` was enough to announce "CPP IS AVAILABLE"
  # and discourage a clone in a session with no CPP surface at all - measured.
  # That is this issue's own defect class committed by its own fix: a check
  # reading one property (how many things are here) to answer another (is OUR
  # thing here). The availability claim now rests on CPP's own command document
  # being READABLE; the family count is reported beside it as context and
  # decides nothing.
  #
  # `-L ... -type d` follows symlinks deliberately: an installed family IS a
  # symlink to a directory, so a bare -type d would count zero on a correctly
  # installed host, while a DANGLING link stays excluded - it is type l even
  # under -L, and a broken link is not a served family.
  cpp_surface=no
  [ -r ~/.claude/commands/cpp/init.md ] && cpp_surface=yes
  families=$(find -L ~/.claude/commands -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
  helpers=$(find -L ~/.claude/scripts -mindepth 1 -maxdepth 1 -type f 2>/dev/null | wc -l)

  # Locating the source precedes installation consent. Do not create a probe file.
  surface_writable="unverified (not probed before confirmation)"

  echo "No claude-power-pack CHECKOUT found at any known path."
  echo "  CPP command surface served here: $cpp_surface (~/.claude/commands/cpp/init.md readable)"
  echo "  command families already served: $families"
  echo "  helpers already served:          $helpers"
  echo "  ~/.claude/commands writable:     $surface_writable"
  echo

  if [ "$cpp_surface" = yes ]; then
    echo "CPP IS AVAILABLE IN THIS SESSION - $families command families are already being served,"
    echo "which is how you invoked this command. What is absent is the source CHECKOUT that"
    echo "installing FROM requires."
    echo
    echo "Do NOT clone a checkout to get past this message. If something else is providing"
    echo "the surface (a container substrate projects it read-only, for instance), a clone"
    echo "adds a redundant copy and carries you into an install that cannot change anything"
    echo "and, before #1138, reported success for doing so."
    echo
    echo "Nothing to do here. Install or update CPP where the checkout lives instead."
    exit 0
  fi

  echo "ERROR: claude-power-pack not found, and no command surface is being served here."
  echo "Please clone it first:"
  echo "  git clone https://github.com/cooneycw/claude-power-pack ~/Projects/claude-power-pack"
  exit 1
fi
```

---
## Step 2: Check Current Version and Remote

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
cd "$CPP_DIR" || exit 4

# CLAUDE.md owns the current version; fall back only when its line is absent (#544).
CURRENT_VERSION=$(grep -oPm1 '^Current version: \K[0-9]+\.[0-9]+\.[0-9]+' CLAUDE.md 2>/dev/null)
if [ -z "$CURRENT_VERSION" ]; then
  CURRENT_VERSION=$(grep -oPm1 '^\#\# \[\K[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md 2>/dev/null)
fi
CURRENT_VERSION="${CURRENT_VERSION:-unknown}"
CURRENT_COMMIT=$(git rev-parse --short HEAD)
CURRENT_BRANCH=$(git branch --show-current)

echo "Current: v$CURRENT_VERSION ($CURRENT_COMMIT) on $CURRENT_BRANCH"

# Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo ""
  echo "WARNING: Uncommitted changes detected in CPP repo"
  git status --short
  echo ""
  echo "These changes may be overwritten by the update."
fi

# Fetch and compare (issue #1282). The helper checks the fetch and reports
# `unknown: <reason>` when it cannot count - a failed fetch, a read-only
# checkout, a detached HEAD (empty CURRENT_BRANCH) - instead of the old
# `|| echo "0"`, which printed "Already up to date!" for all of them.
echo ""
echo "Fetching latest from origin..."
FRESHNESS=$("$CPP_DIR/scripts/cpp-checkout-freshness.sh" --path "$CPP_DIR" --branch "$CURRENT_BRANCH")
FRESHNESS_EXIT=$?
echo "$FRESHNESS"
VERDICT=$(printf '%s\n' "$FRESHNESS" | sed -n 's/^CPP_CHECKOUT_FRESHNESS: //p')
BEHIND=""
case "$VERDICT" in
  current)     echo ""; echo "Already up to date!"; BEHIND=0 ;;
  "behind "*)  BEHIND=${VERDICT#behind } ;;
  "diverged "*) BEHIND=$(printf '%s' "$VERDICT" | sed -n 's/.*behind \([0-9]*\).*/\1/p') ;;
  "ahead "*)   BEHIND=0; echo ""; echo "Not behind, but carrying local commits origin/$CURRENT_BRANCH does not have." ;;
  *)           echo ""; echo "Could not determine whether an update is available (exit $FRESHNESS_EXIT) - NOT reporting up to date." ;;
esac
```

Report the version comparison to the user.

---
## Step 3: Pull Updates

**Only if behind remote.** Ask user for confirmation before pulling.

If there are uncommitted changes, warn and **ask** whether to set them aside.
Ask for real - this step used to say "ask" in prose and stash unconditionally in
the code, which is how a user's work was moved without their knowing (issue
#1056).

**The stash stack is SHARED with every linked worktree** (`refs/stash` lives in
the repository's common git dir, which a worktree does not get its own copy of).
So two rules govern the block below, and neither is optional:

1. **Tag the entry and restore it by SHA - never a bare `git stash pop`.** A
   bare pop takes whatever is on TOP of the stack, which with concurrent
   sessions is routinely somebody else's entry: on #1032 a worker's pop restored
   67 lines of a different session's in-progress work and lost its own. The SHA
   captured at push time names OUR entry and cannot resolve to a stranger's.
2. **Never leave the entry behind silently.** The version of this step before
   #1056 pushed and had NO restore step at all, so a `/cpp:update` on 2026-09-03
   left an entry sitting unclaimed on the shared stack for sixteen days. If the
   restore cannot run, say the SHA out loud - an orphan nobody is told about is
   indistinguishable from work that was never set aside.

`/cpp:update` runs in `$CPP_DIR`, the MAIN checkout, so
`scripts/stash-worktree-guard.sh` does not refuse this push - that guard
refuses pushes from a linked worktree. The discipline here is what makes the
main-checkout case safe; nothing enforces it for you. See
`docs/agents/shared-stash-stack.md`.

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
cd "$CPP_DIR" || exit 4

CURRENT_BRANCH=$(git branch --show-current)
[ -n "$CURRENT_BRANCH" ] || exit 4
CURRENT_COMMIT=$(git rev-parse --short HEAD)
CURRENT_VERSION=$(grep -oPm1 '^Current version: \K[0-9]+\.[0-9]+\.[0-9]+' CLAUDE.md 2>/dev/null)
if [ -z "$CURRENT_VERSION" ]; then
  CURRENT_VERSION=$(grep -oPm1 '^\#\# \[\K[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md 2>/dev/null)
fi
CURRENT_VERSION="${CURRENT_VERSION:-unknown}"
# Set aside only on the user's answer above, and only with an entry we can
# identify later. $$ disambiguates two /cpp:update runs started in the same
# second (issue #1056).
STASH_TAG="cpp-update-$(date +%Y%m%d-%H%M%S)-$$"
STASH_SHA=""
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Setting uncommitted changes aside as '$STASH_TAG'..."
  if git stash push -m "$STASH_TAG"; then
    # Capture only our exact tagged stash SHA; ambiguous matches require manual recovery.
    STASH_MATCHES=$(git stash list --format='%H%x09%gs' \
      | awk -F'\t' -v t=": $STASH_TAG" \
          '{ n=length($2); m=length(t); if (n >= m && substr($2, n-m+1) == t) print $1 }')
    STASH_COUNT=$(printf '%s' "$STASH_MATCHES" | grep -c . || true)
    if [ "$STASH_COUNT" = "1" ]; then
      STASH_SHA="$STASH_MATCHES"
      echo "  entry: $STASH_SHA"
    else
      STASH_SHA=""
      echo "  WARNING: $STASH_COUNT entries matched '$STASH_TAG' - not restoring automatically."
      echo "  Your work is on the stash stack; find it with: git stash list"
    fi
  else
    echo "STOP: could not set the changes aside; not pulling over a dirty tree."
    exit 1
  fi
fi

# Pull latest
git pull origin $CURRENT_BRANCH

# Restore by SHA, never `git stash pop` (issue #1056).
if [ -n "$STASH_SHA" ]; then
  if git stash apply "$STASH_SHA"; then
    # Keep the stash entry: shared-stack indices can change before a safe drop (#1056).
    echo "Restored your uncommitted changes."
    echo "  The stash entry was kept (dropping it safely needs a stable handle the"
    echo "  shared stack does not offer). Clear it when no other session is stashing:"
    echo "    git stash list   # find the entry tagged $STASH_TAG"
    echo "    git stash drop stash@{N}"
  else
    echo ""
    echo "NOTE: your changes are SAFE but could not be applied cleanly (likely a"
    echo "      conflict with what was just pulled). They are kept at:"
    echo "        $STASH_SHA  ($STASH_TAG)"
    echo "      Recover with:  git stash apply $STASH_SHA"
    echo "      The entry was NOT dropped."
  fi
fi

NEW_COMMIT=$(git rev-parse --short HEAD)
# Same source-of-truth derivation as Step 2 (issue #544).
NEW_VERSION=$(grep -oPm1 '^Current version: \K[0-9]+\.[0-9]+\.[0-9]+' CLAUDE.md 2>/dev/null)
if [ -z "$NEW_VERSION" ]; then
  NEW_VERSION=$(grep -oPm1 '^\#\# \[\K[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md 2>/dev/null)
fi
NEW_VERSION="${NEW_VERSION:-unknown}"
echo ""
# Never report a same-version pull as a no-op: when the release number did not
# move but the commit did, say so and point at the unreleased delta instead of
# printing a misleading "vX -> vX" (issue #544).
if [ "$CURRENT_VERSION" = "$NEW_VERSION" ] && [ "$CURRENT_COMMIT" != "$NEW_COMMIT" ]; then
  echo "Updated: v$NEW_VERSION unchanged, code moved $CURRENT_COMMIT -> $NEW_COMMIT"
  echo "(unreleased changes - see the [Unreleased] section of CHANGELOG.md)"
else
  echo "Updated: v$CURRENT_VERSION ($CURRENT_COMMIT) -> v$NEW_VERSION ($NEW_COMMIT)"
fi
```

---
## Step 3.5: Re-read Self (the pull may have changed this command)

The pull may have changed this command document. Compare its on-disk version
to the `Current:` SHA printed in Step2, bound as a LITERAL below. Re-read changed
instructions before continuing; the pre-pull copy can reference deleted helpers
(#545). Do not use `ORIG_HEAD`: another session's pull can overwrite it (#1263).
A missing pre-pull commit leaves the instructions possibly stale, never current.

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
cd "$CPP_DIR" || exit 4
PRE_PULL_COMMIT="<the SHA from Step 2's 'Current:' line>"
SELF=".claude/commands/cpp/update.md"
SELF_CHANGED=unknown
if git rev-parse -q --verify "${PRE_PULL_COMMIT}^{commit}" >/dev/null 2>&1; then
  if git diff --quiet "$PRE_PULL_COMMIT" -- "$SELF"; then
    SELF_CHANGED=no
    echo "No change to /cpp:update since $PRE_PULL_COMMIT - the steps in context are current."
  else
    SELF_CHANGED=yes
    echo ""
    echo "NOTE: /cpp:update itself changed since $PRE_PULL_COMMIT. Diff against the copy in context:"
    git --no-pager diff "$PRE_PULL_COMMIT" -- "$SELF"
    echo ""
    echo "The /cpp:update steps loaded in context are now STALE."
  fi
else
  echo "Could not resolve the pre-pull commit '$PRE_PULL_COMMIT' - treat the in-context steps as possibly stale."
fi
```

**Then, unless `SELF_CHANGED` is `no`, STOP following the in-context steps and
RE-READ the on-disk command before continuing.** Open
`$CPP_DIR/.claude/commands/cpp/update.md` (resolve `$CPP_DIR` from Step 1) and
follow **its** Step 4 onward - the freshly-pulled file on disk is authoritative
now, not the copy this run started with. Only when `SELF_CHANGED` is `no` may you
continue with the in-context steps as-is. This is the one point where re-reading is
mandatory; everything below is what you execute *after* confirming it is current.

---
## Step 3.6: Bash Floor Report (issue #1628)

CPP's helpers need bash 4.4 or newer, and macOS ships 3.2. Below the floor, later
steps fail with raw shell errors that do not name the cause, so say it once here
in plain words. Call the CHECKOUT copy: the pull may have changed the check, and
an installed helper from before this version does not have it.

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
BASH_FLOOR_REPORT=$("$CPP_DIR/scripts/flow-preflight.sh" --checks bash 2>/dev/null)
BASH_FLOOR_RC=$?
if [ "$BASH_FLOOR_RC" -ne 0 ]; then
  printf '%s\n' "$BASH_FLOOR_REPORT"
  echo "BASH_FLOOR: not met or not verified (exit $BASH_FLOOR_RC)"
fi
```

- No output - the floor is met on this PATH. Say nothing and move on.
- `BASH_FLOOR:` with exit 1 (`UNSUPPORTED` or `MISSING`) - report the line and its
  remedy prominently, and carry it to Step 10. Do not stop the update: expect helper
  failures in the steps below, and attribute them to this rather than diagnosing
  each one.
- `BASH_FLOOR:` with any other exit - report that the floor was not verified. Never
  relay it as met.

---
## Step 3.7: Recorded CI Provider Report (issue #1677)

Since 10.2.0 a project with no recorded CI provider cannot merge through flow:
`gh-pr-merge.sh` stops with exit 13. Say so now, by name, for the project this
session is working in, rather than letting the first merge find out. Call the
CHECKOUT copy, for the same reason as Step 3.6, and point it at the session's
project directory (the directory this session reports as its cwd), not at
`$CPP_DIR`:

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
"$CPP_DIR/scripts/ci-provider-advisory.sh" /path/to/session/project
```

- A `CPP CI: <project> has no recorded CI provider` line - report it verbatim and
  carry it to Step 10. Do not stop the update and do not record a provider on the
  user's behalf: which CI a project uses is the project's choice (ADR 0012).
- No output - a provider is recorded, OR the check could not ask (not a git
  checkout, no reader). Say nothing; never relay silence as "recorded".

Sessions that were already running when the checkout was pulled do not see this
step. Where a project git-ignores `.claude/`, one record in its main checkout
covers every linked worktree.

---
## Step 4: Update Dependencies

CPP no longer ships in-repo MCP server venvs. The second-opinion server is an
external project (https://github.com/cooneycw/mcp-second-opinion) with its own
dependencies, and playwright runs via npx. There are no CPP-managed server venvs
to sync here.

```bash
echo "No in-repo MCP server venvs to update (second-opinion is external, playwright is npx)."
```

---
## Step 4.6: Refresh Spec-Kit CLI (Optional)

If the official spec-kit CLI (`specify`) is installed, upgrade it so `/spec:adopt`
delegates to the current upstream. If it is absent, offer to install it (never forced -
`/spec:adopt` also installs it on first use). This only touches the CLI; it does not
scaffold `.specify/` into any project.

```bash
if command -v specify &>/dev/null; then
  echo ""
  echo "Upgrading spec-kit CLI..."
  uv tool upgrade specify-cli 2>/dev/null && echo "Done: spec-kit CLI up to date" \
    || echo "Note: could not upgrade specify-cli (not a uv tool install?) - skipping"
else
  echo ""
  echo "spec-kit CLI (specify) is not installed."
  echo "  Install now with: uv tool install specify-cli --from git+https://github.com/github/spec-kit.git"
  echo "  (or just run /spec:adopt in a project - it installs the CLI on first use)"
  # If the user agrees, run:
  #   uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
fi
```

---

## Step 4.7: Retired PreToolUse Hook Cleanup

The PreToolUse dangerous-command hook (`hook-validate-command.sh`) was retired
(issue #439) - native destructive-git blocking + OS sandboxing now cover it. The
secret-masking hook that used to be declared alongside it is gone too (issue
#1206): it was never registered where Claude Code reads, so it never ran.
Because scripts are symlinked into `~/.claude/scripts/` and `hooks.json` was
**copied** into each project, an
older install can be left with a dangling `hook-validate-command.sh` symlink and
a stale `PreToolUse` block that points at it. A dangling hook command exits
non-zero and would **block every Bash command**, so sweep both. This is a
migration step only - do not change anything until the user confirms.

```bash
# 1. Dangling/retired symlink in ~/.claude/scripts/
HOOK_LINK="$HOME/.claude/scripts/hook-validate-command.sh"
if [ -L "$HOOK_LINK" ] || [ -f "$HOOK_LINK" ]; then
  echo "Found retired hook script: $HOOK_LINK"
  echo "  (safe to remove - the PreToolUse dangerous-command hook was retired in #439)"
  # On user confirm:  rm -f "$HOOK_LINK" && echo "Removed $HOOK_LINK"
fi

# Detect the retired hooks.json file, not only its former script reference (#1206).
if [ -f ".claude/hooks.json" ]; then
  echo "This project's .claude/hooks.json is a leftover: CPP no longer ships it (#1206)."
  echo "  Claude Code never loaded that path, so nothing in it ever ran -"
  echo "  neither the masking declarations nor the SessionStart notice."
  if grep -q "hook-validate-command.sh" .claude/hooks.json 2>/dev/null; then
    echo "  It also still references the PreToolUse hook retired in #439."
  fi
  echo "  Offer to remove the WHOLE FILE (user-confirmed; default N)."
  # On user confirmation: rm .claude/hooks.json (Claude Code loads none of it).
fi
```

---

## Step 4.5: Legacy Systemd Teardown

Detect legacy MCP systemd units in both system and user scopes. This is a
migration step only: systemd is no longer a supported runtime model. Do not
stop, disable, or remove anything until the user confirms.

Known legacy unit names to scan:

- `mcp-second-opinion`
- `second-opinion`
- `mcp-playwright`
- `mcp-playwright-persistent`
- `playwright-persistent`
- `mcp-evaluate`
- `evaluate`
- `mcp-coordination`
- `coordination`

Also include discovered units matching `mcp-*`, `nano-*`, or `*coordination*`
from `/etc/systemd/system/`, `~/.config/systemd/user/`, and systemd's unit
indexes.

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
cd "$CPP_DIR" || exit 4

LEGACY_SYSTEMD_REPORT="$(mktemp)"
LEGACY_SYSTEMD_FOUND=false
SYSTEMD_TEARDOWN_STATUS="none"
: > "$LEGACY_SYSTEMD_REPORT"

collect_systemd_units() {
  scope="$1"

  if [ "$scope" = "user" ]; then
    {
      find "$HOME/.config/systemd/user" -maxdepth 1 -type f \
        \( -name 'mcp-*.service' -o -name 'nano-*.service' -o -name '*coordination*.service' \) \
        -printf '%f\n' 2>/dev/null || true
      systemctl --user list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
      systemctl --user list-unit-files --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    } | sed 's/\.service$//' | grep -E '^(mcp-|nano-|.*coordination|second-opinion|playwright-persistent|evaluate|coordination)$' | sort -u || true
  else
    {
      find /etc/systemd/system -maxdepth 1 -type f \
        \( -name 'mcp-*.service' -o -name 'nano-*.service' -o -name '*coordination*.service' \) \
        -printf '%f\n' 2>/dev/null || true
      systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
      systemctl list-unit-files --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    } | sed 's/\.service$//' | grep -E '^(mcp-|nano-|.*coordination|second-opinion|playwright-persistent|evaluate|coordination)$' | sort -u || true
  fi
}

KNOWN_LEGACY_SYSTEMD_UNITS=$(cat <<'EOF'
mcp-second-opinion
second-opinion
mcp-playwright
mcp-playwright-persistent
playwright-persistent
mcp-evaluate
evaluate
mcp-coordination
coordination
EOF
)

USER_LEGACY_SYSTEMD_UNITS="$(collect_systemd_units user)"
SYSTEM_LEGACY_SYSTEMD_UNITS="$(collect_systemd_units system)"
ALL_LEGACY_SYSTEMD_UNITS="$(
  {
    printf '%s\n' "$KNOWN_LEGACY_SYSTEMD_UNITS"
    printf '%s\n' "$USER_LEGACY_SYSTEMD_UNITS"
    printf '%s\n' "$SYSTEM_LEGACY_SYSTEMD_UNITS"
  } | sed '/^$/d' | sort -u
)"

for unit in $ALL_LEGACY_SYSTEMD_UNITS; do
  user_path="$HOME/.config/systemd/user/${unit}.service"
  system_path="/etc/systemd/system/${unit}.service"

  if printf '%s\n' "$USER_LEGACY_SYSTEMD_UNITS" | grep -qx "$unit"; then
    active="$(systemctl --user is-active "$unit" 2>/dev/null || true)"
    enabled="$(systemctl --user is-enabled "$unit" 2>/dev/null || true)"
    failed="$(systemctl --user is-failed "$unit" 2>/dev/null || true)"
    [ -f "$user_path" ] || user_path="-"
    printf 'user\t%s\t%s\t%s\t%s\t%s\n' "$unit" "${active:-unknown}" "${enabled:-unknown}" "${failed:-unknown}" "$user_path" >> "$LEGACY_SYSTEMD_REPORT"
    LEGACY_SYSTEMD_FOUND=true
  fi

  if printf '%s\n' "$SYSTEM_LEGACY_SYSTEMD_UNITS" | grep -qx "$unit"; then
    active="$(systemctl is-active "$unit" 2>/dev/null || true)"
    enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
    failed="$(systemctl is-failed "$unit" 2>/dev/null || true)"
    [ -f "$system_path" ] || system_path="-"
    printf 'system\t%s\t%s\t%s\t%s\t%s\n' "$unit" "${active:-unknown}" "${enabled:-unknown}" "${failed:-unknown}" "$system_path" >> "$LEGACY_SYSTEMD_REPORT"
    LEGACY_SYSTEMD_FOUND=true
  fi
done

if [ "$LEGACY_SYSTEMD_FOUND" = "true" ]; then
  echo ""
  echo "Legacy systemd MCP units detected:"
  printf '%-8s %-32s %-12s %-12s %-12s %s\n' "Scope" "Unit" "Active" "Enabled" "Failed" "Path"
  printf '%-8s %-32s %-12s %-12s %-12s %s\n' "-----" "----" "------" "-------" "------" "----"
  awk -F '\t' '{printf "%-8s %-32s %-12s %-12s %-12s %s\n", $1, $2, $3, $4, $5, $6}' "$LEGACY_SYSTEMD_REPORT"
else
  echo ""
  echo "No legacy systemd MCP units detected."
fi
printf "LEGACY_SYSTEMD_FOUND=%s\nLEGACY_SYSTEMD_REPORT=%s\n" "$LEGACY_SYSTEMD_FOUND" "$LEGACY_SYSTEMD_REPORT"
```

If legacy units were found, ask the user before teardown:

```
Legacy systemd MCP units can revive stale server versions or bind ports that
conflict with your MCP servers (the external second-opinion server, playwright).
Remove the listed systemd units?
```

Options:
- **Tear down legacy systemd** - Stop, disable, remove unit files, reload systemd
- **Skip teardown** - Leave systemd units in place and continue with a port-conflict warning

If the user confirms teardown, run:

```bash
: "${LEGACY_SYSTEMD_FOUND:?bind the printed presence literal}"
: "${LEGACY_SYSTEMD_REPORT:?bind the printed report path}"
case "$LEGACY_SYSTEMD_FOUND" in true|false) ;; *) exit 4 ;; esac
[[ "$LEGACY_SYSTEMD_REPORT" = /* && -f "$LEGACY_SYSTEMD_REPORT" && ! -L "$LEGACY_SYSTEMD_REPORT" && -r "$LEGACY_SYSTEMD_REPORT" ]] || exit 4
SYSTEMD_TEARDOWN_STATUS=none
if [ "$LEGACY_SYSTEMD_FOUND" = "true" ]; then
  REMOVED_SYSTEMD_UNITS=0

  while IFS=$'\t' read -r scope unit active enabled failed path; do
    echo ""
    echo "Removing legacy $scope systemd unit: $unit"

    if [ "$scope" = "user" ]; then
      systemctl --user stop "$unit" 2>/dev/null || true
      systemctl --user disable "$unit" 2>/dev/null || true
      if [ "$path" != "-" ] && [ -f "$path" ]; then
        rm -f "$path"
      fi
      systemctl --user daemon-reload
    else
      sudo systemctl stop "$unit" 2>/dev/null || true
      sudo systemctl disable "$unit" 2>/dev/null || true
      if [ "$path" != "-" ] && [ -f "$path" ]; then
        sudo rm -f "$path"
      fi
      sudo systemctl daemon-reload
    fi

    REMOVED_SYSTEMD_UNITS=$((REMOVED_SYSTEMD_UNITS + 1))
  done < "$LEGACY_SYSTEMD_REPORT"

  SYSTEMD_TEARDOWN_STATUS="removed ${REMOVED_SYSTEMD_UNITS} unit scope(s)"
  echo ""
  echo "Legacy systemd teardown complete: $SYSTEMD_TEARDOWN_STATUS"
fi
```

If the user skips teardown, set `SYSTEMD_TEARDOWN_STATUS="skipped"` and warn:

```
WARNING: Legacy systemd units were left installed. Stale units may still bind
MCP ports or restart old server versions. Run /cpp:update again and choose
teardown if you hit a port conflict with your MCP servers.
```

---

## Step 5: Runtime Refresh (no Docker stack)

CPP no longer builds or runs a Docker MCP stack. The second-opinion server is an
external project (https://github.com/cooneycw/mcp-second-opinion) that you run
yourself, and playwright runs via npx - so there is nothing for /cpp:update to
rebuild here. The git pull already refreshed the symlinked commands.

Retired MCP containers left on this host (mcp-second-opinion, aws-secrets-agent,
mcp-playwright-persistent, ...) are handled by the orphaned-Docker-MCP teardown
in Step 6c/7, not by a rebuild.

```bash
RUNTIME_STATUS="no Docker MCP stack (second-opinion external, playwright via npx)"
echo "$RUNTIME_STATUS"
```

---

## Step 5a: Shared Managed Host Refresh (PARTIAL, issue #1889)

Run the shared refresh even when Step3 pulled no commits: source currency does
not establish installed currency. This replaces the script/command link loops
and the separate Codex install. The driver discovers existing CPP installs;
CLI presence alone does not enroll a host, and each Claude link kind enrolls
independently. It forwards `CPP_DEFER_SURFACES` to the declared managers.
Never fall back to a legacy writer after a refusal or unavailable result.

The parent and pinned child use the same Python interpreter. Claude links and
Codex require only the standard library; selected Claude topics and AGY require
PyYAML and report their own named UNAVAILABLE result if it is absent. Keep the
full source revision for the final summary guard. Execute the checkout entry,
never a personal file preserved at an installed helper path.

```bash
# CPP_SHARED_REFRESH
CPP_DIR=REPLACE_WITH_CPP_DIR
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
HOST_REFRESH_REVISION=$(git -C "$CPP_DIR" rev-parse --verify HEAD 2>/dev/null)
HOST_REFRESH_STATUS=$(python3 -I -B - "$CPP_DIR" "$HOST_REFRESH_REVISION" <<'CPP_REFRESH_READER'
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

root, revision = Path(sys.argv[1]), sys.argv[2]
failure_code = 4
try:
    if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        raise ValueError("full source revision unavailable")
    if not (root / "scripts/cpp-host-update.py").is_file():
        raise ValueError("production entry unavailable; no fallback writer")
    failure_code = 1
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(root / "scripts/cpp-host-update.py"), "refresh",
         "--source-root", str(root), "--home", os.path.expanduser("~"),
         "--revision", revision, "--json", *sys.argv[3:]],
        capture_output=True, text=True, timeout=360)
    print(result.stderr, end="", file=sys.stderr)
    report = json.loads(result.stdout)
    sys.path.insert(0, str(root))
    from lib.host_update.source import valid_report
    producer_revision = revision
    if (result.returncode in (1, 4, 5) and report.get("revision") == ""
            and all(row["action"] in ("not-attempted", "refused") for row in report["results"])):
        # Discovery/refusal can finish before any source is bound or write attempted.
        producer_revision = ""
    if not valid_report(report, result.returncode, producer_revision):
        raise ValueError("incomplete or inconsistent production report; inspect installed state")
    finish = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    if finish != revision:
        raise ValueError("source revision changed during refresh; inspect installed state")
    states = {0: "current", 1: "failure", 4: "UNAVAILABLE", 5: "not-applicable"}
    print(f"Managed refresh: {states[result.returncode]} (coverage=partial; native effectiveness unexamined)")
    print(f"Revision: {revision}")
    for row in report["results"]:
        after = row["after"]
        print(f"{row['harness']}: {after['state']}; {row['action']}; exit {row['exit_code']}; "
              f"packages={after['expected_packages']}; "
              f"members={after['examined_members']}/{after['expected_members']}")
        for detail in (row["reason"], row["remedy"]):
            if detail:
                print("  " + detail.replace("\n", " "))
        for conflict in after.get("conflicts", []):
            print(f"  {conflict['package']}: {conflict['state']}; " + conflict['reason'].replace("\n", " "))
        if row["harness"] == "codex" and row["reason"] == "legacy packages require explicit reviewed migration":
            from lib.host_update.scope import slug
            stale = sorted(slug(c["package"]) for c in after["conflicts"] if c["state"] == "unknown")
            unexpected = sorted(c["package"] for c in after["conflicts"] if c["state"] == "unmanaged")
            print("Codex refresh frozen: unverified legacy packages require review; no adoption has run.")
            if unexpected:
                print("Unexpected legacy packages preserved; separate review required before migration: "
                      + ", ".join(unexpected))
            elif stale:
                flags = [v for name in stale for v in ("--adopt", "codex:" + name)]
                print("Codex migration packages: " + " ".join(stale))
                print("Codex migration command: " + shlex.join(
                    ["python3", "-I", "-B", str(root / "scripts/cpp-host-update.py"), "refresh",
                     "--source-root", str(root), "--home", os.path.expanduser("~"),
                     "--revision", revision, "--json", *flags]))
    print("Deferred coverage: " + "; ".join(report["unimplemented"]))
except Exception as error:
    state = "failure" if failure_code == 1 else "UNAVAILABLE"
    print(f"Managed refresh: {state} - " + str(error).replace("\n", " "))
    print(f"Revision: {revision or 'unavailable'}")
    raise SystemExit(failure_code)
raise SystemExit(result.returncode)
CPP_REFRESH_READER
)
HOST_REFRESH_EXIT=$?
case "$HOST_REFRESH_EXIT" in
  0|1|4|5) ;;
  *) HOST_REFRESH_EXIT=4
     HOST_REFRESH_STATUS="Managed refresh: UNAVAILABLE - shared reader did not complete; inspect installed state" ;;
esac
printf '%s\n' "$HOST_REFRESH_STATUS"
printf 'Managed refresh exit: %s\n' "$HOST_REFRESH_EXIT"
exit "$HOST_REFRESH_EXIT"
```

If the refresh prints `Codex migration packages:`, show that exact named list
and `Codex migration command:`. Ask ONCE with AskUserQuestion whether to adopt
that list. Only then run the migration fence; otherwise skip it. These bytes may contain edits: there is no verified prior manifest.
The shared core retains each original package in its transaction backup before
replacing it; the result names the recovery location. Explain this before asking.
Bind the printed revision, package names, initial exit1/4 and explicit yes/no
as literals below. Use `no` on decline; never default an absent answer to yes.
Never infer consent from CLI presence, a CPP marker, silence or an earlier run.
Retired/unexpected packages are listed separately, preserved and never adopted;
when present they require separate review before any migration is offered.
A byte-identical legacy install bootstraps its record without this question.

```bash
# CPP_CODEX_MIGRATION
CPP_DIR=REPLACE_WITH_CPP_DIR
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
HOST_REFRESH_REVISION=REPLACE_WITH_REFRESH_REVISION
HOST_MIGRATION_PACKAGES=(REPLACE_WITH_REVIEWED_PACKAGES)
CODEX_MIGRATION_CONFIRMED=REPLACE_WITH_DECISION
HOST_INITIAL_EXIT=REPLACE_WITH_INITIAL_EXIT
[[ "$HOST_REFRESH_REVISION" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]] || exit 4
case "$CODEX_MIGRATION_CONFIRMED:$HOST_INITIAL_EXIT" in yes:4|yes:1|no:4|no:1) ;; *) exit 4 ;; esac
((${#HOST_MIGRATION_PACKAGES[@]})) || exit 4
HOST_MIGRATION_ARGS=()
for package in "${HOST_MIGRATION_PACKAGES[@]}"; do
  [[ "$package" =~ ^[a-z0-9][a-z0-9-]*$ ]] || exit 4
  HOST_MIGRATION_ARGS+=(--adopt "codex:$package")
done
HOST_MIGRATION_COMMAND=(python3 -I -B "$CPP_DIR/scripts/cpp-host-update.py" refresh
  --source-root "$CPP_DIR" --home "$HOME" --revision "$HOST_REFRESH_REVISION" "${HOST_MIGRATION_ARGS[@]}")
if [ "$CODEX_MIGRATION_CONFIRMED" = no ]; then
  printf 'Codex refresh frozen: migration declined; run after review: '
  printf '%q ' "${HOST_MIGRATION_COMMAND[@]}"; printf '\n'
  exit "$HOST_INITIAL_EXIT"
fi
if [ "$(git -C "$CPP_DIR" rev-parse --verify HEAD 2>/dev/null)" != "$HOST_REFRESH_REVISION" ]; then
  echo 'Managed refresh: UNAVAILABLE - revision changed before migration; no adoption run'
  exit 4
fi
"${HOST_MIGRATION_COMMAND[@]}"
```

Use the latest actual Step5a per-component report and exit in Step10 (migration
report when approved; original report plus frozen command when declined). Exit0 means all selected components are current at the
bound revision; exit1 means failure or preserved conflicts; exit4 means
unexamined/unavailable; exit5 means no applicable existing installation.
Failures continue the unrelated update steps, but never become a success claim.
Preserve personal, foreign, hand-edited and deferred entries; offer their named
remedy separately. Only the named migration above permits reviewed adoption;
no automatic adoption or tier upgrade is authorized here.

For links, only proven retired dangling entries may be removed. A retired
executable kind whose target still exists stays as an unmanaged conflict with
exit1. The shared ownership proof also preserves foreign-checkout dangling,
unproven and relative links that legacy confirmed pruning could delete.

---

## Step 5b.1: Shared-Stash Guard Refresh (ON BY DEFAULT, issue #1056)

The guard is a git `reference-transaction` hook, so unlike the symlinks above it
does NOT follow `git pull` - it is a COPY in `.git/hooks/`, deliberately, because
a symlink into a checkout that is later moved or deleted leaves a dangling hook
in every worktree of the repository. A copy goes stale instead, which is
recoverable and reported. So this step refreshes it.

This is also the step that makes the guard true for the repository `/cpp:update`
runs in, which is exactly where the #1056 orphan was found: `/cpp:update`'s own
Step 3 pushed to the shared stack and never restored.

Bare (resolution order per #581/#590; on exit 127 fall back to
`"$CPP_DIR/scripts/stash-worktree-guard.sh"`):

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
~/.claude/scripts/stash-worktree-guard.sh --install "$CPP_DIR"
```

Act on `STASH_GUARD:`:

- `installed` - it was absent or stale and is now armed. Report it.
- `current` - nothing to do.
- `disabled` - the repository recorded `cpp.stashGuard=false`. **Leave it off,
  and do not re-offer.** An opt-out that is re-asked on every update is not an
  opt-out; it is the oscillation ADR 0009 predicts, arriving as the remedy.
  Report it as a state, in one line, so the user can see it is off on purpose:
  `→ Shared-stash guard: off for this repo (cpp.stashGuard=false; --enable to turn back on)`
- `foreign` - a different `reference-transaction` hook is installed. Report it
  and change nothing; merging the two is the user's call.
- `unsupported` - git below 2.28, or a RELATIVE `core.hooksPath`. Report the
  reason rather than a bare failure.
- No `STASH_GUARD:` line - the guard did not run, which is NOT `unsupported`, and
  the exit-127 fallback does not apply. Only when Step 3.6 reported exit 1 with
  `UNSUPPORTED bash` and this is a shell `syntax error` (issue #1628), report
  `→ Shared-stash guard: NOT installed (bash below floor)`. Otherwise old bash is
  not the established cause: report `→ Shared-stash guard: NOT installed (cause
  unknown)` with the helper's own diagnostic. Either way, continue.

**Turning it off from here** is the same one action that records the choice:

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
~/.claude/scripts/stash-worktree-guard.sh --uninstall "$CPP_DIR"
```

Offer that only if the user asks, or if this run is the FIRST to install it
here - never as a recurring prompt. See `docs/agents/shared-stash-stack.md`.

---

## Step 5c: Command-Surface Result

Read the `claude-links` row from Step5a. Its result covers tracked source bytes,
executable modes and expected link membership, with personal/foreign conflicts
preserved. No second command-link installer runs here. A current link row does
not establish native runtime effectiveness or marketplace-cache currency.

**Marketplace-cache migration (#662 / ADR 0005):** while the retired `/plugin`
families remain installed, sessions may read the STALE cached copies instead of
these symlinks. If `~/.claude/plugins/cache/cpp/` still contains CPP families,
print the uninstall list and recommend running it (user-typed CLI built-ins -
this command cannot run them):

```
/plugin uninstall <family>@cpp    # for each family present in the cache
```

---

## Step 5d: Local-Model Lane Refresh (Tiers 6/7)

Local-model harnesses and configuration do not follow the checkout symlinks.
Refresh them separately so an existing Tier 6 or Tier 7 host sees harness
upgrades and, most importantly, the current Gemma permission profile
(issue #754). Update is not an installer: detect the lanes first and never
create a lane that the user did not already select.

#### 5d.1 Detect the Installed Lanes

Tier 6 is present only when the Qwen Code harness is on `PATH`. Tier 7 is
present when the OpenCode harness is on `PATH` OR the existing OpenCode config
contains the `gemma-ollama` provider. The config signal is independent because
the provider and mechanical fence still need refreshing when an installed
OpenCode binary is temporarily unavailable.

```bash
OC_CONFIG="$HOME/.config/opencode/opencode.json"
QWEN_LANE_PRESENT=false
OPENCODE_HARNESS_PRESENT=false
GEMMA_CONFIG_PRESENT=false
GEMMA_LANE_PRESENT=false
LOCAL_MODEL_LANE_STATUS_PARTS=()

if command -v qwen &>/dev/null; then
  QWEN_LANE_PRESENT=true
fi

if command -v opencode &>/dev/null; then
  OPENCODE_HARNESS_PRESENT=true
fi

has_gemma_provider() {
  [ -f "$OC_CONFIG" ] || return 1
  PYTHONPATH= python3 - "$OC_CONFIG" <<'PYEOF'
import json, sys, pathlib
cfg_path = pathlib.Path(sys.argv[1])
try:
    cfg = json.loads(cfg_path.read_text())
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
raise SystemExit(0 if "gemma-ollama" in cfg.get("provider", {}) else 1)
PYEOF
}

if has_gemma_provider; then
  GEMMA_CONFIG_PRESENT=true
fi

if $OPENCODE_HARNESS_PRESENT || $GEMMA_CONFIG_PRESENT; then
  GEMMA_LANE_PRESENT=true
fi

if ! $QWEN_LANE_PRESENT && ! $GEMMA_LANE_PRESENT; then
  echo "-> Local-model lanes not installed (Tier 6/7 not selected) - skipped"
else
  if ! $QWEN_LANE_PRESENT; then
    echo "-> Tier 6 Qwen lane not installed - skipped"
  fi
  if ! $GEMMA_LANE_PRESENT; then
    echo "-> Tier 7 Gemma lane not installed - skipped"
  fi
fi
declare -p QWEN_LANE_PRESENT OPENCODE_HARNESS_PRESENT GEMMA_CONFIG_PRESENT GEMMA_LANE_PRESENT LOCAL_MODEL_LANE_STATUS_PARTS
```

When neither lane is present, skip the lane refresh subsections. Do not prompt
and do not install either harness. Still compose the Step 10 value at the end
of Step 5d before continuing to Step 6.

#### 5d.2 Refresh Tier 6 (Local Qwen)

Only run this subsection when `QWEN_LANE_PRESENT=true`. Report the installed
version, retain the headless-mode probe from `/cpp:init`, and flag the retired
Codex-harness environment variable so remote consumers do not carry obsolete
configuration forward.

```bash
QWEN_LANE_VERDICT="not examined (lane absent)"
: "${QWEN_LANE_PRESENT:?bind the printed true/false literal in this call}"
case "$QWEN_LANE_PRESENT" in true|false) ;; *) exit 4 ;; esac
if $QWEN_LANE_PRESENT; then
  echo ""
  echo "=== Tier 6: Local Qwen Orchestration ==="
  echo ""

  QWEN_CLI_VERSION=$(qwen --version 2>/dev/null || echo "unknown")
  QWEN_LANE_VERDICT="checked (no upgrade offered)"
  echo "[x] Qwen Code CLI harness: $QWEN_CLI_VERSION"
  if ! qwen --help 2>&1 | grep -q -- "--output-format"; then
    echo "[!] This Qwen Code version lacks headless stream-json support"
    echo "    Upgrade below - and read its verdict: on a host whose node is too"
    echo "    old for the current release, the upgrade cannot deliver the feature"
    echo "    this probe is asking for (issue #1022)."
  fi

  # Flag the retired Codex-harness env var if still set (issue #745)
  if [ -n "$QWEN_CODEX_PROFILE" ]; then
    echo "[~] QWEN_CODEX_PROFILE is set but no longer used (Codex harness retired,"
    echo "    issue #745). Remote machines need only QWEN_OLLAMA_URL. Unset it."
  fi
fi
declare -p QWEN_LANE_VERDICT
```

When `QWEN_LANE_PRESENT=true`, OFFER to upgrade the already-installed harness.
Ask the user, then upgrade only if the answer is yes. Never offer or run the
upgrade when `qwen` was absent.

Use `npm-global-upgrade.sh` to report the actual version transition, engine
ceiling or unknown result; npm exit0 alone cannot establish an upgrade (#1022).
The helper compares installed versions and the latest package's node requirement.

```bash
: "${QWEN_LANE_VERDICT:?bind the printed literal in this call}"
[[ "$QWEN_LANE_VERDICT" != *REPLACE_WITH* && "$QWEN_LANE_VERDICT" != *$'\n'* ]] || exit 4
: "${QWEN_UPGRADE_CONFIRMED:?bind the explicit yes/no answer from this run}"
case "$QWEN_UPGRADE_CONFIRMED" in yes|no) ;; *) exit 4 ;; esac
: "${QWEN_LANE_PRESENT:?bind the printed true/false literal in this call}"
case "$QWEN_LANE_PRESENT" in true|false) ;; *) exit 4 ;; esac
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
if $QWEN_LANE_PRESENT && [ "$QWEN_UPGRADE_CONFIRMED" = "yes" ]; then
  # Same resolution order as every other CPP helper: the stable installed path
  # first (Step 5 has already refreshed those symlinks), then the checkout.
  NPM_UPGRADE_SH="$HOME/.claude/scripts/npm-global-upgrade.sh"
  [ -f "$NPM_UPGRADE_SH" ] || NPM_UPGRADE_SH="$CPP_DIR/scripts/npm-global-upgrade.sh"

  # A global install needs sudo wherever the npm prefix is root-owned. Decide it
  # once rather than discovering it from an EACCES the verdict then has to
  # explain.
  QWEN_UPGRADE_ARGS=(--package @qwen-code/qwen-code --binary qwen --label "Tier 6 Qwen Code")
  NPM_PREFIX=$(npm config get prefix 2>/dev/null)
  if [ -n "$NPM_PREFIX" ] && [ ! -w "$NPM_PREFIX/lib/node_modules" ]; then
    QWEN_UPGRADE_ARGS+=(--sudo)
  fi

  if [ -f "$NPM_UPGRADE_SH" ]; then
    # The exit code is deliberately NOT the verdict here: `capped` exits 1 and is
    # a truthful report about this host, not a broken update run. Read the marker
    # line, report it, and carry on.
    QWEN_UPGRADE_OUT=$(sh "$NPM_UPGRADE_SH" "${QWEN_UPGRADE_ARGS[@]}" 2>&1) || true
    printf '%s\n' "$QWEN_UPGRADE_OUT"
    QWEN_LANE_VERDICT=$(printf '%s\n' "$QWEN_UPGRADE_OUT" | sed -n 's/^NPM_UPGRADE: //p' | head -1)
    # An absent marker means the helper produced no verdict at all. That is not
    # an upgrade; it is an unmeasured host, and it must not read like one that
    # was measured and found fine.
    [ -n "$QWEN_LANE_VERDICT" ] || QWEN_LANE_VERDICT="unknown (the upgrade helper emitted no verdict)"
  else
    QWEN_LANE_VERDICT="unknown (npm-global-upgrade.sh is not installed; upgrade NOT attempted)"
    echo "[!] $QWEN_LANE_VERDICT - run /flow:repair or re-run /cpp:update after the pull."
  fi
fi
declare -p QWEN_LANE_VERDICT
```

Bind `QWEN_UPGRADE_CONFIRMED` to this run's explicit yes/no answer in this call;
`no` retains the printed prior verdict.

Then mirror the Tier 6 Ollama reachability and model checks from `/cpp:init`.
The environment variable names and defaults must stay identical so serving and
consumer machines get the same diagnosis from both commands:

```bash
[[ "$(declare -p LOCAL_MODEL_LANE_STATUS_PARTS 2>/dev/null)" == 'declare -a '* ]] || exit 4
for part in "${LOCAL_MODEL_LANE_STATUS_PARTS[@]}"; do
  [[ -n "$part" && "$part" != *REPLACE_WITH* ]] || exit 4
done
: "${QWEN_LANE_VERDICT:?bind the printed literal in this call}"
[[ "$QWEN_LANE_VERDICT" != *REPLACE_WITH* && "$QWEN_LANE_VERDICT" != *$'\n'* ]] || exit 4
: "${QWEN_LANE_PRESENT:?bind the printed true/false literal in this call}"
case "$QWEN_LANE_PRESENT" in true|false) ;; *) exit 4 ;; esac
if $QWEN_LANE_PRESENT; then
  QWEN_ENDPOINT="${QWEN_OLLAMA_URL:-http://127.0.0.1:11434}"
  QWEN_MODEL="${QWEN_MODEL:-qwen3.8-code:latest}"

  if curl -sf --max-time 5 "$QWEN_ENDPOINT/api/version" > /dev/null; then
    echo "[x] Ollama reachable at $QWEN_ENDPOINT"
    # Only judge model presence after a readable endpoint/model list (#1263).
    if TAGS=$(curl -sf --max-time 5 "$QWEN_ENDPOINT/api/tags" 2>/dev/null) \
     && echo "$TAGS" | grep -q '"models"'; then
      if echo "$TAGS" | grep -qF "\"$QWEN_MODEL\""; then
        echo "[x] Model present: $QWEN_MODEL"
      else
        echo "[ ] Model '$QWEN_MODEL' missing"
        echo "    On the serving machine:"
        echo "      ollama pull qwen3.8:27b"
        echo "      printf 'FROM qwen3.8:27b\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.7\nPARAMETER top_p 0.8\n' | ollama create qwen3.8-code -f -"
      fi
    else
      echo "[?] Model '$QWEN_MODEL' unknown (the model list could not be read from $QWEN_ENDPOINT)"
    fi
  else
    echo "[ ] Ollama NOT reachable at $QWEN_ENDPOINT"
    echo "    Serving machine: install and start Ollama (brew install ollama on macOS),"
    echo "    bind to the network with OLLAMA_HOST=0.0.0.0:11434 for LAN/tailnet use."
    echo "    Consumer machine: set QWEN_OLLAMA_URL=http://<serving-ip>:11434"
    echo "[?] Model '$QWEN_MODEL' unknown (endpoint unreachable - not checked)"
  fi

  # Carry the measured harness verdict into the lane summary (#1022).
  echo "✓ Tier 6 Qwen lane checked: Ollama/model above; harness $QWEN_LANE_VERDICT"
  LOCAL_MODEL_LANE_STATUS_PARTS+=("Tier 6 harness $QWEN_LANE_VERDICT")
fi
declare -p LOCAL_MODEL_LANE_STATUS_PARTS
```

#### 5d.3 Refresh Tier 7 (Local Gemma)

Only run the Tier 7 checks when `GEMMA_LANE_PRESENT=true`. An existing
OpenCode harness gets a version report and an offered upgrade. If the provider
is the only presence signal, report the absent harness but do not install it;
the config re-merge below must still run.

```bash
GEMMA_HARNESS_VERDICT="not examined (lane absent)"
: "${GEMMA_LANE_PRESENT:?bind the printed true/false literal in this call}"
case "$GEMMA_LANE_PRESENT" in true|false) ;; *) exit 4 ;; esac
: "${OPENCODE_HARNESS_PRESENT:?bind the printed true/false literal in this call}"
case "$OPENCODE_HARNESS_PRESENT" in true|false) ;; *) exit 4 ;; esac
if $GEMMA_LANE_PRESENT; then
  echo ""
  echo "=== Tier 7: Local Gemma Orchestration ==="
  echo ""

  GEMMA_HARNESS_VERDICT="checked (no upgrade offered)"
  if $OPENCODE_HARNESS_PRESENT; then
    echo "[x] OpenCode harness: $(opencode --version 2>/dev/null)"
  else
    GEMMA_HARNESS_VERDICT="absent (install/upgrade skipped; config refresh only)"
    echo "[~] OpenCode harness absent - install/upgrade skipped; config refresh only"
  fi
fi
declare -p GEMMA_HARNESS_VERDICT
```

When `OPENCODE_HARNESS_PRESENT=true`, OFFER to upgrade the already-installed
harness. Ask the user, then upgrade only if the answer is yes. Never upgrade
without explicit confirmation.

Use the same transition-reporting npm helper as Tier6 (issue #1022).

```bash
: "${GEMMA_HARNESS_VERDICT:?bind the printed literal in this call}"
[[ "$GEMMA_HARNESS_VERDICT" != *REPLACE_WITH* && "$GEMMA_HARNESS_VERDICT" != *$'\n'* ]] || exit 4
: "${GEMMA_UPGRADE_CONFIRMED:?bind the explicit yes/no answer from this run}"
case "$GEMMA_UPGRADE_CONFIRMED" in yes|no) ;; *) exit 4 ;; esac
: "${OPENCODE_HARNESS_PRESENT:?bind the printed true/false literal in this call}"
case "$OPENCODE_HARNESS_PRESENT" in true|false) ;; *) exit 4 ;; esac
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
if $OPENCODE_HARNESS_PRESENT && [ "$GEMMA_UPGRADE_CONFIRMED" = "yes" ]; then
  NPM_UPGRADE_SH="$HOME/.claude/scripts/npm-global-upgrade.sh"
  [ -f "$NPM_UPGRADE_SH" ] || NPM_UPGRADE_SH="$CPP_DIR/scripts/npm-global-upgrade.sh"

  GEMMA_UPGRADE_ARGS=(--package opencode-ai --binary opencode --label "Tier 7 OpenCode")
  NPM_PREFIX=$(npm config get prefix 2>/dev/null)
  if [ -n "$NPM_PREFIX" ] && [ ! -w "$NPM_PREFIX/lib/node_modules" ]; then
    GEMMA_UPGRADE_ARGS+=(--sudo)
  fi

  if [ -f "$NPM_UPGRADE_SH" ]; then
    GEMMA_UPGRADE_OUT=$(sh "$NPM_UPGRADE_SH" "${GEMMA_UPGRADE_ARGS[@]}" 2>&1) || true
    printf '%s\n' "$GEMMA_UPGRADE_OUT"
    GEMMA_HARNESS_VERDICT=$(printf '%s\n' "$GEMMA_UPGRADE_OUT" | sed -n 's/^NPM_UPGRADE: //p' | head -1)
    [ -n "$GEMMA_HARNESS_VERDICT" ] || GEMMA_HARNESS_VERDICT="unknown (the upgrade helper emitted no verdict)"
  else
    GEMMA_HARNESS_VERDICT="unknown (npm-global-upgrade.sh is not installed; upgrade NOT attempted)"
    echo "[!] $GEMMA_HARNESS_VERDICT - run /flow:repair or re-run /cpp:update after the pull."
  fi
fi
declare -p GEMMA_HARNESS_VERDICT
```

Bind `GEMMA_UPGRADE_CONFIRMED` to this run's explicit yes/no answer in this call;
`no` retains the printed prior verdict.

Mirror the Tier 7 Ollama checks for either Tier 7 presence signal:

```bash
: "${GEMMA_LANE_PRESENT:?bind the printed true/false literal in this call}"
case "$GEMMA_LANE_PRESENT" in true|false) ;; *) exit 4 ;; esac
if $GEMMA_LANE_PRESENT; then
  GEMMA_ENDPOINT="${GEMMA_OLLAMA_URL:-http://127.0.0.1:11434}"
  GEMMA_MODEL="${GEMMA_MODEL:-gemma4-code:latest}"

  if curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/version" > /dev/null; then
    echo "[x] Ollama reachable at $GEMMA_ENDPOINT"
    # Only judge model presence after a readable endpoint/model list (#1263).
    if TAGS=$(curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/tags" 2>/dev/null) \
     && echo "$TAGS" | grep -q '"models"'; then
      if echo "$TAGS" | grep -qF "\"$GEMMA_MODEL\""; then
        echo "[x] Model present: $GEMMA_MODEL"
      else
        echo "[ ] Model '$GEMMA_MODEL' missing"
        echo "    On the serving machine:"
        echo "      ollama pull gemma4:31b-it-qat"
        echo "      printf 'FROM gemma4:31b-it-qat\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.2\n' > /tmp/Modelfile.gemma4-code"
        echo "      ollama create gemma4-code -f /tmp/Modelfile.gemma4-code"
        echo "    Then confirm 'ollama ps' still reports 100% GPU: the 64K context"
        echo "    bump costs VRAM, and one layer spilling to CPU collapses throughput."
      fi
    else
      echo "[?] Model '$GEMMA_MODEL' unknown (the model list could not be read from $GEMMA_ENDPOINT)"
    fi
  else
    echo "[ ] Ollama NOT reachable at $GEMMA_ENDPOINT"
    echo "    Serving machine: start it ('ollama serve') and retry."
    echo "    Consumer machine: set GEMMA_OLLAMA_URL=http://<serving-host>:11434"
    echo "    Shared-GPU host: another VM may currently hold the card."
    echo "[?] Model '$GEMMA_MODEL' unknown (endpoint unreachable - not checked)"
  fi
fi
```

Re-merge only when `GEMMA_CONFIG_PRESENT=true`. This is not an install path:
an absent `gemma-ollama` provider means Tier 7 configuration was not selected
on this host, so leave the config untouched. Reuse the non-destructive init
merge so unrelated providers and agents remain unchanged. Before merging,
compare the two owned blocks so the verdict identifies what changed and what
was already current.

```bash
OC_CONFIG="$HOME/.config/opencode/opencode.json"
GEMMA_PROFILE_STATUS="not examined (lane absent)"
: "${GEMMA_CONFIG_PRESENT:?bind the printed true/false literal in this call}"
case "$GEMMA_CONFIG_PRESENT" in true|false) ;; *) exit 4 ;; esac
: "${GEMMA_LANE_PRESENT:?bind the printed true/false literal in this call}"
case "$GEMMA_LANE_PRESENT" in true|false) ;; *) exit 4 ;; esac
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
if $GEMMA_CONFIG_PRESENT; then
  GEMMA_PROFILE_STATUS=$(PYTHONPATH= python3 - \
    "$CPP_DIR/templates/opencode-gemma.json" "$OC_CONFIG" <<'PYSTATUS'
import json, sys, pathlib
tmpl_path, cfg_path = sys.argv[1], pathlib.Path(sys.argv[2])
tmpl = json.loads(pathlib.Path(tmpl_path).read_text())
cfg = json.loads(cfg_path.read_text())
states = []
for section, name, label in (
    ("provider", "gemma-ollama", "gemma-ollama provider"),
    ("agent", "gemma-implementer", "gemma-implementer mechanical fence"),
):
    current = cfg.get(section, {}).get(name) == tmpl[section][name]
    states.append(f"{label} {'already current' if current else 'refreshed'}")
print("; ".join(states))
PYSTATUS
  )

  # Through the declaring seam (#1132). This merge was embedded PYTHON, which is
  # why no shell pattern found it: a cfg_path.write_text() satisfies no grep for
  # a redirect, cp, tee, mv or ln. Same .update() semantics, moved not improved.
  "$CPP_DIR/scripts/cpp-host-write.sh" json-merge-sections \
    "$CPP_DIR/templates/opencode-gemma.json" "$OC_CONFIG" provider agent
  #: $GEMMA_PROFILE_STATUS was computed BEFORE the merge, so on its own it
  #: describes the state the merge was meant to change - printing it
  #: unconditionally reported a refreshed profile over a refusal (issue #1198).
  case $? in
    0) : ;;
    3) GEMMA_PROFILE_STATUS="DEFERRED by request - the profile was NOT merged" ;;
    *) GEMMA_PROFILE_STATUS="NOT merged (the seam failed or is not installed)" ;;
  esac

  echo "✓ Tier 7 Gemma profile: $GEMMA_PROFILE_STATUS"
  echo "    Re-merge keeps the gemma-implementer mechanical fence from going stale."
elif $GEMMA_LANE_PRESENT; then
  GEMMA_PROFILE_STATUS="no gemma-ollama provider selected; mechanical fence skipped"
  echo "-> Tier 7 Gemma profile not installed (no gemma-ollama provider) - skipped"
fi
declare -p GEMMA_PROFILE_STATUS
```

Finish the Tier 7 report with one lane verdict after the harness, server/model,
and eligible profile checks have run:

```bash
[[ "$(declare -p LOCAL_MODEL_LANE_STATUS_PARTS 2>/dev/null)" == 'declare -a '* ]] || exit 4
for part in "${LOCAL_MODEL_LANE_STATUS_PARTS[@]}"; do
  [[ -n "$part" && "$part" != *REPLACE_WITH* ]] || exit 4
done
: "${GEMMA_HARNESS_VERDICT:?bind the printed literal in this call}"
[[ "$GEMMA_HARNESS_VERDICT" != *REPLACE_WITH* && "$GEMMA_HARNESS_VERDICT" != *$'\n'* ]] || exit 4
: "${GEMMA_PROFILE_STATUS:?bind the printed literal in this call}"
[[ "$GEMMA_PROFILE_STATUS" != *REPLACE_WITH* && "$GEMMA_PROFILE_STATUS" != *$'\n'* ]] || exit 4
: "${GEMMA_LANE_PRESENT:?bind the printed true/false literal in this call}"
case "$GEMMA_LANE_PRESENT" in true|false) ;; *) exit 4 ;; esac
if $GEMMA_LANE_PRESENT; then
  # Carries the harness verdict for the same reason Tier 6 does (issue #1022):
  # the profile status alone said nothing about whether the harness moved.
  echo "✓ Tier 7 Gemma lane checked: harness $GEMMA_HARNESS_VERDICT; $GEMMA_PROFILE_STATUS"
  LOCAL_MODEL_LANE_STATUS_PARTS+=("Tier 7 harness $GEMMA_HARNESS_VERDICT ($GEMMA_PROFILE_STATUS)")
fi
declare -p LOCAL_MODEL_LANE_STATUS_PARTS
```

Compose the Step 10 value only after every present lane has contributed its
outcome. A lane skipped by presence gating contributes nothing:

```bash
[[ "$(declare -p LOCAL_MODEL_LANE_STATUS_PARTS 2>/dev/null)" == 'declare -a '* ]] || exit 4
for part in "${LOCAL_MODEL_LANE_STATUS_PARTS[@]}"; do
  [[ -n "$part" && "$part" != *REPLACE_WITH* ]] || exit 4
done
if ((${#LOCAL_MODEL_LANE_STATUS_PARTS[@]})); then
  printf -v LOCAL_MODEL_LANES_STATUS '%s; ' "${LOCAL_MODEL_LANE_STATUS_PARTS[@]}"
  LOCAL_MODEL_LANES_STATUS="${LOCAL_MODEL_LANES_STATUS%; }"
else
  LOCAL_MODEL_LANES_STATUS="not installed (Tier 6/7 not selected)"
fi
printf "%s\n" "$LOCAL_MODEL_LANES_STATUS"
```

---

## Step 6: MCP Server Drift Detection

After pulling, scan for drift between what CPP expects and what is actually
installed/running on this host. CPP no longer runs a Docker MCP stack, so the
findings that matter now are: retired MCP containers/images/registrations left
behind (torn down via Step 6c/7), legacy systemd units, and stale MCP
registrations. Any remaining systemd unit is a legacy migration finding, not a
runtime option to repair or restart.

### 6a: Build Inventory

Build two lists - what CPP expects vs what is installed/running on this host -
then compare.

**Repo inventory** - what CPP expects for MCP servers now:

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
cd "$CPP_DIR" || exit 4

echo "=== Repo MCP Server Inventory ==="

# CPP no longer ships a Docker MCP stack. It expects:
echo "  second-opinion - external streamable-http server, user scope only (default :8080/mcp)"
echo "  playwright      - upstream @playwright/mcp via npx/stdio"

echo ""
echo "Retired servers (curated in .claude/deprecated-mcps.yaml, torn down as"
echo "orphans by Step 6c/7):"
grep -E '^\s{2}- name:' .claude/deprecated-mcps.yaml | sed 's/- name:/  -/'
```

**Installed inventory** - scan what is currently running/registered:

```bash
echo ""
echo "=== Installed MCP Inventory ==="

echo "MCP registrations (claude mcp list):"
claude mcp list 2>/dev/null | sed 's/^/  /' || echo "  (none)"

echo ""
echo "Leftover MCP containers (retired; torn down by Step 6c/7):"
if command -v docker &>/dev/null; then
  docker ps -a --format '{{.Names}}' 2>/dev/null \
    | grep -E '^(mcp-second-opinion|aws-secrets-agent|mcp-playwright-persistent|mcp-nano-banana|mcp-woodpecker-ci|mcp-coordination)$' \
    | sed 's/^/  /' || echo "  (none)"
else
  echo "  (docker unavailable)"
fi

echo ""
echo "Legacy systemd units (migration required if present):"
LEGACY_SYSTEMD_INVENTORY="$(
  {
    find "$HOME/.config/systemd/user" /etc/systemd/system -maxdepth 1 -type f \
      \( -name 'mcp-*.service' -o -name 'nano-*.service' -o -name '*coordination*.service' \) \
      -printf '%f\n' 2>/dev/null || true
    systemctl --user list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    systemctl --user list-unit-files --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    systemctl list-unit-files --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
  } | sed 's/\.service$//' | grep -E '^(mcp-|nano-|.*coordination|second-opinion|playwright-persistent|evaluate|coordination)$' | sort -u || true
)"
if [ -n "$LEGACY_SYSTEMD_INVENTORY" ]; then
  printf '%s\n' "$LEGACY_SYSTEMD_INVENTORY"
else
  echo "  (none)"
fi
```

Run the drift helper for its raw inventory if available:

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
if [ -x "$CPP_DIR/scripts/drift-detect.sh" ]; then
  "$CPP_DIR/scripts/drift-detect.sh" --fix || DRIFT_FOUND=true
fi
```

### 6b: Detect Drift

#### 6b.0: Second-Opinion Registration (legacy migration, issue #1256)

Until #1256, CPP shipped a tracked root `.mcp.json` that defined `second-opinion`
at PROJECT scope. That was a second definition beside the USER-scope one
`/cpp:init` registers, and whenever the two differed - a stdio server, a
Tailscale URL, a hand edit - Claude Code saw `[Conflicting scopes]` and which one
a session reached depended on the directory it started in. The per-host escape,
`disabledMcpjsonServers` in `~/.claude.json`, is keyed per path (every worktree
still conflicted) and was lost to a concurrent session rewriting that file.

The pull in Step 3 deleted `.mcp.json`, which removes the competing definition
for every checkout and worktree at once. An install that relied on it has no
`second-opinion` left, so register it at user scope - the same command and the
same guard as `/cpp:init` step 3c. An install that already has a user-scope
entry keeps it untouched, whatever its transport or URL: that is the owner's
chosen wiring, and now the only one.

```bash
# Check user scope in the active profile; register only on established absence.
USER_JSON="${CLAUDE_CONFIG_DIR:-$HOME}/.claude.json"
python3 - "$USER_JSON" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
except FileNotFoundError:
    sys.exit(1)  # only a missing file is an established absence
except (OSError, ValueError):
    sys.exit(3)  # permission denied, a directory, bad JSON: unknown
servers = data.get("mcpServers", {}) if isinstance(data, dict) else None
if not isinstance(servers, dict):
    sys.exit(3)
if "second-opinion" not in servers:
    sys.exit(1)
sys.exit(0 if isinstance(servers["second-opinion"], dict) else 3)
PY
SO_USER_RC=$?
if [ "$SO_USER_RC" -eq 0 ]; then
  SO_REGISTRATION_STATUS="already at user scope"
  echo "→ second-opinion already registered at user scope (left untouched)"
elif [ "$SO_USER_RC" -ne 1 ]; then
  SO_REGISTRATION_STATUS="NOT ASSESSED (user config unreadable)"
  echo "? could not read $USER_JSON (unreadable or not the expected shape) - registered nothing"
elif claude mcp add --transport http --scope user second-opinion "${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp"; then
  SO_REGISTRATION_STATUS="registered at user scope"
  echo "✓ second-opinion registered at user scope (no user-scope entry existed)"
else
  SO_REGISTRATION_STATUS="FAILED"
  echo "✗ second-opinion user-scope registration FAILED (see the error above)"
fi
```

For a server that is not on localhost, the user exports `SECOND_OPINION_URL`
(base URL, no `/mcp`) before this step; the user scope expands it once, at
registration, so changing it later means `claude mcp remove second-opinion -s
user` and this step again. A `disabledMcpjsonServers` entry for
`second-opinion` left over from the old workaround now disables nothing and is
harmless; leave it.

Compare the inventories and classify each finding. Use the following logic:

**Expected servers** (what CPP wires now, registration-only - no containers):
- `second-opinion` - external streamable-http server, registered at USER scope
  only (Step 6b.0); CPP ships no project-scope definition of it (#1256). The
  default endpoint is `http://127.0.0.1:8080/mcp`. CPP does not build or run it.
- `playwright` - upstream `@playwright/mcp` via npx/stdio.
- `tavily` - upstream `tavily-mcp` via npx/stdio; provides web search, extract,
  crawl, and map tools. API key from `claude-power-pack/mcp-keys` in AWS SM.

**Retired servers** (removed; listed in `.claude/deprecated-mcps.yaml`, torn down as
orphans by Step 6c/7 + `scripts/mcp-drift.py`):
- `mcp-second-opinion` (retired #469 - the containerized server moved to its own
  external repo; only the stale container/images are orphans - the `second-opinion`
  registration is the user's valid new wiring and is intentionally NOT flagged)
- `aws-secrets-agent` (retired #469 - the AWS SM sidecar fed the old container and
  has no other consumer)
- `mcp-playwright-persistent` (retired #423 - browser automation moved to the
  upstream `@playwright/mcp` npx/stdio server)
- `mcp-nano-banana`, `mcp-woodpecker-ci`, `mcp-coordination` (retired earlier)

**Deprecated servers**:
- `mcp-evaluate` (deprecated - absorbed into /evaluate:issue skill; the
  subproject itself was REMOVED from CPP in #943. It stays on this list because
  the list drives host teardown, and a host that installed its systemd unit or
  registered it still has one to clean up)

**For each expected server**, check:
1. Is it registered in `claude mcp list`?
2. For second-opinion, is `http://127.0.0.1:8080/mcp` reachable (external server up)?
3. Is it defined at ONE endpoint? A name can be defined at user, local and
   project scope at once, and when those point at different endpoints the server
   a session reaches depends on the directory it started in (issue #1256).
   "Registered" does not answer this - it read a two-endpoint `second-opinion`
   as OK while `claude mcp list` itself warned about it. Ask the file-reading
   check, which covers EVERY MCP name, not only CPP's:

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
cd "$CPP_DIR" || exit 4
MCP_SCOPE_STATUS="clean"
python3 scripts/mcp-drift.py --scope-check
MCP_SCOPE_RC=$?
# REPORT and CONTINUE on every outcome - this is advice, never a reason to stop
# the update. 1 = a conflict (named, with both endpoints, redacted); 3 = a config
# could not be read, which is NOT clean and must not be relayed as clean.
case "$MCP_SCOPE_RC" in
  0) ;;
  1) MCP_SCOPE_STATUS="SCOPE CONFLICT (see above)" ;;
  3) MCP_SCOPE_STATUS="NOT ASSESSED (MCP config unreadable)" ;;
  *) MCP_SCOPE_STATUS="NOT ASSESSED (scope check exited $MCP_SCOPE_RC)" ;;
esac
```

Never remove a definition yourself. On a conflict, show both scopes and
endpoints, and offer Claude Code's own `claude mcp remove <name> -s <user|local>`
for the scope the user says to drop - which wiring is canonical is the user's call.
To drop a PROJECT entry, never offer `-s project`: that rewrites a tracked
`.mcp.json` for every user of that repository. Offer adding the name to
`projects["<dir>"].disabledMcpjsonServers` in `~/.claude.json` instead, which
`--scope-check` honours (a disabled project entry is not a definition). CPP
itself ships no project-scope `second-opinion` any more (Step 6b.0), so a
`second-opinion` conflict in a CPP checkout is now user versus local scope.

**For each installed legacy systemd service matching mcp-*, nano-*, or
coordination**, classify it as:

1. **LEGACY SYSTEMD** if it maps to a retired server
2. **ORPHANED LEGACY** if CPP no longer ships it
3. **LEGACY DEPRECATED** for `mcp-evaluate`/`evaluate`

Build a drift report table:

```
MCP Server Drift Report
========================

Server                    Expected  MCP Reg   Container   Legacy Units              Status
------------------------------------------------------------------------------------------
second-opinion            yes       yes       --          --                        OK
playwright                yes       yes       --          --                        OK
mcp-second-opinion        retired   --        present     --                        ORPHANED DOCKER MCP
aws-secrets-agent         retired   --        present     --                        ORPHANED DOCKER MCP
mcp-coordination          retired   yes       none        system:mcp-coordination   ORPHANED LEGACY
mcp-evaluate              depr.     no        none        user:mcp-evaluate         LEGACY DEPRECATED
```

Status classifications:
- **OK** - expected server is registered at ONE endpoint (and, for second-opinion,
  reachable). Registered at two scopes that disagree is not OK - it is:
- **SCOPE CONFLICT** - the name is defined at 2+ scopes with different endpoints
  (`mcp-drift.py --scope-check` exit 1). Report only; never removed by this command
- **LEGACY SYSTEMD** - a systemd unit remains for a retired server; teardown only
- **LEGACY DEPRECATED** - a deprecated server has a systemd unit; teardown only
- **ORPHANED LEGACY** - an installed/running legacy systemd unit CPP no longer ships
- **ORPHANED DOCKER MCP** - a curated retired server (`.claude/deprecated-mcps.yaml`)
  still present locally as a container, an `mcp-<name>:*` image, or a
  `claude`/`codex mcp` registration after CPP retired it (CPP ships no compose
  file, so any listed server still present locally is an orphan)
- **PORT CONFLICT** - multiple listener processes are bound to the same MCP port
- **NOT REGISTERED** - a server is reachable but not in `claude mcp list`

Use `scripts/drift-detect.sh --fix` as raw inventory for:

- legacy MCP systemd units such as `mcp-coordination`
- port double-binding on MCP ports 8080-8089

When presenting the final drift table, reclassify any systemd finding from that
script as `LEGACY SYSTEMD`, `LEGACY DEPRECATED`, or `ORPHANED LEGACY`. Do not
report systemd as `CONFLICT`, `FAILED SYSTEMD`, or `STALE SERVICE`.

#### 6b.1: Friction Capture .gitignore (issue #1498)

`/cpp:init` adds `.claude/friction.jsonl` and `.claude/friction/` to the
target `.gitignore` (same step as `settings.local.json`), but a project
initialised BEFORE that fix only gets it through `/cpp:update`. This step did
not exist in `/cpp:update` at all until now - add it, idempotent exactly like
`/cpp:init`'s own version:

```bash
# Keep project friction artifacts local; add each ignore pattern independently.
if [ -f ".gitignore" ]; then
  FRICTION_HEADER_WRITTEN=0
  for pattern in ".claude/friction.jsonl" ".claude/friction/"; do
    if ! grep -qxF -- "$pattern" .gitignore; then
      if [ "$FRICTION_HEADER_WRITTEN" -eq 0 ]; then
        echo "" >> .gitignore
        echo "# Claude Code friction capture (local, not shared history)" >> .gitignore
        FRICTION_HEADER_WRITTEN=1
      fi
      echo "$pattern" >> .gitignore
      echo "✓ Added $pattern to .gitignore"
    fi
  done
fi
```

### 6c: Detect Orphaned Docker MCP Servers

Systemd orphans are only half the picture: when a server is retired from CPP, a
machine that ran it keeps the old container, the old `mcp-<name>:*` images, and a
live `claude`/`codex mcp` registration on a now-unmanaged port. This now includes
the Docker MCP runtime CPP retired wholesale in #469 - a lingering
`mcp-second-opinion` or `aws-secrets-agent` container is exactly this kind of
orphan. `scripts/mcp-drift.py` detects those, driven by the curated
`.claude/deprecated-mcps.yaml` list of record (never a blanket "every
registration not in compose" sweep, which would tear down a user's own custom
MCP servers).

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
cd "$CPP_DIR" || exit 4

MCP_DOCKER_DRIFT_STATUS="clean"
python3 scripts/mcp-drift.py --check
MCP_DOCKER_DRIFT_RC=$?

# Exit 3 = the docker inventory could not be READ. Nothing was assessed, so this
# is NOT a clean result and must never be relayed as one (issue #673).
if [ "$MCP_DOCKER_DRIFT_RC" -eq 3 ]; then
  MCP_DOCKER_DRIFT_STATUS="NOT ASSESSED (docker unreadable)"
fi
```

A server is classified **ORPHANED DOCKER MCP** only when it is listed in
`deprecated-mcps.yaml` **and** no longer a compose service **and** still present
locally. CPP now ships NO `docker-compose.yml`, so `mcp-drift.py` treats the
service set as empty by absence - any listed server still lingering on the host is
a genuine orphan. (If a compose file is ever reintroduced, a listed name that is
still a service is `OK`.) A listed server with nothing present is `ABSENT`; if the
service set cannot be read the server is `UNKNOWN` (never torn down). Registrations
CPP never shipped are never listed, so they are never flagged - and the valid new
`second-opinion` registration is deliberately left off the retired entry's
registration list, so the user's new wiring is never torn down.

**Exit code 3 is "I could not look", not "clean" (issue #673).** A docker socket
that refuses the read (permission denied, or a dead daemon) used to empty the
container inventory silently: every curated server classified `ABSENT` and the
report printed `No orphaned Docker MCP servers detected.` on a host that had two
retired containers running the whole time - and this command relayed that as a
positive finding. A refused read now classifies every curated server `UNKNOWN`,
prints a `DOCKER UNREADABLE` banner instead of the clean line, and exits **3**.
When `MCP_DOCKER_DRIFT_RC` is 3, report the host as **not assessed** - never as
clean - and offer no teardown (there is nothing trustworthy to tear down from).
The script retries a permission-refused read once via non-interactive `sudo -n`
before giving up; when that retry is what succeeded, the report says so and the
teardown commands carry the same `sudo -n` prefix, so what `--plan` prints is what
`--teardown` runs. A **missing** docker binary is deliberately different: nothing
can run under a runtime that is not installed, so that stays a clean read and is
named as such in the report.

A server may also be classified **NAME COLLISION**: it would have been flagged
orphaned, but its declared port answers on localhost, or a live `claude`/`codex`
registration targets that port - evidence that the retired name is the user's own
deployment rather than a CPP leftover. Collisions are reported with their evidence,
are never counted as orphans, and teardown hard-refuses them.

Limitation to surface if asked: like skill drift, detection is curated-list
driven. A retired server without a `deprecated-mcps.yaml` entry reads as
untracked; the fix is to add it to that file, not to broaden the teardown.

---

## Step 7: Guided Remediation

For each drift finding, offer the user actionable options using AskUserQuestion.

**Only show this if drift was detected.** If everything is clean, skip to Step 8.

### For LEGACY SYSTEMD or LEGACY DEPRECATED findings

Default recommendation: tear down legacy systemd (systemd is no longer a
supported runtime). Ask once for all remaining legacy units if possible:

```
Legacy systemd MCP units remain installed: {units}.
Systemd is no longer a supported CPP runtime. Leaving these units installed can
cause port conflicts or stale server restarts.
```

Options:
- **Tear down legacy systemd** - Stop, disable, remove unit files, reload systemd
- **Skip** - Leave units in place and keep the port-conflict warning visible

If they choose teardown, use the same scope-aware removal commands from Step
4.5 and re-run drift detection to verify no legacy units remain.

### For ORPHANED DOCKER MCP findings

**Only if `MCP_DOCKER_DRIFT_RC` is 1** (Step 6c found orphans). Pull the
structured findings and drive a per-server, user-confirmed teardown. Teardown is
reversible-where-possible: images keep a newest-tag restore point unless the user
chooses prune-all, and `mcp-drift.py` hard-refuses to touch anything not
classified `ORPHANED DOCKER MCP`.

**On `MCP_DOCKER_DRIFT_RC` = 3 there is nothing to offer** (issue #673): the
docker inventory was never read, so every server is `UNKNOWN` and every teardown
would be refused anyway. Do not present a teardown option; report the host as not
assessed, surface the `DOCKER UNREADABLE` line from Step 6c verbatim, and tell the
user what would make the read work (docker group membership, or starting the
daemon). Saying "no orphaned Docker MCP" here is the exact false-positive this
guard exists to prevent.

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
cd "$CPP_DIR" || exit 4
python3 scripts/mcp-drift.py --json > /tmp/mcp-drift.json
```

For each orphaned server, show the user what is present (container, image tags,
`claude`/`codex` registrations) plus its `reason` and `replacement`, and ask once
per server with AskUserQuestion:

```
mcp-second-opinion was retired from CPP but is still on this machine
({reason}).
Replacement: {replacement}
Present: {container} container, {N} image tag(s), claude:{regs}, codex:{regs}
Port to reclaim: {port}
```

Options:
- **Tear down (keep a restore image)** - stop + remove the container, prune old
  `mcp-<name>:*` image tags but keep the newest as a restore point, unregister
  from `claude`/`codex mcp`. Runs:
  ```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
: "${RETIRED_MCP_NAME:?bind the reviewed server name in this call}"
[[ "$RETIRED_MCP_NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || exit 4
  python3 "$CPP_DIR/scripts/mcp-drift.py" --teardown "$RETIRED_MCP_NAME"
  ```
- **Tear down (prune all images)** - same, but remove every `mcp-<name>:*` image:
  ```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
: "${RETIRED_MCP_NAME:?bind the reviewed server name in this call}"
[[ "$RETIRED_MCP_NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || exit 4
  python3 "$CPP_DIR/scripts/mcp-drift.py" --teardown "$RETIRED_MCP_NAME" --prune-all-images
  ```
- **Keep** - leave it in place (re-runs of /cpp:update will keep flagging it).

The teardown stops and removes the container (`docker stop` / `docker rm -f`),
prunes images, removes the `claude mcp` registration at its detected scope
(`claude mcp remove <name> -s <scope>`), removes any `codex mcp` registration,
and reports the freed port and image tags. After all confirmed teardowns, re-scan
and record the outcome for the summary:

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
cd "$CPP_DIR" || exit 4
python3 scripts/mcp-drift.py --check
RESCAN_RC=$?
if [ "$RESCAN_RC" -eq 0 ]; then
  MCP_DOCKER_DRIFT_STATUS="torn down (newest image kept as restore point unless prune-all)"
elif [ "$RESCAN_RC" -eq 3 ]; then
  # Do not call an unreadable re-scan "drift remaining" either - it is unknown.
  MCP_DOCKER_DRIFT_STATUS="NOT ASSESSED (docker became unreadable during the re-scan)"
else
  MCP_DOCKER_DRIFT_STATUS="drift remaining (user kept some servers)"
fi
```

Never tear down a server the user chose to keep, and never tear down without an
explicit per-server confirmation. `mcp-drift.py` refuses any server still in
compose (`OK`), any with nothing present (`ABSENT`), and any name not on the
curated list - so a user's own custom MCP registration is never removed.

### For ORPHANED LEGACY services

Ask the user per service:

```
mcp-coordination is a legacy systemd unit and is no longer a CPP Docker server.
```

Options:
- **Remove** - Stop service, disable, remove service file, unregister from claude mcp
- **Keep** - Leave it running (user may have a custom setup)

If they choose remove:
1. `sudo systemctl stop <name>`
2. `sudo systemctl disable <name>`
3. `sudo rm /etc/systemd/system/<name>.service`
4. `sudo systemctl daemon-reload`
5. `claude mcp remove <name>` (if registered)

For user-scope orphaned units, use `systemctl --user ...`, remove the file from
`~/.config/systemd/user/`, and run `systemctl --user daemon-reload`.

### For NOT REGISTERED servers (reachable but not in claude mcp list):

```
The external second-opinion server answers on http://127.0.0.1:8080/mcp but is
not registered with Claude Code at any scope (CPP ships no .mcp.json entry for
it - Step 6b.0 registers it at user scope; if you see this, that step failed).
```

Options:
- **Register** - `claude mcp add --transport http --scope user second-opinion "${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp"` (for a Tailscale host, export `SECOND_OPINION_URL` first rather than editing the URL, so every CPP document installs the same endpoint - issue #1256)
- **Skip** - Leave unregistered

---

## Step 7.5: User-Level Flow Allowlist Refresh

The git pull may have updated `templates/claude-settings-permissions.json`
(the user-level read-only allowlist that keeps `/flow:*` from prompting for
its git/gh plumbing - see `templates/claude-settings-permissions.md`). Check
whether `~/.claude/settings.json` is missing any template rules and offer to
merge the difference.

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
cd "$CPP_DIR" || exit 4
TEMPLATE="$CPP_DIR/templates/claude-settings-permissions.json"
TARGET="$HOME/.claude/settings.json"

if [ -f "$TEMPLATE" ]; then
  if [ -f "$TARGET" ]; then
    MISSING=$(jq -s '(.[1].permissions.allow - (.[0].permissions.allow // [])) | length' "$TARGET" "$TEMPLATE")
    jq -rs '(.[1].permissions.allow - (.[0].permissions.allow // []))[] | "  + \(.)"' "$TARGET" "$TEMPLATE"
  else
    MISSING=$(jq '.permissions.allow | length' "$TEMPLATE")
    jq -r '.permissions.allow[] | "  + \(.)"' "$TEMPLATE"
  fi

  if [ "$MISSING" -eq 0 ]; then
    echo "✓ Flow allowlist up to date"
  else
    echo "Flow allowlist: $MISSING rule(s) from the template are not in ~/.claude/settings.json"
  fi
fi
```

If rules are missing, ask the user:

```
Merge the missing flow allowlist rules into ~/.claude/settings.json?
(Additive and idempotent - existing settings and rules are preserved.
Rationale and caveats: templates/claude-settings-permissions.md)  [y/N]
```

If yes, run the same merge as `/cpp:init`:

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
TEMPLATE="$CPP_DIR/templates/claude-settings-permissions.json"
TARGET="$HOME/.claude/settings.json"
# Through the declaring seam (#1132), same call /cpp:init makes.
"$CPP_DIR/scripts/cpp-host-write.sh" settings-merge "$TEMPLATE"
# A refused or failed merge must never report a successful allowlist refresh (#1198).
case $? in
  0) echo "✓ Flow allowlist merged ($(jq '.permissions.allow | length' "$TARGET") total allow rules)" ;;
  3) echo "→ Flow allowlist DEFERRED by request - ~/.claude/settings.json was NOT modified" ;;
  127) echo "✗ Flow allowlist NOT merged - the host-write seam is not installed (see Step 5a)" ;;
# A failed write can modify the surface; report failure and inspect, never assert rollback.
  *) echo "✗ Flow allowlist merge FAILED - check ~/.claude/settings.json - a failed write may have modified it" ;;
esac
```

If no: report `→ Flow allowlist refresh skipped` and continue.

---

## Step 7.6: Permission-Prompt Census Hook Registration

The git pull may have added `scripts/hook-permission-census.sh` (the observe-only
`PermissionRequest` hook that records each permission prompt - with a derived
allow-rule candidate and a risk tier - to the project's `.claude/friction.jsonl`,
so `/self-improvement:retro` Step 4 finally has real input; issue #482). The
script itself is re-linked into `~/.claude/scripts/` by the Tier 2 refresh; this
step registers it in `~/.claude/settings.json` if it is not already there. Same
user-level trust boundary as Step 7.5, so it is user-confirmed.

```bash
TARGET="$HOME/.claude/settings.json"
CENSUS_CMD="~/.claude/scripts/hook-permission-census.sh"
CENSUS_SCRIPT="$HOME/.claude/scripts/hook-permission-census.sh"

# Only offer if the script is installed and not already registered.
if [ -e "$CENSUS_SCRIPT" ]; then
  ALREADY=0
  if [ -f "$TARGET" ]; then
    ALREADY=$(jq --arg cmd "$CENSUS_CMD" \
      '[.hooks.PermissionRequest[]? | (.hooks // [])[]? | select(.command == $cmd)] | length' \
      "$TARGET" 2>/dev/null || echo 0)
  fi
  if [ "${ALREADY:-0}" -gt 0 ]; then
    echo "✓ Permission-prompt census hook already registered"
  else
    echo "Permission-prompt census hook is not registered in ~/.claude/settings.json"
  fi
fi
```

If not registered, ask the user:

```
Register the observe-only PermissionRequest census hook in ~/.claude/settings.json?
It records each permission prompt (derived allow-rule candidate + risk tier) to the
project friction ledger so /self-improvement:retro can propose an allowlist from real
data. Never blocks or alters a permission decision.  [y/N]
```

If yes, run the same idempotent merge as `/cpp:init`:

```bash
CENSUS_CMD="~/.claude/scripts/hook-permission-census.sh"
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
# Through the declaring seam (#1132): the helper owns the write, this
# document keeps the jq program. --defer ~/.claude/settings.json yields a
# stated refusal instead of a silent skip.
"$CPP_DIR/scripts/cpp-host-write.sh" settings-edit --arg cmd "$CENSUS_CMD" <<'JQ'
  .hooks = (.hooks // {})
  | .hooks.PermissionRequest = (.hooks.PermissionRequest // [])
  | if any(.hooks.PermissionRequest[]?; (.hooks // [])[]?.command == $cmd)
    then .
    else .hooks.PermissionRequest += [{"hooks":[{"type":"command","command":$cmd}]}]
    end
JQ
case $? in
  0) echo "✓ PermissionRequest census hook registered in ~/.claude/settings.json" ;;
  3) echo "→ Census hook registration DEFERRED by request - settings.json was NOT modified" ;;
  127) echo "✗ Census hook NOT registered - the host-write seam is not installed (see Step 5a)" ;;
  *) echo "✗ Census hook registration FAILED - check settings.json - a failed write may have modified it" ;;
esac
```

If no: report `→ Permission-prompt census hook registration skipped` and continue.

---

## Step 7.7: Pending-Retro Reminder Registration (opt-in)

The git pull may have added `scripts/hook-pending-retro.sh` (a `SessionStart`
hook that prints up to TWO independent advisory lines at session open: pending
retro material - `.claude/friction.jsonl` signals plus uncodified
`Status: proposed` learnings, pointing at `/self-improvement:retro` (#530) - and
installed-vs-checkout command drift via the sibling `scripts/install-drift.sh`
(#622)). It only surfaces, never codifies, and is silent when there is nothing to
report. The script is re-linked
into `~/.claude/scripts/` by the Tier 2 refresh; this step registers it in
`~/.claude/settings.json` if not already there. Opt-in and user-confirmed
(default N) - CPP ships no hooks file at all since #1206, so it never
turns itself on.

```bash
TARGET="$HOME/.claude/settings.json"
RETRO_CMD="~/.claude/scripts/hook-pending-retro.sh"
RETRO_SCRIPT="$HOME/.claude/scripts/hook-pending-retro.sh"

# Only offer if the script is installed and not already registered.
if [ -e "$RETRO_SCRIPT" ]; then
  ALREADY=0
  if [ -f "$TARGET" ]; then
    ALREADY=$(jq --arg cmd "$RETRO_CMD" \
      '[.hooks.SessionStart[]? | (.hooks // [])[]? | select(.command == $cmd)] | length' \
      "$TARGET" 2>/dev/null || echo 0)
  fi
  if [ "${ALREADY:-0}" -gt 0 ]; then
    echo "✓ Pending-retro reminder already registered"
  else
    echo "Pending-retro reminder is not registered in ~/.claude/settings.json"
  fi
fi
```

If not registered, ask the user:

```
Register the session-open reminder in ~/.claude/settings.json? It prints one
advisory line when pending friction signals or uncodified learnings exist (run
/self-improvement:retro), and one when a retired CPP marketplace cache is still
pending uninstall (#662/#663). Surfaces only - never codifies, never blocks.
Silent when there is nothing to report.  [y/N default N]
```

If yes, run the same idempotent merge as `/cpp:init`:

```bash
RETRO_CMD="~/.claude/scripts/hook-pending-retro.sh"
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
# Through the declaring seam (#1132): the helper owns the write, this
# document keeps the jq program. --defer ~/.claude/settings.json yields a
# stated refusal instead of a silent skip.
"$CPP_DIR/scripts/cpp-host-write.sh" settings-edit --arg cmd "$RETRO_CMD" <<'JQ'
  .hooks = (.hooks // {})
  | .hooks.SessionStart = (.hooks.SessionStart // [])
  | if any(.hooks.SessionStart[]?; (.command == $cmd) or ((.hooks // [])[]?.command == $cmd))
    then .
    else .hooks.SessionStart += [{"hooks":[{"type":"command","command":$cmd}]}]
    end
JQ
case $? in
  0) echo "✓ Session-open pending-retro reminder registered in ~/.claude/settings.json" ;;
  3) echo "→ Pending-retro reminder DEFERRED by request - settings.json was NOT modified" ;;
  127) echo "✗ Pending-retro reminder NOT registered - the seam is not installed (see Step 5a)" ;;
  *) echo "✗ Pending-retro reminder registration FAILED - check settings.json - a failed write may have modified it" ;;
esac
```

If no: report `→ Pending-retro reminder registration skipped (default)` and continue.

---

## Step 7.8: Commands-Mirror Refresh (opt-in, fail-open)

Hosts that serve the command surface from an out-of-repo byte-copy of
`.claude/commands/` (e.g. `~/Projects/.claude/commands`, project scope for
sessions started above the checkout) instead of `/plugin` installs had nothing
maintaining that mirror, so it silently went stale as merges landed (issue #582).
This step guards it. It is a no-op on hosts without a mirror.

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
MIRROR="${CPP_COMMANDS_MIRROR:-}"
# Auto-detect the common layout when the env var is unset: a commands dir in a
# .claude/ directory directly above this checkout.
if [ -z "$MIRROR" ]; then
  CAND="$(dirname "${CPP_DIR}")/.claude/commands"
  [ -d "$CAND" ] && MIRROR="$CAND"
fi
if [ -n "$MIRROR" ] && [ -d "$MIRROR" ]; then
  if ! "$CPP_DIR/scripts/commands-mirror-sync.sh" --check "$MIRROR"; then
    echo "Commands mirror at $MIRROR has drifted from the repo."
  fi
fi
```

If drift is reported, ask the user:

```
Refresh the commands mirror at {MIRROR} from the repo (prunes files the repo
no longer has, copies everything current)?  [Y/n]
```

If yes: `scripts/commands-mirror-sync.sh --write "$MIRROR"`. If no: report
`→ Commands mirror left stale (re-run scripts/commands-mirror-sync.sh --write later)`
and continue. Long term, prefer retiring the mirror in favor of `/plugin`
installs (#582 follow-through tracked with #575).

---

## Step 7.9: Generated Host-Surface Refresh (issue #575)

Managed skills were handled once in Step5a. This step retains the separate
memory-harness installer and retired-surface review. Failures warn and continue
with their own verdict; they do not replace the managed-component report.

**7.9a - Read the shared Codex result.** Step5a already refreshed existing
managed Codex copies at the bound revision. Use that row's actual state and
counts; no separate installer runs here. A Codex executable alone does not
select an absent install. Explicit installation remains `/cpp:init` work.

**7.9b - Wire the common-memory harness.** `scripts/install-memory-harness.sh`
has always advertised itself as safe to re-run from `/cpp:update`, and nothing
ever ran it - so `cpp-memory` was missing from PATH on hosts that never ran it
by hand. Idempotent.

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
bash "$CPP_DIR/scripts/install-memory-harness.sh" || echo "WARNING: memory harness install failed (continuing)"
```

**7.9c - Detect retired surfaces still present.** Directories CPP once
generated into and no longer does. Detection is curated
(`.claude/retired-surfaces.yaml`) AND marker-gated, so a hand-authored file or
a skill the user installed themselves is never a finding:

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
python3 "$CPP_DIR/scripts/retired-surface-prune.py" --check
```

Exit 0 means nothing on this host is CPP-generated in those directories -
report `✓ No retired host surfaces present` and continue to Step 8.

On exit 1, show the user exactly what would move (`--plan` is pure - it prints
the `mv` commands and changes nothing), then ask **per surface**:

```
Retired surface {name} still has {N} CPP-generated file(s) at {path}.
  Retired because: {reason}
  Superseded by:   {replacement}
  Preserved untouched: {the non-CPP files in that directory}

Move the {N} CPP-generated item(s) aside to {path}-retired-{date}?
(Reversible - files are MOVED, not deleted; recover with mv.)  [y/N]
```

If yes: `python3 scripts/retired-surface-prune.py --prune {name}`. If no:
report `→ {name} left in place` and continue. Never pass `--all` without
per-surface assent, and never delete - the script only ever moves.

Set `HOST_SURFACE_STATUS` to `refreshed`, `partial`, or `clean` for the Step 10
summary.

---

## Step 7.10: Retired Marketplace-Cache Report (issues #622/#662)

CPP's marketplace lane is retired by #662 / ADR 0005. The old clone/cache
parity walk has no source after `plugins/` removal. This step now names any CPP
families still installed under `~/.claude/plugins/cache/cpp/` as migration state.
It is read-only, informational, and fail-open.

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
"$CPP_DIR/scripts/install-drift.sh" || true
```

- `INSTALL_DRIFT: skipped` with no cache - nothing remains; continue silently.
- `INSTALL_DRIFT: skipped` with retired families - surface the informational
  report and the per-family migration commands. Exit status remains zero.
- `INSTALL_DRIFT: error` - report the diagnostic and continue; this advisory
  never blocks an update.

  ```text
  CPP's marketplace lane is retired (#662). For every family listed, run:

    /plugin uninstall <family>@cpp

  Issue #663's restored tiered symlink surface replaces the cache.
  ```

---

## Step 8: Detect Current Installation Tier

Determine the user's current tier level so we can offer upgrades:

```bash
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
cd "$CPP_DIR" || exit 4

# Tier 1 checks
TIER=0

# Commands
if [ -L ".claude/commands" ] || [ -d ".claude/commands" ]; then
  TIER=1
fi

# Tier 2: scripts (hooks conjunct dropped in #1206 - see below)
SCRIPTS_COUNT=0
for script in prompt-context.sh worktree-remove.sh secrets-mask.sh hook-mask-output.sh; do
  [ -f ~/.claude/scripts/$script ] || [ -L ~/.claude/scripts/$script ] && SCRIPTS_COUNT=$((SCRIPTS_COUNT + 1))
done
# Scripts ALONE decide Tier 2 since #1206. Requiring .claude/hooks.json here
# capped every newly initialised project at Tier 1 once CPP stopped shipping it -
# a predicate that cannot become true, degrading silently while the ladder still
# advertised the rung.
[ "$SCRIPTS_COUNT" -ge 3 ] && TIER=2

# Tier 3: MCP servers
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
if echo "$MCP_LIST" | grep -q "second-opinion"; then
  TIER=3
fi
```

---

## Step 9: Offer Tier Upgrade

If the user is not at the highest tier, ask if they want to upgrade using AskUserQuestion:

**Only show this if current tier < 3.**

```
Your current installation: Tier {TIER}

Available upgrades:
  Tier 1 (Minimal): Commands + Skills symlinks
  Tier 2 (Standard): + Scripts, hooks, shell prompt, permission profiles
  Tier 3 (Full): + MCP servers (external second-opinion + playwright)

Would you like to upgrade to a higher tier?
```

**Options:**
- **Keep current tier** - No changes beyond the git pull
- **Upgrade to Tier 2** (if currently Tier 0 or 1)
- **Upgrade to Tier 3** (if currently below Tier 3)

If upgrading, follow the same installation steps as `/cpp:init` for the new tier only.

---

## Step 10: Update Summary

**Report the commit this run FINISHED on, not only the one it pulled (issue
#1263).** Every step from 4 onward acts on the working tree, and in a shared
checkout that tree is not pinned to `NEW_COMMIT`: another session can pull while
this run is still going (measured: two foreign pulls mid-run, so the summary
named a commit two behind the one the host's commands, helpers and Codex skills
were actually served from). Re-read HEAD now, and say so when it moved:

```bash
# CPP_SHARED_FINISH_GUARD
CPP_DIR=REPLACE_WITH_CPP_DIR
: "${CPP_DIR:?bind the absolute checkout path from Step1 in this call}"
[[ "$CPP_DIR" = /* && -d "$CPP_DIR" ]] || exit 4
HOST_REFRESH_REVISION=REPLACE_WITH_REFRESH_REVISION
[[ "$HOST_REFRESH_REVISION" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]] || exit 4
FINISH_COMMIT=$(git -C "$CPP_DIR" rev-parse --short HEAD)
HOST_FINISH_REVISION=$(git -C "$CPP_DIR" rev-parse --verify HEAD 2>/dev/null)
echo "Finished on: $FINISH_COMMIT"
printf 'Revision: %s\n' "$HOST_REFRESH_REVISION"
if [ "$HOST_FINISH_REVISION" != "$HOST_REFRESH_REVISION" ]; then
  printf 'Managed refresh: UNAVAILABLE - revision changed after refresh; inspect installed state\nFinished revision: %s\n' "${HOST_FINISH_REVISION:-unavailable}"
  exit 4
fi
echo 'CPP_REVISION_GUARD: stable (use the latest actual Step5a report; no component state inferred here)'
```

When `FINISH_COMMIT` differs from `NEW_COMMIT`, the `Commit:` line below reads
`{OLD_COMMIT} -> {NEW_COMMIT} (finished on {FINISH_COMMIT} - the checkout moved
during this run, likely another session's pull)`. The summary is read later by
people and sessions that do not re-derive it, so it names the state the host is
in, not the state this run passed through.

```
=================================
CPP Update Report
=================================

Version: v{OLD_VERSION} -> v{NEW_VERSION}
Commit:  {OLD_COMMIT} -> {NEW_COMMIT} {(finished on FINISH_COMMIT - moved during this run) if it differs}
Branch:  {BRANCH}
Tier:    {TIER} {(upgraded from X if applicable)}
{Bash:   Step 3.6 finding with its remedy - only when Step 3.6 reported one}
Managed refresh (PARTIAL, exit {HOST_REFRESH_EXIT}):
  {latest actual Step5a per-component report; include any Step10 revision refusal}

Changes pulled:
  {list of new commits, or "Already up to date"}

Dependencies:
  {synced servers or "No MCP venvs to update"}

Runtime:
  Model: no Docker MCP stack (second-opinion external, playwright via npx)
  Legacy systemd: {none, removed N unit scope(s), or skipped with warning}

Second-opinion registration:
  {SO_REGISTRATION_STATUS - "already at user scope", "registered at user scope",
   "NOT ASSESSED (user config unreadable)", or "FAILED" (Step 6b.0)}

MCP Drift:
  {drift summary - e.g. "1 new server refreshed via Docker, 1 legacy unit removed"
   or "No drift detected - all servers in sync"}

Docker MCP Drift:
  {MCP_DOCKER_DRIFT_STATUS - e.g. "clean", "torn down (newest image kept as restore
   point unless prune-all)", or "drift remaining (user kept some servers)"}

Host Surfaces:
  {HOST_SURFACE_STATUS - memory harness / retired-surface result only; Codex is in the managed report above}

Local-Model Lanes:
  {LOCAL_MODEL_LANES_STATUS - carries each harness's OWN verdict, e.g. "Tier 6
   harness capped @qwen-code/qwen-code 0.15.10 (latest 0.24.0 requires node
   >=22.0.0; this host has v20.20.2); Tier 7 harness upgraded opencode-ai
   1.18.29 -> 1.18.31 (gemma-ollama provider refreshed; gemma-implementer
   mechanical fence already current)" or "not installed (Tier 6/7 not selected)".
   There is deliberately no unqualified "Tier 6 refreshed" value any more
   (issue #1022): it was composed from an exit code and read identically whether
   the harness moved or npm silently installed the version already present}

Run /cpp:status for full installation details.
=================================
```

---

## Notes

- This command is safe to run repeatedly (idempotent)
- Uncommitted changes in CPP are auto-stashed before pull
- Symlinked commands are automatically updated by the git pull
- CPP ships no in-repo MCP server venvs; second-opinion is external, playwright is npx
- CPP no longer builds or runs a Docker MCP stack, so there is no Docker refresh step
- Legacy systemd units are detected and removed only after user confirmation
- MCP drift detection compares CPP's expected servers against leftover retired
  containers, legacy systemd remnants, claude mcp registrations, and listening ports
- Managed copies and links use the single shared Step5a refresh. Step7.9 retains
  the memory harness and retired-surface review against the curated
  `.claude/retired-surfaces.yaml`
- Step 5d refreshes already-present Tier 6/7 harnesses and re-merges the Gemma
  provider and agent profile, but never installs an absent tier. The re-merge
  keeps the `gemma-implementer` mechanical fence from going stale (issue #754)
- A harness upgrade reports the VERSION TRANSITION, never the install command's
  exit code (issue #1022), through `scripts/npm-global-upgrade.sh`. npm resolves
  `latest` down to the newest engine-compatible release and exits 0, so a host
  whose node is too old installs the version it already had and the old step
  called that "Tier 6 refreshed". The helper's five findings - `capped`,
  `not-upgraded`, `failed`, `unknown`, and the two clean verdicts `upgraded` and
  `current` - each carry a committed case in `controls/npm-global-upgrade/`
- Retired-surface teardown is per-surface, user-confirmed, marker-gated, and
  REVERSIBLE - files are moved to a timestamped sibling directory, never deleted
- Step 7.10 names retired CPP marketplace cache families (#622/#662) and points
  at `/plugin uninstall <family>@cpp`; it is informational until #663 restores
  the canonical symlink tier
- Orphaned legacy systemd units such as `mcp-coordination` are flagged for teardown
- Orphaned Docker MCP infra (Step 6c/7) - a container, `mcp-<name>:*` image, or
  `claude`/`codex mcp` registration left behind after a server is retired from CPP
  (including the `mcp-second-opinion`/`aws-secrets-agent` containers retired in #469)
  - is detected via the curated `.claude/deprecated-mcps.yaml` list and torn down
  per-server with confirmation, keeping a newest-image restore point unless prune-all
  is chosen. Driven by `scripts/mcp-drift.py`; a user's own custom MCP registration
  (and the valid new `second-opinion` registration) is never flagged or removed
- mcp-evaluate is recognized as deprecated and flagged for legacy teardown if installed
  (the subproject was removed from CPP in #943; the teardown stays because a host
  that installed its systemd unit still has one to remove)
- Use `/cpp:init` instead if you need the full interactive setup wizard
