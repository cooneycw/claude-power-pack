---
description: Update Claude Power Pack to the latest version
allowed-tools: Bash(git:*), Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(cat:*), Bash(uv:*), Bash(claude mcp list:*), Bash(claude mcp add:*), Bash(claude mcp remove:*), Bash(sudo systemctl:*), Bash(systemctl:*), Bash(command -v:*), Bash(ln:*), Bash(mkdir:*), Bash(cp:*), Bash(diff:*), Bash(find:*), Bash(grep:*), Bash(sed:*), Bash(awk:*), Bash(sort:*), Bash(mktemp:*), Bash(rm:*), Bash(sudo rm:*), Bash(curl:*), Bash(ss:*), Bash(docker:*), Bash(make:*), Bash(python3:*), AskUserQuestion
---

# Claude Power Pack Update

Update CPP to the latest version, detect MCP server and skill drift, and offer guided remediation.

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

  # A PROBE, NOT `[ -w ]` (issue #1138). Permission bits are not the authority
  # on whether a write succeeds: measured in a kyle container, the projected
  # ~/.claude/settings.json is mode -rw-rw-r-- owned by the running user and an
  # append-open still returns "Read-only file system", because the mount is
  # read-only. A check reading the mode to answer a question the mount decides
  # is the same defect class as the one this issue is about.
  # The subshell is load-bearing: `if : > "$probe" 2>/dev/null` still leaks
  # "Permission denied", because the shell processes redirections left to right
  # and reports the failed one BEFORE 2>/dev/null takes effect. Measured.
  # Through the declaring seam (#1132). A probe in intent, a write in fact -
  # it creates a file under the surface and removes it. Deferring the surface
  # answers the question the probe asks, so a deferred probe reports `no`
  # rather than writing to find out what it was already told.
  surface_writable=$(~/.claude/scripts/cpp-host-write.sh probe-writable ~/.claude/commands 2>/dev/null)
  #: EXIT 0 AND 3 ARE BOTH ANSWERS (issue #1198): the helper prints yes/no and
  #: returns 0, or prints no and returns 3 when the surface is deferred. Any
  #: other status means the seam could not run, and the capture is then EMPTY -
  #: which this line used to print as though it were a probe result, under a
  #: label saying "probed, not inferred from mode bits". There is no checkout
  #: here by construction, so there is nothing to bootstrap from: the honest
  #: answer is that it was not probed.
  case $? in
    0|3) : ;;
    *)   surface_writable="unknown (seam not installed here, so this was NOT probed)" ;;
  esac

  echo "No claude-power-pack CHECKOUT found at any known path."
  echo "  CPP command surface served here: $cpp_surface (~/.claude/commands/cpp/init.md readable)"
  echo "  command families already served: $families"
  echo "  helpers already served:          $helpers"
  echo "  ~/.claude/commands writable:     $surface_writable (probed, not inferred from mode bits)"
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
cd "$CPP_DIR"

# Get current version from CLAUDE.md - the maintained source of truth (issue
# #544: the CHANGELOG head can be a digit-less "[Unreleased]" block, so a grep
# for the first bracketed version silently falls through to the PREVIOUS
# release and reports a stale no-op update). Fall back to the newest bracketed
# CHANGELOG release only if the CLAUDE.md line is missing.
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

# Fetch latest from origin
echo ""
echo "Fetching latest from origin..."
git fetch origin 2>&1

# Compare with remote
BEHIND=$(git rev-list HEAD..origin/$CURRENT_BRANCH --count 2>/dev/null || echo "0")
AHEAD=$(git rev-list origin/$CURRENT_BRANCH..HEAD --count 2>/dev/null || echo "0")

if [ "$BEHIND" -eq 0 ]; then
  echo ""
  echo "Already up to date!"
else
  echo ""
  echo "$BEHIND commit(s) behind origin/$CURRENT_BRANCH"
  echo ""
  echo "New changes:"
  git log --oneline HEAD..origin/$CURRENT_BRANCH
