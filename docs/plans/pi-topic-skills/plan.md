# Part 1 Plan (rev 6.1): `claude-power-pack` into `pi` (`@earendil-works/pi-coding-agent` `1.6.0`) - Option B Topic Skills & Installation Validation Only

- **Status:** Round 4 accepted Part 1 with nits. Rev 6.1 makes session-history source precedence and refusal controls explicit after rev 6 closed the session-history and trusted-configuration destination gaps (2026-11-22). This revised document awaits review; no implementation acceptance is claimed.
- **Evidence boundary:** Historical install/discovery observations below are supplied by the owner-approved test log; this documentation preparer has not rerun the host experiments. Security controls described here are planned tests, not implemented or executed proof.
- **Target CLI:** `@earendil-works/pi-coding-agent` `1.6.0` (Node `>= 22.19.0`)
- **Binding Owner Scope & Sequencing (`2026-11-22`):**
  1. **Strictly limited scope:** Part 1 is **limited strictly to copying CPP's canonical topic skills into `~/.pi/agent/skills/` (Option B) and validating their installation** - specifically:
     - Option B topic-skill copying (`scripts/pi-skill-sync.py`);
     - bundled-reference parity (`./references/*.md`);
     - expected-package membership floor;
     - foreign-collision protection; and
     - install and discovery validation (`skills-check.py` + isolated `pi --mode rpc` discovery check).
  2. **Everything deeper is deferred until Part 1 is validated (Section 5):** Shared `/cpp:update` cohort enrollment, global rules (`~/.pi/agent/AGENTS.md` / `AGENTS.override.md`), MCP configuration (`~/.pi/agent/mcp.json`) and `mcp-drift.py`, `cpp-install-receipt.py` capability rows, command-derived workflow skill generation, `counter-model-receipt.py` schema/adapter changes, `/copilot:{auto,ask,...}`, and containerized `pi`-in-Kyle runtime (Kyle ADR 0016 (pi into Kyle, tracked separately)) are **all deferred** until Part 1 is validated.
  3. **Release independence & host boundaries:** Non-destructive `pi` preparation stays independent of the Kyle prod release (`#2619`/`#2613`); neither blocks the other's non-destructive preparation. Documented plans merge before implementation scaffolding is activated. Under the current assignment, the two parked Part-1 issue drafts may be filed only after master review; no CPP documentation PR is opened or pushed and no CPP CI runs before the Kyle series-27 pin. Implementation follows AGY Wave 1; pi remains in the later updater cohort. Only CPP skill-install tests in `~/.pi/agent/skills/` ran on the host and were cleanly undone ([skill_install_test_log.md](./skill_install_test_log.md)); neither CPP nor Kyle ever reads, stats, or copies `~/.pi/agent/auth.json` or `mcp-auth.json`.

---

## Change Summary (rev 6 to rev 6.1)

1. Explicitly resolve session-history candidates in this order: CLI `--session-dir`, `$PI_CODING_AGENT_SESSION_DIR`, merged global/project `sessionDir`, then `<agent>/sessions`. Refuse output under the effective directory and every non-empty candidate, including overridden candidates. This is the required plan contract, not a claim that the preparer independently verified pi runtime behavior.
2. Read only the non-secret settings inputs `<agent>/settings.json` and `<cwd>/.pi/settings.json`, read-only without a lock; project settings override global settings. Unreadable or malformed settings exit 1 rather than silently selecting a default. Never inspect authentication files. Normalize `~`, `file:` URLs and cwd-relative paths before realpath resolution; unresolved or unsafe paths fail closed without forbidden-root probes.
3. Extend `output_root_under_sessions` with separate CLI, environment, global-settings, project-settings and default cases, plus conflicting-source precedence and overridden-candidate cases. These are planned negative controls, not newly executed tests. The release freeze and Part-1 scope remain unchanged.

## Historical Change Summary (rev 5 to rev 6)

1. `--output-root` must resolve outside the entire agent directory, including its skills, sessions, extensions, settings, tools and all B3 trusted configuration. The build-output interface cannot be used as an alternate install interface. Add `output_root_under_trusted_config` with direct `<agent>/extensions/skills` and alias/symlink cases; all refuse with zero forbidden-root touches. A legal isolated build root remains the positive comparison.
2. Resolve the actual effective session-history directory using the same precedence as pi, including `--session-dir`, configured `sessionDir` and the default. Refuse output inside that directory even when it is outside the agent tree. Add a non-default external `sessionDir` case and aliases to `output_root_under_sessions`; an agent-only or basename-only guard must fail the control.
3. Preserve the six security boundaries, zero credential-file inspection, syscall-level transient-write detection, limited topic-skill scope and the downstream release freeze. This is documentation only; no runtime or copier behavior has been executed by this revision.

