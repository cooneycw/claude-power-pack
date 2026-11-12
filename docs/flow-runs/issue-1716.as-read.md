<!-- flow-run n=1 id=a92b39b9fc1248899263c18f46599057 -->
## Run 1 - issue #1716 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1716
- Read at:      2026-11-12T04:11:48Z
- updatedAt:    2026-11-11T23:07:44Z   (context only - moves on comments and labels)
- Body digest:  6757e6adae0791e30d6c1071027dcfdc2005313bf934a3dd288357100d7b0396   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4498 of 4498 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 9 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
`/cpp:init` and its two checkers. The Trusted preset's deny rule `Bash(dd if=:*)` does not match `dd if=/dev/x`, so the protection it advertises is absent. The desk-pool tier writes `.claude/playwright-pool.json` into the invoking repository, and the cicd tier does not check the chosen folder against the defer set. `check-cpp-init-promises.py` resolves a promise with `Path.exists()` without checking the file ships. The capability step asks an eight-option question where the tool allows four, and Tier wording survives from before the redesign.

## Findings (9)
- [seq 623](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6469697751), 2026-10-28, medium (estimated): cpp/init.md:283 Trusted deny Bash(dd if=:*) needs a space after if= so misses dd if=/dev/x. Status at origin/main `f63dc946`: init.md still has Bash(dd if=:*) at lines 334 and 411 (Trusted and YOLO profiles); shape needs a space after if=.
- [seq 626](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6473343925), 2026-10-28, medium (estimated): check-cpp-init-promises.py resolves supplied promises with Path.exists() without checking they ship; untracked local .venv passed the gate. Status at origin/main `f63dc946`: Lines ~97-119 still use candidate.exists()/glob with no tracked-file check; script unchanged since the comment.
- [seq 635](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6523113398), 2026-10-30, low (stated): /cpp:init Tier 3 desk pool writes .claude/playwright-pool.json into the invoking repository. Status at origin/main `f63dc946`: init.md lines 1885-1911 still create project .claude/playwright-pool.json; #1613 only narrowed the ADR claim and sent this to the nit store.
- [seq 674](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6724780853), 2026-11-08, low (estimated): check-cpp-init-promises.py false positive when a generated-path sentence wraps so the path starts a new line. Status at origin/main `f63dc946`: Script has no commits since the comment; per-line classification (lines ~107, 196-240) unchanged.
- [seq 678](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6726366890), 2026-11-08, low (estimated): check-cpp-host-writes.py:129 flags embedded Python writes to project paths as INLINE-HOST-WRITE. Status at origin/main `f63dc946`: embedded-python pattern at line ~129 still classifies by write call only, no destination check; no commits since.
- [seq 700](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6732618268), 2026-11-09, low (estimated): cpp:init step 8b registers Codex MCP even without codex capability; preset 5 offers it twice (5d and 8b). Status at origin/main `f63dc946`: init.md still has both 5d (L2109) and 8b (L2730) offers.
- [seq 701](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6732618435), 2026-11-09, low (estimated): cpp:init Step 3 asks 8-option capability multi-select though AskUserQuestion allows 4 options. Status at origin/main `f63dc946`: init.md:182 still lists eight capabilities in one multi-select question. 4-option limit taken from comment, not re-verified.
- [seq 702](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6732618632), 2026-11-09, low (estimated): Leftover Tier N wording in cpp/init.md after capability redesign; PROFILE_NAME not checked against scripts selection. Status at origin/main `f63dc946`: Tier 5/6/7 banners remain (L725,750,780). PROFILE_NAME half is fixed: init.md:224 records not-selected unless scripts planned.
- [seq 725](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6806805856), 2026-11-11, low (stated): cpp:init cicd tier does not check chosen projects folder against defer set or substrate surfaces before writing cpp-host.json. Status at origin/main `f63dc946`: init.md has no CPP_DEFER_SURFACES check; only cpp-host-write.sh seam consults it.

## Acceptance
- The deny rule is shown to match the command it names, by a test; the remaining items are fixed or declined here.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

Parent: #1690 (child of #1673)


<!-- end of body -->
