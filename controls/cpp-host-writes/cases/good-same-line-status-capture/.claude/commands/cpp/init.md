# cpp:init fixture

```bash
~/.claude/scripts/cpp-host-write.sh settings-merge "$TEMPLATE"; rc=$?
[ "$rc" = 0 ] && echo "✓ merged" || echo "✗ NOT merged"
```
