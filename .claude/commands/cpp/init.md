---
description: Interactive setup wizard for Claude Power Pack
allowed-tools: Bash(mkdir:*), Bash(ln:*), Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(cat:*), Bash(cp:*), Bash(python3:*), Bash(PYTHONPATH=*), Bash(claude mcp list:*), Bash(claude mcp add:*), Bash(command -v:*), Bash(git:*), Bash(docker:*), Bash(make:*), Bash(sleep:*), Bash(grep:*), Bash(head:*), Bash(touch:*)
---

# Claude Power Pack Setup Wizard

Interactive wizard to install and configure Claude Power Pack components.

---

## Step 0: Observe prerequisites before setup

Run the installed shared observer before installation work:

```bash
~/.claude/scripts/flow-preflight.sh --json --repo . --harness auto
```

Report every required gap and unknown observation; optional Codex absence is a
warning. If the helper is absent, report observation unavailable and use the
verified CPP source found in Step 1 to repair it. Never invoke a target-project
lookalike. Do not stop authorized setup or repair because identity, gh, optional
review tooling or the installation itself needs attention. No login, tool
installation, git configuration change or runtime download happens in this
observation. The cicd capability separately requires verified uv and installed CPP Python.

## Step 1: Locate CPP Source

Find where claude-power-pack is installed:

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

## Step 1b: Bash Floor Report (issue #1628)

Step 0 asks the INSTALLED observer, which a fresh host does not have and an older
install has without this check. So ask the checkout now, on every tier:

```bash
BASH_FLOOR_REPORT=$("$CPP_DIR/scripts/flow-preflight.sh" --checks bash 2>/dev/null)
BASH_FLOOR_RC=$?
if [ "$BASH_FLOOR_RC" -ne 0 ]; then
  printf '%s\n' "$BASH_FLOOR_REPORT"
  echo "BASH_FLOOR: not met or not verified (exit $BASH_FLOOR_RC)"
fi
```

No output means the floor is met on this PATH. On a `BASH_FLOOR:` line, report it and
its remedy, and do not stop setup: expect helper failures below until bash is
upgraded, and attribute them to this rather than diagnosing each one. Anything but
exit 1 means the floor was not verified, which is never relayed as met.

---

## Step 2: Detect Current State

Collect these presence observations to guide the remaining steps. They do not
prove that the installed capabilities are ready; use `/cpp:status` for readiness:

```bash
# Tier 1 checks
COMMANDS_INSTALLED=false
[ -L ".claude/commands" ] || [ -d ".claude/commands" ] && COMMANDS_INSTALLED=true

# Tier 2 checks (count every linked helper, not just .sh - issue #669)
# Scripts ALONE decide Tier 2 since #1206: CPP no longer ships .claude/hooks.json,
# so a predicate that also required it could never become true for a new project.
SCRIPTS_COUNT=$(find ~/.claude/scripts -maxdepth 1 -type l 2>/dev/null | wc -l)

# Tier 3 checks
# CPP no longer runs a Docker MCP stack. Second Opinion is an external
# streamable-http server (its own repo) and playwright runs via npx. The only
# Docker interest here is spotting retired containers that /cpp:update tears down.
DOCKER_INSTALLED=false
LEFTOVER_CONTAINERS=""
LEGACY_SYSTEMD_UNITS=""

command -v docker &>/dev/null && DOCKER_INSTALLED=true

if [ "$DOCKER_INSTALLED" = "true" ]; then
  LEFTOVER_CONTAINERS=$(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -E '^(aws-secrets-agent|mcp-second-opinion|mcp-playwright-persistent)$' || true)
fi

for unit in mcp-second-opinion second-opinion mcp-playwright mcp-playwright-persistent playwright-persistent mcp-evaluate evaluate mcp-coordination coordination; do
  [ -f "/etc/systemd/system/${unit}.service" ] && LEGACY_SYSTEMD_UNITS="$LEGACY_SYSTEMD_UNITS system:${unit}"
  [ -f "$HOME/.config/systemd/user/${unit}.service" ] && LEGACY_SYSTEMD_UNITS="$LEGACY_SYSTEMD_UNITS user:${unit}"
done

MCP_SERVERS=""
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
for server in second-opinion playwright; do
  echo "$MCP_LIST" | grep -q "$server" && MCP_SERVERS="$MCP_SERVERS $server"
done
```

Report current state to user.

---

## Step 3: Select Capabilities

Ask which capabilities the user wants in ONE AskUserQuestion call with two
multi-select questions (the tool allows four options per question): first
**commands**, **scripts**, **MCP servers**, **CI/CD host checks**; then **Codex**,
**Qwen**, **Gemma**, **optional extras**. Union both answers; any combination is supported.
Explain that Codex also installs commands and scripts used by its orchestration
commands; Qwen and Gemma install their commands. Optional
extras enables later individual questions; it never consents to those writes.
The commands capability includes command-family symlinks and the default project stash guard.

Offer the historical tier names as quick-start presets that preselect choices:

| Preset | Name | Preselected capabilities |
| --- | --- | --- |
| 1 | Minimal | commands, extras |
| 2 | Standard | commands, scripts, extras |
| 3 | Full | commands, scripts, mcp, extras |
| 4 | CI/CD | commands, scripts, mcp, cicd, extras |
| 5 | Codex | commands, scripts, mcp, cicd, codex, extras |
| 6 | Local Qwen | commands, qwen, extras |
| 7 | Local Gemma | commands, gemma, extras |

The Codex preset preserves its historical contents, including CI/CD. A custom
**Codex + Gemma** choice resolves to **commands, scripts, codex, gemma** and does
not install Claude MCP servers or CI/CD host checks. Qwen uses Qwen Code;
Gemma uses OpenCode. Both local lanes can be selected together.

Resolve the choice with the checkout helper before any installation write.
Its capability catalog, prerequisite graph, preset table and step ownership are
authoritative; do not infer dependencies from section numbers or duplicate the
graph in the wizard. For custom choices, use fixed machine IDs from the list:

```bash
# Bind this JSON to the user's actual choices in each fresh Bash tool call.
CPP_CAPABILITIES_JSON='["codex","gemma"]'
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" plan --capabilities "$CPP_CAPABILITIES_JSON"
```

For an unchanged preset, call `plan --preset N` instead, and use its `requested`
array as `CPP_CAPABILITIES_JSON` in subsequent calls. If the user edits those
choices, resolve them as a custom selection. Retain the returned plan and show
its resolved capabilities, prerequisites and execution order for confirmation.
Stop on a plan error. Selection never proves installation success.

Record `PROFILE_NAME=not-selected` unless the resolved plan includes `scripts`.
Keep the requested array bound explicitly in every Bash tool call; variables
do not survive between tool calls. Never substitute a default preset when the
selection binding is absent.

## Step 3b: Permission Profile (scripts capability)

**Only show this step if the resolved capabilities include `scripts`.**

Claude Code prompts "Allow?" before running tools. You can auto-approve safe operations to reduce interruptions and deny the listed dangerous command forms.

Ask the user which permission profile they want using AskUserQuestion:

**Options:**

| Profile | Description | Best For |
|---------|-------------|----------|
| **Cautious** | Minimal auto-approvals (Read only) | New users, shared machines |
| **Standard** | Common dev tools auto-approved (Recommended) | Most developers |
| **Trusted** | Broad development approvals; asks on listed Git/GitHub verbs, including ordinary push and API calls. Optional hooks only advise | Solo developers, power users |
| **Custom** | Choose individual permission categories | Fine-grained control |

Keep the initial AskUserQuestion choices to Cautious, Standard, Trusted, and
Custom. If the user selects Trusted, ask one additional question:

**Which broad-approval profile?**
- **Keep Trusted (default)** - ask on the listed Git/GitHub verbs, including ordinary push and API calls.
- **YOLO (explicit opt-in)** - auto-approve those commands too; show the disclosure below before confirmation.

YOLO is never the default and is never recommended. Do not select it from the
installation tier, prior permissions, or a request to reduce prompts. A user must
choose it explicitly and confirm its disclosure; declining returns to the profile
chooser. Standard remains the recommended default.

### Profile Definitions

**Cautious Profile:**
```json
{
  "permissions": {
    "allow": ["Read", "Glob", "Grep"],
    "deny": ["Bash(rm -rf:*)", "Bash(git push --force:*)"]
  }
}
```

**Standard Profile (Default):**
```json
{
  "permissions": {
    "allow": [
      "Read", "Glob", "Grep",
      "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
      "Bash(git add:*)", "Bash(git commit:*)", "Bash(git branch:*)",
      "Bash(git checkout:*)", "Bash(git stash:*)", "Bash(git fetch:*)",
      "Bash(ls:*)", "Bash(pwd)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
      "Bash(npm:*)", "Bash(npx:*)", "Bash(uv:*)", "Bash(pip:*)", "Bash(yarn:*)",
      "Bash(python:*)", "Bash(node:*)",
      "Bash(gh issue list:*)", "Bash(gh issue view:*)",
      "Bash(gh pr list:*)", "Bash(gh pr view:*)",
      "WebFetch(domain:github.com)", "WebFetch(domain:docs.python.org)",
      "Skill(project-next)", "Skill(project-lite)"
    ],
    "deny": [
      "Bash(rm -rf:*)", "Bash(git push --force:*)", "Bash(git reset --hard:*)",
      "Bash(sudo:*)", "Bash(chmod -R:*)"
    ]
  }
}
```

**Trusted Profile:**
```json
{
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "Write",
      "Bash(git:*)",
      "Bash(gh:*)",
      "Bash(npm:*)",
      "Bash(npx:*)",
      "Bash(uv:*)",
      "Bash(pip:*)",
      "Bash(yarn:*)",
      "Bash(python:*)",
      "Bash(node:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(mkdir:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(curl:*)",
      "Bash(wget:*)",
      "WebFetch",
      "WebSearch",
      "Skill(*)",
      "mcp__second-opinion__*",
      "mcp__playwright__*"
    ],
    "deny": [
      "Bash(rm -rf /:*)",
      "Bash(rm -rf ~:*)",
      "Bash(rm -rf /home:*)",
      "Bash(git push --force origin main:*)",
      "Bash(git push --force origin master:*)",
      "Bash(sudo rm:*)",
      "Bash(mkfs*)",
      "Bash(dd if=*)"
    ],
    "ask": [
      "Bash(git push:*)",
      "Bash(git reset:*)",
      "Bash(git clean:*)",
      "Bash(git rebase:*)",
      "Bash(git filter-branch:*)",
      "Bash(git filter-repo:*)",
      "Bash(git replace:*)",
      "Bash(git update-ref:*)",
      "Bash(gh repo delete:*)",
      "Bash(gh repo archive:*)",
      "Bash(gh pr merge:*)",
      "Bash(gh issue delete:*)",
      "Bash(gh release delete:*)",
      "Bash(gh api:*)",
      "Bash(git commit --amend*)",
      "Bash(git commit * --amend*)",
      "Bash(git branch -D*)",
      "Bash(git branch * -D*)",
      "Bash(git branch --force*)",
      "Bash(git branch * --force*)",
      "Bash(git branch -f*)",
      "Bash(git branch * -f*)",
      "Bash(git branch -df*)",
      "Bash(git branch * -df*)",
      "Bash(git branch -rD*)",
      "Bash(git branch * -rD*)",
      "Bash(git branch -M*)",
      "Bash(git branch * -M*)",
      "Bash(git branch -C*)",
      "Bash(git branch * -C*)"
    ]
  }
}
```

**YOLO Profile:**
```json
{
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "Write",
      "Bash(git:*)",
      "Bash(gh:*)",
      "Bash(npm:*)",
      "Bash(npx:*)",
      "Bash(uv:*)",
      "Bash(pip:*)",
      "Bash(yarn:*)",
      "Bash(python:*)",
      "Bash(node:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(mkdir:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(curl:*)",
      "Bash(wget:*)",
      "WebFetch",
      "WebSearch",
      "Skill(*)",
      "mcp__second-opinion__*",
      "mcp__playwright__*"
    ],
    "deny": [
      "Bash(rm -rf /:*)",
      "Bash(rm -rf ~:*)",
      "Bash(rm -rf /home:*)",
      "Bash(git push --force origin main:*)",
      "Bash(git push --force origin master:*)",
      "Bash(sudo rm:*)",
      "Bash(mkfs*)",
      "Bash(dd if=*)"
    ]
  }
}
```

#### Trusted approval scope

Trusted keeps its original broad allow list **and every original deny rule**,
then adds `permissions.ask`. Normal rule precedence is **deny, then ask, then
allow**, independent of specificity. Existing exact force-push-to-main/master
prefix denies remain denied; they are not weakened into prompts.

Whole-verb asks cover git push, reset, clean, rebase, filter-branch, filter-repo,
replace and update-ref; gh repo delete/archive, pr merge, issue delete, release
delete and api. All pushes and all API calls prompt, including ordinary pushes
and GET requests such as `gh api repos/owner/repo`: flags, refspecs, grouped push
options and implicit API methods make a finite dangerous-only list too easy to
miss. This is a usability cost: the separate explicit YOLO choice restores the
original Trusted policy if you accept that risk. Ordinary commits and branch
creation/listing/rename/copy remain auto-approved; commit amend and forced branch
delete/rename/copy forms use flag patterns instead. The JSON above is the complete
installed ask list.

Flags after operands are covered, for example `git push origin main --force`,
`git commit -m fix --amend`, `git branch old -D`, and
`gh api repos/owner/repo -X DELETE`. Claude Code checks every compound subcommand,
so `cd subdir && git push -f` also prompts for the push.

