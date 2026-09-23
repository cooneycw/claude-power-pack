# cpp:init fixture

```bash
~/.claude/scripts/cpp-host-write.sh json-merge-sections \
  "$CPP_DIR/templates/opencode-gemma.json" "$OC_CONFIG" provider agent
case $? in
  0) echo "✓ merged" ;;
  *) echo "✗ NOT merged" ;;
esac
```
