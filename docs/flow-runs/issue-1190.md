# Flow run record - issue #1190

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1190
- Base SHA:          d3f474b
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          wave orchestrator `claude-improvements-new`
                     (session a9c791f1-8a8d-4b1b-a7b2-c7e181009503), wave
                     `claude-improvements`, ruling delivered as mailbox rev 3
                     with a correction in rev 4
- Recorded at:       2026-09-23T12:05:00Z

## Section B evidence

Issue filed 2026-09-21T20:57:39Z. Inspected:

- Commits touching the three scripts and their tests since filing - exactly two,
  out of 16 commits landed overall in that window:
    - `e9a58b6` refactor(gates): migrate flow-finish-gate onto gate-lib (Closes #1061) (#1195)
    - `43286db` fix(controls): isolate the six flow-finish-gate controls (#1203)
- Merged PRs inspected: #1183 through #1209. Material: #1195. #1203 matters only
  because it reshapes the control directory layout this change adds to.
- Duplicate / superseding issues: NONE. A search across all states returns
  #1190 itself, #864 (the Nit Store this issue was aggregated FROM), and #1031
  (adjacent - git idioms that silently revert a sibling's work - not
  superseding).

Verdict reasoning, defect by defect:

- **Defect 3** (counter-model receipt id concatenated with the branch name) is
  ALREADY DELIVERED by `e9a58b6`. Verified by CONTENT at base `d3f474b`, not by
  ancestry: the `if/else` repair matches once, the broken nested-expansion form
  matches zero times outside comments, from the same extractor - so the zero is
  a real absence rather than a dead grep. No work is owed.
- **Defect 1** (flow-pr-watch scrapes the whole log) is LIVE.
- **Defect 2** (no `FLOW_WAVE: error` on a usage failure) is LIVE, reproduced:
  `register` with no role gives `FLOW_WAVE_EXIT=2` and zero `FLOW_WAVE:` lines.

The issue is a faithful record of what was true when filed; #1195 landed after.
Stale, not wrong.

## Section C - the approved plan

 1. `scripts/flow-pr-watch.sh` - bound the failed-id scrape to pytest's own
    summary region instead of the whole log, and emit the summary's own failure
    COUNT beside the scraped list so a disagreement is visible. Where no summary
    marker exists (killed/truncated log) the scrape stays whole-log but REPORTS
    itself as unbounded; unbounded must never render as clean. Declare the new
    control with a `#: NEGATIVE-CONTROL:` marker.
 2. `tests/test_flow_pr_watch.py` - regression tests. The load-bearing case
    builds a log holding a negative control's echoed `FAILED ...::...` lines
    inside a BAD-case block plus a real one-failure summary, and asserts the
    scrape yields only the real failure. It must FAIL on pre-fix code, run there.
 3. `scripts/flow-wave-registry.sh` - four changes, all verdict-shaped:
    (a) `usage_fail` (:436) emits the documented `FLOW_WAVE: error` before
        exit 2 - one function, ~45 call sites, not just the four the issue named.
    (b) the `self-address` verb (:1944) emits a verdict instead of exiting 0
        silently.
    (c) the three `with_lock` paths (:817 lock timeout, :820 mktemp failure,
        :826 corrupt-registry update) emit a verdict. Exit CODES are NOT
        changed - exit 3 is documented in the published contract instead.
    (d) `report_overlap` (:1202) stops letting a KNOWN-FALSE worktree match mask
        a true file-lane collision - the NARROW fix: suppress only the worktree
        match that `cwd_is_shared_parent` already identifies as an artefact of a
        pre-worktree registration. NOT the additive version. The reversal
        trigger is recorded at the predicate in the code.
    `--help` and the `--any-live-only` sub-mode are deliberately left alone.
 4. `tests/test_flow_wave_registry.py` - regression tests for each: a usage
    failure emits exactly one `FLOW_WAVE: error`; `self-address` and the
    `with_lock` paths emit verdicts; a pair with nested cwds AND overlapping
    lanes still names the shared files. All must fail pre-fix.
 5. `controls/flow-pr-watch` - new committed control. BAD case: a log whose only
    `FAILED` lines are a control's echo must NOT be reported as pipeline
    failures. GOOD case: a real failure still is.
 6. `controls/flow-wave-registry` - new committed control, the red case the
    orchestrator named: a registered pair with nested cwds AND overlapping file
    lanes MUST still warn, shown RED on pre-fix code.
 7. `docs/flow-runs/issue-1190.md`, `docs/flow-runs/issue-1190.as-read.md` -
    this run's own artifacts.

Scope: 2 scripts modified, 2 test modules extended, 2 control directories
created, 2 run artifacts. Roughly 250-400 lines including cases.

Risks:

- **Bounding the scrape can lose a real failure** when a pipeline is killed
  before pytest prints its summary. Mitigated by keeping the whole-log scrape as
  a labelled-unbounded fallback rather than silently.
- **Changing `report_overlap` is two-sided** (oscillation hazard). The additive
  version would restore the warning noise the precedence was built to control
  and invite a later re-suppression. Narrow fix only. Reversal trigger: if real
  nested-worktree pairs start being reported twice, the narrow rule was drawn
  wrong - redraw it, do NOT restore blanket precedence.
- **`usage_fail` now prints a block on ~45 paths**, so any existing test
  asserting exact stdout on a usage error needs updating - to be found, not
  discovered at the gate.
- **The registry is live tooling for twelve sessions** across two waves, and
  `~/.claude/scripts` symlinks into the MAIN checkout. Edits are confined to this
  worktree, so nothing changes under anyone until merge; at merge every live
  session picks up new behaviour in place. Merge authority for this PR is
  narrowed to the orchestrator for exactly that reason.