## Historical Change Summary (rev 4 to rev 5)

1. Close the remaining Round-4 Part-1 nit: explicitly refuse every `--output-root` destination under `<agent>/sessions`, even one ending in `skills`, before any session-history access. Add the named `output_root_under_sessions` control with nested/alias cases, a legal-build positive comparison and a seeded basename-only guard that must fail.
2. Preserve all six owner security boundaries, including zero authentication-file probing and syscall-level transient-write observation. Runtime/container controls remain deferred; no live pi-in-Kyle work is authorized.
3. Apply current scheduling direction: prepare documentation locally without CPP pushes or CI before the Kyle series-27 pin; the two parked issue drafts require review before filing. Implementation follows AGY Wave 1, with pi in the later updater cohort. Copilot is an owner-acknowledged assumption, with configurable limits/budgets and alternative providers, not a design blocker.

## Historical Change Summary (rev 3 to rev 4)

1. **Applied Round-3 Nit (a) - Syscall-level write observation for Boundary 3 (`session_overwrites_trusted_config`):** Replaced snapshot-only `host-surface-observe.py` reliance (which sees only surviving paths) with **syscall-level write tracing** (`strace -f -e trace=%file` / `seccomp` write-intent audit in the test harness) asserting zero mutating or write-open syscalls outside `<agent_dir>/skills/` and `<agent_dir>/.cpp-skill-install.lock`, backed by a seeded transient create-then-unlink outside `skills/` proven to fail the syscall check even when the post-run directory snapshot is clean.
2. **Applied Round-3 Nit (b) - Positive destination confinement requiring zero auth-file probe (`Section 2.1`):** Replaced negative checks ("contains `auth.json` or `settings.json`", which would `stat` `auth.json` and collide with `pi_auth_open_attempt`) with **strictly positive path rules**: `--install` targets **only** `<resolved_agent_dir>/skills` (`lstat`-verified real directory), and `--output-root <DIR>` accepts **only** a resolved path whose final component is literally `skills` (or a dedicated build subdirectory under `<repo>/pi/skills` or `$TMPDIR`) that is not `$HOME`, `~/.pi`, or `<resolved_agent_dir>` - inspecting zero neighbor filenames inside `<resolved_agent_dir>`.

---

## 1. Empirical Baseline (`pi 1.6.0`, Verified 2026-11-22)

| Surface | Verified `pi 1.6.0` Fact (`docs/skills.md` + live `pi:0.0` test) | Consequence for Part 1 |
|---|---|---|
| User skill root | `~/.pi/agent/skills/<name>/SKILL.md` (`PI_CODING_AGENT_DIR` override supported). Agent Skills spec: `name` 1-64 lowercase `[a-z0-9-]` matching parent dir, `description` $\le 1024$ chars. | `scripts/pi-skill-sync.py` writes **only** inside `<resolved_agent_dir>/skills/<slug>/` (plus advisory lock `<resolved_agent_dir>/.cpp-skill-install.lock`). |
| Discovery & tool non-replacement | Live `/reload` in `pi:0.0` loaded Option B bundled `code-quality` (`./references/code-quality.md`) with zero warnings; isolated RPC `get_commands` returned `skill:code-quality` (`source: "skill"`, `sourceInfo.baseDir` set); undo + `/reload` restored the absent baseline. Skills expand only as `/skill:<name>` Markdown (`docs/extensions.md:1775`) and cannot register LLM tools unless a `package.json` manifest smuggles extensions. | Forbidding `package.json`, symlinks, traversal, and executable/script files inside copied topic skills guarantees skills cannot replace trusted tools or escape `~/.pi/agent/skills/<slug>/` (`skill_path_escape`). |
| `skills-check.py --managed-root` `MANAGED_DRIFT` (proven live) | `scripts/skills-check.py:644-698, 741-756` strips `metadata.source` and diffs `SKILL.md` body and `_supporting_files()` against unbundled `.claude/skills/<slug>/`. On bundled `code-quality`, it exited `1` (`MANAGED_DRIFT: SKILL.md metadata or body differs; supporting files differ (extra references/code-quality.md)`). | Part 1 adds bundled-reference parity (`--bundled-topic-root` / normalization) + expected-package membership verification so bundled topic skills validate cleanly without a 0-validated blind spot. |

---

## 2. Design: Topic-Skill Copying & Installation Validation

