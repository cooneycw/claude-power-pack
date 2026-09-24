# Flow run record - issue #1232

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1232
- Base SHA:          c5b1c5edb180db748738878e577809b47d112611
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the repository owner, in session, replying "approved" to the Section C report
- Recorded at:       2026-09-24T09:33:12Z

## Section B evidence

- commits since 2026-09-24T09:23:05Z: none globally, and none touching
  scripts/codex-skill-sync.py, tests/test_codex_skill_sync.py or tests/conftest.py
- merged PRs in the window: #1231 only (flow plan-comparison NUL delimiting,
  Closes #1220) - unrelated to the install lane
- duplicate / superseding issues: none. #1067 and #1211 (open) differ in subject;
  #1151 and #1185 (closed) touch the same script but neither the --install mode
  nor test isolation. #823 (closed) is the nearest neighbour - stale copies under
  ~/.codex/skills, diagnosed as the install lane never being re-run - a
  same-shaped symptom from a different cause, so it neither covered nor
  superseded this.

## Section C - the approved plan

1. `scripts/codex-skill-sync.py` - add a refusal to run_install(): when the environment names a forbidden destination (CPP_REFUSE_INSTALL_DEST) and the resolved dest_root IS that exact path, raise instead of installing. Refuse at the WRITE, not at install_dest_root() - three existing tests resolve that function read-only to build assertions. Raise rather than return a code, because a test ignoring the return value would otherwise let the leak through silently. Adds `import os`.
2. `tests/conftest.py` - arm that refusal for the whole suite in pytest_configure, setting CPP_REFUSE_INSTALL_DEST to this process's own Path.home()/".codex"/"skills". Subprocesses inherit it; a sandboxed-HOME child computes a different destination and is unaffected. When the home cannot be resolved, arm nothing and SAY SO in the terminal summary - an unarmed guard must not read as a clean one.
3. `tests/test_codex_skill_sync.py` - add the missing tmp_home fixture to test_the_two_success_lines_cannot_be_read_as_the_same_question, the one leaky call site; and add the negative control: a pytester sub-run with the REAL tests/conftest.py copied in and HOME pointed at a temporary directory, holding one inner test that calls main(["--install"]) with no tmp_home and must FAIL and one that uses tmp_home and must PASS, plus an assertion that the sub-run's own .codex/skills was never created. The sandboxed HOME is what makes the control safe: with the guard deleted the inner test writes into a temp folder and the outer control goes red, destroying nothing.

Scope: 3 files edited, ~120 lines, plus the 2 generated mirrors of file 1
(codex/skills/flow-auto/scripts/, codex/skills/flow-finish/scripts/) regenerated
by scripts/codex-skill-resync.sh at Step 6.

Risks:
- One deviation from the issue's wording, toward a STRICTER rule: the issue
  proposed a guard that fires "without opting in"; there is no opt-in here,
  because no test has a legitimate reason to write to that path. The existing
  tmp_home fixture satisfies the prohibition by pointing somewhere else.
- A test-only branch in production code. If CPP_REFUSE_INSTALL_DEST leaked into
  a real shell, `make codex-install` would refuse. Bounded deliberately: the
  variable names an exact PATH rather than carrying a boolean, so it can only
  block that one destination; the failure is a loud refusal, not a silent skip;
  nothing is destroyed by it.
- The guard is BOUNDED and its docstring says so: it protects the Codex install
  destination, not every write a future test might make under the real $HOME.
  Its green must not be read as "no test touches the host home".
- pytester sub-runs are slow (a real pytest subprocess) and depend on PYTHONPATH
  plus copying the real conftest. The existing precedent carries the same cost.

Deferred by agreement: run_install()'s copy-then-prune window (the issue's "Also
worth deciding"). A correct fix stages the tree and swaps it atomically, which
changes install semantics and needs its own control; it gets its own issue,
referenced from this PR, rather than riding a fix whose subject is test
isolation.
