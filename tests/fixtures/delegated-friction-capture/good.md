### Friction Capture (always-on, fail-open)

Parent: follow [/flow:auto](../flow/auto.md)'s Friction Capture (always-on) section
every step, before STOP. Classes: gate-failure, red-output, manual-intervention;
never log permission-prompt by hand. Missing helper: continue.

```bash
~/.claude/scripts/friction-log.sh --class <class> --signal "<signal>" --run "codex:auto #42" --step "<N/8 Name>"
```

Substitute assigned issue for 42. Capture only; retro fixes.

---

### Step 1: Start - Create Worktree
