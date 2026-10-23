# Flow run record - issue #1542

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=97a9324581764707a5404eb2570784c6 -->
## Run 1

- Run-id:            97a9324581764707a5404eb2570784c6
- Run-start:         ff0bbdf9cbeb421129e8ef3d25135725c87d60aa
- Issue:             #1542
- Base SHA:          ff0bbdf9
- Necessity verdict: Still needed
- Approval:          granted (GATE: GO-WITH-CONDITIONS rev 6; RATIFY of condition 1 and of the narrowed condition 3, rev 7)
- Approver:          cpp-group orchestrator (cpp-orch), authority-model=orchestrator-only, policy rev 1
- Recorded at:       2026-10-23T12:40:00Z

### Section B evidence
commits: ff0bbdf9 (#1545) only, which adds one more affected call. PRs: #1545. dup/super: none (#1408 introduced the
rewrite, #1543 added the merge block). Host: no sibling worktree with unpushed commits on these paths.
Pre-fix reds on ff0bbdf9 using the real flow-auto mirror line: scratch target -> exit 127; decoy target -> DECOY-GATE-RAN, exit 0.
Codex 0.164.0: the system prompt gives the absolute SKILL.md location (alias r0=/home/cooneycw/.codex/skills) and says
"Resolve relative paths against the directory containing a filesystem-backed SKILL.md"; a live `codex exec` env had no
skill-dir variable and no CODEX_HOME, with pwd = target. Skill roots per OpenAI docs: .agents/skills (cwd..repo root),
~/.agents/skills, /etc/codex/skills, system; plus ~/.codex/skills on this host.

### Section C - the approved plan
1. `scripts/codex-skill-sync.py` - rewrite `~/.claude/scripts/<name>` and fenced relative `scripts/<name>` (to real scripts, minus an enumerated CPP-checkout exception table) to `${CPP_SKILL_DIR:-/dev/null}/scripts/<name>`; correct the "skill-dir-relative" comment; rewrite BUNDLED_SCRIPTS_BULLET (definition, set-or-substitute, 126/127 "Not a directory" = unset, CPP-checkout exception, prose naming rule)
2. `controls/codex-skill-sync-remap/run-case.sh` - execute the rendered invocation from a scratch non-skill cwd holding a decoy, with CPP_SKILL_DIR set to a tmp skill dir; finding = the bundled copy ran AND the decoy did not; new historical anchor = the ff0bbdf9 gate (control.json + anchors/)
3. `tests/test_codex_skill_sync.py` - rendered form; red (1) on the real flow-auto gate line from a scratch target; red (2) decoy never runs (set or unset); unset expansion pinned, including a decoy at /scripts; exception-table staleness; every rendered ref is bundled in the same skill (with a deletion mutant)
4. `tests/test_gh_pr_merge.py` - mirror merge-block tests place the stub via CPP_SKILL_DIR; mirror block with the variable unset and a decoy in cwd gives MERGE_RC 12, decoy never runs
5. `.claude/commands/flow/auto.md` - the Step-2 speckit sentence points at the skill-anchored form
Scope: 4 sources plus the control and regenerated mirrors. Risk: agents that ignore the bullet get a loud 126 on every helper call (intended); a test elsewhere may pin the old mirror spelling.

CPP-checkout exceptions that stay cwd-relative (enforced as data in scripts/codex-skill-sync.py; file:line at ff0bbdf9, with the source sentence that makes each CPP-only):
- cpp/update.md 1448, 1565, 1656, 1676, 1680, 1692 (mcp-drift.py): the block opens `cd "$CPP_DIR"`
- cpp/update.md 1527 (friction-log.sh, a comment in a CPP_DIR block); 1969 (commands-mirror-sync.sh), 2005 (codex-skill-sync.py --install), 2017 (install-memory-harness.sh), 2026 (retired-surface-prune.py), 2062 (install-drift.sh): /cpp:update operates on the checkout ("directly above this checkout")
- cpp/init.md 314 (cpp-commands-link.sh) and 2347 (memories-db-setup.sh): text naming checkout scripts in an init run from the checkout
- flow/auto.md 901, 902, 1586, 1587 and flow/finish.md 92, 93 (codex-skill-resync.sh): "`[ -x ]` KEEPS THIS CPP-ONLY"
- flow/repair.md 60 (flow-helpers-install.sh): "**1. CPP checkout** - a source of truth, preferred"
- flow/register.md 224 and 603 (flow-wave-registry.sh): lane path DATA in the CPP repo (`--granted '...'`, a PUSHBACK example), not invocations; 885 (flow-vantage.sh): "or scripts/flow-vantage.sh in a CPP checkout"
- project/init.md 187 (project-init.py): an echo naming the "claude-power-pack checkout"
Rewritten fenced relative refs: documentation/c4.md 135; flow/merge.md 471; flow/wave.md 725, 862, 872, 886; security/permissions.md 32; self-improvement/retro.md 87; spec/adopt.md 81, 84.
Unset-default rationale: /dev/null is a character device, so /dev/null/scripts/X is ENOTDIR (bash exit 126). A container runtime mounts /dev itself; a busybox image that tried to make /dev/null a directory still saw the char device at runtime, and the decoy did not run.
