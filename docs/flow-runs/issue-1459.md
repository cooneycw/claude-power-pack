# Flow run record - issue #1459

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=2e7a4d0aa2b9477f881bb71177903071 -->
## Run 1

- Run-id:            2e7a4d0aa2b9477f881bb71177903071
- Run-start:         0320c43686dbf40c21b7aac533cb5f099ffaf0ef
- Issue:             #1459
- Base SHA:          0320c43686dbf40c21b7aac533cb5f099ffaf0ef
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          master:kyle (mailbox message 6518, replying to plan 6517), with the local_credentials addition
- Recorded at:       2026-10-17T02:50:00Z

### Section B evidence
Commits since filing: 77530ec (#1458, same file, network probe only - not the credential block), 145d42d, 0320c43. Merged PRs: #1463, #1464, #1465. Duplicates: none (#1450 is the origin). Sibling worktrees: none.

### Section C - the approved plan
1. `.claude/commands/codex/code_review.md` - reviewer env: HOME = empty temp dir with CODEX_HOME pinned; GIT_CONFIG_NOSYSTEM=1; GIT_CONFIG_GLOBAL = temp file holding only the caller's safe.directory entries; GIT_CONFIG_PARAMETERS resetting credential.helper and http.extraheader (replacing GIT_CONFIG_COUNT/KEY_0); unset SSH_AUTH_SOCK and DBUS_SESSION_BUS_ADDRESS; GIT_SSH_COMMAND=false; temp dirs removed on every exit path. A MEASURED local_credentials (present|absent|unknown) on the relay banner, naming config keys only, never values. The claim reworded to what is and is not withdrawn.
2. `scripts/counter-model-receipt.py` - a `--local-credentials` field, recorded as measured, refused on skipped and delegated receipts.
3. `.claude/commands/flow/auto.md` - pass --local-credentials with the receipt write.
4. `tests/test_code_review_network_fence.py` - behavioural tests per path, plus local_credentials detection, and a proof that a token value never appears in output.
5. `tests/test_counter_model_review.py` - receipt field tests.
Scope: ~5 source files plus regenerated mirrors, ~250 lines. Risks: the HOME swap is broad (cold reviewer caches; a live codex run confirms it still starts); a local credential is measured, not removed.
