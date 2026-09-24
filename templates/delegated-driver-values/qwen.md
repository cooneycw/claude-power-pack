<!-- Slot values for `/qwen:auto` (issue #1011).

     The shared lifecycle lives in templates/delegated-driver-core.md; this file
     supplies only what is genuinely Qwen-specific inside it. Render with
     `python3 scripts/delegated-core-vendor.py --write`.

     A slot's value is the EXACT lines between its marker and the next one -
     nothing is stripped, so a trailing blank line here is a trailing blank line
     in the rendered document. A marker immediately followed by the next marker
     is an EMPTY value: a block slot's line is removed entirely, an inline slot
     renders as nothing.
-->
<!-- slot: DRIVER -->
qwen
<!-- slot: DRIVER_TITLE -->
Qwen
<!-- slot: PROMPT_TARGET -->
the Qwen model
<!-- slot: MODEL_WROTE -->
the local Qwen model wrote
<!-- slot: HARNESS_CMD -->
the `qwen` harness
<!-- slot: STEP4_STEPLINE -->
Step 4/8: Execute Qwen (delegate implementation to local Qwen via Qwen Code CLI)
<!-- slot: VERIFY_EXTRA_BASH -->
<!-- slot: VERIFY_EXTRA -->
<!-- slot: CAPABILITY_WEB_BULLET -->
- Does closing it require consulting a **live source** - current terms, an
  upstream changelog, a present-day API or price? That is `web`, and this lane
  provides no retrieval tool.
<!-- slot: STEP2_CALIBRATION -->
   **Local-model calibration:** a locally hosted ~27B model is markedly weaker
   than a frontier cloud model. Compensate in the prompt:
   - Be more explicit and concrete than you would be for Codex - name the exact
     files to modify, the function signatures involved, and the expected behavior.
   - Prefer smaller, sharply scoped changes. If the issue is broad, decompose it
     and consider warning the user that `/flow:auto` or `/codex:auto` may fit better.
   - Repeat the most important constraint at the END of the prompt as well as
     the beginning; small models weight prompt endings heavily.

<!-- slot: STEP3_EXTRA -->
<!-- slot: STEP5_EMPHASIS -->
**This step carries more weight than in `/codex:auto`** - a local 27B model
produces plausible-but-wrong code at a higher rate than a frontier model.
Review the diff line by line, not just structurally.
<!-- slot: STEP5_REVIEW_EXTRA -->
   - Hallucination: Does it call functions, imports, or APIs that do not exist
     in this codebase? (The most common local-model failure mode.)
<!-- slot: STEP5_CRITICAL -->
If review finds CRITICAL issues that a re-prompt cannot fix (fundamentally
wrong approach), STOP and report. Offer to re-prompt Qwen, escalate to
`/codex:auto`, or hand off to manual implementation.
<!-- slot: FIX_REEXEC -->
3. **Age the Step-4 verdict before re-delegating (issue #921).** The pass
   Step 4 recorded is a reading with a timestamp, and by now it is usually past
   its 120s window. Ask whether it is still current - this probes nothing:
   ```bash
   ~/.claude/scripts/lane-serveability-check.sh --check-age 1789000000 --recorded serving --lane qwen
   ```
   (substituting the literal `LANE_SERVE_AT` / `LANE_SERVE_STATUS` from Step 4,
   or from the latest re-probe below).
   - `fresh` -> re-execute.
   - `stale` or `unknown` -> probe ONCE, immediately before the re-execute, then
     act on it exactly as Step 4 does (set the endpoint and model variables as
     Step 4 does, in the same call - they do not survive from Step 4's shell):
     ```bash
     ~/.claude/scripts/lane-serveability-check.sh --endpoint "$QWEN_ENDPOINT" --model "$QWEN_MODEL" --lane qwen
     ```
     - `serving` -> re-execute, and carry this probe's `LANE_SERVE_AT` forward.
     - `dead` or `unreachable` -> **STOP** the fix loop, report
       `LANE_SERVE_DETAIL` verbatim, and say the **qwen lane is down** - the
       re-execute would have failed the same way, minutes in.
     - `unknown` -> **STOP** the fix loop and say the lane is **unverified**: the
       probe could not run (no `curl`), so it observed nothing and is not an
       outage diagnosis. Report `LANE_SERVE_DETAIL`; do not re-execute unchecked.

   **Never probe on a timer, and never probe without a delegated call right
   behind it** (owner ruling on #921: treat the serving host as NOT pinning its
   model, whatever it was once configured to do). On an unpinned host every probe
   of a cold model IS a full weight load - the operation that was observed being
   killed. A probe placed directly before a re-execute performs
   the load that re-execute would perform anyway: if it passes the model is
   resident for the call, if it fails the call is not spent. A probe anywhere
   else is an extra load on the exact resource that was exhausted.
   Then **Re-execute** with the same invocation as Step 4 (same sandbox, same
   provider flags), REDIRECTING to `/tmp/qwen-fix-${ISSUE_NUM}-${RETRY}.jsonl`
   - never piping through `tee` - with the exit capture in the SAME block, then
   checking the payload (issue #798):
   ```bash
   QWEN_FIX_OUTPUT="/tmp/qwen-fix-${ISSUE_NUM}-${RETRY}.jsonl"
   # ... same qwen invocation as Step 4 ... > "$QWEN_FIX_OUTPUT" 2>&1
   QWEN_FIX_EXIT=$?
   echo "qwen fix attempt exited $QWEN_FIX_EXIT; output: $QWEN_FIX_OUTPUT"
   ```
   ```bash
   ~/.claude/scripts/delegated-run-check.sh /tmp/qwen-fix-42-1.jsonl 0 --lane qwen --expect-tools
   ```
<!-- slot: STEP6_ESCALATION -->
 Offer escalation: re-run the remaining fix loop under `/codex:auto` (frontier model) or fix manually.
<!-- slot: IMPLEMENTER_TRAILER -->
   - Note the Qwen model tag as implementer in the commit body
     (e.g., `Implemented-By: qwen3.8-code:latest via Qwen Code CLI (headless)`)
<!-- slot: PR_DELEGATION_NOTE -->
     - Note that implementation was delegated to a local Qwen model
<!-- slot: IMPLEMENTER_SUMMARY -->
  Implementer: {QWEN_MODEL} via Qwen Code CLI headless (local, zero API cost)
<!-- slot: FINAL_SUMMARY_EXTRA -->
<!-- slot: RESUME_EXEC_LINE -->
    /qwen:exec "<prompt>"    (if step 4 failed)
<!-- slot: ERROR_ROWS -->
- **Qwen Code CLI not installed:** Stop at step 4; it is required as the harness (no cloud API key is used)
- **Ollama unreachable / model missing:** Stop at step 4; run `/qwen:status` to diagnose
- **Execution fails or stalls:** Stop at step 4, show last 20 lines of JSONL output
- **Model makes no changes:** Stop at step 4; tighten the prompt or escalate to `/codex:auto`
- **Review finds critical issues:** Stop at step 5; offer re-prompt, escalation, or manual hand-off
- **Quality gates fail after retries:** Stop at step 6; offer escalation to `/codex:auto`