This is not a complete destructive-command list or a security boundary around
programs. Flag patterns can also prompt when flag-like text occurs in a quoted
argument; unlisted grouped branch flags may escape them. Alternate forms such as
`/usr/bin/git`, `git -C . push`, `git 'push'`, and `sh -c '...'` are outside these
prefixes; other rules and permission modes decide them. Broad runtime approvals
can execute commands indirectly. Native sandbox and permission-mode settings
still apply. The [Claude Code permission docs](https://code.claude.com/docs/en/permissions.md)
document precedence, wildcard patterns, compounds and these matching limits,
but do not name an earliest version for ask precedence. Do not promise it for
an unverified old client.

### YOLO Disclosure

Show this after an explicit YOLO choice and before any installation confirmation:

```
=== YOLO permission profile: explicit opt-in ===

This writes the selected profile to .claude/settings.local.json when that file
is absent. Existing local settings are skipped; selecting a profile does not
silently replace them.

YOLO uses the original Trusted allow AND deny lists exactly. It auto-approves
many destructive direct git and gh forms, unless an existing deny matches:
  git push --force / -f / --force-with-lease (including flags after operands)
  git reset --hard; git clean -f; git branch -D / -M / -C
  git commit --amend; git rebase; git filter-branch; git filter-repo
  git replace; git update-ref
  gh repo delete; gh repo archive; gh pr merge; gh issue delete
  gh release delete; gh api -X DELETE (including the method after the URL)

These operations can discard work, rewrite published history, delete repositories
or issues, and merge changes without an additional permission prompt. The existing
exact git push --force origin main/master prefix denies remain, along with all
original system denies. Other argument orders may not match those denies.

YOLO is never the default or a recommendation. Native policy still applies; this
choice does not enable bypassPermissions mode.

Proceed? [y/N]
```

The Standard profile lists direct GitHub issue and PR read commands.
The Custom GitHub CLI write category adds PR create/merge only; it
does not include issue-write verbs. Other permission settings and modes still apply.

### Custom Mode Categories

If user selects "Custom", ask which categories to enable using multi-select:

| Category | Permissions | Default |
|----------|-------------|---------|
| **File Reading** | Read, Glob, Grep | ✓ Enabled |
| **Git (safe)** | git status/diff/log/add/commit/branch/checkout/stash/fetch | ✓ Enabled |
| **Git (all)** | git push/pull/merge/rebase | ○ Disabled |
| **Package Managers** | npm, npx, uv, pip, yarn | ✓ Enabled |
| **Runtimes** | python, node | ✓ Enabled |
| **GitHub CLI (read)** | gh issue list, gh issue view, gh pr list, gh pr view | ✓ Enabled |
| **GitHub CLI (write)** | gh pr create, gh pr merge | ○ Disabled |
| **File Writing** | Write tool | ○ Disabled |
| **Web Access** | WebFetch, WebSearch | ○ Disabled |
| **MCP Tools** | All installed MCP servers | ○ Disabled |
| **Skills** | Auto-activate all skills | ✓ Enabled |

### Security Notes

- **Matching deny rules take precedence** - In normal rule evaluation, deny wins over ask, and ask wins over allow
- **A deny rule is not a boundary** - It matches the command text Claude usually produces. The same program run another way (`dd of=X if=Y`, `/usr/bin/dd`) is not matched; use sandboxing for enforcement
- **Native policy still applies** - Profiles configure permission rules; the selected permission mode and sandbox settings also govern execution
- **Nothing masks tool output** - CPP registers no output filter, so treat anything a command prints as reaching the transcript verbatim
- **Trusted and YOLO require scripts** - Offer the broad-approval chooser only when the resolved scripts capability installs the required helpers

---

## Step 4: Show Disclosure

**CRITICAL**: Before making ANY changes, show the user exactly what will be modified.

### Applicable write and credential inventory

Every selection creates a private temporary run directory under `$TMPDIR` (or the
system temporary directory), mode 0700. It contains generated `routines.sh`,
fixed-ID `results.json`, an ownership marker and pending-attempt state. Files
contain no credential or endpoint values. Recording atomically replaces the
results file. After the final project receipt is written, remove these temporary
files and report cleanup. Failed persistence retains temporary state for retry.
These artifacts are not written into the target project.

Every selection also creates project `.claude/cpp-install.json`, atomically
replacing an existing receipt after installation and optional choices. It records
the requested and resolved capabilities/profile, offered steps and their observed
outcomes, recording times, CPP revision and fixed references to shared user
components. It stores no credentials, endpoints or configuration values. An
existing receipt is replaced only after the new record is saved successfully;
a failed write is reported as incomplete and never displays the older receipt
as this run's result. Include this project-file write in the confirmation below.

Before the Proceed question, show this inventory with only rows belonging to
the resolved capabilities. Presets expand through the same resolver; custom
choices never inherit another preset's contents. Resolve `{PROJECT}`,
`{CPP_DIR}`, the home/config directories, the npm global prefix, and the Git hook
location using read-only inspection. If a location cannot be resolved, label it
unknown before asking; do not make a temporary write to test access. Selecting a
profile is not consent to install. Required parent directories and temporary
files for atomic replacement are included in each write below. Optional rows
run only after their own choice, with the same destinations repeated there.

| Applies to | Writes and scope | Credential handling |
| --- | --- | --- |
| commands | User command-family symlinks under `~/.claude/commands/` are installed/refreshed and stale CPP-owned links may be pruned; foreign content is preserved. Optional project `.claude/commands` symlink and `.claude/` directory. The default shared-stash guard installs the repository's `reference-transaction` hook at the common Git hooks directory or configured absolute `core.hooksPath`; refusal/foreign hooks are reported. Opt-out removes CPP's own hook and records `cpp.stashGuard=false` in the repository Git config. | None. |
| scripts | Link **all executable scripts** supplied under `{CPP_DIR}/scripts/` into `~/.claude/scripts/`, including the host-write helper. Create project `.claude/settings.local.json` only if absent, and append the relevant settings/friction ignore entries to an existing `.gitignore`. Optional user-level `~/.claude/settings.json` merges permission and hook entries; optional `~/.bashrc` prompt/tmux additions; global npm Happy installation uses its reported prefix/cache; uv Spec-Kit uses its tool directory, executable directory (normally `~/.local/bin`) and cache. | Permission lists are configuration, not credential values; existing unrelated settings are preserved. |
| mcp | User-scope Claude MCP registrations update `${CLAUDE_CONFIG_DIR:-$HOME}/.claude.json`: second-opinion URL, Playwright and conditional Tavily (when `TAVILY_API_KEY` is available). npm/npx uses its configured cache; Playwright can download browser binaries to `~/.cache/ms-playwright` on later use. Optional desk pool creates project `.claude/playwright-pool.json` if absent and adds user MCP desk registrations; later browser use writes `.claude/playwright-state/`. | Tavily requires Node.js 20+. `TAVILY_API_KEY` is read from the environment and stored **in plaintext** in the Tavily server environment entry in that user MCP config. Show its name and destination only, never its value. External second-opinion provider keys remain in its separate repository; CPP registers its URL. |
| cicd | Probe every registered provider independently. Ask once for the projects folder (default: CPP main-checkout parent). Write only `<projects>/.claude/cpp-host.json` through the defer-aware seam; uv uses `~/.cache/claude-power-pack/host-ci/{venv,uv}` and disables project bytecode writes. No project generation. | Persist only verdicts, controlled reasons, timestamp and numeric versions; credentials never enter argv, output or the record. |
| codex | Optional global npm Codex CLI installation; optional MCP registration updates `${CODEX_HOME:-$HOME/.codex}/config.toml`. CPP skills install under `$HOME/.codex/skills/` even when CODEX_HOME differs, with managed entries refreshed or pruned and lock `~/.codex/.cpp-skill-install.lock`. Common-memory harness links `~/.local/bin/cpp-memory` and copies `~/.codex/prompts/cpp-memory.md`. | The auth check reads existing auth state. `codex login` is advice, not an init credential write. A separately invoked login has its own credential storage. |
| qwen/gemma | Preserve the disclosed `~/.claude/scripts/cpp-host-write.sh` bootstrap link. Optional global npm Qwen Code/OpenCode installation uses its global prefix/cache. Optional endpoint persistence adds `QWEN_OLLAMA_URL` or `GEMMA_OLLAMA_URL` to the resolved shell RC path. Gemma merges provider/agent entries into `~/.config/opencode/opencode.json`. Optional smoke tests may create temporary probe files and vendor runtime cache/logs. Ollama model pulls shown here are instructions for the serving host, not an automatic init download. | Local Ollama requires no cloud API key; do not print any credentials embedded in a supplied endpoint. |
| extras | Enables the later individual choices for Sequential Thinking, Codex MCP registration, workstation tuning and the common-memory backend. Show each selected tool's destinations and undo instructions again at its own question; no optional write is authorized by this row alone. | Repeat the credential name and storage scope at each applicable choice, never the value. |

For every credential supplied to a selected optional tool, name its environment
variable and actual persistent storage scope before confirmation, say whether it
is plaintext, and never echo or interpolate its value into the disclosure. The
vendor cache/config areas above are vendor-managed; this inventory lists CPP's
controlled destinations and relevant vendor areas, not every file a vendor may
create at runtime.

For an unchanged preset, show its historical disclosure below. For a custom
choice, compose the disclosure solely from the applicable inventory rows above,
show the selected component destinations and undo instructions, and ask
**Proceed with these capabilities? [y/N]** once. Do not show cumulative preset
disclosures for a custom choice. In either case, refusal makes no installation
writes. Optional choices still require their own later consent.

### Tier 1 Disclosure (Minimal)

```
=== Tier 1: Minimal Installation ===

This will create the following symlinks (issue #663 - symlinks are the
CANONICAL command surface: they follow `git pull` atomically, so the executed
command text can never drift from the checkout):

  User scope (every session on this host):
    • ~/.claude/commands/<family> → {CPP_DIR}/.claude/commands/<family>
      (per-family links via scripts/cpp-commands-link.sh - your own files in
       ~/.claude/commands/ are preserved; a name collision with your own
       content is reported as foreign and never touched)

  Project scope (this project only):
    • .claude/commands → {CPP_DIR}/.claude/commands

  Disk usage: ~0 MB (symlinks only)

  To undo:
    rm .claude/commands
    # user scope: remove the per-family symlinks (only ones pointing into a
    # CPP checkout's .claude/commands/):
    ~/.claude/scripts/cpp-commands-link.sh --check   # lists what is linked

  Note: if the retired /plugin marketplace families are still installed
  (#662 / ADR 0005), the cached copies coexist with these symlinks - uninstall
  them (`/plugin uninstall <family>@cpp`) so sessions read only the current
  text.

Proceed? [y/N]
```

### Tier 2 Disclosure (Standard)

```
=== Tier 2: Standard Installation ===

This will make the following changes:

  [Tier 1 - Symlinks]
    • .claude/commands → {CPP_DIR}/.claude/commands

  [Tier 2 - Scripts] (~/.claude/scripts/)
    • prompt-context.sh       - Shell prompt worktree context
    • worktree-remove.sh      - Safe worktree cleanup
    • secrets-mask.sh         - Secret-masking filter for files at rest
    • hook-mask-output.sh     - Standalone JSON helper for files at rest;
      not registered as a hook and masking nothing live

  [Tier 2 - Shell Prompt] (optional)
    • Add worktree context to PS1: [CPP #42] ~/project $

  [Tier 2 - Tmux Auto-Start] (optional)
    • Add tmux auto-start to ~/.bashrc
    • Each new terminal tab opens its own tmux session
    • Skipped inside existing tmux sessions and non-interactive shells

  Disk usage: ~50 KB

  To undo:
    rm .claude/commands
    find ~/.claude/scripts -maxdepth 1 -type l -delete   # CPP installs symlinks only
    # Remove PS1 line from ~/.bashrc or ~/.zshrc

Proceed? [y/N]
```

### Tier 3 Disclosure (Full)

```
=== Tier 3: Full Installation ===

This will make the following changes:

  [Tier 1 + 2 - All Standard components]
    (see above)

  [Tier 3 - Second Opinion MCP (external server)]
    • The second-opinion server is a SEPARATE project run from its own repo:
      https://github.com/cooneycw/mcp-second-opinion
    • Start it there (localhost or a Tailscale host). It listens on
      http://127.0.0.1:8080/mcp (streamable-http). CPP does not build or run it.
    • API keys (Gemini/OpenAI/Anthropic) are configured in that repo, not here.
    • This tier registers it at USER scope - the only place CPP defines it (the
      repo ships no .mcp.json entry that could compete, issue #1256):
        claude mcp add --transport http --scope user second-opinion "${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp"
      For a server elsewhere (e.g. a Tailscale address), export SECOND_OPINION_URL
      (base URL, no /mcp) first - do not edit the URL in the command.

  [Tier 3 - Browser Automation] (upstream @playwright/mcp, no container)
    • Registers the upstream `@playwright/mcp` server via npx/stdio
    • Requires Node.js 18+ (for npx); Chromium downloads to ~/.cache/ms-playwright
      on first use. No Docker container.

  [Tier 3 - Browser desk pool] (optional, off by default)
    • /browser:session named concurrent sessions over upstream @playwright/mcp
    • Registers playwright-desk-1..N (npx, no custom image) - requires a restart
    • Skip unless you need several logged-in browser sessions at once

  Disk usage: ~1.3 GB for the Chromium browser cache (varies by host and cache
  state). The second-opinion server's own footprint lives in its own repo.
  Ports used: 8080 is the external second-opinion server (not started by CPP)

  To undo:
    # Tier 1+2 cleanup (see above)
    claude mcp remove second-opinion
    claude mcp remove playwright
    # If the browser desk pool was enabled:
    for d in $(python3 -c "import json;print(' '.join(json.load(open('.claude/playwright-pool.json'))['desks']))" 2>/dev/null); do claude mcp remove "$d"; done

Proceed? [y/N]
```

### Tier 4 Disclosure (Host CI Capabilities)

Ask once for the host projects folder. Default to the parent of the verified
CPP **main checkout**, resolved through Git common-dir/worktree metadata, even
when CPP runs in a relocated worktree. Store the answer in `CPP_PROJECTS_ROOT`;
do not walk up from the current directory. Show the resolved folder before
approval. Reject a folder inside the invoked repository.

```
=== Tier 4: Host CI Capabilities ===

This will make the following changes:

  [Tier 1 + 2 + 3 - All Full components]
    (see above)

  [Tier 4 - Host CI capabilities]
    - Check every registered provider independently; do not select a provider.
    - GitHub: verify real github.com authentication and classic repo scope.
      Non-introspectable scope is unknown; a public repository is no proof.
    - Woodpecker: verify CLI/auth using environment credentials or the existing
      AWS Secrets Manager source. Credentials stay out of output and the record.
    - Write <projects>/.claude/cpp-host.json through the host-write/defer seam.
      Record only verdicts, controlled reasons, checked-at and tool versions.
    - uv may sync ~/.cache/claude-power-pack/host-ci/{venv,uv}; no project files.
    - A container or unreachable host reports unknown, never mounted-host ready.

  To undo:
    # Tier 1+2+3 cleanup (see above)
    # Remove only the host record at the approved projects folder:
    Delete <projects>/.claude/cpp-host.json (only this host record).

Proceed? [y/N]
```

For project CI selection and file generation, use `/project:init` or `/cicd:init`.

### Tier 5 Disclosure (Codex)

```
=== Tier 5: Codex Orchestration ===

This will make the following changes:

  [Tier 1 + 2 + 3 + 4 - All CI/CD components]
    (see above)

  [Tier 5 - Codex CLI]
    - Requires: Codex CLI (npm install -g @openai/codex)
    - Requires: ChatGPT sign-in or API-key authentication (codex login)
    - Installs: /codex:auto, /codex:exec, /codex:ask, /codex:status, /codex:help commands
    - Optional: Register CPP MCP servers with Codex

  Disk usage: ~0 MB (commands via symlink)

  To undo:
    # Tier 1+2+3+4 cleanup (see above)
    npm uninstall -g @openai/codex

Proceed? [y/N]
```

### Tier 6 Disclosure (Local Qwen)

```
=== Tier 6: Local Qwen Orchestration ===

This will make the following changes:

  [Tier 1 - Commands symlink]
    (see above; Tiers 2-5 are NOT required for this tier)

  [Tier 6 - Local Qwen]
    - Installs if absent: ~/.claude/scripts/cpp-host-write.sh (link to the verified checkout helper).
    - Requires: Qwen Code CLI as the agentic harness
      (npm install -g @qwen-code/qwen-code)
      NOTE: no cloud API key is needed - the harness talks straight to Ollama
    - Requires: an Ollama server with the Qwen model, either on this machine
      (ollama pull qwen3.8:27b + tuned qwen3.8-code tag) or reachable over the
      network (QWEN_OLLAMA_URL)
    - Installs: /qwen:auto, /qwen:exec, /qwen:status, /qwen:help commands

  Disk usage: ~0 MB (commands via symlink); the model itself is ~17 GB
  and lives on the serving machine only.

  To undo:
    # Tier 1 cleanup (see above)
    # On the serving machine, optionally: ollama rm qwen3.8-code qwen3.8:27b

Proceed? [y/N]
```

### Tier 7 Disclosure (Local Gemma)

```
=== Tier 7: Local Gemma Orchestration ===

This will make the following changes:

  [Tier 1 - Commands symlink]
    (see above; Tiers 2-6 are NOT required for this tier)

  [Tier 7 - Local Gemma]
    - Installs if absent: ~/.claude/scripts/cpp-host-write.sh (link to the verified checkout helper).
    - Requires: OpenCode CLI as the agentic harness
      (npm install -g opencode-ai)
      NOTE: no cloud API key is needed - the harness talks straight to Ollama
    - Requires: an Ollama server with the Gemma model, either on this machine
      (ollama pull gemma4:31b-it-qat + tuned 64K gemma4-code tag) or reachable
      over the network (GEMMA_OLLAMA_URL)
    - Writes: ~/.config/opencode/opencode.json - adds a 'gemma-ollama'
      provider (native /api/chat) and a 'gemma-implementer' agent profile
      whose permission rules deny git/gh/deploy commands and out-of-directory
      writes. An existing file is merged into, never overwritten.
    - Installs: /gemma:auto, /gemma:exec, /gemma:status, /gemma:help commands

  Disk usage: ~0 MB (commands via symlink); the model itself is ~18 GB
  and lives on the serving machine only.

  To undo:
    # Tier 1 cleanup (see above)
    # Remove the gemma-ollama provider and gemma-implementer agent blocks
    #   from ~/.config/opencode/opencode.json
    # On the serving machine, optionally: ollama rm gemma4-code gemma4:31b-it-qat

Proceed? [y/N]
```

---

## Step 5: Execute Installation

Execute only the components that aren't already installed.

### Capability execution guard

The plan's `sections` is the execution order. Execute only those sections,
once each, and offer optional extras only if `extras` appears. Section numbers
below are navigation labels; they never imply that another component runs.
The shared MCP initializer is bookkeeping used by the final receipt for every
selection; it performs no client registration by itself.

Every component Bash block below begins with an executable selection check.
Retain that check when running or adapting the block. The equivalent wrapper
below shows its admission contract in the same tool call. Bind `CPP_DIR`, `CPP_CAPABILITIES_JSON` to the confirmed requested array,
`CPP_SECTION` to the component's fixed ID, and other block inputs explicitly in
that call. Replace the body marker with the exact block when using this wrapper. Do not
run a component's fenced blocks directly or default a missing selection. This
also applies to optional substeps: a later optional choice cannot enable an
unselected component. Keep its own consent checks inside the guard.

```bash
# CPP_CAPABILITY_EXECUTION_GUARD_BEGIN
if python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
    --capabilities "$CPP_CAPABILITIES_JSON" --section "$CPP_SECTION"; then
  # CPP_CAPABILITY_BODY
  :
else
  CPP_SECTION_STATUS=$?
  if [ "$CPP_SECTION_STATUS" -eq 3 ]; then
    echo "Component $CPP_SECTION not selected; no installation attempted."
  else
    echo "ERROR: capability selection invalid; installation stopped." >&2
  fi
  exit "$CPP_SECTION_STATUS"
fi
# CPP_CAPABILITY_EXECUTION_GUARD_END
```

For example, the host CI block is `CPP_SECTION=cicd`, Codex uses `codex`,
and the shared local-model bootstrap uses `local-seam`. An unselected section
returns 3 before its body; it adds no offered steps or observations. An invalid
selection stops the run. Record command outcomes from the body, never from
the guard's successful selection check.

Keep the existing observed `{STEP_RESULTS}` as structured `STEP_RESULTS_JSON`
for the receipt as well as for display. This is the same outcome record, not a
second checklist. Add/update one entry after each attempted step or explicit
skip/decline; never use the selected tier as evidence. For ordinary steps, a
nonzero command exit records `FAILED`; an unreadable observation records `unverified`; an existing
component is `already` only after verification. Map the existing succeeded /
failed / deferred wording for ordinary steps to `installed` / `FAILED` / `skipped`. Optional extras
must have an outcome too, including `declined` when the user says no.

Maintain `OFFERED_STEPS_JSON`, an array of the fixed IDs below, separately from
outcomes. Start with the plan's `required_steps`; add an optional ID **before**
offering its choice, even when the user later declines it. Do not reconstruct
this population from successful or observed results. A missing observation for
an offered step is `unverified`, so an unrecorded optional choice cannot make
the summary complete. Choices never offered by this run are outside its record.
Only IDs in the plan's `allowed_steps` may be offered or recorded. The receipt
re-derives this boundary from the selection; unselected steps cannot enter it.

Each entry has only `step`, `outcome`, the observed numeric `exit_code` when
available, and optionally `user_scope` reference IDs. A nonzero exit forces
`FAILED` for ordinary steps even if the supplied outcome says installed.
`host-ci` instead records its actual write outcome (`written`, `deferred`,
`failed`, `unknown`) with the observed launcher exit: only `written` + 0
completes it. A deferred/unknown write is not a completed installation. Provider
ready/missing/unknown verdicts are independent of whether the record was written.
Historical schema-1 receipts retain the retired project-generation IDs; new
The `cicd` capability requires only `host-ci`.
Do not put stdout, stderr, command arguments, settings, endpoints, environment
variables, credentials or their values into the record. The helper stamps each
outcome with the UTC time it was recorded in the receipt, not an invented
execution time. Its fixed reference registry describes user-scope dependencies
without copying their configuration. It is a mode-0644 checkout helper called
with python3, not an executable linked into `~/.claude/scripts`.

Use these stable IDs for the existing steps (record optional steps only when
offered; do not add unrelated tiers):

| Existing steps | Receipt IDs |
| --- | --- |
| Tier 1 command setup / optional project scope / stash guard | `commands`, `project-commands`, `stash-guard` |
| Tier 2 scripts / profile / prompt | `scripts`, `permission-profile`, `shell-prompt` |
| Tier 2 optional user allowlist / census / reminders / tmux / Happy / Spec-Kit | `user-flow-allowlist`, `permission-census`, `session-reminders`, `tmux-autostart`, `happy-cli`, `spec-kit-cli` |
| Tier 3 uv / second-opinion / playwright / tavily / optional pool | `uv`, `second-opinion`, `playwright`, `tavily`, `browser-pool` |
| Tier 4 host CI capability record | `host-ci` |
| Tier 5 CLI / doctor / auth / MCPs / skills / memory harness | `codex-cli`, `codex-doctor`, `codex-auth`, `codex-second-opinion`, `codex-playwright`, `codex-tavily`, `codex-skills`, `memory-harness` |
| Tier 6 CLI / model / endpoint / smoke / always-on | `qwen-cli`, `qwen-model`, `qwen-endpoint`, `qwen-smoke`, `qwen-always-on` |
| Tier 7 CLI / model / endpoint / provider / smoke | `gemma-cli`, `gemma-model`, `gemma-endpoint`, `gemma-provider`, `gemma-smoke` |
| Extras | `sequential-thinking`, `codex-second-opinion`, `codex-playwright`, `codex-tavily`, `workstation-tuning`, `memory-store` |
| Optional memory service start / recorded backend ping | `memory-store-start`, `memory-store-ping` |

If an extra retries an earlier step, replace that step's final outcome using
the latest observation; do not duplicate it. For example, a failed commands
step and a verified existing stash guard are represented as:

```json
[{"step":"commands","outcome":"FAILED"},{"step":"stash-guard","outcome":"already"}]
```

The helper adds `unverified` records for required selected or offered steps with no
observed outcome. It never fills those gaps with success.

The existing stash-guard opt-out is `declined`; conditional Tavily setup with
no available API key is `skipped`. These are explicit optional dispositions,
not failures and not missing observations. If a grouped step performs several
writes, record it as `FAILED` when any required sub-operation fails; a later
successful sub-operation must not overwrite that failure.

### Shared MCP registration routines

Every Bash tool invocation starts a fresh shell. Do not rely on functions,
arrays or variables surviving a prior call. The initialization block below
creates a private per-run temporary directory and prints its absolute path.
For EACH later Bash tool call, bind `CPP_DIR` to the verified checkout and
`CPP_MCP_RUN_DIR` to that exact printed path in that same invocation. Carry the
literal path in the wizard's context; do not assume an exported variable lasts.
Run blocks sequentially within a run; parallel setups require separate run paths.
Each registration, decline and persistence block loads the generated routines
and saved outcomes itself. Missing/unreadable run state refuses the block.

The following fenced body is template data for the initialization block, not a
separate setup action. The generated script contains these definitions and the verified state-helper
path, no credential values. The checkout helper `scripts/cpp-mcp-state.py` owns
temporary-file initialization, validation and atomic persistence; it is mode 0644,
invoked with python3 and not linked into the executable host-helper population. Call registration only after approval for the named server
and its disclosed destinations. Recovery initializes a new run after approval.

The per-client routines retain command exit status, withhold command output and
endpoint/key values, and save fixed-ID outcomes for the R4 receipt. Existing
configuration is an observation, not a connectivity/authentication test. A failed
list/config read is unverified and does not authorize a write. Browser desks
share one receipt row; any failed desk keeps that pool incomplete.

```bash
# CPP_MCP_ROUTINES_BEGIN
CPP_MCP_RUN_DIR="${BASH_SOURCE[0]%/*}"
declare -A CPP_MCP_RESULTS=()
cpp_mcp_load() {
  local saved id row
  if ! saved=$(python3 "$CPP_MCP_STATE_HELPER" load --run-dir "$CPP_MCP_RUN_DIR"); then
    echo "WARNING: MCP run results unavailable or interrupted; setup incomplete" >&2
    return 3
  fi
  while IFS=$'\t' read -r id row; do
    if [ -n "$id" ]; then CPP_MCP_RESULTS[$id]="$row"; fi
  done <<< "$saved"
}

cpp_mcp_attempt() {
  # Create a write-ahead marker before invoking a client. An interrupted or
  # unrecorded attempt prevents a later shell from reusing an old green row.
  if ! python3 "$CPP_MCP_STATE_HELPER" attempt --run-dir "$CPP_MCP_RUN_DIR"; then
    echo "WARNING: cannot start MCP attempt; registered nothing" >&2
    return 1
  fi
}

cpp_mcp_record() {
  local id="$1" outcome="$2" code="${3-}" keep=0
  # A later desk must not conceal a failed, unreadable or skipped desk.
  if [ "$id" = browser-pool ]; then
    if [[ "${CPP_MCP_RESULTS[$id]-}" = *'"outcome":"FAILED"'* ]]; then keep=1; fi
    if [[ "${CPP_MCP_RESULTS[$id]-}" = *'"outcome":"unverified"'* ]] && [ "$outcome" != FAILED ]; then keep=1; fi
    if [[ "${CPP_MCP_RESULTS[$id]-}" = *'"outcome":"skipped"'* ]] && [[ "$outcome" = installed || "$outcome" = already ]]; then keep=1; fi
  fi
  if [ "$keep" -eq 0 ]; then
    CPP_MCP_RESULTS[$id]="{\"step\":\"$id\",\"outcome\":\"$outcome\"${code:+,\"exit_code\":$code}}"
  fi
  if ! python3 "$CPP_MCP_STATE_HELPER" save --run-dir "$CPP_MCP_RUN_DIR" "${CPP_MCP_RESULTS[@]}"; then
    echo "WARNING: MCP result persistence failed; setup incomplete" >&2
    return 1
  fi
}

cpp_register_claude_mcp() {
  local server="$1" id="$1" state rc kind="$1"
  local -a args
  if [ "${2-}" = desk ]; then kind=desk; id=browser-pool; fi
  cpp_mcp_attempt || return 1
  case "$kind" in
    second-opinion) args=(--transport http --scope user "$server" "${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp") ;;
    playwright) args=(--transport stdio --scope user "$server" -- npx -y @playwright/mcp@latest --headless) ;;
    tavily) args=(--transport stdio --scope user "$server" -e "TAVILY_API_KEY=${TAVILY_API_KEY-}" -- npx -y tavily-mcp@latest) ;;
    sequential-thinking) args=(--transport stdio --scope user "$server" -- npx -y @modelcontextprotocol/server-sequential-thinking) ;;
    desk)
      if [[ ! "$server" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        cpp_mcp_record browser-pool unverified || return 1
        echo "WARNING: unsupported browser desk name; registered nothing"
        return 2
      fi
      args=(--transport stdio --scope user "$server" -- npx -y @playwright/mcp@0.0.77 --isolated)
      ;;
    *) echo "WARNING: unsupported Claude MCP server; registered nothing"; return 2 ;;
  esac
  if ! claude mcp list >/dev/null 2>&1; then
    cpp_mcp_record "$id" unverified || return 1
    echo "WARNING: claude MCP registrations could not be read; registered nothing"
    return 3
  fi
  # Query USER scope, not a list that also contains project registrations (#1256).
  if python3 - "${CLAUDE_CONFIG_DIR:-$HOME}/.claude.json" "$server" <<'PY_MCP'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    sys.exit(1)
except (OSError, ValueError):
    sys.exit(3)
servers = data.get("mcpServers", {}) if isinstance(data, dict) else None
if not isinstance(servers, dict):
    sys.exit(3)
if sys.argv[2] not in servers:
    sys.exit(1)
sys.exit(0 if isinstance(servers[sys.argv[2]], dict) else 3)
PY_MCP
  then state=0; else state=$?; fi
  if [ "$state" -eq 0 ]; then
    cpp_mcp_record "$id" already || return 1
    echo "-> $server MCP already registered at user scope (skipped)"
    return 0
  elif [ "$state" -ne 1 ]; then
    cpp_mcp_record "$id" unverified || return 1
    echo "WARNING: could not read user MCP config (unreadable or wrong shape) - registered nothing"
    return 3
  fi
  if [ "$server" != second-opinion ] && ! command -v npx >/dev/null 2>&1; then
    cpp_mcp_record "$id" skipped || return 1
    echo "WARNING: npx not found; $server registration skipped"
    return 0
  fi
  if [ "$server" = tavily ] && [ -z "${TAVILY_API_KEY-}" ]; then
    cpp_mcp_record "$id" skipped || return 1
    echo "WARNING: TAVILY_API_KEY not set; tavily registration skipped"
    return 0
  fi
  if claude mcp add "${args[@]}" >/dev/null 2>&1; then
    cpp_mcp_record "$id" installed 0 || return 1
    echo "✓ $server MCP registered (user scope)"
    return 0
  else
    rc=$?
    cpp_mcp_record "$id" FAILED "$rc" || return 1
    echo "WARNING: $server MCP registration FAILED (exit $rc)"
    return "$rc"
  fi
}

cpp_register_codex_mcp() {
  local server="$1" id="codex-$1" list state rc
  local -a args
  cpp_mcp_attempt || return 1
  case "$server" in
    second-opinion) args=("$server" --url "${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp") ;;
    playwright) args=("$server" -- npx -y @playwright/mcp@latest --headless) ;;
    *) echo "WARNING: unsupported Codex MCP server; registered nothing"; return 2 ;;
  esac
  if ! list=$(codex mcp list --json 2>/dev/null); then
    cpp_mcp_record "$id" unverified || return 1
    echo "WARNING: codex MCP registrations could not be read; registered nothing"
    return 3
  fi
  if printf '%s\n' "$list" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except (OSError, ValueError):
    sys.exit(3)
if not isinstance(data, list) or any(not isinstance(x, dict) or not isinstance(x.get("name"), str) for x in data):
    sys.exit(3)
sys.exit(0 if any(x["name"] == sys.argv[1] for x in data) else 1)
' "$server"; then state=0; else state=$?; fi
  if [ "$state" -eq 0 ]; then
    cpp_mcp_record "$id" already || return 1
    echo "-> $server MCP already registered with Codex (skipped)"
    return 0
  elif [ "$state" -ne 1 ]; then
    cpp_mcp_record "$id" unverified || return 1
    echo "WARNING: could not read Codex MCP registration shape; registered nothing"
    return 3
  fi
  if [ "$server" = playwright ] && ! command -v npx >/dev/null 2>&1; then
    cpp_mcp_record "$id" skipped || return 1
    echo "WARNING: npx not found; Codex playwright registration skipped"
    return 0
  fi
  if [ "$server" = second-opinion ] && ! curl -sf --max-time 2 "${SECOND_OPINION_URL:-http://127.0.0.1:8080}/" >/dev/null 2>&1; then
    cpp_mcp_record "$id" skipped || return 1
    echo "WARNING: second-opinion not reachable; Codex registration skipped"
    return 0
  fi
  if codex mcp add "${args[@]}" >/dev/null 2>&1; then
    cpp_mcp_record "$id" installed 0 || return 1
    echo "✓ $server MCP registered with Codex"
    return 0
  else
    rc=$?
    cpp_mcp_record "$id" FAILED "$rc" || return 1
    echo "WARNING: Codex $server MCP registration FAILED (exit $rc)"
    return "$rc"
  fi
}
cpp_mcp_load
# CPP_MCP_ROUTINES_END
```

Initialize the per-run files now, after confirmation. Retain the printed path
and rebind it explicitly in each later tool call; each new wizard/recovery run
must initialize its own directory, even in the same project. These temporary
local artifacts are historical setup observations, not a host readiness scan.
Do not copy another run's results. They are removed after the final receipt is
written; failed persistence retains the temporary run for retry.

```bash
# CPP_MCP_RUN_INIT_BEGIN
if CPP_MCP_RUN_DIR=$(python3 "$CPP_DIR/scripts/cpp-mcp-state.py" begin \
    --document "$CPP_DIR/.claude/commands/cpp/init.md"); then
  printf 'CPP_MCP_RUN_DIR=%s\n' "$CPP_MCP_RUN_DIR"
else
  echo "CPP Installation Incomplete"
  echo "WARNING: MCP run state could not be initialized"
  exit 1
fi
# CPP_MCP_RUN_INIT_END
```


### Commands Execution

Execution guard: `CPP_SECTION=commands`.

**User scope first (issue #663):** per-family symlinks into
`~/.claude/commands/` serve the command surface to every session on this
host and follow `git pull` atomically. The helper owns the safety rules
(replaces only symlinks it created, never a user's file or dir) - do not
re-implement it inline. Call it BARE (the #581 allowlist rule matches the
stable path); on exit 127 fall back to `"$CPP_DIR/scripts/cpp-commands-link.sh"`:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section commands || exit $?
~/.claude/scripts/cpp-commands-link.sh
```

`foreign` lines in its output are the user's own content winning a name
collision - report them, never "fix" them. If a retired `/plugin`
marketplace cache still carries CPP families (#662 / ADR 0005), tell the user to
run `/plugin uninstall <family>@cpp` for each so sessions stop reading the
stale cached copies.

**Project scope (optional, this project only):**

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section commands || exit $?
# Create .claude directory if needed
mkdir -p .claude

# Symlink commands (skip if exists)
if [ ! -L ".claude/commands" ] && [ ! -d ".claude/commands" ]; then
  if ln -sf "$CPP_DIR/.claude/commands" .claude/commands; then
    echo "✓ Commands symlinked"
  else
    echo "WARNING: setup command failed (exit $?)."
  fi
else
  echo "→ Commands already installed (skipped)"
fi
```

**Shared-stash guard (ON BY DEFAULT, issue #1056):**

A linked worktree isolates the working tree and NOT the refs: `refs/stash` lives
in the repository's common git dir, so every worktree plus the main checkout
share ONE stack, and `git stash pop` takes whatever is on top rather than what
you put there. It has swapped sessions' uncommitted work three times in this
project. The guard is a git `reference-transaction` hook, so it binds every
caller - a human, Claude, Codex, Qwen, a shell script - rather than only whoever
is reading the document that states the rule.

Install it into THIS project, bare (resolution order per #581/#590; on exit 127
fall back to `"$CPP_DIR/scripts/stash-worktree-guard.sh"`):

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section commands || exit $?
~/.claude/scripts/stash-worktree-guard.sh --install .
```

Act on `STASH_GUARD:`:

- `installed` / `current` - armed. Say so in the Step 7 summary.
- `disabled` - this repository recorded `cpp.stashGuard=false` on a previous
  opt-out. **Leave it off** and do not re-offer: re-asking every install is the
  oscillation an opt-out exists to end.
- `foreign` - a different `reference-transaction` hook is already installed.
  Report it, change nothing. That hook fires on every ref update here; merging
  the two is the user's call.
- `unsupported` - git below 2.28 (no `reference-transaction` hook), or a
  RELATIVE `core.hooksPath` (each worktree resolves it against its own
  top-level, so no single install could cover the family). Report the reason.

**Then offer the opt-out, once:**

```
=== Shared-stash guard ===

Installed: `git stash push` from a linked worktree is now refused, because the
stash stack is shared with every other worktree of this repository.

It guards `push` only. `pop` and `drop` cannot be guarded - git removes the
entry before a hook can refuse - so its silence there is not approval. See
docs/agents/shared-stash-stack.md.

Consent: keeping the reference-transaction hook leaves the project hook installed.
No removes CPP's own hook and writes cpp.stashGuard=false in the repository Git config.

Keep it on? [Y/n]
```

On `n`, turn it off and RECORD the choice, so `/cpp:update` and the flow
worktree lane do not reinstall it:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section commands || exit $?
~/.claude/scripts/stash-worktree-guard.sh --uninstall .
```

That writes `cpp.stashGuard=false` in the repository config. The way back on is
`--enable`, and the prompt above must not be shown again while the record
stands.

### Scripts Execution

Execution guard: `CPP_SECTION=scripts`.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
# BOOTSTRAP THE SEAM, AND CREATE ITS DIRECTORY IN ONE CALL (issue #1198).
#
# This line used to invoke ~/.claude/scripts/cpp-host-write.sh to CREATE
# ~/.claude/scripts - the directory the helper itself gets linked into, two
# statements below. On a fresh host, which is exactly what /cpp:init is for,
# that symlink does not exist yet: the call exited 127, Tier 2 installed
# nothing, and every later step reported success anyway.
#
# The checkout copy always exists when a checkout does, and installing the seam
# THROUGH the seam keeps the write declared and deferrable rather than making it
# a carve-out the check-cpp-host-writes gate has to be taught to ignore.
# `link-into` does its own `mkdir -p`, so this single call replaces the
# ensure-dir it supersedes.
"$CPP_DIR/scripts/cpp-host-write.sh" link-into \
  "$CPP_DIR/scripts/cpp-host-write.sh" ~/.claude/scripts cpp-host-write.sh
case $? in
  0) SEAM_STATUS="available" ;;
  3) SEAM_STATUS="the seam's own install was deferred by request" ;;
  *) SEAM_STATUS="UNAVAILABLE - the seam could not be installed" ;;
esac
echo "Host-write seam: $SEAM_STATUS"
#: /cpp:init CREATING ~/.claude/scripts is correct here and is the difference
#: from /cpp:update's Step 5a, which must not: this is the Tier 2 installer,
#: the tier the user just chose, so the directory is the deliverable rather
#: than a side effect. Update refreshes an EXISTING install and promises never
#: to self-upgrade a tier, so it reads the directory before bootstrapping.

# Symlink all executable helpers, regardless of extension (issue #669: the
# old *.sh-only glob skipped flow-wave-plan.py, so its shipped allow rule in
# templates/claude-settings-permissions.json pointed at a nonexistent path).
# The executability gate skips non-executable .py library files, directories,
# and __pycache__.
SEAM_OK=0; SEAM_DEFERRED=0; SEAM_FAILED=0
for script in "$CPP_DIR"/scripts/*; do
  [ -f "$script" ] && [ -x "$script" ] || continue
  name=$(basename "$script")
  # Through the declaring seam (#1132). One `ln -sf` in the source becomes
  # ninety-odd links at run time, which is why no per-site enumeration found
  # this write. The helper carries the already-linked skip this block had.
  ~/.claude/scripts/cpp-host-write.sh link-into "$script" ~/.claude/scripts "$name"
  #: COMPOSE A VERDICT, do not just run (issue #1198). Ninety calls that drew no
  #: conclusion meant an absent seam linked nothing and the step said so nowhere.
  case $? in
    0) SEAM_OK=$((SEAM_OK + 1)) ;;
    3) SEAM_DEFERRED=$((SEAM_DEFERRED + 1)) ;;
    *) SEAM_FAILED=$((SEAM_FAILED + 1)) ;;
  esac
done
echo "→ Helper scripts: $SEAM_OK linked/current, $SEAM_DEFERRED deferred, $SEAM_FAILED failed"
[ "$SEAM_FAILED" -gt 0 ] && echo "  WARNING: $SEAM_FAILED script(s) were NOT linked. The allowlist rules installed below cite ~/.claude/scripts/<name> paths that will not exist."

# NO HOOKS ARE INSTALLED HERE (issue #1206). CPP used to copy
# .claude/hooks.json into every initialised project. Claude Code never loads
# that path, so nothing in it ever ran and its only effect was to make people
# believe their tool output was being masked. Removed rather than relocated:
# the owner ruled against registering it (Decision 2 declined).
#
# A project that already has one from an older install is offered its removal
# by /cpp:update Step 4.7.
```

**Permission Profile Configuration**

Based on the profile selected in Step 3b, generate `.claude/settings.local.json`:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
# Generate settings.local.json based on selected profile
# (The profile JSON content is determined by user selection in Step 3b)

if [ ! -f ".claude/settings.local.json" ]; then
  # Write the selected profile to settings.local.json
  if cat > .claude/settings.local.json << 'SETTINGS_EOF'
{PROFILE_JSON_CONTENT}
SETTINGS_EOF
  then
    echo "✓ Permission profile configured: {PROFILE_NAME}"
  else
    echo "WARNING: configuration write failed (exit $?)."
  fi
else
  echo "→ settings.local.json exists (skipped)"
  echo "  To reconfigure, delete .claude/settings.local.json and run /cpp:init"
fi

# Add settings.local.json to .gitignore if not already there
if [ -f ".gitignore" ]; then
  if ! grep -q "settings.local.json" .gitignore; then
    if printf '\n# Claude Code local settings (contains user-specific permissions)\n.claude/settings.local.json\n' >> .gitignore; then
      echo "✓ Added settings.local.json to .gitignore"
    else
      echo "WARNING: .gitignore update failed (exit $?)."
    fi
  fi
fi
```

Add `.claude/friction.jsonl` and `.claude/friction/` to the target `.gitignore`
if not already there (issue #1498). `/flow:auto`'s friction capture
(`scripts/friction-log.sh`) writes into this project's own `.claude/`, same
as CPP's own `.gitignore` (:288-289) - without this, friction capture dirties
the consumer project's working tree. Each entry is checked independently, so
re-running `/cpp:init` never duplicates a line already present, and a project
with no `.gitignore` at all is left alone (this step never creates one):

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
if [ -f ".gitignore" ]; then
  FRICTION_HEADER_WRITTEN=0
  for pattern in ".claude/friction.jsonl" ".claude/friction/"; do
    if ! grep -qxF -- "$pattern" .gitignore; then
      if [ "$FRICTION_HEADER_WRITTEN" -eq 0 ]; then
        echo "" >> .gitignore
        echo "# Claude Code friction capture (local, not shared history)" >> .gitignore
        FRICTION_HEADER_WRITTEN=1
      fi
      if echo "$pattern" >> .gitignore; then
        echo "✓ Added $pattern to .gitignore"
      else
        echo "WARNING: .gitignore update failed (exit $?)."
      fi
    fi
  done
fi
```

**Profile JSON Templates:**

- **Cautious**: `{"permissions":{"allow":["Read","Glob","Grep"],"deny":["Bash(rm -rf:*)","Bash(git push --force:*)"]}}`

- **Standard**: See Step 3b for full JSON

- **Trusted**: See Step 3b for full JSON, including the ask exceptions

- **YOLO**: See Step 3b; only after explicit selection and disclosure confirmation

- **Custom**: Build JSON from selected categories

**User-Level Flow Allowlist (Optional)**

Consent: merge permission rules into user `~/.claude/settings.json` (creating its parent/file if absent); existing unrelated settings remain. Applies to every project on this host, not just this project.

The project profiles above govern ONE repo. The `/flow:*` commands also run
git/gh workflow commands (issue reads, fetches and worktree creation,
the branch-slug text pipeline) in EVERY repo, which prompts on every run unless the rules
exist at user level. Offer to merge the CPP allowlist template into
`~/.claude/settings.json`:

```
=== Optional: User-Level Flow Allowlist ===

/flow commands run git/gh workflow commands (gh issue view, git fetch,
git worktree, slug pipelines) that triggers a permission prompt on every
run, in every repo, unless allowed at user level.

Merge the CPP workflow allowlist into ~/.claude/settings.json?
(This allows repository mutations including fetches and worktree creation.)
(Additive and idempotent - existing settings and rules are preserved.
Rationale and caveats: templates/claude-settings-permissions.md)  [y/N]
```

If yes:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
TEMPLATE="$CPP_DIR/templates/claude-settings-permissions.json"
TARGET="$HOME/.claude/settings.json"

BEFORE=$([ -f "$TARGET" ] && jq '(.permissions.allow // []) | length' "$TARGET" || echo 0)
# Through the declaring seam (#1132): the helper owns the write - defer
# check, parent dir, `{}` bootstrap, atomic tmp+mv - and this document keeps
# the jq program. A managed environment passes --defer ~/.claude/settings.json
# and gets a stated refusal naming the surface and its owner.
~/.claude/scripts/cpp-host-write.sh settings-merge "$TEMPLATE"
#: READ THE VERDICT (issue #1198). This pair printed a checkmark whether the
#: seam wrote, deferred by request, failed, or was absent. The delta softened it
#: - a failed merge shows "0 new rules" - but "✓ merged ... 0 new rules" still
#: asserts a merge, and on a fresh host AFTER is read from a file the merge
#: never touched.
SEAM_RC=$?
AFTER=$(jq '.permissions.allow | length' "$TARGET" 2>/dev/null || echo 0)

case "$SEAM_RC" in
  0) echo "✓ Flow allowlist merged into ~/.claude/settings.json ($((AFTER - BEFORE)) new rules, $AFTER total)" ;;
  3) echo "→ Flow allowlist DEFERRED by request - ~/.claude/settings.json was NOT modified" ;;
  127) echo "✗ Flow allowlist NOT merged - the host-write seam is not installed (see Tier 2 bootstrap)" ;;
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
echo "  Note: sed is allowed for the flow slug pipeline; see the template doc for the sed -i caveat."
```

If no:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
echo "→ Flow allowlist skipped"
echo "  Merge later via /cpp:update, or read templates/claude-settings-permissions.md"
```

**Permission-Prompt Census Hook (Optional)**

Consent: merge the PermissionRequest registration into user `~/.claude/settings.json`, creating its parent/file if absent. Later hook use appends project `.claude/friction.jsonl`; it observes prompts and does not grant permissions.

The retro loop's `permission-prompt` friction class (issue #426) can only be
captured by the harness: a manually approved tool call and an auto-allowed one
are indistinguishable to the model. `scripts/hook-permission-census.sh` (a
`PermissionRequest` hook, installed as a Tier 2 script above) fires when a
permission dialog is shown and appends one risk-rated record to the project's
`.claude/friction.jsonl`, so `/self-improvement:retro` Step 4 gets real input
(issue #482). It is observe-only (never influences the decision) and fail-open.
Registering it edits `~/.claude/settings.json` - the same user-level trust
boundary as the flow allowlist above - so it is offered, not applied silently:

```
=== Optional: Permission-Prompt Census Hook ===

Register the observe-only PermissionRequest census hook in
~/.claude/settings.json? It records each permission prompt (with a derived
allow-rule candidate and a risk tier) to the project's friction ledger so
/self-improvement:retro can propose an allowlist from real data. Never blocks
or alters a permission decision.  [y/N]
```

If yes:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
TARGET="$HOME/.claude/settings.json"
CENSUS_CMD="~/.claude/scripts/hook-permission-census.sh"
# Through the declaring seam (#1132): the helper owns the write, this
# document keeps the jq program. --defer ~/.claude/settings.json yields a
# stated refusal instead of a silent skip.
~/.claude/scripts/cpp-host-write.sh settings-edit --arg cmd "$CENSUS_CMD" <<'JQ'

# Idempotent: add the hook only if this exact command is not already registered.
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
  127) echo "✗ Census hook NOT registered - the host-write seam is not installed" ;;
  *) echo "✗ Census hook registration FAILED - check settings.json - a failed write may have modified it" ;;
esac
```

If no:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
echo "→ Permission-prompt census hook skipped"
echo "  Register later via /cpp:update, or read docs/HOST_MANAGED_ARTIFACTS.md"
```

**Session-Open Reminders (Optional, opt-in)**

Consent: merge the SessionStart registration into user `~/.claude/settings.json`, creating its parent/file if absent. No stored credentials; later sessions read the advisory inputs described below.

`scripts/hook-pending-retro.sh` (a `SessionStart` hook, installed as a Tier 2
script above) prints up to TWO advisory lines at session open, each independent
of the other:

1. **Pending retro material** - `.claude/friction.jsonl` signals (actionable vs
   the bulk permission-prompt census, counted separately) plus any uncodified
   `Status: proposed` learnings, pointing at `/self-improvement:retro` (#530).
2. **Retired CPP marketplace cache** - which families still remain under
   `~/.claude/plugins/cache/cpp/`, via `scripts/install-drift.sh` (#622/#662),
   so the host can migrate them with `/plugin uninstall <family>@cpp` before
   #663 restores the canonical symlink tier.

It only SURFACES; it never codifies, and it is silent when there is nothing to
report. CPP ships no hooks file at all since #1206, so it never turns
itself on; registering it edits `~/.claude/settings.json` (the user-level trust
boundary), so it is offered, not applied - default N:

```
=== Optional: Session-Open Reminders (opt-in) ===

Register the session-open reminder in ~/.claude/settings.json? It prints one
advisory line when pending friction signals or uncodified learnings exist (run
/self-improvement:retro), and one when a retired CPP marketplace cache is still
pending uninstall (#662/#663). Surfaces only - never codifies, never blocks.
Silent when there is nothing to report.  [y/N default N]
```

If yes:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
TARGET="$HOME/.claude/settings.json"
RETRO_CMD="~/.claude/scripts/hook-pending-retro.sh"
# Through the declaring seam (#1132): the helper owns the write, this
# document keeps the jq program. --defer ~/.claude/settings.json yields a
# stated refusal instead of a silent skip.
~/.claude/scripts/cpp-host-write.sh settings-edit --arg cmd "$RETRO_CMD" <<'JQ'

# Idempotent: add the hook only if this exact command is not already registered
# (tolerant of both the {hooks:[...]} group shape and a bare {command} entry).
  .hooks = (.hooks // {})
  | .hooks.SessionStart = (.hooks.SessionStart // [])
  | if any(.hooks.SessionStart[]?; (.command == $cmd) or ((.hooks // [])[]?.command == $cmd))
    then .
    else .hooks.SessionStart += [{"hooks":[{"type":"command","command":$cmd}]}]
    end
JQ
case $? in
  0) echo "✓ Session-open retro reminder registered in ~/.claude/settings.json" ;;
  3) echo "→ Session-open retro reminder DEFERRED by request - settings.json was NOT modified" ;;
  127) echo "✗ Session-open retro reminder NOT registered - the seam is not installed" ;;
  *) echo "✗ Session-open retro reminder registration FAILED - check settings.json - a failed write may have modified it" ;;
esac
```

If no:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
echo "→ Pending-retro reminder skipped (default)"
echo "  Enable later via /cpp:update"
```

**Shell Prompt Integration (Optional)**

Consent: append a managed prompt block to user `~/.bashrc`, creating it if absent. This changes future interactive shells on this host.

Ask the user if they want shell prompt integration:

```
Would you like to add worktree context to your shell prompt?

This shows [PREFIX #ISSUE] before your prompt, e.g.:
  [CPP #42] ~/Projects/claude-power-pack-issue-42 $

Add to ~/.bashrc? [y/N]
```

If yes:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
# Add to bashrc through the declaring helper (#1139). The helper declares
# ~/.bashrc as a host surface it writes, and a managed environment can defer
# it with --defer ~/.bashrc and get a stated refusal rather than a failure.
# Guarded by its marker, like the tmux block below: running /cpp:init twice
# leaves one export, not two (#1142).
~/.claude/scripts/cpp-host-write.sh bashrc-append \
  '# Claude Power Pack - worktree context in prompt' - <<'PS1_EOF'

# Claude Power Pack - worktree context in prompt
export PS1='$(~/.claude/scripts/prompt-context.sh)\w $ '
PS1_EOF
case $? in
  0) echo "✓ Shell prompt configured (restart shell or source ~/.bashrc)" ;;
  3) echo "→ Shell prompt DEFERRED by request - ~/.bashrc was NOT modified" ;;
  127) echo "✗ Shell prompt NOT configured - the host-write seam is not installed" ;;
  *) echo "✗ Shell prompt configuration FAILED - check ~/.bashrc - a failed write may have modified it" ;;
esac
```

**Tmux Auto-Start (Optional)**

Consent: append a managed tmux block to user `~/.bashrc`, creating it if absent. This changes future interactive shells on this host.

Ask the user if they want tmux to start automatically in new terminal tabs:

```
=== Optional: Tmux Auto-Start ===

Start tmux automatically when opening a new terminal tab?

Each tab gets its own independent tmux session. Skipped inside existing
tmux sessions and non-interactive shells (scripts, cron, Claude Code).

Requires: tmux installed (apt install tmux)

Add to ~/.bashrc? [y/N]
```

If yes:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
# Check if tmux is installed
if ! command -v tmux &>/dev/null; then
  echo "⚠ tmux not found. Install it first:"
  echo "  sudo apt install tmux"
  echo "  Skipping tmux auto-start."
else
  # Through the declaring helper (#1139), which owns the marker guard this
  # block already had. A managed environment defers it with --defer ~/.bashrc
  # and gets a stated refusal naming the surface and its owner.
  ~/.claude/scripts/cpp-host-write.sh bashrc-append 'tmux new-session' - <<'TMUX_EOF'

# Claude Power Pack - tmux auto-start
if command -v tmux &>/dev/null && [ -z "$TMUX" ] && [[ $- == *i* ]]; then
    tmux new-session
fi
TMUX_EOF
case $? in
  0) echo "✓ tmux auto-start configured in ~/.bashrc" ;;
  3) echo "→ tmux auto-start DEFERRED by request - ~/.bashrc was NOT modified" ;;
  127) echo "✗ tmux auto-start NOT configured - the host-write seam is not installed" ;;
  *) echo "✗ tmux auto-start configuration FAILED - check ~/.bashrc - a failed write may have modified it" ;;
esac
fi
```

If no:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
echo "→ Tmux auto-start skipped"
echo "  Add later by appending to ~/.bashrc:"
echo '  if command -v tmux &>/dev/null && [ -z "$TMUX" ] && [[ $- == *i* ]]; then tmux new-session; fi'
```

**Project Makefile Handoff**

Configure project build targets through `/project:init` for new projects or
`/cicd:init` for existing repositories. Run that project workflow separately;
this host setup leaves every existing project entry intact.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
echo "Project Makefile setup: /project:init (new projects); /cicd:init (existing repositories)."
```

**Happy CLI Installation (Optional)**

Consent: if absent, install happy-coder with npm into the resolved global prefix and configured npm cache. Show those areas before offering this choice; onboarding is a later separate action.

Ask the user if they want to install happy-cli:

```
=== Optional: Happy CLI ===

Happy CLI is an AI coding assistant that complements Claude Code.
https://github.com/slopus/happy-cli

Install happy-cli? [y/N]
```

If yes:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
# Check if already installed
if command -v happy &>/dev/null; then
  echo "→ happy-cli already installed (skipped)"
  happy --version 2>&1 | head -1
else
  echo "Installing happy-cli..."
  if npm install -g happy-coder && command -v happy &>/dev/null; then
    echo "✓ happy-cli installed"
    echo "  Run 'happy' to complete onboarding"
  else
    echo "⚠ Installation failed - check npm permissions"
    echo "  Try: sudo npm install -g happy-coder"
  fi
fi
echo "  Verify /cpp:happy-check availability with /cpp:status."
```

If no:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
echo "→ Happy CLI installation skipped"
```

**Spec-Kit CLI Installation (Optional)**

Consent: if absent, install specify-cli in the resolved uv tool directory and executable directory (normally `~/.local/bin`), using the uv cache. This does not scaffold a project.

Ask the user if they want to install the official spec-kit CLI (`specify`). This is the
authoring engine behind `/spec:adopt`; installing it now means `/spec:adopt` and the
`/speckit-*` skills work in any project without a first-run install step. This installs
only the CLI - it does NOT scaffold `.specify/` into any project (that stays on-demand
via `/spec:adopt`).

```
=== Optional: Spec-Kit CLI ===

Spec-Kit is GitHub's spec-driven-development toolkit. CPP's /spec:adopt delegates to
its `specify` CLI (constitution -> specify -> clarify -> plan -> tasks).
https://github.com/github/spec-kit

Install the spec-kit CLI? [y/N]
```

If yes:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
# Check if already installed
if command -v specify &>/dev/null; then
  echo "→ spec-kit CLI already installed (skipped)"
  specify version 2>/dev/null | head -1 || true
else
  echo "Installing spec-kit CLI (uv tool)..."
  if uv tool install specify-cli --from git+https://github.com/github/spec-kit.git && command -v specify &>/dev/null; then
    echo "✓ spec-kit CLI installed"
    echo "  Run /spec:adopt in a project to scaffold spec-kit into it"
  else
    echo "⚠ Installation failed - ensure 'uv' is installed and ~/.local/bin is on PATH"
    echo "  Try: uv tool install specify-cli --from git+https://github.com/github/spec-kit.git"
  fi
fi
echo "  Verify /spec:adopt availability with /cpp:status."
```

If no:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section scripts || exit $?
echo "→ Spec-Kit CLI installation skipped (/spec:adopt installs it on first use)"
```

### MCP Execution

Execution guard: `CPP_SECTION=mcp`.

#### 3a. Legacy Runtime Note (informational)

CPP no longer builds or runs a Docker MCP stack, and it no longer manages systemd
MCP units. Tier 3 registers an external second-opinion server plus the upstream
playwright npx server; no containers are built here. If an older install left
legacy systemd MCP units or retired MCP containers (mcp-second-opinion,
aws-secrets-agent, mcp-playwright-persistent) behind, run /cpp:update to tear
them down.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section mcp || exit $?
LEGACY_SYSTEMD_UNITS=""
for unit in mcp-second-opinion second-opinion mcp-playwright mcp-playwright-persistent playwright-persistent mcp-evaluate evaluate mcp-coordination coordination; do
  [ -f "/etc/systemd/system/${unit}.service" ] && LEGACY_SYSTEMD_UNITS="$LEGACY_SYSTEMD_UNITS system:${unit}"
  [ -f "$HOME/.config/systemd/user/${unit}.service" ] && LEGACY_SYSTEMD_UNITS="$LEGACY_SYSTEMD_UNITS user:${unit}"
done

if [ -n "$LEGACY_SYSTEMD_UNITS" ]; then
  echo "WARNING: legacy systemd MCP unit files were detected:"
  for item in $LEGACY_SYSTEMD_UNITS; do
    echo "  - $item"
  done
  echo ""
  echo "Run /cpp:update to migrate or remove legacy systemd units and leftover containers."
  echo "/cpp:init no longer installs, starts, or manages systemd services."
fi
```

#### 3b. Second Opinion Server (external)

The second-opinion MCP server is a SEPARATE project. Run it from its own repo -
it is not built or started by CPP:

  https://github.com/cooneycw/mcp-second-opinion

Start the server there (on localhost or a Tailscale host). It listens on
http://127.0.0.1:8080/mcp (streamable-http). API keys (Gemini/OpenAI/Anthropic)
are configured in that repo, not here.

The next step registers it at USER scope, at
`${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp`. That is the only definition
CPP makes: the repository used to ship a root `.mcp.json` defining it at project
scope as well, and whenever the two differed Claude Code reported
`[Conflicting scopes]` (issue #1256), so that file is gone. If the server is not
on localhost (e.g. a Tailscale host), export `SECOND_OPINION_URL` with its base
URL, no `/mcp`, before this step - do not edit the URL in the command. The value
is expanded once, at registration: if you later change `SECOND_OPINION_URL`,
re-register (`claude mcp remove second-opinion -s user`, then this step again).

#### 3c. Register MCP Servers

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section mcp || exit $?
# Rebind CPP_MCP_RUN_DIR to this run's printed absolute path in this tool call.
if [ -z "${CPP_MCP_RUN_DIR-}" ] || ! source "$CPP_MCP_RUN_DIR/routines.sh"; then
  echo "CPP Installation Incomplete"
  echo "WARNING: MCP run state could not be loaded"
  exit 1
fi
# Approved Tier 3 registrations, using the shared definitions above.
if cpp_register_claude_mcp second-opinion; then :; else echo "WARNING: second-opinion setup incomplete"; fi
if cpp_register_claude_mcp playwright; then :; else echo "WARNING: playwright setup incomplete"; fi
if cpp_register_claude_mcp tavily; then :; else echo "WARNING: tavily setup incomplete"; fi

# Report only: never remove a conflicting registration automatically.
USER_JSON="${CLAUDE_CONFIG_DIR:-$HOME}/.claude.json"
python3 "$CPP_DIR/scripts/mcp-drift.py" --scope-check --claude-json "$USER_JSON" --project-dir "$CPP_DIR" \
  || echo "⚠ MCP scope check did not pass (see above) - init continues"
```

#### 3d. Register the browser desk pool (optional, off by default)

Consent: create project `.claude/playwright-pool.json` if absent and merge desk registrations into the user MCP config (`${CLAUDE_CONFIG_DIR:-$HOME}/.claude.json`). npx uses its cache, later browser downloads use `~/.cache/ms-playwright`, and later sessions write project `.claude/playwright-state/`. Show the configured desk names/count before the choice.

The **lease-desk pool** powers `/browser:session` - named **concurrent** browser
sessions over upstream `@playwright/mcp` (issue #421). It is opt-in: it registers
N always-present upstream instances ("desks"), each adding a `browser_*` tool
surface to every session's startup context. Single-session work (`/qa:test`, a
one-off screenshot) does **not** need it.

Ask the user with AskUserQuestion: **"Enable the browser desk pool (named concurrent
sessions)? Adds N upstream playwright-mcp instances via npx."** Default: **No**.

If the user opts in, seed the pool config into the project and register the desks as
stdio MCP servers (upstream via `npx`, no custom image, pinned version):

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section mcp || exit $?
# Rebind CPP_MCP_RUN_DIR to this run's printed absolute path in this tool call.
if [ -z "${CPP_MCP_RUN_DIR-}" ] || ! source "$CPP_MCP_RUN_DIR/routines.sh"; then
  echo "CPP Installation Incomplete"
  echo "WARNING: MCP run state could not be loaded"
  exit 1
fi
# Seed the project's pool config (edit desk count / idle timeout there later).
mkdir -p .claude
if [ ! -f .claude/playwright-pool.json ]; then
  if cp "$CPP_DIR/templates/playwright-pool.example.json" .claude/playwright-pool.json; then
    echo "✓ Seeded .claude/playwright-pool.json"
  else
    echo "WARNING: setup command failed (exit $?)."
  fi
fi

# Register one MCP server per desk listed in the pool config. Each runs upstream
# @playwright/mcp with --isolated (blank context per lease; session identity lives
# in the portable state file, not the desk).
unset 'CPP_MCP_RESULTS[browser-pool]'
if DESKS=$(python3 - <<'PY_DESKS'
import json, re, sys
try:
    with open('.claude/playwright-pool.json', encoding='utf-8') as f:
        data = json.load(f)
    desks = data.get('desks') if isinstance(data, dict) else None
    if not isinstance(desks, list) or not desks:
        sys.exit(3)
    if any(not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', name) for name in desks):
        sys.exit(3)
except (OSError, ValueError):
    sys.exit(3)
print('\n'.join(desks))
PY_DESKS
); then
  # Every element has been validated before the first registration.
  while IFS= read -r desk; do
    if cpp_register_claude_mcp "$desk" desk; then :; else echo "WARNING: browser desk setup incomplete"; fi
  done <<< "$DESKS"
else
  cpp_mcp_record browser-pool unverified || exit 1
  echo "WARNING: browser desk configuration could not be read or has invalid names; no desks registered."
fi

echo ""
echo "IMPORTANT: restart Claude Code so the playwright-desk-* servers load at startup"
echo "(MCP config is read only at startup; mid-session registration does not take effect)."
echo "Then verify with: /browser:session pool"
```

### CI/CD Execution (Host CI Capabilities)

Execution guard: `CPP_SECTION=cicd`.

Run the prerequisite boundary against the verified CPP source before any host
probe. A refusal leaves Tier 4 unexecuted: report missing/unknown prerequisites
and continue only other authorized setup/repair choices. Never claim persistence
when the seam fails or defers. This tier performs no project generation.

<!-- CPP_TIER4_PREFLIGHT_BEGIN -->
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section cicd || exit $?
CPP_TIER4_REPORT=$(bash "$CPP_DIR/scripts/flow-preflight.sh" --json --repo "$PWD" --checks uv,cpp_python)
CPP_TIER4_STATUS=$?
printf '%s\n' "$CPP_TIER4_REPORT" | bash "$CPP_DIR/scripts/flow-preflight.sh" --json --checks uv,cpp_python --validate-exit "$CPP_TIER4_STATUS"
if [ "$?" -ne 0 ]; then
  echo "Tier 4 prerequisites unverified; no host CI probe ran." >&2
  exit 1
fi
```
<!-- CPP_TIER4_PREFLIGHT_END -->

The projects-folder answer is requested once during disclosure. If the user
accepts the default, resolve it from the verified CPP main checkout:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section cicd || exit $?
if [ -z "${CPP_PROJECTS_ROOT:-}" ]; then
  CPP_COMMON_DIR=$(git -C "$CPP_DIR" rev-parse --path-format=absolute --git-common-dir) || exit 1
  CPP_CURRENT_GIT_DIR=$(git -C "$CPP_DIR" rev-parse --absolute-git-dir) || exit 1
  if [ "$CPP_CURRENT_GIT_DIR" = "$CPP_COMMON_DIR" ]; then
    CPP_MAIN_CHECKOUT=$(git -C "$CPP_DIR" rev-parse --show-toplevel) || exit 1
    CPP_PROJECTS_ROOT=$(dirname "$CPP_MAIN_CHECKOUT")
  else
    CPP_PROJECTS_ROOT=$(git --git-dir "$CPP_COMMON_DIR" worktree list --porcelain -z | python3 -c 'import pathlib,sys; entry=sys.stdin.read().split("\0",1)[0]; assert entry.startswith("worktree "); main=pathlib.Path(entry[9:]); assert (main/".git").exists(); print(main.parent)') || exit 1
  fi
fi
```

Use a host-local uv environment/cache and disable bytecode writes. `--locked`
behavior keeps the CPP lock unchanged even if the invoked repository is CPP.
These runtime cache locations are part of Tier 4 consent; no project `.venv`,
Makefile, cicd config, workflow or container files are created by this tier.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section cicd || exit $?
CPP_HOST_RUNTIME="$HOME/.cache/claude-power-pack/host-ci"
CPP_HOST_CI_REPORT=$(PYTHONPATH="$CPP_DIR:$PYTHONPATH" env -u UV_PROJECT_ENVIRONMENT "CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT-}" "CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT_PRESENT=${UV_PROJECT_ENVIRONMENT+x}" UV_PROJECT_ENVIRONMENT="$CPP_HOST_RUNTIME/venv" UV_CACHE_DIR="$CPP_HOST_RUNTIME/uv" UV_LOCKED=1 PYTHONDONTWRITEBYTECODE=1 uv run --python 3.11 --no-python-downloads --project "$CPP_DIR" python -m lib.cicd host-ci --path "$PWD" --projects-root "$CPP_PROJECTS_ROOT" --write)
CPP_HOST_CI_STATUS=$?
printf '%s\n' "$CPP_HOST_CI_REPORT"
# Derive this observation from the actual write receipt, never from tier choice.
if CPP_HOST_UPDATED_RESULTS=$(printf '%s\n' "$CPP_HOST_CI_REPORT" | python3 "$CPP_DIR/scripts/cpp-install-receipt.py" host-ci-outcome --exit-code "$CPP_HOST_CI_STATUS" --steps-json "${STEP_RESULTS_JSON:-[]}"); then
  STEP_RESULTS_JSON="$CPP_HOST_UPDATED_RESULTS"
  printf 'CPP_INSTALL_STEP_RESULTS: %s\n' "$STEP_RESULTS_JSON"
else
  # An unrecorded retry must never leave an older green row as this run's evidence.
  CPP_HOST_PRIOR_STEP_RESULTS_JSON="${STEP_RESULTS_JSON:-[]}"
  STEP_RESULTS_JSON=""
  echo "Host CI observation unverified; retain prior metadata and retry before saving the receipt." >&2
  exit 1
fi
case "$CPP_HOST_CI_STATUS" in
  0) echo "Host CI record persisted; see each provider's independent verdict above." ;;
  3) echo "Host CI persistence deferred, unavailable or unconfirmed; see record state above." ;;
  *) echo "Host CI record write failed; previous record preserved." >&2; exit 1 ;;
esac
```

For project CI selection and file generation, use `/project:init` or `/cicd:init`.

### Codex Execution (Codex Orchestration)

Execution guard: `CPP_SECTION=codex`.

#### 5a. Check Codex CLI

Consent: before offering an absent CLI install, show the resolved npm global prefix and cache used by @openai/codex. This installs a host-wide executable; it does not perform login.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section codex || exit $?
echo ""
echo "=== Tier 5: Codex Orchestration ==="
echo ""

if command -v codex &>/dev/null; then
  CODEX_VERSION=$(codex --version 2>/dev/null || echo "unknown")
  echo "[x] Codex CLI: $CODEX_VERSION"
else
  echo "[ ] Codex CLI: not installed"
  echo ""
  echo "Install Codex CLI?"
  echo "  npm install -g @openai/codex"
  echo ""
  # Ask user if they want to install
  # If yes:
  if npm install -g @openai/codex && command -v codex &>/dev/null; then
    echo "Codex CLI installed"
  else
    echo "WARNING: Codex CLI installation failed"
    echo "  Try: sudo npm install -g @openai/codex"
    echo "  Codex commands will not work until installed"
  fi
fi
```

#### 5b. Run Codex Doctor

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section codex || exit $?
if command -v codex &>/dev/null; then
  echo ""
  echo "Running codex doctor..."
  DOCTOR_OUTPUT=$(codex doctor 2>&1)
  DOCTOR_STATUS=$?
  echo "$DOCTOR_OUTPUT"

  if [ "$DOCTOR_STATUS" -ne 0 ]; then
    echo ""
    echo "WARNING: codex doctor failed (exit $DOCTOR_STATUS). Resolve before using /codex:auto."
  else
    echo "[x] codex doctor: all checks passed"
  fi
fi
```

#### 5c. Observe Codex Authentication Configuration

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section codex || exit $?
if command -v codex &>/dev/null; then
  echo ""
  echo "=== Codex Authentication Configuration ==="

  CODEX_CONFIG="$HOME/.codex/config.toml"
  if [ -n "$OPENAI_API_KEY" ]; then
    echo "[x] OPENAI_API_KEY is set (authentication unverified)"
  elif [ -f "$CODEX_CONFIG" ]; then
    echo "[?] Codex config exists; API credentials unverified"
  else
    echo "[?] No API-key environment variable or config file observed; authentication unverified"
    echo ""
    echo "Configure with one of:"
    echo "  codex login                    (interactive ChatGPT sign-in)"
    echo "  export OPENAI_API_KEY=sk-...   (environment variable)"
    echo ""
    echo "Codex supports ChatGPT sign-in or API-key authentication."
    echo "Use codex login status to inspect stored authentication; this step does not verify it."
  fi
fi
```

#### 5d. Register MCP Servers with Codex (Optional)

Consent: register the selected servers in `${CODEX_HOME:-$HOME/.codex}/config.toml`; create its parent/file if absent and preserve unrelated configuration. Show the server names and transport before asking.

Use the shared per-client definitions above, just as in Step 6 section 8b. Record both IDs in the offered-step set before asking this choice:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section codex || exit $?
# Rebind CPP_MCP_RUN_DIR to this run's printed absolute path in this tool call.
if [ -z "${CPP_MCP_RUN_DIR-}" ] || ! source "$CPP_MCP_RUN_DIR/routines.sh"; then
  echo "CPP Installation Incomplete"
  echo "WARNING: MCP run state could not be loaded"
  exit 1
fi
# Only run this block after Yes to this section's registration choice.
if command -v codex &>/dev/null; then
  if cpp_register_codex_mcp second-opinion; then :; else echo "WARNING: Codex second-opinion setup incomplete"; fi
  if cpp_register_codex_mcp playwright; then :; else echo "WARNING: Codex playwright setup incomplete"; fi
  echo "Restart Codex for tools to become available."
else
  cpp_mcp_record codex-second-opinion skipped || exit 1
  cpp_mcp_record codex-playwright skipped || exit 1
  echo "WARNING: Codex CLI not found; registration skipped"
fi
```

#### 5e. Install CPP Codex Skills (issue #575)

CPP generates one Codex skill dir per CPP command - but until #575 nothing in
`/cpp:init` or `/cpp:update` installed them to `~/.codex/skills/`, so a freshly
initialized Codex tier had the MCP servers registered and **not one CPP skill
installed**. The observed state on the primary box was `~/.codex/skills/`
containing only `.system`.

Since issue #1670 the skills are not a tracked tree: `--install` builds them
from the checkout's sources into a private directory, checks that build against
the sources, and only then publishes it. A build that differs from what the
sources generate is refused and the destination is left unchanged.

The installer replaces each managed skill dir wholesale and prunes managed
orphans at the destination, so a skill CPP has dropped stops loading. Ownership
is decided by the GENERATED marker: hand-curated skill dirs, skills the user
wrote, and dotted runtime state such as `.system` are never touched.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section codex || exit $?
if command -v codex &>/dev/null; then
  echo ""
  echo "=== Installing CPP Codex Skills ==="
  python3 "$CPP_DIR/scripts/codex-skill-sync.py" --install \
    || echo "WARNING: codex skill install failed (continuing)"
fi
```

Init only ever INSTALLS. Teardown of retired surfaces belongs to `/cpp:update`
Step 7.9, which asks before moving anything - a first-time init has no history
to reconcile.

#### 5f. Wire the Common-Memory Harness (issue #575)

`scripts/install-memory-harness.sh` links `scripts/cpp-memory` onto `PATH` and
installs the hand-authored Codex `/cpp-memory` prompt. Its header has always
said it is safe to re-run from `/cpp:update`, but no step ever invoked it, so
`cpp-memory` was missing from `PATH` unless run by hand. The Tier 2 symlink
loop now also links `scripts/cpp-memory` into `~/.claude/scripts/` (it links
every executable helper since issue #669), but that dir is not on `PATH` -
this harness remains the canonical `PATH` install. Idempotent.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section codex || exit $?
bash "$CPP_DIR/scripts/install-memory-harness.sh" \
  || echo "WARNING: memory harness install failed (continuing)"
```

### Local-model host-write seam (qwen/gemma capabilities)

Execution guard: `CPP_SECTION=local-seam`.

When qwen or gemma is selected, run this block once before either local setup.
These capabilities need only the declaring host-write helper, not all scripts.
Use the verified checkout copy to bootstrap it on a fresh host. An existing
unusable path is refused rather than overwritten; a deferred install leaves
local-tier configuration unexecuted. If this block returns nonzero, stop the
selected local-tier setup: do not run its endpoint persistence or provider/fence
blocks. Report that outcome in the final summary; other authorized setup may
continue.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section local-seam || exit $?
CPP_LOCAL_SEAM="$HOME/.claude/scripts/cpp-host-write.sh"
if [ ! -e "$CPP_LOCAL_SEAM" ] && [ ! -L "$CPP_LOCAL_SEAM" ]; then
  "$CPP_DIR/scripts/cpp-host-write.sh" link-into \
    "$CPP_DIR/scripts/cpp-host-write.sh" "$HOME/.claude/scripts" cpp-host-write.sh
  CPP_LOCAL_SEAM_STATUS=$?
  case "$CPP_LOCAL_SEAM_STATUS" in
    0) ;; # Check executability below before any configuration step.
    3)
      echo "Local-model host-write seam deferred by request; local-tier configuration not run."
      exit 3
      ;;
    *)
      echo "ERROR: local-model host-write seam install failed (exit $CPP_LOCAL_SEAM_STATUS); local-tier configuration not run."
      exit 1
      ;;
  esac
fi
if [ ! -f "$CPP_LOCAL_SEAM" ] || [ ! -x "$CPP_LOCAL_SEAM" ]; then
  echo "ERROR: local-model host-write seam is not an executable regular file at $CPP_LOCAL_SEAM; local-tier configuration not run."
  exit 1
fi
echo "Local-model host-write seam available: $CPP_LOCAL_SEAM"
```

### Qwen Execution (Local Qwen Orchestration)

Execution guard: `CPP_SECTION=qwen`.

Only run when the resolved plan includes `qwen`; commands are its prerequisite. Ask whether this machine SERVES the model or
CONSUMES a remote server before running the checks.

#### 6a. Verify the Qwen Code CLI Harness (no API key needed)

Consent: before offering an absent Qwen Code CLI install, show the resolved npm global prefix and cache used by @qwen-code/qwen-code. No cloud API key is stored.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section qwen || exit $?
echo ""
echo "=== Tier 6: Local Qwen Orchestration ==="
echo ""

if command -v qwen &>/dev/null; then
  QWEN_CLI_VERSION=$(qwen --version 2>/dev/null || echo "unknown")
  echo "[x] Qwen Code CLI harness: $QWEN_CLI_VERSION"
  if ! qwen --help 2>&1 | grep -q -- "--output-format"; then
    echo "[!] This Qwen Code version lacks headless stream-json support"
    echo "    Upgrade: npm install -g @qwen-code/qwen-code"
  fi
else
  echo "[ ] Qwen Code CLI: not installed (required as the local-model harness)"
  echo "    NOTE: /qwen:* talks straight to Ollama - no cloud API key is required"
  # Ask user if they want to install; if yes:
  npm install -g @qwen-code/qwen-code
fi

# Flag the retired Codex-harness env var if still set (issue #745)
if [ -n "$QWEN_CODEX_PROFILE" ]; then
  echo "[~] QWEN_CODEX_PROFILE is set but no longer used (Codex harness retired,"
  echo "    issue #745). Remote machines need only QWEN_OLLAMA_URL. Unset it."
fi
```

#### 6b. Verify the Ollama Server and Model

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section qwen || exit $?
QWEN_ENDPOINT="${QWEN_OLLAMA_URL:-http://127.0.0.1:11434}"
QWEN_MODEL="${QWEN_MODEL:-qwen3.8-code:latest}"

if curl -sf --max-time 5 "$QWEN_ENDPOINT/api/version" > /dev/null; then
  echo "[x] Ollama reachable at configured QWEN_OLLAMA_URL (value withheld)"
  # The model is judged only against an endpoint that answered (issue #1263).
  # /api/tags fails for the SAME single cause as /api/version, so a "missing"
  # read off an unreachable host is not an observation - and its rebuild
  # advice tells the user to recreate a model nothing showed to be absent.
  # A FAILED tags read is not an empty model list: a version probe that
  # answered does not prove /api/tags will (HTTP error, timeout, dropped
  # connection), and a 200 carrying no `models` key (an empty body, `{}`, an HTML
  # redirect page) is not a model list either - so only a body that IS one
  # reaches the membership test.
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
    echo "[?] Model '$QWEN_MODEL' unknown (the model list could not be read from configured QWEN_OLLAMA_URL (value withheld))"
  fi
else
  echo "[ ] Ollama NOT reachable at configured QWEN_OLLAMA_URL (value withheld)"
  echo "    Serving machine: install and start Ollama (brew install ollama on macOS),"
  echo "    bind to the network with OLLAMA_HOST=0.0.0.0:11434 for LAN/tailnet use."
  echo "    Consumer machine: set QWEN_OLLAMA_URL=http://<serving-ip>:11434"
  echo "[?] Model '$QWEN_MODEL' unknown (endpoint unreachable - not checked)"
fi
```

#### 6c. Remote Access (consumer machines only)

Consent: the endpoint option appends QWEN_OLLAMA_URL to the resolved shell RC path (`~/.bashrc` or `~/.zshrc`); show that path before asking. This persists the endpoint in plaintext; do not display any credential value embedded in it.

No harness config file is needed for a remote Ollama server. Only offer to
persist the endpoint when `QWEN_ENDPOINT` is not
`http://127.0.0.1:11434`, or when the user said this machine consumes a
remote server. If the user identified it as a consumer but the endpoint is
still the localhost default, ask for the actual serving endpoint first and
use that value. Do not offer this on the serving machine: the localhost
default already works there, and a hardcoded export is a liability. This
closes the fresh-shell persistence gap tracked in issue #755.

Choose the rc file from the user's shell: `~/.zshrc` when `$SHELL` ends in
`zsh`, otherwise `~/.bashrc`:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section qwen || exit $?
case "${SHELL##*/}" in
  zsh) QWEN_RC="$HOME/.zshrc"; QWEN_RC_DISPLAY="~/.zshrc" ;;
  *) QWEN_RC="$HOME/.bashrc"; QWEN_RC_DISPLAY="~/.bashrc" ;;
