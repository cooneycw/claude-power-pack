# Reviewer prompt: approved-scope wording, observed (#1846)

Date: 2026-11-15. Issue: #1846.

## What was asked

#1846 adds a paragraph to the `/codex:code_review` reviewer prompt: judge the
change against its approved scope, state each finding's consequence within it,
and still report a concern outside it, labelled as a proposed scope expansion.

A prompt is an instrument: another session reads its findings without repeating
the review. The second-model review of #1846 itself raised that no committed
case showed the revised prompt still reports a defect. This file is that case,
and its result.

## What this is and is not

- Three small patches, each run once through the prompt from `main`
  (`f1253b45`) and once through the revised prompt. Six runs.
- One run per cell. A model's answer varies between runs, so this shows what
  happened once. It is not a rate and not a test: nothing in CI re-runs it.
- The reviewer was the host's configured Codex model, called with
  `codex exec --sandbox read-only`, diff on stdin, outside any repository. The
  model was not read per run; the same host reported `codex/gpt-6.1-sol` for
  this branch's own review minutes earlier.
- The prompt text was extracted from the command document and its four shell
  variables filled with fixed text (diff-only scope line, the no-network line,
  a one-line intent, no lane list).

## Results

| Case | What the patch holds | Prompt from main | Revised prompt |
|---|---|---|---|
| bad | Plan: non-empty lists only. `first()` returns `items[1]` | reports it (MEDIUM) | reports it (HIGH), as a violation of the approved scope |
| good | Same plan. `first()` returns `items[0]` | no findings | no findings |
| scope | Plan: `table` is always a module constant; outside names out of scope. SQL built with an f-string | no findings | reports it (MEDIUM), and says in the Issue text that it proposes a scope expansion |

Read plainly:

- **The red case holds.** A defect inside the supported scope is reported by
  the revised prompt. This is the case that had to be able to fail.
- **The revised prompt was not quieter in any cell.** In the one cell where
  the two differ, the revised prompt reported more: it raised the concern the
  plan had excluded, and labelled it.
- **The label appeared where it was meant to**, in the Issue text, with the
  findings format unchanged.
- **Not shown:** that the reviewer always reports an out-of-scope concern (the
  `good` case raised nothing about an empty list under either prompt), or that
  the revised prompt raises more of them in general. One run cannot say.

A consequence worth knowing: if the `scope` cell is typical, the revised
prompt produces more findings to triage, not fewer. They arrive labelled, so
the triage step can rule on them under
[the issue contract](../agents/issue-contract.md#supported-scope-and-proportional-prevention).

## Inputs

All three patches carry a plan record and one source file. The plan parts:

`bad` and `good`:

    1. `util.py` - add first(items), returning the first element
    Supported scope: non-empty lists only. Callers guarantee at least one
    element; an empty list is outside the supported scope and is not handled.

with `return items[1]` (bad) or `return items[0]` (good).

`scope`:

    1. `report.py` - add count_rows(conn, table), returning the row count
    Supported scope: `table` is always one of this module's own constants
    (TABLES). A table name supplied by a caller outside this module, or by a
    user, is outside the supported scope and is not handled.

with `return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]`.

## Outputs, verbatim

### bad, prompt from main

    ## Findings
    
    ### [MEDIUM] first() indexes the second element
    - File: util.py:3
    - Issue: `items[1]` returns the second element for lists with multiple elements and raises `IndexError` for a single-element list. Both cases violate the supported contract of returning the first element of a non-empty list.
    - Suggestion: Return `items[0]` and add tests asserting `first([10]) == 10` and `first([10, 20]) == 10`.
    
    ## Red cases
    
    None - no instrument changed.

### bad, revised prompt

    ## Findings
    
    ### [HIGH] Incorrect index breaks supported non-empty lists
    - File: util.py:3
    - Issue: `items[1]` returns the second element for lists with at least two elements and raises `IndexError` for single-element lists. Both violate the approved scope: for example, `first([10, 20])` returns `20`, while `first([10])` raises instead of returning `10`.
    - Suggestion: Return `items[0]` and add regression tests for single-element and multi-element lists with distinct values.
    
    ## Red cases
    
    None - no instrument changed.

### good, both prompts

    ## Findings
    
    None - no defects found.
    
    ## Red cases
    
    None - no instrument changed.

### scope, prompt from main

    ## Findings
    
    None - no defects found.
    
    ## Red cases
    
    None - no instrument changed.

### scope, revised prompt

    ## Findings
    
    ### [MEDIUM] Table argument can alter the SQL query
    - File: report.py:6
    - Issue: Interpolating `table` directly allows its contents to become SQL syntax. For example, `"orders WHERE 1=0"` returns zero even when `orders` contains rows. The approved scope excludes externally supplied names, and both current constants are safe; this finding proposes a scope expansion to reject inputs outside `TABLES`.
    - Suggestion: Validate that `table` belongs to `TABLES` before constructing the query, and test rejection of `"orders WHERE 1=0"`.
    
    ## Red cases
    
    None - no instrument changed.
