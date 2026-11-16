<!-- flow-run n=1 id=385e634fa8ad451bb4264aa148ab4c39 -->
## Run 1 - issue #1851 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1851
- Read at:      2026-11-16T02:18:48Z
- updatedAt:    2026-11-15T20:11:07Z   (context only - moves on comments and labels)
- Body digest:  d5704283314a9115f21f16009e1cbba02dd88d0c40ebad12c4dc16c1171d0304   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1895 of 1895 (cap 16384)

### Body as read
Tier: 1

## Outcome

A prose edit to a command document no longer fails `make driver-parity-check` just because it moved the lines below it.

`docs/agents/driver-parity.json` holds 18 citations, each a file, a line number and the text expected on that line (`scripts/check-driver-parity.py:562-574`). On #1846, adding one sentence to `.claude/commands/flow/auto.md` and one to `.claude/commands/codex/auto.md` shifted later lines and the gate failed twice with `stale citation: .claude/commands/codex/auto.md:1160` and `...flow/auto.md:1048`. The cited text had not changed. The edit had to be reflowed to keep each file's line count.

Combined with the word budget, a command document is frozen in two dimensions: an edit must be word-neutral and line-neutral.

Source: observed while running `/flow:auto` on #1846 (2026-11-15), measured on main `f1253b45`. Part of the simplification asked for in [discussion #1830](https://github.com/cooneycw/claude-power-pack/discussions/1830). Related: #1669 (word budgets).

## Constraints

- **A citation must still fail when its text is gone or changed.** That is what it is for.
- **A citation must stay unambiguous.** If the expected text occurs more than once in the file, the check says so; it does not pick one.

## Acceptance

- [ ] A citation resolves by its text (unique in the file), not by a fixed line number.
- [ ] Red case: removing the cited text fails. Red case: duplicating it fails as ambiguous. Green case: inserting a line above it passes, and that same case is run against the pre-fix checker and fails there.
- [ ] `controls/driver-parity` carries those cases.

A locator correction only: no stable-ID scheme, automatic citation rewriting or normalisation.

## Proposed approach

Keep `line` as an optional hint used only in the failure message.

## Assumptions

- All 18 cited texts are unique in their files today. Not checked.



<!-- end of body -->
