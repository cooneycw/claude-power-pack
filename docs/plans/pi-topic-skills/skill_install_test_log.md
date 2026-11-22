# Empirical CPP Skill-Install Verification Log (`pi` `1.6.0`)

- **Attribution:** This is a retained operator-provided historical record, not a rerun by the Codex documentation preparer. The command-derived specimen is historical research only and is outside the selected topic-only Part-1 delivery.
- **Date:** 2026-11-22
- **Target CLI:** `@earendil-works/pi-coding-agent` `1.6.0` (GitHub Copilot provider, active model `gpt-5.3-codex`, attached `tmux` session `pi:0.0`)
- **Authorized Scope:** Per owner authorization relayed via `kyle-cli-helper` (`2026-11-22`), **only** CPP skill-install tests in `~/.pi/agent/skills/` and live `/reload` verification in `tmux` session `pi` were executed on the host, with every install logged alongside its exact undo command.
- **Strict Boundaries Respected:**
  - Zero `pi` credential or settings files (`~/.pi/agent/<pi-auth-file>`, `~/.pi/agent/<pi-mcp-auth-file>`, `~/.pi/agent/settings.json`, `~/.pi/agent/models-store.json`) were read, copied, or modified.
  - Zero global rule files (`~/.pi/agent/AGENTS.md`), MCP configs (`~/.pi/agent/mcp.json`), auth tokens, or container experiments were touched on the host (all such work is gated on a `master`-arranged fresh-`HOME` session).
  - Zero tracked files in `kyle` or `claude-power-pack` were modified.

---

## 1. Pre-Test Baseline (`2026-11-22T09:04-05:00`)

1. Directory listing of `~/.pi/agent/` showed **no** `skills/` directory (`PRE_SKILLS_EXISTED=no`).
2. Read-only `tmux capture-pane -p -t pi:0.0` recorded five empirical facts directly relevant to both plans:
   - `pi` `v1.6.0` automatically loaded workspace-level `[Context] AGENTS.md`.
   - On first launch without `fd` or `ripgrep` in `~/.pi/agent/bin/`, `pi` downloaded both (`fd installed to ~/.pi/agent/bin/fd`, `ripgrep installed to ~/.pi/agent/bin/rg`).
   - `pi` emitted: `Warning: tmux extended-keys is off. Modified Enter keys may not work. Add set -g extended-keys on to ~/.tmux.conf and restart tmux.`
   - `pi` emitted: `Error: Logged in to GitHub Copilot, but its default model "gpt-6.1-sol" is not available. Use /model to select a model. Model: gpt-5.3-codex` - proving `pi`'s static catalog default (`gpt-6.1-sol`) is gated by account `availableModelIds` and `gpt-5.3-codex` (`gpt-5.3-codex • minimal`) is live on the subscription.
   - Standard `tmux capture-pane -p` captured the full idle composer frame (`────...────` borders + footer `$0.000 (sub) 0.0%/1.0M (auto) ... gpt-5.3-codex • minimal`) cleanly.

---

## 2. Installed Probe Packages & Exact Undo Commands (`2026-11-22T09:06-05:00`)

### Install #1 - Option B Bundled Topic Skill (`code-quality`)
- **Action:** Created `~/.pi/agent/skills/code-quality/` by copying canonical `claude-power-pack/.claude/skills/code-quality/SKILL.md`, injecting `metadata.source: claude-power-pack/.claude/skills/code-quality`, copying `claude-power-pack/docs/skills/code-quality.md` into `references/code-quality.md`, and rewriting the `docs/skills/code-quality.md` reference to `./references/code-quality.md` (no symlinks, no plugins).
- **Installed files & SHA256 digests:**
  - `9346e7a20690a3d730fd629a4178075335f9f7bd61625d826b68082de6b08b24`  `~/.pi/agent/skills/code-quality/SKILL.md`
  - `f706341c9a9d4a9255482639ce7648d7ae5f31e4c59fa11915559a91c41ba80e`  `~/.pi/agent/skills/code-quality/references/code-quality.md`
- **Exact Undo Command:**
  ```bash
  rm -rf ~/.pi/agent/skills/code-quality
  rmdir --ignore-fail-on-non-empty ~/.pi/agent/skills
  ```

