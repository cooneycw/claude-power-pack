### Step 4: Execute

```bash
codex exec "$PROMPT" > "$OUTPUT" 2>&1
CODEX_EXIT=$?
case $? in
    4|5) echo "report third state" ;;
esac
```
