## Findings

### [HIGH] Unrelated settings are merged into one knob history
- File: scripts/check-oscillation.py:154
- Issue: Hunk pairing overwrites repeated keys, and subsequent grouping identifies settings only by `(path, key)`. Changing `first(timeout=60)` to `first(timeout=30)`, then independently changing `second(timeout=10)` to `second(timeout=20)`, reports a reversal although neither setting reversed. Conversely, when both calls change in one hunk, the last `timeout` overwrites the first and can hide its reversal. The same-SHA exclusion does not fix either case. A finding therefore cannot distinguish the target setting from its neighbour.
- Suggestion: Preserve individual occurrences and pair them using their enclosing section, function, or call context. Track that identity across commits and report ambiguous pairings separately. Add tests covering independent call sites and repeated keys within one hunk.

### [MEDIUM] Common assignment syntax is missed or attributed to the type
- File: scripts/check-oscillation.py:84
- Issue: `_knobs('timeout = 30 # seconds')` and `_knobs('"timeout": 30,')` return nothing, while `_knobs('timeout: int = 30')` returns `{'int': 30}`. Consequently, inline rationale comments make settings invisible, JSON configuration reversals disappear, and unrelated annotated settings collapse under their shared type. If another recognized setting changes in the range, these omissions are masked by a nonempty population and an `OSCILLATION: none` verdict.
- Suggestion: Recognize inline comments, quoted keys, and annotated assignments while retaining the actual setting name and rejecting partial numeric literals. Add extraction and reversal tests using these real syntaxes.

### [MEDIUM] Flag values are compared using only their numeric prefix
- File: scripts/check-oscillation.py:86
- Issue: `FLAG` has no trailing token boundary, so `--timeout 1m`, `--timeout 60s`, and `--timeout 2m` become `1`, `60`, and `2`. This produces a reversal even though the duration stayed equal and then increased. Version strings and other numeric-prefixed arguments are similarly treated as numeric settings.
- Suggestion: Require a complete numeric argument. Either normalize explicitly supported units before comparison or exclude unit-bearing values and document that narrower population. Test equivalent durations and monotonic changes expressed with different units.

### [MEDIUM] Git’s quoted paths can attribute another file’s changes to the previous file
- File: scripts/check-oscillation.py:173
- Issue: The parser recognizes only `+++ b/`. Git quotes paths containing characters such as tabs and, under its default configuration, non-ASCII characters. A quoted file header leaves `path` pointing to the preceding file in the commit, so its hunks become moves belonging to that neighbour; if it is the first file, its moves are dropped. This can manufacture a reversal in a file that did not reverse.
- Suggestion: Flush and reset file state at every file boundary, and decode Git’s quoted path representation or use an unambiguous path protocol. Add a multi-file regression case containing a quoted filename.

### [MEDIUM] Parallel branch changes are treated as a sequential reversal
- File: scripts/check-oscillation.py:134
- Issue: `git log --reverse --no-merges` includes commits from both sides of a merge, while `find_oscillations()` treats adjacent entries as successive states. Two branches independently changing a shared base value of `30` to `60` and `10` therefore produce an apparent reversal even though neither branch changed back. Excluding merge commits also hides reversals introduced by merge resolution.
- Suggestion: Define the historical lineage being measured. For the integrated branch, walk first-parent history and compare merge results against their first parent; alternatively, require ancestry and state continuity when pairing moves. Test both divergent branches and a reversal introduced at a merge.

### [MEDIUM] Prose about exit codes is counted as executable policy
- File: scripts/check-oscillation.py:87
- Issue: `EXITC` matches any occurrence of `exit 3`, including comments, documentation, and string literals. Editing prose from “exit 0” to “exit 3” and back creates an oscillation finding without changing an executable exit policy. Because every occurrence is named `exit`, edits to unrelated paragraphs can also combine into one reported sequence.
- Suggestion: Recognize executable exit statements in supported contexts, or classify textual mentions separately from policy changes. Add paired tests proving that executable reversals are detected while prose-only edits are excluded.

### [MEDIUM] Claimed allowlist coverage has no corresponding extraction
- File: scripts/check-oscillation.py:36
- Issue: The script claims to discover allowlist membership changes, but `_knobs()` extracts only numbers and `flush()` requires both removed and added lines. Adding a string entry to `.gitleaks.toml` and later removing it produces no moves. The corpus substitutes `paths = 12` for an actual list, so it never exercises this gap. With unrelated numeric moves present, the detector can report `none` despite an allowlist reversal.
- Suggestion: Either implement history-derived membership tracking with real list fixtures, or explicitly scope the detector and its verdict to supported numeric settings. If that narrower scope is intentional, document that allowlist reversals remain a question for ADR-directed human review and remove the synthetic corpus’s implication of membership coverage.