### 2.1 Option B Topic-Skill Copier (`scripts/pi-skill-sync.py`)
1. **`scripts/codex-skill-sync.py` stays untouched (`CPP#1876` Decision 3):** `scripts/pi-skill-sync.py` (`--check`, `--write`, `--install`, `--verify-installed`, `--output-root`) is a standalone thin CLI so `kyle` (`core/container_capabilities.py`), `skillc`, and `kyle-candidate` face zero interface risk.
2. **Deterministic build (`pi/skills/<slug>/`, gitignored per ADR 0013):**
   - Copies canonical `.claude/skills/<slug>/` topic skills into `pi/skills/<slug>/`, bundles referenced `docs/skills/<topic>.md` files into `./references/<topic>.md`, rewrites `SKILL.md` links to `./references/<topic>.md`, and injects `metadata.source: claude-power-pack/.claude/skills/<slug>`.
3. **Confinement & positive destination guards (`skill_path_escape`, `pi_auth_open_attempt`):**
   - `<slug>` must match `^[a-z0-9]+(?:-[a-z0-9]+)*$` (`1..64` chars; rejects `.`, `..`, `/`, leading/trailing/`--` hyphens).
   - Every source and destination entry is checked with `O_NOFOLLOW` and `realpath` containment strictly inside `<skills_root>/<slug>/`; **any symlink anywhere in the package is refused (`exit 1`)**.
   - **Regular `0644` Markdown-only allowlist:** Only `SKILL.md` and `references/*.md` regular UTF-8 files (`0644`, zero `+x` bits) are permitted. Any `package.json` (`pi` package manifest), `.ts`, `.js`, `.mjs`, `.py`, `.sh`, dotfile, or binary file is **refused (`exit 1`)**.
   - **Positive destination confinement (zero auth-file probe):**
     - `--install` writes **exclusively** to `<resolved_agent_dir>/skills` (`~/.pi/agent/skills` or `$PI_CODING_AGENT_DIR/skills`), checking via `lstat` only that `<resolved_agent_dir>` is an existing non-symlink directory and `<resolved_agent_dir>/skills` (if present) is a non-symlink directory - **never listing or `stat`ting sibling files in `<resolved_agent_dir>`**.
     - **Build-output confinement:** `--output-root <DIR>` accepts only a permitted build root ending in `skills` that resolves **outside `<resolved_agent_dir>` entirely**, and outside every effective session-history root. It refuses the agent root and all descendants, including `<agent>/skills`, `<agent>/sessions`, `<agent>/extensions/skills`, settings, tools and every B3 trusted configuration root. Only `--install` may select the canonical `<agent>/skills` installation root. Refuse an unsafe or unresolved destination with exit 1 before creating, listing, opening or statting forbidden descendants; do not probe authentication neighbors.
     - **Alias-safe exclusion (`output_root_under_trusted_config`):** normalize traversal and resolve symlink aliases without descending into forbidden roots. Check normalized link targets before following into a forbidden tree; inability to establish confinement refuses. Both direct `<agent>/extensions/skills` and an external alias/symlink targeting it must refuse with zero touches under trusted configuration. A legal isolated build root outside both the agent and history trees is the positive comparison.
     - **Actual session-history exclusion (`output_root_under_sessions`):** resolve CLI `--session-dir` first, then `$PI_CODING_AGENT_SESSION_DIR`, then `sessionDir` from global `<agent>/settings.json` merged with project `<cwd>/.pi/settings.json` (project wins), then `<agent>/sessions`. Read these settings read-only without locking; unreadable or malformed settings exit 1. Normalize `~`, `file:` URLs and cwd-relative paths, then resolve realpaths safely. Refuse output under the effective directory AND every non-empty candidate, even an overridden one. Test each source separately, conflicting sources, overridden candidates and unsafe/unresolved paths; no unresolved history configuration may silently fall back and pass. Refuse the actual history root and all descendants, including a non-default external `<history>/skills`, nested forms and aliases, before any history probe or write. Never read, stat or copy authentication files to obtain this setting.

4. **Foreign-collision protection & atomic `--install` (`foreign_package_collision`):**
   - Acquires advisory `flock` on `<resolved_agent_dir>/.cpp-skill-install.lock` (refusing cleanly with `not-applicable` exit `5` if `<resolved_agent_dir>` is absent).
   - Preserves unmarked user-authored skill directories (`metadata.source` absent or non-CPP) untouched.
   - If an unmarked directory occupies a canonical CPP topic-skill `<slug>` (e.g., user-authored `~/.pi/agent/skills/code-quality/`), `--install` **refuses** (`foreign-collision`, `exit 1`, zero bytes overwritten) unless `--adopt` backs it up first.
   - Declares `HOST-SURFACE:` headers (`~/.pi/agent/skills`, `~/.pi/agent/skills/<skill>`, `~/.pi/agent/.cpp-skill-install.lock`) for `scripts/host-surface-observe.py` (`#1150`).

