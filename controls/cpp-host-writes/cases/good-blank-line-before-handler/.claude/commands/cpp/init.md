# cpp:init fixture

```bash
~/.claude/scripts/cpp-host-write.sh settings-merge "$TEMPLATE"

case $? in
  0) echo "✓ merged" ;;
  *) echo "✗ NOT merged" ;;
esac
```
