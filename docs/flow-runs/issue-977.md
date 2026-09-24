# Flow run record - issue #977

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #977
- Base SHA:          47db657a09caba31453368df09b3696194265f74
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cooneycw (interactive session user, "approved")
- Recorded at:       2026-09-24T11:20:00Z

## Section B evidence
Commits touching lib/cicd/{outcomes,runner,steps,manifest}.py since 2026-09-15:
a8a7402 (#939), 1fb0589 (#1027), 78493c9, e7c8708, 529d470, 95d6d95, be64279,
6040bc1, 9162b8e, 790d97c, e12b8e7 - none touch the UNKNOWN branch's cause
handling (runner.py still carries the "flagged as a residual" comment).
Merged PRs referencing #977: none other than #1137 (docs sweep, "none").
Duplicate/superseding issues: none. #864 routed a related negative-controls
finding (tool-absent vs crash) here; out of scope, different instrument.

## Section C - the approved plan
1. `lib/cicd/outcomes.py` - add classify_unparsed(text): recognise a supported runner's signature (pytest session header/collected, jest Test Suites:/PASS|FAIL path, unittest Ran-N with no verdict) without its summary; return (framework, evidence line) or None.
2. `lib/cicd/steps.py` - StepDef.unsupported_runner: Optional[str], the declaration naming the runner.
3. `lib/cicd/manifest.py` - StepModel.unsupported_runner (non-empty when present), carried through step_model_to_step_def.
4. `lib/cicd/runner.py` - UNKNOWN warning keeps its sentence and appends a DETAIL cause: supported-runner-empty or unclassifiable (naming the declaration); a declared runner is quiet (log only, gate ok); a supported signature overrides a declaration; a declaration contradicted by a parsed summary warns; two-sided pre-commitment in the comment.
5. `tests/test_runner.py` - control that the three causes produce pairwise different text; declared quiet; declaration cannot silence a supported signature; contradicted declaration warns; classify_unparsed units; manifest round-trip; existing printed-nothing bound untouched.

Scope: 5 files, ~200-260 lines.
Risks: signature detection is itself parsing - a misclassification changes DETAIL only, never the verdict; manifest-less projects must create .claude/cicd_tasks.yml to declare; aggregate steps (make verify) never reached this warning and still do not.