fi
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
cd "$CPP_DIR"

# Set aside only on the user's answer above, and only with an entry we can
# identify later. $$ disambiguates two /cpp:update runs started in the same
# second (issue #1056).
STASH_TAG="cpp-update-$(date +%Y%m%d-%H%M%S)-$$"
STASH_SHA=""
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Setting uncommitted changes aside as '$STASH_TAG'..."
  if git stash push -m "$STASH_TAG"; then
    # Capture the SHA IMMEDIATELY. stash@{0} is a moving target - a sibling
    # session pushing between here and the restore renumbers every entry, and
    # the SHA is the only handle that stays ours.
    #
    # EXACT match, not a substring. git records the message as "On <branch>:
    # <tag>", so the tag is an exact SUFFIX; `$0 ~ t` would let the tag
    # cpp-update-20260919-120000-123 select an entry tagged ...-1234 and restore
    # a different session's work despite using a SHA afterwards. Require exactly
    # one match, too: two is ambiguous and picking the first is a guess.
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
    # DO NOT DROP IT AUTOMATICALLY. `git stash drop` takes only a stash@{n}
    # index, and an index is not a stable handle on a shared stack: between
    # resolving stash@{n} by tag and running the drop, a sibling session's push
    # renumbers every entry and the drop deletes THEIRS. There is no SHA form of
    # drop to close that window with, so this step reports the entry instead of
    # racing for it - the same reasoning that made the restore above use the SHA.
    # An entry the user is TOLD about is not the #1056 orphan; an entry nobody
    # mentions is.
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

`/cpp:update` is **self-modifying**: the Step 3 pull can change *this very file*
(`.claude/commands/cpp/update.md`). The copy of these instructions loaded into
context is the **pre-pull** version, so every step below may now be stale - a
removed step could run against a deleted script, or a renamed step could act on a
changed tree (issue #545: a `/cpp:update` run pulled #522, which deleted
`scripts/skill-drift.py` and stripped a whole step from this command; the pre-pull
context still contained that step and would have executed it against a now-deleted
script).

**First, surface any change to this command.** `git pull` set `ORIG_HEAD` to the
pre-pull commit, so no variable needs to survive between bash blocks:

