<!-- Slot values for `/codex:auto` (issue #1011).

     The shared lifecycle lives in templates/delegated-driver-core.md; this file
     supplies only what is genuinely Codex-specific inside it. Render with
     `python3 scripts/delegated-core-vendor.py --write`.

     A slot's value is the EXACT lines between its marker and the next one -
     nothing is stripped, so a trailing blank line here is a trailing blank line
     in the rendered document. A marker immediately followed by the next marker
     is an EMPTY value: a block slot's line is removed entirely, an inline slot
     renders as nothing.
-->
<!-- slot: DRIVER -->
codex
<!-- slot: DRIVER_TITLE -->
Codex
<!-- slot: PROMPT_TARGET -->
Codex
<!-- slot: MODEL_WROTE -->
Codex wrote
<!-- slot: HARNESS_CMD -->
`codex exec`
<!-- slot: STEP4_STEPLINE -->
Step 4/8: Execute Codex (delegate implementation to Codex CLI)
<!-- slot: VERIFY_EXTRA_BASH -->
<!-- slot: VERIFY_EXTRA -->
<!-- slot: CAPABILITY_WEB_BULLET -->
- Does closing it require consulting a **live source** - current terms, an
  upstream changelog, a present-day API or price? That is `web`, and this driver
  has none.
<!-- slot: STEP2_CALIBRATION -->
<!-- slot: STEP3_EXTRA -->
<!-- slot: STEP5_EMPHASIS -->
<!-- slot: STEP5_REVIEW_EXTRA -->
<!-- slot: STEP5_CRITICAL -->
If review finds CRITICAL issues that Codex cannot fix via re-prompt (e.g., fundamentally wrong approach), STOP and report. Offer to either re-prompt Codex or hand off to manual implementation.
<!-- slot: STEP5_RECEIPT -->
4. **Record the review as a counter-model receipt (issue #1383).** This review
   IS the cross-model review for this lane - Codex implemented, this Claude
   session reviewed - and the finish gate (`flow-finish-gate.sh`) refuses a PR
   whose branch carries no receipt. Record it in the DELEGATED direction: the
   implementer is derived from the Step 4 exec stream and the rollout its thread
   names, the reviewer from this session's transcript. Never record it as a skip
   (no reviewer was absent) and never as a `/codex:code_review` run (that would
   be Codex reviewing its own code). Only in a repository that already keeps
   receipts - writing one elsewhere would enrol it:

   ```bash
   CM_RECEIPT=~/.claude/scripts/counter-model-receipt.py
   [ -f "$CM_RECEIPT" ] || CM_RECEIPT="${CLAUDE_PLUGIN_ROOT}/scripts/counter-model-receipt.py"
   if [ -d docs/measurements/counter-model ] && [ -f "$CM_RECEIPT" ]; then
       python3 "$CM_RECEIPT" write --dir docs/measurements/counter-model \
           --issue "$ISSUE_NUM" --branch "$(git branch --show-current)" --status ran \
           --implementer-exec-log "$CODEX_OUTPUT" \
           --reviewer-session-id "$CLAUDE_CODE_SESSION_ID" \
           --accepted <findings fixed> --rejected <n> --deferred <n>
       git add docs/measurements/counter-model/*.json
   fi
   ```

   A refusal (non-zero, no file) means an identity could not be derived - say
   so in the PR body; do not hand-write a receipt to get past the gate.
<!-- slot: FIX_REEXEC -->
3. **Re-execute Codex** with the fix prompt, under the same sandbox as Step 4:
   `workspace-write` unless the caller supplied `CODEX_AUTO_SANDBOX` (issue
   #1285). Never choose `danger-full-access` yourself - only a caller that
   states it, as data, may.
   The retry gets the same treatment as the first run (issue #798): redirect
   rather than pipe, exit captured in the SAME block, payload checked. A fix
   attempt that failed silently is exactly how a fix loop burns its two retries
   on nothing and then reports the ORIGINAL gate failure as the diagnosis:
   ```bash
   CODEX_FIX_OUTPUT="/tmp/codex-fix-${ISSUE_NUM}-${RETRY}.jsonl"
   # Sandbox mode (issue #1285). A caller that knows codex's own sandbox cannot
   # start where it runs supplies CODEX_AUTO_SANDBOX as data - Kyle does, for the
   # session containers it starts, where workspace-write exits 0 having executed
   # nothing. Unset keeps #735's workspace-write. Any other value is refused, never
   # defaulted: a silent fallback would re-create the inert run this exists to end.
   CODEX_SANDBOX="${CODEX_AUTO_SANDBOX:-workspace-write}"
   case "$CODEX_SANDBOX" in
       workspace-write) ;;
       danger-full-access) ;;
       *) echo "ERROR: CODEX_AUTO_SANDBOX='$CODEX_SANDBOX' is not workspace-write or danger-full-access; refusing to run codex (issue #1285)"; exit 1 ;;
   esac

   codex exec \
       --json \
       -C "$WORKTREE_PATH" \
       --sandbox "$CODEX_SANDBOX" \
       "$FIX_PROMPT" < /dev/null > "$CODEX_FIX_OUTPUT" 2>&1   # </dev/null: non-TTY EOF so codex never blocks reading stdin

   CODEX_FIX_EXIT=$?
   echo "codex fix attempt exited $CODEX_FIX_EXIT; output: $CODEX_FIX_OUTPUT"
   tail -40 "$CODEX_FIX_OUTPUT"
   ```
   Then check the payload, bare and with LITERAL values (the retry block above
   prints both - #798 review):
   ```bash
   ~/.claude/scripts/delegated-run-check.sh /tmp/codex-fix-42-1.jsonl 0 --lane codex --expect-tools
   ```
<!-- slot: STEP6_ESCALATION -->
<!-- slot: IMPLEMENTER_TRAILER -->
   - Note Codex as implementer in the commit body
<!-- slot: PR_DELEGATION_NOTE -->
     - Note that implementation was delegated to Codex CLI
<!-- slot: IMPLEMENTER_SUMMARY -->
  Implementer: Codex CLI (codex exec)
<!-- slot: FINAL_SUMMARY_EXTRA -->
<!-- slot: RESUME_EXEC_LINE -->
    /codex:exec "<prompt>"   (if step 4 failed)
<!-- slot: ERROR_ROWS -->
- **Codex not installed:** Stop at step 4, suggest `npm install -g @openai/codex`
- **Codex execution fails:** Stop at step 4, show last 20 lines of JSONL output
- **Codex makes no changes:** Stop at step 4, suggest reviewing the prompt
- **Review finds critical issues:** Stop at step 5, offer to re-prompt or hand off
- **Quality gates fail after retries:** Stop at step 6, show error output
- **Push/PR fails:** Stop at step 7, suggest manual resolution
