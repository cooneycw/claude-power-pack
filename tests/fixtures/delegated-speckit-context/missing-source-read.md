## Instructions

### Step 2: Analyze - Build Codex Prompt

**Spec context (parent, before planning):**

```bash
BODY_FILE="$(mktemp -t delegated-body-XXXXXX.md)" || exit 1
if ! gh issue view 42 --json body --jq .body > "$BODY_FILE"; then
    echo "STOP: issue fetch failed; context unchecked."
    exit 1
fi
if [ -x ~/.claude/scripts/speckit-context.py ]; then
    ~/.claude/scripts/speckit-context.py check --body-file "$BODY_FILE" --root .
else
    echo "Context unchecked: checker unavailable; read the source directly."
fi
```

3. **Build the Codex prompt:**

Plan from the issue and source.

### Step 3: Approve

Wait for approval.
