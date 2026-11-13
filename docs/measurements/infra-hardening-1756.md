# Infrastructure workflow hardening (#1756)

Tier: 2. Scope and limits approved by the wave orchestrator in messages 23935
and 23937 on 2026-11-13. This records the measurement and reader boundaries;
the issue remains the acceptance contract.

## Measurement and decisions

On main `87239afd`, the existing Actions hardening file passed 149 tests. Its
infra cases checked shared action refs only. Applying the existing permissions,
timeout and checkout-credential assertions to actual infra output failed each
property. No infra image-digest or IaC-command assertion existed.

The approved policy grants GitHub contents-read only, disables checkout token
persistence, and bounds plan/apply at 30/120 minutes. Apply gets a loose deadline
because interruption can leave a state lock and partly-created cloud resources.
Cloud authentication remains caller setup. Woodpecker's timeout is a project
setting, explicitly stated in generated YAML rather than represented by an
unverified field.

Both providers use the existing GitHub init/plan/apply commands through one helper.
Only Azure location expression syntax differs: GitHub variables versus an escaped,
required Woodpecker runtime environment value. Unsupported config/API tools fail
before file writes, including the previously silent `none`/`cloudformation`
fallbacks. The scaffold generator does not call the pipeline generator.

## Lanes for this change and readers

Reader search: references to `generate_infra_pipeline` and both private emitters
found the CLI preview/write/JSON paths, provider dispatch, package re-export and
tests. This found known readers, rather than inferring absence from an empty scan.
`checks.py` and `doctor.py` read committed pipeline shapes/contexts; they do not
compare bytes with current generation. External consumer repositories are not
enumerated by this search and must regenerate manually.

| Lane or reader | Answer | Evidence or boundary |
| --- | --- | --- |
| Checkout: main / linked worktree | not relevant | Emitters use supplied config/output paths; no checkout or Git metadata discovery changes. CLI cases use temporary project paths. |
| Harness: Claude / Codex | not covered for live installs | Canonical command docs updated; `make codex-skills` builds the real mirror, which was read. No host install performed. |
| Driver: flow / delegated | not relevant | Driver selection is unchanged; tests invoke the emitter and actual CLI handler. |
| Coordination: without / with Kyle | not relevant | No coordinator call or authority decision is added to generation. |
| CI provider: GitHub / Woodpecker | will test | `test_generated_infra_hardening` exercises real output for all three tools and tiers. Live CI services are not exercised locally. |
| CI provider: none recorded | reader unchanged | Existing provider selection still refuses an unrecorded provider before generation. |
| Project state: adopted / not adopted | will test / unchanged | CLI tests read actual configs and prove rejected values write nothing; existing repositories are not rewritten automatically. No regeneration notice is added. |
| Reader: local YAML hardening assertions | tested against real output | `test_generated_infra_hardening` parses emitter output; one-field bad fixtures and repairs prove each property can fail and pass. |
| Reader: shell running emitted commands | tested against real output | `test_emitted_infra_commands_execute_the_selected_tool` runs the actual command strings in Bash with owned executable stubs. Bicep location is checked set and unset. |
| Reader: real IaC/cloud CLIs | not covered | Stubs record selected argv; no cloud credentials, real plan/apply or provider API is exercised. No claim of successful cloud deployment. |
| Reader: CLI errors and file writes | tested against real output | `test_cli_rejects_unsupported_infra_tool_without_writing` goes through `main`/`cmd_infra_pipeline` with actual config and compares the file population before/after. |
| Reader: CLI preview text | reader unchanged for supported tools | The handler prints generated strings without parsing the changed fields. Unsupported values now take the tested error/no-write path in preview mode. |
| Reader: CLI JSON file inventory | reader unchanged for supported tools | JSON contains provider names and generated path names, which are unchanged; it does not include workflow content. Unsupported values take the tested error/no-write path in JSON mode. |
| Reader: required-check derivation | tested against real output | Existing `test_cicd_required_checks.py` generates real infra files and verifies the path-filtered population boundary. |
| Reader: doctor | reader unchanged | `collect` reads committed file inventory and derived contexts; paths, event/path filters and job/step names are unchanged. It does not inspect the altered permission, timeout, credential, image or command fields. |
| Reader: GitHub/Woodpecker service parser | not covered | Local YAML parsing and execution controls are evidence about generated structure/commands, not an actual provider run. |

GitHub expression substitution is simulated by inserting the raw value. Its
existing unquoted location expression is preserved: a committed control uses a
spaced value to prove the harness exposes argument splitting. Normal GitHub
execution uses a valid location; Woodpecker's quoted runtime value is additionally
tested with a space. No new quoting is attributed to GitHub substitution.

The first regression run with main's infrastructure module (new image constants
retained for imports) failed 61 cases and passed 34. After the initial fix, 276
focused hardening/required-check tests passed. Review then added CLI preview/JSON
rejection coverage and corrected the GitHub substitution harness; the final
counts and full-gate evidence are recorded in the PR.

## Image provenance

Direct registry manifest GETs on 2026-11-13 requested OCI image indexes and Docker
manifest lists. Every response was a Docker manifest list; its header digest
matched SHA256 of the raw body. Each exact release resolved to the same index as
`latest` at that measurement time. The reference tag labels the release; the
digest selects the immutable index.

| Registry and repository | Release | Index SHA256 | Linux targets |
| --- | --- | --- | --- |
| registry-1.docker.io/hashicorp/terraform | 1.17.2 | `6e9c1e647c31a960dc9b59e13272f9111d90010c10b717f77ffb324767660475` | 386, amd64, arm64, arm/v6, s390x |
| registry-1.docker.io/pulumi/pulumi-python | 3.276.0 | `addffc4b7f1af47ccad1475ae0ab1d10d939748c26e2389660072759130b3bce` | amd64, arm64 |
| mcr.microsoft.com/azure-cli | 2.92.0 | `a4e2660b4099b76f02001a9316a0eb0dc56e330b5f7d1d1312c932200645bf26` | amd64, arm64 |

Requests used `/v2/<repository>/manifests/<release>` and `/manifests/latest`.
Media type: `application/vnd.docker.distribution.manifest.list.v2+json`.
Pins deliberately stop following future tool releases until a reviewed update.
