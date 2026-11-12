# Flow run record - issue #1712

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=bad17c9042764f0f9420b54594fba851 -->
## Run 1

- Run-id:            bad17c9042764f0f9420b54594fba851
- Run-start:         3e52bf6d67ac80607ccb82bd5f29ecaf149e032f
- Issue:             #1712
- Base SHA:          3e52bf6d67ac80607ccb82bd5f29ecaf149e032f
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 64: "GATE: GO-WITH-CONDITIONS #1712 ... PR ONE: GO. PR TWO: its design as states comes to me before any code"
- Recorded at:       2026-11-12T05:45:00Z

### Section B evidence
- commits on these paths since 2026-11-11T23:07:39Z: ca918973, 3eaf643d, 545267b9 (#1692), a88aafdd (#1719), e2c0d037 (#1697 Part 1); none delivers a row
- merged or open PRs delivering a row: none; duplicates: none
- all thirteen rows re-checked read-only at 3e52bf6d and still true
- neither kyle nor skillc carries a generated pipeline or Makefile (no generator header, no .github/workflows, no .claude/cpp-install.json); nothing tells an existing consumer to regenerate (doctor-ci compares inventory and check names, never content); Makefile scaffolds are one-shot
- `deploy` is a recommended target, never required (lib/cicd/config.py:99-101, lib/cicd/models.py:130-137); /flow:auto Step 9 tests `grep -q "^deploy:" Makefile`; no test builds a scaffold and asserts a deploy target

### Scope of this run
PR ONE of two: seq 643, 644, 684, 685, 695, 721 and the 686 pointer. It leaves the issue open. PR TWO (seq 699 and 698, plus this repository's own secret-scan lines) is a second run whose design goes to the orchestrator as states before any code.

### Rulings and conditions attached to the approval
- seq 688 and 697 are their own issues (#1754, #1755); the infra least-privilege gaps are #1756; seq 694 and 704 are Nit Store comments; seq 686 is declined with the documented reason.
1. seq 643: check first whether anything requires a deploy target, say which form is built; a scaffold must not be able to print success for a deploy that did nothing, asserted by running the generated Makefile. Form built: the deploy block commented out.
2. seq 644: the logged status is the deploy's on both paths; tested by making the deploy fail and reading the log line.
3. seq 695: infra workflows join the hardening samples.
4. seq 685: only if every message is authored; otherwise decline with the reason.
5. seq 721: check nothing parses comment positions before moving them.
6. deploy.md within its budget; templates are fixes only; the changelog says existing Makefiles keep a do-nothing deploy target until their owner edits it.
7. Exact lane names; full suite before the first gate; two passes, ask before a third.

### Section C - the approved plan
1. `templates/makefiles/python-uv.mk` - the deploy block commented out with instructions
2. `templates/makefiles/python-pip.mk` - the same
3. `templates/makefiles/django-uv.mk` - the same
4. `templates/makefiles/go.mk` - the same
5. `templates/makefiles/node-npm.mk` - the same
6. `templates/makefiles/node-yarn.mk` - the same
7. `templates/makefiles/powershell.mk` - the same
8. `templates/makefiles/multi.mk` - the same
9. `templates/makefiles/rust.mk` - the same
10. `templates/Makefile.example` - the same, for deploy and deploy-staging
11. `lib/cicd/makefile.py` - the inline generator emits the commented block
12. `.claude/commands/flow/deploy.md` - the deploy's own status captured on both paths and logged
13. `lib/cicd/infrastructure.py` - the pinned checkout constant at both sites
14. `lib/cicd/doctor.py` - the derive reason carried, if authored
15. `.woodpecker.yml` - two misplaced comment blocks moved
16. `docs/agents/generated-ci-enrolment.md` - the infra exclusion recorded in place, link repointed
17. `tests/test_cicd_makefile.py` - a generated Makefile has no live deploy target; running it cannot print a successful deploy
18. `tests/test_cicd_doctor.py` - the explicit-False lane case and the derive reason
19. `tests/test_actions_hardening.py` - infra workflows in the samples, checkout pinned
20. `tests/test_flow_deploy_log.py` - the log line carries the deploy's status on both paths
21. `CHANGELOG.md` - entry
Scope: 21 files, about 300 lines.
Risks: a reader not yet found may expect a scaffolded deploy target; existing consumers get none of this without a hand edit or regeneration.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | not applicable: generators and documents with no path-dependent behaviour |
| Harness | not covered: no Codex-driven deploy is run; the generated flow-deploy skill is rebuilt by the existing mirror tests |
| Driver | not applicable |
| Coordination | not covered: no Kyle run; kyle and skillc carry no generated file |
| CI provider | will test: Woodpecker and GitHub Actions generator output for the infra checkout pin |
| Project state | will test: a project with a freshly generated Makefile and one with a real deploy target |
| Reader: /flow:auto Step 9 and /flow:deploy, which read whether a deploy target exists and the deploy log's status column | will test: the document's own target test and log line run against a real generated Makefile |
| Reader: a consumer repository that already generated its files | not covered: nothing reaches it; stated in the changelog |

<!-- flow-run n=2 id=575e90c8d6da466ea1c65ccc418b6fce -->
## Run 2

- Run-id:            575e90c8d6da466ea1c65ccc418b6fce
- Run-start:         9e3bd1f8d5a6f65ab628f583960b2c121733b075
- Issue:             #1712
- Base SHA:          9e3bd1f8d5a6f65ab628f583960b2c121733b075
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 75: "RATIFY: the smaller option for #1712, part 1 only. No base-ref mechanism. No print-on-touch tripwire."
- Recorded at:       2026-11-12T07:58:00Z

### Section B evidence
- PR ONE of this issue merged as #1772 (9e3bd1f8); it left seq 698 and 699 for this run
- commits on docs/skills/woodpecker-ci.md or the generated secret-scan step since PR ONE: none
- measured before this plan, on the pinned gitleaks v8.30.1 in scratch repositories with a red baseline before each case: the change under scan can excuse its own finding by three channels (an in-tree config with no --config; a .gitleaksignore, even untracked, which no flag switches off; an inline gitleaks:allow), and on a same-repository pull request the pipeline file is also the change's own
- the design "config from the base ref" was written as states and does not hold; the orchestrator amends the issue's acceptance: not achievable in the generated step, the scan says what it is and is not, and the docs name the control that does the job

### Scope of this run
PR TWO of two, documentation only: seq 698 and seq 699. It closes the issue. No code, so no control and no census row.

### Section C - the approved plan
1. `docs/skills/woodpecker-ci.md` - what the generated secret scan is and is not, the four paths whose review is the control, the adoption path for a repository with findings already in history, and the same statement for this repository's own scan lines
2. `docs/measurements/gitleaks-self-allowlist-2026-11.md` - the dated measurement: binary version, the three channels with baseline-red-then-case results, the blind first attempt named as such, and why a mechanism was not built
3. `CHANGELOG.md` - entry
Scope: 3 files, about 150 lines of prose.
Risks: a statement about gitleaks that was not measured; each claim in the docs is one the measurement note records, and what was not measured is listed there.

Lanes: none - documentation only; no behaviour changes in any lane, and the generated step and this repository's own scan lines are not edited