esac
```

Show the selected endpoint and actual rc path, but redact credential values
(including URL userinfo and query tokens). Fill `QWEN_ENDPOINT_REDACTED` for
display only; never render the unredacted endpoint in the confirmation. The
approved write below still uses the actual value internally:

```
=== Optional: Persist Qwen Endpoint ===

Remote Qwen commands need this setting in every fresh shell. I can add:
  # Claude Power Pack - Qwen serving endpoint (issue #755)
  export QWEN_OLLAMA_URL={QWEN_ENDPOINT_REDACTED}

Add to ${QWEN_RC_DISPLAY}? [y/N]
```

If yes:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section qwen || exit $?
# Through the declaring seam (#1132). This block used to write "$QWEN_RC"
# inline - the same ~/.bashrc that two other blocks already routed through the
# helper - so a defer-set naming ~/.bashrc refused those two, printed a stated
# refusal, and wrote this one anyway. rc-append carries the marker guard this
# block already had, and honours --defer for ~/.bashrc AND ~/.zshrc.
~/.claude/scripts/cpp-host-write.sh rc-append "$QWEN_RC" 'QWEN_OLLAMA_URL' - <<QWEN_RC_EOF

# Claude Power Pack - Qwen serving endpoint (issue #755)
export QWEN_OLLAMA_URL=$QWEN_ENDPOINT
QWEN_RC_EOF
case $? in
  0) echo "  Restart the shell or source $QWEN_RC_DISPLAY" ;;
  3) echo "  → DEFERRED by request - $QWEN_RC_DISPLAY was NOT modified; export QWEN_OLLAMA_URL yourself" ;;
  127) echo "  ✗ NOT written - the host-write seam is not installed; export QWEN_OLLAMA_URL yourself" ;;
  *) echo "  ✗ FAILED - check $QWEN_RC_DISPLAY - a failed write may have modified it; export QWEN_OLLAMA_URL yourself" ;;
esac
```