```bash
cd "$CPP_DIR"
SELF=".claude/commands/cpp/update.md"
SELF_CHANGED=unknown
if git rev-parse -q --verify ORIG_HEAD >/dev/null 2>&1; then
  if git diff --quiet ORIG_HEAD..HEAD -- "$SELF"; then
    SELF_CHANGED=no
    echo "No change to /cpp:update in this pull - the steps in context are current."
  else
    SELF_CHANGED=yes
    echo ""
    echo "NOTE: this pull modified /cpp:update itself. Diff since the pre-pull copy:"
    git --no-pager diff ORIG_HEAD..HEAD -- "$SELF"
    echo ""
    echo "The /cpp:update steps loaded in context are now STALE."
  fi
else
  echo "Could not determine ORIG_HEAD - treat the in-context steps as possibly stale."
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

# 2. Leftover hooks.json in this project (CPP no longer ships one)
# DETECT THE FILE, NOT THE RETIRED SCRIPT NAME. Keying on
# hook-validate-command.sh missed every project carrying the hooks.json CPP
# itself shipped - it holds only SessionStart and masking declarations, so the
# grep never matched and the offer /cpp:status promises was never made.
if [ -f ".claude/hooks.json" ]; then
  echo "This project's .claude/hooks.json is a leftover: CPP no longer ships it (#1206)."
  echo "  Claude Code never loaded that path, so nothing in it ever ran -"
  echo "  neither the masking declarations nor the SessionStart notice."
  if grep -q "hook-validate-command.sh" .claude/hooks.json 2>/dev/null; then
    echo "  It also still references the PreToolUse hook retired in #439."
  fi
  echo "  Offer to remove the WHOLE FILE (user-confirmed; default N)."
  # On user confirm, remove the file outright - there is nothing in it to
  # preserve, since Claude Code loads none of it:
  #   rm .claude/hooks.json
  # (The older recipe stripped only the PreToolUse block and KEPT the file,
  # which is no longer the right outcome - nothing in it is loaded.)
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
cd "$CPP_DIR"

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

## Step 5a: Bootstrap the Host-Write Seam (issue #1198)

Every host write below goes through `~/.claude/scripts/cpp-host-write.sh`. That
symlink is itself one of the things Step 5b installs, so on a host that does not
have it yet EVERY call below exits 127 - and before #1198 the next line printed a
checkmark regardless. Measured on 2026-09-22: `/cpp:update` reported
`Flow allowlist merged (52 total allow rules)` having merged nothing, because the
count it printed was read BEFORE the merge it never performed.

The bootstrap goes through the seam too, invoked at its CHECKOUT path - which
always exists when a checkout does. That keeps it declared and deferrable like
every other write, rather than a carve-out the `check-cpp-host-writes` gate has
to be taught to ignore. `link-into` does its own `mkdir -p`, so this one call is
the whole bootstrap.

**IT MUST NOT CREATE `~/.claude/scripts`.** `link-into` does its own `mkdir -p`,
so bootstrapping unconditionally would create that directory on a Tier 0/1 host
- and Step 5b's `[ -d ~/.claude/scripts ]` guard would then pass for the first
time and install ninety helpers, silently upgrading an install the next step
explicitly promises never to self-upgrade. So the tier is read BEFORE the
bootstrap, and decides it (counter-model review).

```bash
if [ -d ~/.claude/scripts ]; then
  "$CPP_DIR/scripts/cpp-host-write.sh" link-into \
    "$CPP_DIR/scripts/cpp-host-write.sh" ~/.claude/scripts cpp-host-write.sh
  case $? in
    0) SEAM_STATUS="available" ;;
    3) SEAM_STATUS="the seam's own install was deferred by request" ;;
    *) SEAM_STATUS="UNAVAILABLE - the seam could not be installed" ;;
  esac
else
  SEAM_STATUS="not installed (Tier 0/1: no ~/.claude/scripts, and this command will not create one)"
