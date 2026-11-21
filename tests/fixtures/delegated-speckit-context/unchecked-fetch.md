## Instructions

### Step 2: Analyze - Build Codex Prompt

**Spec context (parent, before planning):**

```bash
BODY_FILE="$(mktemp -t delegated-body-XXXXXX.md)" || exit 1
gh issue view 42 --json body --jq .body > "$BODY_FILE"
if [ -x ~/.claude/scripts/speckit-context.py ]; then
    ~/.claude/scripts/speckit-context.py check --body-file "$BODY_FILE" --root .
else
    echo "Context unchecked: checker unavailable; read the source directly."
fi
```

Substitute the assigned issue for 42. Follow the
[context states](../../../docs/scripts/speckit-context.md): `absent` is ordinary;
otherwise read the reference source before building the prompt. Exit 3 reports
a state; changed bytes alone never change acceptance. Missing checker is
explicitly unchecked, never absent.

3. **Build the Codex prompt:**

Plan from the issue and source.

### Step 3: Approve

Wait for approval.
