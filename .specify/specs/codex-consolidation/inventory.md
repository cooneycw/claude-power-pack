# Codex Consolidation: Capability Inventory

> **Governing spec:** [spec.md](spec.md) - see "Evidence baseline", US1, and
> boundary **B1** (state and credential isolation).
> **Established by:** #1068 | **Epic:** #1067
> **Baseline:** CPP `5ceb966aac96ca4ec1ddafd4cd330b5a174d9a00`,
> CxPP `681ea26b68ff30debdc1efcfa7c57f814f01a0da`, 2026-09-19

---

## How to read this document

This is **what exists**, at a stated baseline. What HAPPENS to each entry is
[ledger.md](ledger.md); this file does not assign dispositions.

Three honesty rules apply throughout, and they are the reason this document is
longer than a file listing:

1. **Counts cite their baseline.** A number without a SHA cannot be told apart
   from a stale one later.
2. **Unknown is written down.** A consumer nobody has enumerated is recorded as
   `unknown`, never omitted (spec US1). An empty list and an unexamined list must
   not look alike.
3. **No credential values.** Namespace paths and variable NAMES are inventory.
   Their contents are not, and are not recorded here or anywhere in this spec
   set (spec boundary **B1**).

---

## 1. Skills and command surfaces

| Surface | Repo | Path | Count @ baseline | Nature |
|---|---|---|---|---|
| Native Codex skills | CxPP | `.codex/skills/` | **85** | Authored for Codex; CxPP's distinguishing asset |
| Plugin-packaged skills | CxPP | `plugins/*/skills/` | **74** across 16 families | Packaged for plugin distribution |
| Generated Codex skills | CPP | `codex/skills/` | **75** | Generated from `.claude/commands/**` by `scripts/codex-skill-sync.py` |
| Claude commands | CPP | `.claude/commands/` | 18 families | The generator's source of record |
| Claude skills | CPP | `.claude/skills/` | 18 | Claude-side skill surface |

**CxPP plugin families (16):** `agents-md` (2), `cicd` (11), `claude` (1),
`cxpp` (3: `cxpp-init`, `cxpp-status`, `cxpp-update`), `documentation` (3),
`evaluate` (2), `flow` (12), `github` (6), `project` (5), `qa` (2),
`second-opinion` (3), `secrets` (9), `security` (6), `self-improvement` (3),
`spec` (2), `woodpecker` (4).

**CPP command families (18):** `browser`, `cicd`, `claude-md`, `codex`, `cpp`,
`documentation`, `evaluate`, `flow`, `gemma`, `github`, `project`, `qa`, `qwen`,
`second-opinion`, `secrets`, `security`, `self-improvement`, `spec`.

**The 85/75 gap is not a defect count.** The two surfaces are produced by
different processes - CxPP's are authored native, CPP's are generated - and the
difference includes CxPP-only families (`agents-md`, `woodpecker`, `cxpp`)
alongside CPP-only ones (`gemma`, `qwen`, `browser`, `cpp`). A per-skill
reconciliation is #1071's work, not this inventory's; what is recorded here is
that the surfaces are **not** a superset/subset pair in either direction.

**CPP already has a Codex command family** (`.claude/commands/codex/`: `ask`,
`auto`, `code_review`, `exec`, `help`, `status`) and Makefile targets
`codex-init`, `codex-install`, `codex-skills`, `codex-skills-check`,
`skills-check`. The adapter of #1071 has an existing foothold; it is not
greenfield.

---

## 2. Runtime and helper modules

| Module | Repo | CPP analogue | Note |
|---|---|---|---|
| `lib/cicd` | both | `lib/cicd` | Parallel implementations. cxpp#256 records that CxPP's `verify` dispatches to nothing |
| `lib/creds` | both | `lib/creds` | Credential handling; see **B1** |
| `lib/security` | both | `lib/security` | Security scanning |
| `lib/project_next` | CxPP | `vendor/project_next/**` (vendored FROM CxPP) | **CPP depends on CxPP here.** #1069 |
| `lib/native_wave` | CxPP | none | 16 modules: `claims`, `codex_transport`, `cursors`, `delivery`, `delivery_store`, `delivery_types`, `event_types`, `events`, `identity`, `ports`, `registry`, `replay`, `storage`, `types`. **CxPP-only.** #1072 |
| `lib/skill_eval` | CxPP | none | `cases`, `cli`, `deterministic`, `evaluate`, `live`, `models`, `naming`. **CxPP-only** |
| `lib/friction` | CxPP | `.claude/friction.jsonl` + `scripts/friction-log.sh` | Different shapes: CxPP has a library, CPP a script + JSONL queue |
| `lib/cpp_memory` | CPP | n/a | **CPP-only** |
| `lib/vendor.py` | CPP | n/a | **CPP-only.** The vendor core that pulls `project_next` from CxPP |

