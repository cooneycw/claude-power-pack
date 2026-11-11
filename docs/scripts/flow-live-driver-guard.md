# `flow-live-driver-guard` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `flow-live-driver-guard`

- flow-live-driver-guard - advisory concurrent-session guard (#503): warns when a worktree's dirty files were modified within the freshness window, the signature of another live session mid-implementation; wrapped by flow-start-resolve on the resume lane, and re-run at `/flow:auto` Step 4 before the first edit (#597) because a single Step-1 check goes stale across the analysis + ELI5 pause
- flow-live-driver-guard names its subject (#1271, the #614 shape) - `FLOW_LIVE_DRIVER_PATH: <root>` immediately precedes every `FLOW_LIVE_DRIVER:` verdict, fail-open unknowns included, and a call with no WORKTREE_PATH prints a stderr NOTE that it is inspecting the ambient cwd; the cwd default is kept as a published interface, and `/flow:auto` Step 4 now passes `WT_PATH` explicitly