fi
echo "Host-write seam: $SEAM_STATUS"
```

Report `SEAM_STATUS` and continue. Anything but `available` is a supported
state, not a stop: the steps below each read their own call's verdict, so they
say which of the four things happened rather than claiming the write landed.

**The status says what it measured, and nothing wider.** An earlier draft had
the deferred branch announce that "every host write below will report deferred"
- which is not something this call establishes. `--defer ~/.claude/scripts`
defers the SEAM'S OWN INSTALL; it says nothing about `~/.claude/settings.json`
or `~/.bashrc`, whose calls each consult their own defer-set entry and report
their own verdict. Overclaiming from one surface to all of them is this issue's
defect wearing the fix's clothes.

---

## Step 5b: Script Symlink Refresh (Tier 2)

The git pull may have ADDED new helper scripts under `scripts/` (e.g. the flow
helper family, issue #581). EXISTING symlinks in `~/.claude/scripts/` follow
the pull automatically, but a NEW script has no symlink yet - and the flow
allowlist rules delivered by Step 7.5 match the stable `~/.claude/scripts/`
path, so without this refresh a new rule points at a path that does not exist
and the zero-prompt lane silently degrades. The loop links every EXECUTABLE
file in `scripts/` regardless of extension (issue #669: the old `*.sh`-only
glob skipped `flow-wave-plan.py`, so its shipped allow rule pointed at a
nonexistent path); non-executable `.py` library files, directories, and
`__pycache__` are skipped by the executability gate. Re-run the same
idempotent link loop as `/cpp:init` Tier 2; skip when this install has no
`~/.claude/scripts/` directory (Tier 0/1 - never self-upgrade the tier here):

```bash
if [ -d ~/.claude/scripts ]; then
  SEAM_OK=0; SEAM_DEFERRED=0; SEAM_FAILED=0
  for script in "$CPP_DIR"/scripts/*; do
    [ -f "$script" ] && [ -x "$script" ] || continue
    name=$(basename "$script")
    # Through the declaring seam (#1132). The helper carries the already-linked
    # skip this block had, and honours --defer ~/.claude/scripts by name.
    ~/.claude/scripts/cpp-host-write.sh link-into "$script" ~/.claude/scripts "$name"
    #: COMPOSE A VERDICT, do not just run (issue #1198). This loop made ninety
    #: calls and drew no conclusion, so a seam that was absent linked nothing and
    #: the step said so nowhere - measured on 2026-09-22, 25 scripts unlinked
    #: while the run reported success. The tally is what makes the next step's
    #: "npm-global-upgrade.sh is not installed" traceable to a cause here.
    case $? in
      0) SEAM_OK=$((SEAM_OK + 1)) ;;
      3) SEAM_DEFERRED=$((SEAM_DEFERRED + 1)) ;;
      *) SEAM_FAILED=$((SEAM_FAILED + 1)) ;;
    esac
  done
  echo "→ Script refresh: $SEAM_OK linked/current, $SEAM_DEFERRED deferred, $SEAM_FAILED failed"
  [ "$SEAM_FAILED" -gt 0 ] && echo "  WARNING: $SEAM_FAILED script(s) were NOT linked. Allowlist rules and command docs citing ~/.claude/scripts/<name> point at paths that do not exist."
else
  echo "→ Script refresh skipped (no ~/.claude/scripts - Tier 0/1 install)"
fi
```

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

**Turning it off from here** is the same one action that records the choice:

```bash
~/.claude/scripts/stash-worktree-guard.sh --uninstall "$CPP_DIR"
```

Offer that only if the user asks, or if this run is the FIRST to install it
here - never as a recurring prompt. See `docs/agents/shared-stash-stack.md`.

---

## Step 5c: Command-Surface Symlink Check (issue #663)

The user-scope command symlinks (`~/.claude/commands/<family>` -> the
checkout, installed by `/cpp:init` Tier 1) are the CANONICAL command surface:
they follow the Step-3 `git pull` atomically, so there is nothing to refresh -
this step only VERIFIES they exist and still point at this checkout. Call the
helper BARE (allowlist rule matches the stable path):

```bash
~/.claude/scripts/cpp-commands-link.sh --check
```

The drift verdicts are deliberately split (issue #756). A family CPP just
shipped with no link at all is unambiguous: the symlink tier (issue #663)
exists so the command surface follows `git pull`, and requiring a prompt here
means every new family silently fails to reach users who defer the update. A
link pointing somewhere else is a choice the user may have made, and still
needs a human.

- `CPP_COMMANDS_LINK: ok` - report `✓ Command symlinks current` and continue.
  **Report it as a TOPOLOGY result, never as an install-health verdict** (issue
  #685): quote the helper's own `families:` and `ok:` numbers from its summary
  line; the `ok:` number means that many family links resolve to this checkout,
  and says nothing about whether the checkout's CONTENT is correct. A
  restore-over-clone accident produced a working tree with 106 files reverted
  and 111 upstream-deleted files resurrected; every link resolved, this step
  read `ok`, and the Step-3 `git pull` said "Already up to date" - three green
  signals while every served command was stale. Do not summarise this step as
  "command surface healthy".
- A `checkout: N tracked modified, M untracked (-uall) ...` line may precede the
  verdict. It is an ADVISORY observation, not drift: relay it with its counts
  and leave the verdict alone. Dirtiness is not staleness - a maintainer
  mid-edit and a corrupted restore look the same from here, which is why the
  counts are split (a handful of untracked scratch reads very differently from
  106 tracked modifications). If the numbers look wrong for the host, the
  content checks are `git -C "$CPP_DIR" status --porcelain -uall` (expect empty)
  and `git -C "$CPP_DIR" rev-parse HEAD origin/main` (expect equal).
- `CPP_COMMANDS_LINK: drift-missing` (exit 3) - new families have no link and
  no stale link needs a decision. Without prompting, run the install bare
  (`~/.claude/scripts/cpp-commands-link.sh`). Use its `linked   <fam> -> ...`
  lines and `changed:` counter as the source for N, then report
  `✓ linked N new famil(ies)`.
- `CPP_COMMANDS_LINK: drift` (exit 1) - a link points at ANOTHER checkout, or
  an owned link is an orphan for a retired family. Ask the user, then run the
  install (bare, no flags):
  `~/.claude/scripts/cpp-commands-link.sh`
- `foreign` lines are the user's own content winning a name collision -
  surface them, never modify them.
- Exit 127 (helper not yet linked): Step 5b just linked it on Tier 2+ hosts;
  fall back to `"$CPP_DIR/scripts/cpp-commands-link.sh" --check` once, or skip
  with a note on a Tier 0/1 install.

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
```

When `QWEN_LANE_PRESENT=true`, OFFER to upgrade the already-installed harness.
Ask the user, then upgrade only if the answer is yes. Never offer or run the
upgrade when `qwen` was absent.

**Do NOT run `npm install -g` directly and read its exit code (issue #1022).**
That is what this step used to do, and it is why it reported upgrades that never
happened: on a host running node 20, `npm install -g @qwen-code/qwen-code` exits
0 and installs the version that was already there, because npm resolves `latest`
down to the newest ENGINE-COMPATIBLE release and 0.24.0 declares
`engines.node >=22.0.0`. A real upgrade and a silently-capped one are the same
bytes on stdout. `scripts/npm-global-upgrade.sh` reads the installed version
before and after and reports the TRANSITION, with the reason taken from
`npm view <pkg>@latest engines.node` and `node --version` when there is one:

```bash
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
```

Set `QWEN_UPGRADE_CONFIRMED` from the user's answer before this block; leave it
unset or `no` and the lane keeps its `checked (no upgrade offered)` verdict.

Then mirror the Tier 6 Ollama reachability and model checks from `/cpp:init`.
The environment variable names and defaults must stay identical so serving and
consumer machines get the same diagnosis from both commands:

```bash
if $QWEN_LANE_PRESENT; then
  QWEN_ENDPOINT="${QWEN_OLLAMA_URL:-http://127.0.0.1:11434}"
  QWEN_MODEL="${QWEN_MODEL:-qwen3.8-code:latest}"

  if curl -sf --max-time 5 "$QWEN_ENDPOINT/api/version" > /dev/null; then
    echo "[x] Ollama reachable at $QWEN_ENDPOINT"
  else
    echo "[ ] Ollama NOT reachable at $QWEN_ENDPOINT"
    echo "    Serving machine: install and start Ollama (brew install ollama on macOS),"
    echo "    bind to the network with OLLAMA_HOST=0.0.0.0:11434 for LAN/tailnet use."
    echo "    Consumer machine: set QWEN_OLLAMA_URL=http://<serving-ip>:11434"
  fi

  if curl -sf --max-time 5 "$QWEN_ENDPOINT/api/tags" 2>/dev/null | grep -qF "\"$QWEN_MODEL\""; then
    echo "[x] Model present: $QWEN_MODEL"
  else
    echo "[ ] Model '$QWEN_MODEL' missing"
    echo "    On the serving machine:"
    echo "      ollama pull qwen3.8:27b"
    echo "      printf 'FROM qwen3.8:27b\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.7\nPARAMETER top_p 0.8\n' | ollama create qwen3.8-code -f -"
  fi

  # The lane verdict CARRIES the harness verdict rather than asserting
  # "refreshed" over it (issue #1022). `Tier 6 refreshed` was composed from an
  # exit code, so it said the same thing whether the harness moved, stalled at a
  # node-engine ceiling, or was never touched at all - and the Step 10 summary is
  # read by the operator and by later sessions, none of which re-derive the
  # version.
  echo "✓ Tier 6 Qwen lane checked: Ollama/model above; harness $QWEN_LANE_VERDICT"
  LOCAL_MODEL_LANE_STATUS_PARTS+=("Tier 6 harness $QWEN_LANE_VERDICT")
fi
```

#### 5d.3 Refresh Tier 7 (Local Gemma)

Only run the Tier 7 checks when `GEMMA_LANE_PRESENT=true`. An existing
OpenCode harness gets a version report and an offered upgrade. If the provider
is the only presence signal, report the absent harness but do not install it;
the config re-merge below must still run.

```bash
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
```

When `OPENCODE_HARNESS_PRESENT=true`, OFFER to upgrade the already-installed
harness. Ask the user, then upgrade only if the answer is yes. Never upgrade
without explicit confirmation.

**Through the same helper, for the same reason (issue #1022).** This offer is
not exempt because it happens to upgrade cleanly today: `opencode-ai` and
`@qwen-code/qwen-code` were run back to back on the same host, one moved and one
silently did not, and their output was indistinguishable. Whichever package hits
an engine ceiling next, the report has to be able to say so:

```bash
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
```

Set `GEMMA_UPGRADE_CONFIRMED` from the user's answer before this block; leave it
unset or `no` and the harness keeps its `checked (no upgrade offered)` verdict.

Mirror the Tier 7 Ollama checks for either Tier 7 presence signal:

```bash
if $GEMMA_LANE_PRESENT; then
  GEMMA_ENDPOINT="${GEMMA_OLLAMA_URL:-http://127.0.0.1:11434}"
  GEMMA_MODEL="${GEMMA_MODEL:-gemma4-code:latest}"

  if curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/version" > /dev/null; then
    echo "[x] Ollama reachable at $GEMMA_ENDPOINT"
  else
    echo "[ ] Ollama NOT reachable at $GEMMA_ENDPOINT"
    echo "    Serving machine: start it ('ollama serve') and retry."
    echo "    Consumer machine: set GEMMA_OLLAMA_URL=http://<serving-host>:11434"
    echo "    Shared-GPU host: another VM may currently hold the card."
  fi

  if curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/tags" 2>/dev/null | grep -qF "\"$GEMMA_MODEL\""; then
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
fi
```

Re-merge only when `GEMMA_CONFIG_PRESENT=true`. This is not an install path:
an absent `gemma-ollama` provider means Tier 7 configuration was not selected
on this host, so leave the config untouched. Reuse the non-destructive init
merge so unrelated providers and agents remain unchanged. Before merging,
compare the two owned blocks so the verdict identifies what changed and what
was already current.

```bash
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
  ~/.claude/scripts/cpp-host-write.sh json-merge-sections \
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
```

Finish the Tier 7 report with one lane verdict after the harness, server/model,
and eligible profile checks have run:

```bash
if $GEMMA_LANE_PRESENT; then
  # Carries the harness verdict for the same reason Tier 6 does (issue #1022):
  # the profile status alone said nothing about whether the harness moved.
  echo "✓ Tier 7 Gemma lane checked: harness $GEMMA_HARNESS_VERDICT; $GEMMA_PROFILE_STATUS"
  LOCAL_MODEL_LANE_STATUS_PARTS+=("Tier 7 harness $GEMMA_HARNESS_VERDICT ($GEMMA_PROFILE_STATUS)")
fi
```

Compose the Step 10 value only after every present lane has contributed its
outcome. A lane skipped by presence gating contributes nothing:

```bash
if ((${#LOCAL_MODEL_LANE_STATUS_PARTS[@]})); then
  printf -v LOCAL_MODEL_LANES_STATUS '%s; ' "${LOCAL_MODEL_LANE_STATUS_PARTS[@]}"
  LOCAL_MODEL_LANES_STATUS="${LOCAL_MODEL_LANES_STATUS%; }"
else
  LOCAL_MODEL_LANES_STATUS="not installed (Tier 6/7 not selected)"
fi
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
cd "$CPP_DIR"

echo "=== Repo MCP Server Inventory ==="

# CPP no longer ships a Docker MCP stack. It expects:
echo "  second-opinion - external streamable-http server (root .mcp.json -> :8080/mcp)"
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
if [ -x "$CPP_DIR/scripts/drift-detect.sh" ]; then
  "$CPP_DIR/scripts/drift-detect.sh" --fix || DRIFT_FOUND=true
fi
```

### 6b: Detect Drift

Compare the inventories and classify each finding. Use the following logic:

**Expected servers** (what CPP wires now, registration-only - no containers):
- `second-opinion` - external streamable-http server; the root `.mcp.json` points
  Claude Code at `http://127.0.0.1:8080/mcp` (project scope), optionally also
  registered at user scope. CPP does not build or run it.
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
- **OK** - expected server is registered (and, for second-opinion, reachable)
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
cd "$CPP_DIR"

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
cd "$CPP_DIR"
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
  python3 scripts/mcp-drift.py --teardown <name>
  ```
- **Tear down (prune all images)** - same, but remove every `mcp-<name>:*` image:
  ```bash
  python3 scripts/mcp-drift.py --teardown <name> --prune-all-images
  ```
- **Keep** - leave it in place (re-runs of /cpp:update will keep flagging it).

The teardown stops and removes the container (`docker stop` / `docker rm -f`),
prunes images, removes the `claude mcp` registration at its detected scope
(`claude mcp remove <name> -s <scope>`), removes any `codex mcp` registration,
and reports the freed port and image tags. After all confirmed teardowns, re-scan
and record the outcome for the summary:

```bash
cd "$CPP_DIR"
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
not registered with Claude Code (the root .mcp.json only applies inside CPP).
```

Options:
- **Register** - `claude mcp add second-opinion --transport http --url http://127.0.0.1:8080/mcp --scope user` (edit the URL for a Tailscale host)
- **Skip** - Leave unregistered

---

## Step 7.5: User-Level Flow Allowlist Refresh

The git pull may have updated `templates/claude-settings-permissions.json`
(the user-level read-only allowlist that keeps `/flow:*` from prompting for
its git/gh plumbing - see `templates/claude-settings-permissions.md`). Check
whether `~/.claude/settings.json` is missing any template rules and offer to
merge the difference.

```bash
cd "$CPP_DIR"
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
# Through the declaring seam (#1132), same call /cpp:init makes.
~/.claude/scripts/cpp-host-write.sh settings-merge "$TEMPLATE"
#: THE MEASURED CASE (issue #1198). This pair printed
#: "✓ Flow allowlist merged (2 total allow rules)" with the seam absent and
#: nothing merged, and printed the same line with the surface DEFERRED exactly
#: as asked. The count made it worse, not better: read after a failed merge it
#: is the PRE-merge total, so the false claim carried a plausible number and
#: read as a smaller install rather than an error.
case $? in
  0) echo "✓ Flow allowlist merged ($(jq '.permissions.allow | length' "$TARGET") total allow rules)" ;;
  3) echo "→ Flow allowlist DEFERRED by request - ~/.claude/settings.json was NOT modified" ;;
  127) echo "✗ Flow allowlist NOT merged - the host-write seam is not installed (see Step 5a)" ;;
#: A FAILURE DOES NOT ESTABLISH THAT THE SURFACE IS UNCHANGED (counter-model
#: review). The first draft of these handlers said "... is unchanged" on the
#: failure branch, which asserts a rollback nothing performs. Measured: given a
#: malformed template and no existing file, `settings-merge` exits 1 AND leaves
#: a newly created ~/.claude/settings.json containing `{}`. Append and
#: replace operations can likewise modify a file before an I/O error. So the
#: failure branch reports the failure and sends the reader to look - claiming
#: an unverified rollback is the same overclaim as claiming an unperformed
#: write, pointed the other way.
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
# Through the declaring seam (#1132): the helper owns the write, this
# document keeps the jq program. --defer ~/.claude/settings.json yields a
# stated refusal instead of a silent skip.
~/.claude/scripts/cpp-host-write.sh settings-edit --arg cmd "$CENSUS_CMD" <<'JQ'
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
# Through the declaring seam (#1132): the helper owns the write, this
# document keeps the jq program. --defer ~/.claude/settings.json yields a
# stated refusal instead of a silent skip.
~/.claude/scripts/cpp-host-write.sh settings-edit --arg cmd "$RETRO_CMD" <<'JQ'
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
MIRROR="${CPP_COMMANDS_MIRROR:-}"
# Auto-detect the common layout when the env var is unset: a commands dir in a
# .claude/ directory directly above this checkout.
if [ -z "$MIRROR" ]; then
  CAND="$(dirname "$(pwd)")/.claude/commands"
  [ -d "$CAND" ] && MIRROR="$CAND"
fi
if [ -n "$MIRROR" ] && [ -d "$MIRROR" ]; then
  if ! scripts/commands-mirror-sync.sh --check "$MIRROR"; then
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

CPP ships installers and teardowns for the generated surfaces it writes into
HOME, and until #575 **none of them were invoked here** - so an updated host
ended up missing current files AND keeping retired ones. Both halves run in
this step. It is fail-open throughout: any failure warns and continues, never
aborting the update.

**7.9a - Install the current Codex skills.** The repo's `codex/skills/` is the
CI-gated source of truth (`codex-skills-check`), but nothing ever copied it to
`~/.codex/skills/`, so Codex could not see any CPP skill. The installer prunes
managed orphans at the destination too, so a skill dropped upstream stops
loading here. Skip when Codex is not installed on this box.

```bash
if command -v codex >/dev/null 2>&1; then
  python3 scripts/codex-skill-sync.py --install || echo "WARNING: codex skill install failed (continuing)"
else
  echo "→ Codex skills skipped (codex CLI not installed)"
fi
```

**7.9b - Wire the common-memory harness.** `scripts/install-memory-harness.sh`
has always advertised itself as safe to re-run from `/cpp:update`, and nothing
ever ran it - so `cpp-memory` was missing from PATH on hosts that never ran it
by hand. Idempotent.

```bash
bash scripts/install-memory-harness.sh || echo "WARNING: memory harness install failed (continuing)"
```

**7.9c - Detect retired surfaces still present.** Directories CPP once
generated into and no longer does. Detection is curated
(`.claude/retired-surfaces.yaml`) AND marker-gated, so a hand-authored file or
a skill the user installed themselves is never a finding:

```bash
python3 scripts/retired-surface-prune.py --check
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
scripts/install-drift.sh || true
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
cd "$CPP_DIR"

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

```
=================================
CPP Update Complete
=================================

Version: v{OLD_VERSION} -> v{NEW_VERSION}
Commit:  {OLD_COMMIT} -> {NEW_COMMIT}
Branch:  {BRANCH}
Tier:    {TIER} {(upgraded from X if applicable)}

Changes pulled:
  {list of new commits, or "Already up to date"}

Dependencies:
  {synced servers or "No MCP venvs to update"}

Runtime:
  Model: no Docker MCP stack (second-opinion external, playwright via npx)
  Legacy systemd: {none, removed N unit scope(s), or skipped with warning}

MCP Drift:
  {drift summary - e.g. "1 new server refreshed via Docker, 1 legacy unit removed"
   or "No drift detected - all servers in sync"}

Docker MCP Drift:
  {MCP_DOCKER_DRIFT_STATUS - e.g. "clean", "torn down (newest image kept as restore
   point unless prune-all)", or "drift remaining (user kept some servers)"}

Host Surfaces:
  {HOST_SURFACE_STATUS - e.g. "refreshed (73 codex skills installed, memory harness
   linked, no retired surfaces present)", "partial (user kept a retired surface)",
   or "clean"}

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
- Generated host surfaces are refreshed in Step 7.9 (issue #575): the Codex skill
  install and the common-memory harness both run here, and retired surfaces are
  detected against the curated `.claude/retired-surfaces.yaml`
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
