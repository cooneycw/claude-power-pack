# ADR 0003: Configurable worktree base location (CPP + CxPP)

- Status: Proposed (awaiting owner decisions 1-3 below)
- Date: 2026-07-18
- Deciders: cooneycw (owner)
- Issue: #572 (exploration/design; Phase 0 per the security-first-before-scaffolding norm)
- Supersedes: nothing
- Related: #440 (flow rebased onto native worktrees), #486 (worktree path-resolution rule + leak guard), #578 (cross-repo git lane - the mechanics Option A reuses), PR #527 (the no-personal-prefs-in-shipped-config norm), cooneycw/codex-power-pack#64 / #75 (hybrid SoT; CxPP vendors CPP's command source)

## TL;DR

Make the worktree base location configurable via a single env var,
`FLOW_WORKTREE_BASE`, read identically by CPP and codex-power-pack (CxPP), with
the shipped default byte-identical to today's in-repo paths
(`.claude/worktrees/` / `.codex/worktrees/`). When the override is set, CPP
commits the run to the deterministic git-worktree lane that #578 already built
for cross-repo runs - no new mechanics. A lighter Option D (a symlink farm that
moves nothing) is presented as the better answer if the owner's real need is
"see the active worktrees," not "work from `~/Projects`." No code changes in
this ADR; Phase 1 implementation issues get cut per the owner's answers to the
three decisions at the bottom.

## Context

Active worktrees live inside each repo at `.claude/worktrees/<name>` (CPP) and
`.codex/worktrees/<name>` (CxPP). They are gitignored and invisible from the
`~/Projects` directory the owner actually looks at, so in-flight work is easy
to lose track of across sessions and machines. Issue #572 asks for a design
pass on making the base location configurable - visible under `~/Projects` on
the owner's box - defined the same way in both packs, WITHOUT baking one
operator's box layout into shipped config (the PR #527 misstep).

Constraints carried in from the issue:

1. **No personal prefs in shipped config.** The shipped default must remain
   today's in-repo path; `~/Projects` is an owner-box override only.
2. **A native hook is not the mechanism.** Codex has no `WorktreeCreate` hook
   at all, and in CPP a hook would only intercept the `EnterWorktree` fresh
   lane, not the `git worktree add` lanes. The only lever that works uniformly
   in both packs is the path string the flow commands pass to
   `git worktree add` / `EnterWorktree`.

## Grounded current behavior (verified 2026-07-18, per-file sweep)

### Functional path producers (behavior changes if the base moves)

CPP - the only places that CONSTRUCT a worktree path:

