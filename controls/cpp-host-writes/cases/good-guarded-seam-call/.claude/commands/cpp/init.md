# cpp:init fixture

```bash
~/.claude/scripts/cpp-host-write.sh settings-merge "$TEMPLATE"
case $? in
  0) echo "✓ Flow allowlist merged" ;;
  3) echo "→ DEFERRED by request - settings.json was NOT modified" ;;
  *) echo "✗ NOT merged" ;;
esac
```
