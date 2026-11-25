<!-- flow-run n=1 id=491e55fba4da40ac91d983677dceecde -->
## Run 1 - issue #1896 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1896
- Read at:      2026-11-25T19:01:45Z
- updatedAt:    2026-11-25T16:43:06Z   (context only - moves on comments and labels)
- Body digest:  45beac9ac3a5d4efe83dfe1c2ad313daa79695cf4ca73a4308d5913cdb921b52   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 6595 of 6595 (cap 16384)

### Body as read
Tier: 2

Parent: #1876

Parked: implementation follows AGY Wave 1 and the pi Part-1 plan landing; pi is
in the later updater cohort. No CPP PR push or CI until the owner lifts the current downstream release freeze.

Outcome: install self-contained copies of canonical CPP topic skills into
`<agent>/skills/<slug>/` and verify bundled-reference fidelity, expected
membership, discovery and the owner-approved security boundaries.

Authoritative design: pi Part-1 plan rev 6.1, Section 2 (copier/validation),
Section 3 (six boundaries), Section 4 P1-A. The docs-only PR/link awaits lifting of the
downstream release freeze and must be attached before implementation. This issue implements no
pi runtime, credential service or workflow command generation.

Acceptance:

- Add the separate thin `scripts/pi-skill-sync.py` with the planned check,
  write, install, verify-installed and output-root interfaces plus Makefile
  targets. Keep `codex-skill-sync.py` unchanged. Build ignored `pi/skills/`
  output from canonical topics and guides; copy guides to `references/`, rewrite
  links, inject CPP `metadata.source`, and use managed copies, never symlinks.
- Allow only the planned regular 0644 UTF-8 Markdown package files and valid
  slugs. Refuse symlinks, traversal, executable/script files and package
  manifests; copied skills must not register/replace trusted tools.
- Install only within the positively selected skills root plus its advisory
  lock. Refuse foreign slug collisions without explicit adoption and a
  documented backup destination inside the approved writable scope. Preserve
  unmarked neighbors. Do not probe authentication files to classify roots.
- `--output-root` must resolve outside the entire agent directory and outside
  pi's effective session-history directory AND every non-empty candidate.
  Resolve CLI `--session-dir`, then `$PI_CODING_AGENT_SESSION_DIR`, then merged
  global `<agent>/settings.json` / project `<cwd>/.pi/settings.json` `sessionDir`
  (project wins), then default `<agent>/sessions`. Read settings read-only,
  without locking; unreadable/malformed inputs exit 1. Normalize `~`, `file:`
  URLs and cwd-relative paths before safe realpath resolution; unsafe or
  unresolved paths fail closed, including non-default external history. Refuse all
  agent descendants (extensions, settings, tools, skills and every B3 trusted
  root), direct/nested history paths and traversal/symlink aliases before any
  forbidden-root touch. Only `--install` targets canonical agent skills. Retain
  the legal isolated build-root positive comparison. Named controls are
  `output_root_under_trusted_config` and `output_root_under_sessions`.
- Add bundled-topic parity to `skills-check.py` and expected-package membership
  checks in the pi verifier/install-drift path. Feed actual fresh build output
  into installed verification. Every expected package must validate; zero
  validated is never clean, and unreadable inputs do not pass.
- In a hermetic fixture home and agent directory, offline/no-session RPC
  discovery must expose each copied `skill:<slug>` with the expected skill
  source/baseDir and no warnings; the built-in tool set stays intact. No real
  authentication/configuration or live provider session is used by automation.
- Add HOST-SURFACE disclosures for the skills root and advisory lock. Keep
  runtime/container boundary enforcement explicitly deferred and unclaimed.

Six boundaries and named controls (fixture-only inputs; demonstrate known-bad
cases fail, including regression cases on pre-fix behavior where applicable):

| Boundary | Part-1 named control and required opposite case |
|---|---|
| B1: never inspect pi authentication files | `pi_auth_open_attempt`: audit open/stat calls; a seeded auth-file stat is detected, while valid operations make no auth probe. No real auth file is read, copied or statted. |
| B2: auth inaccessible to sessions | `topic_skill_auth_helper_rejected`: a seeded helper/auth-link topic is refused without credential access. Actual trusted-service isolation remains runtime-deferred; `session_can_obtain_bearer` and `bearer_in_logs` are named future controls, not Part-1 proof. |
| B3: trusted settings/tools/extensions unwritable | `session_overwrites_trusted_config` catches transient outside-skills create-then-unlink even when the final snapshot is clean. `output_root_under_trusted_config` refuses direct `<agent>/extensions/skills` and alias/symlink spellings, plus settings/tools/other B3 trusted roots, with zero forbidden-root touches; a legal external build root is the positive case. |
| B4: writable session history separate from trusted config | `output_root_under_sessions` plus `writable_session_dir_isolated_from_skill_root` refuse the effective directory and every non-empty CLI/env/global-settings/project-settings/default candidate in the specified precedence; include a red case per source, conflicting/overridden sources and external non-default `<history>/skills`, nested and symlink aliases, with zero touches. Basename-only or agent-only guards that admit a seeded case must fail; legal isolated output passes. |
| B5: no tool replacement or path escape | `skill_path_escape` and `foreign_package_collision`: traversal, symlink, manifest or executable payloads fail; a skill called bash remains only a skill and cannot replace the tool; foreign collision is refused and a neighbor survives. |
| B6: boundary tests and fidelity distinguish bad state | `missing_expected_skill_or_marker` and `modified_bundled_reference`: missing slug/marker and a one-byte guide change fail, while actual fresh installed output passes. |

No row here claims runtime credential isolation; that is ADR 0016 scope.

Readers: pi loads the real installed Markdown; skills-check/install-drift read
the real builder's output and install; syscall audit observes actual child
operations, not only before/after snapshots. The implementation plan answers
all repository lane rows; offline fixture results do not claim live runtime,
provider or container coverage.

Deferred until Part 1 is validated: shared cpp-update enrollment, pi capability
receipt rows, command/workflow generation, `/copilot:*`, counter-model receipt
schema/adapter work, MCP, rules and pi-in-Kyle. Copilot concurrency/terms remain
an owner-acknowledged assumption; configurable limits/budgets and alternative
providers are preserved future features, not a Part-1 blocker.

Sequencing links: AGY Wave 1 #1887, #1888 and #1889 must complete first. The pi Part-1 documentation PR is local preparation only until release clearance.


<!-- end of body -->