- `.claude/commands/flow/auto.md` - 3 sites: the cross-machine pickup lane
  (`git worktree add ".claude/worktrees/${LOCAL_BRANCH}"`), the cross-repo
  fresh lane (`$TARGET_REPO/.claude/worktrees/${BRANCH}`, added by #578 AFTER
  #572 was filed - the inventory in the issue body is one site short), and the
  native fresh lane (`EnterWorktree(name=...)`, base fixed by the harness).
- `.claude/commands/flow/start.md` - 2 sites: same pickup + fresh lanes.
- `.claude/commands/flow/sync.md` - receiving-end prose describing the pickup
  path (documentation of the same lane, not an independent site).

CxPP - always plain `git worktree add`, so every site is a string substitution:

- `.codex/skills/flow-start/reference.md` (9 hits, path construction at the
  pickup and fresh lanes)
- `.codex/skills/flow-auto/reference.md` (10 hits, same)

### Already layout-aware - NO functional change needed if the base moves

The issue body estimated "~5-8 files per pack, coordinated" of guard/merge/
remove machinery. The sweep shows that machinery is already layout-agnostic;
every `.claude/worktrees` occurrence in these scripts is a comment or an error
message, never a path comparison:

- `scripts/gh-pr-merge.sh` - detects a linked worktree via the `.git` FILE
  (`[ -f .git ]`), not the path string.
- `scripts/worktree-remove.sh` - resolves via `git worktree list` plus an
  ancestor walk; explicitly documents handling worktrees at arbitrary paths.
- `scripts/friction-log.sh` - resolves the durable buffer via
  `git rev-parse --git-common-dir` (#471), which follows the worktree's gitdir
  pointer wherever the worktree lives.
- `scripts/flow-worktree-guard.sh` - finds the main repo from
  `--git-common-dir` and compares dirty-file sets; no literal path logic.

These four are vendored byte-identical into CxPP's skill dirs by
`codex-skill-sync.py`, so their layout-agnosticism carries over automatically.

### In-repo-only hygiene (becomes a harmless no-op if the base moves out)

- `.gitignore` - the `.claude/worktrees/` entry. Must STAY for the shipped
  default; with an out-of-repo base there is simply nothing under the repo to
  ignore.
- `scripts/drift-detect.sh` - 2 `find -prune` sites excluding sibling
  checkouts under `.claude/worktrees`. Same: required for the default,
  naturally inert for an out-of-repo base.

### Docs / policy surfaces (prose updates only)

- `CLAUDE.md` - the native-worktrees section and the #486 path-resolution
  rule (which is already stated in base-relative terms: "resolve from
  `git rev-parse --show-toplevel`", so the rule itself survives a moved base
  unchanged).
- `.claude/commands/flow/status.md`, `cleanup.md`, `merge.md` - example
  output and prose mentioning the default path.
- Generated surfaces (`plugins/flow/`, `codex/skills/flow-*`) regenerate from
  the command source via `plugin-sync.sh --write` / `codex-skill-sync.py
  --write`; they are never edited directly.

## Native-harness constraints (new facts this pass established)

1. **The `EnterWorktree` base directory is NOT configurable.** The only
   worktree setting Claude Code exposes is `worktree.baseRef` (which ref new
   worktrees branch from). There is no settings key, env var, or flag for the
   worktree PATH, and no documented plan for one
   (https://code.claude.com/docs/en/worktrees.md). An out-of-repo base
   therefore cannot ride `EnterWorktree(name=...)` at all.
2. **`EnterWorktree(path=...)` to a path outside the repo triggers an
   approval prompt that permission rules cannot suppress** (v2.1.206+; only
   `bypassPermissions` skips it), because the move transfers the session cwd,
   write access, and project config to that location
   (https://code.claude.com/docs/en/tools-reference.md). Wiring the override
   through `EnterWorktree(path=...)` would cost one unsuppressable prompt per
   fresh run - or train the owner to click through a prompt that exists as a
   security boundary.
3. **The #578 cross-repo lane already solves this shape.** Cross-repo runs
   commit to the git lane end-to-end: `git worktree add` + `cd` (no
   `EnterWorktree`), git cleanup at Step 7, guards resolving via git plumbing.
   A base-override run is the SAME shape with a different path prefix - the
   override can reuse that lane verbatim instead of inventing new mechanics,
   and it sidesteps the constraint-2 prompt entirely because `cd` inside Bash
   is not a session-cwd transfer.
4. **Codex hook events** are `SessionStart`, `PermissionRequest`, `PreToolUse`,
   `PostToolUse`, `UserPromptSubmit` only - confirming the issue's premise
   that no hook-based mechanism can exist on the CxPP side.

## Options

### Option A (recommended if the owner wants to WORK from ~/Projects): configurable base, default unchanged

Introduce one knob, identical in both packs (hybrid SoT):

- **Name:** `FLOW_WORKTREE_BASE` (env var; host-level, e.g. `~/.bashrc`).
  An env var rather than a repo config file because the setting is a
  per-BOX operator preference - putting it in repo config would re-create
  the PR #527 problem in a different file; an env var also behaves
  identically under both harnesses and in the bash-driven flow commands.
- **Semantics:** unset (shipped default) -> exactly today's behavior,
  byte-identical paths, `EnterWorktree(name=...)` fresh lane intact. Set ->
  worktrees are created at `$FLOW_WORKTREE_BASE/<repo>-<branch>` (the
  `<repo>-` prefix disambiguates across repos sharing one base) and the run
  commits to the #578 git lane end-to-end: `git worktree add` + `cd`, git
  cleanup at Step 7, `ExitWorktree` never involved.
- **Blast radius (corrected, much smaller than the issue's estimate):**
  - CPP: `auto.md` (3 sites), `start.md` (2 sites), prose in `sync.md` /
    `status.md` / `cleanup.md` / `merge.md` / `CLAUDE.md`, then regen
    `plugins/` + `codex/skills/`. The guard/merge/remove/friction scripts
    need NO changes (verified above). `.gitignore` and `drift-detect.sh`
    stay as-is for the default.
  - CxPP: `flow-start/reference.md` + `flow-auto/reference.md` (twin issue,
    same knob name and semantics).
- **Costs / risks:** see Security notes below; primary trade-off is that
  out-of-repo checkouts leave the repo's gitignore/backup boundary.

### Option B: native WorktreeCreate hook - REJECTED

Codex has no such hook (constraint 4), and in CPP it would cover only the
`EnterWorktree` fresh lane, not the two git lanes. Asymmetric and incomplete;
carried over from the issue body, confirmed by this pass.

### Option C: hardcode a new default in both packs - REJECTED

Imposes the owner's box layout on every pack user (PR #527 norm) and breaks
the in-repo hygiene assumptions (`.gitignore`, drift-prune) for everyone.

### Option D (recommended if the owner mostly wants to SEE them): symlink farm, storage unmoved

Worktrees stay exactly where they are; visibility is a projection:

- `flow:start` / `flow:auto` Step 1 create
  `~/Projects/_worktrees/<repo>-<branch>` as a symlink to the real in-repo
  worktree; `flow:merge` / `flow:cleanup` remove it; `flow:doctor` reports
  dangling links. Opt-in via its own env var (e.g.
  `FLOW_WORKTREE_LINK_FARM=$HOME/Projects/_worktrees`), default off - shipped
  behavior unchanged.
- **Why it is attractive given the constraints:** zero storage move, zero
  guard impact, no `EnterWorktree` change, no unsuppressable approval prompt
  (constraint 2 never fires), trivially symmetric in CxPP, and `cd`-ing
  through the symlink into the worktree works for normal git use.
- **What it cannot do:** make the worktree a first-class directory for
  tooling that resolves real paths (`project-next` enumeration, shells that
  resolve symlinks); the checkout still physically lives inside the repo.
  If the owner's answer to decision 2 is "actually work from `~/Projects`",
  D is insufficient and A is the answer.

## Security / risk notes (Phase 0 norm)

- **Out-of-repo checkouts (A only) leave the repo boundary.** Backup tools,
  file indexers, and other repos' tooling can see worktree contents that
  today sit behind the repo's own gitignore. Owner-box-only exposure (the
  default never moves), but worth stating: anything secret-ish that lands in
  a worktree becomes visible to whatever scans `~/Projects`.
- **Project-enumeration pollution:** a worktree interleaved directly under
  `~/Projects/<name>` would be picked up by `project-next` / `project-lite`
  and `CLAUDE_PROJECT` resolution as if it were a project. The dedicated
  `_worktrees/` subdir (decision 3) exists to prevent this in both options.
- **No permission-boundary change under D**; under A the git-lane design
  AVOIDS the `EnterWorktree(path=...)` prompt rather than normalizing
  clicking through it (constraint 2).
- **Guard integrity:** the #486 leak guard and #471 friction buffer resolve
  via git plumbing and keep working under both options (verified in the
  sweep); no guard needs a compensating change, so neither option weakens an
  existing protection.

## Open decisions for owner (restated with this pass's findings weighed in)

1. **Scope: real feature in both packs, or personal-box-only override?**
   The corrected blast radius (2 command files + prose per pack, guards
   untouched) makes the real feature cheap enough that the shipped-knob path
   no longer carries the coordination cost the issue feared. Recommendation:
   ship the knob (A or D per decision 2); the owner's box sets the env var.
2. **What must "visibility" solve - see them, or work from `~/Projects`?**
   This is the fork between D (see) and A (work-from). Constraint 2 (the
   unsuppressable prompt) and the boundary note above are the new costs on
   A's side of the scale; D's cost is that the projection is shallow.
3. **Layout under the base:** dedicated subdir
   `~/Projects/_worktrees/<repo>-<branch>` vs interleaved
   `~/Projects/<name>`. Recommendation: dedicated subdir in BOTH options -
   it keeps `project-next` / `project-lite` enumeration clean and groups
   in-flight checkouts in one glanceable place, which is most of the
   visibility win anyway.

## Phase 1 exit bar (issues to cut once the owner decides)

If **A** (work-from):

- CPP: wire `FLOW_WORKTREE_BASE` into `start.md` + `auto.md` Step 1 (override
  -> git lane, reusing the #578 mechanics), update the prose surfaces +
  CLAUDE.md, regen `plugins/` + `codex/skills/`, add a `flow:doctor` check
  reporting the effective base.
- CxPP twin issue: same knob, same semantics, in the two `reference.md` files.
- Owner box (no repo change): `export FLOW_WORKTREE_BASE=$HOME/Projects/_worktrees`.

If **D** (see):

- CPP: link create in `start.md` / `auto.md`, link prune in `merge.md` /
  `cleanup.md`, dangling-link report in `doctor.md`; regen generated
  surfaces.
- CxPP twin issue: same, in the flow skill references.
- Owner box: `export FLOW_WORKTREE_LINK_FARM=$HOME/Projects/_worktrees`.

Either way the exit bar for #572 itself is this ADR plus the decision comment
on the issue - implementation is deliberately NOT started until the owner
answers, per the issue's own framing.