### 2.2 Bundled-Reference Parity, Membership Floor, & Discovery Validation
1. **Bundled-reference parity (`scripts/skills-check.py`):** Add `--bundled-topic-root <fresh-build-dir>` (comparing `--managed-root` against a fresh bundled topic-skill tree rather than unbundled `.claude/skills/`) plus the `skill_path_escape` containment checks (`0644` Markdown-only, no symlinks, no `package.json`/scripts).
2. **Expected-package membership floor (`pi-skill-sync.py --verify-installed` & `scripts/install-drift.sh`):** Build fresh `pi/skills/` in a temporary directory, run `skills-check.py --managed-root ~/.pi/agent/skills --bundled-topic-root <tmp>`, and assert that **every** expected canonical topic-skill slug was validated (`managed_checked == len(EXPECTED_TOPIC_SKILLS)` and `missing == 0`; `0` validated is never clean).
3. **Hermetic `pi` discovery validation:** In automated tests (isolated empty `$HOME` + `PI_OFFLINE=1`, zero host credentials), run `pi --mode rpc --no-session --offline -ns --skill <installed_dir>` with `{"id":"c1","type":"get_commands"}` and assert every copied topic skill loads cleanly as `skill:<slug>` (`source: "skill"`, `sourceInfo.baseDir` set) with zero stderr warnings and without altering `pi`'s built-in tool list.

---

## 3. Six Mandatory Security Boundaries & Named Negative Controls (`ADR 0008`)

All six owner-mandated security boundaries are named in both plans; **host/skill controls execute in Part 1**, while **container/runtime session controls execute in Kyle ADR 0016 (pi into Kyle, tracked separately) (deferred until Part 1 is validated)**:

| # | Security Boundary | Part 1 Enforcement & Active Named Control(s) | Runtime / Container Control(s) (Deferred to ADR 0016) |
|---|---|---|---|
| **1** | Never directly read or inspect `pi`'s authentication file | **`pi_auth_open_attempt`** *(Part 1 active)*: `0000`-mode canary `~/.pi/agent/{auth,mcp-auth}.json` + syscall/`open`/`stat` audit hook proves `--check`/`--write`/`--install`/`--verify-installed` (including positive `--output-root` rejection) make `0` open/stat calls on `pi` auth files (seeded `stat("auth.json")` fails test). | `pi_auth_open_attempt` (bootstrap & renewal) & `ambient_oauth` *(deferred to ADR 0016)*. |
| **2** | Auth stays isolated in trusted service, inaccessible to user session | **`topic_skill_auth_helper_rejected`** *(Part 1 active)*: the static Markdown-only copier handles zero credentials or tokens, rejects `!command` helpers or auth links in skill frontmatter/body, and a seeded helper/auth-link package must fail without credential access. Runtime authentication isolation itself is not claimed by Part 1. | **`session_can_obtain_bearer`** & **`bearer_in_logs`** (with seeded leak check) *(deferred to ADR 0016)*. |
| **3** | Cannot write `pi`'s trusted settings, tool definitions, or executable extensions | **`session_overwrites_trusted_config`** *(Part 1 installer leg - syscall-verified)*: Run `--install` under **syscall-level write tracing** (`strace -f -e trace=openat,creat,rename,renameat,renameat2,unlink,unlinkat,mkdir,mkdirat,chmod,fchmodat,symlink,symlinkat,linkat` or `seccomp` audit) with `0444` `~/.pi/agent/{settings,models,mcp}.json` and `0555` `extensions/`; assert **`0` mutating or write-intent syscalls** (`O_WRONLY`/`O_RDWR`/`O_CREAT`/`O_TRUNC`) outside `<agent_dir>/skills/` and `<agent_dir>/.cpp-skill-install.lock` (**seeded transient create-then-unlink outside `skills/` fails the syscall trace** even though surviving-path snapshots stay unchanged). **`output_root_under_trusted_config`** additionally refuses `--output-root <agent>/extensions/skills` and its alias/symlink spelling, plus paths under settings, tools and every B3 trusted root; syscall observation proves zero forbidden-root touches. Valid build writes are allowed only in the explicitly isolated external output root. | **`session_overwrites_trusted_config`** (mounted `:ro` container targets) & **`tampered_extension_contents`** *(deferred to ADR 0016)*. |
| **4** | Session-writable directories separate from trusted config | **`writable_session_dir_isolated_from_skill_root`** *(Part 1 active)*: **`output_root_under_sessions`** and **`writable_session_dir_isolated_from_skill_root`** refuse the default history tree and the actual effective history root and every non-empty candidate: CLI `--session-dir`, `$PI_CODING_AGENT_SESSION_DIR`, merged global/project `sessionDir` (project wins), then default, even outside the agent root. Include one red case per source and conflicting/overridden sources. Seed `<agent>/sessions/skills`, nested/traversal forms, external `<configured-history>/skills` and symlink aliases; all exit 1 with zero history touches or auth-neighbor probes. A legal isolated build destination passes. Basename-only and agent-only guards that admit these cases must fail the control. | **`shadowed_substrate`** & `writable_history_disjoint_from_trusted_config` *(deferred to ADR 0016)*. |
| **5** | Copied skills cannot replace trusted tools or escape permitted directories | **`skill_path_escape`** & **`foreign_package_collision`** *(Part 1 active)*: (a) `../extensions/evil` traversal, (b) symlink inside `references/`, (c) `package.json` `"pi"` extension manifest, and (d) `+x`/`.ts`/`.sh` file each fail with `exit 1`; (e) a skill named `bash` registers only `/skill:bash` and cannot replace built-in `bash` tool; (f) unmarked `skills/code-quality` collision refused (`exit 1`) without `--adopt`, while unmarked `skills/user-custom` is preserved. | **`skill_path_escape`** enforced in `deploy/artifacts.py:build()` *(deferred to ADR 0016)*. |
| **6** | Automated tests verify boundaries & install fidelity | **`missing_expected_skill_or_marker`** (missing slug or stripped `metadata.source` fails membership floor) & **`modified_bundled_reference`** (1-byte edit in `references/code-quality.md` exits `1` `MANAGED_DRIFT`) *(Part 1 active)*. | Full container boundary suite (`B1`-`B6`) *(deferred to ADR 0016)*. |

