<!-- flow-run n=1 id=436421200a034ac5ab42a4fe1c242621 -->
## Run 1 - issue #1888 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1888
- Read at:      2026-11-25T21:31:16Z
- updatedAt:    2026-11-25T16:45:44Z   (context only - moves on comments and labels)
- Body digest:  c2facc36d23f04d8a5946660249f583368c00282d61bea01bf044e792460ecf4   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2183 of 2183 (cap 16384)

### Body as read


Parked: scaffold pending the ADR 0014 / plan merge; scope may change
Tier: 2

Parent: #1876

Planning scope: this Codex group authors CPP code and issues; AGY is test-only. One AGY PR in flight, PR CI only, Kyle series-27 CI priority. Owner accepts and merges ADR0014 before code merges; Kyle stays on CPP v13.0.0.

Owner rulings remain open: measured packaging Option A/B, initial skill scope, and Qwen/OpenCode/other managed-harness coverage. Do not treat proposals as rulings.

Outcome: build the owner-selected skill set from CPP canonical sources into
self-contained AGY packages, without changing Codex consumers.

Acceptance:
- Add the thin antigravity-skill-sync.py surface and Makefile build/check
  targets; generated trees remain ignored and deterministic.
- Bundle the external docs/skills guides referenced by published topic skills
  into references/ and rewrite their links. Preserve any required scripts and
  resources, respecting the measured packaging contract.
- Feed the real build output to an AGY skill invocation in an unrelated repo;
  prove it reads the intended bundled guide instead of a same-named file in
  that repo. Missing bundled content must be detected.
- Apply measured frontmatter/ownership requirements; under loose-copy Option B
  inject CPP metadata.source. Enforce the expected package set, not a zero-
  validated green. No edits to codex-skill-sync.py or its interfaces.
- If topic-only scope is chosen, name the follow-up item for command-derived
  skills and actual AGY cpp-update invocation before workflow parity claims.

Dependencies: 1.1 and recorded scope/packaging rulings; ADR merge prerequisite
for code merge, one-PR-at-a-time scheduling.
Controls: fresh build passes; changed output, removed package and broken bundled
reference fail; unreadable source is unknown. Any build parity gate ships its
committed cases. Prove regression tests red on pre-fix code where applicable.
Readers/lanes: installer consumes the real bundle; AGY consumes the installed
output. Root/external cwd and checkout/worktree paths need explicit coverage;
existing Codex output remains unchanged, not assumed newly tested.

Dependency links: #1887.


<!-- end of body -->
