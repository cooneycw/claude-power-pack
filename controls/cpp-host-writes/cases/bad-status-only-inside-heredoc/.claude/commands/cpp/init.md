# cpp:init fixture

```bash
~/.claude/scripts/cpp-host-write.sh settings-edit --arg cmd "$CMD" <<'JQ'
  .note = "exit $? is jq program text, not a handler"
  | .hooks = (.hooks // {})
JQ
echo "✓ hook registered"
```