If no:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section qwen || exit $?
echo "-> QWEN_OLLAMA_URL persistence skipped"
echo "  Set QWEN_OLLAMA_URL in $QWEN_RC_DISPLAY to the selected endpoint; its value is withheld from output."
```

`/qwen:auto`, `/qwen:exec`, and `/qwen:status` derive the harness endpoint
from it (`$QWEN_OLLAMA_URL/v1` via `--openai-base-url`). If the user still
has a `QWEN_CODEX_PROFILE` export or a `[model_providers.qwen-local]` block
in `~/.codex/config.toml` from the retired Codex harness (issue #745), advise
removing them - a leftover `wire_api = "chat"` provider block hard-errors
every modern Codex invocation, including unrelated `/codex:*` commands.

#### 6d. Smoke Test (optional)

Consent: offer to skip before running the real Qwen harness. It contacts the selected Ollama endpoint and can write vendor runtime cache/logs in its configured user area; it can take minutes.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section qwen || exit $?
QWEN_ENDPOINT="${QWEN_OLLAMA_URL:-http://127.0.0.1:11434}"
timeout 600 qwen --openai-base-url "$QWEN_ENDPOINT/v1" --openai-api-key ollama \
  --auth-type openai -m "$QWEN_MODEL" \
  --approval-mode plan --output-format text \
  "Reply with exactly: QWEN-HARNESS-OK" < /dev/null 2>&1 | tail -3
```