### Install #2 - Command-Derived Workflow Skill Specimen (`flow-check`)
- **Action:** Generated the `flow` family into a temporary staging directory via `scripts/codex-skill-sync.py --write flow --output-root <tmp>` and copied `flow-check/` (`SKILL.md`, `reference.md`, `PROVENANCE.md`, `lib/cicd/*`, `scripts/*`) into `~/.pi/agent/skills/flow-check/` to test multi-file command-skill loading (`reference.md` + `scripts/`) under `pi`'s Agent Skills loader.
- **Installed files & SHA256 digests:**
  - `324996a33274896d6436cc8f4a924c2c57c08b3576e24829050f7758ab1595b7`  `~/.pi/agent/skills/flow-check/SKILL.md`
  - `47ffce93a9fc10648b1df943e47f3d77daeb4cf412a7e4b1ba9009e6f3412289`  `~/.pi/agent/skills/flow-check/reference.md`
  - `2ce281239a304ed3fe60f126b47158deb274ff46237f678e006a2a8f5e313c12`  `~/.pi/agent/skills/flow-check/PROVENANCE.md`
  - `84bfb89f64418d571f8bfceaee74770ceca7cb509a3980b7119ae82a7836b4cf`  `~/.pi/agent/skills/flow-check/lib/cicd/__init__.py`
  - `11310cd33c814c18c196677911323171425415b842c6999672e9c82906bcefc3`  `~/.pi/agent/skills/flow-check/lib/cicd/evidence.py`
  - `9d194dcb58129a70395c89d908f86da2c44ce392e0442c1663ad67a8afa55d81`  `~/.pi/agent/skills/flow-check/lib/cicd/state.py`
  - `287e0ae0b17aac17c06046993d0ed9b2830bf39148f4720b28872b603581a6d5`  `~/.pi/agent/skills/flow-check/scripts/SHA256SUMS`
  - `8824f2c71c4d82d9a2b5784b64a55aa4de22a0d237408db2ed970766f75b67ce`  `~/.pi/agent/skills/flow-check/scripts/check-ignored-additions.sh`
  - `d1e7f70fc3784c4a9f53e9328caecf848447b704c79a079a3211e2f5c68b273e`  `~/.pi/agent/skills/flow-check/scripts/coordination-admission.sh`
  - `48cd3596f1d5d670fa51d6690a60ac17085fa609d4a8d3ca7ad32a49a88a342c`  `~/.pi/agent/skills/flow-check/scripts/counter-model-receipt.py`
  - `21b2aecaa85de18724f8f09a37a4a0bd44790db494b56571c6a25f548805b299`  `~/.pi/agent/skills/flow-check/scripts/execution-evidence-verify.py`
  - `7343756ac852fc327c44784434d2dcbe8c13e31ce9989408e7b65348e3d31239`  `~/.pi/agent/skills/flow-check/scripts/flow-finish-gate.sh`
  - `4095e524bf802a97f48add745e5c64addfe1055eac67c484b5ad81e5c26b38a8`  `~/.pi/agent/skills/flow-check/scripts/gate-lib.sh`
- **Exact Undo Command:**
  ```bash
  rm -rf ~/.pi/agent/skills/flow-check
  rmdir --ignore-fail-on-non-empty ~/.pi/agent/skills
  ```

---

## 3. Verification Results

1. **Live `tmux` session `pi:0.0` `/reload`:**
   - Sent `/reload` + `Enter` to `pi:0.0`.
   - `pi` reloaded cleanly with zero validation errors or warnings and displayed:
     ```text
     [Context]
       AGENTS.md

     [Skills]
       code-quality, flow-check

      Reloaded keybindings, extensions, skills, prompts, themes, and context files
     ```
2. **Isolated RPC `get_commands` inspection (empty temporary `$HOME`, `--offline -ns --skill ...`):**
   - Returned `success: true` with `skill:code-quality` and `skill:flow-check`, each carrying `source: "skill"` and `sourceInfo.baseDir` pointing to the skill directory (confirming relative `./references/code-quality.md` and `scripts/*` resolve against `baseDir`, and confirming `pi` skill commands use `/skill:<name>` rather than Codex's `/<name>`).
3. **`scripts/skills-check.py --managed-root ~/.pi/agent/skills` empirical finding (`RC=1`):**
   - Output:
     ```text
     skills-check: managed installs: checked 1 CPP-marked package(s), 0 clean, skipped 1 (no CPP source marker)
     skills-check: 1 failure(s)
       MANAGED_DRIFT: .../skills/code-quality/SKILL.md: SKILL.md metadata or body differs; supporting files differ (extra references/code-quality.md)
     ```
   - **Architectural consequence for CPP (`CPP#1876` & `pi`):** `scripts/skills-check.py:670-698` (`_managed_differences`) currently compares `--managed-root` directly against unbundled `.claude/skills/<slug>/` (which still points at `docs/skills/<topic>.md` and has no `references/` directory). Therefore, bundling `docs/skills/*.md` into `./references/*.md` under Option B **requires** `skills-check.py` (or `install-drift.sh`) to compare `--managed-root` against the deterministic bundled topic-skill build output (or apply the identical bundling normalization before `_managed_differences`), alongside an explicit package-name membership floor (`0` validated is never clean).

---

## 4. Undo Execution & Clean-State Verification (`2026-11-22T09:06:31-05:00`)

- Executed both logged undo commands (`rm -rf ~/.pi/agent/skills/code-quality ~/.pi/agent/skills/flow-check && rmdir ~/.pi/agent/skills`) and confirmed `[ ! -e ~/.pi/agent/skills ]` (`UNDO_VERIFIED=skills_dir_removed_cleanly`).
- Sent `/reload` + `Enter` to `pi:0.0`; `capture-pane` confirmed `[Skills]` disappeared cleanly and `pi` returned to its exact pre-test idle prompt (`gpt-5.3-codex • minimal`) with zero residual host artifacts.