**Scripts:** CxPP 19, CPP 75 (at baseline). CxPP-distinctive scripts with no CPP
analogue: `harness_lint.py`, `skill_contract_lint.py`,
`skill_contract_baseline.py`, `skill-eval.py`, `release_validate.py`,
`native-wave-delivery.py`, `cxpp-hook-transition.py`, `cxpp-influence.py`,
`codex_skills_sync.py`, `prompt-context.sh`, `bash-prep.sh`.

---

## 3. The bidirectional vendor bridge

Recorded in [spec.md](spec.md) as a governing constraint on archival order; the
mechanics are here.

**CPP -> CxPP (the pull model).** `vendor/claude-power-pack/` in CxPP holds:

| File | Content @ baseline |
|---|---|
| `PIN` | `commit: f64a654f76ea8d26a33eb33f785f6e1065a823b6`; `pulls: codex/skills/ -> .codex/skills/` |
| `adoption-policy.json` | `kind: cxpp-selective-cpp-adoption`, schema v1, source commit `f64a654f`, tree `29fc82d3`, `codex_skills_tree` `71046ffe`, plus a historical audit block with baseline/target payload digests |
| `codex-skills.sha256` | Payload digest manifest |
| `overlays/` | CxPP-local adaptations applied over the pulled payload |

The pin `f64a654f` is **behind** CPP main `5ceb966a` at baseline. Any statement
that the two Codex surfaces agree must name the pin it was measured at.

**CxPP -> CPP.** `lib/vendor.py` declares `vendor/project_next/**` as 16 whole
files pulled from CxPP, with three modes (`check` offline hard gate, plus
fetch/compare/re-copy). Makefile targets: `project-next-check`,
`project-next-drift`, `project-next-revendor`.

CPP vendors a second external core the same way - `.claude/commands/flow/eli5.md`
from `cooneycw/eli5-gate` - which is **not** part of this migration but shares
the machinery, so changes to `lib/vendor.py` under #1069 affect it.

---

## 4. Hooks, bootstrap, update and status flows

**CxPP hooks** (`.codex/hooks.json`, 5 events):

| Event | Handler | Note |
|---|---|---|
| `SessionStart` | inline `bash` - fetches origin, reports commits behind | Self-currency notice |
| `PermissionRequest` | `scripts/codex-friction-hook.py` | Friction telemetry |
| `PreToolUse` (Bash) | `~/.codex/scripts/hook-validate-command.sh` | **Installed path**, not repo path |
| `PostToolUse` | `codex-friction-hook.py`, `~/.codex/scripts/hook-mask-output.sh` (x2) | Secret masking on output |
| `UserPromptSubmit` | `python3` handler | Prompt context injection |

Three handlers resolve to `~/.codex/scripts/`, i.e. **installed copies, not repo
files**. This is the concrete shape of spec boundary **B2**: an update that
repoints those paths at different bytes is a hook-trust change even though no
hook definition visibly changed. `scripts/cxpp-hook-transition.py` exists
specifically to manage that transition and is a capability to preserve, not an
implementation detail.

**Lifecycle commands:** CxPP `plugins/cxpp/` provides `cxpp-init`,
`cxpp-status`, `cxpp-update`. CPP provides `/cpp:init`, `/cpp:status`,
`/cpp:update` plus `bootstrap-check`, `install-drift-check`,
`host-surfaces-check|plan|prune`.

**Installed sources.** CxPP resolves helpers from `~/.codex/scripts/`
(`prompt-context`, `validate-prompt`, `worktree-remove`, `secrets-mask`,
`hook-validate-command.sh`, `hook-mask-output.sh`). CPP resolves from
`~/.claude/scripts/` with a documented three-tier fallback
(stable -> `${CLAUDE_PLUGIN_ROOT}` -> checkout). **The resolution contracts
differ**, and #1073's installer work must not assume CPP's tiers apply to a
Codex host.

---

## 5. Security, test and verification protections