A local 27B model takes minutes for a first turn (model load + prompt eval);
warn the user before running and offer to skip.

#### 6e. Always-On Second Opinion (optional)

The external mcp-second-opinion server (v2.3.0+) supports a keyless `ollama`
provider and an `ALWAYS_CONSULT_MODELS` list: models merged into EVERY
second-opinion consultation, so the local Qwen weighs in on every review at
zero cost. Offer to enable it:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section qwen || exit $?
# Check whether the running server already supports it
SO_HEALTH=$(curl -sf --max-time 5 "${SECOND_OPINION_URL:-http://127.0.0.1:8080}/" > /dev/null 2>&1 && echo up || echo down)
echo "second-opinion server: $SO_HEALTH"
```

- Server v2.3.0+ defaults are already always-on: `qwen-local` is in
  `DEFAULT_MODELS` and `ALWAYS_CONSULT_MODELS`, pointing at
  `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`) with model
  `OLLAMA_MODEL` (default `qwen3.8-code:latest`).
- If the second-opinion server runs on a DIFFERENT machine than the Qwen
  server, set `OLLAMA_BASE_URL=http://<qwen-serving-ip>:11434` in the
  server's environment (launchd plist or .env) and restart it.
- To disable the always-on behavior: `ALWAYS_CONSULT_MODELS=""` in the
  server's environment.
