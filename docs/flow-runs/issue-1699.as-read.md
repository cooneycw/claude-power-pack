<!-- flow-run n=1 id=6e86809a9f7042d0bdc952b193c1778d -->
## Run 1 - issue #1699 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1699
- Read at:      2026-11-12T08:59:33Z
- updatedAt:    2026-11-11T22:55:46Z   (context only - moves on comments and labels)
- Body digest:  70ca5fe58f9a5ca85bc0baf55c0cecfac5b98e754865444bdef2363bed47c216   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4313 of 4313 (cap 16384)

### Body as read
## What
The closing issue of the series filed 2026-11-11. When every issue in the series is closed, cut the release that carries it and set the version. Owner's expectation (2026-11-11, verbatim): "the lanes change should reset us to 11, i think." So the default is **11.0.0** (current: 10.2.0, tag `v10.2.0`).

This issue does no feature work. It is the one place the version question is answered, so that none of the series' PRs bumps the version on its own.

## The series (as filed; the gate is "all closed", including any added later under #1673)
- #1673 epic: simplification wave for flow and cicd, Nit Store rollover
- #1669 flow command documents on a word budget
- #1689 scrub the host account name and home paths
- #1690 aggregate Nit Store #864, close it, open the successor
- #1691 simplify the wave machinery
- #1692 simplify the gate path
- #1693 simplify the merge-and-cleanup tail
- #1695 lanes exercised: name where each acceptance item was demonstrated
- #1696 `/lane:create`, `/lane:update`, lane file from `/project:init`
- #1697 corrective processes

## Do
1. Confirm every issue above (and anything added to the epic since) is closed. Do not start before that; an early cut means a second release for the stragglers.
2. Decide the version from what actually merged, not from this title. Major (11.0.0) if a consumer following 10.2.0 must change something: a renamed or removed helper, a changed exit code or output line a script parses, a new required file (the lane file from #1695/#1696 is the expected case), a changed command contract. List each such break; that list is the changelog's "Breaking" section. If the list is honestly empty, say so and take it to the owner before choosing 10.3.0 over the expected 11.0.0.
3. Bump `pyproject.toml` and every other place the version is recorded (find them; do not trust a remembered list), changelog, README; tag. Use the standing release checkpoint #1278 for the procedure.
4. **Update this repository's documentation** (owner, 2026-11-11: "we also need to update our documentation"). The series renames, removes and simplifies commands and helpers and adds the lane file, so the docs are wrong in more places than the changelog. Sweep, do not spot-fix: README, `docs/`, the command documents and `/…:help` texts, `scripts.md`, the best-practices and install/`/cpp:init` texts, and any example that shows a helper's output or exit code. For each break in step 2, name the documents that mentioned the old shape and show they now say the new one. Red case: a search for each removed or renamed name returns nothing in tracked docs (and returns hits on the commit before the sweep).
5. Name the downstream work, as issues in the consumers, not as edits there: Kyle pins a CPP adaptation commit (`core/cpp_adapt_pin.json`) and bundles CPP in its session image, so a major release needs a Kyle re-pin issue that lists the breaks from step 2; codex-power-pack and skillc likewise if they consume a changed surface.
6. **Place a note for aws-learn** (owner, 2026-11-11: "place a note for aws-learn to update its documentation"). `cooneycw/aws-learn` (the learn-agentic-coding.com workstations) documents and installs this pack for learners. File an issue there, not an edit, that states the released version, the breaks from step 2 in learner terms (which commands changed name or behaviour, the new lane file and how a learner gets one), and which of its pages or workstation setup steps are affected as far as can be seen from its tracked files. Link it here.

## Acceptance
- All series issues closed before the tag.
- The version on main, the tag, the changelog heading and any reported version (`/cpp:status` or equivalent) agree. Red case: the agreement check must fail when one of them is left at 10.2.0; run it that way once and say so.
- The changelog's Breaking section matches step 2's list, or states that there are none and that the owner chose the number.
- The documentation sweep of step 4 is in the release PR or a PR merged before the tag, with its red case stated.
- Downstream issues exist and are linked here: the Kyle re-pin, and the aws-learn documentation note.

## Not in scope
Any change to the series' content; any consumer edit.

Refs #1673, #1278. Filed by the kyle-cli orchestrator session at the owner's request.


<!-- end of body -->
