# Flow run record - issue #1298

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1298
- Base SHA:          84f414e95fb22c6ea2856da6d3c4a096530ea614
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 1780 in reply to ELI5 message 1779
- Recorded at:       2026-09-28T11:00:00Z

## Section B evidence
- Reproduced on 84f414e: `bash -c "/opt/venv/bin/pytest /tmp/cases"` (id check)
  is_test_step()=False; `PYTEST_WORKERS=4 make lint` (id lint) =True; control
  `pytest /tmp/cases` =True.
- Commits since filing touching lib/cicd/steps.py: ce5f296 (#1296, the #1294 fix
  this builds on). Merged PRs since: 1296, 1302, 1304 - none touch the classifier.
- Duplicate/superseding: none; #1289 shares files (serial, next). Nit Store
  comment 5858154209 is case (2).

## Section C - the approved plan
1. `lib/cicd/steps.py` - bounded shlex tokenizer for the command: drop words matching ^[A-Za-z_][A-Za-z0-9_]*= only; basename per word; multi-word word starting like a path -> basename, else existing word-level strip; shell -c scripts re-tokenized once (depth 1); unparseable -> hint regex over the raw command (fails toward test)
2. `tests/test_cicd_outcomes.py` - regressions for both cases (red on 84f414e), env-prefixed variants, precision pins (--junitxml=report-test.xml, -k=test_foo, make test-file FILE=..., make PYTEST_ARGS=-x lint), -lc cluster, depth-2, unparseable, python -c
3. `tests/test_runner.py` - gate-level through DeterministicRunner: quoted fake pytest all-skipped warns; env-prefixed zero-examined lint warns (#1027); both red on 84f414e

Scope: 3 files, ~150-200 lines. Risks: shlex/bash quoting disagreements (covered by
fail-toward-test); unsupported forms ($VAR expansions, aliases, eval, heredocs,
nested -c past depth 1, non-shell quoted arg starting with a path) stated in code and PR.
