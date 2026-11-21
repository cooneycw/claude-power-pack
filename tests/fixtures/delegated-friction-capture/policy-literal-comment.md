```text
<!--
```
### Friction Capture (always-on)

Record friction the moment it happens, on every step, success OR failure, and
before any STOP, via the fail-open capture helper:

- a **quality-gate failure or retry** (lint/test/build/deploy)
- **red output** you narrated past or worked around instead of resolving
- a **manual intervention / correction** the user had to make

```bash
~/.claude/scripts/friction-log.sh --class <gate-failure|red-output|manual-intervention> \
  --signal "<what happened>" --fix "<proposed fix, if obvious>" \
  --scope <local|portable> --run "flow:auto #$ISSUE_NUM" --step "<N/7 Name>" --outcome "<retried|worked-around|corrected>"
```

Never log the **permission-prompt** class by hand (issue #482). Missing
helper: skip capture rather than stopping.
Capture only: fixes are proposed and applied in the retro, not here.

---