---

## 4. Rollout (Topic Skills Only; After AGY Wave 1, Later Updater Cohort)

Non-destructive preparation remains release-independent. Publication still waits for the Kyle series-27 pin; implementation waits for AGY Wave 1 and the documentation/plan landing. The two existing deliverables below stay parked until those dependencies are satisfied.

Copilot is an owner-acknowledged assumption, not a concurrency or terms blocker. Concurrency limits, usage budgets and alternative provider/authentication options remain configurable features. Live pi-in-Kyle work is outside Part 1 and requires a fresh owner go when it is reached.

1. **P1-A - `scripts/pi-skill-sync.py` + `skills-check.py` `--bundled-topic-root` + `install-drift.sh` membership floor + syscall-verified boundary & RPC discovery tests:** Ship Option B topic-skill copying, outside-agent/effective-history destination confinement, bundled-reference parity, all active Section 3 negative controls, and `docs/HOST_MANAGED_ARTIFACTS.md` disclosure (`codex-skill-sync.py` untouched).
2. **P1-B - Live host validation gate:** Install CPP topic skills into `~/.pi/agent/skills/` via `pi-skill-sync.py --install`, verify `--verify-installed` + `/reload` in `"pi"`, and obtain owner sign-off that Part 1 is validated before unparking any item in Section 5.

---

## 5. Deferred Until Part 1 Is Validated (Out of Scope)

1. **Shared `/cpp:update` later-cohort enrollment & `cpp-install-receipt.py` `"pi"` capability** (with `updater_fault_isolation` and capability selection controls).
2. **`pi` global rules (`~/.pi/agent/AGENTS.md`) & MCP (`~/.pi/agent/mcp.json` / `mcp-drift.py`):** Requires a `master`-arranged fresh-`HOME` probe; note `pi` honors even an **empty (`0`-byte)** `AGENTS.override.md` (`os.path.lexists` must report `overridden`, `docs/configuration.md:45`), normalizes hyphens in MCP tool names (`mcp__second_opinion__*`, `docs/mcp.md:77`), and requires `"exposure": "direct"`.
3. **Workflow skill generation, `/copilot:{auto,ask,...}`, & `counter-model-receipt.py`:** Narrow `/copilot:ask` to model-declared tools (`--tools read,grep,find,ls --no-mcp -ne`) and use separate parsers for persisted v3 JSONL (`message`) vs. streamed `--mode json` (`message_end` + `agent_settled`).
4. **Containerized `pi`-in-Kyle runtime (Kyle ADR 0016 (pi into Kyle, tracked separately)).**
