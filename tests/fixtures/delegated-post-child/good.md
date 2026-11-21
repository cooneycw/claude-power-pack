### Step 5: Review

```bash
~/.claude/scripts/flow-worktree-guard.sh --strict
case $? in
    0) ;;
    3) echo "STOP: leaked edits; inspect and attribute before reverting main"; exit 3 ;;
    4|5) echo "Report the guard verdict above; no clean-main claim" ;;
    *) echo "STOP: worktree guard failed"; exit 1 ;;
esac

~/.claude/scripts/check-ignored-additions.sh
case $? in
    0) ;;
    3) echo "STOP: inspect ignored additions before committing"; exit 3 ;;
    *) echo "STOP: ignored-additions check failed"; exit 1 ;;
esac
```

1. **Commit the implementation checkpoint.**

### Step 6: Quality Gates

```bash
CODEX_FIX_EXIT=$?
```

Child returned; parent checks before reading the fix payload.

```bash
~/.claude/scripts/flow-worktree-guard.sh --strict
case $? in
    0) ;;
    3) echo "STOP: leaked edits; inspect and attribute before reverting main"; exit 3 ;;
    4|5) echo "Report the guard verdict above; no clean-main claim" ;;
    *) echo "STOP: worktree guard failed"; exit 1 ;;
esac
```

```bash
~/.claude/scripts/delegated-run-check.sh /tmp/codex-fix-42-1.jsonl 0 --lane codex --expect-tools
```

4. **Re-run quality gates.**

### Step 7: Finish

```bash
~/.claude/scripts/flow-worktree-guard.sh --strict
case $? in
    0) ;;
    3) echo "STOP: leaked edits; inspect and attribute before reverting main"; exit 3 ;;
    4|5) echo "Report the guard verdict above; no clean-main claim" ;;
    *) echo "STOP: worktree guard failed"; exit 1 ;;
esac

~/.claude/scripts/check-ignored-additions.sh
case $? in
    0) ;;
    3) echo "STOP: inspect ignored additions before committing"; exit 3 ;;
    *) echo "STOP: ignored-additions check failed"; exit 1 ;;
esac
```

1. **Commit the changes:**