- Verify with the server's `health_check` tool: `always_consult_models`
  should list `qwen-local` and `ollama_configured` should be true.

### Gemma Execution (Local Gemma Orchestration)

Execution guard: `CPP_SECTION=gemma`.

Only run when the resolved plan includes `gemma`. It is independent of Qwen: different
model, harness, env var, and config block.

#### 7a. Verify the OpenCode Harness (no API key needed)

Consent: before offering an absent OpenCode CLI install, show the resolved npm global prefix and cache used by opencode-ai. No cloud API key is stored.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section gemma || exit $?
echo ""
echo "=== Tier 7: Local Gemma Orchestration ==="
echo ""

if command -v opencode &>/dev/null; then
  echo "[x] OpenCode harness: $(opencode --version 2>/dev/null)"
else
  echo "[ ] OpenCode CLI: not installed (required as the local-model harness)"
  echo "    NOTE: /gemma:* talks straight to Ollama - no cloud API key is required"
  npm install -g opencode-ai
fi
```

#### 7b. Verify the Ollama Server and Model

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section gemma || exit $?
GEMMA_ENDPOINT="${GEMMA_OLLAMA_URL:-http://127.0.0.1:11434}"
GEMMA_MODEL="${GEMMA_MODEL:-gemma4-code:latest}"

if curl -sf --max-time 5 "$GEMMA_ENDPOINT/api/version" > /dev/null; then
  echo "[x] Ollama reachable at configured GEMMA_OLLAMA_URL (value withheld)"
  # The model is judged only against an endpoint that answered (issue #1263).
  # /api/tags fails for the SAME single cause as /api/version, so a "missing"
  # read off an unreachable host is not an observation - and its rebuild
  # advice tells the user to recreate a model nothing showed to be absent.
  # A FAILED tags read is not an empty model list: a version probe that
  # answered does not prove /api/tags will (HTTP error, timeout, dropped
  # connection), and a 200 carrying no `models` key (an empty body, `{}`, an HTML
  # redirect page) is not a model list either - so only a body that IS one
  # reaches the membership test.
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
    echo "[?] Model '$GEMMA_MODEL' unknown (the model list could not be read from configured GEMMA_OLLAMA_URL (value withheld))"
  fi
else
  echo "[ ] Ollama NOT reachable at configured GEMMA_OLLAMA_URL (value withheld)"
  echo "    Serving machine: start it ('ollama serve') and retry."
  echo "    Consumer machine: set GEMMA_OLLAMA_URL=http://<serving-host>:11434"
  echo "    Shared-GPU host: another VM may currently hold the card."
  echo "[?] Model '$GEMMA_MODEL' unknown (endpoint unreachable - not checked)"
fi
```