| Protection | CxPP | CPP |
|---|---|---|
| Secret scan | `make secret-scan`, `.gitleaks.toml`, `scripts/secrets-mask.sh` | `make secret-scan`, `.gitleaks.toml`, `controls/secret-scan` |
| Dependency audit | `make dep-audit` | `make dep-audit`, `dep-audit-selftest`, `dep-audit-capture`, `.dependency-audit-allow` |
| Python SAST | present (see cxpp#282/#274 for its limits) | **absent** - CPP #962 owns bandit adoption |
| shellcheck | **absent** - cxpp#249: 81 tracked `.sh`, none linted | `make shellcheck`, `controls/shellcheck-gate`; CPP #972 records 175 sub-error findings |
| Negative controls | cxpp#250, cxpp#283 - coverage incomplete | `controls/check-negative-controls`, `check-negative-fixture-preconditions`, ADR 0008 |
| Oscillation control | cxpp#242 - adoption proposed, not done | `make oscillation`, `controls/check-oscillation` |
| Harness / skill-contract lint | `harness_lint.py`, `skill_contract_lint.py`, `skill_contract_baseline.py` | **no analogue** |
| Skill evaluation | `lib/skill_eval`, `make skill-eval-check`, `skill-eval-live` | **no analogue** |
| Release validation | `scripts/release_validate.py`, `make release-validate` | **no analogue** |
| Pin / payload integrity | `codex-skills-pin-check`, `codex-skills-currency-check`, `codex-skills-upstream-report` | `delegated-core-check`, `install-drift-check`, `drift-check` |
| Test suites | 66 test modules | 122 test modules |

**Asymmetry runs in both directions.** CPP has shellcheck and a mature
negative-control battery that CxPP lacks; CxPP has SAST, harness lint, skill
contract lint, skill evaluation and release validation that CPP lacks. A
migration that moves only toward CPP's current shape **loses the second column**.
This is the substance of spec Open Question **Q5** and of cpp#962 (SAST).

---

## 6. Credential and state namespaces

Recorded by **name only** (spec **B1**). No value appears here.

**Codex side.** `CODEX_HOME`; `~/.codex/` (`config`, `history`, `rules/default`,
`scripts/`, `skills/`, `secrets-mask`);
`~/.config/codex-power-pack/secrets/{project_id}.env`;
`~/.config/codex-power-pack/secrets/{project_id}/`;
`~/.config/codex-power-pack/audit.log`.

**Claude side.** `~/.claude/` (`commands/`, `scripts/`, `plugins/`,
`plugins/cache/cpp/`, `plugins/marketplaces/cpp`, `projects/`, `boot-types/`,
`daemon/roster`); `~/.claude-power-pack/`; CPP secrets via AWS Secrets Manager.

**These namespaces do not merge.** A co-installed host keeps both. Consolidating
the source does not relocate a Codex user's credentials or history, and
`install approval` does not authorize touching either.

---

## 7. Configuration, docs and templates

**CxPP config:** `.codex/cicd.yml`, `.codex/cicd_tasks.yml`, `.codex/secrets.yml`,
`.codex/harness-lint-allowlist.txt`, `.codex/friction.jsonl`, `.codex/hooks.json`.
**CxPP docs:** 34 entries under `docs/` including 6 native-wave / Codex-wave
contract documents (`native-codex-wave-contract.md`, `native-wave-delivery.md`,
`native-wave-resilience.md`, `native-wave-transport-proof.md`,
`spec-sync-native-wave-handoff-contract.md`, `cpp-wave-comparison.md`), a
`release-process.md`, 6 plugin-marketplace and lifecycle e2e records, and
`skill-evaluation*.md`.
**CxPP extras:** `extras/sequential-thinking`.
**CxPP extensions:** `extensions/cxpp-issue-sync` (one preview command).
**CxPP templates:** `Makefile.example`, `cicd.yml.example`, `config.toml.example`,
`project-next.json.example`, `project-next.schema.json`, `qa.yml.example`,
`makefiles/`, `workflows/`.
**Shared by both:** `.woodpecker.yml`, `woodpecker/`, `.github/ISSUE_TEMPLATE/`
(4 forms + config), `AGENTS.md` (CxPP) vs `CLAUDE.md` (CPP),
`ISSUE_DRIVEN_DEVELOPMENT.md`, `CHANGELOG.md`.

`project-next.schema.json` and `templates/` are consumer-facing contracts:
relocating them changes what a downstream project resolves. #1069.

---

## 8. Native-wave: shipped foundations vs unfinished support

Spec **US3** requires this split, and requires that **library tests alone are not
accepted as evidence of a working native wave**.

**Shipped foundations** (code present at baseline; presence is not a claim of
end-to-end function):
- `lib/native_wave/` - 14 modules covering identity, claims, cursors, events,
  storage, replay, delivery and a Codex transport.
- `scripts/native-wave-delivery.py`.
- Contract documentation: `docs/native-codex-wave-contract.md`,
  `native-wave-delivery.md`, `native-wave-transport-proof.md`,
  `native-wave-resilience.md`.

**Unfinished end-to-end support** (declared, not demonstrated) - the open issues:
cxpp#189 (epic), #192, #193, #194 (wave epics), #201, #202, #203, #206, #208
(stories), #229 (hardening), #230 (evergreen revalidation).

**What has NOT been demonstrated at baseline:** a complete native CxPP wave with
three independent Codex workers (cxpp#203 open), packaged flow-register/flow-wave
with complete installed dependencies (cxpp#202 open), native session wake and
delivery adapters (cxpp#206 open), and local Kylex delivery with reproducible
evidence (cxpp#208 open).

**Therefore:** the transport proof and the library modules are foundations. They
are **not** a working native wave, and must not be moved or retired on the
strength of a claim that they are. Disposition: spec Open Question **Q1**,
ledger rows for #189-#208.

---

## 8b. Delivery, CI and provenance surfaces

Added on independent review (finding **R6**): all three reviewers observed that
the first inventory treated "capability" as code and skills, while the things
most likely to be lost silently are the guardrails and the delivery machinery -
nobody misses a CI workflow until a release needs one.

| Surface | CxPP | CPP | Note |
|---|---|---|---|
| CI pipeline | `.woodpecker.yml`, `woodpecker/` | `.woodpecker.yml`, `woodpecker/` | Both self-hosted Woodpecker; step graphs differ |
| GitHub Actions | none found at baseline | `.github/` (issue forms only) | Neither repo uses Actions for CI at baseline |
| Issue forms | `.github/ISSUE_TEMPLATE/` (4 + config) | `.github/ISSUE_TEMPLATE/` | Route to the issue contract; a retiring repo's forms stop being reachable |
| Release process | `docs/release-process.md`, `scripts/release_validate.py`, `make release-validate` | no direct analogue | **Q5.** Bears directly on #1074 |
| Publishing credentials / channels | plugin distribution; channel list not enumerable from the repo | marketplace retired (#662) | **UNKNOWN** - see §9. Credentials are named nowhere here and must not be |
| Branch protection | not inspected | `make branch-protection-check|apply|show` | Not inspected on the CxPP side at baseline; recorded as unexamined, not as absent |
| Changelog | `CHANGELOG.md` | `CHANGELOG.md` | Historical record; spec **B6** keeps it reachable |

**Git history is a capability too.** Relocating `project_next` and (per Q1)
`native_wave` by copy loses `git blame` for every line, and with it the
provenance of decisions the ledger's own rows depend on. Whether the move
carries history is **Q8**; it is not a mechanical detail of #1069, and choosing
it late means choosing a copy by default.

**Hook byte-provenance is the sharpest of these.** §4 records that three of five
handlers resolve to `~/.codex/scripts/`. What is NOT yet recorded, anywhere, is
which bytes those installed copies currently hold and whether they match the
repo files of the same name. Until that mapping exists, spec **B2** ("an
already-trusted path is never repointed at different bytes") cannot be verified
- only asserted. Producing it is #1073's first task, and its absence at baseline
is a stated gap rather than a clean finding.

---

## 9. Known and unknown consumers

| Consumer | Status | Evidence |
|---|---|---|
| **CPP itself** | **known** | Vendors `vendor/project_next/**` from CxPP via `lib/vendor.py`. Hard dependency. |
| **CxPP itself** | **known** | Pulls `codex/skills/` from CPP at pin `f64a654f`. Hard dependency, currently stale. |
| **Kyle** (`cooneycw/kyle`) | **known, scope unconfirmed** | CxPP epics #189/#193 target "CxPP waves through Kyle scaffolding" and "Integrate native Codex formations into Kyle". Whether Kyle has a *runtime* dependency on CxPP at baseline is **not established by this inventory**. |
| **Installed Codex hosts** | **UNKNOWN** | Any host with `~/.codex/skills/` or `~/.config/codex-power-pack/` populated from CxPP. Not enumerable from the repositories. Count unknown. |
| **Plugin-marketplace installs** | **UNKNOWN** | CxPP ships 16 plugin families; installs are not tracked in-repo. |
| **Downstream projects using templates** | **UNKNOWN** | `project-next.schema.json` and `templates/` are consumer-facing; adopters are not enumerable from the repositories. |

**Three of six are `unknown`, and that is the finding.** An inventory that listed
only the three knowns would read as complete. Per spec **US1**, these are
recorded as unknown with the reason they could not be confirmed; resolving them
is #1076's archive-readiness work ("every known active consumer is migrated or
explicitly retired"), and #1076 cannot discharge that criterion while these rows
remain unknown.

---

## 10. Baseline counts, for staleness detection

| Metric | Value @ baseline |
|---|---|
| CxPP open issues | 40 |
| CxPP open PRs | 1 (cxpp#239) |
| CPP open issues | 34 |
| CxPP Nit Store (cxpp#227) comments | 29 |
| CPP Nit Store (cpp#864) comments | 165 |
| CxPP native skills | 85 |
| CxPP plugin skills | 74 (16 families) |
| CPP generated Codex skills | 75 |
| CxPP test modules | 66 |
| CPP test modules | 122 |
| CxPP scripts | 19 |
| CPP scripts | 75 |

All measured at CPP `5ceb966a` / CxPP `681ea26b` on 2026-09-19.
