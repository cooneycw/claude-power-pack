# Flow run record - issue #1946

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=71a98a3ad2c64c7a8b45956348ab38e7 -->
## Run 1

- Run-id:            71a98a3ad2c64c7a8b45956348ab38e7
- Run-start:         1ee2e709b21bd01af9d1df37240c1ed95e47c9b1
- Issue:             #1946
- Base SHA:          1ee2e709b21bd01af9d1df37240c1ed95e47c9b1
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run140:ch-orch mailbox43974, split of proposed plan43973
- Recorded at:       2026-11-28T04:46:16.897149+00:00

### Section A - What this issue wants
The launch-facing pages currently promise a kind of security review and a local encrypted store that CPP does not supply. Readers need to know which deterministic checks CPP runs, which review belongs to Claude Code, and when local secret values remain plaintext. This first partial PR corrects claims only; runtime checkout resolution is a separate follow-up.

### Section B evidence
Issue created2026-11-27T15:55:23Z. Main1ee2e709 still contains the named claims. No post-filing commits touch the named docs/security/creds paths. Inspected merged PRs1975,1974,1971,1969,1968,1966,1962,1954; none addresses these claims. Historical issues98/87 are closed, not superseding1946. No sibling unpushed work touches these paths.
Code evidence: lib/security/orchestrator.py34-99 for quick/full/deep composition; lib/security/README.md3-29 for semantic external review boundary; providers/__init__.py exports only env/dotenv/AWS; dotenv.py76-99 writes plaintext/chmod0600; project.py102-140 resolves nested XDG config path/chmod0700; lib/creds/__init__.py84-102 selects available AWS before env.

### Section C - the approved plan
1. `README.md` - correct native/full vulnerability promises, name deterministic checks and external semantic review, state local plaintext storage and qualify no-secrets-on-disk wording.
2. `lib/security/README.md` - clarify built-in deterministic checks and gitleaks history scanning in deep mode; no entry-point/path changes.
3. `.claude/commands/secrets/help.md` - replace nonexistent encrypted tier with actual env-file/dotenv-global/optional AWS capabilities and truthful local at-rest path/permissions; keep runtime command/path lines unchanged.
4. `.claude/commands/secrets/get.md` - correct auto provider-order sentence to AWS when available, otherwise env; keep runtime invocation unchanged.
5. `tests/test_security_secrets_docs.py` - exercise committed false/true claim contracts against actual docs and generated Codex output; characterize unchanged provider storage/selection in owned fixtures, no real credentials/AWS calls.
6. `tests/fixtures/security-secrets-docs/claims.json` - committed required true/forbidden false claims plus known-bad snippets; empty/deleted claims cannot pass.
7. `controls/antigravity-skill-build/codex-baseline.json` - ONLY two new secrets-help/get rows after measured exact values and explicit relayed OWNER approval; historical members/current rows unchanged, pi baseline untouched.
Scope: seven source/fixture paths plus normal flow records, roughly150-250 lines. PR1 is partial Refs1946; runtime/path-locator work is PR2 and must not be edited until PR1 is up.
Risks: implying encryption from masking/permissions, confusing built-in deterministic checks with semantic review, generated member growth or unintended runtime edits. Check false and true cases, actual provider behavior, exact runtime-line identity and full405-member inventory. Stop on unexpected generated members or absent owner approval for new rows. No material concern found with this split.

Lanes: none - documentation claims only; runtime behavior and path locators are unchanged in this PR. Owned fixtures characterize existing behavior, not a new runtime lane.
Reader: README and lib/security reference users - actual changed text checked against explicit claim contracts and source-backed behavior.
Reader: Claude secrets help/get and generated Codex secrets-help/get - tests feed the actual source pages and actual generated pages the same claim checks; no stand-in reader.
Reader: security/secrets command execution - unchanged in PR1; alternate checkout invocation tests belong to PR2 and are not claimed here.