The `num_ctx` bump is not optional tuning. Ollama's 32K default silently
truncates long agent transcripts mid-run - no error, the model just loses the
start of its own session.

#### 7b.1 Persist the Gemma Endpoint (consumer machines only)

Consent: the endpoint option appends GEMMA_OLLAMA_URL to the resolved shell RC path (`~/.bashrc` or `~/.zshrc`); show that path before asking. This persists the endpoint in plaintext; do not display any credential value embedded in it.

Only offer to persist the endpoint when `GEMMA_ENDPOINT` is not
`http://127.0.0.1:11434`, or when the user said this machine consumes a
remote server. If the user identified it as a consumer but the endpoint is
still the localhost default, ask for the actual serving endpoint first and
use that value. Do not offer this on the serving machine: the localhost
default already works there, and a hardcoded export is a liability.

This matters specifically for Gemma because the OpenCode provider's
`baseURL` is the literal `{env:GEMMA_OLLAMA_URL}`. OpenCode resolves it at
invocation time, so an unset variable does not preserve a discovered remote
endpoint - the lane silently addresses localhost (issue #755).

Choose the rc file from the user's shell: `~/.zshrc` when `$SHELL` ends in
`zsh`, otherwise `~/.bashrc`:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section gemma || exit $?
case "${SHELL##*/}" in
  zsh) GEMMA_RC="$HOME/.zshrc"; GEMMA_RC_DISPLAY="~/.zshrc" ;;
  *) GEMMA_RC="$HOME/.bashrc"; GEMMA_RC_DISPLAY="~/.bashrc" ;;
esac
```

Show the selected endpoint and actual rc path, but redact credential values
(including URL userinfo and query tokens). Fill `GEMMA_ENDPOINT_REDACTED` for
display only; never render the unredacted endpoint in the confirmation. The
approved write below still uses the actual value internally:

```
=== Optional: Persist Gemma Endpoint ===

Remote Gemma commands need this setting in every fresh shell. I can add:
  # Claude Power Pack - Gemma serving endpoint (issue #755)
  export GEMMA_OLLAMA_URL={GEMMA_ENDPOINT_REDACTED}

Add to ${GEMMA_RC_DISPLAY}? [y/N]
```

If yes:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section gemma || exit $?
# Through the declaring seam (#1132). This block used to write "$GEMMA_RC"
# inline - the same ~/.bashrc that two other blocks already routed through the
# helper - so a defer-set naming ~/.bashrc refused those two, printed a stated
# refusal, and wrote this one anyway. rc-append carries the marker guard this
# block already had, and honours --defer for ~/.bashrc AND ~/.zshrc.
~/.claude/scripts/cpp-host-write.sh rc-append "$GEMMA_RC" 'GEMMA_OLLAMA_URL' - <<GEMMA_RC_EOF

# Claude Power Pack - Gemma serving endpoint (issue #755)
export GEMMA_OLLAMA_URL=$GEMMA_ENDPOINT
GEMMA_RC_EOF
case $? in
  0) echo "  Restart the shell or source $GEMMA_RC_DISPLAY" ;;
  3) echo "  → DEFERRED by request - $GEMMA_RC_DISPLAY was NOT modified; export GEMMA_OLLAMA_URL yourself" ;;
  127) echo "  ✗ NOT written - the host-write seam is not installed; export GEMMA_OLLAMA_URL yourself" ;;
  *) echo "  ✗ FAILED - check $GEMMA_RC_DISPLAY - a failed write may have modified it; export GEMMA_OLLAMA_URL yourself" ;;
esac
```

If no:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section gemma || exit $?
echo "-> GEMMA_OLLAMA_URL persistence skipped"
echo "  Set GEMMA_OLLAMA_URL in $GEMMA_RC_DISPLAY to the selected endpoint; its value is withheld from output."
```

#### 7c. Install the Provider and the Mechanical Fence

Consent: the selected Tier 7 approval covers a merge into user `~/.config/opencode/opencode.json` (provider and agent entries), preserving unrelated entries. Required parents and replacement temporary files are included. Show this destination again before offering this step.

CPP ships both blocks as `templates/opencode-gemma.json`. Merge them into the
user's OpenCode config; never overwrite an existing file, which may hold their
own providers and agents.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section gemma || exit $?
OC_CONFIG="$HOME/.config/opencode/opencode.json"

# Through the declaring seam (#1132). This merge was embedded PYTHON, which is
# why no shell pattern found it: a cfg_path.write_text() satisfies no grep for a
# redirect, cp, tee, mv or ln. Same .update() semantics, moved not improved.
~/.claude/scripts/cpp-host-write.sh json-merge-sections \
  "$CPP_DIR/templates/opencode-gemma.json" "$OC_CONFIG" provider agent
case $? in
  0) echo "✓ gemma-ollama provider and gemma-implementer fence merged into $OC_CONFIG" ;;
  3) echo "→ DEFERRED by request - $OC_CONFIG was NOT modified; this run did not install or refresh the mechanical fence, and whether one is already present is unverified" ;;
  127) echo "✗ NOT merged - the host-write seam is not installed; this run did not install or refresh the mechanical fence, and whether one is already present is unverified" ;;
  *) echo "✗ Merge FAILED - check $OC_CONFIG - a failed write may have modified it; this run did not install or refresh the mechanical fence, and its current state is unverified" ;;
esac
```

Two things are being installed here, and the second is the safety-critical one:

