# `flow-stale-check` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `flow-stale-check`

- flow-stale-check - advisory early stale-base detector for `/flow:auto` Step 4/6 + `/flow:finish` (#473)
- flow-stale-check declared checkout path (#614, the #592 rule's other half) - the tree to inspect is DECLARED by the caller (second positional arg or `--path <dir>`/`--path=<dir>`, every git call routed `git -C`), never inferred from the Bash process cwd, which drifts on any earlier `cd` and once made the advisory report `current` for the MAIN repo while the run's worktree was behind. The contract is now TWO lines in fixed order, both colon-space form: `FLOW_STALE_PATH: <abs path>` immediately before `FLOW_STALE_BASE: <verdict>`, emitted on EVERY verdict including the fail-open unknowns, so a cwd-drift mismatch is visible in the transcript even on the cwd default (back-compat unchanged). `auto.md` Step 4/6 + `finish.md` pass the worktree path as a trailing literal (keeps the #581 prefix-rule match); relative `--git-path FETCH_HEAD` output is re-anchored against the declared dir
- flow-stale-check failed count (#1271) - a `rev-list --count HEAD..<base>` that fails now reports `unknown`; it used to fall back to `|| echo 0` and report `current`, the one verdict that tells the caller to proceed, made unreachable only by an unrelated base-ref check above it
