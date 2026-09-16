<!-- Slot values for `/gemma:auto` (issue #1011).

     The shared lifecycle lives in templates/delegated-driver-core.md; this file
     supplies only what is genuinely Gemma-specific inside it. Render with
     `python3 scripts/delegated-core-vendor.py --write`.

     A slot's value is the EXACT lines between its marker and the next one -
     nothing is stripped, so a trailing blank line here is a trailing blank line
     in the rendered document. A marker immediately followed by the next marker
     is an EMPTY value: a block slot's line is removed entirely, an inline slot
     renders as nothing.
-->
<!-- slot: DRIVER -->
gemma
<!-- slot: DRIVER_TITLE -->
Gemma
<!-- slot: PROMPT_TARGET -->
the Gemma model
<!-- slot: MODEL_WROTE -->
the local Gemma model wrote
<!-- slot: HARNESS_CMD -->
`opencode run`
<!-- slot: STEP4_STEPLINE -->
Step 4/8: Execute Gemma (delegate implementation to local Gemma via OpenCode)
<!-- slot: VERIFY_EXTRA_BASH -->
WORKTREE_ROOT=$(git rev-parse --show-toplevel)
<!-- slot: VERIFY_EXTRA -->
Capture `WORKTREE_ROOT` here: Step 4 passes it to `opencode --dir` explicitly
rather than trusting the inherited shell cwd, which drifts across tool calls.

<!-- slot: CAPABILITY_WEB_BULLET -->
- Does closing it require consulting a **live source** - current terms, an
  upstream changelog, a present-day API or price? That is `web`, and the
  `gemma-implementer` profile denies the tools outright.
<!-- slot: STEP2_CALIBRATION -->
   **Local-model calibration:** a locally hosted ~31B model is markedly weaker
   than a frontier cloud model. Compensate in the prompt:
   - Be more explicit and concrete than you would be for Codex - name the exact
     files to modify, the function signatures involved, and the expected behavior.
   - Prefer smaller, sharply scoped changes. If the issue is broad, decompose it
     and consider warning the user that `/flow:auto` or `/codex:auto` may fit better.
   - Repeat the most important constraint at the END of the prompt as well as
     the beginning; small models weight prompt endings heavily.
   - Gemma 4 is a vision-capable instruct model with native function calling,
     but it is not a code-specialized tag the way `qwen3-coder` is. Prefer
     naming the edit sites over describing them.

<!-- slot: STEP3_EXTRA -->
**This is not OpenCode's `--auto`.** That flag, in Step 4, governs tool approval
INSIDE Gemma's own run, and it stays - it is unrelated to this gate. This gate is
an orchestrator-level stop before that run begins: passing `--auto` never
satisfies it, and nothing passed at invocation ever does.

<!-- slot: STEP5_EMPHASIS -->
**This step carries more weight than in `/codex:auto`** - a local 31B model
produces plausible-but-wrong code at a higher rate than a frontier model.
Review the diff line by line, not just structurally.
<!-- slot: STEP5_REVIEW_EXTRA -->
   - Hallucination: Does it call functions, imports, or APIs that do not exist
     in this codebase? (The most common local-model failure mode.)
<!-- slot: STEP5_CRITICAL -->
If review finds CRITICAL issues that a re-prompt cannot fix (fundamentally
wrong approach), STOP and report. Offer to re-prompt Gemma, escalate to
`/qwen:auto` or `/codex:auto`, or hand off to manual implementation.
<!-- slot: FIX_REEXEC -->
3. **Re-execute** with the same invocation as Step 4 (same `--agent`, `--dir`,
   and provider flags), REDIRECTING to
   `/tmp/gemma-fix-${ISSUE_NUM}-${RETRY}.jsonl` - never piping through `tee` -
   with the exit capture in the SAME block, then checking the payload (issue
   #798):
   ```bash
   GEMMA_FIX_OUTPUT="/tmp/gemma-fix-${ISSUE_NUM}-${RETRY}.jsonl"
   # ... same opencode invocation as Step 4 ... > "$GEMMA_FIX_OUTPUT" 2>&1
   GEMMA_FIX_EXIT=$?
   echo "opencode fix attempt exited $GEMMA_FIX_EXIT; output: $GEMMA_FIX_OUTPUT"
   ```
   ```bash
   ~/.claude/scripts/delegated-run-check.sh /tmp/gemma-fix-42-1.jsonl 0 --lane gemma --expect-tools
   ```
<!-- slot: STEP6_ESCALATION -->
 Offer escalation: re-run the remaining fix loop under `/codex:auto` (frontier model) or fix manually.
<!-- slot: IMPLEMENTER_TRAILER -->
   - Note the Gemma model tag as implementer in the commit body
     (e.g., `Implemented-By: gemma4-code:latest via OpenCode (headless)`)
<!-- slot: PR_DELEGATION_NOTE -->
     - Note that implementation was delegated to a local Gemma model
<!-- slot: IMPLEMENTER_SUMMARY -->
  Implementer: {GEMMA_MODEL} via OpenCode headless (local GPU, zero API cost)
<!-- slot: FINAL_SUMMARY_EXTRA -->
  Denied ops:  {N} tool calls blocked by the gemma-implementer profile
<!-- slot: RESUME_EXEC_LINE -->
    /gemma:exec "<prompt>"   (if step 4 failed)
<!-- slot: ERROR_ROWS -->
- **OpenCode CLI not installed:** Stop at step 4; it is required as the harness (no cloud API key is used)
- **Agent profile missing:** Stop at step 4; the mechanical fence is mandatory, install it from `templates/opencode-gemma.json` or via `/cpp:init` Tier 7
- **Ollama unreachable / model missing:** Stop at step 4; run `/gemma:status` to diagnose. On the reference server this can mean another VM holds the GPU claim
- **Execution fails or stalls:** Stop at step 4, show last 20 lines of JSONL output
- **Model makes no changes:** Stop at step 4; if the stream has no `tool_use` events at all, suspect the `/v1` tool-call-drop bug before the prompt - `/gemma:status` Step 4 tests for it
- **Review finds critical issues:** Stop at step 5; offer re-prompt, escalation, or manual hand-off
- **Quality gates fail after retries:** Stop at step 6; offer escalation to `/codex:auto`