- **`gemma-ollama` provider** - pinned to the `ai-sdk-ollama` npm package,
  which speaks Ollama's NATIVE `/api/chat`. Do not switch it to
  `@ai-sdk/openai-compatible`, even though that is what OpenCode's own docs
  suggest for Ollama: the `/v1` shim silently discards tool calls once the
  system prompt passes ~1,600 tokens (ollama/ollama#14958), and OpenCode's
  agentic prompt measures ~6,900. The lane would fail as prose, not as an
  error. `baseURL` is left as the literal `{env:GEMMA_OLLAMA_URL}` so one
  config works on the serving machine and every consumer machine.
- **`gemma-implementer` agent** - the MECHANICAL FENCE. OpenCode has no
  `--sandbox` flag, so these permission rules are what stop a wandering local
  model from running the lifecycle itself: ref-modifying git, all `gh`,
  deploy/docker/kubectl/terraform, webfetch/websearch, and writes outside the
  run directory are denied. `/gemma:auto` and `/gemma:exec` both refuse to run
  without it.

#### 7d. Smoke Test (recommended)

Consent: ask before running the real OpenCode harness. It creates a temporary directory with `probe.txt`, deletes that directory afterward, contacts the selected Ollama endpoint, and may write vendor runtime cache/logs. Offer to skip.

This exercises tool calling through a real `opencode run`, including its system
prompt. A bare curl probe checks endpoint reachability but does not exercise
this harness or establish that tool calling works.

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section gemma || exit $?
SMOKE_DIR=$(mktemp -d)
echo "probe" > "$SMOKE_DIR/probe.txt"
GEMMA_OLLAMA_URL="$GEMMA_ENDPOINT" timeout 120 opencode run \
  --dir "$SMOKE_DIR" \
  -m "gemma-ollama/${GEMMA_MODEL%%:*}" \
  --agent gemma-implementer --format json --auto \
  "List the files in the current directory using your tools." 2>&1 | grep -c '"type":"tool_use"'
rm -rf "$SMOKE_DIR"
```

A count of 1 or more means this run emitted matching tool-use events. Zero is inconclusive:
it can reflect CLI, network, provider, model or output-format failures, including
an incorrect `/v1` provider block. Inspect the command output and exit status,
re-check 7c, and run `/gemma:status` for further diagnosis.

---


---

## Error Handling

### Second Opinion Server Not Reachable
```
⚠ The second-opinion server did not answer on http://127.0.0.1:8080/mcp.

It is an EXTERNAL server - start it from its own repo first:
  https://github.com/cooneycw/mcp-second-opinion

If your server runs on a different host (e.g. a Tailscale address), export
SECOND_OPINION_URL with its base URL (no /mcp), then re-register at user scope
from that value:
  claude mcp remove second-opinion -s user
  # Initialize a new run above; bind its printed CPP_MCP_RUN_DIR in this call.
  source "$CPP_MCP_RUN_DIR/routines.sh" || exit 1
  if cpp_register_claude_mcp second-opinion; then :; else echo "WARNING: registration incomplete"; fi
```

### npx Not Available (playwright)
```
⚠ npx not found. Browser automation (upstream @playwright/mcp) needs Node.js 18+.

Install Node.js (https://nodejs.org/), then:
  # Initialize a new run above; bind its printed CPP_MCP_RUN_DIR in this call.
  source "$CPP_MCP_RUN_DIR/routines.sh" || exit 1
  if cpp_register_claude_mcp playwright; then :; else echo "WARNING: registration incomplete"; fi
```

---

## Step 6: Optional Extras

Execution guard: `CPP_SECTION=extras`. Skip this whole step unless `extras` is selected.

After the selected tier steps have run, offer optional extras before the final summary.

### 8a. Sequential Thinking

Consent: add a stdio server to the user MCP config (`${CLAUDE_CONFIG_DIR:-$HOME}/.claude.json`), creating its parent/file if absent. npx uses its configured cache; no API key is needed.

```
=== Optional: Sequential Thinking MCP ===

Adds a `sequentialthinking` tool for structured, step-by-step reasoning
with revision and branching. Useful for complex debugging and architecture decisions.

Requires: Node.js 18+ (for npx)
No API keys needed. Runs as stdio subprocess (no port).

Install Sequential Thinking? [y/N]
```

If yes:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section extras || exit $?
# Rebind CPP_MCP_RUN_DIR to this run's printed absolute path in this tool call.
if [ -z "${CPP_MCP_RUN_DIR-}" ] || ! source "$CPP_MCP_RUN_DIR/routines.sh"; then
  echo "CPP Installation Incomplete"
  echo "WARNING: MCP run state could not be loaded"
  exit 1
fi
if cpp_register_claude_mcp sequential-thinking; then :; else echo "WARNING: Sequential Thinking setup incomplete"; fi
```

If no:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section extras || exit $?
# Rebind CPP_MCP_RUN_DIR to this run's printed absolute path in this tool call.
if [ -z "${CPP_MCP_RUN_DIR-}" ] || ! source "$CPP_MCP_RUN_DIR/routines.sh"; then
  echo "CPP Installation Incomplete"
  echo "WARNING: MCP run state could not be loaded"
  exit 1
fi
echo "→ Sequential Thinking skipped"
cpp_mcp_record sequential-thinking declined || exit 1
echo "  Install later: rerun /cpp:init optional Sequential Thinking"
```

### 8b. Codex MCP Registration (optional)

Skip this step, and say so, when 5d already registered these servers in this run
(`CPP_MCP_RESULTS` holds their outcome). After a 5d No it still runs: only its No
branch records the decline.

Consent: Yes updates `${CODEX_HOME:-$HOME/.codex}/config.toml` with the listed servers and npx can use its cache. No always creates project `.agents/`, even when the setup source is absent; generate project `.agents/CODEX_SETUP.md` by copying the supplied setup artifact only if the source exists; that copy can overwrite an existing setup file. Disclose both branches before asking.

```
=== Optional: Codex MCP Registration ===

Register Claude Power Pack MCP servers with Codex?
This calls the shared Codex registration routine and updates Codex configuration.

MCP servers expose streamable HTTP at /mcp. Claude Code and Codex both use
the /mcp streamable-http endpoint.

Register with Codex? [y/N]
```

If yes:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section extras || exit $?
# Rebind CPP_MCP_RUN_DIR to this run's printed absolute path in this tool call.
if [ -z "${CPP_MCP_RUN_DIR-}" ] || ! source "$CPP_MCP_RUN_DIR/routines.sh"; then
  echo "CPP Installation Incomplete"
  echo "WARNING: MCP run state could not be loaded"
  exit 1
fi
# Only run this block after Yes to this section's registration choice.
if command -v codex &>/dev/null; then
  if cpp_register_codex_mcp second-opinion; then :; else echo "WARNING: Codex second-opinion setup incomplete"; fi
  if cpp_register_codex_mcp playwright; then :; else echo "WARNING: Codex playwright setup incomplete"; fi
  echo "Restart Codex for tools to become available."
else
  cpp_mcp_record codex-second-opinion skipped || exit 1
  cpp_mcp_record codex-playwright skipped || exit 1
  echo "WARNING: Codex CLI not found; registration skipped"
fi
```

If no:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section extras || exit $?
# Rebind CPP_MCP_RUN_DIR to this run's printed absolute path in this tool call.
if [ -z "${CPP_MCP_RUN_DIR-}" ] || ! source "$CPP_MCP_RUN_DIR/routines.sh"; then
  echo "CPP Installation Incomplete"
  echo "WARNING: MCP run state could not be loaded"
  exit 1
fi
echo "-> Codex registration skipped"
for id in codex-second-opinion codex-playwright; do
  if [ -z "${CPP_MCP_RESULTS[$id]-}" ]; then cpp_mcp_record "$id" declined || exit 1; fi
done
# Write setup artifact for manual registration later
mkdir -p .agents
if [ -f "$CPP_DIR/.agents/CODEX_SETUP.md" ]; then
  if cp "$CPP_DIR/.agents/CODEX_SETUP.md" .agents/CODEX_SETUP.md; then
    echo "  Setup commands saved to .agents/CODEX_SETUP.md"
  else
    echo "WARNING: setup command failed (exit $?)."
  fi
else
  echo "  Register later with: /cpp:init optional Codex MCP registration"
fi
```

### 8c. Workstation Tuning (bash-prep)

Consent: sudo may create/recreate `/swapfile`, append its entry to `/etc/fstab`, and write `/etc/sysctl.d/99-claude-code.conf`. It also changes active swap/kernel settings now. Show the calculated swap size and these destinations before asking.

```
=== Optional: Workstation Tuning ===

Linux workstation tuning for optimal Claude Code performance:
  • Swap (min(RAM, 4GB)) - prevent OOM kills during heavy sessions
  • vm.swappiness=10 - keep active data in RAM
  • vm.vfs_cache_pressure=50 - cache filesystem metadata
  • fs.inotify.max_user_watches=524288 - prevent watcher failures
  • fs.inotify.max_user_instances=512 - headroom for multiple watchers

Requires sudo. Safe to run multiple times (idempotent).
Persists across reboots via /etc/sysctl.d/ and /etc/fstab.

Apply workstation tuning? [y/N]
```

If yes:

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section extras || exit $?
# Run bash-prep script
if [ -f "$CPP_DIR/scripts/bash-prep.sh" ]; then
  bash "$CPP_DIR/scripts/bash-prep.sh" --apply
else
  echo "⚠ bash-prep.sh not found at $CPP_DIR/scripts/bash-prep.sh"
fi
```

If no:
```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section extras || exit $?
echo "→ Workstation tuning skipped"
echo "  Run later: bash ~/.claude/scripts/bash-prep.sh"
echo "  Or check current values: bash ~/.claude/scripts/bash-prep.sh --check"
```

### 8d. Common-Memory Store Backend (mini-tier)

Consent: any backend selection replaces the nonsecret choice in `~/.config/claude-power-pack/secrets/cpp-memories.backend` and creates required parents. md writes project `.claude/learnings.md` and `.claude/learnings.rejected.jsonl` only when later memory features are used. local-pg can optionally pull postgres:17 and start Docker container `cpp-memory-db`, with persistent volume `cpp_memory_data` on loopback port 5433; schema initialization runs on an empty volume. The shipped development POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB settings are plaintext in the compose configuration, not production secrets; name them without printing values. remote-pg reads CPP_MEMORIES_DSN, the local `~/.config/claude-power-pack/secrets/cpp-memories.dsn` file or AWS Secrets Manager; the local DSN file, if supplied, is plaintext credential storage. Init writes no DSN or remote schema: its ping is SELECT 1 only. Show this inventory before the backend choice.

Only offer this when the common-memory feature is in use. Tier 2 links the
checkout's executable helpers; Tier 5f installs the PATH harness for `cpp-memory`.
This option selects the storage backend for the friction-knowledge
ledger (`lib/cpp_memory`, issue #472). **Federation is the key column** - only
tier iii shares learnings/rejections across VMs; on i and ii the `is_known` /
`rejected_here` check is this-box-only.

```
=== Optional: Common-Memory Store Backend ===

The friction-knowledge ledger can run on one of three backends. Federation
(does a learning recorded here reach OTHER machines?) differs per tier - pick
with that in mind:

  Tier  Backend     Dedup fidelity              Federation (cross-VM sharing?)
  ----  ----------  --------------------------  ------------------------------
  i     md          best-effort (grep/parse)    NO  - local box only
  ii    local-pg    full (SQL fingerprint)      NO  - single box (docker pg)
  iii   remote-pg   full (SQL fingerprint)      YES - shared across the fleet

  i    = zero dependencies; promotes .claude/learnings.md to a real store.
  ii   = full-fidelity dedup on this box; needs Docker (stock postgres:17).
  iii  = the fleet store over Tailscale; DSN from CPP_MEMORIES_DSN / the local
         dsn file / AWS SM (essent-ai). This is today's default on fleet VMs.

Select backend [i/ii/iii, Enter to skip]:
```

Persist the choice to the backend file the client reads
(`resolve_backend()` in `lib/cpp_memory/config.py`):

```bash
python3 "$CPP_DIR/scripts/cpp-install-receipt.py" section \
  --capabilities "${CPP_CAPABILITIES_JSON-}" --section extras || exit $?
BACKEND_FILE="$HOME/.config/claude-power-pack/secrets/cpp-memories.backend"

case "$MEM_BACKEND_CHOICE" in
  i|md)
    ~/.claude/scripts/cpp-host-write.sh file-write "$BACKEND_FILE" "md"
    #: The backend record decides which store later sessions read (issue #1198).
    #: An unwritten record does not fail loudly - it leaves the PREVIOUS backend
    #: selected, or none, while this line said the choice was applied.
    case $? in
      0) echo "✓ common-memory backend: md (tier i) - local-only, no federation" ;;
      3) echo "→ common-memory backend selection DEFERRED by request - $BACKEND_FILE was NOT written; whichever backend was already recorded, if any, is unchanged by this run" ;;
      127) echo "✗ common-memory backend NOT recorded - the host-write seam is not installed" ;;
      *) echo "✗ common-memory backend selection FAILED - check $BACKEND_FILE - a failed write may have modified it" ;;
    esac
    echo "  Ledger: <repo>/.claude/learnings.md  (+ .claude/learnings.rejected.jsonl)"
    ;;
  ii|local-pg)
    ~/.claude/scripts/cpp-host-write.sh file-write "$BACKEND_FILE" "local-pg"
    #: The backend record decides which store later sessions read (issue #1198).
    #: An unwritten record does not fail loudly - it leaves the PREVIOUS backend
    #: selected, or none, while this line said the choice was applied.
    case $? in
      0) echo "✓ common-memory backend: local-pg (tier ii) - full dedup, no federation" ;;
      3) echo "→ common-memory backend selection DEFERRED by request - $BACKEND_FILE was NOT written; whichever backend was already recorded, if any, is unchanged by this run" ;;
      127) echo "✗ common-memory backend NOT recorded - the host-write seam is not installed" ;;
      *) echo "✗ common-memory backend selection FAILED - check $BACKEND_FILE - a failed write may have modified it" ;;
    esac
    if command -v docker >/dev/null 2>&1; then
      echo "Consent: pull postgres:17; start cpp-memory-db with volume cpp_memory_data, plaintext shipped development POSTGRES_PASSWORD settings, and first-boot schema initialization. No credential values will be printed."
      read -r -p "Start the local postgres:17 store now (docker compose up -d)? [y/N] " START_PG
      if [[ "$START_PG" =~ ^[Yy]$ ]]; then
        docker compose -f "$CPP_DIR/lib/cpp_memory/docker-compose.yml" up -d
        echo "  Store on 127.0.0.1:5433 (schema auto-applied on first boot)."
      else
        echo "  Start later: docker compose -f \"$CPP_DIR/lib/cpp_memory/docker-compose.yml\" up -d"
      fi
    else
      echo "⚠ Docker not found - install it, then: docker compose -f \"$CPP_DIR/lib/cpp_memory/docker-compose.yml\" up -d"
    fi
    echo "  Local credentials: POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_DB in the shipped compose configuration (plaintext development settings); values withheld."
    ;;
  iii|remote-pg)
    ~/.claude/scripts/cpp-host-write.sh file-write "$BACKEND_FILE" "remote-pg"
    #: The backend record decides which store later sessions read (issue #1198).
    #: An unwritten record does not fail loudly - it leaves the PREVIOUS backend
    #: selected, or none, while this line said the choice was applied.
    case $? in
      0) echo "✓ common-memory backend: remote-pg (tier iii) - full dedup, FLEET federation" ;;
      3) echo "→ common-memory backend selection DEFERRED by request - $BACKEND_FILE was NOT written; whichever backend was already recorded, if any, is unchanged by this run" ;;
      127) echo "✗ common-memory backend NOT recorded - the host-write seam is not installed" ;;
      *) echo "✗ common-memory backend selection FAILED - check $BACKEND_FILE - a failed write may have modified it" ;;
    esac
    echo "  DSN resolves fail-open: CPP_MEMORIES_DSN -> ~/.config/claude-power-pack/secrets/cpp-memories.dsn -> AWS SM (essent-ai)."
    echo "  Provision a new remote store with scripts/memories-db-setup.sh (idempotent)."
    if bash "$CPP_DIR/scripts/cpp-memory" ping 2>/dev/null | grep -q '"reachable": true'; then
      echo "  Reachability: OK (store answered ping)."
    else
      echo "  Reachability: not reachable yet - set the DSN, then: cpp-memory ping"
    fi
    ;;
  ""|skip|n|N)
    echo "→ Backend selection skipped - the client infers one (DSN present -> remote-pg, else md)."
    ;;
  *)
    echo "⚠ Unrecognized choice '$MEM_BACKEND_CHOICE' - skipped. Re-run /cpp:init to choose."
    ;;
esac
```

Verify with `cpp-memory ping` (its JSON now reports `backend` and `federation`).

---

## Step 7: Installation Summary

Render this summary only after all selected tier steps and optional extras have
run or been explicitly skipped. Build `{STEP_RESULTS}` from their observed exit
statuses: report each selected step as succeeded, failed, deferred, skipped or
unverified. A failed read is unverified, never absent or already installed.
Registration success proves configuration was written, not server connectivity.
The shared MCP routines automatically merge their latest fixed-ID observations
into `STEP_RESULTS_JSON` before persistence; do not replace a FAILED outcome
with a tier-based success. Record offered MCP IDs before the relevant choice,
including browser-pool, sequential-thinking, codex-second-opinion and
codex-playwright. A declined Codex choice after an earlier successful Tier 5
registration retains the observed registration rather than undoing it.
Never infer success from selecting a tier or finding an old generated file.

The permission lines below describe the project file only. This observer does not re-check other installation steps or effective native permissions. Read the
actual file even when the selected profile was skipped because a file existed;
never infer its name or rules from the selection. It emits only preset identity
and rule counts, never environment, credential or rule values. An unknown/custom
preset identity or failed read is labelled unverified. A null means unverified; numeric zero remains zero.

```bash
if PERMISSION_REPORT=$(python3 - "$CPP_DIR/.claude/commands/cpp/init.md" .claude/settings.local.json <<'PY_PERMISSIONS'
# CPP_INIT_PERMISSION_OBSERVER_BEGIN
import json
import re
import sys
from pathlib import Path

FIELDS = ("allow", "ask", "deny")

def unknown(reason, counts=None):
    return {
        "profile": "unknown", "verified": False,
        "counts": counts if counts is not None else dict.fromkeys(FIELDS),
        "scope": "project-file declarations only", "reason": reason,
    }

def normalized(permissions):
    if not isinstance(permissions, dict):
        raise ValueError("permissions shape")
    result = dict(permissions)
    for field in FIELDS:
        rules = permissions.get(field, [])
        if not isinstance(rules, list) or not all(isinstance(rule, str) for rule in rules):
            raise ValueError("rule list shape")
        result[field] = sorted(rules)
    return result

def observe(presets, settings):
    try:
        data = json.loads(settings.read_text())
    except FileNotFoundError:
        return unknown("project settings absent")
    except OSError:
        return unknown("project settings unreadable")
    except ValueError:
        return unknown("project settings invalid JSON")
    try:
        if not isinstance(data, dict):
            raise ValueError("settings shape")
        actual = normalized(data.get("permissions", {}))
    except ValueError:
        return unknown("project permission rule lists invalid")
    counts = {field: len(actual[field]) for field in FIELDS}
    try:
        source = presets.read_text()
        found = []
        for name in ("Cautious", "Standard", "Trusted", "YOLO"):
            pattern = rf"\*\*{name} Profile(?: \(Default\))?:\*\*\s*```json\n(.*?)```"
            matches = re.findall(pattern, source, re.S)
            if len(matches) != 1:
                return unknown("CPP preset definitions incomplete", counts)
            preset = normalized(json.loads(matches[0])["permissions"])
            if actual == preset:
                found.append(name)
    except (OSError, ValueError, TypeError, KeyError):
        return unknown("CPP preset definitions unavailable", counts)
    if len(found) != 1:
        report = unknown("not a unique named CPP preset", counts)
        report["profile"] = "Custom/existing"
        return report
    return {
        "profile": found[0], "verified": True, "counts": counts,
        "scope": "project-file declarations only", "reason": "",
    }

report = observe(Path(sys.argv[1]), Path(sys.argv[2]))
report["verification"] = "verified" if report["verified"] else "unverified"
print(json.dumps(report, sort_keys=True))
raise SystemExit(0 if report["verified"] else 3)
# CPP_INIT_PERMISSION_OBSERVER_END
PY_PERMISSIONS
); then
  PERMISSION_REPORT_RC=0
else
  PERMISSION_REPORT_RC=$?
fi
if { [ "$PERMISSION_REPORT_RC" -ne 0 ] && [ "$PERMISSION_REPORT_RC" -ne 3 ]; } || [ -z "$PERMISSION_REPORT" ]; then
    PERMISSION_REPORT='{"profile":"unknown","verification":"unverified","verified":false,"counts":{"allow":null,"ask":null,"deny":null},"scope":"project-file declarations only","reason":"permission observer unavailable"}'
fi
printf '%s\n' "$PERMISSION_REPORT"
```

Persist the observed outcomes and permission metadata now. `.claude/cpp-install.json`
is a PROJECT write; it is outside the HOME-only host-write seam. It contains
schema version 2, the local CPP HEAD revision, requested/resolved capabilities,
optional preset and selected profile, per-step
outcomes and recording timestamps, and fixed user-scope references. It replaces
the prior receipt atomically; it contains no command output or configuration
values. The receipt is historical evidence, not a live connectivity probe.

```bash
# CPP_INSTALL_RECEIPT_WRITE_BEGIN
# Rebind CPP_MCP_RUN_DIR to this run's printed absolute path in this tool call.
if [ -z "${CPP_MCP_RUN_DIR-}" ] || ! source "$CPP_MCP_RUN_DIR/routines.sh"; then
  echo "CPP Installation Incomplete"
  echo "WARNING: MCP run state could not be loaded"
  exit 1
fi
# CPP_MCP_RECEIPT_MERGE_BEGIN
if STEP_RESULTS_JSON=$(printf '%s\n' "$STEP_RESULTS_JSON" | python3 -c '
import json, sys
rows = json.load(sys.stdin)
if not isinstance(rows, list):
    raise ValueError("step observations must be an array")
observed = [json.loads(value) for value in sys.argv[1:]]
ids = {row["step"] for row in observed}
print(json.dumps([row for row in rows if row.get("step") not in ids] + observed))
' "${CPP_MCP_RESULTS[@]}"); then
  :
else
  echo "CPP Installation Incomplete"
  echo "WARNING: registration observations could not be merged; receipt not written"
  exit 1
fi
# CPP_MCP_RECEIPT_MERGE_END
# For an unchanged confirmed preset, replace --capabilities with --preset N
# in this invocation to retain preset provenance. Otherwise retain the actual
# requested capability array; never invent a preset for a custom selection.
if printf '%s\n' "$STEP_RESULTS_JSON" | python3 "$CPP_DIR/scripts/cpp-install-receipt.py" write \
    --project-dir "$PWD" --cpp-dir "$CPP_DIR" \
    --capabilities "$CPP_CAPABILITIES_JSON" --profile "$PROFILE_NAME" \
    --offered-steps "$OFFERED_STEPS_JSON" \
    --permission-report "$PERMISSION_REPORT"; then
  if python3 "$CPP_MCP_STATE_HELPER" cleanup --run-dir "$CPP_MCP_RUN_DIR"; then
    echo "MCP setup temporary run removed after receipt persistence."
  else
    echo "WARNING: receipt saved, but temporary MCP run cleanup failed; inspect the retained run."
  fi
  if CPP_INSTALL_SUMMARY=$(python3 "$CPP_DIR/scripts/cpp-install-receipt.py" summary --project-dir "$PWD" --cpp-dir "$CPP_DIR"); then
    printf '%s\n' "$CPP_INSTALL_SUMMARY"
  else
    printf '%s\n' "$CPP_INSTALL_SUMMARY"
    if ! printf '%s\n' "$CPP_INSTALL_SUMMARY" | grep -qxF 'CPP Installation Incomplete'; then
      echo "CPP Installation Incomplete"
    fi
  fi
else
  echo "CPP Installation Incomplete"
  echo "Receipt write FAILED: retain the observed step outcomes and retry; do not render an older receipt as this run's summary."
fi
# CPP_INSTALL_RECEIPT_WRITE_END
```

Writing the receipt is not an installation step and cannot turn any outcome
into installed. The `write` exit says only whether persistence succeeded;
`summary` reads back the saved receipt and returns nonzero for incomplete or
stale recorded state. A write failure itself is reported, with no success
summary and no fallback to an old receipt. Preserve the observed results in
the conversation for recovery.

A failed summary read or revision lookup also ends with an explicit incomplete
verdict, retaining the helper's diagnostic. It never omits the final verdict or
substitutes a success derived from the selected tier.

The helper's output is the authoritative final summary. The template below
shows its fields: `{STEP_RESULTS}` and `{MCP_RESULTS}` come from receipt steps
and user-scope references, and `PERMISSION_REPORT` comes from the receipt's
sanitized permission observation, retaining verified/unverified and counts.
Never rebuild these fields from the selected tier/profile or current shell
variables after persistence.

Use `CPP Installation Complete` for `{INSTALLATION_VERDICT}` only when every
selected step succeeded or its existing state was verified and every optional
extra has run or been explicitly declined. Otherwise use `CPP Installation
Incomplete` and list the failures, deferrals and unverified steps with next
actions. Do not print a blanket installed checklist.

```
=================================
{INSTALLATION_VERDICT}
=================================

Step results:
{STEP_RESULTS}

Permission Profile: {PERMISSION_REPORT.profile} ({PERMISSION_REPORT.verification})
  Declared allow rules: {PERMISSION_REPORT.counts.allow}
  Declared ask rules: {PERMISSION_REPORT.counts.ask}
  Declared deny rules: {PERMISSION_REPORT.counts.deny}
  Settings examined: .claude/settings.local.json (project-file declarations only)

MCP registrations (configuration only; connectivity reported separately):
{MCP_RESULTS}

Update pathway:
  /cpp:update pulls CPP and tears down any legacy systemd units or retired MCP
  containers (mcp-second-opinion, aws-secrets-agent, ...) left on this host.

Next Steps:
  1. Verify the second-opinion server is running (from the mcp-second-opinion
     repo) and reachable at http://127.0.0.1:8080/mcp

  2. Restart your shell to apply prompt changes:
     source ~/.bashrc

  3. Verify installation:
     /cpp:status

  4. Try the commands:
     /project:next    - See what to work on
     /spec:help       - Spec-driven development
     /github:help     - Issue management
     /cicd:help       - CI/CD build & verification
     npx skills find  - Discover community skills from skills.sh

Change Permissions Later:
  • Edit .claude/settings.local.json directly
  • Or delete it and run /cpp:init to reconfigure

Documentation:
  • CLAUDE.md - Full reference
  • ISSUE_DRIVEN_DEVELOPMENT.md - IDD workflow
  • /cpp:load-best-practices - Community tips

=================================
```

---

## Notes

- Steps with presence guards skip the artifacts they recognize; those guards do not prove readiness
- Re-running can repeat optional writes and registrations; review each disclosure and observed result
- Symlinks are preferred over copies for easier updates
- Run `/cpp:status` anytime to check installation state
